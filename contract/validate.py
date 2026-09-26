#!/usr/bin/env python3
"""Validate every GhostCheck SA contract sample against its JSON schema, then run cross-file consistency checks.

Usage:  python validate.py [repo_root]        (default: the folder this script is in)
Needs:  jsonschema>=4.18  (pip install "jsonschema>=4.18")
Exit code 0 = all good, 1 = at least one problem.
"""
import datetime as dt
import glob
import json
import os
import re
import statistics
import sys

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(HERE)
SCHEMAS = os.path.join(HERE, "schemas")

# file glob (relative to repo root) -> schema file
TARGETS = [
    ("config/rules.json", "rules"),
    ("config/site.json", "site-config"),
    ("config/employers.json", "employers-registry"),
    ("config/corrections.json", "corrections"),
    ("data/site.json", "site"),
    ("data/employers/*.json", "employer"),
    ("data/listings/*.json", "listing"),
    ("data/overview.json", "overview"),
    ("data/search-index.json", "search-index"),
    ("data/corrections-log.json", "corrections-log"),
]
FORBIDDEN_KEY = re.compile(r"salary|remuneration|description|recruiter|contact|email|phone|hiring_manager", re.I)
ALLOWED_KEYS = {"CORRECTIONS_EMAIL"}
errors = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def days(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def plus(d, n):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=n)).isoformat()


def walk_keys(obj, where):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if FORBIDDEN_KEY.search(k) and k not in ALLOWED_KEYS:
                err(where, f"POPIA: forbidden field name '{k}'")
            walk_keys(v, where)
    elif isinstance(obj, list):
        for v in obj:
            walk_keys(v, where)


# ---------- 1. schema validation ----------
registry = Registry()
schemas = {}
for p in glob.glob(os.path.join(SCHEMAS, "*.schema.json")):
    s = load(p)
    Draft202012Validator.check_schema(s)
    registry = registry.with_resource(s["$id"], Resource.from_contents(s))
    schemas[os.path.basename(p)[: -len(".schema.json")]] = s

docs = {}
checked = 0
for pattern, name in TARGETS:
    files = sorted(glob.glob(os.path.join(ROOT, pattern)))
    if not files:
        err(pattern, "no file found")
    v = Draft202012Validator(schemas[name], registry=registry)
    for f in files:
        rel = os.path.relpath(f, ROOT)
        doc = load(f)
        docs[rel] = doc
        checked += 1
        for e in sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path)):
            err(rel, f"schema {name}: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}")
        walk_keys(doc, rel)
print(f"schema: {checked} files checked against {len(schemas)} schemas")
if errors:  # consistency checks assume schema-valid input
    print("\n".join("FAIL " + e for e in errors))
    sys.exit(1)

# ---------- 2. consistency checks ----------
R = docs["config/rules.json"]
bs = os.path.join(ROOT, "..", "ux", "badge-system.md")
if os.path.exists(bs):  # rules.json must match badge-system.md §2 exactly
    md = {k: int(v) for k, v in re.findall(r"^\|\s*`([A-Z_]+)`\s*\|\s*\*\*(\d+)\*\*", open(bs, encoding="utf-8").read(), re.M)}
    if md != R:
        err("config/rules.json", f"does not match badge-system.md §2: {md}")
if docs["config/site.json"]["CORRECTIONS_EMAIL"] != "[CORRECTIONS_EMAIL_TBD]":
    err("config/site.json", "CORRECTIONS_EMAIL must stay the literal placeholder until decided")

reg = {e["id"]: e for e in docs["config/employers.json"]["employers"]}
for e in reg.values():
    if e["slug"] != e["id"]:
        err("config/employers.json", f"{e['id']}: slug must equal id (both stable)")
corr = docs["config/corrections.json"]["corrections"]
hidden = {c["listing_id"] for c in corr if c["type"] == "hide_listing"
          and (c["status"] == "upheld" or (c["status"] == "pending_review" and c.get("reason") == "personal_data_claim"))}
upheld_fix = {c["id"]: c for c in corr if c["type"] == "fix_listing_field" and c["status"] == "upheld"}

