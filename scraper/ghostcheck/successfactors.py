"""SAP SuccessFactors Recruiting Marketing (RMK) career-site fetcher/parser.

RMK sites (jobs.<company>.co.za etc.) serve a server-rendered search page at
/search/?q=&startrow=N with 25 results per page, in one of two layouts:
  * classic table: <tr class="data-row"> ... <a class="jobTitle-link" href="/job/.../<id>/">
  * tiles:        <li class="job-tile job-id-<id> ..." data-url="/job/.../<id>/">
"""
from __future__ import annotations

import html as htmllib
import re

from .classify import BLOCKED, ERROR, OK, classify_http, looks_like_sf_results

PAGE_SIZE = 25

_TOTAL_RES = [
    re.compile(r"Results\s*<b>[\d,\s\u2013-]+</b>\s*of\s*<b>([\d,]+)</b>", re.I),
    re.compile(r"Showing\s+\d+\s+to\s+\d+\s+of\s+([\d,]+)", re.I),
]
_ROW_RE = re.compile(r'<tr class="data-row[^"]*">(.*?)</tr>', re.S)
_ROW_LINK_RE = re.compile(r'<a href="([^"]*/job/[^"]*?/(\d+)/)"[^>]*class="jobTitle-link"[^>]*>(.*?)</a>', re.S)
_ROW_LINK_RE2 = re.compile(r'<a[^>]*class="jobTitle-link"[^>]*href="([^"]*/job/[^"]*?/(\d+)/)"[^>]*>(.*?)</a>', re.S)
_ROW_LOC_RE = re.compile(r'<span class="jobLocation">(.*?)</span>', re.S)
_TILE_RE = re.compile(r'<li class="job-tile job-id-(\d+)[^"]*"[^>]*data-url="([^"]+)"(.*?)</li>', re.S)
_TILE_TITLE_RE = re.compile(r'<a[^>]*class="jobTitle-link[^"]*"[^>]*>(.*?)</a>', re.S)
_TILE_FIELD_RE = re.compile(r'<div id="job-\d+-desktop-section-(\w+)-value"[^>]*>(.*?)</div>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_LOCATION_FIELDS = ("multilocation", "location", "city", "state", "country")


def _clean(s: str) -> str:
    return _WS_RE.sub(" ", htmllib.unescape(_TAG_RE.sub(" ", s or ""))).strip()


def parse_total(html: str) -> int | None:
    for rx in _TOTAL_RES:
        m = rx.search(html)
        if m:
            return int(m.group(1).replace(",", ""))
    return None


def parse_page(html: str, base_url: str) -> tuple[list[dict], int | None]:
    if not looks_like_sf_results(html):
        raise ValueError("no RMK search results markup")
    out: dict[str, dict] = {}
    for row in _ROW_RE.findall(html):
        m = _ROW_LINK_RE.search(row) or _ROW_LINK_RE2.search(row)
        if not m:
            continue
        href, jid, title = m.group(1), m.group(2), _clean(m.group(3))
        loc = _ROW_LOC_RE.search(row)
        out[jid] = {"ats_job_id": jid, "title": title, "location": _clean(loc.group(1)) if loc else "",
                    "url": _abs(base_url, href)}
    for jid, href, body in _TILE_RE.findall(html):
        t = _TILE_TITLE_RE.search(body)
        if not t:
            continue
        fields = {}
        for name, val in _TILE_FIELD_RE.findall(body):
            fields.setdefault(name, _clean(val))
        loc = fields.get("multilocation") or ", ".join(
            fields[f] for f in ("city", "state", "country", "location") if fields.get(f))
        out.setdefault(jid, {"ats_job_id": jid, "title": _clean(t.group(1)), "location": loc,
                             "url": _abs(base_url, href)})
    return list(out.values()), parse_total(html)


def _abs(base_url: str, href: str) -> str:
    href = htmllib.unescape(href)
    if href.startswith("http"):
        return href
    from urllib.parse import urlsplit
    p = urlsplit(base_url)
    return f"{p.scheme}://{p.netloc}{href}"


def search_url(emp: dict, startrow: int) -> str:
    return f"{emp['base_url'].rstrip('/')}/search/?q=&sortColumn=referencedate&sortDirection=desc&startrow={startrow}"


def fetch(emp: dict, session, cfg: dict, sleep) -> dict:
    listings: dict[str, dict] = {}
    total = None
    last_http = None
    pages = 0
    startrow = 0
    natural_end = False
    while pages < cfg["max_pages"]:
        if pages:
            sleep(cfg["delay_seconds"])
        try:
            r = session.get(search_url(emp, startrow), timeout=cfg["timeout_seconds"],
                            headers={"Accept": "text/html,application/xhtml+xml"})
        except Exception as e:
            return _result(ERROR, listings, last_http, pages,
                           f"request failed on page {pages + 1}: {type(e).__name__}")
        last_http = r.status_code
        status, note = classify_http(r.status_code, r.text, "html")
        if status != OK:
            if listings:
                note = f"partial ({len(listings)} listings) then {note} on page {pages + 1}"
            return _result(status, listings, last_http, pages, note)
        try:
            page, page_total = parse_page(r.text, emp["base_url"])
        except ValueError as e:
            return _result(ERROR, listings, last_http, pages, f"parse error page {pages + 1}: {e}")
        pages += 1
        if page_total is not None:
            total = page_total
        new = 0
        for item in page:
            if item["ats_job_id"] not in listings:
                new += 1
            listings[item["ats_job_id"]] = item
        startrow += PAGE_SIZE
        if not page or new == 0 or (total is not None and startrow >= total):
            natural_end = True
            break
    note = f"total={total}" if total is not None else "total unknown"
    if not natural_end:
        note += f"; page cap {cfg['max_pages']} hit (incomplete snapshot)"
    return _result(OK, listings, last_http, pages, note, complete=natural_end)


def _result(status, listings, http, pages, note, complete=False):
    return {"status": status, "listings": list(listings.values()), "http_status": http,
            "pages": pages, "note": note, "complete": complete}
