import json
import os
from datetime import datetime

from conftest import FakeResp, FakeSession, fixture_text
from ghostcheck import run as runmod
from ghostcheck import store
from ghostcheck.run import SAST

ALLOWED = {"ats_job_id", "title", "location", "url", "first_seen", "last_seen"}


def sf_one_page(name="sf_table_page.html"):
    t = fixture_text(name)
    return t.replace("of <b>46</b>", "of <b>3</b>").replace("of 54 Jobs", "of 3 Jobs")


def wd_one_page():
    d = json.loads(fixture_text("workday_page1.json"))
    d["total"] = len(d["jobPostings"])
    return json.dumps(d)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def test_sanitize_whitelist_and_normalisation():
    out = store.sanitize({"ats_job_id": " JR1 ", "title": "  Senior\n\tAnalyst  ", "location": "  ",
                          "url": "https://x/1", "first_seen": "2026-09-26", "last_seen": "2026-09-26",
                          "description": "LONG TEXT", "recruiter": "Jane Doe", "email": "a@b.c"})
    assert set(out) == ALLOWED
    assert out["title"] == "Senior Analyst" and out["location"] is None and out["ats_job_id"] == "JR1"


def test_upsert_first_seen_kept_last_seen_advances(tmp_path):
    d = str(tmp_path)
    store.upsert_listings(d, "e", [{"ats_job_id": "1", "title": "A", "location": "Jhb", "url": "u1"},
                                   {"ats_job_id": "2", "title": "B", "location": "", "url": "u2"}], "2026-09-26")
    c = store.upsert_listings(d, "e", [{"ats_job_id": "1", "title": "A  (edited)", "location": "Jhb", "url": "u1"},
                                       {"ats_job_id": "3", "title": "C", "location": "Cpt", "url": "u3"}], "2026-09-27")
    assert c == {"new": 1, "seen": 2, "stored": 3}
    rows = {r["ats_job_id"]: r for r in load(os.path.join(d, "listings", "e.json"))["listings"]}
    assert rows["1"]["first_seen"] == "2026-09-26" and rows["1"]["last_seen"] == "2026-09-27"
    assert rows["1"]["title"] == "A (edited)"
    assert rows["2"]["last_seen"] == "2026-09-26" and rows["2"]["location"] is None  # missing: untouched
    assert rows["3"]["first_seen"] == "2026-09-27"
    for r in rows.values():
        assert set(r) == ALLOWED


def _config(tmp_path):
    cfg = {"defaults": {"delay_seconds": 0, "max_pages": 5, "timeout_seconds": 5},
           "employers": [
               {"id": "wd1", "ats_type": "workday", "tenant": "t", "host": "t.wd3.myworkdayjobs.com", "site": "S"},
               {"id": "sf1", "ats_type": "successfactors", "base_url": "https://jobs.example.co.za"},
               {"id": "wd2", "ats_type": "workday", "tenant": "u", "host": "u.wd3.myworkdayjobs.com", "site": "S"}]}
    p = tmp_path / "employers.json"
    p.write_text(json.dumps(cfg))
    return str(p)


def test_run_blocked_and_error_never_touch_listings(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    cfgp, d = _config(tmp_path), str(tmp_path / "data")
    wd_ok = FakeResp(200, wd_one_page())
    sf_ok = FakeResp(200, sf_one_page())
    day1 = datetime(2026, 9, 26, 6, 17, 3, tzinfo=SAST)
    runmod.run(cfgp, d, sleep=lambda s: None, now=day1,
               session=FakeSession([wd_ok, sf_ok, FakeResp(422, '{"errorCode":"HTTP_422"}')]))
    wd1_before = (tmp_path / "data/listings/wd1.json").read_text()
    sf1_before = (tmp_path / "data/listings/sf1.json").read_text()
    # every employer has a listings file, even the one that failed
    assert load(tmp_path / "data/listings/wd2.json") == {"employer_id": "wd2", "listings": []}

    day2 = datetime(2026, 9, 27, 6, 17, 9, tzinfo=SAST)
    runmod.run(cfgp, d, sleep=lambda s: None, now=day2,
               session=FakeSession([FakeResp(403, fixture_text("akamai_access_denied.html")),
                                    ConnectionError("x"),
                                    FakeResp(200, fixture_text("akamai_bm_verify.html"))]))
    assert (tmp_path / "data/listings/wd1.json").read_text() == wd1_before
    assert (tmp_path / "data/listings/sf1.json").read_text() == sf1_before

    log = load(tmp_path / "data/runlog.json")
    assert [(e["date"], e["employer_id"], e["status"], e["count"]) for e in log] == [
        ("2026-09-26", "wd1", "ok", 5), ("2026-09-26", "sf1", "ok", 3), ("2026-09-26", "wd2", "error", 0),
        ("2026-09-27", "wd1", "blocked", 0), ("2026-09-27", "sf1", "error", 0), ("2026-09-27", "wd2", "blocked", 0)]
    assert log[0]["time"] == "06:17:03" and log[0]["run_at"] == "2026-09-26T06:17:03+02:00"
    assert log[0]["complete"] is True and log[3]["complete"] is None
    assert all(e["runner"] == "local" for e in log)


def test_listing_files_contain_only_allowed_fields(tmp_path):
    cfgp, d = _config(tmp_path), str(tmp_path / "data")
    runmod.run(cfgp, d, sleep=lambda s: None, now=datetime(2026, 9, 26, 6, 0, tzinfo=SAST),
               session=FakeSession([FakeResp(200, wd_one_page()),
                                    FakeResp(200, sf_one_page("sf_tiles_page.html")),
                                    FakeResp(200, wd_one_page())]))
    for name in os.listdir(tmp_path / "data/listings"):
        doc = load(tmp_path / "data/listings" / name)
        assert set(doc) == {"employer_id", "listings"}
        for r in doc["listings"]:
            assert set(r) == ALLOWED
            assert r["first_seen"] == r["last_seen"] == "2026-09-26"
            assert r["title"] == " ".join(r["title"].split())


def test_unhandled_fetcher_exception_is_logged_not_raised(tmp_path, monkeypatch):
    cfgp, d = _config(tmp_path), str(tmp_path / "data")
    def boom(*a, **k):
        raise RuntimeError("bug")
    monkeypatch.setitem(runmod.FETCHERS, "workday", boom)
    runmod.run(cfgp, d, sleep=lambda s: None, now=datetime(2026, 9, 26, 6, 0, tzinfo=SAST),
               session=FakeSession([FakeResp(200, sf_one_page())]))
    log = load(tmp_path / "data/runlog.json")
    assert [e["status"] for e in log] == ["error", "ok", "error"]
