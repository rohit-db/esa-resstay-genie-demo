"""Load and validate contract/dev_gold_mart.yml, the single source of table structure."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "contract" / "dev_gold_mart.yml"
TYPE_PATTERN = re.compile(r"^(STRING|INT|BIGINT|DOUBLE|BOOLEAN|DATE|TIMESTAMP|DECIMAL\(\d{1,2},\d{1,2}\))$")
NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
KINDS = {"table", "materialized_view", "view"}
SCHEMAS = {"mart", "common"}
KEYS = {None, "surrogate", "business"}


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    key: str | None = None
    ref: str | None = None
    join_cast: str | None = None

    @property
    def ref_table(self) -> str | None:
        return self.ref.split(".", 1)[0] if self.ref else None

    @property
    def ref_column(self) -> str | None:
        return self.ref.split(".", 1)[1] if self.ref else None


@dataclass(frozen=True)
class Table:
    name: str
    schema: str
    kind: str
    source: str
    grain: str
    columns: tuple[Column, ...]
    cluster_by: tuple[str, ...] = ()
    unique_key: tuple[str, ...] = ()

    def column(self, name: str) -> Column:
        for col in self.columns:
            if col.name == name:
                return col
        raise KeyError(f"{self.name}.{name}")

    @property
    def surrogate(self) -> Column | None:
        return next((c for c in self.columns if c.key == "surrogate"), None)

    @property
    def business(self) -> Column | None:
        return next((c for c in self.columns if c.key == "business"), None)


@dataclass(frozen=True)
class Contract:
    history_columns: tuple[Column, ...]
    tables: tuple[Table, ...]

    def table(self, name: str) -> Table:
        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(name)

    def of_kind(self, kind: str) -> tuple[Table, ...]:
        return tuple(t for t in self.tables if t.kind == kind)

    def all_columns(self, table: Table) -> tuple[Column, ...]:
        return table.columns + self.history_columns


def _column(raw: dict, where: str, problems: list[str]) -> Column:
    unknown = set(raw) - {"name", "type", "key", "ref", "join_cast"}
    if unknown:
        problems.append(f"{where}: unknown fields {sorted(unknown)}")
    col = Column(name=str(raw.get("name", "")), type=str(raw.get("type", "")), key=raw.get("key"),
                 ref=raw.get("ref"), join_cast=raw.get("join_cast"))
    if not NAME_PATTERN.match(col.name):
        problems.append(f"{where}: invalid column name {col.name!r}")
    if not TYPE_PATTERN.match(col.type):
        problems.append(f"{where}.{col.name}: invalid type {col.type!r}")
    if col.key not in KEYS:
        problems.append(f"{where}.{col.name}: invalid key {col.key!r}")
    if col.join_cast and not TYPE_PATTERN.match(col.join_cast):
        problems.append(f"{where}.{col.name}: invalid join_cast {col.join_cast!r}")
    return col


def load_contract(path: Path = DEFAULT_CONTRACT) -> Contract:
    raw = yaml.safe_load(Path(path).read_text())
    problems: list[str] = []
    if raw.get("version") != 1:
        problems.append("version must be 1")
    history = tuple(_column(c, "history_columns", problems) for c in raw.get("history_columns", []))
    tables = []
    for t in raw.get("tables", []):
        name = str(t.get("name", ""))
        cols = tuple(_column(c, name, problems) for c in t.get("columns", []))
        table = Table(name=name, schema=t.get("schema"), kind=t.get("kind"), source=t.get("source"),
                      grain=str(t.get("grain", "")).strip(), columns=cols,
                      cluster_by=tuple(t.get("cluster_by", [])), unique_key=tuple(t.get("unique_key", [])))
        tables.append(table)
        if not NAME_PATTERN.match(name):
            problems.append(f"invalid table name {name!r}")
        if table.schema not in SCHEMAS:
            problems.append(f"{name}: schema must be one of {sorted(SCHEMAS)}")
        if table.kind not in KINDS:
            problems.append(f"{name}: kind must be one of {sorted(KINDS)}")
        if table.source not in {"exact", "derived"}:
            problems.append(f"{name}: source must be exact or derived")
        if not table.grain:
            problems.append(f"{name}: grain is required")
        names = [c.name.lower() for c in cols] + [c.name.lower() for c in history]
        if len(names) != len(set(names)):
            problems.append(f"{name}: duplicate column names (history columns are appended automatically)")
        for key in table.cluster_by + table.unique_key:
            if key not in {c.name for c in cols}:
                problems.append(f"{name}: cluster_by/unique_key column {key!r} is not a column")
        if sum(c.key == "surrogate" for c in cols) > 1 or sum(c.key == "business" for c in cols) > 1:
            problems.append(f"{name}: at most one surrogate and one business key")
    if len({t.name for t in tables}) != len(tables):
        problems.append("duplicate table names")
    contract = Contract(history_columns=history, tables=tuple(tables))
    for table in tables:
        for col in table.columns:
            if not col.ref:
                continue
            try:
                target = contract.table(col.ref_table).column(col.ref_column)
            except KeyError:
                problems.append(f"{table.name}.{col.name}: ref {col.ref} does not exist")
                continue
            if target.key != "business":
                problems.append(f"{table.name}.{col.name}: ref {col.ref} must point at a business key")
            expected = col.join_cast or col.type
            if expected != target.type:
                problems.append(f"{table.name}.{col.name}: type {col.type} cannot join {col.ref} ({target.type}); set join_cast")
    if problems:
        raise ContractError("Contract problems:\n  " + "\n  ".join(problems))
    return contract
