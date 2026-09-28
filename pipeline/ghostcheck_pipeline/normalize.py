"""Title/location normalisation, fingerprinting and apply_domain (contract §8, B2/B3.5)."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Second-level public suffixes we need for our employer set. Not a full PSL,
# but covers every ccTLD pattern used by South African career sites.
_CC_SECOND_LEVEL = {
    "co.za", "org.za", "gov.za", "ac.za", "net.za", "web.za",
    "co.uk", "org.uk", "ac.uk", "gov.uk",
    "com.au", "net.au", "org.au", "co.nz", "co.in", "com.br", "co.jp",
}


def normalise_text(s: str | None) -> str:
    s = (s or "").casefold()
    return _NON_ALNUM.sub(" ", s).strip()


def normalised_title(title: str) -> str:
    return normalise_text(title) or "untitled"


def normalised_location(location: str | None) -> str | None:
    norm = normalise_text(location)
    if not norm or norm == "remote":
        return None
    return norm


def fingerprint(employer_id: str, norm_title: str, norm_location: str | None) -> str:
    return f"{employer_id}|{norm_title}|{norm_location or '-'}"


def apply_domain(url: str) -> str:
    host = urlsplit(url).netloc.split(":")[0].lower()
    labels = [l for l in host.split(".") if l]
    if len(labels) >= 3 and ".".join(labels[-2:]) in _CC_SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host
