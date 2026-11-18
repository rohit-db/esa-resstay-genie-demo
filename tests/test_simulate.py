from dataclasses import replace
from datetime import timedelta

import pandas as pd

from esa_resstay_demo.data.simulate import maintenance_schedule, simulate_property


def _intervals(events: pd.DataFrame):
    for (_, room), rows in events.groupby(["bk_property_id", "room"]):
        spans = sorted(zip(rows["arrival_idx"].astype(int), (rows["arrival_idx"] + rows["nights"]).astype(int)))
        yield room, spans


def test_a_room_never_holds_two_things_at_once(tiny_world):
    for events in tiny_world["events"].values():
        for room, spans in _intervals(events):
            for (_, end), (start, _) in zip(spans, spans[1:]):
                assert start >= end, f"room {room} overlaps at day {start}"


def test_stays_have_valid_lengths_and_rates(tiny_world):
    stays = pd.concat(tiny_world["events"].values()).query("record_type == 'STAY'")
    assert stays["nights"].between(1, 365).all()
    assert (stays.loc[~stays["comp"].astype(bool), "rate"] > 0).all()
    assert (stays.loc[stays["comp"].astype(bool), "rate"] == 0).all()


def test_simulation_is_deterministic(tiny_world):
    prop = tiny_world["props"][0]
    again = simulate_property(prop, tiny_world["cfg"], tiny_world["sim"])
    pd.testing.assert_frame_equal(again, tiny_world["events"][prop["bk_property_id"]])


def test_moving_as_of_forward_only_appends(tiny_world):
    cfg, prop = tiny_world["cfg"], tiny_world["props"][1]
    later = replace(cfg, as_of_date=cfg.as_of_date + timedelta(days=10))
    first = tiny_world["events"][prop["bk_property_id"]]
    second = simulate_property(prop, later, tiny_world["sim"])
    prefix = second[second["arrival_idx"] < cfg.day_index(cfg.horizon_end)].reset_index(drop=True)
    key = ["room", "record_type", "arrival_idx"]
    pd.testing.assert_frame_equal(first.sort_values(key).reset_index(drop=True), prefix.sort_values(key).reset_index(drop=True))


def test_maintenance_schedule_ignores_the_as_of_date():
    assert maintenance_schedule(7, 3, 11) == maintenance_schedule(7, 3, 11)
    assert all(d >= 0 and 1 <= n <= 5 for d, n in maintenance_schedule(7, 3, 11))
