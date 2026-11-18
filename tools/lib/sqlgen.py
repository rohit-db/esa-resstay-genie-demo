"""Generate DDL, staging-to-mart loads, materialized views, and the staging schema from the contract."""

from __future__ import annotations

from dataclasses import dataclass

from tools.lib.contract import Column, Contract, Table

META_COLUMNS = ("_record_source", "_load_ts", "_dq_status", "_version_start", "_version_end", "_is_current")
STAGING_TYPES = {"STRING": "string", "INT": "bigint", "BIGINT": "bigint", "DOUBLE": "double",
                 "BOOLEAN": "boolean", "DATE": "date", "TIMESTAMP": "timestamp"}
META_TYPES = {"_record_source": "string", "_load_ts": "timestamp", "_dq_status": "string",
              "_version_start": "timestamp", "_version_end": "timestamp", "_is_current": "boolean"}


@dataclass(frozen=True)
class SchemaNames:
    catalog: str
    mart: str
    common: str
    staging: str
    semantic: str
    security: str

    def schema_for(self, logical: str) -> str:
        return {"mart": self.mart, "common": self.common}[logical]

    def fq(self, table: Table) -> str:
        return f"`{self.catalog}`.`{self.schema_for(table.schema)}`.`{table.name}`"

    def staging_fq(self, name: str) -> str:
        return f"`{self.catalog}`.`{self.staging}`.`{name}`"


def q(name: str) -> str:
    return f"`{name}`"


def staging_type(sql_type: str) -> str:
    return "double" if sql_type.startswith("DECIMAL") else STAGING_TYPES[sql_type]


def _history_select(table: Table) -> list[str]:
    hashed = ", ".join(f"coalesce(CAST({q(c.name)} AS STRING), '')" for c in table.columns)
    return [
        f"sha2(concat_ws('||', {hashed}), 256) AS `hash_diff`",
        "`_record_source` AS `record_source`",
        "concat('ETL-', date_format(`_load_ts`, 'yyyyMMdd')) AS `etl_id`",
        "`_load_ts` AS `load_date_time`",
        "`_dq_status` AS `dq_status`",
        "`_version_start` AS `active_start_date_time`",
        "`_version_end` AS `active_end_date_time`",
        "`_is_current` AS `is_current`",
        "false AS `is_deleted`",
    ]


def _select_list(table: Table) -> str:
    business = [f"CAST({q(c.name)} AS {c.type}) AS {q(c.name)}" for c in table.columns]
    return ",\n  ".join(business + _history_select(table))


def create_tables_sql(contract: Contract, names: SchemaNames) -> str:
    statements = []
    for table in contract.of_kind("table"):
        cols = []
        for col in contract.all_columns(table):
            not_null = " NOT NULL" if col.key in ("surrogate", "business") and table.kind == "table" else ""
            cols.append(f"  {q(col.name)} {col.type}{not_null}")
        cluster = f"\nCLUSTER BY ({', '.join(q(c) for c in table.cluster_by)})" if table.cluster_by else ""
        statements.append(f"CREATE OR REPLACE TABLE {names.fq(table)} (\n" + ",\n".join(cols) + f"\n){cluster};")
    return "\n\n".join(statements) + "\n"


def load_sql(contract: Contract, names: SchemaNames) -> str:
    statements = []
    for table in contract.of_kind("table"):
        target_cols = ", ".join(q(c.name) for c in contract.all_columns(table))
        statements.append(
            f"INSERT OVERWRITE TABLE {names.fq(table)} ({target_cols})\n"
            f"SELECT\n  {_select_list(table)}\nFROM {names.staging_fq(table.name)};"
        )
    return "\n\n".join(statements) + "\n"


def materialized_views_sql(contract: Contract, names: SchemaNames) -> str:
    statements = []
    for table in contract.of_kind("materialized_view"):
        cluster = f"\nCLUSTER BY ({', '.join(q(c) for c in table.cluster_by)})" if table.cluster_by else ""
        statements.append(
            f"CREATE OR REPLACE MATERIALIZED VIEW {names.fq(table)}{cluster}\nAS SELECT\n  {_select_list(table)}\n"
            f"FROM {names.staging_fq(table.name)};"
        )
    return "\n\n".join(statements) + "\n"


def refresh_sql(contract: Contract, names: SchemaNames) -> str:
    return "".join(f"REFRESH MATERIALIZED VIEW {names.fq(t)};\n" for t in contract.of_kind("materialized_view"))


def staging_schema(contract: Contract) -> dict[str, list[list[str]]]:
    """Spark column types for every staging table the generator writes (business columns + load metadata)."""
    out = {}
    for table in contract.tables:
        if table.kind == "view":
            continue
        cols = [[c.name, staging_type(c.type)] for c in table.columns]
        out[table.name] = cols + [[m, META_TYPES[m]] for m in META_COLUMNS]
    return out


def schema_ddl(columns: list[list[str]]) -> str:
    return ", ".join(f"`{name}` {spark_type}" for name, spark_type in columns)


def business_names(table: Table) -> list[str]:
    return [c.name for c in table.columns]


def ref_columns(contract: Contract) -> list[tuple[Table, Column]]:
    return [(t, c) for t in contract.tables for c in t.columns if c.ref]
