import json

import pytest

from tools.bootstrap import BootstrapError, ensure_catalog
from tools.lib.dbcli import CliError
from tools.lib.manifest import Manifest

URL = "s3://ws-bucket/"
CREATED = {"name": "dev_gold", "owner": "operator@example.com", "storage_location": "s3://ws-bucket/dev_gold/__unitystorage/catalogs/abc",
           "created_at": 1, "created_by": "operator@example.com", "isolation_mode": "OPEN"}


def handlers(state):
    def get_catalog(args):
        if args[2] == "default_cat":
            return {"storage_root": URL}
        if state.get("catalog") is None:
            raise CliError(args, 1, "Error: Catalog 'dev_gold' does not exist.")
        return state["catalog"]

    def create(args):
        state["catalog"] = dict(CREATED, storage_root=args[args.index("--storage-root") + 1])
        return state["catalog"]

    def update(args):
        # Live behaviour: making a catalog ISOLATED binds it to the calling workspace.
        state["catalog"]["isolation_mode"] = "ISOLATED"
        if state.get("auto_bind", True):
            state["bindings"] = [{"binding_type": "BINDING_TYPE_READ_WRITE", "workspace_id": 42}]
        return state["catalog"]

    def bind(args):
        state["bindings"] = json.loads(args[args.index("--json") + 1])["add"]
        return list(state["bindings"])

    return {
        ("metastores", "current"): {"workspace_id": 42, "default_catalog_name": "default_cat"},
        ("catalogs", "get"): get_catalog,
        ("external-locations", "list"): [{"name": "other", "url": "s3://other/"}, {"name": "ws-loc", "url": URL}],
        ("grants", "get-effective"): {"privilege_assignments": [{"privileges": [{"privilege": state.get("priv", "ALL_PRIVILEGES")}]}]},
        ("catalogs", "create"): create,
        ("catalogs", "update"): update,
        ("workspace-bindings", "get-bindings"): lambda args: list(state.get("bindings", [])),   # the CLI returns a list
        ("workspace-bindings", "update-bindings"): bind,
    }


def test_creates_records_and_binds_a_new_catalog(tmp_path, fake_cli):
    state = {}
    cli = fake_cli(handlers(state))
    manifest = Manifest.load(tmp_path / "m.json")
    record = ensure_catalog(cli, manifest, "dev_gold", "operator@example.com")
    assert record["storage_root"] == "s3://ws-bucket/dev_gold" and record["external_location"] == "ws-loc"
    assert record["bound_workspace_ids"] == [42] and state["catalog"]["isolation_mode"] == "ISOLATED"
    assert json.loads((tmp_path / "m.json").read_text())["catalog"]["fingerprint"]["storage_location"].endswith("abc")
    second = ensure_catalog(cli, Manifest.load(tmp_path / "m.json"), "dev_gold", "operator@example.com")
    assert second["fingerprint"] == record["fingerprint"]
    assert sum(1 for kind, args in cli.calls if args[:2] == ("catalogs", "create")) == 1


def test_refuses_an_existing_catalog_it_did_not_create(tmp_path, fake_cli):
    cli = fake_cli(handlers({"catalog": dict(CREATED)}))
    with pytest.raises(BootstrapError, match="not recorded"):
        ensure_catalog(cli, Manifest.load(tmp_path / "m.json"), "dev_gold", "operator@example.com")


def test_refuses_a_recreated_catalog(tmp_path, fake_cli):
    state = {}
    cli = fake_cli(handlers(state))
    ensure_catalog(cli, Manifest.load(tmp_path / "m.json"), "dev_gold", "operator@example.com")
    state["catalog"]["created_at"] = 2
    with pytest.raises(BootstrapError, match="no longer matches"):
        ensure_catalog(cli, Manifest.load(tmp_path / "m.json"), "dev_gold", "operator@example.com")


def test_requires_managed_storage_rights(tmp_path, fake_cli):
    cli = fake_cli(handlers({"priv": "READ_FILES"}))
    with pytest.raises(BootstrapError, match="CREATE MANAGED STORAGE"):
        ensure_catalog(cli, Manifest.load(tmp_path / "m.json"), "dev_gold", "operator@example.com")


def test_binding_is_added_only_when_isolation_did_not_bind_this_workspace(tmp_path, fake_cli):
    state = {"auto_bind": False}
    cli = fake_cli(handlers(state))
    record = ensure_catalog(cli, Manifest.load(tmp_path / "m.json"), "dev_gold", "operator@example.com")
    assert record["bound_workspace_ids"] == [42] and state["bindings"][0]["workspace_id"] == 42
    assert any(args[:2] == ("workspace-bindings", "update-bindings") for kind, args in cli.calls)
    auto = fake_cli(handlers({}))
    ensure_catalog(auto, Manifest.load(tmp_path / "auto.json"), "dev_gold", "operator@example.com")
    assert not any(args[:2] == ("workspace-bindings", "update-bindings") for kind, args in auto.calls)
