from datetime import date

import pandas as pd

from esa_resstay_demo.data.config import GenConfig
from esa_resstay_demo.data.portfolio import allocate, build_portfolio

FULL = GenConfig(as_of_date=date(2026, 11, 16), story_anchor_date=date(2026, 11, 16))


def test_allocate_is_exact():
    assert allocate(10, [0.35, 0.25, 0.22, 0.18]) == [4, 2, 2, 2]
    assert sum(allocate(600, [1] * 15)) == 600


def test_org_hierarchy_at_full_scale():
    p = build_portfolio(FULL)
    current = p.dim_property[p.dim_property["_is_current"]]
    assert len(current) == 600 and current["bk_property_id"].is_unique
    d = p.districts
    assert len(d) == 60 and d["hotel_count"].eq(10).all()
    assert d["region_name"].nunique() == 15 and d["division_name"].nunique() == 4
    shares = current["brand_cd"].value_counts(normalize=True)
    assert 0.55 < shares["ESAS"] < 0.65 and 0.25 < shares["ESSS"] < 0.32


def test_planted_portfolio_stories():
    p = build_portfolio(FULL)
    reno = p.dim_property_renovation
    story = reno[(reno["renovation_type"] == "Full Renovation") & (reno["renovation_status"] == "In Progress")]
    assert len(story) == 4
    hotels = p.fact_property_renovation.merge(story, on="bk_property_renovation_id")["bk_property_id"]
    districts = p.sim_inputs.set_index("bk_property_id").loc[hotels, "district_name"]
    assert districts.nunique() == 1 and districts.iloc[0].startswith("Texas")
    leaders = p.dim_property_hierarchy[p.dim_property_hierarchy["hierarchy_name"] == "Leadership"]
    assert (~leaders["_is_current"]).sum() == 10                     # one district changed its DM
    assert leaders.groupby("bk_property_hierarchy_id")["_is_current"].sum().eq(1).all()
    assert (~p.dim_property["_is_current"]).sum() == round(600 * 0.013)  # brand conversions keep history
    tiger = p.fact_property_segment["bk_property_segment_id"].str.endswith("TIGER-SITE").sum()
    assert tiger == 30
    ext = p.dim_property_extended
    assert 0.03 < (ext["comp_status"] == "Non-Comp").mean() < 0.07


def test_portfolio_is_deterministic(tiny_cfg):
    a, b = build_portfolio(tiny_cfg), build_portfolio(tiny_cfg)
    for name, frame in a.frames().items():
        pd.testing.assert_frame_equal(frame, b.frames()[name])
