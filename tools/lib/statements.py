"""Run SQL through the Statement Execution API with the CLI wrapper (used by validation)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from tools.lib.dbcli import Cli

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELED", "CLOSED"}


class StatementError(RuntimeError):
    def __init__(self, statement_id: str | None, state: str, message: str):
        self.statement_id, self.state = statement_id, state
        super().__init__(f"statement {statement_id} {state}: {message}")


@dataclass(frozen=True)
class StatementResult:
    statement_id: str
    columns: list[str]
    rows: list[list[str | None]]

    def records(self) -> list[dict[str, str | None]]:
        return [dict(zip(self.columns, row)) for row in self.rows]


def execute(cli: Cli, warehouse_id: str, sql: str, *, timeout_s: int = 1800, poll_s: float = 3.0,
            sleep: Callable[[float], None] = time.sleep, parameters: dict | None = None) -> StatementResult:
    body = {"warehouse_id": warehouse_id, "statement": sql, "wait_timeout": "30s",
            "on_wait_timeout": "CONTINUE", "format": "JSON_ARRAY", "disposition": "INLINE"}
    if parameters:
        body["parameters"] = [{"name": k, "value": str(v)} for k, v in parameters.items()]
    resp = cli.api("post", "/api/2.0/sql/statements", body)
    statement_id = resp.get("statement_id")
    waited = 0.0
    while resp["status"]["state"] not in TERMINAL:
        if waited >= timeout_s:
            cli.api("post", f"/api/2.0/sql/statements/{statement_id}/cancel")
            raise StatementError(statement_id, "TIMEOUT", f"no result after {timeout_s}s")
        sleep(poll_s)
        waited += poll_s
        resp = cli.api("get", f"/api/2.0/sql/statements/{statement_id}")
    state = resp["status"]["state"]
    if state != "SUCCEEDED":
        raise StatementError(statement_id, state, resp["status"].get("error", {}).get("message", ""))
    # DDL succeeds without a result schema.
    columns = [c["name"] for c in ((resp.get("manifest") or {}).get("schema") or {}).get("columns", [])]
    result = resp.get("result") or {}
    rows = list(result.get("data_array") or [])
    while result.get("next_chunk_index") is not None:
        result = cli.api("get", f"/api/2.0/sql/statements/{statement_id}/result/chunks/{result['next_chunk_index']}")
        rows.extend(result.get("data_array") or [])
    return StatementResult(statement_id, columns, rows)
