"""Static-JSON storage with a hard POPIA field whitelist.

Data contract (ux/handoff.md §0.3, B2, B7):
  per listing exactly: ats_job_id, title, location (str|null), url, first_seen, last_seen
  dates are SAST calendar dates YYYY-MM-DD
  listing data is only written for an employer on a run whose status is "ok"
"""
from __future__ import annotations

import json
import os
import re
import tempfile

# POPIA field policy: these are the ONLY per-listing fields ever written.
ALLOWED_FIELDS = ("ats_job_id", "title", "location", "url", "first_seen", "last_seen")
MAX_LEN = {"ats_job_id": 100, "title": 200, "location": 200, "url": 500}
_WS = re.compile(r"\s+")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def norm_ws(s) -> str:
    return _WS.sub(" ", str(s or "")).strip()


def sanitize(item: dict) -> dict:
    """Keep only whitelisted fields, whitespace-normalise, cap lengths, empty location -> None."""
    out = {}
    for k in ALLOWED_FIELDS:
        v = item.get(k)
        if k in MAX_LEN:
            v = norm_ws(v)[:MAX_LEN[k]]
        out[k] = v
    if not out["location"]:
        out["location"] = None
    return out


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
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def listings_path(data_dir: str, employer_id: str) -> str:
    return os.path.join(data_dir, "listings", f"{employer_id}.json")


def ensure_listings_file(data_dir: str, employer_id: str) -> None:
    """Create an empty listings file if none exists (never modifies an existing one)."""
    path = listings_path(data_dir, employer_id)
    if not os.path.exists(path):
        _write_json(path, {"employer_id": employer_id, "listings": []})


def upsert_listings(data_dir: str, employer_id: str, scraped: list[dict], today: str) -> dict:
    """Merge one SUCCESSFUL check into history/listings/<employer>.json.

    New ats_job_ids get first_seen=today; every id found today gets last_seen=today and
    current title/location/url. Ids not found are left untouched (their last_seen plus the
    run log of ok dates is enough to reconstruct closures later).
    Caller must only call this for status == "ok".
    """
    if not _DATE.match(today):
        raise ValueError(f"bad date {today!r}")
    path = listings_path(data_dir, employer_id)
    doc = _read_json(path, {"employer_id": employer_id, "listings": []})
    existing = {str(x["ats_job_id"]): sanitize(x) for x in doc.get("listings", [])}
    new = 0
    for raw in scraped:
        jid = norm_ws(raw.get("ats_job_id"))
        if not jid:
            continue
        cur = existing.get(jid)
        if cur is None:
            new += 1
            cur = {"first_seen": today}
        cur.update({"ats_job_id": jid, "title": raw.get("title"), "location": raw.get("location"),
                    "url": raw.get("url"), "last_seen": today})
        existing[jid] = sanitize(cur)
    listings = sorted(existing.values(), key=lambda x: x["ats_job_id"])
    _write_json(path, {"employer_id": employer_id, "listings": listings})
    return {"new": new, "seen": len(scraped), "stored": len(listings)}


# date/time are SAST; run_at is ISO 8601 with +02:00 offset.
# complete=false on an ok run means the page cap was hit (not a full snapshot:
# do not use that run to infer closures).
RUNLOG_FIELDS = ("date", "time", "run_at", "runner", "employer_id", "ats_type", "status", "count",
                 "complete", "http_status", "pages", "elapsed_s", "note")


def append_runlog(data_dir: str, entries: list[dict]) -> None:
    path = os.path.join(data_dir, "runlog.json")
    log = _read_json(path, [])
    for e in entries:
        log.append({k: e.get(k) for k in RUNLOG_FIELDS})
    _write_json(path, log)