emps = {k.split("/")[-1][:-5]: v for k, v in docs.items() if k.startswith("data/employers/")}
lst = {k.split("/")[-1][:-5]: v for k, v in docs.items() if k.startswith("data/listings/")}
site = docs["data/site.json"]
today = site["data_date"]

for slug, e in emps.items():
    w = f"data/employers/{slug}.json"
    if e["slug"] != slug or slug not in reg:
        err(w, "file name must be {slug}.json and slug must exist in config/employers.json")
        continue
    for k in ("name", "sector", "ats_type", "source_url", "active"):
        if e[k] != reg[slug][k]:
            err(w, f"{k} differs from registry")
    mine = [l for l in lst.values() if l["employer_id"] == slug]
    opn = [l for l in mine if l["status"] == "open"]
    m = e["metrics"]
    if e["has_data"] != (e["tracked_since"] is not None):
        err(w, "has_data must equal tracked_since != null")
    if e["tracked_since"]:
        if e["tracked_days"] != days(e["tracked_since"], today):
            err(w, "tracked_days != data_date - tracked_since")
        if m["open_count"]["value"] != len(opn):
            err(w, "open_count != open listing files")
        if e["total_listings_seen"] != len(mine):
            err(w, "total_listings_seen != listing files")
        gate = e["tracked_days"] >= R["EMPLOYER_METRICS_MIN_TRACKED_DAYS"] and len(mine) >= R["EMPLOYER_METRICS_MIN_LISTINGS_SEEN"]
        for k in ("median_days_seen", "share_open_90", "repost_rate"):
            if not gate and (m[k]["available"] or m[k]["unavailable_reason"] != "gate"):
                err(w, f"{k} must be unavailable (gate)")
            if not m[k]["available"] and m[k]["value"] is not None:
                err(w, f"{k}: value must be null when unavailable (never 0%)")
        if gate and opn:
            if m["median_days_seen"]["value"] != int(statistics.median(l["days_seen"] for l in opn)):
                err(w, "median_days_seen wrong")
            lo = sum(l["days_seen"] >= R["LONG_OPEN_MIN_DAYS"] for l in opn)
            if (m["share_open_90"]["numerator"], m["share_open_90"]["denominator"]) != (lo, len(opn)):
                err(w, "share_open_90 numerator/denominator wrong")
        od = e["tracked_days"] >= R["OVERVIEW_MIN_TRACKED_DAYS"] and len(opn) >= R["OVERVIEW_MIN_OPEN_LISTINGS"]
        if e["overview"]["eligible"] != (od and e["active"]):
            err(w, "overview.eligible wrong")
    elif mine or e["listings"]["open"]:
        err(w, "employer without tracked_since must have no listings")
    want = e["check_status"]
    got = ("no_data" if not e["tracked_since"] else "failed_streak" if e["consecutive_failed_runs"] >= R["FAILED_STREAK_WARNING_RUNS"]
           else "last_run_failed" if e["consecutive_failed_runs"] else "ok")
    if want != got:
        err(w, f"check_status should be {got}")
    if [s["listing_id"] for s in e["listings"]["open"]] != [l["listing_id"] for l in sorted(opn, key=lambda l: (l["first_seen"], l["listing_id"]), reverse=True)]:
        err(w, "listings.open must list every open listing, newest first_seen first")
    for s in e["listings"]["open"] + e["listings"]["recently_closed"]:
        full = lst.get(s["listing_id"])
        if not full or any(full[k] != s[k] for k in s if k in full):
            err(w, f"summary {s['listing_id']} differs from its listing file")
    for s in e["listings"]["recently_closed"]:
        if s["status"] != "closed" or s["closed_on"] < plus(today, -R["RECENTLY_CLOSED_WINDOW_DAYS"]):
            err(w, f"{s['listing_id']} is not closed within RECENTLY_CLOSED_WINDOW_DAYS")

