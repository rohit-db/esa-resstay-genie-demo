import pytest

from tools.lib.statements import StatementError, execute


def test_polls_until_done_and_reads_every_chunk(fake_cli):
    responses = iter([
        {"statement_id": "s1", "status": {"state": "RUNNING"}},
        {"statement_id": "s1", "status": {"state": "SUCCEEDED"},
         "manifest": {"schema": {"columns": [{"name": "failures"}]}},
         "result": {"data_array": [["0"]], "next_chunk_index": 1}},
        {"data_array": [["3"]]},
    ])
    cli = fake_cli({("post", "/api/2.0/sql/statements"): lambda a: next(responses),
                    ("get",): lambda a: next(responses)})
    result = execute(cli, "wh", "SELECT 1", sleep=lambda s: None)
    assert result.statement_id == "s1" and result.records() == [{"failures": "0"}, {"failures": "3"}]


def test_failed_statement_raises_with_its_id(fake_cli):
    cli = fake_cli({("post",): {"statement_id": "s2", "status": {"state": "FAILED", "error": {"message": "boom"}}}})
    with pytest.raises(StatementError, match="s2 FAILED: boom"):
        execute(cli, "wh", "SELECT 1")


def test_timeout_cancels_the_statement(fake_cli):
    cli = fake_cli({("post", "/api/2.0/sql/statements"): {"statement_id": "s3", "status": {"state": "PENDING"}},
                    ("get",): {"statement_id": "s3", "status": {"state": "PENDING"}},
                    ("post", "/api/2.0/sql/statements/s3/cancel"): {}})
    with pytest.raises(StatementError, match="TIMEOUT"):
        execute(cli, "wh", "SELECT 1", timeout_s=6, poll_s=3, sleep=lambda s: None)
    assert ("api", ("post", "/api/2.0/sql/statements/s3/cancel", "")) in cli.calls


def test_ddl_results_without_a_schema_return_no_rows(fake_cli):
    cli = fake_cli({("post", "/api/2.0/sql/statements"): {"statement_id": "s1", "status": {"state": "SUCCEEDED"},
                                                          "manifest": {"total_row_count": 0}}})
    result = execute(cli, "wh", "CREATE OR REPLACE VIEW v AS SELECT 1")
    assert (result.statement_id, result.columns, result.rows) == ("s1", [], [])


def test_named_parameters_are_sent_as_strings(fake_cli):
    sent = {}

    def post(args):
        sent.update(__import__("json").loads(args[2]))
        return {"statement_id": "s2", "status": {"state": "SUCCEEDED"}, "manifest": {"schema": {"columns": []}}}
    cli = fake_cli({("post", "/api/2.0/sql/statements"): post})
    execute(cli, "wh", "SELECT :period", parameters={"period": "MTD", "n": 7})
    assert sent["parameters"] == [{"name": "period", "value": "MTD"}, {"name": "n", "value": "7"}]
