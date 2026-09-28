"""M1 pipeline: turn history/ (M0 raw scrape output) into the data/ contract.

Usage: python -m ghostcheck_pipeline.build [--repo-root ...]

Reads config/{employers,rules,site,corrections}.json and history/{listings/*,runlog}.json,
computes every derived field the contract locks (age_state, reposted, repost_count,
open_before_tracking, days_seen, chain_first_seen, metrics, check_status, overview
eligibility, stale info), and writes data/site.json, data/employers/*.json,
data/listings/*.json, data/overview.json, data/search-index.json and
data/corrections-log.json. Idempotent: re-running on the same history produces the
same output (byte-identical apart from build_time/generated_at).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile

from . import metrics as M
from . import normalize as N
from .ids import Register

SAST = dt.timezone(dt.timedelta(hours=2))
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def _write_json(path: str, data, minify: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        if minify:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    os.replace(tmp, path)


def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def _plus(d: str, n: int) -> str:
    return (dt.date.fromisoformat(d) + dt.timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# Per-employer run stats (from history/runlog.json)
# ---------------------------------------------------------------------------

def employer_run_stats(runs: list[dict]) -> dict:
    runs = sorted(runs, key=lambda r: r["run_at"])
    ok_runs = [r for r in runs if r["status"] == "ok"]
    last_run = None
    if runs:
        r = runs[-1]
        last_run = {"date": r["date"], "time": r["time"][:5], "status": r["status"]}
    consecutive_failed = 0
    for r in reversed(runs):
        if r["status"] == "ok":
            break
        consecutive_failed += 1
    return {
        "tracked_since": ok_runs[0]["date"] if ok_runs else None,
        "last_successful_check_at": ok_runs[-1]["run_at"] if ok_runs else None,
        "last_run": last_run,
        "consecutive_failed_runs": consecutive_failed,
        "ok_run_dates": sorted({r["date"] for r in ok_runs}),
    }


def check_status(tracked_since, consecutive_failed_runs, failed_streak_warning_runs) -> str:
    if not tracked_since:
        return "no_data"
    if consecutive_failed_runs >= failed_streak_warning_runs:
        return "failed_streak"
    if consecutive_failed_runs:
        return "last_run_failed"
    return "ok"


# ---------------------------------------------------------------------------
# Per-listing open/closed detection
# ---------------------------------------------------------------------------

def compute_status(ok_dates: list[str], last_seen: str, close_after: int):
    """A listing is closed once it has been missing from `close_after`
    consecutive *successful* checks after its last_seen (contract B3.3)."""
    later_oks = [d for d in ok_dates if d > last_seen]
    if len(later_oks) >= close_after:
        return "closed", later_oks[close_after - 1]
    return "open", None


def age_state(status: str, days_seen: int, open_before_tracking: bool, rules: dict) -> str:
    if status == "closed":
        return "closed"
    if days_seen <= rules["FRESH_MAX_DAYS"] and not open_before_tracking:
        return "fresh"
    if days_seen >= rules["LONG_OPEN_MIN_DAYS"]:
        return "long_open"
    return "seen"


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(root: str, now: dt.datetime | None = None) -> None:
    now = now or dt.datetime.now(SAST)
    build_time = now.isoformat(timespec="seconds")

    cfg_dir = os.path.join(root, "config")
    data_dir = os.path.join(root, "data")
    history_dir = os.path.join(root, "history")

    registry = _read_json(os.path.join(cfg_dir, "employers.json"))["employers"]
    rules = _read_json(os.path.join(cfg_dir, "rules.json"))
    corrections = _read_json(os.path.join(cfg_dir, "corrections.json"))["corrections"]

    runlog = _read_json(os.path.join(history_dir, "runlog.json"), [])
    runs_by_employer: dict[str, list] = {}
    for r in runlog:
        runs_by_employer.setdefault(r["employer_id"], []).append(r)
    data_date = max((r["date"] for r in runlog), default=None)

    register = Register(os.path.join(history_dir, "listing_id_register.json"))

    hidden_ids = {c["listing_id"] for c in corrections if c["type"] == "hide_listing"
                  and (c["status"] == "upheld"
                       or (c["status"] == "pending_review" and c.get("reason") == "personal_data_claim"))}
    upheld_fixes: dict[str, list[dict]] = {}
    for c in corrections:
        if c["type"] == "fix_listing_field" and c["status"] == "upheld":
            upheld_fixes.setdefault(c["listing_id"], []).append(c)
    suppressed_links = {(c["listing_id"], c["earlier_listing_id"]) for c in corrections
                         if c["type"] == "suppress_repost_link" and c["status"] == "upheld"}

    employer_stats = {}
    for emp in registry:
        stats = employer_run_stats(runs_by_employer.get(emp["id"], []))
        stats["check_status"] = check_status(stats["tracked_since"], stats["consecutive_failed_runs"],
                                              rules["FAILED_STREAK_WARNING_RUNS"])
        employer_stats[emp["id"]] = stats

    # ---- stage 1: raw -> base listing records (per employer, id assigned, corrections applied) ----
    listings: dict[str, dict] = {}  # listing_id -> record (published only)
    for emp in registry:
        eid = emp["id"]
        stats = employer_stats[eid]
        if not stats["tracked_since"]:
            continue
        raw = _read_json(os.path.join(history_dir, "listings", f"{eid}.json"), {"listings": []})["listings"]
        for item in raw:
            jid = str(item["ats_job_id"])
            lid = register.listing_id(eid, jid)
            title, location = item["title"], item["location"]
            correction_ids = []
            for fix in upheld_fixes.get(lid, []):
                if fix["field"] == "title":
                    title = fix["value"]
                elif fix["field"] == "location":
                    location = fix["value"]
                correction_ids.append(fix["id"])
            if lid in hidden_ids:
                continue
            status, closed_on = compute_status(stats["ok_run_dates"], item["last_seen"],
                                                rules["CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS"])
            first_seen, last_seen = item["first_seen"], item["last_seen"]
            days_seen = _days(first_seen, last_seen)
            obt = first_seen == stats["tracked_since"]
            norm_title = N.normalised_title(title)
            norm_location = N.normalised_location(location)
            listings[lid] = {
                "listing_id": lid,
                "employer_id": eid,
                "ats_job_id": jid,
                "title": title,
                "normalised_title": norm_title,
                "location": location,
                "normalised_location": norm_location,
                "fingerprint": N.fingerprint(eid, norm_title, norm_location),
                "url": item["url"],
                "apply_domain": N.apply_domain(item["url"]),
                "first_seen": first_seen,
                "last_seen": last_seen,
                "days_seen": days_seen,
                "status": status,
                "closed_on": closed_on,
                "gaps": [],
                "open_before_tracking": obt,
                "age_state": age_state(status, days_seen, obt, rules),
                "correction_ids": correction_ids,
                "repost_of": None,
                "chain": [],
                "later_reposts": [],
            }

    # ---- stage 2: repost-chain detection (same employer, same fingerprint) ----
    by_fingerprint: dict[str, list[dict]] = {}
    for l in listings.values():
        by_fingerprint.setdefault(l["fingerprint"], []).append(l)
    for group in by_fingerprint.values():
        group.sort(key=lambda l: (l["first_seen"], l["listing_id"]))
        for i in range(1, len(group)):
            later, earlier = group[i], group[i - 1]
            if (later["listing_id"], earlier["listing_id"]) in suppressed_links:
                continue
            if earlier["status"] == "open" or earlier["closed_on"] is None:
                gap = 0
            elif earlier["closed_on"] <= later["first_seen"]:
                gap = _days(earlier["closed_on"], later["first_seen"])
            else:
                continue
            if gap > rules["REPOST_WINDOW_DAYS"] or earlier["first_seen"] >= later["first_seen"]:
                continue
            later["repost_of"] = {"listing_id": earlier["listing_id"], "match_basis": "same_title_location",
                                   "gap_days": gap}
            later["chain"] = [{
                "listing_id": earlier["listing_id"], "title": earlier["title"], "location": earlier["location"],
                "first_seen": earlier["first_seen"], "last_seen": earlier["last_seen"],
                "days_seen": earlier["days_seen"], "status": earlier["status"], "closed_on": earlier["closed_on"],
                "match_basis": "same_title_location", "gap_days": gap,
            }] + earlier["chain"]

    for l in listings.values():
        l["repost_count"] = len(l["chain"])
        l["reposted"] = l["repost_count"] > 0
        l["chain_first_seen"] = l["chain"][-1]["first_seen"] if l["chain"] else None

    for l in listings.values():
        for hop in l["chain"]:
            earlier = listings.get(hop["listing_id"])
            if earlier is not None:
                earlier["later_reposts"].append({"listing_id": l["listing_id"], "first_seen": l["first_seen"],
                                                  "status": l["status"]})
    for l in listings.values():
        l["later_reposts"].sort(key=lambda x: (x["first_seen"], x["listing_id"]))

    # ---- stage 3: per-employer aggregates, metrics, overview eligibility ----
    reg_by_id = {e["id"]: e for e in registry}
    employer_docs = {}
    for emp in registry:
        eid = emp["id"]
        stats = employer_stats[eid]
        mine = [l for l in listings.values() if l["employer_id"] == eid]
        open_l = [l for l in mine if l["status"] == "open"]
        tracked_days = _days(stats["tracked_since"], data_date) if stats["tracked_since"] and data_date else None
        has_data = stats["tracked_since"] is not None

        if not has_data:
            m_open = M.unavailable("count", "no_data")
            m_median = M.unavailable("days", "no_data")
            m_share = M.unavailable("percent", "no_data")
            m_repost = M.unavailable("percent", "no_data")
            long_open_from = None
        else:
            m_open = M.count_metric(len(open_l))
            gate = (tracked_days >= rules["EMPLOYER_METRICS_MIN_TRACKED_DAYS"]
                    and len(mine) >= rules["EMPLOYER_METRICS_MIN_LISTINGS_SEEN"])
            available_from = None
            if not gate and len(mine) >= rules["EMPLOYER_METRICS_MIN_LISTINGS_SEEN"] \
                    and tracked_days < rules["EMPLOYER_METRICS_MIN_TRACKED_DAYS"]:
                available_from = _plus(stats["tracked_since"], rules["EMPLOYER_METRICS_MIN_TRACKED_DAYS"])

            if not gate:
                m_median = M.unavailable("days", "gate", available_from)
                m_share = M.unavailable("percent", "gate", available_from)
                m_repost = M.unavailable("percent", "gate", available_from)
            else:
                if open_l:
                    m_median = M.days_metric(M.median_days_seen([l["days_seen"] for l in open_l]))
                    long_open_count = sum(1 for l in open_l if l["days_seen"] >= rules["LONG_OPEN_MIN_DAYS"])
                    m_share = M.percent_metric(long_open_count, len(open_l))
                else:
                    m_median = M.unavailable("days", "no_open")
                    m_share = M.unavailable("percent", "no_open")
                m_repost = _repost_rate_metric(mine, stats["tracked_since"], data_date, rules)

            long_open_from = _plus(stats["tracked_since"], rules["LONG_OPEN_MIN_DAYS"])
            if long_open_from <= data_date:
                long_open_from = None

        active = emp["active"]
        if not active:
            ov_eligible, ov_from, ov_reason = False, None, "inactive"
        elif not has_data:
            ov_eligible, ov_from, ov_reason = False, None, "no_data"
        else:
            tracked_ok = tracked_days >= rules["OVERVIEW_MIN_TRACKED_DAYS"]
            open_ok = len(open_l) >= rules["OVERVIEW_MIN_OPEN_LISTINGS"]
            if tracked_ok and open_ok:
                ov_eligible, ov_from, ov_reason = True, None, None
            else:
                ov_eligible = False
                ov_reason = ("tracked_days" if not tracked_ok and open_ok else
                             "open_listings" if tracked_ok and not open_ok else
                             "tracked_days_and_open_listings")
                ov_from = _plus(stats["tracked_since"], rules["OVERVIEW_MIN_TRACKED_DAYS"]) if open_ok else None

        recently_closed = [l for l in mine if l["status"] == "closed"
                            and l["closed_on"] >= _plus(data_date, -rules["RECENTLY_CLOSED_WINDOW_DAYS"])] \
            if data_date else []

        employer_docs[eid] = {
            "schema_version": SCHEMA_VERSION,
            "id": eid, "slug": emp["slug"], "name": emp["name"], "sector": emp["sector"],
            "ats_type": emp["ats_type"], "source_url": emp["source_url"], "active": active,
            "tracked_since": stats["tracked_since"], "tracked_days": tracked_days, "has_data": has_data,
            "last_run": stats["last_run"], "last_successful_check_at": stats["last_successful_check_at"],
            "consecutive_failed_runs": stats["consecutive_failed_runs"], "check_status": stats["check_status"],
            "total_listings_seen": len(mine),
            "metrics": {"open_count": m_open, "median_days_seen": m_median, "share_open_90": m_share,
                        "repost_rate": m_repost, "long_open_possible_from": long_open_from},
            "overview": {"eligible": ov_eligible, "eligible_from": ov_from, "reason": ov_reason},
            "listings": {
                "open": [_summary(l, emp) for l in sorted(open_l, key=lambda l: (l["first_seen"], l["listing_id"]),
                                                            reverse=True)],
                "recently_closed": [_summary(l, emp) for l in
                                     sorted(recently_closed, key=lambda l: l["closed_on"], reverse=True)],
            },
        }

    # ---- stage 4: finish listing docs (employer context, more_at_employer) ----
    listing_docs = {}
    for l in listings.values():
        emp = reg_by_id[l["employer_id"]]
        edoc = employer_docs[l["employer_id"]]
        open_here = [o for o in listings.values() if o["employer_id"] == l["employer_id"]
                     and o["status"] == "open" and o["listing_id"] != l["listing_id"]]
        open_here.sort(key=lambda o: (o["first_seen"], o["listing_id"]), reverse=True)
        listing_docs[l["listing_id"]] = {
            "schema_version": SCHEMA_VERSION,
            "listing_id": l["listing_id"], "employer_id": l["employer_id"], "employer_slug": emp["slug"],
            "employer_name": emp["name"], "ats_job_id": l["ats_job_id"], "title": l["title"],
            "normalised_title": l["normalised_title"], "location": l["location"],
            "normalised_location": l["normalised_location"], "fingerprint": l["fingerprint"], "url": l["url"],
            "apply_domain": l["apply_domain"], "first_seen": l["first_seen"], "last_seen": l["last_seen"],
            "days_seen": l["days_seen"], "status": l["status"], "closed_on": l["closed_on"], "gaps": l["gaps"],
            "age_state": l["age_state"], "open_before_tracking": l["open_before_tracking"],
            "reposted": l["reposted"], "repost_count": l["repost_count"], "chain_first_seen": l["chain_first_seen"],
            "repost_of": l["repost_of"], "chain": l["chain"], "later_reposts": l["later_reposts"],
            "correction_ids": l["correction_ids"],
            "employer": {
                "tracked_since": edoc["tracked_since"], "active": edoc["active"], "last_run": edoc["last_run"],
                "last_successful_check_at": edoc["last_successful_check_at"],
                "consecutive_failed_runs": edoc["consecutive_failed_runs"], "check_status": edoc["check_status"],
                "open_count": edoc["metrics"]["open_count"]["value"] or 0,
            },
            "more_at_employer": [_summary(o, emp) for o in open_here[:3]],
        }

    # ---- stage 5: site-level roll-up ----
    site = _build_site(build_time, data_date, runlog, employer_docs, rules)

    # ---- stage 6: overview ----
    overview = _build_overview(build_time, data_date, employer_docs)

    # ---- stage 7: search index ----
    search_index = _build_search_index(build_time, listing_docs, employer_docs)

    # ---- stage 8: corrections log ----
    corrections_log = _build_corrections_log(corrections, reg_by_id)

    # ---- write everything ----
    _write_json(os.path.join(data_dir, "site.json"), site)
    for eid, doc in employer_docs.items():
        _write_json(os.path.join(data_dir, "employers", f"{eid}.json"), doc)
    # remove stale listing files for listings no longer published (e.g. newly hidden)
    listings_out_dir = os.path.join(data_dir, "listings")
    os.makedirs(listings_out_dir, exist_ok=True)
    for name in os.listdir(listings_out_dir):
        lid = name[:-5]
        if name.endswith(".json") and lid not in listing_docs:
            os.remove(os.path.join(listings_out_dir, name))
    for lid, doc in listing_docs.items():
        _write_json(os.path.join(listings_out_dir, f"{lid}.json"), doc)
    _write_json(os.path.join(data_dir, "overview.json"), overview)
    _write_json(os.path.join(data_dir, "search-index.json"), search_index, minify=True)
    _write_json(os.path.join(data_dir, "corrections-log.json"), corrections_log)
    register.save()


def _repost_rate_metric(mine: list[dict], tracked_since: str, data_date: str, rules: dict) -> dict:
    full_window_start = _plus(data_date, -rules["REPOST_RATE_WINDOW_DAYS"] + 1)
    window_start = max(tracked_since, full_window_start)
    in_window = [l for l in mine if l["first_seen"] >= window_start]
    if not in_window:
        return M.unavailable("percent", "no_open")
    reposted_in_window = sum(1 for l in in_window if l["repost_of"])
    label = f"last {rules['REPOST_RATE_WINDOW_DAYS']} days" if window_start == full_window_start \
        else _since_label(window_start)
    return M.percent_metric(reposted_in_window, len(in_window), label, window_start)


def _since_label(window_start: str) -> str:
    d = dt.date.fromisoformat(window_start)
    return f"since {d.day} {d.strftime('%b')} {d.year}"


def _summary(l: dict, emp: dict) -> dict:
    return {
        "listing_id": l["listing_id"], "employer_slug": emp["slug"], "employer_name": emp["name"],
        "title": l["title"], "location": l["location"], "first_seen": l["first_seen"],
        "last_seen": l["last_seen"], "days_seen": l["days_seen"], "status": l["status"],
        "closed_on": l["closed_on"], "age_state": l["age_state"],
        "open_before_tracking": l["open_before_tracking"], "reposted": l["reposted"],
        "repost_count": l["repost_count"], "chain_first_seen": l["chain_first_seen"],
    }


def _build_site(build_time, data_date, runlog, employer_docs, rules) -> dict:
    ok_run_ats = [r["run_at"] for r in runlog if r["status"] == "ok"]
    last_successful_run_at = max(ok_run_ats) if ok_run_ats else None
    last_run_at = max((r["run_at"] for r in runlog), default=None)
    last_run_rows = [r for r in runlog if r["run_at"] == last_run_at] if last_run_at else []

    open_all = [s for e in employer_docs.values() for s in e["listings"]["open"]]
    total_listings = sum(e["total_listings_seen"] for e in employer_docs.values())
    stale_after = None
    stale_at_build = False
    if last_successful_run_at:
        last_ok_dt = dt.datetime.fromisoformat(last_successful_run_at)
        stale_after_dt = last_ok_dt + dt.timedelta(hours=rules["STALE_BUILD_HOURS"])
        stale_after = stale_after_dt.isoformat()
        stale_at_build = dt.datetime.fromisoformat(build_time) > stale_after_dt

    tracked_list = [e["tracked_since"] for e in employer_docs.values() if e["tracked_since"]]
    tracking_started_on = min(tracked_list) if tracked_list else None
    earliest_long_open_possible_on = (_plus(tracking_started_on, rules["LONG_OPEN_MIN_DAYS"])
                                       if tracking_started_on else None)

    closed_listings_count = sum(e["total_listings_seen"] - e["metrics"]["open_count"]["value"]
                                 if e["metrics"]["open_count"]["value"] is not None else 0
                                 for e in employer_docs.values())

    return {
        "schema_version": SCHEMA_VERSION,
        "build_time": build_time,
        "data_date": data_date,
        "last_successful_run_at": last_successful_run_at,
        "tracking_started_on": tracking_started_on,
        "stale": {
            "stale_after": stale_after, "stale_at_build": stale_at_build,
            "last_run_date": last_run_rows[0]["date"] if last_run_rows else None,
            "last_run_employers_ok": sum(1 for r in last_run_rows if r["status"] == "ok"),
            "last_run_employers_failed": sum(1 for r in last_run_rows if r["status"] != "ok"),
        },
        "counts": {
            "open_listings": len(open_all),
            "employers_tracked": sum(1 for e in employer_docs.values() if e["active"]),
            "employers_with_data": sum(1 for e in employer_docs.values() if e["active"] and e["tracked_since"]),
            "fresh": sum(1 for s in open_all if s["age_state"] == "fresh"),
            "seen": sum(1 for s in open_all if s["age_state"] == "seen"),
            "long_open": sum(1 for s in open_all if s["age_state"] == "long_open"),
            "reposted_open": sum(1 for s in open_all if s["reposted"]),
            "open_before_tracking_open": sum(1 for s in open_all if s["open_before_tracking"]),
            "closed_listings": closed_listings_count,
            "listings_total": total_listings,
        },
        "earliest_long_open_possible_on": earliest_long_open_possible_on,
    }


def _build_overview(build_time, data_date, employer_docs) -> dict:
    eligible_rows = []
    not_yet = []
    for e in employer_docs.values():
        if not e["active"]:
            continue
        if e["overview"]["eligible"]:
            eligible_rows.append({
                "slug": e["slug"], "name": e["name"], "sector": e["sector"], "tracked_since": e["tracked_since"],
                "open_count": e["metrics"]["open_count"]["value"],
                "median_days_seen": e["metrics"]["median_days_seen"], "share_open_90": e["metrics"]["share_open_90"],
                "repost_rate": e["metrics"]["repost_rate"],
            })
        else:
            not_yet.append({
                "slug": e["slug"], "name": e["name"], "sector": e["sector"], "tracked_since": e["tracked_since"],
                "open_count": e["metrics"]["open_count"]["value"], "eligible_from": e["overview"]["eligible_from"],
                "reason": e["overview"]["reason"],
            })
    eligible_rows.sort(key=lambda r: (-(r["share_open_90"]["value"] or 0), r["name"]))
    not_yet.sort(key=lambda r: r["name"])
    froms = [r["eligible_from"] for r in not_yet if r["eligible_from"]]
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": build_time, "data_date": data_date,
        "default_sort": "share_open_90_desc", "employers": eligible_rows, "not_yet_eligible": not_yet,
        "earliest_eligible_from": min(froms) if froms else None,
    }


def _build_search_index(build_time, listing_docs, employer_docs) -> dict:
    open_docs = [l for l in listing_docs.values() if l["status"] == "open" and employer_docs[l["employer_id"]]["active"]]
    open_docs.sort(key=lambda l: (l["first_seen"], l["listing_id"]), reverse=True)
    slugs = sorted({l["employer_slug"] for l in open_docs})
    slug_index = {s: i for i, s in enumerate(slugs)}
    names = {l["employer_slug"]: l["employer_name"] for l in open_docs}
    rows = [[l["listing_id"], slug_index[l["employer_slug"]], l["title"], l["location"], l["first_seen"],
             l["days_seen"], l["age_state"], int(l["open_before_tracking"]), int(l["reposted"]), l["repost_count"]]
            for l in open_docs]
    return {
        "v": 1, "generated_at": build_time,
        "fields": ["listing_id", "employer", "title", "location", "first_seen", "days_seen", "age_state",
                   "open_before_tracking", "reposted", "repost_count"],
        "employers": [[s, names[s]] for s in slugs],
        "rows": rows,
    }


def _build_corrections_log(corrections, reg_by_id) -> dict:
    entries = [{
        "date": c["resolved_on"], "employer": reg_by_id[c["employer_id"]]["name"],
        "employer_slug": c["employer_id"], "correction_id": c["id"], "summary": c["public_summary"],
    } for c in corrections if c["status"] == "upheld" and c.get("public_summary") and c["employer_id"] in reg_by_id]
    entries.sort(key=lambda e: e["date"], reverse=True)
    return {"schema_version": SCHEMA_VERSION, "entries": entries}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--repo-root", default=os.path.dirname(here))
    a = ap.parse_args(argv)
    build(a.repo_root)
    print("M1 pipeline build complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
