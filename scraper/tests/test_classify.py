import pytest

from conftest import fixture_text
from ghostcheck.classify import BLOCKED, ERROR, OK, challenge_marker, classify_http


@pytest.mark.parametrize("status", [403, 429, 401])
def test_block_status_codes(status):
    assert classify_http(status, "", "json")[0] == BLOCKED


def test_akamai_access_denied_403():
    st, note = classify_http(403, fixture_text("akamai_access_denied.html"), "json")
    assert st == BLOCKED and "challenge marker" in note


def test_akamai_access_denied_even_with_200():
    st, _ = classify_http(200, fixture_text("akamai_access_denied.html"), "json")
    assert st == BLOCKED


def test_bm_verify_interstitial_200_html_instead_of_json():
    st, note = classify_http(200, fixture_text("akamai_bm_verify.html"), "json")
    assert st == BLOCKED and "instead of JSON" in note


def test_bm_verify_on_sf_html_page():
    assert classify_http(200, fixture_text("akamai_bm_verify.html"), "html")[0] == BLOCKED


def test_503_with_challenge_is_blocked_plain_503_is_error():
    assert classify_http(503, fixture_text("akamai_bm_verify.html"), "html")[0] == BLOCKED
    assert classify_http(503, "Service Unavailable", "html")[0] == ERROR


def test_workday_404_422_are_errors_not_blocks():
    assert classify_http(404, '{"errorCode":"S21","httpStatus":404}', "json")[0] == ERROR
    assert classify_http(422, '{"errorCode":"HTTP_422"}', "json")[0] == ERROR


def test_valid_json_ok():
    assert classify_http(200, fixture_text("workday_page1.json"), "json") == (OK, "")


def test_non_json_without_challenge_is_error():
    assert classify_http(200, fixture_text("generic_html.html"), "json")[0] == ERROR
    assert classify_http(200, "", "json")[0] == ERROR
    assert classify_http(None, None, "json")[0] == ERROR


def test_real_sf_pages_not_misclassified():
    # RMK pages can contain words like "captcha" in scripts; results markup wins.
    page = fixture_text("sf_tiles_page.html").replace("</body>", "<script>recaptcha</script></body>")
    assert classify_http(200, page, "html")[0] == OK
    assert classify_http(200, fixture_text("sf_table_page.html"), "html")[0] == OK


def test_challenge_marker_none_for_normal_text():
    assert challenge_marker("Graduate Programme 2027 - Johannesburg") is None
