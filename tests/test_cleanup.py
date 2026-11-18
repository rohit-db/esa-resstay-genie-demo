import pytest

from tools.cleanup import CleanupError, plan_cleanup, run_cleanup
from tools.lib.manifest import Manifest

FP = {"storage_location": "s3://b/dev_gold/x", "created_at": 1}


def manifest(tmp_path):
    m = Manifest.load(tmp_path / "m.json")
    m.data.update(bundle={"warehouse_id": "w"}, catalog={"name": "dev_gold", "fingerprint": FP}, ontology={
        "pages": {"resstay--adr": {"name": "pages/p1"}},
        "domains": {"revenue": {"domain_id": "d1", "name": "domains/d1", "tag_key": "ESA Revenue Management"},
                    "resstay": {"domain_id": "d2", "name": "domains/d2", "tag_key": "ESA Revenue Management/ResStay"}},
        "tag_policies": {"ESA Revenue Management": {"id": "1"}, "ESA Revenue Management/ResStay": {"id": "2"}}})
    return m


def handlers(over=None):
    base = {
        ("domains", "list-domains"): [{"domain_id": "d1", "tag_key": "ESA Revenue Management", "name": "domains/d1"},
                                      {"domain_id": "d2", "tag_key": "ESA Revenue Management/ResStay", "name": "domains/d2"}],
        ("tag-policies", "list-tag-policies"): [{"id": "1", "tag_key": "ESA Revenue Management"},
                                                {"id": "2", "tag_key": "ESA Revenue Management/ResStay"}],
        ("catalogs", "get"): {"name": "dev_gold", **FP},
    }
    base.update(over or {})
    return base


def test_dry_run_plans_children_first_and_deletes_nothing(tmp_path, fake_cli):
    cli = fake_cli(handlers())
    steps = plan_cleanup(cli, manifest(tmp_path), "demo")
    assert [s[0] for s in steps] == ["Page resstay--adr", "Domain ESA Revenue Management/ResStay",
                                     "Domain ESA Revenue Management", "Governed tag ESA Revenue Management/ResStay",
                                     "Governed tag ESA Revenue Management", "Bundle resources (target demo)",
                                     "Catalog dev_gold (cascade)"]
    assert not any("delete" in " ".join(args) or "destroy" in args for _, args in cli.calls)


def test_refuses_objects_that_no_longer_match_their_records(tmp_path, fake_cli):
    moved = handlers({("domains", "list-domains"): [{"domain_id": "d1", "tag_key": "ESA Someone Else", "name": "domains/d1"}]})
    with pytest.raises(CleanupError, match="refusing"):
        plan_cleanup(fake_cli(moved), manifest(tmp_path), "demo")
    other = handlers({("catalogs", "get"): {"name": "dev_gold", "storage_location": "s3://other", "created_at": 1}})
    with pytest.raises(CleanupError, match="fingerprint"):
        plan_cleanup(fake_cli(other), manifest(tmp_path), "demo")


def test_confirmed_cleanup_runs_the_plan_and_clears_the_records(tmp_path, fake_cli):
    cli = fake_cli({**handlers(), ("delete",): {}, ("domains", "delete-domain"): "", ("tag-policies", "delete-tag-policy"): "",
                    ("bundle", "destroy"): "", ("catalogs", "delete"): ""})
    m = manifest(tmp_path)
    run_cleanup(cli, m, plan_cleanup(cli, m, "demo"))
    saved = Manifest.load(tmp_path / "m.json").data
    assert "bundle" not in saved and "catalog" not in saved and saved["ontology"] == {}
    assert ("run", ("catalogs", "delete", "dev_gold", "--force")) in cli.calls
