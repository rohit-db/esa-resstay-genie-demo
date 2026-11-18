"""Create the demo catalog in this workspace's own storage and bind it to this workspace only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.dbcli import Cli, CliError, is_missing  # noqa: E402
from tools.lib.manifest import Manifest  # noqa: E402

CATALOG_COMMENT = ("ESA ResStay Genie demo: synthetic replica of ESA dev_gold (no ESA data). "
                   "Created and tracked by esa-resstay-genie-demo/.state/manifest.json.")
STORAGE_PRIVILEGES = {"ALL_PRIVILEGES", "CREATE_MANAGED_STORAGE"}


class BootstrapError(RuntimeError):
    pass


def get_catalog(cli: Cli, name: str) -> dict | None:
    try:
        return cli.json(["catalogs", "get", name])
    except CliError as error:
        if is_missing(error):
            return None
        raise


def fingerprint(info: dict) -> dict:
    """Immutable creation facts; storage_location embeds the catalog's UUID."""
    return {key: info.get(key) for key in ("storage_location", "created_at", "created_by")}


def discover_storage(cli: Cli, user: str) -> tuple[str, str, int]:
    """The external location under this workspace's default catalog, which the operator can use."""
    current = cli.json(["metastores", "current"])
    workspace_id = int(current["workspace_id"])
    default_catalog = current.get("default_catalog_name")
    if not default_catalog:
        raise BootstrapError("this workspace has no default catalog to locate its storage from")
    root = (cli.json(["catalogs", "get", default_catalog]) or {}).get("storage_root") or ""
    locations = cli.json(["external-locations", "list"]) or []
    if isinstance(locations, dict):
        locations = locations.get("external_locations", [])
    matches = [loc for loc in locations if root.startswith(loc.get("url", "\0").rstrip("/"))]
    if not matches:
        raise BootstrapError(f"no external location covers the default catalog's storage root {root!r}")
    location = max(matches, key=lambda loc: len(loc["url"]))
    grants = cli.json(["grants", "get-effective", "external_location", location["name"], "--principal", user]) or {}
    privileges = {p["privilege"] for a in grants.get("privilege_assignments", []) for p in a.get("privileges", [])}
    if not privileges & STORAGE_PRIVILEGES:
        raise BootstrapError(f"{user} lacks CREATE MANAGED STORAGE on external location {location['name']}")
    return location["name"], location["url"].rstrip("/"), workspace_id


def bound_workspace_ids(cli: Cli, name: str) -> set[int]:
    """Workspaces bound to the catalog. The CLI returns a JSON list; an object with `bindings` is accepted too."""
    response = cli.json(["workspace-bindings", "get-bindings", "catalog", name]) or []
    bindings = response.get("bindings", []) if isinstance(response, dict) else response
    return {int(b["workspace_id"]) for b in bindings}


def ensure_binding(cli: Cli, name: str, workspace_id: int) -> None:
    info = cli.json(["catalogs", "get", name])
    if info.get("isolation_mode") != "ISOLATED":
        cli.json(["catalogs", "update", name, "--isolation-mode", "ISOLATED"])
    if workspace_id not in bound_workspace_ids(cli, name):
        body = {"add": [{"workspace_id": workspace_id, "binding_type": "BINDING_TYPE_READ_WRITE"}]}
        cli.json(["workspace-bindings", "update-bindings", "catalog", name, "--json", json.dumps(body)])
    if workspace_id not in bound_workspace_ids(cli, name):
        raise BootstrapError(f"catalog {name} is not bound to workspace {workspace_id}")


def ensure_catalog(cli: Cli, manifest: Manifest, name: str, user: str) -> dict:
    """Create the catalog once; afterwards only accept the exact catalog the manifest recorded."""
    recorded = manifest.data.get("catalog")
    existing = get_catalog(cli, name)
    if existing is not None:
        if not recorded or recorded.get("name") != name:
            raise BootstrapError(f"catalog {name} already exists and is not recorded in {manifest.path}; refusing to adopt it")
        if fingerprint(existing) != recorded["fingerprint"] or existing.get("owner") != recorded["owner"]:
            raise BootstrapError(f"catalog {name} no longer matches the manifest (recreated or ownership changed)")
        workspace_id = int(cli.json(["metastores", "current"])["workspace_id"])
    else:
        if recorded and recorded.get("name") == name:
            raise BootstrapError(f"{manifest.path} records catalog {name}, but it does not exist; reconcile before redeploying")
        location, url, workspace_id = discover_storage(cli, user)
        storage_root = f"{url}/{name}"
        info = cli.json(["catalogs", "create", name, "--storage-root", storage_root, "--comment", CATALOG_COMMENT])
        recorded = {"name": name, "storage_root": storage_root, "external_location": location,
                    "fingerprint": fingerprint(info), "owner": info.get("owner")}
        manifest.data["catalog"] = recorded
        manifest.save()
    ensure_binding(cli, name, workspace_id)
    recorded.update({"isolation_mode": "ISOLATED", "bound_workspace_ids": [workspace_id]})
    manifest.data["catalog"] = recorded
    manifest.save()
    return recorded
