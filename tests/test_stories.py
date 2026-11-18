"""The planted demo stories, checked in pandas at 150 properties (about 30 seconds)."""

from datetime import date

import pandas as pd
import pytest

from esa_resstay_demo.data.config import GenConfig
from esa_resstay_demo.data.facts import DayLookup
from esa_resstay_demo.data.reference import los_tier
from esa_resstay_demo.data.simulate import simulate_property
from esa_resstay_demo.jobs.generate import build_dimension_frames, build_property_frames

AS_OF = pd.Timestamp("2026-11-16")
pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def world():
    cfg = GenConfig(as_of_date=AS_OF.date(), story_anchor_date=AS_OF.date(), scale_properties=150)
    frames, sim_inputs, sim = build_dimension_frames(cfg)
    days = DayLookup(cfg)
    out = {"fact_actual_stay": [], "fact_property_statistics": [], "fact_reservation_summary": [], "events": []}
    for prop in sim_inputs.to_dict("records"):
        events = simulate_property(prop, cfg, sim)
        built = build_property_frames(events, prop, cfg, days)
        for name in ("fact_actual_stay", "fact_property_statistics", "fact_reservation_summary"):
            out[name].append(built[name])
        out["events"].append(events)
    world = {k: pd.concat(v, ignore_index=True) for k, v in out.items()}
    props = frames["dim_property"].query("_is_current")[["bk_property_id", "market_name"]].merge(
        sim_inputs[["bk_property_id", "district_name"]])
    lines = world["fact_actual_stay"].merge(props, on="bk_property_id")
    lines["d"] = pd.to_datetime(lines["bk_date_id"], format="%Y%m%d")
    res = world["fact_reservation_summary"].query("_is_current")
    lines = lines.merge(res[["bk_reservation_id", "bk_channel_id", "bk_crm_account_id"]], on="bk_reservation_id")
    world.update(lines=lines, props=props, res=res, frames=frames)
    return world


def _window(df, end, days, col="d"):
    return df[(df[col] > end - pd.Timedelta(days=days)) & (df[col] <= end)]


def _yoy(df, by, days, value="room_revenue_amount"):
    cy = _window(df, AS_OF, days).groupby(by)[value].sum()
    ly = _window(df, AS_OF - pd.DateOffset(years=1), days).groupby(by)[value].sum()
    return (cy / ly - 1).dropna()


def test_renovation_district_has_the_biggest_decline(world):
    yoy = _yoy(world["lines"], "district_name", 28).sort_values()
    reno = world["frames"]["dim_property_renovation"].query("renovation_type == 'Full Renovation' and renovation_status == 'In Progress'")
    hotels = world["frames"]["fact_property_renovation"].merge(reno, on="bk_property_renovation_id")["bk_property_id"]
    district = world["props"].set_index("bk_property_id").loc[hotels, "district_name"].unique()
    assert list(district) == [yoy.index[0]] and yoy.iloc[0] < -0.08
    assert yoy.iloc[-1] - yoy.iloc[0] >= 0.15


def test_web_and_app_grow_while_call_center_declines(world):
    yoy = _yoy(world["lines"], "bk_channel_id", 90)
    assert yoy["CH01"] > yoy["CH03"] + 0.05 and yoy["CH02"] > yoy["CH03"] + 0.05 and yoy["CH03"] < 0.01


def test_stay7_promotion_lifts_one_to_two_week_stays(world):
    res = world["res"]
    stays = res[res["current_room_nights_count"].between(7, 14) & res["actual_arrival_date"].notna()].copy()
    stays["d"] = pd.to_datetime(stays["actual_arrival_date"])
    assert len(_window(stays, AS_OF, 90)) / len(_window(stays, AS_OF - pd.DateOffset(years=1), 90)) >= 1.06


def test_ramp_account_appears_in_phoenix(world):
    ramp = world["lines"].query("bk_crm_account_id == 'CRM00001' and market_name == 'Phoenix'")
    cy = _window(ramp, AS_OF, 60)["consumed_room_nights_count"].sum()
    ly = _window(ramp, AS_OF - pd.DateOffset(years=1), 60)["consumed_room_nights_count"].sum()
    assert cy >= 20 and cy >= 2 * ly


def test_calibration(world):
    stats = world["fact_property_statistics"]
    recent = stats[stats["bk_date_id"] >= 20251117]
    assert 0.65 < recent["occupied_rooms"].sum() / recent["available_rooms"].sum() < 0.78
    year = _window(world["lines"], AS_OF, 365)
    assert 68 < year["room_revenue_amount"].sum() / year["consumed_room_nights_count"].sum() < 80
    stays = world["events"].query("record_type == 'STAY'")
    revenue = (stays["rate"] * stays["nights"].astype(int)).groupby(stays["nights"].astype(int).map(los_tier)).sum()
    share = revenue / revenue.sum()
    assert 0.18 < share[0] < 0.27 and 0.46 < share[3] < 0.61
    total = _yoy(world["lines"].assign(all="all"), "all", 365)["all"]
    assert 0.0 < total < 0.07