for lid, l in lst.items():
    w = f"data/listings/{lid}.json"
    e = emps.get(l["employer_id"])
    if l["listing_id"] != lid:
        err(w, "file name must be {listing_id}.json")
    if lid in hidden:
        err(w, "listing is hidden by a correction and must not be published")
    if not e:
        err(w, "unknown employer")
        continue
    if l["employer_slug"] != e["slug"] or l["employer_name"] != e["name"]:
        err(w, "employer slug/name mismatch")
    if l["days_seen"] != days(l["first_seen"], l["last_seen"]) or l["days_seen"] < 0:
        err(w, "days_seen != last_seen - first_seen")
    if l["last_seen"] > today:
        err(w, "last_seen after data_date")
    if (l["status"] == "open") != (l["closed_on"] is None):
        err(w, "closed_on must be null iff open")
    if l["closed_on"] and l["closed_on"] <= l["last_seen"]:
        err(w, "closed_on must be after last_seen")
    obt = l["first_seen"] == e["tracked_since"]
    if l["open_before_tracking"] != obt:
        err(w, "open_before_tracking != (first_seen == tracked_since)")
    if l["first_seen"] < (e["tracked_since"] or "9999"):
        err(w, "first_seen before tracked_since")
    state = ("closed" if l["status"] == "closed" else
             "fresh" if l["days_seen"] <= R["FRESH_MAX_DAYS"] and not obt else
             "long_open" if l["days_seen"] >= R["LONG_OPEN_MIN_DAYS"] else "seen")
    if l["age_state"] != state:
        err(w, f"age_state should be {state}")
    for g in l["gaps"]:
        if not (l["first_seen"] < g["closed_on"] < g["reopened_on"] <= l["last_seen"]):
            err(w, f"gap {g} outside first_seen..last_seen")
    if l["reposted"] != (l["repost_count"] > 0) or l["repost_count"] != len(l["chain"]) or (l["repost_of"] is None) == l["reposted"]:
        err(w, "reposted / repost_count / chain / repost_of disagree")
    if l["chain_first_seen"] != (l["chain"][-1]["first_seen"] if l["chain"] else None):
        err(w, "chain_first_seen must be first_seen of the oldest chain item")
    newer = l
    for c in l["chain"]:  # newest -> oldest, each step obeys the repost rule
        o = lst.get(c["listing_id"])
        if not o or o["employer_id"] != l["employer_id"] or o["normalised_title"] != l["normalised_title"] \
                or o["normalised_location"] != l["normalised_location"] or o["ats_job_id"] == newer["ats_job_id"]:
            err(w, f"chain item {c['listing_id']} breaks the same-employer/title/location/new-ID rule")
            break
        gap = 0 if not o["closed_on"] or o["closed_on"] >= newer["first_seen"] else days(o["closed_on"], newer["first_seen"])
        if c["gap_days"] != gap or gap > R["REPOST_WINDOW_DAYS"] or o["first_seen"] >= newer["first_seen"]:
            err(w, f"chain item {c['listing_id']}: gap_days/timing violates REPOST_WINDOW_DAYS rule")
        if any(c[k] != o[k] for k in ("title", "first_seen", "last_seen", "days_seen", "status", "closed_on")):
            err(w, f"chain item {c['listing_id']} differs from its listing file")
        if lid not in [x["listing_id"] for x in o["later_reposts"]]:
            err(w, f"{c['listing_id']} must list {lid} in later_reposts")
        newer = o
    for x in l["later_reposts"]:
        if lid not in [c["listing_id"] for c in lst.get(x["listing_id"], {}).get("chain", [])]:
            err(w, f"later_reposts {x['listing_id']} does not have this listing in its chain")
    for cid in l["correction_ids"]:
        if cid not in upheld_fix or upheld_fix[cid]["listing_id"] != lid or l[upheld_fix[cid]["field"]] != upheld_fix[cid]["value"]:
            err(w, f"correction {cid} not upheld for this listing or its value not applied")
    for s in l["more_at_employer"]:
        if s["listing_id"] == lid or s["status"] != "open" or s["employer_slug"] != e["slug"]:
            err(w, "more_at_employer must be other open listings at the same employer")

# search index = open listings of active employers, nothing else
si = docs["data/search-index.json"]
open_ids = {lid for lid, l in lst.items() if l["status"] == "open" and emps[l["employer_id"]]["active"]}
row_ids = [r[0] for r in si["rows"]]
if set(row_ids) != open_ids or len(row_ids) != len(open_ids):
    err("data/search-index.json", "rows must be exactly the open listings of active employers")
