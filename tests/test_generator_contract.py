from esa_resstay_demo.data.frames import META_COLUMNS, business_columns
from esa_resstay_demo.jobs.generate import build_dimension_frames, build_property_frames, run_info_frame
from tools.lib.contract import load_contract


def test_every_staging_frame_matches_the_contract(tiny_world, tiny_days):
    contract = load_contract()
    cfg = tiny_world["cfg"]
    frames, sim_inputs, _ = build_dimension_frames(cfg)
    prop = tiny_world["props"][0]
    frames.update(build_property_frames(tiny_world["events"][prop["bk_property_id"]], prop, cfg, tiny_days))
    expected = {t.name for t in contract.tables if t.kind != "view"}
    assert set(frames) == expected
    for name, frame in frames.items():
        assert business_columns(frame) == [c.name for c in contract.table(name).columns], name
        assert list(frame.columns[-len(META_COLUMNS):]) == list(META_COLUMNS), name
    assert len(sim_inputs) == cfg.scale_properties


def test_run_info_records_the_generation_inputs(tiny_cfg):
    row = run_info_frame(tiny_cfg).iloc[0]
    assert row["as_of_date"] == tiny_cfg.as_of_date and row["story_anchor_date"] == tiny_cfg.story_anchor_date
    assert row["scale_properties"] == 30


def test_generator_refuses_a_run_after_the_story_window_before_writing_anything():
    import pytest
    from esa_resstay_demo.jobs.generate import config_from_args, parse_args
    args = parse_args(["--catalog", "dev_gold", "--staging-schema", "staging", "--staging-schema-file", "unused.json",
                       "--as-of", "2026-12-17", "--story-anchor", "2026-11-16"])
    with pytest.raises(SystemExit, match="more than 30 days after the story anchor"):
        config_from_args(args)
