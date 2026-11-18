import json

import pytest

from tools.lib.manifest import Manifest, ManifestError


def test_missing_manifest_starts_empty(tmp_path):
    m = Manifest.load(tmp_path / "manifest.json")
    assert m.data == {"version": 1, "runs": []}


def test_save_round_trips_atomically(tmp_path):
    path = tmp_path / ".state" / "manifest.json"
    m = Manifest.load(path)
    m.bind("demo", "esa-resstay-demo", "https://h")
    m.record_run(job="setup", status="SUCCESS")
    m.save()
    loaded = json.loads(path.read_text())
    assert loaded["target"] == "demo" and loaded["runs"][0]["job"] == "setup"
    assert [p.name for p in path.parent.iterdir()] == ["manifest.json"]


def test_a_manifest_belongs_to_one_deployment(tmp_path):
    m = Manifest.load(tmp_path / "m.json")
    m.bind("demo", "esa-resstay-demo", "https://h")
    with pytest.raises(ManifestError, match="records host"):
        m.bind("demo", "esa-resstay-demo", "https://other")
