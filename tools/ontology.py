"""Discover ontology for a bundle target: governed tags, ESA domains and subdomains, asset tags, and Pages.

  plan    show what apply would change (read-only)
  apply   create or update recorded objects, then verify
  verify  exit nonzero unless the account matches ontology/ (pending assets are allowed unless --strict)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.bundle_config import load_target  # noqa: E402
from tools.lib.contract import load_contract  # noqa: E402
from tools.lib.dbcli import Cli, assert_host  # noqa: E402
from tools.lib.manifest import DEFAULT_MANIFEST, Manifest  # noqa: E402
from tools.lib.ontology import (DEFAULT_DOMAINS, DEFAULT_PAGES, NAME_KEYS, Context, Result, check_coverage,  # noqa: E402
                                load_ontology, plan, reconcile)
from tools.lib.ontology_client import OntologyClient  # noqa: E402

REPORT_FILE = ROOT / ".state" / "ontology.json"


def build_context(cfg, manifest: Manifest, host: str) -> Context:
    """Names come from the bundle target; dashboard and Genie space IDs from the manifest's bundle record."""
    names = {k: cfg.context[k] for k in NAME_KEYS}
    bundle = manifest.data.get("bundle") or {}
    ids, urls = {}, {}
    for key, space_id in (bundle.get("genie_spaces") or {}).items():
        ids[f"genie:{key}"], urls[f"genie:{key}"] = space_id, f"{host}/genie/rooms/{space_id}"
    for key, dashboard_id in (bundle.get("dashboards") or {}).items():
        ids[f"dashboard:{key}"], urls[f"dashboard:{key}"] = dashboard_id, f"{host}/sql/dashboardsv3/{dashboard_id}/published"
    return Context(names=names, workspace_ids=ids, urls=urls)


def summarize(result: Result, heading: str) -> str:
    lines = [heading]
    lines += [f"  {a.describe()}" for a in result.actions] or ["  (no changes)"]
    for label, items in (("pending", result.pending), ("problems", result.problems), ("unmanaged", result.unmanaged)):
        if items:
            lines.append(f"{label}:")
            lines += [f"  - {item}" for item in items]
    return "\n".join(lines)


def write_report(result: Result, records: dict, status: str, path: Path = REPORT_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": status,
        "remaining_actions": [a.describe() for a in result.actions], "pending": result.pending,
        "problems": result.problems, "unmanaged": result.unmanaged, "records": records}, indent=2) + "\n")


def apply_ontology(cli: Cli, manifest: Manifest, cfg, host: str) -> Result:
    """Reconcile the account with ontology/ for deploy.py; records every created object in the manifest."""
    ontology = load_ontology(DEFAULT_DOMAINS, DEFAULT_PAGES)
    check_coverage(ontology.nodes, load_contract())
    ctx = build_context(cfg, manifest, host)
    client = OntologyClient(cli)
    result = reconcile(ontology, client.gather(ontology, ctx), manifest.data.setdefault("ontology", {}), ctx, client,
                       save=manifest.save)
    manifest.save()
    return result


def main(argv: list[str] | None = None, cli_factory=Cli) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["plan", "apply", "verify"])
    parser.add_argument("--profile", required=True, help="Databricks CLI profile for the target workspace")
    parser.add_argument("--target", default="demo", choices=["demo"], help="the esa target arrives later")
    parser.add_argument("--state", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--strict", action="store_true", help="verify fails while any asset or Page is pending")
    parser.add_argument("--pages-dir", type=Path, default=DEFAULT_PAGES, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    cfg = load_target(args.target)
    cli = cli_factory(args.profile)
    host = assert_host(cli, cfg.host)
    manifest = Manifest.load(args.state)
    if "catalog" not in manifest.data:
        raise SystemExit(f"{args.state} records no catalog; run ./deploy.sh first")
    manifest.bind(args.target, cli.profile, host)
    ontology = load_ontology(DEFAULT_DOMAINS, args.pages_dir)
    check_coverage(ontology.nodes, load_contract())
    ctx = build_context(cfg, manifest, host)
    client = OntologyClient(cli)
    records = manifest.data.setdefault("ontology", {})

    if args.command == "plan":
        print(summarize(plan(ontology, client.gather(ontology, ctx), records, ctx), "Planned changes:"))
        return 0
    if args.command == "apply":
        applied = reconcile(ontology, client.gather(ontology, ctx), records, ctx, client, save=manifest.save)
        manifest.save()
        print(summarize(applied, "Applied:"))
    check = plan(ontology, client.gather(ontology, ctx), records, ctx)
    failed = bool(check.actions or check.problems or (args.strict and check.pending))
    write_report(check, records, "fail" if failed else "pass")
    print(summarize(check, "Verify: " + ("FAIL, remaining differences:" if failed else "PASS")))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
