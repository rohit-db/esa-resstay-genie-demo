import pytest

from tools.lib.personas import PersonaError, expected_sql, load_personas, resolve_sql, set_sql, switch

NAMES = {"catalog": "dev_gold", "mart": "mart", "staging": "staging", "security": "security"}


def test_repo_personas_cover_every_scope():
    personas = load_personas()
    assert [p.scope_level for p in personas.values()] == ["CORPORATE", "DIVISION", "REGION", "DISTRICT", "NONE"]


def test_set_sql_rewrites_only_the_operator_row():
    personas = load_personas()
    merge = set_sql(NAMES, personas["dm"], "Texas District 2")
    assert merge.startswith("MERGE INTO `dev_gold`.`security`.`property_entitlements`")
    assert "lower(e.principal) = lower(current_user())" in merge and "'DISTRICT'" in merge
    assert "'Texas District 2'" in merge and "'dm'" in merge
    assert set_sql(NAMES, personas["corporate"], None).count("NULL") == 2
    delete = set_sql(NAMES, personas["none"], None)
    assert delete.startswith("DELETE FROM") and "current_user()" in delete


def test_scope_values_are_escaped():
    merge = set_sql(NAMES, load_personas()["dm"], "O'Hare District")
    assert "'O\\'Hare District'" in merge


def test_resolution_reads_staging_and_the_unfiltered_lookup():
    sql = resolve_sql(NAMES)
    assert "`dev_gold`.`staging`.`fact_property_renovation`" in sql and "property_scope_lookup" in sql
    assert "dev_gold`.`mart" not in sql
    assert "district_name = 'D1'" in expected_sql(NAMES, load_personas()["dm"], "D1")
    assert expected_sql(NAMES, load_personas()["none"], None) == "SELECT 0 AS hotels"


def test_switch_resolves_applies_and_reports(tmp_path):
    executed = []

    def run(sql):
        executed.append(sql)
        if "duplicates" in sql:
            return []
        if sql.startswith("WITH reno"):
            return [["West", "Texas", "Texas District 2", "4"]]
        if sql.startswith("SELECT count(*) AS hotels"):
            return [["10"]]
        if "visible_hotels" in sql:
            return [["10"]]
        return []
    result = switch(run, NAMES, load_personas()["dm"])
    assert result == {"persona": "dm", "scope_level": "DISTRICT", "scope_value": "Texas District 2",
                      "expected_hotels": 10, "visible_hotels": 10}
    assert any(s.startswith("MERGE INTO") for s in executed)


def test_duplicate_entitlements_stop_the_switch():
    with pytest.raises(PersonaError, match="duplicate"):
        switch(lambda sql: [["someone@example.com", "2"]] if "duplicates" in sql else [], NAMES,
               load_personas()["corporate"])
