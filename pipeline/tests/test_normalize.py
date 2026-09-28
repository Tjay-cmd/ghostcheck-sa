from ghostcheck_pipeline.normalize import (
    apply_domain,
    fingerprint,
    normalised_location,
    normalised_title,
)


def test_normalised_title_casefold_and_punctuation():
    assert normalised_title("IT Intern!") == "it intern"
    assert normalised_title("  Data   Analyst  ") == "data analyst"


def test_normalised_location_remote_and_empty_are_null():
    assert normalised_location("Remote") is None
    assert normalised_location("REMOTE") is None
    assert normalised_location(None) is None
    assert normalised_location("") is None
    assert normalised_location("Centurion") == "centurion"


def test_fingerprint_shape():
    assert fingerprint("absa", "it intern", "centurion") == "absa|it intern|centurion"
    assert fingerprint("absa", "it intern", None) == "absa|it intern|-"


def test_apply_domain_cctld_second_level():
    assert apply_domain("https://jobs.nedbank.co.za/job/123") == "nedbank.co.za"


def test_apply_domain_plain_tld():
    assert apply_domain("https://absa.wd3.myworkdayjobs.com/ABSAcareersite/job/x") == "myworkdayjobs.com"
