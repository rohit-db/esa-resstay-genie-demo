from pathlib import Path

import pytest

from tools.lib.bundle_config import load_target
from tools.lib.checks import Check, CheckError, generated_checks, job_sql, parse_checks
from tools.lib.contract import load_contract
from tools.lib.templates import render_template


def test_parse_checks_ignores_preamble_and_trailing_semicolons():
    checks = parse_checks("-- intro\n-- @check first_one\nSELECT 0 AS failures;\n\n-- @check second\nSELECT 1 AS failures\n")
    assert checks == [Check("first_one", "SELECT 0 AS failures"), Check("second", "SELECT 1 AS failures")]
    with pytest.raises(CheckError, match="has no SQL"):
        parse_checks("-- @check empty\n\n")


def test_generated_checks_cover_rows_keys_current_rows_and_refs():
    names = {c.name for c in generated_checks(load_contract(), load_target("demo").names)}
    assert {"rows_vw_dim_property", "unique_fact_actual_stay", "unique_fact_property_statistics",
            "current_dim_property", "ref_fact_actual_stay_bk_date_id",
            "ref_dim_crm_account_parent_account_id"} <= names


def test_date_ref_check_casts_the_string_key():
    check = next(c for c in generated_checks(load_contract(), load_target("demo").names)
                 if c.name == "ref_fact_actual_stay_bk_date_id")
    assert "CAST(c.`bk_date_id` AS INT) = p.k" in check.sql


def test_job_sql_raises_on_failures_and_rejects_duplicates():
    sql = job_sql([Check("demo_check", "SELECT 2 AS failures")])
    assert "raise_error(concat('Data check demo_check failed: '" in sql and sql.rstrip().endswith(";")
    with pytest.raises(CheckError, match="duplicate"):
        job_sql([Check("a", "SELECT 0 AS failures"), Check("a", "SELECT 0 AS failures")])


def test_story_checks_render_for_the_demo_target():
    text = render_template(Path("src/sql/checks/data_checks.sql.tmpl").read_text(), load_target("demo").context)
    checks = parse_checks(text)
    assert {"occupied_equals_stay_nights", "story_renovation_district_biggest_decline", "story_channel_shift",
            "story_stay7_lift", "story_ramp_account"} <= {c.name for c in checks}
    assert all("failures" in c.sql for c in checks)
