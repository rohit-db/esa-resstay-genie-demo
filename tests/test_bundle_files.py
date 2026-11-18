from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return yaml.safe_load((ROOT / name).read_text())


def test_every_variable_has_a_default_and_targets_exist():
    bundle = load("databricks.yml")
    assert all("default" in spec for spec in bundle["variables"].values())
    assert set(bundle["targets"]) == {"demo", "esa"}
    assert bundle["sync"]["include"] == ["build/**"] and bundle["artifacts"]["esa_wheel"]["dynamic_version"] is True


def test_sql_tasks_point_at_files_the_renderer_writes():
    rendered = {"00_schemas.sql", "10_tables.sql", "20_load.sql", "30_views.sql", "31_materialized_views.sql",
                "32_refresh_materialized_views.sql", "35_comments.sql", "40_data_checks.sql", "50_metric_views.sql", "60_security.sql"}
    for job_file in ("resources/setup_job.yml", "resources/nightly_job.yml"):
        job = next(iter(load(job_file)["resources"]["jobs"].values()))
        for task in job["tasks"]:
            if "sql_task" in task:
                path = task["sql_task"]["file"]["path"]
                assert path.startswith("../build/sql/") and Path(path).name in rendered
                assert task["sql_task"]["warehouse_id"] == "${resources.sql_warehouses.esa_demo_wh.id}"


def test_wheel_task_matches_the_package_entry_point():
    pyproject = (ROOT / "pyproject.toml").read_text()
    assert 'generate = "esa_resstay_demo.jobs.generate:main"' in pyproject
    for job_file in ("resources/setup_job.yml", "resources/nightly_job.yml"):
        job = next(iter(load(job_file)["resources"]["jobs"].values()))
        wheel = next(t for t in job["tasks"] if "python_wheel_task" in t)["python_wheel_task"]
        assert (wheel["package_name"], wheel["entry_point"]) == ("esa_resstay_demo", "generate")
        assert job["environments"][0]["spec"]["dependencies"] == ["../dist/*.whl"]
        gated = [t for t in job["tasks"] if t.get("depends_on") == [{"task_key": "data_enabled", "outcome": "true"}]]
        assert len(gated) == 1


def test_demo_target_pins_the_sandbox_workspace():
    """Pinning the workspace ID makes bundle commands refuse any other workspace, whatever the profile says."""
    demo = load("databricks.yml")["targets"]["demo"]["workspace"]
    assert demo["host"] == "https://fe-sandbox-esa-resstay-demo.cloud.databricks.com"
    assert demo["workspace_id"] == 7474655108048127


def test_setup_job_recreates_tables_only_after_generation_succeeds():
    """A failed generator run must leave the existing mart tables untouched."""
    tasks = {t["task_key"]: t for t in load("resources/setup_job.yml")["resources"]["jobs"]["setup"]["tasks"]}
    assert tasks["generate"]["depends_on"] == [{"task_key": "schemas"}]
    assert {"task_key": "generate"} in tasks["tables"]["depends_on"]


def test_setup_job_comments_and_builds_metric_views_before_the_data_checks():
    tasks = {t["task_key"]: t for t in load("resources/setup_job.yml")["resources"]["jobs"]["setup"]["tasks"]}
    for key in ("comments", "metric_views"):
        assert {d["task_key"] for d in tasks[key]["depends_on"]} == {"views", "materialized_views"}
    assert {d["task_key"] for d in tasks["data_checks"]["depends_on"]} == {"comments", "metric_views", "security"}
    assert {d["task_key"] for d in tasks["security"]["depends_on"]} == {"views", "materialized_views"}
