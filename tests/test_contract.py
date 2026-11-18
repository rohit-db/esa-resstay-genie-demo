from pathlib import Path

import pytest
import yaml

from tools.lib.contract import ContractError, load_contract

EXACT_FACT_ACTUAL_STAY = [
    "fact_actual_stay_id", "entity_id", "hkpms_subledger_sid", "bk_property_id", "bk_date_id",
    "bk_reservation_id", "bk_rate_segment_id", "bk_room_type_id", "consumed_room_nights_count",
    "room_revenue_amount", "credit_revenue_amount", "other_rooms_revenue", "net_room_revenue", "total_room_revenue",
]


def test_contract_has_the_twenty_esa_objects():
    contract = load_contract()
    assert len(contract.tables) == 20
    assert [t.name for t in contract.of_kind("materialized_view")] == ["fact_property_statistics"]
    assert [t.name for t in contract.of_kind("view")] == ["vw_dim_property"]
    assert contract.table("dim_date").schema == "common"


def test_fact_actual_stay_matches_the_exact_layout():
    table = load_contract().table("fact_actual_stay")
    assert table.source == "exact"
    assert [c.name for c in table.columns] == EXACT_FACT_ACTUAL_STAY


def test_history_columns_are_appended_to_every_object():
    contract = load_contract()
    history = [c.name for c in contract.history_columns]
    assert history[0] == "hash_diff" and history[-1] == "is_deleted" and len(history) == 9
    for table in contract.tables:
        assert [c.name for c in contract.all_columns(table)][-9:] == history


def test_date_key_quirk_is_explicit():
    contract = load_contract()
    stay_date = contract.table("fact_actual_stay").column("bk_date_id")
    assert (stay_date.type, stay_date.join_cast) == ("STRING", "INT")
    assert contract.table("fact_property_statistics").column("bk_date_id").type == "INT"
    assert contract.table("dim_date").column("BK_Date_Dim_Id").type == "INT"


def _write(tmp_path: Path, mutate) -> Path:
    raw = yaml.safe_load(Path("contract/dev_gold_mart.yml").read_text())
    mutate(raw)
    path = tmp_path / "contract.yml"
    path.write_text(yaml.safe_dump(raw))
    return path


def test_ref_type_mismatch_without_join_cast_is_rejected(tmp_path):
    def drop_cast(raw):
        for col in raw["tables"][0]["columns"]:
            col.pop("join_cast", None)
    with pytest.raises(ContractError, match="set join_cast"):
        load_contract(_write(tmp_path, drop_cast))


def test_unknown_type_and_dangling_ref_are_rejected(tmp_path):
    def break_it(raw):
        raw["tables"][0]["columns"][1]["type"] = "VARCHAR"
        raw["tables"][0]["columns"][3]["ref"] = "dim_nowhere.bk_id"
    with pytest.raises(ContractError) as error:
        load_contract(_write(tmp_path, break_it))
    assert "invalid type 'VARCHAR'" in str(error.value) and "does not exist" in str(error.value)
