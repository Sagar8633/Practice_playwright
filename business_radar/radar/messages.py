"""Turn a verified business and its research into one message Sagar can defend.

Without this module the alternative is a mail-merge: the same paragraph, the same opening line,
the same three modules, sent to forty businesses across four cities. That message is
recognisable as a bot on the second copy, and the first person who forwards it to the second
person who received it has all the evidence they need. Worse, a free-writing model will happily
state that a hospital "is managing patients in Excel", because that is the kind of sentence that
appears in sales copy - and nobody researched it.

So this module does two things at once. It personalises per business from the industry module
map and that business's own findings, and it forces the model to emit, alongside the message,
the finding id behind every factual sentence it wrote. Nothing it produces is sent from here:
the output goes to radar/policy.py and then to a human.

The third thing it does is a refusal. No value from business_contacts ever reaches the model -
not an email, not a phone number, not a person's name. The greeting travels through generation
as the literal token <<CONTACT_GREETING>> and is substituted locally, once, after the last model
call and before the first database write, so the policy engine, the approval hash and the sent
message all see the same body. assert_no_contact_values() fails the job loudly rather than
redacting, because a redaction would hide the template bug that produced the leak.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from radar.audit import audit
from radar.channels import unsub_address, unsubscribe_token
from radar.channels.identity import Identity, load_identity
from radar.config import Config, load_config
from radar.db import transaction
from radar.ids import new_id_for
from radar.llm import GeminiClient, LLMError, PiiLeak
from radar.models import Draft, Finding, utc_now
from radar.policy import body_hash, check_draft, sentences, store_policy_result

log = logging.getLogger("radar.messages")

TEMPLATE_VERSION = "email.base@v1+industry@v1"
CONTACT_GREETING = "<<CONTACT_GREETING>>"

# The claim types a claim map entry may carry. Same vocabulary as radar/policy.py.
CLAIM_TYPES = ("FACTUAL", "PROCESS", "SELF", "SELF_CAPABILITY", "OFFER",
               "GREETING", "CTA", "IDENTITY", "COMPLIANCE", "SUBJECT")


# ===========================================================================
# The industry-to-module map (spec section 26)
# ===========================================================================

MODULE_LABELS: dict[str, str] = {
    "PATIENTS": "patient records", "APPOINTMENTS": "appointments",
    "DEPARTMENTS": "departments", "BILLING": "billing", "INVENTORY": "inventory",
    "REPORTS": "reports", "STUDENTS": "student records", "FEES": "fees",
    "ATTENDANCE": "attendance", "STAFF": "staff records", "TRANSPORT": "transport",
    "ADMISSIONS": "admissions", "EXAMINATIONS": "examinations", "PRODUCTION": "production",
    "PURCHASING": "purchasing", "PURCHASES": "purchases", "SALES": "sales",
    "QUALITY": "quality checks", "ORDERS": "orders", "CUSTOMERS": "customer records",
    "RECEIVABLES": "receivables", "DELIVERY": "delivery", "PAYMENTS": "payments",
    "VARIANTS": "size and colour variants", "PROFITABILITY": "profitability",
    "EXPENSES": "expenses", "PROFIT": "profit per unit", "TEST_ORDERS": "test orders",
    "SAMPLES": "sample tracking", "JOB_CARDS": "job cards", "SPARES": "spare parts",
    "LABOUR": "labour hours", "ROOMS": "room status", "BOOKINGS": "bookings",
    "GUESTS": "guest records", "HOUSEKEEPING": "housekeeping", "TABLES": "table management",
    "MENU": "menu and recipes", "LISTINGS": "property listings", "ENQUIRIES": "enquiries",
    "SITE_VISITS": "site visits", "CLIENTS": "client records", "ENGAGEMENTS": "engagements",
    "DOCUMENTS": "documents", "DASHBOARD": "a management dashboard", "WORKFLOW": "workflow",
    "FINANCE": "finance tracking", "ROLES": "role management", "AUDIT": "audit logs",
}

# A REPORTS module is "reports" everywhere, but INVENTORY is "stock" in a shop and "inventory"
# in a factory. Saying "inventory" to a bakery is the small wrong word that reads as a template.
LABEL_OVERRIDES: dict[str, dict[str, str]] = {
    "RETAIL_STORE": {"INVENTORY": "stock"},
    "BAKERY": {"PRODUCTION": "daily production", "INVENTORY": "ingredient stock"},
    "GARAGE": {"INVENTORY": "spare parts stock"},
    "HOTEL": {"INVENTORY": "supplies"},
}


@dataclass(frozen=True, slots=True)
class ModuleProfile:
    category: str
    industry: str
    solution_name: str
    module_keys: tuple[str, ...]
    relevant_area: str
    source: str                      # 'SPEC_26' | 'DERIVED' | 'INDUSTRY_FALLBACK'

    @property
    def labels(self) -> tuple[str, ...]:
        overrides = LABEL_OVERRIDES.get(self.category, {})
        return tuple(overrides.get(k, MODULE_LABELS.get(k, k.lower().replace("_", " ")))
                     for k in self.module_keys)

    def label_for(self, key: str) -> str:
        overrides = LABEL_OVERRIDES.get(self.category, {})
        return overrides.get(key, MODULE_LABELS.get(key, key.lower().replace("_", " ")))


def _profile(category: str, industry: str, solution: str, keys: str, area: str,
             source: str) -> ModuleProfile:
    return ModuleProfile(category, industry, solution,
                         tuple(k.strip() for k in keys.split(",")), area, source)


MODULE_MAP: dict[str, ModuleProfile] = {
    "HOSPITAL": _profile(
        "HOSPITAL", "HEALTHCARE", "Hospital Operations Platform",
        "PATIENTS,APPOINTMENTS,DEPARTMENTS,BILLING,INVENTORY,REPORTS",
        "patient records, appointments and billing", "SPEC_26"),
    "DIAGNOSTIC_CENTER": _profile(
        "DIAGNOSTIC_CENTER", "HEALTHCARE", "Diagnostic Centre Operations Platform",
        "PATIENTS,TEST_ORDERS,SAMPLES,REPORTS,BILLING,INVENTORY",
        "test orders, reports and billing", "DERIVED"),
    "SCHOOL": _profile(
        "SCHOOL", "EDUCATION", "School Management System",
        "STUDENTS,FEES,ATTENDANCE,STAFF,TRANSPORT,REPORTS",
        "student records, fees and attendance", "SPEC_26"),
    "COLLEGE": _profile(
        "COLLEGE", "EDUCATION", "College Management System",
        "ADMISSIONS,STUDENTS,DEPARTMENTS,FEES,EXAMINATIONS,REPORTS",
        "admissions, fees and examination records", "SPEC_26"),
    "MANUFACTURER": _profile(
        "MANUFACTURER", "MANUFACTURING", "Manufacturing Management Platform",
        "INVENTORY,PRODUCTION,PURCHASING,SALES,QUALITY,REPORTS",
        "inventory, production and purchase tracking", "SPEC_26"),
    "DISTRIBUTOR": _profile(
        "DISTRIBUTOR", "DISTRIBUTION", "Distribution Management System",
        "INVENTORY,ORDERS,CUSTOMERS,RECEIVABLES,SALES,REPORTS",
        "inventory, orders and receivables", "SPEC_26"),
    "VEHICLE_DEALER": _profile(
        "VEHICLE_DEALER", "AUTOMOBILE", "Dealership Management System",
        "INVENTORY,PURCHASES,EXPENSES,SALES,PROFIT,CUSTOMERS",
        "vehicle stock, purchases and sales", "SPEC_26"),
    "GARAGE": _profile(
        "GARAGE", "AUTOMOBILE", "Service Workshop Management System",
        "JOB_CARDS,SPARES,LABOUR,BILLING,CUSTOMERS,REPORTS",
        "job cards, spare parts and billing", "DERIVED"),
    "HOTEL": _profile(
        "HOTEL", "HOSPITALITY", "Hotel Operations Platform",
        "ROOMS,BOOKINGS,GUESTS,HOUSEKEEPING,BILLING,REPORTS",
        "bookings, room status and billing", "DERIVED"),
    "RESTAURANT": _profile(
        "RESTAURANT", "HOSPITALITY", "Restaurant Operations System",
        "ORDERS,TABLES,MENU,INVENTORY,BILLING,REPORTS",
        "orders, inventory and billing", "DERIVED"),
    "BAKERY": _profile(
        "BAKERY", "RETAIL", "Bakery Operations System",
        "ORDERS,PRODUCTION,INVENTORY,DELIVERY,CUSTOMERS,PAYMENTS",
        "orders, production and delivery", "SPEC_26"),
    "RETAIL_STORE": _profile(
        "RETAIL_STORE", "RETAIL", "Retail Inventory and Sales System",
        "INVENTORY,VARIANTS,PURCHASING,SALES,CUSTOMERS,PROFITABILITY",
        "stock, variants and sales", "SPEC_26"),
    "REAL_ESTATE_AGENCY": _profile(
        "REAL_ESTATE_AGENCY", "REAL_ESTATE", "Property Sales Management System",
        "LISTINGS,ENQUIRIES,SITE_VISITS,BOOKINGS,PAYMENTS,REPORTS",
        "listings, enquiries and bookings", "DERIVED"),
}

INDUSTRY_FALLBACK: dict[str, ModuleProfile] = {
    "HEALTHCARE": _profile("OTHER", "HEALTHCARE", "Healthcare Operations Platform",
                           "PATIENTS,APPOINTMENTS,BILLING,INVENTORY,REPORTS",
                           "patient records and billing", "INDUSTRY_FALLBACK"),
    "EDUCATION": _profile("OTHER", "EDUCATION", "Education Management System",
                          "STUDENTS,FEES,ATTENDANCE,STAFF,REPORTS",
                          "student records and fees", "INDUSTRY_FALLBACK"),
    "AUTOMOBILE": _profile("OTHER", "AUTOMOBILE", "Automotive Business Management System",
                           "INVENTORY,PURCHASES,SALES,CUSTOMERS,REPORTS",
                           "stock, sales and customers", "INDUSTRY_FALLBACK"),
    "MANUFACTURING": _profile("OTHER", "MANUFACTURING", "Manufacturing Management Platform",
                              "INVENTORY,PRODUCTION,PURCHASING,SALES,REPORTS",
                              "inventory and production", "INDUSTRY_FALLBACK"),
    "RETAIL": _profile("OTHER", "RETAIL", "Retail Management System",
                       "INVENTORY,SALES,PURCHASING,CUSTOMERS,REPORTS",
                       "stock and sales", "INDUSTRY_FALLBACK"),
    "HOSPITALITY": _profile("OTHER", "HOSPITALITY", "Hospitality Operations System",
                            "BOOKINGS,ORDERS,INVENTORY,BILLING,REPORTS",
                            "bookings and billing", "INDUSTRY_FALLBACK"),
    "DISTRIBUTION": _profile("OTHER", "DISTRIBUTION", "Distribution Management System",
                             "INVENTORY,ORDERS,RECEIVABLES,CUSTOMERS,REPORTS",
                             "orders and receivables", "INDUSTRY_FALLBACK"),
    "REAL_ESTATE": _profile("OTHER", "REAL_ESTATE", "Property Business Management System",
                            "LISTINGS,ENQUIRIES,PAYMENTS,CUSTOMERS,REPORTS",
                            "listings and enquiries", "INDUSTRY_FALLBACK"),
    "PROFESSIONAL_SERVICES": _profile("OTHER", "PROFESSIONAL_SERVICES",
                                      "Practice Management System",
                                      "CLIENTS,ENGAGEMENTS,DOCUMENTS,BILLING,REPORTS",
                                      "client records and billing", "INDUSTRY_FALLBACK"),
    "OTHER": _profile("OTHER", "OTHER", "Custom Business Management System",
                      "DASHBOARD,WORKFLOW,FINANCE,INVENTORY,REPORTS,ROLES,AUDIT",
                      "day-to-day operations and reporting", "INDUSTRY_FALLBACK"),
}


def resolve_modules(category: str | None, industry: str | None) -> ModuleProfile:
    """The modules this business would recognise as its own daily work.

    Category first, because a bakery and a clothes shop are both RETAIL and want different
    words. Industry is the fallback, and OTHER/OTHER is the generic system from spec section 13.
    """
    profile = MODULE_MAP.get((category or "").upper())
    if profile is not None:
        return profile
    return INDUSTRY_FALLBACK.get((industry or "").upper(), INDUSTRY_FALLBACK["OTHER"])


# ===========================================================================
# The PII scrubber: nothing from business_contacts reaches the model
# ===========================================================================

class ContactLeak(RuntimeError):
    """A business_contacts value was found in an outbound LLM payload."""


_BARE_SHAPES: tuple[tuple[str, str], ...] = (
    (r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "an email address"),
    (r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b", "an Indian mobile number"),
    (r"\b[A-Z]{5}\d{4}[A-Z]\b", "a PAN"),
    (r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d]Z[A-Z\d]\b", "a GSTIN"),
)


def assert_no_contact_values(payload: str, *, business_id: str, conn: sqlite3.Connection,
                             allow: Sequence[str] = ()) -> None:
    """Fail the job rather than send a contact detail to a free-tier API.

    Free-tier content may be used by Google to improve their products, so a proprietor's mobile
    number in a drafting prompt is a contact detail collected for one purpose being handed to a
    third party for another. Under the DPDP Act that is a purpose-limitation failure, and it is
    not one a disclaimer fixes.

    Loads every business_contacts row for this business, searches the assembled prompt for each
    stored value, and then searches for the bare shapes that are not in our contact table but
    are obviously somebody's - a scraped page excerpt can carry a phone number we never stored.

    `allow` is Sagar's own identity block - his from-address, his reply-to, his phone, the
    unsubscribe mailbox. Those are contact details he is choosing to disclose, they are printed
    in the signature of every message, and a scrubber that flagged them would flag every
    compliant draft.

    Not a warning, and not a redaction: a redaction here would hide the template bug that
    produced it, and the next template bug would leak something the redactor did not know about.
    """
    rows = conn.execute(
        "SELECT value_raw, value_norm, value_display, phone_e164, wa_id, person_name "
        "FROM business_contacts WHERE business_id = ?",
        (business_id,),
    ).fetchall()
    haystack = payload.casefold()
    for row in rows:
        for column in ("value_raw", "value_norm", "value_display", "phone_e164", "wa_id",
                       "person_name"):
            value = row[column]
            if value and len(str(value)) >= 4 and str(value).casefold() in haystack:
                raise ContactLeak(
                    f"business_contacts.{column} for {business_id} appears in an LLM payload")
    scanned = payload
    for permitted in allow:
        if permitted:
            scanned = scanned.replace(permitted, "[our own contact detail]")
    for pattern, what in _BARE_SHAPES:
        match = re.search(pattern, scanned)
        if match:
            raise ContactLeak(
                f"the prompt for {business_id} contains {what} ({match.group(0)[:4]}...); "
                f"a contact detail in a finding is still a contact detail")


# ===========================================================================
# The draft context
# ===========================================================================

@dataclass(slots=True)
class DraftContext:
    """Everything the model is allowed to see, and nothing else."""
    business_id: str
    campaign_id: str
    business_name: str
    city: str
    industry: str
    category: str
    size_band: str
    website_host: str
    channel: str
    profile: ModuleProfile
    identity: Identity
    findings: list[Finding] = field(default_factory=list)
    opportunity: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    unsubscribe_address: str = ""
    unsubscribe_token: str = ""
    message_id: str = ""

    @property
    def observed(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "OBSERVED" and f.source_ids]

    @property
    def inferred(self) -> list[Finding]:
        return [f for f in self.findings if f.kind == "INFERRED"]

    @property
    def solution_name(self) -> str:
        if self.opportunity and self.opportunity.get("potential_solution"):
            return str(self.opportunity["potential_solution"])
        return self.profile.solution_name

    def demo_labels(self) -> tuple[str, ...]:
        """Module labels we may offer to demonstrate: the intersection of this business's
        modules and what we have actually built (rule M2)."""
        declared = set(self.identity.demo_modules)
        return tuple(self.profile.label_for(k) for k in self.profile.module_keys
                     if k in declared)


def build_context(
    conn: sqlite3.Connection,
    business_id: str,
    channel: str,
    *,
    config: Config,
    identity: Identity,
    message_id: str,
    contact_norm: str,
    campaign_id: str | None = None,
) -> DraftContext:
    """Assemble the research context. No contact value is read into it."""
    business = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
    if business is None:
        raise ValueError(f"no businesses row {business_id!r}")

    findings = [
        Finding.from_row(row) for row in conn.execute(
            """
            SELECT f.*, group_concat(fs.source_id, ',') AS source_ids
              FROM research_findings f
              LEFT JOIN finding_sources fs ON fs.finding_id = f.id
             WHERE f.business_id = ? AND f.is_current = 1 AND f.kind <> 'UNKNOWN'
             GROUP BY f.id
             ORDER BY f.kind DESC, f.weight DESC, f.ordinal
            """,
            (business_id,),
        ).fetchall()
    ]
    opportunity_row = conn.execute(
        "SELECT * FROM opportunities WHERE business_id = ? AND is_current = 1", (business_id,)
    ).fetchone()
    sources = [
        {"name": r["name"], "type": r["source_type"], "checked_at": r["checked_at"]}
        for r in conn.execute(
            "SELECT name, source_type, checked_at FROM sources WHERE business_id = ? "
            "ORDER BY checked_at DESC LIMIT 8", (business_id,)).fetchall()
    ]

    token = unsubscribe_token(message_id, contact_norm)
    return DraftContext(
        business_id=business_id,
        campaign_id=campaign_id or business["first_seen_campaign_id"],
        business_name=business["name"],
        city=business["city"],
        industry=business["industry"],
        category=business["category"],
        size_band=business["size_band"],
        website_host=(business["website_domain"] or ""),
        channel=channel.upper(),
        profile=resolve_modules(business["category"], business["industry"]),
        identity=identity,
        findings=findings,
        opportunity=dict(opportunity_row) if opportunity_row is not None else None,
        sources=sources,
        unsubscribe_address=unsub_address(identity.from_address, token),
        unsubscribe_token=token,
        message_id=message_id,
    )


# ===========================================================================
# The deterministic render (spec section 24's skeleton)
# ===========================================================================

def _and_list(items: Sequence[str]) -> str:
    """"a, b and c". A comma-separated list in a sentence reads as a database dump."""
    items = list(items)
    if len(items) <= 1:
        return items[0] if items else ""
    return f"{', '.join(items[:-1])} and {items[-1]}"


def render_template(ctx: DraftContext) -> tuple[str | None, str, list[dict[str, Any]]]:
    """The spec section 24 skeleton, filled from this business's own findings.

    This is not a fallback in the apologetic sense. It is the baseline the model is asked to
    improve on, it is what runs when the free tier is exhausted or the key is absent, and it is
    what the policy engine is tested against with no model involved at all - so a weak model can
    only fail to improve on a message that was already legal.
    """
    ident = ctx.identity
    labels = ", ".join(ctx.profile.labels[:3])
    claims: list[dict[str, Any]] = []
    lines: list[str] = []

    def claim(text: str, claim_type: str, finding_ids: Sequence[str] = ()) -> None:
        """One claim entry per sentence, split the way the checker splits.

        This is the whole reason rule T3 exists: a map indexed on a different segmentation from
        the checker's describes text the checker cannot find, and an entry that does not bind is
        the same as no entry at all.
        """
        for piece in sentences(text) or [text]:
            claims.append({"text": piece, "type": claim_type,
                           "finding_ids": list(finding_ids), "bound_by": "TEMPLATE"})

    def para(text: str, claim_type: str, finding_ids: Sequence[str] = ()) -> None:
        lines.append(text)
        claim(text, claim_type, finding_ids)

    if ctx.channel == "WHATSAPP":
        subject = None
        para(CONTACT_GREETING, "GREETING")
        para(f"We build customised business-management software for established businesses.",
             "SELF")
        observed = ctx.observed[:1]
        if observed:
            para(observed[0].statement, "FACTUAL", [observed[0].id])
        para(f"A {ctx.solution_name} would bring {ctx.profile.relevant_area} into one place.",
             "OFFER")
        para("If this is relevant, I would be happy to show you a short demonstration.", "CTA")
        para(f"{ident.sender_name}"
             + (f", {ident.company_name}" if ident.company_name else ""), "IDENTITY")
        para("If you would rather not hear from us, reply with the word STOP and we will not "
             "contact you again.", "COMPLIANCE")
        return subject, "\n\n".join(lines), claims

    subject = f"A possible {ctx.solution_name} for {ctx.business_name}"
    claim(subject, "SUBJECT")

    para(f"{CONTACT_GREETING}", "GREETING")

    who_we_are = ("We build customised business-management software for established "
                  "organisations.")
    how_we_found_you = (f"While researching businesses in {ctx.city} we came across "
                        f"{ctx.business_name} and reviewed its publicly available business "
                        "information.")
    lines.append(f"{who_we_are} {how_we_found_you}")
    claim(who_we_are, "SELF")
    claim(how_we_found_you, "PROCESS")

    observed = ctx.observed[:2]
    inferred = ctx.inferred[:1]
    body_block: list[str] = []
    if observed:
        first = observed[0]
        stated = first.statement.rstrip().rstrip(".") + "."
        body_block.append(stated)
        claim(stated, "FACTUAL", [first.id])
    if inferred:
        hedged = (f"Based on the nature of operations of this kind, we believe "
                  f"{ctx.profile.relevant_area} may be areas where a single system could give "
                  "management a clearer picture.")
        body_block.append(hedged)
        claim(hedged, "FACTUAL", [inferred[0].id])
    else:
        offer = (f"A {ctx.solution_name} typically brings {ctx.profile.relevant_area} into one "
                 "place, with a single view for management.")
        body_block.append(offer)
        claim(offer, "OFFER")
    lines.append(" ".join(body_block))

    demo = ctx.demo_labels()[:4]
    if demo:
        demo_line = ("We are building demonstration systems for businesses in this category, "
                     f"covering areas such as {_and_list(demo)}.")
        para(demo_line, "SELF_CAPABILITY")

    para("If this is relevant to your organisation, I would be happy to show you a short "
         "demonstration and discuss whether such a system could fit the way you work today.",
         "CTA")

    signature = ident.signature_lines()
    lines.append("\n".join(signature))
    for line in signature:
        claim(line, "IDENTITY")

    opt_out = ("If this is not the right address, or you would rather not hear from us, reply "
               "with the word STOP and we will not contact you again.")
    para(opt_out, "COMPLIANCE")
    if ctx.unsubscribe_address:
        para(f"You can also write to {ctx.unsubscribe_address}.", "COMPLIANCE")

    return subject, "\n\n".join(lines), claims


# ===========================================================================
# The Gemini call
# ===========================================================================

SYSTEM_PROMPT = """You write one short business email at a time, for a small software studio in
Maharashtra, India. You are writing to a business that has never heard of us.

