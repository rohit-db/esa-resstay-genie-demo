"""Demo personas (security/personas.yml): rewrite the operator's own entitlement row and check what it can see."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from tools.lib.comments import sql_string

ROOT = Path(__file__).resolve().parents[2]
PERSONAS_FILE = ROOT / "security" / "personas.yml"
LEVELS = {"CORPORATE": None, "DIVISION": "division_name", "REGION": "region_name", "DISTRICT": "district_name",
          "NONE": None}
Run = Callable[[str], list[list]]


class PersonaError(RuntimeError):
    pass


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    scope_level: str


def load_personas(path: Path = PERSONAS_FILE) -> dict[str, Persona]:
    raw = (yaml.safe_load(Path(path).read_text()) or {}).get("personas") or {}
    personas = {k: Persona(k, str(v.get("label", k)), str(v.get("scope_level"))) for k, v in raw.items()}
    bad = [p.key for p in personas.values() if p.scope_level not in LEVELS]
    if bad or "corporate" not in personas:
        raise PersonaError(f"{path}: invalid personas {bad or ''}; a 'corporate' persona is required")
    return personas


def _t(names: dict, schema: str, table: str) -> str:
    return f"`{names['catalog']}`.`{names[schema]}`.`{table}`"


def resolve_sql(names: dict) -> str:
    """The district with the most hotels under an in-progress full renovation, from unfiltered tables only."""
    return f"""WITH reno AS (
  SELECT b.bk_property_id
  FROM {_t(names, 'staging', 'fact_property_renovation')} AS b
  JOIN {_t(names, 'staging', 'dim_property_renovation')} AS r
    ON r.bk_property_renovation_id = b.bk_property_renovation_id AND r._is_current
  WHERE b._is_current AND b.member_flag AND r.renovation_type = 'Full Renovation' AND r.renovation_status = 'In Progress'
)
SELECT s.division_name, s.region_name, s.district_name, count(*) AS hotels
FROM {_t(names, 'security', 'property_scope_lookup')} AS s JOIN reno USING (bk_property_id)
GROUP BY ALL ORDER BY hotels DESC, s.district_name LIMIT 1"""


def expected_sql(names: dict, persona: Persona, scope_value: str | None) -> str:
    if persona.scope_level == "NONE":
        return "SELECT 0 AS hotels"
    where = "" if persona.scope_level == "CORPORATE" else \
        f" WHERE {LEVELS[persona.scope_level]} = {sql_string(scope_value)}"
    return f"SELECT count(*) AS hotels FROM {_t(names, 'security', 'property_scope_lookup')}{where}"


def set_sql(names: dict, persona: Persona, scope_value: str | None) -> str:
    table = _t(names, "security", "property_entitlements")
    if persona.scope_level == "NONE":
        return f"DELETE FROM {table} WHERE principal_type = 'USER' AND lower(principal) = lower(current_user())"
    value = "NULL" if scope_value is None else sql_string(scope_value)
    return f"""MERGE INTO {table} AS e
USING (SELECT current_user() AS principal) AS s
ON e.principal_type = 'USER' AND lower(e.principal) = lower(current_user())
WHEN MATCHED THEN UPDATE SET scope_level = '{persona.scope_level}', scope_value = {value},
  persona_label = '{persona.key}'
WHEN NOT MATCHED THEN INSERT (principal, principal_type, scope_level, scope_value, persona_label)
  VALUES (s.principal, 'USER', '{persona.scope_level}', {value}, '{persona.key}')"""


def visible_sql(names: dict) -> str:
    return f"SELECT count(DISTINCT bk_property_id) AS visible_hotels FROM {_t(names, 'mart', 'vw_dim_property')}"


def duplicates_sql(names: dict) -> str:
    return (f"SELECT lower(principal) AS duplicates, count(*) AS n FROM {_t(names, 'security', 'property_entitlements')} "
            "GROUP BY lower(principal) HAVING count(*) > 1")


def switch(run: Run, names: dict, persona: Persona) -> dict:
    """Point the operator's entitlement at the persona's scope and report expected versus visible hotels."""
    duplicates = run(duplicates_sql(names))
    if duplicates:
        raise PersonaError(f"duplicate entitlement rows (case-insensitive) for {[d[0] for d in duplicates]}")
    scope_value = None
    if LEVELS[persona.scope_level]:
        found = run(resolve_sql(names))
        if not found:
            raise PersonaError("no district has a full renovation in progress; check the story window")
        division, region, district = found[0][:3]
        scope_value = {"DIVISION": division, "REGION": region, "DISTRICT": district}[persona.scope_level]
    run(set_sql(names, persona, scope_value))
    expected = int(run(expected_sql(names, persona, scope_value))[0][0])
    visible = int(run(visible_sql(names))[0][0])
    return {"persona": persona.key, "scope_level": persona.scope_level, "scope_value": scope_value,
            "expected_hotels": expected, "visible_hotels": visible}
