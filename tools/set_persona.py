"""Switch the operator's demo persona: corporate, dvp, rvp, dm, or none. Rewrites only the operator's row."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.bundle_config import load_target  # noqa: E402
from tools.lib.dbcli import Cli, assert_host  # noqa: E402
from tools.lib.manifest import DEFAULT_MANIFEST, Manifest  # noqa: E402
from tools.lib.personas import PersonaError, load_personas, switch  # noqa: E402
from tools.lib.statements import execute  # noqa: E402


def persona_runner(cli: Cli, warehouse_id: str):
    return lambda sql: execute(cli, warehouse_id, sql).rows


def main(argv: list[str] | None = None, cli_factory=Cli) -> int:
    personas = load_personas()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--persona", required=True, choices=sorted(personas))
    parser.add_argument("--target", default="demo", choices=["demo"])
    parser.add_argument("--state", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    cfg = load_target(args.target)
    cli = cli_factory(args.profile)
    host = assert_host(cli, cfg.host)
    manifest = Manifest.load(args.state)
    manifest.bind(args.target, cli.profile, host)
    warehouse = (manifest.data.get("bundle") or {}).get("warehouse_id")
    if not warehouse:
        raise SystemExit(f"{args.state} records no bundle warehouse; run ./deploy.sh first")
    try:
        result = switch(persona_runner(cli, warehouse), cfg.context, personas[args.persona])
    except PersonaError as error:
        raise SystemExit(str(error)) from error
    scope = f" {result['scope_value']}" if result["scope_value"] else ""
    print(f"Persona {args.persona}: {result['scope_level']}{scope}. "
          f"Visible hotels {result['visible_hotels']} (expected {result['expected_hotels']}).")
    return 0 if result["visible_hotels"] == result["expected_hotels"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
