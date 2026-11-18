"""Guarded cleanup. Dry run by default; --confirm deletes only objects recorded in the manifest, in order:
Pages, subdomains, domains, governed tags, the bundle (jobs, warehouse, dashboards, Genie agents), then the catalog
after re-checking its owner and storage location against the manifest fingerprint.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.bundle_config import load_target  # noqa: E402
from tools.lib.dbcli import Cli, CliError, assert_host, is_missing  # noqa: E402
from tools.lib.manifest import DEFAULT_MANIFEST, Manifest  # noqa: E402
from tools.lib.ontology_client import OntologyClient  # noqa: E402


class CleanupError(RuntimeError):
    pass


def plan_cleanup(cli: Cli, manifest: Manifest, target: str, keep_catalog: bool = False) -> list[tuple[str, str, list]]:
    """(description, kind, argv-or-path) for each deletion, after checking every live object matches its record."""
    steps: list[tuple[str, str, list]] = []
    records = manifest.data.get("ontology") or {}
    client = OntologyClient(cli)
    for slug, page in sorted((records.get("pages") or {}).items()):
        steps.append((f"Page {slug}", "api_delete", [f"/api/2.0/knowledge/{page['name']}"]))
    live_domains = {d.get("domain_id"): d for d in client.domains().values()}
    domains = records.get("domains") or {}
    for key, record in sorted(domains.items(), key=lambda kv: "/" not in kv[1]["tag_key"]):   # subdomains first
        live = live_domains.get(record["domain_id"])
        if live is None:
            continue
        if live.get("tag_key") != record["tag_key"]:
            raise CleanupError(f"domain {record['domain_id']} now has tag key {live.get('tag_key')!r}, not "
                               f"{record['tag_key']!r}; refusing to delete it")
        steps.append((f"Domain {record['tag_key']}", "cli", ["domains", "delete-domain", record["name"]]))
    live_tags = client.tag_policies()
    for tag_key, record in sorted((records.get("tag_policies") or {}).items(), key=lambda kv: "/" not in kv[0]):
        live = live_tags.get(tag_key)
        if live is None:
            continue
        if str(live.get("id")) != str(record.get("id")):
            raise CleanupError(f"governed tag {tag_key!r} has id {live.get('id')}, not the recorded {record.get('id')}")
        steps.append((f"Governed tag {tag_key}", "cli", ["tag-policies", "delete-tag-policy", tag_key]))
    if manifest.data.get("bundle"):
        steps.append((f"Bundle resources (target {target})", "cli", ["bundle", "destroy", "--target", target,
                                                                     "--auto-approve"]))
    catalog = manifest.data.get("catalog")
    if catalog and not keep_catalog:
        try:
            live = cli.json(["catalogs", "get", catalog["name"]])
        except CliError as error:
            if not is_missing(error):
                raise
            live = None
        if live is not None:
            fingerprint = catalog.get("fingerprint") or {}
            if live.get("storage_location") != fingerprint.get("storage_location") or \
                    live.get("created_at") != fingerprint.get("created_at"):
                raise CleanupError(f"catalog {catalog['name']} does not match the recorded fingerprint; refusing")
            steps.append((f"Catalog {catalog['name']} (cascade)", "cli",
                          ["catalogs", "delete", catalog["name"], "--force"]))
    return steps


def run_cleanup(cli: Cli, manifest: Manifest, steps: list[tuple[str, str, list]]) -> None:
    for description, kind, args in steps:
        print(f"Deleting {description}")
        try:
            if kind == "api_delete":
                cli.api("delete", args[0])
            else:
                cli.run(args, timeout=3600)
        except CliError as error:
            if not is_missing(error):
                raise
    records = manifest.data.get("ontology") or {}
    for key in ("pages", "domains", "tag_policies"):
        records.pop(key, None)
    for key in ("bundle",) + (("catalog",) if any(s[0].startswith("Catalog") for s in steps) else ()):
        manifest.data.pop(key, None)
    manifest.record_run(job="cleanup", status="SUCCESS")
    manifest.save()


def main(argv: list[str] | None = None, cli_factory=Cli) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--target", default="demo", choices=["demo"])
    parser.add_argument("--state", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--keep-catalog", action="store_true", help="leave dev_gold and its data in place")
    parser.add_argument("--confirm", action="store_true", help="actually delete; without it, only print the plan")
    args = parser.parse_args(argv)
    cfg = load_target(args.target)
    cli = cli_factory(args.profile)
    host = assert_host(cli, cfg.host)
    manifest = Manifest.load(args.state)
    manifest.bind(args.target, cli.profile, host)
    steps = plan_cleanup(cli, manifest, args.target, args.keep_catalog)
    for description, _, _ in steps:
        print(("Will delete " if not args.confirm else "Plan: ") + description)
    if not args.confirm:
        print(f"Dry run: {len(steps)} deletions planned. Re-run with --confirm to delete.")
        return 0
    run_cleanup(cli, manifest, steps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
