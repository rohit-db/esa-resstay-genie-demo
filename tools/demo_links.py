"""Print every demo link (catalog, dashboards, Genie agents, ESA Pages) from the manifest; IDs change per deploy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lib.manifest import DEFAULT_MANIFEST  # noqa: E402

TITLES = {"resstay": "ResStay Dashboard", "occupancy": "Occupancy Trend by Week",
          "resstay_revenue": "Genie: ESA ResStay Revenue", "property_operations": "Genie: ESA Property Operations"}


def links(manifest: dict) -> list[tuple[str, str]]:
    host = manifest["host"].rstrip("/")
    bundle = manifest.get("bundle") or {}
    out = [("Catalog dev_gold", f"{host}/explore/data/{manifest['catalog']['name']}"),
           ("Metric views", f"{host}/explore/data/{manifest['catalog']['name']}/semantic")]
    out += [(TITLES.get(k, k), f"{host}/sql/dashboardsv3/{v}/published") for k, v in (bundle.get("dashboards") or {}).items()]
    out += [(TITLES.get(k, k), f"{host}/genie/rooms/{v}") for k, v in (bundle.get("genie_spaces") or {}).items()]
    pages = (manifest.get("ontology") or {}).get("pages") or {}
    out += [(f"Page {slug}", f"{host}/one/discover/pages/{p['name'].rsplit('/', 1)[-1]}") for slug, p in sorted(pages.items())]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    for title, url in links(json.loads(Path(args.state).read_text())):
        print(f"{title:<45} {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
