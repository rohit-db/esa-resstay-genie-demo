import json
from pathlib import Path

import pytest

from tools.lib.bundle_config import BundleConfigError, load_target
from tools.lib.templates import TemplateError, render_template
from tools.render import render


def test_render_template_is_strict():
    assert render_template("`{{catalog}}`.`{{ mart }}`", {"catalog": "dev_gold", "mart": "mart"}) == "`dev_gold`.`mart`"
    with pytest.raises(TemplateError, match="unknown placeholders"):
        render_template("{{nope}}", {})
    with pytest.raises(TemplateError, match="unbalanced"):
        render_template("{{catalog}} }}", {"catalog": "x"})


def test_demo_and_esa_targets():
    demo = load_target("demo")
    assert demo.host == "https://fe-sandbox-esa-resstay-demo.cloud.databricks.com"
    assert demo.context == {"catalog": "dev_gold", "mart": "mart", "common": "common", "staging": "staging",
                            "semantic": "semantic", "security": "security"}
    assert demo.variables["run_data"] == "true"
    esa = load_target("esa")
    assert esa.host is None and esa.variables["run_data"] == "false"
    with pytest.raises(BundleConfigError, match="unknown bundle target"):
        load_target("prod")


def test_names_must_be_plain_identifiers(tmp_path):
    text = Path("databricks.yml").read_text().replace("default: dev_gold", "default: dev-gold")
    path = tmp_path / "databricks.yml"
    path.write_text(text)
    with pytest.raises(BundleConfigError, match="plain SQL identifier"):
        load_target("demo", path).context


def test_render_writes_every_bundle_file(tmp_path):
    written = render("demo", tmp_path)
    assert set(written) == {"00_schemas.sql", "10_tables.sql", "20_load.sql", "30_views.sql",
                            "31_materialized_views.sql", "32_refresh_materialized_views.sql",
                            "35_comments.sql", "40_data_checks.sql", "50_metric_views.sql", "60_security.sql", "data_checks.json",
                            "staging_schema.json", "resstay_revenue.geniespace.json",
                            "property_operations.geniespace.json", "resstay.lvdash.json",
                            "occupancy.lvdash.json"}
    for path in written.values():
        text = path.read_text()
        assert "{{" not in text and "}}" not in text
    assert "`dev_gold`.`mart`.`vw_dim_property`" in (tmp_path / "sql" / "30_views.sql").read_text()
    metric_views = (tmp_path / "sql" / "50_metric_views.sql").read_text()
    assert "source: dev_gold.mart.fact_actual_stay" in metric_views and metric_views.count("WITH METRICS") == 3
    assert "COMMENT ON COLUMN `dev_gold`.`mart`.`dim_los`.`los_band_1`" in (tmp_path / "sql" / "35_comments.sql").read_text()
    checks = json.loads((tmp_path / "checks" / "data_checks.json").read_text())
    assert len({c["name"] for c in checks}) == len(checks) > 60
