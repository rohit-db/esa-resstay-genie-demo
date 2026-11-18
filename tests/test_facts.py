from dataclasses import replace
from datetime import date, timedelta

import pandas as pd

from esa_resstay_demo.data.config import GenConfig
from esa_resstay_demo.data.facts import DayLookup, build_fact_actual_stay, build_fact_property_statistics, build_reservations
from esa_resstay_demo.data.portfolio import build_portfolio
from esa_resstay_demo.data.reference import build_dim_crm_account, build_sim_reference
from esa_resstay_demo.data.simulate import simulate_property


def _all(world, builder):
    return pd.concat([builder(world["events"][p["bk_property_id"]], p) for p in world["props"]], ignore_index=True)


def test_stay_lines_follow_the_revenue_rules(tiny_world, tiny_days):
    cfg, days = tiny_world["cfg"], tiny_days
    lines = _all(tiny_world, lambda ev, p: build_fact_actual_stay(ev, cfg, days))
    assert lines["fact_actual_stay_id"].is_unique
    assert ((lines["net_room_revenue"] - (lines["room_revenue_amount"] - lines["credit_revenue_amount"])).abs() < 0.005).all()
    assert ((lines["total_room_revenue"] - (lines["room_revenue_amount"] + lines["other_rooms_revenue"])).abs() < 0.005).all()
    credits = lines[lines["consumed_room_nights_count"] == 0]
    assert len(credits) > 0 and (credits["room_revenue_amount"] == 0).all() and (credits["credit_revenue_amount"] > 0).all()
    dates = pd.to_datetime(lines["bk_date_id"], format="%Y%m%d").dt.date
    assert dates.min() >= cfg.history_start_date and dates.max() == cfg.as_of_date


def test_property_statistics_match_stay_nights_and_capacity(tiny_world, tiny_days):
    cfg, days = tiny_world["cfg"], tiny_days
    for prop in tiny_world["props"]:
        events = tiny_world["events"][prop["bk_property_id"]]
        stats = build_fact_property_statistics(events, prop, cfg, days)
        lines = build_fact_actual_stay(events, cfg, days)
        nights = lines.groupby(lines["bk_date_id"].astype(int))["consumed_room_nights_count"].sum()
        merged = stats.set_index("bk_date_id")["occupied_rooms"].sub(nights, fill_value=0)
        assert (merged == 0).all()
        assert (stats["available_rooms"] + stats["out_of_order_rooms"] == prop["room_count"]).all()
        assert (stats["occupied_rooms"] <= stats["available_rooms"]).all()
        assert (stats["paid_rooms"] + stats["comp_rooms"] == stats["occupied_rooms"]).all()


def test_reservations_statuses_and_versions(tiny_world, tiny_days):
    cfg, days = tiny_world["cfg"], tiny_days
    facts = _all(tiny_world, lambda ev, p: build_reservations(ev, cfg, days)[0])
    dims = _all(tiny_world, lambda ev, p: build_reservations(ev, cfg, days)[1])
    current = facts[facts["_is_current"]]
    assert current["bk_reservation_id"].is_unique and facts["fact_reservation_summary_id"].is_unique
    assert set(facts["bk_reservation_id"]) == set(dims["bk_reservation_id"])
    cancelled = current[current["reservation_cancel_flag"]]
    assert (cancelled["cancel_date"] <= cfg.as_of_date).all() and (cancelled["actual_room_nights_count"] == 0).all()
    assert 0.06 < current["reservation_cancel_flag"].mean() < 0.18
    assert (current["booked_date"] <= cfg.as_of_date).all()
    assert (current["actual_room_nights_count"] + current["otb_room_nights_count"]
            <= current["current_room_nights_count"]).all()
    statuses = set(dims.loc[dims["_is_current"], "reservation_status"])
    assert {"Checked Out", "In House", "Reserved", "Cancelled"} <= statuses
    assert (~facts["_is_current"]).sum() == (~dims["_is_current"]).sum()


def test_stay_lines_only_append_when_as_of_moves(tiny_world, tiny_days):
    cfg, prop = tiny_world["cfg"], tiny_world["props"][2]
    later = replace(cfg, as_of_date=cfg.as_of_date + timedelta(days=10))
    first = build_fact_actual_stay(tiny_world["events"][prop["bk_property_id"]], cfg, tiny_days)
    second = build_fact_actual_stay(simulate_property(prop, later, tiny_world["sim"]), later, DayLookup(later))
    second = second[second["bk_date_id"].astype(int) <= int(cfg.as_of_date.strftime("%Y%m%d"))]
    cols = [c for c in first.columns if c != "_load_ts"]
    key = "fact_actual_stay_id"
    pd.testing.assert_frame_equal(first[cols].sort_values(key).reset_index(drop=True),
                                  second[cols].sort_values(key).reset_index(drop=True))


def test_small_and_odd_scales_still_build_consistent_portfolios():
    for scale in (1, 7, 15):
        cfg = GenConfig(as_of_date=date(2026, 1, 31), story_anchor_date=date(2026, 1, 31), seed=3, scale_properties=scale)
        p = build_portfolio(cfg)
        assert len(p.sim_inputs) == scale and p.dim_property["_is_current"].sum() == scale
        prop = p.sim_inputs.to_dict("records")[0]
        sim = build_sim_reference(build_dim_crm_account(cfg))
        stats = build_fact_property_statistics(simulate_property(prop, cfg, sim), prop, cfg, DayLookup(cfg))
        assert (stats["occupied_rooms"] <= stats["available_rooms"]).all()


def test_bookings_long_before_sim_start_keep_their_real_dates(tiny_cfg):
    import pytest
    from esa_resstay_demo.data.simulate import MAX_LEAD_DAYS
    days = DayLookup(tiny_cfg)
    earliest = -(int(MAX_LEAD_DAYS * 1.5) + 1)   # a cancelled booking can lead its arrival by 1.5 x the stay lead + 1 day
    expected = tiny_cfg.sim_start_date + timedelta(days=earliest)
    assert days.dates([earliest])[0] == expected and days.strs([earliest])[0] == expected.strftime("%Y%m%d")
    with pytest.raises(ValueError, match="outside the day lookup"):
        days.dates([-10_000])