Absolute rules, in order of importance:
1. Every sentence that asserts anything about the recipient must be supported by one of the
   RESEARCH FINDINGS you are given, and you must return its finding id in the claim map.
2. A finding marked OBSERVED may be stated plainly. A finding marked INFERRED must be hedged in
   the same sentence, using words such as "may", "could", "we believe" or "based on the nature
   of". Never state an inference as fact.
3. Never write a sentence that begins "we noticed", "we know", "you are currently using", or
   "your problem is". We did not see inside their business and pretending otherwise is the one
   thing that loses the prospect permanently.
4. Invent nothing: no statistics, no percentages, no client names, no prior relationship, no
   guarantees, no prices, no deadlines, no superlatives.
5. Keep the token <<CONTACT_GREETING>> exactly as it appears, as the first line. It is a
   placeholder that is filled in locally afterwards. Do not translate it or reword it.
6. Reproduce the SIGNATURE BLOCK and the OPT-OUT LINES byte for byte, at the end, in order.
7. Plain text. No markdown, no HTML, no links other than any already in the signature.
8. Under 220 words.

Return JSON only, matching the schema: subject, body, claim_map, confidence. The claim map lists
every sentence of the body with its claim type and the finding ids behind it. Write the body
first and then describe it: a claim map written first becomes a plan the body drifts from."""

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "required": ["subject", "body", "claim_map", "confidence"],
    "propertyOrdering": ["subject", "body", "claim_map", "confidence"],
    "properties": {
        "subject": {"type": "STRING", "nullable": True},
        "body": {"type": "STRING"},
        "claim_map": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": ["text", "type", "finding_ids"],
                "propertyOrdering": ["text", "type", "finding_ids"],
                "properties": {
                    "text": {"type": "STRING"},
                    "type": {"type": "STRING", "enum": list(CLAIM_TYPES)},
                    "finding_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
        "confidence": {
            "type": "OBJECT",
            "required": ["level", "pct", "why"],
            "propertyOrdering": ["level", "pct", "why"],
            "properties": {
                "level": {"type": "STRING", "enum": ["HIGH", "MEDIUM", "LOW"]},
                "pct": {"type": "INTEGER"},
                "why": {"type": "STRING"},
            },
        },
    },
}


def build_prompt(ctx: DraftContext) -> str:
    """The user half of the call. Business facts and findings only - never a contact value."""
    ident = ctx.identity
    parts = [
        "BUSINESS",
        f"  name: {ctx.business_name}",
        f"  city: {ctx.city}",
        f"  industry: {ctx.industry}",
        f"  category: {ctx.category}",
        f"  size band: {ctx.size_band}",
        f"  website host: {ctx.website_host or 'none found'}",
        "",
        "RESEARCH FINDINGS (cite these ids in the claim map)",
    ]
    for finding in ctx.findings[:12]:
        parts.append(f"  [{finding.id}] {finding.kind} ({finding.confidence}) "
                     f"{finding.dimension}: {finding.statement}")
    if not ctx.findings:
        parts.append("  (none)")

    if ctx.opportunity:
        parts += [
            "",
            "OPPORTUNITY",
            f"  problem: {ctx.opportunity.get('potential_problem', '')}",
            f"  solution: {ctx.solution_name}",
            f"  expected benefit: {ctx.opportunity.get('expected_benefit', '')}",
        ]
    parts += [
        "",
        "RECOMMENDED MODULES (use these words, and no module from another category)",
        f"  {', '.join(ctx.profile.labels)}",
        f"  we may offer to demonstrate: {', '.join(ctx.demo_labels()) or 'none'}",
        "",
        "GREETING (first line of the body, verbatim)",
        f"  {CONTACT_GREETING}",
        "",
        "SIGNATURE BLOCK (verbatim, at the end, one line each)",
    ]
    parts += [f"  {line}" for line in ident.signature_lines()]
    parts += [
        "",
        "OPT-OUT LINES (verbatim, after the signature)",
        "  If this is not the right address, or you would rather not hear from us, reply with "
        "the word STOP and we will not contact you again.",
    ]
    if ctx.unsubscribe_address:
        parts.append(f"  You can also write to {ctx.unsubscribe_address}.")
    return "\n".join(parts)


@dataclass(slots=True)
class Generation:
    subject: str | None
    body: str
    claim_map: list[dict[str, Any]]
    confidence_level: str | None
    confidence_pct: int | None
    model_id: str
    prompt_version: str
    input_tokens: int | None
    output_tokens: int | None
    source: str                      # 'GEMINI' | 'TEMPLATE'
    raw: dict[str, Any] = field(default_factory=dict)


def generate_message(ctx: DraftContext, config: Config,
                     conn: sqlite3.Connection | None = None) -> Generation:
    """Call Gemini through radar/llm.py, and fall back to the deterministic render on failure.

    A missing key, an exhausted free-tier quota, a 429, a malformed response and a dropped
    connection all land in the same place: the template message, which is legal by construction.
    Refusing to produce a draft because a free API was busy would stop the working day for a
    reason that has nothing to do with the recipient - and the template is the message Sagar
    wrote in the spec, not a degraded one.

    The call goes through GeminiClient rather than the SDK directly, because that is where the
    quota ledger, the rate bucket, the capture file and the second PII assertion live. A drafting
    call that skipped it would spend a request nothing recorded.
    """
    prompt_version = config.llm.message_prompt_version
    client = GeminiClient(config.llm, conn)
    if not client.configured:
        log.info("no GEMINI_API_KEY; rendering %s from the template", ctx.business_id)
        return _template_generation(ctx, prompt_version, "no api key")

    ident = ctx.identity
    try:
        response = client.complete_json(
            system=SYSTEM_PROMPT,
            user=build_prompt(ctx),
            schema=_RESPONSE_SCHEMA,
            purpose="MESSAGE",
            prompt_version=prompt_version,
            business_id=ctx.business_id,
            campaign_id=ctx.campaign_id,
            entity_table="outreach_drafts",
            # Our own contact details are printed in every signature on purpose. Everything
            # else that looks like a contact detail is a leak, and assert_no_pii says so.
            protect=(ident.from_address, ident.reply_to, ident.phone_display,
                     ctx.unsubscribe_address, ident.site_url),
            capture_name=f"message-{ctx.business_id}",
        )
    except (LLMError, PiiLeak) as exc:
        log.warning("Gemini draft failed for %s (%s); rendering from the template",
                    ctx.business_id, exc)
        return _template_generation(ctx, prompt_version, f"generation failed: {exc}"[:200])
    except Exception as exc:                            # noqa: BLE001 - any failure falls back
        log.warning("Gemini draft raised for %s (%s); rendering from the template",
                    ctx.business_id, exc)
        return _template_generation(ctx, prompt_version, f"generation raised: {exc}"[:200])

    payload = response.data or {}
    body = str(payload.get("body") or "").strip()
    claim_map = payload.get("claim_map") or []
    if not body or CONTACT_GREETING not in body or not isinstance(claim_map, list):
        # The placeholder is a frozen span. A model that dropped it has produced a body we
        # cannot hydrate, and hydrating by guesswork is how a stranger gets called by the wrong
        # name. The template render is the safe answer.
        log.warning("Gemini returned an unusable draft for %s; rendering from the template",
                    ctx.business_id)
        return _template_generation(ctx, prompt_version, "placeholder or claim map missing")

    confidence = payload.get("confidence") or {}
    return Generation(
        subject=(payload.get("subject") or None) if ctx.channel == "EMAIL" else None,
        body=body,
        claim_map=[c for c in claim_map if isinstance(c, dict)],
        confidence_level=str(confidence.get("level") or "MEDIUM").upper(),
        confidence_pct=_as_int(confidence.get("pct")),
        model_id=response.model_id or config.llm.model,
        prompt_version=prompt_version,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        source="GEMINI",
        raw={"confidence_why": confidence.get("why"), "temperature": config.llm.temperature,
             "requested_model": config.llm.model,
             "capture_sha256": response.capture_sha256,
             "latency_ms": response.latency_ms},
    )


def _template_generation(ctx: DraftContext, prompt_version: str, why: str) -> Generation:
    subject, body, claims = render_template(ctx)
    return Generation(
        subject=subject, body=body, claim_map=claims,
        confidence_level="MEDIUM", confidence_pct=60,
        model_id="template", prompt_version=prompt_version,
        input_tokens=None, output_tokens=None, source="TEMPLATE",
        raw={"reason": why, "template_version": TEMPLATE_VERSION},
    )


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ===========================================================================
# Hydration: the only line in this path that reads business_contacts
# ===========================================================================

def _field(row: Mapping[str, Any] | sqlite3.Row | None, key: str) -> Any:
    """Read one column from a sqlite3.Row or a dict, tolerating either and neither."""
    if row is None:
        return None
    if isinstance(row, sqlite3.Row):
        return row[key] if key in row.keys() else None
    return row.get(key)


def greeting_for(contact: Mapping[str, Any] | sqlite3.Row | None, business_name: str) -> str:
    """"Hello Dr Kulkarni," or "Hello ABC Hospital team," - and nothing in between.

    A message addresses either a verified named contact or the business itself. There is no
    third option, because the third option is guessing at somebody's name.
    """
    person = _field(contact, "person_name")
    verified = bool(_field(contact, "human_verified"))
    if person and verified:
        return f"Hello {person},"
    return f"Hello {business_name} team,"


def hydrate_contact(text: str, contact: Mapping[str, Any] | sqlite3.Row | None,
                    business_name: str) -> str:
    """Substitute the greeting locally, after the last model call, before the first write."""
    return (text or "").replace(CONTACT_GREETING, greeting_for(contact, business_name))


# ===========================================================================
# generate_draft
# ===========================================================================

def pick_contact(conn: sqlite3.Connection, business_id: str,
                 channel: str) -> sqlite3.Row | None:
    kinds = {"EMAIL": ("EMAIL",), "WHATSAPP": ("WHATSAPP", "PHONE"), "PHONE": ("PHONE",),
             "MANUAL": ("EMAIL", "PHONE", "WHATSAPP")}.get(channel.upper(), ("EMAIL",))
    placeholders = ",".join("?" for _ in kinds)
    return conn.execute(
        f"""
        SELECT * FROM business_contacts
         WHERE business_id = ? AND kind IN ({placeholders})
           AND is_active = 1 AND valid = 1 AND human_verified = 1
         ORDER BY is_primary DESC, COALESCE(confidence_pct, 0) DESC, created_at
         LIMIT 1
        """,
        (business_id, *kinds),
    ).fetchone()


def generate_draft(
    conn: sqlite3.Connection,
    business_id: str,
    channel: str = "EMAIL",
    *,
    config: Config | None = None,
    campaign_id: str | None = None,
    contact_id: str | None = None,
    selection_id: str | None = None,
    actor: str = "draft_outreach",
    created_by: str | None = None,
) -> Draft:
    """Research context in, one approvable draft out - plus the message row it belongs to.

    The order is the guarantee: build the context without any contact value, scrub the prompt,
    generate, hydrate the greeting locally, write the draft, then check it. The policy engine
    and the approval hash both see the substituted text, so there is no "checked version" and
    separate "sent version" - there is one body, and it contains the name.
    """
    cfg = config or load_config(strict=False)
    identity = load_identity(cfg)
    channel = channel.upper()

    contact = (conn.execute("SELECT * FROM business_contacts WHERE id = ?", (contact_id,))
               .fetchone() if contact_id else pick_contact(conn, business_id, channel))
    if contact is None and channel == "EMAIL":
        raise ValueError(f"{business_id} has no verified email contact to write to")

    message_id = new_id_for("outreach_messages")
    contact_norm = contact["value_norm"] if contact is not None else ""

    ctx = build_context(conn, business_id, channel, config=cfg, identity=identity,
                        message_id=message_id, contact_norm=contact_norm,
                        campaign_id=campaign_id)

    prompt = f"{SYSTEM_PROMPT}\n\n{build_prompt(ctx)}"
    assert_no_contact_values(
        prompt, business_id=business_id, conn=conn,
        allow=(identity.from_address, identity.reply_to, identity.phone_display,
               ctx.unsubscribe_address, identity.site_url))

    generation = generate_message(ctx, cfg, conn)
    body = hydrate_contact(generation.body, contact, ctx.business_name)
    subject = hydrate_contact(generation.subject or "", contact, ctx.business_name) or None
    claim_map = [
        {**entry, "text": hydrate_contact(str(entry.get("text", "")), contact, ctx.business_name)}
        for entry in generation.claim_map
    ]

    draft_id = new_id_for("outreach_drafts")
    sequence_no = 1 + (conn.execute(
        "SELECT COUNT(*) AS n FROM outreach_messages WHERE business_id = ? AND channel = ?",
        (business_id, channel)).fetchone()["n"])
    digest = body_hash(subject, body)

    with transaction(conn):
        conn.execute(
            """
            INSERT INTO outreach_drafts
                (id, business_id, campaign_id, selection_id, contact_id, channel, sequence_no,
                 subject, body, model_id, prompt_version, input_tokens, output_tokens,
                 facts_used, inferences_used, ai_confidence, ai_confidence_pct,
                 created_by, template_version, claim_map, raw_generation, unsubscribe_token)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (draft_id, business_id, ctx.campaign_id, selection_id,
             contact["id"] if contact is not None else None, channel, sequence_no,
             subject, body, generation.model_id, generation.prompt_version,
             generation.input_tokens, generation.output_tokens,
             json.dumps([f.id for f in ctx.observed]),
             json.dumps([f.id for f in ctx.inferred]),
             generation.confidence_level, generation.confidence_pct, created_by,
             TEMPLATE_VERSION, json.dumps(claim_map, ensure_ascii=False),
             json.dumps({"source": generation.source, **generation.raw}, ensure_ascii=False),
             ctx.unsubscribe_token),
        )
        conn.execute(
            """
            INSERT INTO outreach_messages
                (id, draft_id, business_id, campaign_id, contact_id, channel, status,
                 sequence_no, thread_key, to_address_norm, to_address_dedupe,
                 to_address_display, recipient_domain, subject_final, body_final, body_hash,
                 idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (message_id, draft_id, business_id, ctx.campaign_id,
             contact["id"] if contact is not None else None, channel, sequence_no,
             f"{business_id}:{channel}",
             contact_norm or None,
             contact["value_dedupe"] if contact is not None else None,
             contact["value_display"] if contact is not None else None,
             contact["domain"] if contact is not None else None,
             subject, body, digest,
             f"{business_id}:{channel}:{sequence_no}:{digest[:16]}"),
        )
        conn.execute(
            "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id, detail) "
            "VALUES (?, ?, 'DRAFTED', 'SYSTEM', ?, ?)",
            (new_id_for("outreach_events"), message_id, actor,
             json.dumps({"source": generation.source, "model_id": generation.model_id})),
        )
        audit(conn, created_by or actor, "DRAFT_GENERATED", "outreach_drafts", draft_id,
              after={"channel": channel, "model_id": generation.model_id},
              detail={"source": generation.source, "template_version": TEMPLATE_VERSION,
                      "prompt_version": generation.prompt_version},
              business_id=business_id, campaign_id=ctx.campaign_id, message_id=message_id)

    result = check_draft(conn, draft_id, config=cfg, identity=identity)
    store_policy_result(conn, draft_id, result, actor=actor)
    log.info("draft %s for %s: %s (%s)", draft_id, ctx.business_name, result.verdict,
             generation.source)

    row = conn.execute("SELECT * FROM outreach_drafts WHERE id = ?", (draft_id,)).fetchone()
    return Draft.from_row(row)


def edit_draft(conn: sqlite3.Connection, draft_id: str, new_body: str, *, user_id: str,
               new_subject: str | None = None, config: Config | None = None) -> Draft:
    """Record a human edit and re-run the checker. An edit must not inherit the old PASS."""
    cfg = config or load_config(strict=False)
    with transaction(conn):
        row = conn.execute("SELECT * FROM outreach_drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise ValueError(f"no outreach_drafts row {draft_id!r}")
        state = conn.execute(
            "SELECT id, status FROM outreach_messages WHERE draft_id = ?", (draft_id,)
        ).fetchone()
        if state is not None and state["status"] not in {"DRAFT", "PENDING_APPROVAL",
                                                         "POLICY_BLOCKED"}:
            # A sent message's body is what the approval hash covers and what the recipient
            # actually received. Editing it afterwards would rewrite history.
            raise ValueError(
                f"message {state['id']} is {state['status']}; a sent or approved message "
                f"cannot be edited. Regenerate a new draft instead.")
        subject = new_subject if new_subject is not None else row["subject"]
        conn.execute(
            """
            UPDATE outreach_drafts
               SET body_edited = ?, subject = ?, edited_by = ?, edited_at = ?,
                   edit_count = edit_count + 1, policy_result = NULL,
                   policy_checked_body_hash = NULL
             WHERE id = ?
            """,
            (new_body, subject, user_id, utc_now(), draft_id),
        )
        message = conn.execute(
            "SELECT id, status FROM outreach_messages WHERE draft_id = ?", (draft_id,)
        ).fetchone()
        if message is not None:
            if message["status"] in {"PENDING_APPROVAL", "POLICY_BLOCKED"}:
                conn.execute("UPDATE outreach_messages SET status = 'DRAFT' WHERE id = ?",
                             (message["id"],))
            conn.execute(
                """
                UPDATE outreach_messages
                   SET subject_final = ?, body_final = ?, body_hash = ?
                 WHERE id = ?
                """,
                (subject, new_body, body_hash(subject, new_body), message["id"]),
            )
            conn.execute(
                "INSERT INTO outreach_events (id, message_id, event, actor_type, actor_id) "
                "VALUES (?, ?, 'EDITED', 'HUMAN', ?)",
                (new_id_for("outreach_events"), message["id"], user_id),
            )
        audit(conn, user_id, "DRAFT_EDITED", "outreach_drafts", draft_id,
              detail={"edit_count": int(row["edit_count"] or 0) + 1},
              business_id=row["business_id"], campaign_id=row["campaign_id"],
              message_id=message["id"] if message is not None else None)

    result = check_draft(conn, draft_id, config=cfg)
    store_policy_result(conn, draft_id, result, actor=user_id)
    return Draft.from_row(
        conn.execute("SELECT * FROM outreach_drafts WHERE id = ?", (draft_id,)).fetchone())
