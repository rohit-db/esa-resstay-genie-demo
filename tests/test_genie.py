import json
from pathlib import Path

import pytest
import yaml

from tools.lib.bundle_config import load_target
from tools.lib.contract import load_contract
from tools.lib.genie import GENIE_DIR, GenieError, load_space, serialized_space

NAMES = load_target("demo").context

SPEC = """\
key: demo_space
metric_views: [semantic.resstay_metrics]
tables: [mart.vw_dim_property]
match:
  semantic.resstay_metrics: [Brand, District Manager]
  mart.vw_dim_property: [property_name]
hide:
  mart.vw_dim_property: [gm_name]
instructions: |
  ## PURPOSE
  - Answer revenue questions.
sample_questions:
  - What is MTD room revenue by brand?
examples:
  - question: Room revenue by brand
    sql: |
      SELECT `Brand`, MEASURE(`Room Revenue`) AS room_revenue
      FROM {{catalog}}.{{semantic}}.resstay_metrics
      GROUP BY ALL
benchmarks:
  - question: How many hotels are there?
    sql: SELECT COUNT(*) FROM {{catalog}}.{{mart}}.vw_dim_property
"""


def build(tmp_path, text=SPEC):
    path = tmp_path / "demo_space.yml"
    path.write_text(text)
    return serialized_space(load_space(path), NAMES, load_contract())


def test_serialized_space_has_the_api_shape(tmp_path):
    space = build(tmp_path)
    assert space["version"] == 2
    assert [m["identifier"] for m in space["data_sources"]["metric_views"]] == ["dev_gold.semantic.resstay_metrics"]
    table = space["data_sources"]["tables"][0]
    assert table["identifier"] == "dev_gold.mart.vw_dim_property"
    configs = {c["column_name"]: c for c in table["column_configs"]}
    assert configs["property_name"] == {"column_name": "property_name", "enable_entity_matching": True,
                                        "enable_format_assistance": True}
    assert configs["hash_diff"] == {"column_name": "hash_diff", "exclude": True}
    assert configs["dim_property_id"]["exclude"] is True          # surrogate keys are hidden
    assert configs["gm_name"] == {"column_name": "gm_name", "exclude": True}
    assert [c["column_name"] for c in table["column_configs"]] == sorted(configs)
    example = space["instructions"]["example_question_sqls"][0]
    assert example["question"] == ["Room revenue by brand"]
    assert "".join(example["sql"]).startswith("SELECT `Brand`") and "dev_gold.semantic.resstay_metrics" in "".join(
        example["sql"])
    benchmark = space["benchmarks"]["questions"][0]
    assert benchmark["answer"] == [{"format": "SQL", "content": ["SELECT COUNT(*) FROM dev_gold.mart.vw_dim_property"]}]
    text = space["instructions"]["text_instructions"]
    assert len(text) == 1 and "".join(text[0]["content"]).startswith("## PURPOSE")
    ids = [x["id"] for x in space["config"]["sample_questions"] + space["benchmarks"]["questions"]]
    assert all(len(i) == 32 and int(i, 16) >= 0 for i in ids) and len(set(ids)) == len(ids)


def test_ids_are_stable_across_renders(tmp_path):
    assert build(tmp_path) == build(tmp_path)


@pytest.mark.parametrize("old, new, message", [
    ("tables: [mart.vw_dim_property]", "tables: [mart.not_a_table]", "not a contract object"),
    ("  - question: How many hotels are there?", "  - question: Room revenue by brand", "duplicate question"),
    ("  mart.vw_dim_property: [property_name]", "  mart.vw_dim_property: [no_such_column]", "no_such_column"),
    ("key: demo_space", "key: demo_space\nextra: 1", "unknown fields"),
])
def test_spec_problems_are_reported(tmp_path, old, new, message):
    assert old in SPEC
    with pytest.raises(GenieError, match=message):
        build(tmp_path, SPEC.replace(old, new))


def test_repo_spaces_render_and_match_the_bundle_resources():
    resources = yaml.safe_load(Path("resources/genie_spaces.yml").read_text())["resources"]["genie_spaces"]
    specs = sorted(GENIE_DIR.glob("*.yml"))
    assert {p.stem for p in specs} == set(resources) == {"resstay_revenue", "property_operations"}
    for path in specs:
        spec = load_space(path)
        space = serialized_space(spec, NAMES, load_contract())
        assert resources[spec.key]["file_path"] == f"../build/genie/{spec.key}.geniespace.json"
        assert resources[spec.key]["warehouse_id"] == "${resources.sql_warehouses.esa_demo_wh.id}"
        assert len(space["instructions"]["example_question_sqls"]) >= 5
        assert len(space["benchmarks"]["questions"]) >= 10
        assert len("".join(space["instructions"]["text_instructions"][0]["content"])) <= 2000
        assert "{{" not in json.dumps(space)
