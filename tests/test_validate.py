import json

from tools.lib.bundle_config import load_target
from tools.lib.contract import load_contract
from tools.lib.manifest import Manifest
from tools.validate import run_validation, schema_problems


def live_rows(contract, cfg, mutate=None):
    rows = []
    for table in contract.tables:
        schema = cfg.names.schema_for(table.schema)
        for i, col in enumerate(contract.all_columns(table), start=1):
            rows.append({"table_schema": schema, "table_name": table.name, "column_name": col.name,
                         "ordinal_position": str(i), "full_data_type": col.type.lower().replace(",", ", ")})
    return mutate(rows) if mutate else rows


def test_schema_matches_when_live_columns_equal_the_contract():
    contract, cfg = load_contract(), load_target("demo")
    assert schema_problems(contract, cfg, live_rows(contract, cfg)) == []


def test_schema_reports_missing_objects_and_wrong_types():
    contract, cfg = load_contract(), load_target("demo")

    def mutate(rows):
        rows = [r for r in rows if r["table_name"] != "dim_los"]
        for r in rows:
            if r["table_name"] == "fact_actual_stay" and r["column_name"] == "room_revenue_amount":
                r["full_data_type"] = "double"
        return rows
    problems = schema_problems(contract, cfg, live_rows(contract, cfg, mutate))
    assert "mart.dim_los: missing" in problems
    assert any("room_revenue_amount is double not decimal(38,2)" in p for p in problems)


def test_report_records_each_check_and_fails_on_violations(tmp_path, fake_cli):
    checks = tmp_path / "checks.json"
    checks.write_text(json.dumps([{"name": "good", "sql": "SELECT 0 AS failures"}, {"name": "bad", "sql": "SELECT 5 AS failures"}]))
    answers = {"SELECT 0 AS failures": "0", "SELECT 5 AS failures": "5"}

    def post(args):
        sql = json.loads(args[2])["statement"]
        return {"statement_id": f"id-{answers[sql]}", "status": {"state": "SUCCEEDED"},
                "manifest": {"schema": {"columns": [{"name": "failures"}]}}, "result": {"data_array": [[answers[sql]]]}}
    manifest = Manifest(tmp_path / "m.json", {"version": 1, "bundle": {"warehouse_id": "wh"}})
    report = run_validation(fake_cli({("post", "/api/2.0/sql/statements"): post}), manifest, load_target("demo"),
                            sections=("data",), checks_file=checks, report_file=tmp_path / "validation.json")
    assert report["status"] == "fail"
    by_name = {c["name"]: c for c in report["sections"]["data"]["checks"]}
    assert by_name["good"]["status"] == "pass" and by_name["bad"] == {"name": "bad", "status": "fail", "failures": 5, "statement_id": "id-5"}
    assert json.loads((tmp_path / "validation.json").read_text())["status"] == "fail"
