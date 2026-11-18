from tools.lib.live_checks import check_genie_one, check_security, evaluate_answer

OURS = {"5261c919-d62f-4b45-a606-6d4268d57fcd"}
ANSWER = {"status": "completed",  # the CLI reports lowercase
           "text": "ADR is up for ESAS and ESAP. [ADR](https://h/one/discover/pages/5261c919-d62f-4b45-a606-6d4268d57fcd) "
          "[mv](https://h/explore/data/dev_gold/semantic/resstay_metrics?x=1)",
          "tool_calls": [{"name": "ask_genie_space", "arguments": '{"space_id": "s1", "question": "q"}'}]}  # live: a string


def test_in_scope_answers_pass_and_gaps_need_review():
    hard, review = evaluate_answer(ANSWER, ["ESAS", "ESAP"], OURS, OURS, {"s1"}, "dev_gold")
    assert hard == [] and review == []
    hard, review = evaluate_answer(ANSWER, ["ESSS"], OURS, OURS, {"s1"}, "dev_gold")
    assert hard == [] and review == ["does not mention 'ESSS'"]


def test_out_of_scope_sources_fail():
    other = dict(ANSWER, text=ANSWER["text"] + " https://h/one/discover/pages/00000000-0000-0000-0000-000000000000 "
                 "https://h/explore/data/main/sales/orders/")
    hard, _ = evaluate_answer(other, [], set(), OURS, {"s2"}, "dev_gold")
    assert any("outside the ESA domains" in h for h in hard)
    assert any("other than dev_gold: main" in h for h in hard)
    assert any("not an ESA agent: s1" in h for h in hard)


def test_security_restores_corporate_even_when_a_persona_fails():
    calls = []

    def run(sql):
        calls.append(sql)
        if "duplicates" in sql:
            return []
        if sql.startswith("WITH reno"):
            return [["South", "Texas", "Texas District 2", "4"]]
        if sql.startswith("SELECT count(*) AS hotels"):
            return [["600"]] if "WHERE" not in sql else [["10"]]
        if sql.startswith("SELECT 0"):
            return [["0"]]
        if "visible_hotels" in sql:
            last_set = [c for c in calls if c.startswith(("MERGE", "DELETE"))][-1]
            return [["600"]] if "'CORPORATE'" in last_set else [["10"]]
        return []
    report = check_security(run, {"catalog": "dev_gold", "mart": "mart", "staging": "staging", "security": "security"})
    by_name = {c["name"]: c["status"] for c in report["checks"]}
    assert by_name["persona dm"] == "pass" and by_name["persona none"] == "fail"
    assert by_name["persona corporate (restored)"] == "pass" and report["status"] == "fail"
    assert "'CORPORATE'" in [c for c in calls if c.startswith(("MERGE", "DELETE"))][-1]


def test_genie_one_replays_prompts_in_one_session(fake_cli, tmp_path):
    prompts = tmp_path / "p.yml"
    prompts.write_text("prompts:\n"
                       "  - key: a\n    session: hero\n    question: 'In {{catalog}}: ADR?'\n"
                       "    expect_pages: [resstay--adr]\n    expect_sql: SELECT 1\n"
                       "  - key: b\n    session: hero\n    question: Next?\n    expect_pages: []\n    expect_sql: SELECT 1\n")
    cli = fake_cli({("post", "/api/2.0/sql/statements"): {"statement_id": "s", "status": {"state": "SUCCEEDED"},
                                                          "manifest": {"schema": {"columns": [{"name": "v"}]}},
                                                          "result": {"data_array": [["ESAS"]]}}})
    seen = []
    ask = lambda q, s: seen.append((q, s)) or ANSWER
    records = {"pages": {"resstay--adr": {"name": "pages/5261c919-d62f-4b45-a606-6d4268d57fcd"}}}
    report = check_genie_one(cli, "wh", {"catalog": "dev_gold"}, records, {"s1"}, "run1", prompts, ask=ask)
    assert report["status"] == "pass" and seen == [("In dev_gold: ADR?", "run1-hero"), ("Next?", "run1-hero")]