for r in si["rows"]:
    l = lst.get(r[0])
    if l and [si["employers"][r[1]][0], r[2], r[3], r[4], r[5], r[6], bool(r[7]), bool(r[8]), r[9]] != \
            [l["employer_slug"], l["title"], l["location"], l["first_seen"], l["days_seen"], l["age_state"],
             l["open_before_tracking"], l["reposted"], l["repost_count"]]:
        err("data/search-index.json", f"row {r[0]} differs from its listing file")
size = os.path.getsize(os.path.join(ROOT, "data/search-index.json"))
if size > 100 * 1024:
    err("data/search-index.json", f"{size} bytes > 100 KB first-load budget")

# site counts
opn = [l for l in lst.values() if l["status"] == "open"]
c = site["counts"]
exp = {"open_listings": len(opn), "fresh": sum(l["age_state"] == "fresh" for l in opn),
       "seen": sum(l["age_state"] == "seen" for l in opn), "long_open": sum(l["age_state"] == "long_open" for l in opn),
       "reposted_open": sum(l["reposted"] for l in opn), "open_before_tracking_open": sum(l["open_before_tracking"] for l in opn),
       "closed_listings": len(lst) - len(opn), "listings_total": len(lst),
       "employers_tracked": sum(e["active"] for e in reg.values()),
       "employers_with_data": sum(1 for e in emps.values() if e["active"] and e["tracked_since"])}
for k, v in exp.items():
    if c[k] != v:
        err("data/site.json", f"counts.{k} should be {v}")
ts = [e["tracked_since"] for e in emps.values() if e["tracked_since"]]
if site["tracking_started_on"] != (min(ts) if ts else None):
    err("data/site.json", "tracking_started_on must be the earliest tracked_since")
if site["last_successful_run_at"]:
    last_ok = dt.datetime.fromisoformat(site["last_successful_run_at"])
    if site["stale"]["stale_after"] != (last_ok + dt.timedelta(hours=R["STALE_BUILD_HOURS"])).isoformat():
        err("data/site.json", "stale.stale_after != last_successful_run_at + STALE_BUILD_HOURS")
    built = dt.datetime.fromisoformat(site["build_time"])
    if site["stale"]["stale_at_build"] != (built > last_ok + dt.timedelta(hours=R["STALE_BUILD_HOURS"])):
        err("data/site.json", "stale.stale_at_build wrong")

# overview: only eligible employers, neutral (no rank field is allowed by the schema)
ov = docs["data/overview.json"]
for row in ov["employers"]:
    e = emps.get(row["slug"])
    if not e or not e["overview"]["eligible"] or row["open_count"] < R["OVERVIEW_MIN_OPEN_LISTINGS"] \
            or e["tracked_days"] < R["OVERVIEW_MIN_TRACKED_DAYS"]:
        err("data/overview.json", f"{row['slug']} does not meet the OVERVIEW_MIN_* thresholds")
listed = {r["slug"] for r in ov["employers"]} | {r["slug"] for r in ov["not_yet_eligible"]}
if listed != {s for s, e in emps.items() if e["active"]}:
    err("data/overview.json", "employers + not_yet_eligible must cover every active employer exactly")
text = json.dumps(ov).lower()
for word in ("ghost", "fake", "worst", "rank", "top "):
    if word in text:
        err("data/overview.json", f"non-neutral wording '{word}'")

# corrections log refers to upheld corrections only
cids = {c["id"]: c for c in corr}
for ent in docs["data/corrections-log.json"]["entries"]:
    cc = cids.get(ent["correction_id"])
    if not cc or cc["status"] != "upheld" or cc["employer_id"] != ent["employer_slug"]:
        err("data/corrections-log.json", f"{ent['correction_id']} is not an upheld correction for {ent['employer_slug']}")

# hidden listings appear nowhere in the published data
blob = json.dumps({k: v for k, v in docs.items() if k.startswith("data/")})
for h in hidden:
    if h in blob:
        err("data/", f"hidden listing {h} is referenced in published output")

if errors:
    print("\n".join("FAIL " + e for e in errors))
    print(f"FAILED: {len(errors)} problem(s)")
    sys.exit(1)
print(f"consistency: {len(lst)} listings, {len(emps)} employers, search index {size} bytes: all checks passed")
print("OK")
