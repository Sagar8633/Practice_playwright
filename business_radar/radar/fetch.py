"""The only door in this system that opens onto the public internet.

Two different disasters live behind this module, and it exists to stop both.

The first is being blocked. Every request the pipeline makes to a stranger's web server is made
by a small tool on one laptop against a business that never asked to be crawled. A fetcher that
ignores robots.txt, hammers a host four times a second, or arrives with a default Python
User-Agent, is the thing 02-research-pipeline.md section 2.2.3 refuses to become. There is no
second IP address and no support contact: the first serious mistake here ends discovery.

The second is worse and quieter. Every URL this fetcher is asked for comes from somewhere
untrusted - an OSM tag typed in by a stranger, a link on a page, later a URI a language model
produced. The application is bound to 127.0.0.1 and the laptop sits inside a home network with
a router admin page and whatever else is on the LAN. Handing "http://192.168.1.1/reboot" or
"http://169.254.169.254/" to a naive fetcher turns this tool into a proxy into its own
network. So every host is resolved and checked against the private, loopback, link-local and
reserved ranges BEFORE the socket opens - and again after every redirect, because a public
hostname that 302s to 127.0.0.1 is the standard way round a check done only once.

Text extraction is stdlib html.parser rather than bs4: one less dependency, and the extractor
only has to be good enough to feed a language model and a marker search, not to render.
"""
from __future__ import annotations

import gzip
import hashlib
import ipaddress
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests

from radar.identity import host_of, normalise_source_url, normalise_url

log = logging.getLogger("radar.fetch")

DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_MAX_BYTES = 2_000_000
MAX_REDIRECTS = 4

# Platforms that are either forbidden by their terms (02-research-pipeline.md section 2.2.3) or
# never carry anything a research finding could rest on. A hit here is not an error, it is a
# URL we decline to fetch.
HOST_DENYLIST: frozenset[str] = frozenset({
    "justdial.com", "sulekha.com", "indiamart.com", "tradeindia.com", "yellowpages.in",
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "youtube.com", "youtu.be", "pinterest.com", "tiktok.com", "wa.me",
    "google.com", "goo.gl", "maps.app.goo.gl", "bit.ly", "tinyurl.com",
})

_SKIP_ELEMENTS = {"script", "style", "noscript", "template", "svg", "canvas", "iframe"}
_BLOCK_ELEMENTS = {
    "p", "div", "br", "li", "tr", "td", "th", "section", "article", "header", "footer",
    "nav", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "form", "main", "aside",
}

_EMAIL_IN_TEXT = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_IN_TEXT = re.compile(r"(?:\+?91[\s.-]?)?(?:0)?[6-9]\d{4}[\s.-]?\d{5}\b")
_LANDLINE_IN_TEXT = re.compile(r"(?:\+?91[\s.-]?)?0?\d{2,4}[\s.-]\d{6,8}\b")
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


class FetchError(RuntimeError):
    """A fetch that could not even be attempted: a bad scheme, a blocked host, a robots refusal.

    Raised only by the guard helpers. fetch_url() never raises for a network problem - it
    returns a FetchResult with ok=False, because 02-research-pipeline.md section 2.2.6 requires
    a failed fetch to become a recorded sources row rather than a silent absence.
    """


# --------------------------------------------------------------------------------------------
# SSRF guards
# --------------------------------------------------------------------------------------------

