"""Business descriptions (contract/descriptions.yml) rendered as Unity Catalog COMMENT statements."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from tools.lib.contract import Contract
from tools.lib.sqlgen import SchemaNames, q

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DESCRIPTIONS = ROOT / "contract" / "descriptions.yml"


class DescriptionsError(ValueError):
    pass


@dataclass(frozen=True)
class Descriptions:
    history: dict[str, str]
    tables: dict[str, dict]

    def table(self, name: str) -> str:
        return self.tables[name]["table"]

    def column(self, table: str, column: str) -> str:
        return self.tables[table].get("columns", {}).get(column) or self.history[column]


def load_descriptions(path: Path = DEFAULT_DESCRIPTIONS, contract: Contract | None = None) -> Descriptions:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    descriptions = Descriptions(history=dict(raw.get("history_columns") or {}), tables=dict(raw.get("tables") or {}))
    if contract is None:
        return descriptions
    problems = []
    history = [c.name for c in contract.history_columns]
    problems += [f"history column {name}: no description" for name in history if not descriptions.history.get(name)]
    known = {t.name: t for t in contract.tables}
    problems += [f"{name} is not in the contract" for name in descriptions.tables if name not in known]
    for table in contract.tables:
        entry = descriptions.tables.get(table.name) or {}
        if not str(entry.get("table") or "").strip():
            problems.append(f"{table.name}: no description")
        columns = entry.get("columns") or {}
        business = [c.name for c in table.columns]
        problems += [f"{table.name}.{c}: no description" for c in business if not str(columns.get(c) or "").strip()]
        problems += [f"{table.name}.{c} is not in the contract" for c in columns if c not in business]
    if problems:
        raise DescriptionsError(f"{path}: " + "; ".join(problems))
    return descriptions


def sql_string(text: str) -> str:
    """A Spark SQL string literal. Doubled quotes would concatenate adjacent literals, so escape with backslashes."""
    return "'" + " ".join(str(text).split()).replace("\\", "\\\\").replace("'", "\\'") + "'"


def comments_sql(contract: Contract, descriptions: Descriptions, names: SchemaNames) -> str:
    statements = []
    for table in contract.tables:
        fq = names.fq(table)
        statements.append(f"COMMENT ON TABLE {fq} IS {sql_string(descriptions.table(table.name))};")
        for column in contract.all_columns(table):
            text = descriptions.column(table.name, column.name)
            statements.append(f"COMMENT ON COLUMN {fq}.{q(column.name)} IS {sql_string(text)};")
    return "\n".join(statements) + "\n"
