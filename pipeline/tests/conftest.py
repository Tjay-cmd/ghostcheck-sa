import datetime as dt
import json
import os

import pytest

SAST = dt.timezone(dt.timedelta(hours=2))


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


@pytest.fixture
def repo(tmp_path):
    """A minimal repo layout the pipeline can build from."""
    root = str(tmp_path)

    write_json(os.path.join(root, "config", "rules.json"), {
        "FRESH_MAX_DAYS": 13, "LONG_OPEN_MIN_DAYS": 91, "CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS": 2,
        "REPOST_WINDOW_DAYS": 60, "REPOST_RATE_WINDOW_DAYS": 180, "EMPLOYER_METRICS_MIN_TRACKED_DAYS": 30,
        "EMPLOYER_METRICS_MIN_LISTINGS_SEEN": 5, "OVERVIEW_MIN_TRACKED_DAYS": 91, "OVERVIEW_MIN_OPEN_LISTINGS": 5,
        "STALE_BUILD_HOURS": 36, "FAILED_STREAK_WARNING_RUNS": 7, "RECENTLY_CLOSED_WINDOW_DAYS": 90,
    })
    write_json(os.path.join(root, "config", "site.json"), {
        "CORRECTIONS_EMAIL": "[CORRECTIONS_EMAIL_TBD]", "FEATURE_OVERVIEW": False,
        "SITE_PHASE": "soft", "POPIA_REVIEWED": False,
    })
    write_json(os.path.join(root, "config", "employers.json"), {
        "defaults": {"delay_seconds": 1.5, "max_pages": 40, "timeout_seconds": 30},
        "employers": [{
            "id": "acme", "slug": "acme", "name": "Acme Corp", "sector": "Other", "ats_type": "workday",
            "tenant": "acme", "host": "acme.wd3.myworkdayjobs.com", "site": "AcmeCareers",
            "source_url": "https://acme.wd3.myworkdayjobs.com/AcmeCareers",
            "active": True, "added_on": "2026-01-01",
        }],
    })
    write_json(os.path.join(root, "config", "corrections.json"), {"corrections": []})
    write_json(os.path.join(root, "history", "runlog.json"), [])
    write_json(os.path.join(root, "history", "listings", "acme.json"), {"employer_id": "acme", "listings": []})
    return root
