"""Room-by-room stay simulation for one property.

Each room alternates vacancies and stays drawn from the LOS mix, so a room never holds two
guests and no hotel can exceed capacity. Every room has its own random stream that always
starts at sim_start_date, so moving as_of_date forward only appends events.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from esa_resstay_demo.data.config import GenConfig
from esa_resstay_demo.data.portfolio import allocate
from esa_resstay_demo.data.reference import (
    CHANNEL_INDEX, COMP_SEGMENT, COMP_SHARE, LONG_STAY_EXTRA_MEAN, MAX_LOS, MONTHLY_ACCOUNT_SHARE, RAMP_ACCOUNT_ID,
    RAMP_ACCOUNT_SHARE, ROOM_MIX, SimReference, geometric_extra, los_tier, promotion_window,
)

UNIFORMS_PER_CYCLE = 24
CHUNK_ROWS = 256
MAINTENANCE_MEAN_INTERVAL = 180.0
MAINTENANCE_HORIZON_DAYS = 5 * 365
NO_SHOW_SHARE = 0.02
CREDIT_SHARE = 0.05
EARLY_CHECKIN_SHARE = 0.03
DATE_CHANGE_SHARE = 0.01
EXTENSION_SHARE = 0.25
PET_SHARE = 0.10
RATE_NOISE_SIGMA = 0.06
RATE_CALIBRATION = 0.97
MAX_LEAD_DAYS = 180
DISCOUNTS = {"STAY7": 0.15, "MONTH30": 0.10, "APPONLY": 0.08, "BOOKEARLY": 0.12, "SENIOR": 0.10, "WEEKEND": 0.10}

EVENT_COLUMNS = (
    "record_type", "bk_property_id", "room", "seq", "arrival_idx", "nights", "room_type", "channel", "segment",
    "account", "promo", "lead_days", "pets", "rate", "comp", "cancel_shadow", "noshow_shadow", "credit",
    "credit_factor", "early_fee", "adults", "children", "date_change", "date_shift", "original_los",
    "affiliate", "shadow_frac", "ooo_reason",
)
EVENTS_DDL = (
    "record_type string, bk_property_id string, room bigint, seq bigint, arrival_idx bigint, nights bigint, "
    "room_type string, channel string, segment string, account string, promo string, lead_days bigint, "
    "pets boolean, rate double, comp boolean, cancel_shadow boolean, noshow_shadow boolean, credit boolean, "
    "credit_factor double, early_fee boolean, adults bigint, children bigint, date_change boolean, "
    "date_shift bigint, original_los bigint, affiliate string, shadow_frac double, ooo_reason string"
)


class UniformStream:
    """Hands out fixed-width rows of uniforms; the sequence never depends on how many are used."""

    def __init__(self, rng: np.random.Generator, width: int = UNIFORMS_PER_CYCLE, chunk: int = CHUNK_ROWS):
        self._rng, self._width, self._chunk = rng, width, chunk
        self._block = rng.random((chunk, width))
        self._pos = 0

    def next(self) -> np.ndarray:
        if self._pos == self._chunk:
            self._block = self._rng.random((self._chunk, self._width))
            self._pos = 0
        row = self._block[self._pos]
        self._pos += 1
        return row


def room_types(brand_cd: str, room_count: int) -> list[str]:
    mix = ROOM_MIX[brand_cd]
    out = []
    for code, count in zip((c for c, _ in mix), allocate(room_count, [w for _, w in mix])):
        out.extend([code] * count)
    return out


def maintenance_schedule(seed: int, prop_index: int, room: int) -> list[tuple[int, int]]:
    """Scheduled maintenance (day index, duration) over a fixed five-year horizon."""
    rng = np.random.default_rng([seed, prop_index, room, 2])
    out, day = [], 0.0
    while True:
        day += rng.exponential(MAINTENANCE_MEAN_INTERVAL)
        duration = int(rng.integers(1, 6))
        if day >= MAINTENANCE_HORIZON_DAYS:
            return out
        out.append((int(day), duration))


def renovation_blocks(renos: list, room: int, room_count: int) -> list[tuple[int, int]]:
    """Out-of-order windows for one room: each project takes rooms out in sequential batches."""
    blocks = []
    for start, end, batches, _ in renos:
        batch = room * batches // room_count
        length = max(1, (end - start) // batches)
        b0 = start + batch * length
        b1 = end if batch == batches - 1 else b0 + length
        if b1 > b0:
            blocks.append((b0, b1))
    return sorted(blocks)


def property_curves(prop: dict, cfg: GenConfig, n_days: int, sim: SimReference) -> dict[str, np.ndarray]:
    days = np.arange(n_days)
    dates = pd.date_range(cfg.sim_start_date, periods=n_days, freq="D")
    doy = dates.dayofyear.to_numpy()
    years = (days - cfg.day_index(cfg.stories.trend_reference)) / 365.25
    season = 1 + 0.06 * np.sin(2 * np.pi * (doy - 80) / 365.25) - 0.05 * np.exp(-(((doy - 358) / 10.0) ** 2))
    demand = np.ones(n_days)
    for start, end, _, factor in json.loads(prop["renos_json"]):
        demand[max(start, 0):max(min(end, n_days), 0)] *= factor
    start_idx = cfg.day_index(prop["start_date"])
    if start_idx > 0:
        demand *= 0.6 + 0.4 * np.clip((days - start_idx) / 90.0, 0.0, 1.0)
    if prop["ramp_market"]:
        demand[max(cfg.day_index(cfg.stories.account_ramp_start), 0):] *= 1.06
    occupancy = np.clip(prop["base_occ"] * season * (1 + prop["occ_growth"]) ** years * demand, 0.25, 0.97)
    rate = (1 + prop["adr_growth"]) ** years * (1 + 0.03 * np.sin(2 * np.pi * (doy - 80) / 365.25))
    channel = sim.channel_base[None, :] * (1 + sim.channel_drift[None, :]) ** years[:, None]
    return {"occupancy": occupancy, "rate": rate, "channel": channel, "weekday": dates.dayofweek.to_numpy()}


def _promo_bounds(cfg: GenConfig, code: str) -> tuple[int, int]:
    start, end = promotion_window(cfg, code)
    return cfg.day_index(start), cfg.day_index(end)


def simulate_property(prop: dict, cfg: GenConfig, sim: SimReference) -> pd.DataFrame:
    """Simulate every room of one property from its start date to the booking horizon."""
    horizon = cfg.day_index(cfg.horizon_end)
    curves = property_curves(prop, cfg, horizon, sim)
    occ, rate_curve, chan_curve, weekday = curves["occupancy"], curves["rate"], curves["channel"], curves["weekday"]
    renos = json.loads(prop["renos_json"])
    start = cfg.day_index(prop["start_date"])
    pid, idx, n_rooms = prop["bk_property_id"], int(prop["prop_index"]), int(prop["room_count"])
    stay7 = _promo_bounds(cfg, "STAY7")
    book_early = _promo_bounds(cfg, "BOOKEARLY")
    weekend = _promo_bounds(cfg, "WEEKEND")
    ramp_idx = cfg.day_index(cfg.stories.account_ramp_start)
    types = room_types(prop["brand_cd"], n_rooms)
    cancel_odds = sim.channel_cancel / (1 - sim.channel_cancel)
    base_rate = prop["base_adr"] / RATE_CALIBRATION
    rows: list[tuple] = []
    for room in range(n_rooms):
        stream = UniformStream(np.random.default_rng([cfg.seed, idx, room, 1]))
        maintenance = [m for m in maintenance_schedule(cfg.seed, idx, room) if m[0] + m[1] > start]
        blocks = renovation_blocks(renos, room, n_rooms)
        for b0, b1 in blocks:
            if b1 > start:
                rows.append(("OOO", pid, room, -1, max(b0, start), b1 - max(b0, start)) + (None,) * 21 + ("Renovation",))
        t, mi, seq = start, 0, 0
        while t < horizon:
            u = stream.next()
            in_promo = stay7[0] <= t < stay7[1]
            o = occ[t]
            mean_gap = (sim.mean_los_promo if in_promo else sim.mean_los) * (1 - o) / o
            s = t + geometric_extra(u[0], mean_gap)
            if mi < len(maintenance) and maintenance[mi][0] < s:
                m_day, m_dur = maintenance[mi]
                mi += 1
                a, a_end = max(t, m_day), max(t, m_day) + m_dur
                for b0, b1 in blocks:
                    if b0 <= a < b1:
                        a = a_end = b1
                    elif a < b0 < a_end:
                        a_end = b0
                if a < a_end:
                    rows.append(("OOO", pid, room, -1, a, a_end - a) + (None,) * 21 + ("Maintenance",))
                    t = a_end
                continue
            if s >= horizon:
                break
            inside = next((b for b in blocks if b[0] <= s < b[1]), None)
            if inside:
                t = inside[1]
                continue
            promo_now = stay7[0] <= s < stay7[1]
            tier = int(np.searchsorted(sim.tier_cdf_promo if promo_now else sim.tier_cdf, u[1], side="right"))
            if tier == 0:
                nights = 1 + int(np.searchsorted(sim.tier0_cdf, u[2], side="right"))
            elif tier == 1:
                nights = 7 + int(np.searchsorted(sim.tier1_cdf, u[2], side="right"))
            elif tier == 2:
                nights = 15 + min(int(u[2] * 15), 14)
            else:
                nights = min(30 + geometric_extra(u[2], LONG_STAY_EXTRA_MEAN), MAX_LOS)
            next_block = next((b[0] for b in blocks if b[0] > s), None)
            if next_block is not None:
                nights = min(nights, next_block - s)
            tier = los_tier(nights)
            weights = chan_curve[s] * sim.channel_affinity[tier]
            c = int(np.searchsorted(np.cumsum(weights) / weights.sum(), u[3], side="right"))
            c = min(c, len(sim.channel_ids) - 1)
            channel = sim.channel_ids[c]
            seg_i = min(int(np.searchsorted(sim.segment_cdf[c, tier], u[4], side="right")), len(sim.segment_ids) - 1)
            segment = COMP_SEGMENT if u[5] < COMP_SHARE else sim.segment_ids[seg_i]
            long_stay = nights >= 30
            account = None
            if prop["ramp_market"] and long_stay and s >= ramp_idx and u[7] < RAMP_ACCOUNT_SHARE and segment != COMP_SEGMENT:
                account, segment = RAMP_ACCOUNT_ID, "RS04"
            elif (segment, long_stay) in sim.account_cdf and (segment != "RS03" or u[7] < MONTHLY_ACCOUNT_SHARE):
                eligible, cdf = sim.account_cdf[(segment, long_stay)]
                if len(eligible):
                    pick = min(int(np.searchsorted(cdf, u[6], side="right")), len(eligible) - 1)
                    account = sim.account_ids[eligible[pick]]
            lead = 0 if channel == "CH04" else min(MAX_LEAD_DAYS, int(-sim.channel_lead[c] * math.log(max(u[9], 1e-12))) + (5 if long_stay else 0))
            promo = "NONE"
            if tier == 1 and promo_now:
                promo = "STAY7" if u[8] < 0.60 else "NONE"
            elif segment == "RS03" and long_stay:
                promo = "MONTH30" if u[8] < 0.15 else "NONE"
            elif channel == "CH02":
                promo = "APPONLY" if u[8] < 0.30 else "NONE"
            elif segment == "RS06":
                promo = "SENIOR" if u[8] < 0.50 else "NONE"
            elif segment == "RS09" and long_stay:
                promo = "RELO" if u[8] < 0.40 else "NONE"
            elif nights <= 6 and book_early[0] <= s < book_early[1] and lead >= 14:
                promo = "BOOKEARLY" if u[8] < 0.10 else "NONE"
            elif nights <= 3 and weekend[0] <= s < weekend[1] and weekday[s] in (4, 5):
                promo = "WEEKEND" if u[8] < 0.15 else "NONE"
            z = math.sqrt(-2.0 * math.log(max(u[11], 1e-12))) * math.cos(2.0 * math.pi * u[12])
            rate = (base_rate * sim.segment_adr[sim.segment_ids.index(segment)] * sim.room_type_adr[types[room]]
                    * rate_curve[s] * math.exp(RATE_NOISE_SIGMA * z))
            if promo in DISCOUNTS:
                rate *= 1 - DISCOUNTS[promo]
            elif promo == "RELO":
                rate = max(rate * 0.5, rate - 150.0 / nights)
            comp = segment == COMP_SEGMENT
            rate = 0.0 if comp else round(rate, 2)
            if nights >= 7 and u[20] < EXTENSION_SHARE:
                original = max(1, int(nights * (0.45 + 0.45 * u[21])))
            else:
                original = nights
            affiliate = ("AAA" if u[22] < 0.6 else "AARP") if segment == "RS06" else ("USAA" if u[22] < 0.03 else None)
            adults = 1 if u[18] < 0.75 else 2 if u[18] < 0.97 else 3
            child_draw = (u[18] * 7.0) % 1.0
            children = 0 if child_draw < 0.85 else 1 if child_draw < 0.95 else 2
            date_change = u[19] < DATE_CHANGE_SHARE
            shift = (1 + int(u[23] * 14)) * (1 if u[20] < 0.5 else -1) if date_change else 0
            rows.append((
                "STAY", pid, room, seq, s, nights, types[room], channel, segment, account, promo, lead,
                bool(u[10] < PET_SHARE), rate, comp, bool(u[13] < cancel_odds[c]), bool(u[14] < NO_SHOW_SHARE),
                bool(u[15] < CREDIT_SHARE), 0.1 + 0.2 * float(u[16]), bool(u[17] < EARLY_CHECKIN_SHARE),
                adults, children, bool(date_change), shift, original, affiliate, float(u[23]), None,
            ))
            seq += 1
            t = s + nights
    events = pd.DataFrame(rows, columns=list(EVENT_COLUMNS))
    events = events[events["arrival_idx"] < horizon].reset_index(drop=True)
    for col in ("room", "seq", "arrival_idx", "nights", "lead_days", "adults", "children", "date_shift", "original_los"):
        events[col] = events[col].astype("Int64")
    return events
