"""Live validation beyond schema and data: semantics, dashboards, Genie, security, Genie One."""

from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import yaml

from tools.lib.dashboards import dataset_queries
from tools.lib.dbcli import Cli, scrubbed_env
from tools.lib.personas import load_personas, switch
from tools.lib.statements import StatementError, execute
from tools.lib.templates import render_template

ROOT = Path(__file__).resolve().parents[2]
HERO_PROMPTS = ROOT / "genie" / "one" / "hero_prompts.yml"
METRIC_VIEWS = ("resstay_metrics", "occupancy_metrics", "booking_metrics")
PARITY = [
    ("resstay by brand, current month",
     """WITH l AS (SELECT MEASURE(`Latest Stay Date`) AS d FROM {{catalog}}.{{semantic}}.resstay_metrics)
SELECT `Brand` AS k, MEASURE(`Room Revenue`) AS rr, MEASURE(`Room Nights`) AS rn, MEASURE(`ADR`) AS adr
FROM {{catalog}}.{{semantic}}.resstay_metrics
WHERE `Stay Date` BETWEEN (SELECT trunc(d, 'MM') FROM l) AND (SELECT d FROM l) GROUP BY ALL ORDER BY 1""",
     """WITH l AS (SELECT max(bk_date_id) AS d FROM {{catalog}}.{{mart}}.fact_actual_stay WHERE is_current)
SELECT p.brand_cd AS k, SUM(f.room_revenue_amount) AS rr, SUM(f.consumed_room_nights_count) AS rn,
       try_divide(SUM(f.room_revenue_amount), SUM(f.consumed_room_nights_count)) AS adr
FROM {{catalog}}.{{mart}}.fact_actual_stay f JOIN {{catalog}}.{{mart}}.vw_dim_property p USING (bk_property_id)
WHERE f.is_current AND f.bk_date_id BETWEEN concat(substr((SELECT d FROM l), 1, 6), '01') AND (SELECT d FROM l)
GROUP BY ALL ORDER BY 1"""),
    ("occupancy by brand, current month",
     """WITH l AS (SELECT MEASURE(`Latest Date`) AS d FROM {{catalog}}.{{semantic}}.occupancy_metrics)
SELECT `Brand` AS k, MEASURE(`Occupancy`) AS occ, MEASURE(`RevPAR`) AS revpar
FROM {{catalog}}.{{semantic}}.occupancy_metrics
WHERE `Date` BETWEEN (SELECT trunc(d, 'MM') FROM l) AND (SELECT d FROM l) GROUP BY ALL ORDER BY 1""",
     """WITH l AS (SELECT max(bk_date_id) AS d FROM {{catalog}}.{{mart}}.fact_property_statistics),
r AS (SELECT bk_property_id, CAST(bk_date_id AS INT) AS d, SUM(room_revenue_amount) AS rev
      FROM {{catalog}}.{{mart}}.fact_actual_stay WHERE is_current GROUP BY 1, 2)
SELECT p.brand_cd AS k, try_divide(SUM(s.occupied_rooms), SUM(s.available_rooms)) AS occ,
       try_divide(SUM(r.rev), SUM(s.available_rooms)) AS revpar
FROM {{catalog}}.{{mart}}.fact_property_statistics s JOIN {{catalog}}.{{mart}}.vw_dim_property p USING (bk_property_id)
LEFT JOIN r ON r.bk_property_id = s.bk_property_id AND r.d = s.bk_date_id
WHERE s.bk_date_id BETWEEN (SELECT d FROM l) DIV 100 * 100 + 1 AND (SELECT d FROM l) GROUP BY ALL ORDER BY 1"""),
    ("bookings by channel, current month",
     """WITH l AS (SELECT MEASURE(`Latest Booked Date`) AS d FROM {{catalog}}.{{semantic}}.booking_metrics)
SELECT `Channel` AS k, MEASURE(`Reservations`) AS n, MEASURE(`Cancellation Rate`) AS cr
FROM {{catalog}}.{{semantic}}.booking_metrics
WHERE `Booked Date` BETWEEN (SELECT trunc(d, 'MM') FROM l) AND (SELECT d FROM l) GROUP BY ALL ORDER BY 1""",
     """WITH l AS (SELECT max(booked_date) AS d FROM {{catalog}}.{{mart}}.fact_reservation_summary WHERE is_current)
SELECT c.channel_name AS k, COUNT(1) AS n, try_divide(COUNT_IF(r.reservation_cancel_flag), COUNT(1)) AS cr
FROM {{catalog}}.{{mart}}.fact_reservation_summary r JOIN {{catalog}}.{{mart}}.dim_channel c USING (bk_channel_id)
WHERE r.is_current AND r.booked_date BETWEEN trunc((SELECT d FROM l), 'MM') AND (SELECT d FROM l)
GROUP BY ALL ORDER BY 1"""),
]


def _status(results: list[dict]) -> dict:
    return {"status": "pass" if all(r["status"] == "pass" for r in results) else "fail", "checks": results}


