"""Read a bundle target's variables and host from databricks.yml, the single source of names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from tools.lib.sqlgen import SchemaNames

ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NAME_VARIABLES = {"catalog": "catalog", "mart": "mart_schema", "common": "common_schema",
                  "staging": "staging_schema", "semantic": "semantic_schema", "security": "security_schema"}


class BundleConfigError(ValueError):
    pass


@dataclass(frozen=True)
class TargetConfig:
    target: str
    host: str | None
    variables: dict[str, str]

    @property
    def context(self) -> dict[str, str]:
        out = {}
        for key, variable in NAME_VARIABLES.items():
            value = self.variables.get(variable, "")
            if not IDENTIFIER.match(value):
                raise BundleConfigError(f"variable {variable}={value!r} must be a plain SQL identifier")
            out[key] = value
        return out

    @property
    def names(self) -> SchemaNames:
        return SchemaNames(**self.context)


def load_target(target: str, path: Path = ROOT / "databricks.yml") -> TargetConfig:
    raw = yaml.safe_load(Path(path).read_text())
    targets = raw.get("targets") or {}
    if target not in targets:
        raise BundleConfigError(f"unknown bundle target {target!r}; expected one of {sorted(targets)}")
    values = {}
    for key, spec in (raw.get("variables") or {}).items():
        values[key] = str(spec.get("default", "")) if isinstance(spec, dict) else str(spec)
    for key, value in ((targets[target] or {}).get("variables") or {}).items():
        values[key] = str(value)
    unresolved = sorted(k for k, v in values.items() if "${" in v)
    if unresolved:
        raise BundleConfigError(f"variables must be literal values for rendering: {unresolved}")
    host = ((targets[target] or {}).get("workspace") or {}).get("host") or (raw.get("workspace") or {}).get("host")
    return TargetConfig(target=target, host=host.rstrip("/").lower() if host else None, variables=values)
