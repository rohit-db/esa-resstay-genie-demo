"""One-command deployment of a bundle target: catalog, bundle, synthetic data, validation."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from esa_resstay_demo.data.config import STORY_WINDOW_DAYS, check_story_window, yesterday_in_new_york  # noqa: E402,F401
from tools.bootstrap import ensure_catalog  # noqa: E402
from tools.lib.bundle_config import load_target  # noqa: E402
from tools.lib.dbcli import Cli, CliError, GuardError, assert_host  # noqa: E402
from tools.lib.manifest import DEFAULT_MANIFEST, Manifest  # noqa: E402
from tools.ontology import apply_ontology  # noqa: E402
from tools.render import render  # noqa: E402
from tools.validate import run_validation, summarize  # noqa: E402

WAREHOUSE_KEY = "esa_demo_wh"
JOB_KEYS = ("setup", "nightly_refresh")


class DeployError(RuntimeError):
    pass


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Databricks CLI profile for the target workspace")
    parser.add_argument("--target", default="demo", choices=["demo"], help="the esa target arrives in milestone 5")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="YYYY-MM-DD; default yesterday (New York)")
    parser.add_argument("--skip-data", action="store_true", help="deploy without running the setup job")
    parser.add_argument("--nightly", choices=["on", "off"], default="off", help="schedule the 06:00 refresh")
    parser.add_argument("--state", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args(argv)


def record_bundle(cli: Cli, manifest: Manifest, target: str) -> None:
    resources = (cli.json(["bundle", "summary", "--target", target]) or {}).get("resources", {})
    warehouse = (resources.get("sql_warehouses") or {}).get(WAREHOUSE_KEY, {})
    jobs = resources.get("jobs") or {}
    if not warehouse.get("id") or any(not (jobs.get(k) or {}).get("id") for k in JOB_KEYS):
        raise DeployError("bundle summary is missing the warehouse or job IDs; check `databricks bundle summary`")
    manifest.data["bundle"] = {"warehouse_id": warehouse["id"], "jobs": {k: str(jobs[k]["id"]) for k in JOB_KEYS},
                               "genie_spaces": {k: str(v.get("id") or v.get("space_id"))
                                                for k, v in (resources.get("genie_spaces") or {}).items()},
                               "dashboards": {k: str(v.get("id") or v.get("dashboard_id"))
                                              for k, v in (resources.get("dashboards") or {}).items()}}
    manifest.save()


def deploy(args: argparse.Namespace, cli: Cli, today=None) -> int:
    cfg = load_target(args.target)
    host = assert_host(cli, cfg.host)
    try:
        user = cli.current_user()
    except CliError as error:
        raise GuardError(f"profile {cli.profile} cannot call the workspace ({error.stderr[:300]}); "
                         f"run: databricks auth login --host {host} --profile {cli.profile}") from error
    manifest = Manifest.load(args.state)
    manifest.bind(args.target, cli.profile, host)
    manifest.save()
    as_of = args.as_of or yesterday_in_new_york(today)
    anchor = date.fromisoformat(manifest.data.setdefault("story_anchor_date", as_of.isoformat()))
    if as_of < anchor:
        raise DeployError(f"--as-of {as_of} is before the recorded story anchor {anchor}")
    try:
        check_story_window(as_of, anchor)
    except ValueError as error:
        raise DeployError(str(error)) from error
    manifest.save()
    print(f"[1/6] Catalog {cfg.variables['catalog']}")
    ensure_catalog(cli, manifest, cfg.variables["catalog"], user)
    print("[2/6] Rendering build/")
    render(args.target)
    print("[3/6] Deploying the bundle")
    pause = "UNPAUSED" if args.nightly == "on" else "PAUSED"
    cli.run(["bundle", "deploy", "--target", args.target, "--var", f"story_anchor_date={anchor.isoformat()}",
             "--var", f"nightly_pause_status={pause}"], timeout=3600)
    record_bundle(cli, manifest, args.target)
    if args.skip_data:
        print("[4/6] Skipping the setup job (--skip-data)")
    else:
        print(f"[4/6] Running the setup job for as-of {as_of} (about 20 minutes)")
        try:
            cli.run(["bundle", "run", "setup", "--target", args.target, "--params", f"as_of_date={as_of.isoformat()}"],
                    timeout=7200)
        except CliError as error:
            manifest.record_run(job="setup", as_of_date=as_of.isoformat(), status="FAILED", error=str(error)[:2000])
            manifest.save()
            raise
        manifest.data["last_as_of_date"] = as_of.isoformat()
        manifest.record_run(job="setup", as_of_date=as_of.isoformat(), status="SUCCESS")
        manifest.save()
    print("[5/6] Discover ontology: governed tags, domains, asset tags, Pages")
    applied = apply_ontology(cli, manifest, cfg, host)
    print(f"      {len(applied.actions)} changes; {len(applied.pending)} pending")
    print("[6/6] Validating (about 15 minutes, including the Genie One hero prompts)")
    report = run_validation(cli, manifest, cfg)
    print(summarize(report))
    return 0 if report["status"] == "pass" else 1


def main(argv: list[str] | None = None, cli_factory=Cli) -> int:
    args = parse_args(argv)
    return deploy(args, cli_factory(args.profile))


if __name__ == "__main__":
    raise SystemExit(main())
