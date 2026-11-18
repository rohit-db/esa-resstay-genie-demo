"""Render bundle-ready SQL, data checks, and the generator's staging schema for one target into build/."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.bundle_config import load_target  # noqa: E402
from tools.lib.checks import generated_checks, job_sql, parse_checks  # noqa: E402
from tools.lib.comments import comments_sql, load_descriptions  # noqa: E402
from tools.lib.contract import DEFAULT_CONTRACT, load_contract  # noqa: E402
from tools.lib.genie import GENIE_DIR, load_space, serialized_space  # noqa: E402
from tools.lib import dashboards  # noqa: E402
from tools.lib.manifest import DEFAULT_MANIFEST  # noqa: E402
from tools.lib.sqlgen import create_tables_sql, load_sql, materialized_views_sql, refresh_sql, staging_schema  # noqa: E402
from tools.lib.templates import render_template  # noqa: E402

SQL_DIR = ROOT / "src" / "sql"
BUILD_DIR = ROOT / "build"


def deployed_genie_spaces(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, str]:
    """Genie space IDs from an earlier deploy, so dashboards can link their agent (absent on a first deploy)."""
    if not Path(manifest_path).exists():
        return {}
    return (json.loads(Path(manifest_path).read_text()).get("bundle") or {}).get("genie_spaces") or {}


def render(target: str, out: Path = BUILD_DIR, contract_path: Path = DEFAULT_CONTRACT,
           bundle_path: Path = ROOT / "databricks.yml", sql_dir: Path = SQL_DIR,
           manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Path]:
    cfg = load_target(target, bundle_path)
    contract = load_contract(contract_path)
    names, context = cfg.names, cfg.context
    sql_out, checks_out, genie_out, dash_out = out / "sql", out / "checks", out / "genie", out / "dashboards"
    for folder in (sql_out, checks_out, genie_out, dash_out):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
    checks = generated_checks(contract, names) + parse_checks(
        render_template((sql_dir / "checks" / "data_checks.sql.tmpl").read_text(), context))
    files = {
        sql_out / "00_schemas.sql": render_template((sql_dir / "00_schemas.sql.tmpl").read_text(), context),
        sql_out / "10_tables.sql": create_tables_sql(contract, names),
        sql_out / "20_load.sql": load_sql(contract, names),
        sql_out / "30_views.sql": render_template((sql_dir / "30_views.sql.tmpl").read_text(), context),
        sql_out / "31_materialized_views.sql": materialized_views_sql(contract, names),
        sql_out / "32_refresh_materialized_views.sql": refresh_sql(contract, names),
        sql_out / "35_comments.sql": comments_sql(contract, load_descriptions(contract=contract), names),
        sql_out / "40_data_checks.sql": job_sql(checks),
        sql_out / "50_metric_views.sql": render_template((sql_dir / "50_metric_views.sql.tmpl").read_text(), context),
        sql_out / "60_security.sql": render_template((sql_dir / "60_security.sql.tmpl").read_text(), context),
        checks_out / "data_checks.json": json.dumps([{"name": c.name, "sql": c.sql} for c in checks], indent=2) + "\n",
        out / "staging_schema.json": json.dumps(staging_schema(contract), indent=2) + "\n",
    }
    for spec in (load_space(p) for p in sorted(GENIE_DIR.glob("*.yml"))):
        space = serialized_space(spec, context, contract)
        files[genie_out / f"{spec.key}.geniespace.json"] = json.dumps(space, indent=2) + "\n"
    spaces = deployed_genie_spaces(manifest_path)
    names = dashboards.Names(context["catalog"], context["mart"], context["semantic"])
    settings = yaml.safe_load((ROOT / "dashboards" / "config.yml").read_text()) or {}
    built = {"resstay": dashboards.resstay_dashboard(names, spaces.get("resstay_revenue"),
                                                     settings.get("comparison_district")),
             "occupancy": dashboards.occupancy_dashboard(names, spaces.get("property_operations"))}
    for key, dashboard in built.items():
        files[dash_out / f"{key}.lvdash.json"] = json.dumps(dashboard, indent=2) + "\n"
    for path, text in files.items():
        path.write_text(text)
    return {path.name: path for path in files}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default="demo")
    parser.add_argument("--out", type=Path, default=BUILD_DIR)
    args = parser.parse_args(argv)
    written = render(args.target, args.out)
    print(f"Rendered {len(written)} files for target {args.target} into {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
