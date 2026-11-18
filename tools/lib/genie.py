"""Genie agent specs (genie/*.yml) rendered into serialized Genie spaces (version 2) for the bundle's genie_spaces.

A spec names its sources logically (semantic.<metric view>, mart.<table>), the columns that get value lookup, the text
instructions, sample questions, example SQL, and benchmarks. IDs are derived from the content, so re-rendering an
unchanged spec yields an identical space and a bundle deploy changes nothing.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from tools.lib.contract import Contract
from tools.lib.templates import TemplateError, render_template

ROOT = Path(__file__).resolve().parents[2]
GENIE_DIR = ROOT / "genie"
METRIC_VIEWS_SQL = ROOT / "src" / "sql" / "50_metric_views.sql.tmpl"
FIELDS = {"key", "metric_views", "tables", "match", "hide", "join_specs", "instructions", "sample_questions",
          "examples", "benchmarks"}
SURROGATE = re.compile(r"^(dim|fact)_\w+_id$")
RELATIONSHIPS = {"MANY_TO_ONE", "ONE_TO_MANY", "ONE_TO_ONE", "MANY_TO_MANY"}
METRIC_VIEW = re.compile(r"CREATE OR REPLACE VIEW `\{\{catalog\}\}`\.`\{\{semantic\}\}`\.`(\w+)`\s+WITH METRICS\s+"
                         r"LANGUAGE YAML\s+AS \$\$\n(.*?)\n\$\$;", re.S)


class GenieError(ValueError):
    pass


@dataclass(frozen=True)
class SpaceSpec:
    key: str
    metric_views: tuple[str, ...]
    tables: tuple[str, ...]
    match: dict
    hide: dict
    join_specs: tuple[dict, ...]
    instructions: str
    sample_questions: tuple[str, ...]
    examples: tuple[dict, ...]
    benchmarks: tuple[dict, ...]


def load_space(path: Path) -> SpaceSpec:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if set(raw) - FIELDS:
        raise GenieError(f"{path}: unknown fields {sorted(set(raw) - FIELDS)}")
    return SpaceSpec(key=str(raw.get("key")), metric_views=tuple(raw.get("metric_views") or ()),
                     tables=tuple(raw.get("tables") or ()), match=dict(raw.get("match") or {}),
                     hide=dict(raw.get("hide") or {}),
                     join_specs=tuple(raw.get("join_specs") or ()), instructions=str(raw.get("instructions") or ""),
                     sample_questions=tuple(raw.get("sample_questions") or ()),
                     examples=tuple(raw.get("examples") or ()), benchmarks=tuple(raw.get("benchmarks") or ()))


def metric_view_dimensions(path: Path = METRIC_VIEWS_SQL) -> dict[str, set[str]]:
    """Dimension names of every metric view in the template, for checking value-lookup columns."""
    out = {}
    for name, body in METRIC_VIEW.findall(path.read_text()):
        spec = yaml.safe_load(re.sub(r"\{\{\s*(\w+)\s*\}\}", r"\1", body))
        out[name] = {d["name"] for d in spec.get("dimensions") or []}
    return out


def _id(space: str, kind: str, text: str) -> str:
    return hashlib.md5(f"{space}|{kind}|{text}".encode()).hexdigest()


def _lines(text: str) -> list[str]:
    return str(text).strip("\n").splitlines(keepends=True)


def serialized_space(spec: SpaceSpec, names: dict[str, str], contract: Contract) -> dict:
    problems: list[str] = []
    tables = {t.name: t for t in contract.tables}
    dimensions = metric_view_dimensions()

    def render(text: str, where: str) -> str:
        try:
            return render_template(str(text), names)
        except TemplateError as error:
            problems.append(f"{where}: {error}")
            return str(text)

    def fq(ref: str) -> str:
        schema, _, name = ref.partition(".")
        if schema == "semantic":
            if name not in dimensions:
                problems.append(f"{ref} is not a metric view in {METRIC_VIEWS_SQL.name}")
        elif tables.get(name) is None or tables[name].schema != schema:
            problems.append(f"{ref} is not a contract object")
        return f"{names['catalog']}.{names.get(schema, schema)}.{name}"

    def matched(ref: str, known: set[str]) -> list[str]:
        columns = list(spec.match.get(ref) or [])
        problems.extend(f"{ref}: unknown column {c!r} in match" for c in columns if c not in known)
        return columns

    metric_views = []
    for ref in spec.metric_views:
        entry = {"identifier": fq(ref)}
        columns = matched(ref, dimensions.get(ref.partition(".")[2], set()))
        if columns:
            entry["column_configs"] = sorted(({"column_name": c, "enable_entity_matching": True,
                                               "enable_format_assistance": True} for c in columns),
                                             key=lambda c: c["column_name"])
        metric_views.append(entry)

    data_tables = []
    for ref in spec.tables:
        entry = {"identifier": fq(ref)}
        table = tables.get(ref.partition(".")[2])
        if table is not None:
            columns = contract.all_columns(table)
            match = set(matched(ref, {c.name for c in columns}))
            hidden = {c.name for c in contract.history_columns} | {
                c.name for c in columns if c.key == "surrogate" or SURROGATE.match(c.name)}
            extra = set(spec.hide.get(ref) or [])
            problems.extend(f"{ref}: unknown column {c!r} in hide" for c in sorted(extra - {c.name for c in columns}))
            hidden |= extra
            configs = [{"column_name": c, "enable_entity_matching": True, "enable_format_assistance": True}
                       for c in match] + [{"column_name": c, "exclude": True} for c in hidden - match]
            entry["column_configs"] = sorted(configs, key=lambda c: c["column_name"])
        data_tables.append(entry)
    unknown_match = (set(spec.match) | set(spec.hide)) - set(spec.metric_views) - set(spec.tables)
    problems.extend(f"match names {ref}, which is not a source" for ref in sorted(unknown_match))

    joins = []
    for join in spec.join_specs:
        relationship = str(join.get("relationship", ""))
        if relationship not in RELATIONSHIPS:
            problems.append(f"join {join.get('left')} -> {join.get('right')}: relationship must be one of "
                            f"{sorted(RELATIONSHIPS)}")
        sql = render(join.get("sql", ""), "join")
        joins.append({"id": _id(spec.key, "join", sql),
                      "left": {"identifier": fq(join["left"]), "alias": join["left"].partition(".")[2]},
                      "right": {"identifier": fq(join["right"]), "alias": join["right"].partition(".")[2]},
                      "sql": [sql, f"--rt=FROM_RELATIONSHIP_TYPE_{relationship}--"]})

    questions = [str(x["question"]) for x in spec.examples + spec.benchmarks]
    problems.extend(f"duplicate question {q!r}" for q in sorted({q for q in questions if questions.count(q) > 1}))
    examples = [{"id": _id(spec.key, "example", x["question"]), "question": [x["question"]],
                 "sql": _lines(render(x["sql"], x["question"]))} for x in spec.examples]
    benchmarks = [{"id": _id(spec.key, "benchmark", x["question"]), "question": [x["question"]],
                   "answer": [{"format": "SQL", "content": _lines(render(x["sql"], x["question"]))}]}
                  for x in spec.benchmarks]
    samples = [{"id": _id(spec.key, "sample", q), "question": [q]} for q in spec.sample_questions]
    if not spec.instructions.strip():
        problems.append("instructions are required")
    if problems:
        raise GenieError(f"genie space {spec.key}: " + "; ".join(problems))

    by_id = lambda items: sorted(items, key=lambda x: x["id"])  # noqa: E731
    instructions = {"text_instructions": [{"id": _id(spec.key, "text", "instructions"),
                                           "content": _lines(spec.instructions)}],
                    "example_question_sqls": by_id(examples)}
    if joins:
        instructions["join_specs"] = by_id(joins)
    data_sources = {}
    if data_tables:
        data_sources["tables"] = sorted(data_tables, key=lambda t: t["identifier"])
    if metric_views:
        data_sources["metric_views"] = sorted(metric_views, key=lambda t: t["identifier"])
    return {"version": 2, "config": {"sample_questions": by_id(samples)}, "data_sources": data_sources,
            "instructions": instructions, "benchmarks": {"questions": by_id(benchmarks)}}
