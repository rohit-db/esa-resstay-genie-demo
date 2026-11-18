import re

from tools.lib.contract import load_contract
from tools.lib.sqlgen import SchemaNames, create_tables_sql, load_sql, materialized_views_sql, refresh_sql, staging_schema

NAMES = SchemaNames("dev_gold", "mart", "common", "staging", "semantic", "security")


def _statement(sql: str, table: str) -> str:
    return next(s for s in sql.split(";") if f"`{table}`" in s.strip().split("\n", 1)[0])


def test_ddl_creates_every_table_with_contract_columns_in_order():
    contract = load_contract()
    ddl = create_tables_sql(contract, NAMES)
    for table in contract.of_kind("table"):
        stmt = _statement(ddl, table.name)
        assert stmt.strip().startswith(f"CREATE OR REPLACE TABLE {NAMES.fq(table)}")
        cols = re.findall(r"^\s+`([^`]+)` ", stmt, flags=re.MULTILINE)
        assert cols == [c.name for c in contract.all_columns(table)]
    assert "`dev_gold`.`common`.`dim_date`" in ddl
    assert "CLUSTER BY (`bk_date_id`, `bk_property_id`)" in _statement(ddl, "fact_actual_stay")
    assert "`fact_actual_stay_id` STRING NOT NULL" in ddl


def test_load_casts_business_columns_and_derives_history():
    contract = load_contract()
    sql = load_sql(contract, NAMES)
    stmt = _statement(sql, "fact_actual_stay")
    assert stmt.strip().startswith("INSERT OVERWRITE TABLE `dev_gold`.`mart`.`fact_actual_stay` (`fact_actual_stay_id`")
    assert "CAST(`room_revenue_amount` AS DECIMAL(38,2)) AS `room_revenue_amount`" in stmt
    assert "sha2(concat_ws('||', coalesce(CAST(`fact_actual_stay_id` AS STRING), '')" in stmt
    assert "false AS `is_deleted`" in stmt
    assert "FROM `dev_gold`.`staging`.`fact_actual_stay`" in stmt
    assert sql.count("INSERT OVERWRITE") == len(contract.of_kind("table"))


def test_materialized_view_and_refresh():
    contract = load_contract()
    mv = materialized_views_sql(contract, NAMES)
    assert mv.startswith("CREATE OR REPLACE MATERIALIZED VIEW `dev_gold`.`mart`.`fact_property_statistics`")
    assert "CAST(`bk_date_id` AS INT) AS `bk_date_id`" in mv
    assert refresh_sql(contract, NAMES) == "REFRESH MATERIALIZED VIEW `dev_gold`.`mart`.`fact_property_statistics`;\n"


def test_staging_schema_uses_spark_types_and_load_metadata():
    schema = staging_schema(load_contract())
    assert "vw_dim_property" not in schema and len(schema) == 19
    cols = dict(schema["fact_actual_stay"])
    assert cols["room_revenue_amount"] == "double" and cols["consumed_room_nights_count"] == "bigint"
    assert [c for c, _ in schema["dim_date"][-6:]] == ["_record_source", "_load_ts", "_dq_status", "_version_start", "_version_end", "_is_current"]
