"""Run a rendered SQL file (for example build/sql/50_metric_views.sql) statement by statement on the bundle warehouse.

Use it to re-apply comments, metric views, or row security after editing their templates, without rerunning the
setup job: `tools/render.py` first, then `tools/run_sql.py --profile <p> build/sql/<file>.sql`.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.bundle_config import load_target  # noqa: E402
from tools.lib.dbcli import Cli, assert_host  # noqa: E402
from tools.lib.manifest import DEFAULT_MANIFEST, Manifest  # noqa: E402
from tools.lib.statements import StatementError, execute  # noqa: E402

BOUNDARY = re.compile(r";\s*\n(?=\s*(?:CREATE|COMMENT|ALTER|MERGE|INSERT|DROP|--|\Z))")


def split_statements(sql: str) -> list[str]:
    """Split on statement-ending semicolons; comment-only chunks are dropped. Bodies between $$ are left intact."""
    parts = [p.strip() for p in BOUNDARY.split(sql.strip() + "\n")]
    keep = []
    for part in parts:
        body = "\n".join(line for line in part.splitlines() if not line.strip().startswith("--")).strip().rstrip(";")
        if body:
            keep.append(body)
    return keep


def main(argv: list[str] | None = None, cli_factory=Cli) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--target", default="demo", choices=["demo"])
    parser.add_argument("--state", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("file", type=Path, help="a rendered file under build/sql/")
    args = parser.parse_args(argv)
    if "{{" in args.file.read_text():
        raise SystemExit(f"{args.file} still has placeholders; run tools/render.py and pass the build/ copy")
    cfg = load_target(args.target)
    cli = cli_factory(args.profile)
    assert_host(cli, cfg.host)
    warehouse = (Manifest.load(args.state).data.get("bundle") or {}).get("warehouse_id")
    if not warehouse:
        raise SystemExit(f"{args.state} records no bundle warehouse; run ./deploy.sh first")
    statements = split_statements(args.file.read_text())
    for i, statement in enumerate(statements, 1):
        started = time.time()
        try:
            execute(cli, warehouse, statement)
        except StatementError as error:
            print(f"[{i}/{len(statements)}] FAILED: {error}")
            return 1
        print(f"[{i}/{len(statements)}] ok {time.time() - started:4.1f}s  {statement.splitlines()[0][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
