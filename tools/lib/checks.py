"""Data checks: integrity checks generated from the contract plus hand-written story checks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from tools.lib.contract import Contract
from tools.lib.sqlgen import SchemaNames, q

MARKER = re.compile(r"^--\s*@check\s+(\S+)\s*$", re.MULTILINE)
NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class CheckError(ValueError):
    pass


@dataclass(frozen=True)
class Check:
    name: str
    sql: str   # returns exactly one row with a BIGINT column `failures`; 0 means pass


def parse_checks(text: str) -> list[Check]:
    parts = MARKER.split(text)
    checks = []
    for name, body in zip(parts[1::2], parts[2::2]):
        sql = body.strip().rstrip(";").strip()
        if not NAME.match(name):
            raise CheckError(f"invalid check name {name!r}")
        if not sql:
            raise CheckError(f"check {name} has no SQL")
        checks.append(Check(name, sql))
    return checks


def generated_checks(contract: Contract, names: SchemaNames) -> list[Check]:
    checks = []
    for table in contract.tables:
        fq = names.fq(table)
        checks.append(Check(f"rows_{table.name}", f"SELECT CASE WHEN count(*) = 0 THEN 1 ELSE 0 END AS failures FROM {fq}"))
        unique = table.unique_key or ((table.surrogate.name,) if table.surrogate else ())
        if unique:
            cols = ", ".join(q(c) for c in unique)
            checks.append(Check(f"unique_{table.name}", f"SELECT count(*) - count(DISTINCT {cols}) AS failures FROM {fq}"))
        if table.business:
            bk = q(table.business.name)
            checks.append(Check(
                f"current_{table.name}",
                f"SELECT count(*) AS failures FROM (SELECT {bk}, count_if(is_current) AS current_rows "
                f"FROM {fq} GROUP BY {bk}) WHERE current_rows <> 1"))
        for col in table.columns:
            if not col.ref:
                continue
            parent = contract.table(col.ref_table)
            key = f"CAST(c.{q(col.name)} AS {col.join_cast})" if col.join_cast else f"c.{q(col.name)}"
            checks.append(Check(
                f"ref_{table.name}_{col.name.lower()}",
                f"SELECT count(*) AS failures FROM {fq} AS c LEFT ANTI JOIN "
                f"(SELECT DISTINCT {q(col.ref_column)} AS k FROM {names.fq(parent)} WHERE is_current) AS p "
                f"ON {key} = p.k WHERE c.{q(col.name)} IS NOT NULL"))
    return checks


def job_sql(checks: list[Check]) -> str:
    """A SQL-task file: each statement raises an error if its check finds violations."""
    seen = set()
    statements = []
    for check in checks:
        if check.name in seen:
            raise CheckError(f"duplicate check name {check.name}")
        seen.add(check.name)
        statements.append(
            f"-- {check.name}\nSELECT CASE WHEN failures > 0 THEN raise_error(concat('Data check {check.name} failed: ', "
            f"CAST(failures AS STRING), ' violation(s)')) ELSE 'ok' END AS {q(check.name)}\n"
            f"FROM (\n{check.sql}\n) AS check_result;")
    return "\n\n".join(statements) + "\n"
