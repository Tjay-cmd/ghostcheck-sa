import datetime as dt
import json
import os

from ghostcheck_pipeline import build as B
from ghostcheck_pipeline.ids import Register
from tests.conftest import write_json, SAST


def _day(n):
    return (dt.date(2026, 1, 1) + dt.timedelta(days=n)).isoformat()


def _run_at(n):
    return dt.datetime.combine(dt.date(2026, 1, 1) + dt.timedelta(days=n), dt.time(6, 0), SAST).isoformat()


def _seed_runlog(root, days):
    runs = [{
        "date": _day(d), "time": "06:00:00", "run_at": _run_at(d), "runner": "test",
        "employer_id": "acme", "ats_type": "workday", "status": "ok", "count": 6, "complete": True,
        "http_status": 200, "pages": 1, "elapsed_s": 1.0, "note": "",
    } for d in days]
    write_json(os.path.join(root, "history", "runlog.json"), runs)


def _load(root, *parts):
    with open(os.path.join(root, *parts), encoding="utf-8") as f:
        return json.load(f)


def test_closure_and_repost_chain(repo):
    root = repo
    # 41 consecutive successful daily runs, day 0..40. data_date = day 40.
    _seed_runlog(root, range(41))

    write_json(os.path.join(root, "history", "listings", "acme.json"), {
        "employer_id": "acme",
        "listings": [
            # R-1 seen day0-2, then never again -> closed on day4 (2nd missed ok run after day2: day3, day4).
            {"ats_job_id": "R-1", "title": "Data Analyst", "location": "Sandton",
             "url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers/job/Data-Analyst_R-1",
             "first_seen": _day(0), "last_seen": _day(2)},
            # R-2: same title+location, posted 6 days after R-1 closed -> repost of R-1.
            {"ats_job_id": "R-2", "title": "Data Analyst", "location": "Sandton",
             "url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers/job/Data-Analyst_R-2",
             "first_seen": _day(10), "last_seen": _day(40)},
            # Filler listings so total_listings_seen/tracked_days clear the metrics + overview gates.
            {"ats_job_id": "R-3", "title": "Warehouse Clerk", "location": "Durban",
             "url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers/job/Warehouse-Clerk_R-3",
             "first_seen": _day(0), "last_seen": _day(40)},
            {"ats_job_id": "R-4", "title": "Payroll Officer", "location": "Cape Town",
             "url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers/job/Payroll-Officer_R-4",
             "first_seen": _day(0), "last_seen": _day(40)},
            {"ats_job_id": "R-5", "title": "Store Manager", "location": None,
             "url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers/job/Store-Manager_R-5",
             "first_seen": _day(0), "last_seen": _day(40)},
            {"ats_job_id": "R-6", "title": "Security Guard", "location": "Pretoria",
             "url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers/job/Security-Guard_R-6",
             "first_seen": _day(0), "last_seen": _day(40)},
        ],
    })

    B.build(root, now=dt.datetime.combine(dt.date(2026, 1, 1) + dt.timedelta(days=40), dt.time(6, 30), SAST))

    reg = Register(os.path.join(root, "history", "listing_id_register.json"))
    lid_r1 = reg.listing_id("acme", "R-1")
    lid_r2 = reg.listing_id("acme", "R-2")

    l1 = _load(root, "data", "listings", f"{lid_r1}.json")
    l2 = _load(root, "data", "listings", f"{lid_r2}.json")

    assert l1["status"] == "closed"
    assert l1["closed_on"] == _day(4)
    assert l1["later_reposts"] == [{"listing_id": lid_r2, "first_seen": _day(10), "status": "open"}]

    assert l2["status"] == "open"
    assert l2["repost_of"] == {"listing_id": lid_r1, "match_basis": "same_title_location", "gap_days": 6}
    assert l2["reposted"] is True
    assert l2["repost_count"] == 1
    assert l2["chain_first_seen"] == _day(0)
    assert l2["chain"][0]["listing_id"] == lid_r1
    assert l2["chain"][0]["gap_days"] == 6

    emp = _load(root, "data", "employers", "acme.json")
    assert emp["tracked_since"] == _day(0)
    assert emp["tracked_days"] == 40
    assert emp["total_listings_seen"] == 6
    assert emp["metrics"]["open_count"]["value"] == 5  # R-1 closed, 5 others open
    assert emp["metrics"]["median_days_seen"]["available"] is True  # gate: 40>=30 days, 6>=5 listings
    assert emp["overview"]["eligible"] is False  # tracked_days 40 < OVERVIEW_MIN_TRACKED_DAYS 91
    assert emp["overview"]["reason"] == "tracked_days"


