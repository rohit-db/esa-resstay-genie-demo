import re
from pathlib import Path

import pytest
import yaml

from tools.lib import dashboards as d

NAMES = d.Names("dev_gold", "mart", "semantic")
VERSIONS = {"counter": 2, "table": 2, "bar": 3, "line": 3, "filter-multi-select": 2, "filter-single-select": 2}
BUILT = {"resstay": d.resstay_dashboard(NAMES, "g1", "Texas District 2"), "occupancy": d.occupancy_dashboard(NAMES, "g2")}


def widgets(dashboard):
    for page in dashboard["pages"]:
        for item in page["layout"]:
            yield page, item["widget"], item["position"]


@pytest.mark.parametrize("key", sorted(BUILT))
def test_widgets_bind_fields_measures_and_versions_consistently(key):
    dashboard = BUILT[key]
    datasets = {ds["name"]: ds for ds in dashboard["datasets"]}
    names = set()
    for page, widget, _ in widgets(dashboard):
        assert re.fullmatch(r"[A-Za-z0-9_-]{1,60}", widget["name"]) and widget["name"] not in names
        names.add(widget["name"])
        if "multilineTextboxSpec" in widget:
            continue
        spec = widget["spec"]
        assert spec["version"] == VERSIONS[spec["widgetType"]], widget["name"]
        assert spec["frame"]["showTitle"] is True
        query_names = {q["name"] for q in widget["queries"]}
        fields = {f["name"] for q in widget["queries"] for f in q["query"].get("fields", [])}
        for q in widget["queries"]:
            ds = datasets[q["query"]["datasetName"]]
            measures = {c["displayName"] for c in ds.get("columns", [])}
            for f in q["query"].get("fields", []):
                for m in re.findall(r"MEASURE\(`([^`]+)`\)", f["expression"]):
                    assert m in measures, f"{widget['name']}: {m} is not a measure of {ds['name']}"
            for p in q["query"].get("parameters", []):
                assert p["keyword"] in {x["keyword"] for x in ds.get("parameters", [])}
        enc = spec["encodings"]
        bound = []
        for value in enc.values():
            items = value if isinstance(value, list) else [value]
            for item in items:
                bound += item.get("fields", []) if isinstance(item.get("fields"), list) else [item]
        for item in bound:
            if "fieldName" in item:
                assert item["fieldName"] in fields, f"{widget['name']}: {item['fieldName']} has no query field"
            if "queryName" in item:
                assert item["queryName"] in query_names
        if page["pageType"] == "PAGE_TYPE_GLOBAL_FILTERS":
            assert spec["widgetType"].startswith("filter-")


@pytest.mark.parametrize("key", sorted(BUILT))
def test_canvas_layouts_fit_the_grid_without_overlaps(key):
    for page in BUILT[key]["pages"]:
        assert page["layoutVersion"] == "GRID_V1"
        if page["pageType"] != "PAGE_TYPE_CANVAS":
            continue
        cells = set()
        for item in page["layout"]:
            p = item["position"]
            assert p["x"] + p["width"] <= 12
            for x in range(p["x"], p["x"] + p["width"]):
                for y in range(p["y"], p["y"] + p["height"]):
                    assert (x, y) not in cells, f"{page['name']}: overlap at {(x, y)}"
                    cells.add((x, y))


def test_every_global_filter_reaches_every_data_dataset():
    dashboard = BUILT["resstay"]
    filters = next(p for p in dashboard["pages"] if p["pageType"] == "PAGE_TYPE_GLOBAL_FILTERS")["layout"]
    for item in filters:
        widget = item["widget"]
        targets = {q["query"]["datasetName"] for q in widget["queries"]}
        if widget["name"] == "filter-period":
            assert targets == {"ds_period_options", "ds_property", "ds_los", "ds_channel"}
        elif widget["name"] != "filter-view-by":
            assert targets == {"ds_property", "ds_los", "ds_channel", "ds_month"}, widget["name"]


def test_queries_use_target_names_and_the_period_parameter():
    queries = dict((name, (sql, params)) for name, sql, params in d.dataset_queries(BUILT["resstay"]))
    sql, params = queries["ds_property"]
    assert "dev_gold.semantic.resstay_metrics" in sql and "dev_gold.semantic.occupancy_metrics" in sql
    assert params == {"period": "MTD", "view_by": "District Manager"}
    assert ":period" in queries["ds_los"][0] and queries["ds_month"][1] == {}
    assert BUILT["resstay"]["uiSettings"]["genieSpace"]["overrideId"] == "g1"


def test_bundle_dashboards_match_the_rendered_files():
    resources = yaml.safe_load(Path("resources/dashboards.yml").read_text())["resources"]["dashboards"]
    assert set(resources) == set(BUILT)
    for key, resource in resources.items():
        assert resource["file_path"] == f"../build/dashboards/{key}.lvdash.json"
        assert resource["warehouse_id"] == "${resources.sql_warehouses.esa_demo_wh.id}"
        assert resource["embed_credentials"] is False          # each viewer's row security applies
