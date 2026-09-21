"""Business identity across campaigns, sources and spellings.

Without this module, "A.B.C. Hospital" from an OSM node in August and "ABC Hospital, Dhule"
from a registry row in November are two rows. Two rows means two research runs charged against
the Gemini free-tier quota, two verification queue items for Sagar to read, two entries in the
same report, two independent attempt budgets, and - the one that actually costs something - two
cold emails to the same hospital administrator six weeks apart, the second of which arrives
after the first was ignored and reads as a bulk mailer. The duplicate check on business ids
cannot catch it, because those are different business ids.

The normaliser here is deliberately more aggressive than a naive slug and deliberately less
aggressive than a fuzzy matcher. It folds spelling, punctuation, honorifics, legal suffixes and
a trailing city token, because those are the ways one business gets written down twice. It does
not fold word order, does not stem, and never merges on a similarity score: similarity() and
merge_candidates() return candidates for a human, and nothing in this module auto-merges on
them. A false split costs one verification; a false merge hides a prospect and silently applies
one business's rejection to another company. Those prices are not symmetric.

See 01-data-model.md section 1.12 for the full ruling, including the merge_candidates queue
this module deliberately does not write to.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit

log = logging.getLogger("radar.identity")

# Pinned into business_contacts.phone_norm_version so a row normalised by an older rule set is
# identifiable after the rules change.
NAME_NORM_VERSION = "name-norm-1"
PHONE_NORM_VERSION = "phone-in-1"

# --------------------------------------------------------------------------------------------
# Vocabularies. All of these are hand-maintained lists of what actually appears in Maharashtra
# business names, not general-purpose language resources.
# --------------------------------------------------------------------------------------------

_LEGAL_SUFFIXES: tuple[str, ...] = (
    "private limited", "pvt limited", "pvt ltd", "p ltd",
    "and sons", "and co", "and company", "and brothers",
    "limited", "ltd", "llp", "llc", "inc", "incorporated", "corp", "corporation",
    "company", "co",
    "enterprises", "enterprise", "trust", "society", "foundation", "group",
)

# SIMPLIFIED: 01-data-model.md section 1.12.2 also lists shri / shree / sri as honorifics to
# drop, but its own SAMPLE table (section 1.12.3, rows 7-9) requires "Shri ABC Hospital",
# "Sri A.B.C. Hospital" and the Devanagari form to all normalise to "shree abc hospital" - that
# is, folded to one spelling and KEPT, not dropped. The SAMPLE table wins: dropping them would
# merge "Shree Bakery" with every other bakery in the town. Only the honorifics that carry no
# distinguishing information are dropped here.
_HONORIFICS: tuple[str, ...] = ("messrs", "smt", "dr", "prof", "mr", "mrs")

_TRANSLITERATIONS: dict[str, str] = {
    # Devanagari -> the Latin form the rest of the database uses. Not a general transliterator:
    # a general one produces "shrii" and "srii" for the same word and creates the split this
    # map exists to close.
    "रुग्णालय": "hospital",   # rugnalaya
    "हॉस्पिटल": "hospital",   # hospital
    "दवाखाना": "clinic",           # davakhana
    "विद्यालय": "school",     # vidyalaya
    "शाळा": "school",                             # shala
    "महाविद्यालय": "college",
    "उद्योग": "industries",             # udyog
    "ट्रेडर्स": "traders",
    "स्टोअर्स": "stores",
    "श्री": "shree",                              # shri
    "मेडिकल": "medical",
    "ऑटो": "auto",
}

_LATIN_VARIANTS: dict[str, str] = {
    # Common romanisation splits, folded to one spelling.
    "shri": "shree", "sri": "shree", "shree": "shree", "shrii": "shree",
    "laxmi": "lakshmi", "lakshmi": "lakshmi",
    "hospitl": "hospital", "hosp": "hospital",
    "indl": "industrial", "inds": "industries", "ind": "industries",
    "mfg": "manufacturing", "mfrs": "manufacturers",
}

# Local parts that belong to a role, not a person. A group of three schools under one trust
# routinely shares one info@, so a role address is never treated as an identity.
ROLE_LOCALS: frozenset[str] = frozenset({
    "info", "contact", "enquiry", "enquiries", "inquiry", "sales", "admin", "office",
    "support", "help", "hello", "mail", "email", "care", "customercare", "service",
    "services", "reception", "frontdesk", "accounts", "billing", "hr", "careers", "jobs",
    "marketing", "webmaster", "postmaster", "noreply", "no-reply", "donotreply",
})

# SIMPLIFIED: a real public-suffix list is thousands of entries and a dependency. These are the
# multi-label suffixes that actually appear on Indian business sites, plus the handful of
# foreign ones seen on franchise pages. A suffix missing from here yields a too-short
# registrable domain, which would over-merge two unrelated sites - so anything new that turns
# up belongs in this set. Full rule: 05-outreach-workflow.md section 5.9.2.
_MULTI_LABEL_SUFFIXES: frozenset[str] = frozenset({
    "co.in", "net.in", "org.in", "gen.in", "firm.in", "ind.in", "ac.in", "edu.in",
    "res.in", "gov.in", "nic.in", "mil.in",
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk",
    "com.au", "net.au", "org.au", "edu.au",
    "co.jp", "com.br", "com.sg", "com.my", "co.za", "com.cn", "co.nz", "com.np",
})

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+&'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_WS_RE = re.compile(r"\s+")
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_MS_PREFIX_RE = re.compile(r"\bm\s*[/.]\s*s\b")


# --------------------------------------------------------------------------------------------
# Cities
# --------------------------------------------------------------------------------------------

def city_slug(city: str | None) -> str:
    """The join key for a city. businesses.city is a label; this is the identity.

    "Nashik", "nashik ", "NASHIK" and "Nashik " must all land in the same campaign section, and
    a report grouped on the display column silently splits them into four.
    """
    if not city:
        return ""
    text = unicodedata.normalize("NFKD", str(city)).casefold()
    text = "".join(ch if (ch.isascii() and ch.isalnum()) else " " for ch in text)
    return "-".join(part for part in _WS_RE.split(text.strip()) if part)


# --------------------------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------------------------

def _merge_initial_runs(tokens: list[str]) -> list[str]:
    """Join runs of two or more single-letter tokens: ["a","b","c"] -> ["abc"].

    This is the step that closes "A.B.C. Hospital" against "ABC Hospital". Both arrive here as
    the same token list only because punctuation has already gone.
    """
    out: list[str] = []
    run: list[str] = []
    for token in tokens:
        if len(token) == 1 and token.isalpha():
            run.append(token)
            continue
        out.append("".join(run)) if len(run) >= 2 else out.extend(run)
        run = []
        out.append(token)
    out.append("".join(run)) if len(run) >= 2 else out.extend(run)
    return out


def _strip_legal_suffixes(tokens: list[str]) -> list[str]:
    """Drop trailing legal suffixes repeatedly, so "Pvt Ltd Company" loses both."""
    changed = True
    while changed and len(tokens) > 1:
        changed = False
        for suffix in _LEGAL_SUFFIXES:
            parts = suffix.split()
            if len(tokens) > len(parts) and tokens[-len(parts):] == parts:
                tokens = tokens[:-len(parts)]
                changed = True
                break
    return tokens


def normalise_name(name: str | None, *, city: str | None = None) -> str:
    """Canonical comparison form of a business name.

    Steps, in order:
      1. NFKC normalise, casefold.
      2. Map Devanagari tokens through _TRANSLITERATIONS; drop any remaining non-Latin script
         rather than transliterating it blindly.
      3. Remove the "M/s" prefix form, replace "&" with " and ", strip all other punctuation
         including the dots in "A.B.C.".
      4. Join runs of single letters, so "a b c" becomes "abc".
      5. Drop leading honorifics when another token follows.
      6. Drop trailing legal suffixes, repeatedly.
      7. Drop a trailing city token when it matches the city argument, so
         "abc hospital dhule" == "abc hospital" for a business in Dhule. Only trailing, and
         only the row's own city: "Nashik Motors" in Dhule keeps its "nashik".
      8. Fold _LATIN_VARIANTS token by token.

    Not done, on purpose: no stemming, no stopword removal beyond the lists above, no sorting
    of tokens. "Krishna Motors" and "Motors Krishna" stay different, because in practice they
    are different businesses.
    """
    if not name:
        return ""

    text = unicodedata.normalize("NFKC", str(name)).casefold()

    for source, target in _TRANSLITERATIONS.items():
        if source in text:
            text = text.replace(source, " " + target + " ")

    text = _MS_PREFIX_RE.sub(" ", text)
    text = text.replace("&", " and ")
    # Everything that is not an ASCII letter or digit becomes a space. That drops the remaining
    # non-Latin script (step 2 already rescued the tokens worth keeping) and every dot, comma,
    # hyphen and quote in one pass.
    text = "".join(ch if (ch.isascii() and ch.isalnum()) else " " for ch in text)

    tokens = [t for t in _WS_RE.split(text.strip()) if t]
    tokens = _merge_initial_runs(tokens)

    while len(tokens) > 1 and tokens[0] in _HONORIFICS:
        tokens = tokens[1:]

    tokens = _strip_legal_suffixes(tokens)

    slug_parts = [p for p in city_slug(city).split("-") if p]
    if slug_parts and len(tokens) > len(slug_parts) and tokens[-len(slug_parts):] == slug_parts:
        tokens = tokens[:-len(slug_parts)]

    tokens = [_LATIN_VARIANTS.get(t, t) for t in tokens]
    return " ".join(tokens)


# 01-data-model.md section 1.12.2 names the function name_norm, and the column it feeds is
# called name_norm too. One implementation, two names people will reach for.
name_norm = normalise_name


def similarity(left: str, right: str) -> int:
    """A 0-100 token-set similarity between two already-normalised names.

    SIMPLIFIED: 01-data-model.md section 1.12.4 specifies rapidfuzz token_set_ratio. This is a
    difflib approximation over the sorted token sets, close enough to rank merge candidates and
    adding no dependency. It is never used to merge: rules R5-R8 in that section are
    candidate-only, and so is every caller here.
    """
    if not left or not right:
        return 0
    a = " ".join(sorted(set(left.split())))
    b = " ".join(sorted(set(right.split())))
    if a == b:
        return 100
    return int(round(SequenceMatcher(None, a, b).ratio() * 100))


def merge_candidates(
    name_a: str,
    name_b: str,
    *,
    same_city: bool,
    same_category: bool,
) -> tuple[bool, str]:
    """Would these two names go to a human as a possible duplicate? Never an auto-merge.

    Returns (is_candidate, confidence). The thresholds are rules R5 and R6: 92 within a
    category, 96 across categories, and nothing at all across cities - "Shree Bakery" in
    Shirpur and "Shree Bakery" in Dhule are two bakeries, and pairing them wastes the one
    scarce resource in this system, which is Sagar's attention.
    """
    if not same_city:
        return False, "LOW"
    score = similarity(name_a, name_b)
    if same_category and score >= 92:
        return True, "MEDIUM"
    if not same_category and score >= 96:
        return True, "LOW"
    return False, "LOW"


# --------------------------------------------------------------------------------------------
# Phones
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PhoneNorm:
    """One phone number, normalised. valid=False means do not store it as reachable."""
    raw: str
    e164: str | None
    national: str | None
    number_type: str            # MOBILE | FIXED_LINE | TOLL_FREE | INVALID
    valid: bool
    reason: str = ""
    version: str = PHONE_NORM_VERSION

    @property
    def is_mobile(self) -> bool:
        return self.valid and self.number_type == "MOBILE"

    @property
    def display(self) -> str:
        """The human form, +91 98123 45678. Never used as an identity."""
        if not self.valid or not self.national:
            return self.raw.strip()
        return "+91 " + self.national[:5] + " " + self.national[5:]


def normalise_phone(raw: str | None, *, default_country: str = "91") -> PhoneNorm:
    """An Indian business phone number in E.164, plus what kind of number it is.

    The number type is not a curiosity: business_key takes the phone branch only for a MOBILE
    number, because a landline shared by a building is common and a mobile shared by two
    unrelated businesses is not. Getting the type wrong here merges two clinics that share a
    reception desk into one prospect, and one of them then never gets contacted at all.
    """
    if not raw:
        return PhoneNorm(raw="", e164=None, national=None, number_type="INVALID",
                         valid=False, reason="empty")

    text = str(raw).strip()
    # A tag may carry several numbers: "phone=+91 2562 123456;+91 98123 45678". Take the first.
    first = re.split(r"[;,/]| or ", text, maxsplit=1)[0]
    digits = re.sub(r"\D", "", first)

    if not first.strip().startswith("+") and digits.startswith("00"):
        digits = digits[2:]

    country_len = len(default_country)
    if digits.startswith(default_country) and len(digits) == 10 + country_len:
        national = digits[country_len:]
    elif len(digits) == 11 and digits.startswith("0"):
        national = digits[1:]
    elif len(digits) == 10:
        national = digits
    else:
        return PhoneNorm(
            raw=text, e164=None, national=None, number_type="INVALID", valid=False,
            reason="not a 10-digit Indian number (" + str(len(digits)) + " digits)",
        )

    lead = national[0]
    if lead in "6789":
        number_type = "MOBILE"
    elif national.startswith(("1800", "1860")):
        number_type = "TOLL_FREE"
    elif lead in "2345":
        number_type = "FIXED_LINE"
    else:
        return PhoneNorm(raw=text, e164=None, national=None, number_type="INVALID",
                         valid=False, reason="no Indian number starts with " + lead)

    return PhoneNorm(
        raw=text,
        e164="+" + default_country + national,
        national=national,
        number_type=number_type,
        valid=True,
    )


# --------------------------------------------------------------------------------------------
# Emails
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class EmailNorm:
    """One email address in three forms, because they answer three different questions."""
    raw: str
    value_norm: str | None      # identity: what we store and compare
    value_dedupe: str | None    # looser: gmail dots and plus-tags folded away
    domain: str | None
    is_role_address: bool
    valid: bool
    reason: str = ""

    @property
    def display(self) -> str:
        return self.value_norm or self.raw.strip()


def normalise_email(raw: str | None) -> EmailNorm:
    """Normalise an address, and say whether it is a role address.

    value_dedupe folds Gmail dots and plus-tags, so owner.name@gmail.com and
    ownername+leads@gmail.com are recognised as the same inbox - which matters because an
    opt-out arriving from one of them has to suppress the other. value_norm keeps the address
    as written, because that is what we would actually send to.
    """
    if not raw:
        return EmailNorm(raw="", value_norm=None, value_dedupe=None, domain=None,
                         is_role_address=False, valid=False, reason="empty")

    text = str(raw).strip()
    if text.lower().startswith("mailto:"):
        text = text[7:]
    text = re.split(r"[;,\s]", text.strip(), maxsplit=1)[0].strip().strip("<>")
    value = text.lower()

    if not _EMAIL_RE.match(value):
        return EmailNorm(raw=text, value_norm=None, value_dedupe=None, domain=None,
                         is_role_address=False, valid=False, reason="not a valid address")

    local, _, domain = value.partition("@")
    domain = domain.rstrip(".")

    dedupe_local = local.split("+", 1)[0]
    if domain in {"gmail.com", "googlemail.com"}:
        dedupe_local = dedupe_local.replace(".", "")
        dedupe_domain = "gmail.com"
    else:
        dedupe_domain = domain

    if not dedupe_local:
        return EmailNorm(raw=text, value_norm=None, value_dedupe=None, domain=None,
                         is_role_address=False, valid=False, reason="empty local part")

    return EmailNorm(
        raw=text,
        value_norm=local + "@" + domain,
        value_dedupe=dedupe_local + "@" + dedupe_domain,
        domain=domain,
        is_role_address=dedupe_local in ROLE_LOCALS,
        valid=True,
    )


# --------------------------------------------------------------------------------------------
# Websites
# --------------------------------------------------------------------------------------------

def normalise_url(url: str | None) -> str | None:
    """An absolute http(s) URL, or None. A bare "abchospital.in" becomes https://abchospital.in.

    OSM website tags are written by hand and arrive as "www.x.in", "x.in/", "HTTP://X.IN" and
    "facebook.com/x" in roughly equal measure. Every one of those has to become one comparable
    string before it can key a business.
    """
    if not url:
        return None
    text = str(url).strip().strip("<>").rstrip(",;")
    if " " in text:
        parts = text.split()
        text = parts[0] if parts else ""
    if not text:
        return None
    if text.lower().startswith(("mailto:", "tel:", "javascript:", "data:", "file:")):
        return None
    if not _SCHEME_RE.match(text):
        text = "https://" + text
    scheme, _, rest = text.partition("://")
    if scheme.lower() not in {"http", "https"}:
        return None
    authority = rest.split("/")[0]
    if not authority or "." not in authority:
        return None
    return scheme.lower() + "://" + rest


def host_of(url: str | None) -> str | None:
    """The lowercase hostname of a URL, without port or credentials."""
    normalised = normalise_url(url)
    if not normalised:
        return None
    try:
        host = (urlsplit(normalised).hostname or "").lower().strip(".")
    except ValueError:
        return None
    return host or None


def registrable_domain(url: str | None) -> str | None:
    """The domain one organisation controls: "https://WWW.ABC-Hospital.IN/x" -> "abc-hospital.in".

    This is the first branch of business_key, and it is first because a registrable domain is
    the only signal a business controls and rarely shares. Which makes the shared-hosting case
    the one to watch: two schools on one site-builder subdomain would key the same. The
    multi-label suffix set is what keeps "x.co.in" and "y.co.in" apart, which is the version of
    that hazard the free stack actually produces.
    """
    host = host_of(url)
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) < 2 or any(not label for label in labels):
        return None
    last_two = ".".join(labels[-2:])
    if last_two in _MULTI_LABEL_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def normalise_source_url(url: str | None) -> str:
    """The comparison form of a source URL: lowercase host, no fragment, no trailing slash.

    Feeds sources.url_norm, whose unique index with business_id is what stops the same page
    being recorded four times because it was linked as /about, /about/, /About and /about#team.
    """
    normalised = normalise_url(url)
    if not normalised:
        return ""
    try:
        parts = urlsplit(normalised)
    except ValueError:
        return ""
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if parts.port and parts.port not in (80, 443):
        host = host + ":" + str(parts.port)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, host, path, parts.query, ""))


# --------------------------------------------------------------------------------------------
# The key itself
# --------------------------------------------------------------------------------------------

def business_key(
    *,
    name: str,
    city: str,
    website: str | None = None,
    phone_norm: str | None = None,
    phone_number_type: str | None = None,
) -> str:
    """A stable identity for one real-world business across campaigns.

    Preference order, first non-empty wins:
      1. registrable domain of website    -> "d:abc-hospital.in"
      2. E.164 MOBILE phone               -> "p:+919812345678"
      3. name_norm + "@" + city_slug      -> "n:abc hospital@dhule"

    The phone branch is taken only for a MOBILE number. A FIXED_LINE or an unknown type falls
    through to the name branch, because a shared reception number for two clinics in one
    building would otherwise turn two businesses into one prospect.

    Raises ValueError when the name branch would produce an empty key ("n:@dhule"). An element
    with no usable name, no domain and no mobile is not a business and must not be inserted as
    one - see 02-research-pipeline.md section 2.4.3, the "not a business" filter.
    """
    domain = registrable_domain(website)
    if domain:
        return "d:" + domain

    if phone_norm and (phone_number_type or "").upper() == "MOBILE":
        return "p:" + phone_norm

    normalised = normalise_name(name, city=city)
    slug = city_slug(city)
    if not normalised or not slug:
        raise ValueError(
            "business_key would be empty: name=" + repr(name) + " city=" + repr(city) +
            ". An element with no name, no domain and no mobile is not a business."
        )
    return "n:" + normalised + "@" + slug