def test_fix_and_hide_corrections(repo):
    root = repo
    _seed_runlog(root, range(2))
    write_json(os.path.join(root, "history", "listings", "acme.json"), {
        "employer_id": "acme",
        "listings": [
            {"ats_job_id": "FIX-1", "title": "Branch Consultant", "location": "JHB-014",
             "url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers/job/Branch-Consultant_FIX-1",
             "first_seen": _day(0), "last_seen": _day(1)},
            {"ats_job_id": "HIDE-1", "title": "Assistant to Jane Smith", "location": "Sandton",
             "url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers/job/x_HIDE-1",
             "first_seen": _day(0), "last_seen": _day(1)},
        ],
    })
    reg = Register(os.path.join(root, "history", "listing_id_register.json"))
    lid_fix = reg.listing_id("acme", "FIX-1")
    lid_hide = reg.listing_id("acme", "HIDE-1")
    reg.save()

    write_json(os.path.join(root, "config", "corrections.json"), {"corrections": [
        {"id": "corr-2026-0001", "received_on": _day(1), "type": "fix_listing_field", "status": "upheld",
         "employer_id": "acme", "listing_id": lid_fix, "field": "location", "value": "Johannesburg",
         "hides_listing": False, "resolved_on": _day(1),
         "public_summary": "Corrected the location of one Acme listing.", "note": "internal branch code"},
        {"id": "corr-2026-0002", "received_on": _day(1), "type": "hide_listing", "reason": "personal_data_claim",
         "status": "pending_review", "employer_id": "acme", "listing_id": lid_hide, "hides_listing": True,
         "resolved_on": None, "public_summary": None, "note": "title contains a staff member's name"},
    ]})

    B.build(root, now=dt.datetime.combine(dt.date(2026, 1, 1) + dt.timedelta(days=1), dt.time(6, 30), SAST))

    l_fix = _load(root, "data", "listings", f"{lid_fix}.json")
    assert l_fix["location"] == "Johannesburg"
    assert l_fix["normalised_location"] == "johannesburg"
    assert l_fix["correction_ids"] == ["corr-2026-0001"]

    assert not os.path.exists(os.path.join(root, "data", "listings", f"{lid_hide}.json"))
    blob = json.dumps(_load(root, "data", "employers", "acme.json"))
    assert lid_hide not in blob
    log_text = json.dumps(_load(root, "data", "corrections-log.json"))
    assert lid_hide not in log_text

    log = _load(root, "data", "corrections-log.json")
    assert log["entries"] == [{
        "date": _day(1), "employer": "Acme Corp", "employer_slug": "acme",
        "correction_id": "corr-2026-0001", "summary": "Corrected the location of one Acme listing.",
    }]


def test_no_data_employer_has_empty_output(repo):
    root = repo
    B.build(root, now=dt.datetime(2026, 1, 2, 6, 30, tzinfo=SAST))
    emp = _load(root, "data", "employers", "acme.json")
    assert emp["has_data"] is False
    assert emp["tracked_since"] is None
    assert emp["check_status"] == "no_data"
    assert emp["listings"]["open"] == []
    assert emp["metrics"]["open_count"]["available"] is False
    assert emp["metrics"]["open_count"]["unavailable_reason"] == "no_data"
    site = _load(root, "data", "site.json")
    assert site["counts"]["open_listings"] == 0
