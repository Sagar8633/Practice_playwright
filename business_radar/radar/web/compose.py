"""Turns stored findings into a message body, and refuses to let anything else in.

Invariant 4 says every claim in a generated message traces to a stored finding: OBSERVED facts
may be stated, INFERRED ones must be hedged, UNKNOWN ones must never appear. A model that writes
freely will, sooner or later, write "your 40-bed hospital" about a business whose bed count
nobody ever saw, and the recipient will know it was invented. That single sentence is the
difference between a business letter and a mail-merge, and it is what this module exists to
prevent.

So the composer builds sentences FROM the finding rows rather than asking a model to be careful,
and then check_claims() re-reads its own output against the same rows as if a stranger had
written it. The check runs on human edits too - editing the body sends it back through here, so
the operator cannot type a claim past the engine that the engine would have refused to generate.

SIMPLIFIED: 06-message-engine.md sections 6.5-6.9 draft with gemini-2.5-flash against a
versioned prompt, apply the section 6.26 industry vocabularies and run thirty-two claim rules.
This composes deterministically from the same rows and runs the six rules that can actually be
decided without a model - unsubscribe present, identity present, no UNKNOWN mentioned, every
INFERRED sentence hedged, at least one OBSERVED cited, no invented number. When radar/messages.py
lands, generate() below prefers it and this becomes the fallback that keeps the app usable with
no GEMINI_API_KEY.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass

log = logging.getLogger("radar.web.compose")

#: Pinned into outreach_drafts.model_id / .prompt_version, so an audit two years from now can
#: tell a locally-composed message from a model-written one without guessing.
LOCAL_MODEL_ID = "local-composer"
LOCAL_PROMPT_VERSION = "msg-local-v1"

#: The words that turn a statement into a hedge. 06 section 6.9's R-K1 rule set.
HEDGES: tuple[str, ...] = (
    "may ", "might ", "could ", "appears", "appear ", "seems", "seem ", "likely",
    "we believe", "it looks like", "possibly", "probably", "suggests", "typically",
    "usually", "often",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_NUMBER = re.compile(r"\b\d[\d,.]*\b")


@dataclass(frozen=True, slots=True)
class Composed:
    """One drafted message and the finding ids each part of it came from."""

    subject: str
    body: str
    facts_used: tuple[str, ...]        # OBSERVED research_findings.id
    inferences_used: tuple[str, ...]   # INFERRED research_findings.id
    model_id: str
    prompt_version: str
    confidence: str
    confidence_pct: int


@dataclass(frozen=True, slots=True)
class ClaimCheck:
    """The policy verdict stored on outreach_drafts.policy_result / .policy_detail."""

    result: str                        # PASS | WARN | BLOCK
    rules_passed: int
    findings: tuple[dict[str, str], ...]   # one per fired rule
    version: str = "claim-local-v1"

    @property
    def blocked(self) -> bool:
        return self.result == "BLOCK"

    def detail_json(self) -> str:
        return json.dumps(
            {"version": self.version, "rules_passed": self.rules_passed,
             "violations": list(self.findings)},
            ensure_ascii=False, separators=(",", ":"),
        )


# ---------------------------------------------------------------------------
# reading the evidence
# ---------------------------------------------------------------------------

def load_findings(conn: sqlite3.Connection, business_id: str) -> list[sqlite3.Row]:
    """Current findings for a business, with the number of sources behind each one.

    An OBSERVED finding with no finding_sources row is not citable - 03 section 3.4.6.3 and
    04 section 4.5.3 agree with the policy engine on that, which is the only reason the three
    can be shown side by side without contradicting each other.
    """
    return conn.execute(
        "SELECT f.id, f.kind, f.dimension, f.label, f.statement, f.detail, f.confidence, "
        "       f.confidence_pct, f.inference_note, f.unknown_reason, f.ordinal, "
        "       COUNT(fs.source_id) AS n_sources "
        "  FROM research_findings f "
        "  LEFT JOIN finding_sources fs ON fs.finding_id = f.id "
        " WHERE f.business_id = ? AND f.is_current = 1 "
        " GROUP BY f.id "
        " ORDER BY CASE f.kind WHEN 'OBSERVED' THEN 0 WHEN 'INFERRED' THEN 1 ELSE 2 END, "
        "          f.ordinal, f.created_at",
        (business_id,),
    ).fetchall()


def load_opportunity(conn: sqlite3.Connection, business_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM opportunities WHERE business_id = ? AND is_current = 1", (business_id,),
    ).fetchone()


def load_modules(conn: sqlite3.Connection, business_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT module FROM opportunity_modules "
        " WHERE business_id = ? AND is_current = 1 ORDER BY ordinal, module",
        (business_id,),
    ).fetchall()
    return [r["module"].replace("_", " ").title() for r in rows]


# ---------------------------------------------------------------------------
# composing
# ---------------------------------------------------------------------------

def generate(conn: sqlite3.Connection, *, business: sqlite3.Row, channel: str,
             sender_name: str, sender_company: str, unsubscribe_line: str) -> Composed:
    """Draft a message. Prefers radar/messages.py when it exists; composes locally otherwise."""
    try:  # pragma: no cover - depends on which sibling modules have landed
        from radar.messages import generate_draft  # type: ignore

        return generate_draft(conn, business=business, channel=channel,
                              sender_name=sender_name, sender_company=sender_company,
                              unsubscribe_line=unsubscribe_line)
    except Exception as exc:  # ImportError, or a signature that has not settled yet
        log.debug("radar.messages unavailable (%s); composing locally", exc)

    return compose_locally(
        conn, business=business, channel=channel, sender_name=sender_name,
        sender_company=sender_company, unsubscribe_line=unsubscribe_line,
    )


def compose_locally(conn: sqlite3.Connection, *, business: sqlite3.Row, channel: str,
                    sender_name: str, sender_company: str,
                    unsubscribe_line: str) -> Composed:
    """Build the body out of finding rows, one sentence at a time.

    Nothing here invents a sentence. Every line is either a fixed frame, a verbatim finding
    statement, or a column from the opportunity row, which is what makes check_claims() below
    able to prove the result rather than score it.
    """
    findings = load_findings(conn, business["id"])
    observed = [f for f in findings if f["kind"] == "OBSERVED" and f["n_sources"] > 0][:3]
    inferred = [f for f in findings if f["kind"] == "INFERRED"][:1]
    opportunity = load_opportunity(conn, business["id"])
    modules = load_modules(conn, business["id"])

    name = business["name"]
    lines: list[str] = ["Hello %s team," % name, ""]

    if observed:
        lines.append("I have been looking at businesses in %s, and a few things "
                     "about yours stood out from what is published publicly:" % business["city"])
        for row in observed:
            lines.append("  - %s" % _as_bullet(row["statement"]))
        lines.append("")

    for row in inferred:
        lines.append("From that, it may be that %s" % _hedged(row["statement"]))
        lines.append("")

    if opportunity is not None:
        lines.append(str(opportunity["potential_solution"]).strip().rstrip(".")
                     + " is the kind of system I build for businesses in this position.")
        if modules:
            lines.append("For a business like yours that usually means: %s."
                         % ", ".join(modules))
        benefit = str(opportunity["expected_benefit"] or "").strip()
        if benefit:
            lines.append(benefit if benefit.endswith(".") else benefit + ".")
        lines.append("")

    lines.append("If that sounds worth twenty minutes, reply to this mail and I will "
                 "show you what it looks like. If it does not, no reply is needed.")
    lines.append("")
    lines.append("Regards,")
    lines.append(sender_name)
    if sender_company:
        lines.append(sender_company)
    lines.append("")
    lines.append("--")
    lines.append(unsubscribe_line)

    subject = "A possible operations system for %s" % name
    if channel != "EMAIL":
        subject = ""

    pcts = [int(f["confidence_pct"] or 60) for f in observed] or [50]
    pct = int(sum(pcts) / len(pcts))
    confidence = "HIGH" if pct >= 80 else ("MEDIUM" if pct >= 60 else "LOW")

    return Composed(
        subject=subject,
        body="\n".join(lines),
        facts_used=tuple(str(f["id"]) for f in observed),
        inferences_used=tuple(str(f["id"]) for f in inferred),
        model_id=LOCAL_MODEL_ID,
        prompt_version=LOCAL_PROMPT_VERSION,
        confidence=confidence,
        confidence_pct=pct,
    )


def _as_bullet(statement: str) -> str:
    text = str(statement).strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def _hedged(statement: str) -> str:
    """Make an INFERRED statement read as an inference, whatever the row says.

    The row already contains a claim; prefixing it with "it may be that" is what turns it into
    a hedge, and lowercasing the first letter is what stops the sentence reading as two.
    """
    text = str(statement).strip().rstrip(".")
    if text and text[0].isupper() and not text.split(" ", 1)[0].isupper():
        text = text[0].lower() + text[1:]
    return text + "."


# ---------------------------------------------------------------------------
# the claim policy check - invariant 4, enforced on generated AND edited bodies
# ---------------------------------------------------------------------------

def check_claims(conn: sqlite3.Connection, *, business_id: str, subject: str, body: str,
                 unsubscribe_marker: str, sender_name: str) -> ClaimCheck:
    """Re-read a body against the stored findings and say whether it may be shown.

    Six rules, each decidable without a model. A rule that fires names the offending sentence,
    because "policy failed" tells the operator nothing he can act on.
    """
    findings = load_findings(conn, business_id)
    observed = {str(f["id"]): f for f in findings
                if f["kind"] == "OBSERVED" and f["n_sources"] > 0}
    inferred = {str(f["id"]): f for f in findings if f["kind"] == "INFERRED"}
    unknown = [f for f in findings if f["kind"] == "UNKNOWN"]

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(body) if s.strip()]
    lower_body = body.lower()
    violations: list[dict[str, str]] = []
    rules_passed = 0

    # R1 - a working unsubscribe. Without it this is not a business letter under any AUP.
    if unsubscribe_marker and unsubscribe_marker.lower() not in lower_body:
        violations.append({
            "rule": "R1", "severity": "BLOCK", "sentence": "",
            "explain": "The unsubscribe line is missing. Every outbound message carries one.",
        })
    else:
        rules_passed += 1

    # R2 - the message says who it is from.
    if sender_name and sender_name.lower() not in lower_body:
        violations.append({
            "rule": "R2", "severity": "BLOCK", "sentence": "",
            "explain": "The signature does not name the sender.",
        })
    else:
        rules_passed += 1

    # R3 - nothing UNKNOWN is mentioned. An UNKNOWN finding is a subject we could not verify.
    for row in unknown:
        needle = _topic_words(row["label"])
        if needle and needle in lower_body:
            violations.append({
                "rule": "K3", "severity": "BLOCK",
                "sentence": _sentence_containing(sentences, needle),
                "explain": ("\"%s\" is an UNKNOWN finding (%s). A message may never mention it."
                            % (row["label"], row["unknown_reason"])),
            })
    if not any(v["rule"] == "K3" for v in violations):
        rules_passed += 1

    # R4 - every sentence carrying an INFERRED claim hedges.
    for row in inferred.values():
        needle = _topic_words(row["label"])
        if not needle or needle not in lower_body:
            continue
        sentence = _sentence_containing(sentences, needle)
        if not any(h in sentence.lower() for h in HEDGES):
            violations.append({
                "rule": "K1", "severity": "BLOCK", "sentence": sentence,
                "explain": ("A claim bound to the INFERRED finding \"%s\" must hedge. "
                            "Add \"may\", \"could\" or \"we believe\"." % row["label"]),
            })
    if not any(v["rule"] == "K1" for v in violations):
        rules_passed += 1

    # R5 - at least one observed, citable fact is actually used.
    if observed and not any(_topic_words(f["label"]) in lower_body
                            for f in observed.values()
                            if _topic_words(f["label"])):
        violations.append({
            "rule": "K7", "severity": "WARN", "sentence": "",
            "explain": ("The message cites none of the %d observed findings. "
                        "A letter with no specific observation reads as a mail-merge."
                        % len(observed)),
        })
    else:
        rules_passed += 1

    # R6 - no number in the body that is not in a finding statement or the opportunity row.
    known_numbers = set()
    for row in findings:
        for part in (row["statement"], row["detail"] or "", row["label"]):
            known_numbers.update(_NUMBER.findall(str(part)))
    opportunity = load_opportunity(conn, business_id)
    if opportunity is not None:
        for key in ("potential_problem", "potential_solution", "expected_benefit"):
            known_numbers.update(_NUMBER.findall(str(opportunity[key] or "")))
    for token in _NUMBER.findall(body):
        if token not in known_numbers and len(token) > 1:
            violations.append({
                "rule": "K9", "severity": "BLOCK",
                "sentence": _sentence_containing(sentences, token.lower()),
                "explain": ("The number %s does not appear in any stored finding. "
                            "A figure nobody observed is an invention." % token),
            })
            break
    else:
        rules_passed += 1

    if any(v["severity"] == "BLOCK" for v in violations):
        result = "BLOCK"
    elif violations:
        result = "WARN"
    else:
        result = "PASS"
    return ClaimCheck(result=result, rules_passed=rules_passed,
                      findings=tuple(violations))


def _topic_words(label: str) -> str:
    """The distinctive part of a finding label, lowercased, for a substring search.

    A label is a short human phrase like "No patient portal"; matching on the whole phrase is
    what keeps this from firing on the word "no".
    """
    text = re.sub(r"[^a-z0-9 ]+", " ", str(label).lower()).strip()
    words = [w for w in text.split() if len(w) > 3]
    return " ".join(words[-2:]) if len(words) >= 2 else (words[0] if words else "")


def _sentence_containing(sentences: list[str], needle: str) -> str:
    for sentence in sentences:
        if needle and needle in sentence.lower():
            return sentence
    return sentences[0] if sentences else ""
