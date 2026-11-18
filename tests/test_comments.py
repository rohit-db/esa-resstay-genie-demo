import pytest

from tools.lib.bundle_config import load_target
from tools.lib.comments import DescriptionsError, comments_sql, load_descriptions, sql_string
from tools.lib.contract import load_contract


def test_repo_descriptions_cover_every_contract_object_and_column():
    contract = load_contract()
    descriptions = load_descriptions(contract=contract)
    for table in contract.tables:
        assert descriptions.table(table.name)
        for column in contract.all_columns(table):
            assert descriptions.column(table.name, column.name), f"{table.name}.{column.name}"


def test_missing_or_unknown_descriptions_are_reported(tmp_path):
    path = tmp_path / "d.yml"
    path.write_text("version: 1\nhistory_columns: {}\ntables:\n  fact_actual_stay:\n    table: Stay ledger.\n"
                    "    columns:\n      not_a_column: Nope.\n")
    with pytest.raises(DescriptionsError) as error:
        load_descriptions(path, load_contract())
    message = str(error.value)
    assert "fact_actual_stay.not_a_column is not in the contract" in message
    assert "dim_los: no description" in message and "history column hash_diff" in message


def test_sql_string_escapes_quotes_and_backslashes():
    assert sql_string("hotel's \\ rate") == "'hotel\\'s \\\\ rate'"


def test_comments_sql_comments_every_object_and_column_with_target_names():
    contract = load_contract()
    sql = comments_sql(contract, load_descriptions(contract=contract), load_target("demo").names)
    assert "COMMENT ON TABLE `dev_gold`.`common`.`dim_date` IS '" in sql
    assert "COMMENT ON COLUMN `dev_gold`.`mart`.`fact_actual_stay`.`is_current` IS '" in sql
    expected = sum(1 + len(contract.all_columns(t)) for t in contract.tables)
    assert sql.count(";\n") == expected
