import json
import os

from ghostcheck_pipeline.ids import Register


def test_stable_across_instances(tmp_path):
    path = os.path.join(tmp_path, "register.json")
    r1 = Register(path)
    lid = r1.listing_id("absa", "R-123")
    r1.save()

    r2 = Register(path)
    assert r2.listing_id("absa", "R-123") == lid


def test_format(tmp_path):
    r = Register(os.path.join(tmp_path, "register.json"))
    lid = r.listing_id("absa", "R-123")
    assert len(lid) == 10
    assert all(c in "0123456789abcdefghjkmnpqrstvwxyz" for c in lid)


def test_different_keys_different_ids(tmp_path):
    r = Register(os.path.join(tmp_path, "register.json"))
    assert r.listing_id("absa", "R-1") != r.listing_id("absa", "R-2")
    assert r.listing_id("absa", "R-1") != r.listing_id("discovery", "R-1")


def test_hidden_ids_stay_reserved_forever(tmp_path):
    path = os.path.join(tmp_path, "register.json")
    r1 = Register(path)
    lid = r1.listing_id("absa", "R-123")
    r1.save()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["issued"][lid] == "absa:R-123"
