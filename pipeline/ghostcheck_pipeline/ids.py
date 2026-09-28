"""Stable listing_id generation (contract §0, "Listing ID stability").

listing_id = 10 lowercase Crockford-base32 chars = the top 50 bits of
sha256("{employer_id}:{ats_job_id}"), computed once and cached forever in a
register so a hash collision (or a re-run) never changes or reissues an id.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile

CROCKFORD = "0123456789abcdefghjkmnpqrstvwxyz"


def _hash50(key: str) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:7], "big") >> 6  # top 56 bits -> top 50 bits


def _encode(n: int, length: int = 10) -> str:
    return "".join(CROCKFORD[(n >> (5 * i)) & 0x1F] for i in range(length - 1, -1, -1))


class Register:
    """Permanent issued-id register (contract: "IDs of hidden listings stay
    reserved forever"). Persisted to history/ (internal, not part of the
    public data contract) so ids survive across pipeline runs.
    """

    def __init__(self, path: str):
        self.path = path
        data = _read_json(path, {"by_key": {}, "issued": {}})
        self.by_key: dict[str, str] = data.get("by_key", {})
        self.issued: dict[str, str] = data.get("issued", {})

    def listing_id(self, employer_id: str, ats_job_id: str) -> str:
        key = f"{employer_id}:{ats_job_id}"
        cached = self.by_key.get(key)
        if cached:
            return cached
        suffix = 0
        while True:
            candidate_key = key if suffix == 0 else f"{key}:{suffix}"
            lid = _encode(_hash50(candidate_key))
            if lid not in self.issued:
                self.by_key[key] = lid
                self.issued[lid] = candidate_key
                return lid
            suffix += 1

    def save(self) -> None:
        _write_json(self.path, {"by_key": self.by_key, "issued": self.issued})


def _read_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
