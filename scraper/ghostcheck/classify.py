"""Classify HTTP responses as ok / blocked / error.

Pure functions (no network) so they can be unit-tested with saved fixtures.
"""
from __future__ import annotations

import re

OK = "ok"
BLOCKED = "blocked"
ERROR = "error"

# Status codes that almost always mean "bot management / rate limiting said no".
BLOCK_STATUS = {401, 403, 405, 407, 429, 451}

# Case-insensitive markers of Akamai Bot Manager, Cloudflare, Imperva etc.
# Kept specific so that a normal careers page is not misclassified.
CHALLENGE_MARKERS = [
    r"access denied.{0,600}reference(?:\s*#|&#32;&#35;)",  # classic Akamai edge deny page
    r"<title>\s*access denied\s*</title>",
    r"errors\.edgesuite\.net",
    r"akamai(?:ghost|-bot|botmanager| bot manager)",
    r"_abck",                                # Akamai BMP sensor cookie
    r"bm-verify",                            # Akamai interstitial challenge
    r"sec-if-cpt",                           # Akamai crypto challenge
    r"/_sec/cp_challenge",
    r"ak_bmsc",
    r"pardon our interruption",              # Imperva / Distil
    r"incapsula incident id",
    r"request rejected.{0,200}support id",   # F5 ASM
    r"cf-chl-|challenge-platform|attention required! \| cloudflare|just a moment\.\.\.",
    r"captcha",
    r"are you a robot|verify you are human|unusual traffic",
]
_CHALLENGE_RE = re.compile("|".join(CHALLENGE_MARKERS), re.I | re.S)


def challenge_marker(text: str | None) -> str | None:
    """Return the matched challenge marker snippet, or None."""
    if not text:
        return None
    m = _CHALLENGE_RE.search(text[:200_000])
    return m.group(0)[:60] if m else None


def classify_http(status: int | None, text: str | None, expect: str) -> tuple[str, str]:
    """Classify a raw HTTP response before parsing.

    expect: "json" (Workday CXS API) or "html" (SuccessFactors RMK search page).
    Returns (status, note). status == OK means "looks like a real response,
    go ahead and parse it"; parse failures are handled by the caller.
    """
    marker = challenge_marker(text)
    if status is None:
        return ERROR, "no response"
    if status in BLOCK_STATUS:
        return BLOCKED, f"HTTP {status}" + (f" + challenge marker '{marker}'" if marker else "")
    if status == 503 and marker:
        return BLOCKED, f"HTTP 503 + challenge marker '{marker}'"
    if status >= 400:
        return ERROR, f"HTTP {status}"
    # 2xx/3xx from here on
    body = (text or "").lstrip()
    if expect == "json":
        if not body.startswith(("{", "[")):
            if marker:
                return BLOCKED, f"HTML challenge instead of JSON ('{marker}')"
            if not body:
                return ERROR, "empty body"
            return ERROR, "non-JSON body"
        return OK, ""
    # html
    if marker and not looks_like_sf_results(body):
        return BLOCKED, f"challenge page ('{marker}')"
    if not body:
        return ERROR, "empty body"
    return OK, ""


def looks_like_sf_results(html: str) -> bool:
    return any(
        s in html
        for s in ('class="data-row', 'class="job-tile ', "paginationLabel",
                  "job-tile-result-container", 'id="searchresults"')
    )
