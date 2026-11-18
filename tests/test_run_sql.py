from tools.lib.bundle_config import load_target
from tools.render import render
from tools.run_sql import split_statements


def test_splits_rendered_files_into_whole_statements(tmp_path):
    render("demo", tmp_path)
    metric = split_statements((tmp_path / "sql" / "50_metric_views.sql").read_text())
    assert len(metric) == 7 and sum("WITH METRICS" in s for s in metric) == 3
    assert all(s.count("$$") in (0, 2) for s in metric)                 # YAML bodies stay whole
    security = split_statements((tmp_path / "sql" / "60_security.sql").read_text())
    assert security[0].startswith("CREATE TABLE IF NOT EXISTS") and security[1].startswith("MERGE INTO")
    assert sum(s.startswith("ALTER") for s in security) == 9
    assert not any(s.startswith("--") for s in metric + security)