def _address_is_public(address: str) -> bool:
    """True only for an address it is safe to talk to from inside somebody's home network."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def resolve_public_host(host: str, *, timeout: float = 5.0) -> list[str]:
    """Resolve a hostname and return its addresses, or raise if ANY of them is not public.

    Any, not all: a name that resolves to both 93.184.216.34 and 127.0.0.1 is a DNS rebinding
    attempt, and there is no version of following it that is safe. The cost of being strict is
    that a misconfigured business site with a stray private A record does not get fetched, and
    that is a cost worth paying on a laptop.
    """
    if not host:
        raise FetchError("no host to resolve")

    original_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError("cannot resolve " + host + ": " + str(exc)) from exc
    finally:
        socket.setdefaulttimeout(original_timeout)

    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise FetchError("no addresses for " + host)

    bad = [a for a in addresses if not _address_is_public(a)]
    if bad:
        raise FetchError(
            host + " resolves to a private or reserved address (" + ", ".join(bad) +
            "); refusing to fetch it from inside this network"
        )
    return addresses


def is_denied_host(host: str | None) -> bool:
    """True when the host, or its registrable parent, is on the denylist."""
    if not host:
        return True
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    for index in range(len(labels) - 1):
        if ".".join(labels[index:]) in HOST_DENYLIST:
            return True
    return False


def check_url(url: str | None, *, allow_http: bool = True) -> str:
    """Validate a URL for fetching and return its normalised absolute form.

    Raises FetchError with a reason a human can read, because that reason is what ends up in
    the sources row explaining why a page was never loaded.
    """
    absolute = normalise_url(url)
    if not absolute:
        raise FetchError("not an http(s) URL: " + repr(url))

    scheme = urlsplit(absolute).scheme
    if scheme == "http" and not allow_http:
        raise FetchError("plain http is not allowed by config: " + absolute)

    host = host_of(absolute)
    if not host:
        raise FetchError("no host in " + absolute)
    if is_denied_host(host):
        raise FetchError(host + " is on the host denylist")

    resolve_public_host(host)
    return absolute


# --------------------------------------------------------------------------------------------
# Politeness
# --------------------------------------------------------------------------------------------

class HostThrottle:
    """One request per host per interval, enforced by sleeping.

    Shared across threads because the fetcher runs in a job worker pool. A per-thread throttle
    would let four workers hit one small hospital website simultaneously, which is exactly the
    behaviour that gets a crawler blocked and deserves to.
    """

    def __init__(self, min_interval_seconds: float = 2.0) -> None:
        self.min_interval = max(0.0, float(min_interval_seconds))
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> float:
        """Block until this host may be contacted again. Returns the seconds slept."""
        if self.min_interval <= 0:
            return 0.0
        with self._lock:
            now = time.monotonic()
            earliest = self._last.get(host, 0.0) + self.min_interval
            delay = max(0.0, earliest - now)
            self._last[host] = now + delay
        if delay:
            log.debug("waiting %.1fs before the next request to %s", delay, host)
            time.sleep(delay)
        return delay


class RobotsCache:
    """robots.txt per host, fetched once and remembered for the life of the object.

    A disallowed path is not a failure. It is a recorded decision: the caller writes a sources
    row with robots_allowed = 0 and no content, so the report can say "their site says do not
    crawl this" instead of showing a business with no online presence.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self._session = session or requests.Session()
        self._parsers: dict[str, RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def _parser_for(self, origin: str) -> RobotFileParser | None:
        with self._lock:
            if origin in self._parsers:
                return self._parsers[origin]

        parser: RobotFileParser | None = RobotFileParser()
        robots_url = origin + "/robots.txt"
        try:
            response = self._session.get(
                robots_url,
                headers={"User-Agent": self.user_agent, "Accept": "text/plain"},
                timeout=self.timeout,
                allow_redirects=True,
            )
            if response.status_code >= 500:
                # RFC 9309: a 5xx on robots.txt means "assume disallowed". A None parser is the
                # signal for that, and it is deliberately not cached as "allow".
                log.warning("%s returned %s; treating the whole host as disallowed",
                            robots_url, response.status_code)
                parser = None
            elif response.status_code >= 400:
                # No robots.txt is an allow-all, which is what the standard says and what every
                # small business site in these four towns actually has.
                parser = RobotFileParser()
                parser.parse([])
            else:
                assert parser is not None
                parser.parse(response.text.splitlines())
        except requests.RequestException as exc:
            log.warning("could not read %s (%s); treating the host as disallowed",
                        robots_url, exc)
            parser = None

        with self._lock:
            self._parsers[origin] = parser
        return parser

    def allows(self, url: str) -> bool:
        """May we fetch this URL? Failure to read robots.txt is a no, not a yes."""
        parts = urlsplit(url)
        if not parts.scheme or not parts.netloc:
            return False
        origin = parts.scheme + "://" + parts.netloc
        parser = self._parser_for(origin)
        if parser is None:
            return False
        try:
            return bool(parser.can_fetch(self.user_agent, url))
        except Exception:                       # a malformed robots.txt is not our crash
            log.warning("unreadable robots.txt rules at %s; declining", origin)
            return False


# --------------------------------------------------------------------------------------------
# HTML to text
# --------------------------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Turn HTML into the plain text a language model and a marker search can read."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.links: list[str] = []
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_ELEMENTS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            for key, value in attrs:
                if key == "href" and value:
                    self.links.append(value.strip())
        if tag in _BLOCK_ELEMENTS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_ELEMENTS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "title":
            self._in_title = False
        if tag in _BLOCK_ELEMENTS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_title and self.title is None:
            cleaned = data.strip()
            if cleaned:
                self.title = cleaned
        self._chunks.append(data)

    @property
    def text(self) -> str:
        joined = "".join(self._chunks)
        joined = _WS.sub(" ", joined)
        lines = [line.strip() for line in joined.split("\n")]
        return _BLANK_LINES.sub("\n\n", "\n".join(line for line in lines if line))


def extract_text(html: str) -> tuple[str, str | None, list[str]]:
    """(text, title, links) from an HTML document. Never raises on malformed markup."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:                    # html.parser can still object to some inputs
        log.debug("html parse gave up part way through: %s", exc)
    return parser.text, parser.title, parser.links


def extract_emails(text: str) -> list[str]:
    """Every email-looking string, in document order, deduplicated.

    These become business_contacts rows and are then removed from the copy of the page that
    reaches a prompt. No value found here is ever sent to the LLM - _CONTEXT.md section 2.
    """
    seen: dict[str, None] = {}
    for match in _EMAIL_IN_TEXT.finditer(text):
        value = match.group(0).lower().rstrip(".")
        seen.setdefault(value, None)
    return list(seen)


def extract_phones(text: str) -> list[str]:
    """Every phone-looking string. Normalisation and validation belong to radar.identity."""
    seen: dict[str, None] = {}
    for pattern in (_PHONE_IN_TEXT, _LANDLINE_IN_TEXT):
        for match in pattern.finditer(text):
            seen.setdefault(match.group(0).strip(), None)
    return list(seen)


# --------------------------------------------------------------------------------------------
# The fetch itself
# --------------------------------------------------------------------------------------------

@dataclass(slots=True)
class FetchResult:
    """One attempt at one URL, successful or not. Every field is a fact about what happened.

    An unsuccessful result is not an exception because it is data: sources rows record the 404,
    the timeout and the robots refusal, and website_status only becomes ABSENT under the
    positive-absence rule, never after an error.
    """
    url: str
    ok: bool
    final_url: str | None = None
    status: int | None = None
    reason: str = ""
    robots_allowed: bool | None = None
    content_type: str | None = None
    text: str = ""
    title: str | None = None
    links: list[str] = field(default_factory=list)
    content_sha256: str | None = None
    bytes_read: int = 0
    truncated: bool = False
    elapsed_ms: int = 0
    redirects: list[str] = field(default_factory=list)

    @property
    def url_norm(self) -> str:
        """The sources.url_norm value for this attempt."""
        return normalise_source_url(self.final_url or self.url)

    @property
    def host(self) -> str | None:
        return host_of(self.final_url or self.url)


def fetch_url(
    url: str,
    *,
    user_agent: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    respect_robots: bool = True,
    robots: RobotsCache | None = None,
    throttle: HostThrottle | None = None,
    session: requests.Session | None = None,
    allow_http: bool = True,
    max_redirects: int = MAX_REDIRECTS,
) -> FetchResult:
    """Fetch one page politely and safely. Returns a FetchResult; does not raise on failure.

    Redirects are followed by hand rather than by requests, because the SSRF check has to run
    against every hop. A public hostname that redirects to 127.0.0.1 is the ordinary way past a
    guard that only checked the URL it was given.
    """
    started = time.monotonic()
    result = FetchResult(url=url, ok=False)

    try:
        target = check_url(url, allow_http=allow_http)
    except FetchError as exc:
        result.reason = str(exc)
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
        log.info("declining %s: %s", url, exc)
        return result

    owns_session = session is None
    http = session or requests.Session()
    robots_cache = robots
    if respect_robots and robots_cache is None:
        robots_cache = RobotsCache(user_agent=user_agent, session=http, timeout=min(timeout, 10))

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
        "Accept-Language": "en-IN,en;q=0.9,mr;q=0.6",
    }

    try:
        for hop in range(max_redirects + 1):
            host = host_of(target) or ""

            if respect_robots and robots_cache is not None:
                allowed = robots_cache.allows(target)
                result.robots_allowed = allowed
                if not allowed:
                    result.reason = "robots.txt disallows " + target
                    result.final_url = target
                    log.info("robots.txt disallows %s", target)
                    return result

            if throttle is not None:
                throttle.wait(host)

            try:
                response = http.get(
                    target,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=False,
                    stream=True,
                )
            except requests.RequestException as exc:
                result.reason = type(exc).__name__ + ": " + str(exc)
                result.final_url = target
                log.info("fetch failed for %s: %s", target, result.reason)
                return result

            result.status = response.status_code
            result.final_url = target

            if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location", "")
                response.close()
                if not location:
                    result.reason = "redirect with no Location header"
                    return result
                if hop >= max_redirects:
                    result.reason = "more than " + str(max_redirects) + " redirects"
                    return result
                nxt = urljoin(target, location)
                try:
                    target = check_url(nxt, allow_http=allow_http)
                except FetchError as exc:
                    # This is the branch the guard exists for.
                    result.reason = "redirect refused: " + str(exc)
                    log.warning("refusing redirect from %s to %s: %s", result.final_url, nxt, exc)
                    return result
                result.redirects.append(target)
                continue

            with response:
                if response.status_code >= 400:
                    result.reason = "HTTP " + str(response.status_code)
                    return result

                result.content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip()

                body = bytearray()
                for chunk in response.iter_content(chunk_size=16384):
                    if not chunk:
                        continue
                    body.extend(chunk)
                    if len(body) >= max_bytes:
                        result.truncated = True
                        break
                raw = bytes(body[:max_bytes])

            if raw[:2] == b"\x1f\x8b":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass

            result.bytes_read = len(raw)
            result.content_sha256 = hashlib.sha256(raw).hexdigest()

            encoding = response.encoding or "utf-8"
            try:
                document = raw.decode(encoding, errors="replace")
            except LookupError:
                document = raw.decode("utf-8", errors="replace")

            if result.content_type and "html" not in result.content_type:
                result.text = document if "text" in (result.content_type or "") else ""
            else:
                result.text, result.title, result.links = extract_text(document)

            result.ok = True
            result.reason = "OK"
            return result

        result.reason = "redirect loop"
        return result
    finally:
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
        if owns_session:
            http.close()


def save_snapshot(directory: Path, name: str, text: str) -> Path:
    """Write extracted page text to a gzip file, atomically, and return the path.

    Atomic because a half-written snapshot referenced by a sources row is a source that cannot
    be reopened, and "open the source" is the whole promise the verification screen makes.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + ".txt.gz")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as handle:
        handle.write(text)
    tmp.replace(path)
    return path


def read_snapshot(path: Path) -> str:
    """Read back a snapshot written by save_snapshot()."""
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return handle.read()