def _run_queries(cli: Cli, warehouse_id: str, items: list[tuple[str, str, dict]], workers: int = 6):
    def one(item):
        name, sql, params = item
        try:
            result = execute(cli, warehouse_id, sql, parameters=params or None)
            return name, result, None
        except StatementError as error:
            return name, None, error
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, items))


def _query_result(name, result, error, extra_problem: str | None = None) -> dict:
    if error is not None:
        return {"name": name, "status": "error", "error": str(error)[:800], "statement_id": error.statement_id}
    if not result.rows:
        return {"name": name, "status": "fail", "failures": "no rows", "statement_id": result.statement_id}
    if extra_problem:
        return {"name": name, "status": "fail", "failures": extra_problem, "statement_id": result.statement_id}
    return {"name": name, "status": "pass", "rows": len(result.rows), "statement_id": result.statement_id}


def check_semantics(cli: Cli, warehouse_id: str, contract, context: dict) -> dict:
    """Every contract table and column carries a comment; metric views equal direct SQL within 0.01."""
    n = context
    results = []
    sql = (f"SELECT table_schema, table_name, column_name FROM `{n['catalog']}`.information_schema.columns "
           f"WHERE table_schema IN ('{n['mart']}', '{n['common']}') AND (comment IS NULL OR trim(comment) = '')")
    try:
        uncommented = execute(cli, warehouse_id, sql)
        wanted = {(n[t.schema], t.name) for t in contract.tables}
        missing = [f"{r[1]}.{r[2]}" for r in uncommented.rows if (r[0], r[1]) in wanted]
        results.append({"name": "every contract column is commented", "status": "fail" if missing else "pass",
                        "statement_id": uncommented.statement_id, **({"failures": missing[:20]} if missing else {})})
    except StatementError as error:
        results.append({"name": "every contract column is commented", "status": "error", "error": str(error)})
    certified = (f"SELECT table_name FROM `{n['catalog']}`.information_schema.table_tags WHERE schema_name = "
                 f"'{n['semantic']}' AND tag_name = 'system.certification_status' AND tag_value = 'certified'")
    try:
        tagged = {r[0] for r in execute(cli, warehouse_id, certified).rows}
        missing = sorted(set(METRIC_VIEWS) - tagged)
        results.append({"name": "metric views are certified", "status": "fail" if missing else "pass",
                        **({"failures": missing} if missing else {})})
    except StatementError as error:
        results.append({"name": "metric views are certified", "status": "error", "error": str(error)})
    pairs = [(f"{name} (metric view)", render_template(mv, n), None) for name, mv, _ in PARITY]
    pairs += [(f"{name} (direct)", render_template(direct, n), None) for name, _, direct in PARITY]
    ran = {name: (result, error) for name, result, error in _run_queries(cli, warehouse_id, pairs)}
    for name, _, _ in PARITY:
        (mv, mv_error), (direct, direct_error) = ran[f"{name} (metric view)"], ran[f"{name} (direct)"]
        if mv_error or direct_error:
            results.append({"name": f"parity: {name}", "status": "error", "error": str(mv_error or direct_error)})
            continue
        diffs = [f"{a[0]}: {x} vs {y}" for a, b in zip(mv.rows, direct.rows) for x, y in zip(a[1:], b[1:])
                 if abs(float(x or 0) - float(y or 0)) > 0.01]
        if len(mv.rows) != len(direct.rows) or [r[0] for r in mv.rows] != [r[0] for r in direct.rows]:
            diffs.insert(0, f"groups differ: {[r[0] for r in mv.rows]} vs {[r[0] for r in direct.rows]}")
        results.append({"name": f"parity: {name}", "status": "fail" if diffs or not mv.rows else "pass",
                        **({"failures": diffs[:10]} if diffs else {})})
    return _status(results)


def check_dashboards(cli: Cli, warehouse_id: str, build_dir: Path) -> dict:
    """Every dataset of every rendered dashboard runs with its default parameters and returns widget columns."""
    items, used = [], {}
    for path in sorted(Path(build_dir, "dashboards").glob("*.lvdash.json")):
        dashboard = json.loads(path.read_text())
        key = path.name.split(".")[0]
        for page in dashboard["pages"]:
            for item in page["layout"]:
                for q in item["widget"].get("queries", []):
                    columns = used.setdefault(f"{key}:{q['query']['datasetName']}", set())
                    for f in q["query"].get("fields", []):
                        columns.update(re.findall(r"^`([^`]+)`$", f["expression"]))
        items += [(f"{key}:{name}", sql, params) for name, sql, params in dataset_queries(dashboard)]
    results = []
    for name, result, error in _run_queries(cli, warehouse_id, items):
        missing = sorted(used.get(name, set()) - set(result.columns)) if result else []
        results.append(_query_result(name, result, error, f"missing columns {missing}" if missing else None))
    return _status(results)


