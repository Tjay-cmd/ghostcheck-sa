"""Workday CXS JSON API fetcher/parser."""
from __future__ import annotations

import json
import re

from .classify import BLOCKED, ERROR, OK, classify_http

PAGE_SIZE = 20  # Workday rejects limit > 20


def endpoint(emp: dict) -> str:
    return f"https://{emp['host']}/wday/cxs/{emp['tenant']}/{emp['site']}/jobs"


def public_base(emp: dict) -> str:
    return f"https://{emp['host']}/{emp['site']}"


_ID_RE = re.compile(r"_([A-Za-z]*-?\d[\w-]*)$")


def job_id_from_path(path: str) -> str:
    """'/job/Cape-Town/Contracts-Specialist_JR-83572' -> 'JR-83572'."""
    m = _ID_RE.search(path or "")
    return m.group(1) if m else (path or "").rsplit("/", 1)[-1]


def parse_page(data: dict, emp: dict) -> tuple[list[dict], int | None]:
    """Return (listings, total). Only allowed fields are extracted."""
    postings = data.get("jobPostings")
    if postings is None or not isinstance(postings, list):
        raise ValueError("no jobPostings array")
    out = []
    for p in postings:
        path = p.get("externalPath") or ""
        title = (p.get("title") or "").strip()
        if not path or not title:
            continue
        out.append({
            "ats_job_id": job_id_from_path(path),
            "title": title,
            "location": (p.get("locationsText") or "").strip(),
            "url": public_base(emp) + path,
        })
    total = data.get("total")
    return out, (int(total) if isinstance(total, (int, float)) else None)


def fetch(emp: dict, session, cfg: dict, sleep) -> dict:
    """Fetch all pages (capped). Returns a result dict for the run log."""
    url = endpoint(emp)
    listings: dict[str, dict] = {}
    total = None
    last_http = None
    pages = 0
    max_pages = cfg["max_pages"]
    offset = 0
    while pages < max_pages:
        if pages:
            sleep(cfg["delay_seconds"])
        body = {"limit": PAGE_SIZE, "offset": offset, "appliedFacets": {}, "searchText": ""}
        try:
            r = session.post(url, json=body, timeout=cfg["timeout_seconds"],
                             headers={"Accept": "application/json", "Content-Type": "application/json"})
        except Exception as e:  # network error
            return _result(ERROR, listings, last_http, pages,
                           f"request failed on page {pages + 1}: {type(e).__name__}")
        last_http = r.status_code
        status, note = classify_http(r.status_code, r.text, "json")
        if status != OK:
            if listings:
                note = f"partial ({len(listings)} listings) then {note} on page {pages + 1}"
            return _result(status, listings, last_http, pages, note)
        try:
            page, page_total = parse_page(json.loads(r.text), emp)
        except (ValueError, json.JSONDecodeError) as e:
            return _result(ERROR, listings, last_http, pages, f"parse error page {pages + 1}: {e}"[:160])
        pages += 1
        if total is None and page_total:
            total = page_total  # Workday often only returns total on the first page
        for item in page:
            listings[item["ats_job_id"]] = item
        offset += PAGE_SIZE
        if not page or (total is not None and offset >= total):
            break
    capped = pages >= max_pages and (total is None or offset < total)
    note = f"total={total}" if total is not None else "total unknown"
    if capped:
        note += f"; page cap {max_pages} hit (incomplete snapshot)"
    return _result(OK, listings, last_http, pages, note, complete=not capped)


def _result(status, listings, http, pages, note, complete=False):
    return {"status": status, "listings": list(listings.values()), "http_status": http,
            "pages": pages, "note": note, "complete": complete}
