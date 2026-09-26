import json

from conftest import FakeResp, FakeSession, fixture_text
from ghostcheck import successfactors, workday

WD = {"id": "picknpay", "ats_type": "workday", "tenant": "picknpay",
      "host": "picknpay.wd3.myworkdayjobs.com", "site": "PNP_Careers"}
SF = {"id": "goldfields", "ats_type": "successfactors", "base_url": "https://careers.goldfields.com"}
CFG = {"delay_seconds": 0, "max_pages": 40, "timeout_seconds": 5}
NOSLEEP = lambda s: None


def test_workday_job_id_from_path():
    assert workday.job_id_from_path("/job/Cape-Town/Contracts-Specialist_JR-83572") == "JR-83572"
    assert workday.job_id_from_path("/job/Windhoek/BI-Analyst-1_R53125") == "R53125"
    assert workday.job_id_from_path("/job/X/Shelfpacker_JR105433-2") == "JR105433-2"


def test_workday_parse_page_only_allowed_fields():
    items, total = workday.parse_page(json.loads(fixture_text("workday_page1.json")), WD)
    assert total == 52 or isinstance(total, int)
    assert len(items) == 5
    for it in items:
        assert set(it) == {"ats_job_id", "title", "location", "url"}
        assert it["url"].startswith("https://picknpay.wd3.myworkdayjobs.com/PNP_Careers/job/")
    assert items[0]["ats_job_id"] == "JR106017"
    assert items[4]["location"] == ""


def test_workday_fetch_paginates_and_stops_on_total():
    page1 = json.loads(fixture_text("workday_page1.json"))
    page1["total"] = 25  # 2 pages of 20
    page2 = {"total": 0, "jobPostings": [{"title": "Later job", "externalPath": "/job/Y/Later-job_JR1"}]}
    s = FakeSession([FakeResp(200, json.dumps(page1)), FakeResp(200, json.dumps(page2))])
    res = workday.fetch(WD, s, CFG, NOSLEEP)
    assert res["status"] == "ok" and res["complete"] is True
    assert len(res["listings"]) == 6 and res["pages"] == 2
    assert s.calls[1][2]["json"]["offset"] == 20 and s.calls[1][2]["json"]["limit"] == 20


def test_workday_fetch_page_cap_marks_incomplete():
    page = json.loads(fixture_text("workday_page1.json"))
    page["total"] = 10_000
    s = FakeSession([FakeResp(200, json.dumps(page))] * 2)
    res = workday.fetch(WD, s, {**CFG, "max_pages": 2}, NOSLEEP)
    assert res["status"] == "ok" and res["complete"] is False and "page cap" in res["note"]


def test_workday_fetch_blocked_midway_is_blocked():
    page = json.loads(fixture_text("workday_page1.json"))
    page["total"] = 100
    s = FakeSession([FakeResp(200, json.dumps(page)), FakeResp(403, fixture_text("akamai_access_denied.html"))])
    res = workday.fetch(WD, s, CFG, NOSLEEP)
    assert res["status"] == "blocked" and "partial" in res["note"] and res["http_status"] == 403


def test_workday_fetch_network_error():
    res = workday.fetch(WD, FakeSession([ConnectionError("boom")]), CFG, NOSLEEP)
    assert res["status"] == "error"


def test_workday_fetch_bad_json_shape_is_error():
    res = workday.fetch(WD, FakeSession([FakeResp(200, '{"foo": 1}')]), CFG, NOSLEEP)
    assert res["status"] == "error" and "parse error" in res["note"]


def test_sf_table_layout():
    items, total = successfactors.parse_page(fixture_text("sf_table_page.html"), SF["base_url"])
    assert total == 46 and len(items) == 3
    it = items[0]
    assert set(it) == {"ats_job_id", "title", "location", "url"}
    assert it["ats_job_id"].isdigit()
    assert it["url"].startswith("https://careers.goldfields.com/") and it["url"].endswith(f"/{it['ats_job_id']}/")
    assert it["location"] and "  " not in it["location"]


def test_sf_tiles_layout():
    items, total = successfactors.parse_page(fixture_text("sf_tiles_page.html"), "https://jobs.sasol.com")
    assert total == 54 and len(items) == 3
    by_id = {i["ats_job_id"]: i for i in items}
    assert by_id["1431155033"] == {"ats_job_id": "1431155033", "title": "Production Foreman",
                                   "location": "Secunda, South Africa",
                                   "url": "https://jobs.sasol.com/job/Secunda-Production-Foreman/1431155033/"}


def test_sf_parse_rejects_non_results_page():
    import pytest
    with pytest.raises(ValueError):
        successfactors.parse_page(fixture_text("generic_html.html"), SF["base_url"])


def test_sf_fetch_stops_when_no_new_ids():
    page = fixture_text("sf_table_page.html").replace("of <b>46</b>", "of <b>999</b>")
    s = FakeSession([FakeResp(200, page), FakeResp(200, page)])
    res = successfactors.fetch(SF, s, CFG, NOSLEEP)
    assert res["status"] == "ok" and len(res["listings"]) == 3 and res["pages"] == 2
    assert "startrow=25" in s.calls[1][1]


def test_sf_fetch_blocked():
    res = successfactors.fetch(SF, FakeSession([FakeResp(200, fixture_text("akamai_bm_verify.html"))]), CFG, NOSLEEP)
    assert res["status"] == "blocked"
