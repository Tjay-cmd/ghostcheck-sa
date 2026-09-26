"""Entry point: python -m ghostcheck.run [--config ...] [--data-dir ...] [--only id,id]

Never raises for a single employer failure; always exits 0 unless the config
itself is broken, so the Actions job still commits whatever was collected.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from . import store, successfactors, workday
from .classify import ERROR, OK

SAST = timezone(timedelta(hours=2))  # South Africa has no DST
# Honest, identifiable UA. Set GHOSTCHECK_CONTACT (e.g. the repo URL) in the workflow.
USER_AGENT = ("Mozilla/5.0 (compatible; GhostCheckSA-M0/0.1; daily job-freshness research; "
              "~1 req/1.5s" + (f"; +{os.environ['GHOSTCHECK_CONTACT']}" if os.environ.get("GHOSTCHECK_CONTACT") else "") + ")")
FETCHERS = {"workday": workday.fetch, "successfactors": successfactors.fetch}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-ZA,en;q=0.9"})
    return s


def run(config_path: str, data_dir: str, only: set[str] | None = None, sleep=time.sleep,
        session=None, now=None) -> list[dict]:
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    defaults = cfg.get("defaults", {})
    now = now or datetime.now(SAST)  # one timestamp per run: all employers share date/time
    today = now.date().isoformat()
    runner = "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"
    session = session or make_session()
    entries = []
    employers = [e for e in cfg["employers"] if not only or e["id"] in only]
    for i, emp in enumerate(employers):
        if i:
            sleep(defaults.get("delay_seconds", 1.5))
        ecfg = {"delay_seconds": 1.5, "max_pages": 40, "timeout_seconds": 30, **defaults,
                **emp.get("overrides", {})}
        t0 = time.monotonic()
        try:
            res = FETCHERS[emp["ats_type"]](emp, session, ecfg, sleep)
        except Exception as e:  # never let one employer kill the run
            res = {"status": ERROR, "listings": [], "http_status": None, "pages": 0,
                   "note": f"unhandled {type(e).__name__}: {e}"[:160]}
        elapsed = round(time.monotonic() - t0, 1)
        note = res["note"]
        status = res["status"]
        store.ensure_listings_file(data_dir, emp["id"])
        if status == OK:
            # Only a successful check may touch listing data (handoff B3.2/B3.3).
            try:
                c = store.upsert_listings(data_dir, emp["id"], res["listings"], today)
                note = (note + f"; new={c['new']}").strip("; ")
            except Exception as e:
                status = ERROR
                note = (note + f"; store failed: {type(e).__name__}").strip("; ")
        elif res["listings"]:
            note = (note + "; listing data NOT written (run not ok)").strip("; ")
        entry = {"date": today, "time": now.strftime("%H:%M:%S"),
                 "run_at": now.isoformat(timespec="seconds"), "runner": runner,
                 "employer_id": emp["id"], "ats_type": emp["ats_type"], "status": status,
                 "count": len(res["listings"]) if status == OK else 0,
                 "complete": bool(res.get("complete")) if status == OK else None,
                 "http_status": res["http_status"],
                 "pages": res["pages"], "elapsed_s": elapsed, "note": note[:200]}
        entries.append(entry)
        print(f"{emp['id']:<12} {emp['ats_type']:<15} {entry['status']:<8} count={entry['count']:<5} "
              f"http={entry['http_status']} pages={entry['pages']} {elapsed}s  {entry['note']}", flush=True)
    store.append_runlog(data_dir, entries)
    return entries


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "..", "config", "employers.json"))
    ap.add_argument("--data-dir", default=os.path.join(HERE, "..", "history"))
    ap.add_argument("--only", default="", help="comma-separated employer ids")
    a = ap.parse_args(argv)
    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    entries = run(a.config, a.data_dir, only)
    ok = sum(e["status"] == "ok" for e in entries)
    print(f"summary: {ok}/{len(entries)} ok, "
          f"{sum(e['status'] == 'blocked' for e in entries)} blocked, "
          f"{sum(e['status'] == 'error' for e in entries)} error")
    return 0


if __name__ == "__main__":
    sys.exit(main())
