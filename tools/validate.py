"""Validate a deployment and write .state/validation.json: schema, data, semantics, dashboards, Genie,
ontology, row security, and the Genie One hero prompts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.bundle_config import TargetConfig, load_target  # noqa: E402
from tools.lib.contract import Contract, load_contract  # noqa: E402
from tools.lib.dbcli import Cli, assert_host  # noqa: E402
from tools.lib.manifest import DEFAULT_MANIFEST, Manifest  # noqa: E402
from tools.lib.statements import StatementError, execute  # noqa: E402
from tools.lib import live_checks  # noqa: E402

SECTIONS = ("schema", "data", "semantics", "dashboards", "genie", "ontology", "security", "genie_one")
PASSING = {"pass", "review"}          # review: Genie One answered in scope but needs a human read
BUILD_DIR = ROOT / "build"
CHECKS_FILE = ROOT / "build" / "checks" / "data_checks.json"
REPORT_FILE = ROOT / ".state" / "validation.json"


def normalize_type(value: str) -> str:
    return value.replace(" ", "").lower()


def schema_problems(contract: Contract, cfg: TargetConfig, rows: list[dict]) -> list[str]:
    """Compare live information_schema columns with the contract (names, order, and types)."""
    names = cfg.names
    live: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for row in sorted(rows, key=lambda r: (r["table_schema"], r["table_name"], int(r["ordinal_position"]))):
        live.setdefault((row["table_schema"].lower(), row["table_name"].lower()), []).append(
            (row["column_name"].lower(), normalize_type(row["full_data_type"])))
    problems = []
    for table in contract.tables:
        key = (names.schema_for(table.schema).lower(), table.name.lower())
        expected = [(c.name.lower(), normalize_type(c.type)) for c in contract.all_columns(table)]
        actual = live.get(key)
        if actual is None:
            problems.append(f"{key[0]}.{table.name}: missing")
        elif actual != expected:
            missing = [c for c, _ in expected if c not in dict(actual)]
            wrong = [f"{c} is {dict(actual)[c]} not {t}" for c, t in expected if c in dict(actual) and dict(actual)[c] != t]
            problems.append(f"{key[0]}.{table.name}: columns differ (missing {missing}; types {wrong}; "
                            f"order matches={[c for c, _ in actual] == [c for c, _ in expected]})")
    return problems


def check_schema(cli: Cli, warehouse_id: str, contract: Contract, cfg: TargetConfig) -> dict:
    n = cfg.names
    sql = (f"SELECT table_schema, table_name, column_name, ordinal_position, full_data_type "
           f"FROM `{n.catalog}`.information_schema.columns "
           f"WHERE table_schema IN ('{n.mart}', '{n.common}') ORDER BY table_schema, table_name, ordinal_position")
    try:
        result = execute(cli, warehouse_id, sql)
    except StatementError as error:
        return {"status": "error", "statement_id": error.statement_id, "error": str(error)}
    problems = schema_problems(contract, cfg, result.records())
    return {"status": "pass" if not problems else "fail", "statement_id": result.statement_id, "problems": problems}


def check_data(cli: Cli, warehouse_id: str, checks_file: Path) -> dict:
    checks = json.loads(Path(checks_file).read_text())
    results = []
    for check in checks:
        try:
            result = execute(cli, warehouse_id, check["sql"])
            failures = int(result.records()[0]["failures"])
            results.append({"name": check["name"], "status": "pass" if failures == 0 else "fail",
                            "failures": failures, "statement_id": result.statement_id})
        except (StatementError, KeyError, IndexError, TypeError, ValueError) as error:
            results.append({"name": check["name"], "status": "error", "error": str(error),
                            "statement_id": getattr(error, "statement_id", None)})
    status = "pass" if all(r["status"] == "pass" for r in results) else "fail"
    return {"status": status, "checks": results}


def check_ontology(cli: Cli, manifest: Manifest, cfg: TargetConfig) -> dict:
    """Strict ontology verify: nothing left to create or update, and nothing pending."""
    from tools.lib.contract import load_contract as _contract
    from tools.lib.ontology import check_coverage, load_ontology, plan
    from tools.lib.ontology_client import OntologyClient
    from tools.ontology import build_context
    ontology = load_ontology()
    check_coverage(ontology.nodes, _contract())
    ctx = build_context(cfg, manifest, str(manifest.data.get("host") or cfg.host))
    result = plan(ontology, OntologyClient(cli).gather(ontology, ctx), manifest.data.get("ontology") or {}, ctx)
    problems = [a.describe() for a in result.actions] + result.problems + [f"pending: {p}" for p in result.pending]
    return {"status": "fail" if problems else "pass", "problems": problems, "unmanaged": result.unmanaged}


def run_validation(cli: Cli, manifest: Manifest, cfg: TargetConfig, sections=SECTIONS,
                   checks_file: Path = CHECKS_FILE, report_file: Path = REPORT_FILE,
                   contract: Contract | None = None) -> dict:
    warehouse_id = (manifest.data.get("bundle") or {}).get("warehouse_id")
    if not warehouse_id:
        raise SystemExit("the manifest has no bundle.warehouse_id; run deploy.py first")
    contract = contract or load_contract()
    report = {"target": cfg.target, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sections": {}}
    if "schema" in sections:
        report["sections"]["schema"] = check_schema(cli, warehouse_id, contract, cfg)
    if "data" in sections:
        report["sections"]["data"] = check_data(cli, warehouse_id, checks_file)
    context = cfg.context
    if "semantics" in sections:
        report["sections"]["semantics"] = live_checks.check_semantics(cli, warehouse_id, contract, context)
    if "dashboards" in sections:
        report["sections"]["dashboards"] = live_checks.check_dashboards(cli, warehouse_id, BUILD_DIR)
    if "genie" in sections:
        report["sections"]["genie"] = live_checks.check_genie(cli, warehouse_id, BUILD_DIR)
    if "ontology" in sections:
        report["sections"]["ontology"] = check_ontology(cli, manifest, cfg)
    if "security" in sections:
        report["sections"]["security"] = live_checks.check_security(
            lambda sql: execute(cli, warehouse_id, sql).rows, context)
    if "genie_one" in sections:
        spaces = set(((manifest.data.get("bundle") or {}).get("genie_spaces") or {}).values())
        report["sections"]["genie_one"] = live_checks.check_genie_one(
            cli, warehouse_id, context, manifest.data.get("ontology") or {}, spaces,
            session=f"validate-{datetime.now(timezone.utc):%Y%m%d%H%M%S}")
    report["status"] = "pass" if all(s["status"] in PASSING for s in report["sections"].values()) else "fail"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2) + "\n")
    return report


def summarize(report: dict) -> str:
    lines = [f"Validation {report['status'].upper()} for target {report['target']}"]
    for name, section in report["sections"].items():
        lines.append(f"  {name}: {section['status']}")
        for problem in section.get("problems", []):
            lines.append(f"    - {problem}")
        for check in section.get("checks", []):
            if check["status"] != "pass":
                detail = check.get("failures", check.get("error", check.get("problems", "")))
                lines.append(f"    - {check['name']}: {check['status']} {detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None, cli_factory=Cli) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--target", default="demo")
    parser.add_argument("--state", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--sections", default=",".join(SECTIONS))
    args = parser.parse_args(argv)
    cfg = load_target(args.target)
    cli = cli_factory(args.profile)
    assert_host(cli, cfg.host)
    report = run_validation(cli, Manifest.load(args.state), cfg, tuple(args.sections.split(",")))
    print(summarize(report))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