def check_genie(cli: Cli, warehouse_id: str, build_dir: Path) -> dict:
    """Every example and benchmark SQL in the rendered Genie spaces executes and returns rows."""
    items = []
    for path in sorted(Path(build_dir, "genie").glob("*.geniespace.json")):
        space, key = json.loads(path.read_text()), path.name.split(".")[0]
        items += [(f"{key} example: {x['question'][0]}", "".join(x["sql"]), None)
                  for x in space["instructions"]["example_question_sqls"]]
        items += [(f"{key} benchmark: {x['question'][0]}", "".join(x["answer"][0]["content"]), None)
                  for x in space["benchmarks"]["questions"]]
    return _status([_query_result(*r) for r in _run_queries(cli, warehouse_id, items)])


def check_security(run: Callable[[str], list], context: dict) -> dict:
    """Each persona sees exactly its scope's hotels; corporate is always restored, even after a failure."""
    personas = load_personas()
    results = []
    try:
        for key in ("dm", "rvp", "dvp", "none"):
            outcome = switch(run, context, personas[key])
            ok = outcome["visible_hotels"] == outcome["expected_hotels"]
            results.append({"name": f"persona {key}", "status": "pass" if ok else "fail", **outcome})
    finally:
        outcome = switch(run, context, personas["corporate"])
        ok = outcome["visible_hotels"] == outcome["expected_hotels"] > 0
        results.append({"name": "persona corporate (restored)", "status": "pass" if ok else "fail", **outcome})
    return _status(results)


PAGE_ID = re.compile(r"(?:knowledge_page\.|/discover/pages/)([0-9a-f-]{36})")
TABLE_LINK = re.compile(r"/explore/data/([^/?#\s)]+)/")


def evaluate_answer(answer: dict, expected_values: list[str], expected_pages: set[str], our_pages: set[str],
                    our_spaces: set[str], catalog: str) -> tuple[list[str], list[str]]:
    """(out-of-scope problems, review notes) for one Genie One answer."""
    text = answer.get("text") or ""
    blob = text + " " + json.dumps(answer.get("tool_calls") or [])
    cited = set(PAGE_ID.findall(blob))
    hard = [f"cites a Page outside the ESA domains: {p}" for p in sorted(cited - our_pages)]
    hard += [f"links a catalog other than {catalog}: {c}" for c in sorted(set(TABLE_LINK.findall(text)) - {catalog})]
    for call in answer.get("tool_calls") or []:
        arguments = call.get("arguments") or {}
        if isinstance(arguments, str):                 # the CLI returns tool arguments as a JSON string
            try:
                arguments = json.loads(arguments)
            except ValueError:
                arguments = {}
        space = str(arguments.get("space_id") or "")
        if call.get("name") == "ask_genie_space" and space and space not in our_spaces:
            hard.append(f"asked a Genie space that is not an ESA agent: {space}")
    review = []
    if str(answer.get("status") or "completed").lower() != "completed":
        review.append(f"status {answer.get('status')}")
    review += [f"does not cite the expected Page {p}" for p in sorted(expected_pages - cited)]
    review += [f"does not mention {v!r}" for v in expected_values if v.lower() not in text.lower()]
    return hard, review


def check_genie_one(cli: Cli, warehouse_id: str, context: dict, records: dict, spaces: set[str],
                    session: str, prompts_file: Path = HERO_PROMPTS, ask=None) -> dict:
    """Replay the hero prompts. Out-of-scope sources fail; missing facts or citations need a human review."""
    prompts = (yaml.safe_load(Path(prompts_file).read_text()) or {}).get("prompts") or []
    our_pages = {str(p["name"]).rsplit("/", 1)[-1]: slug for slug, p in (records.get("pages") or {}).items()}
    ask = ask or (lambda question, session_id: genie_ask(cli, question, session_id))
    results = []
    for prompt in prompts:
        question = " ".join(render_template(prompt["question"], context).split())
        expected = [str(r[0]) for r in execute(cli, warehouse_id, render_template(prompt["expect_sql"], context)).rows]
        page_ids = {pid for pid, slug in our_pages.items() if slug in set(prompt.get("expect_pages") or [])}
        try:
            answer = ask(question, f"{session}-{prompt.get('session', prompt['key'])}")
            hard, review = evaluate_answer(answer, expected, page_ids, set(our_pages), spaces, context["catalog"])
        except Exception as error:  # noqa: BLE001 - one bad answer must not hide the other prompts' results
            answer, hard, review = {}, [], [f"could not evaluate the answer: {error}"]
        status = "fail" if hard else ("review" if review else "pass")
        results.append({"name": prompt["key"], "status": status, "question": question,
                        "conversation_id": answer.get("conversation_id"), "problems": hard + review,
                        "answer": (answer.get("text") or "")[:4000]})
    statuses = {r["status"] for r in results}
    return {"status": "fail" if "fail" in statuses else ("review" if "review" in statuses else "pass"),
            "checks": results}


def genie_ask(cli: Cli, question: str, session: str) -> dict:
    proc = subprocess.run(["databricks", "genie", "ask", "-s", session, question, "--profile", cli.profile,
                           "--output", "json"], env=scrubbed_env(), capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        return {"status": "ERROR", "text": proc.stderr[-1000:]}
    return json.loads(proc.stdout)
