"""Fact builders: turn one property's simulated events into staging rows."""

from __future__ import annotations

from datetime import datetime, time, timedelta

import numpy as np
import pandas as pd

from esa_resstay_demo.data.config import OPEN_ENDED, GenConfig
from esa_resstay_demo.data.frames import with_meta
from esa_resstay_demo.data.reference import (
    AFFILIATES, CHANNELS, EARLY_CHECKIN_FEE, MAX_LOS, PET_FEE_MAX_NIGHTS, PET_FEE_PER_NIGHT,
)
from esa_resstay_demo.data.simulate import MAX_LEAD_DAYS

ENTITY_ID = "HK-ESA"
RESERVATION_SOURCE = {row[0]: row[9] for row in CHANNELS}


class DayLookup:
    """Vectorised day-index conversions; indices may be negative (bookings before sim start)."""

    PAD = int(1.5 * MAX_LEAD_DAYS) + 2   # cancelled bookings lead their arrival by up to 1.5 x MAX_LEAD_DAYS + 1

    def __init__(self, cfg: GenConfig):
        n = cfg.day_index(cfg.horizon_end) + MAX_LOS + 2 * self.PAD
        self._n = n
        idx = pd.date_range(cfg.sim_start_date - timedelta(days=self.PAD), periods=n, freq="D")
        self._id = (idx.year * 10000 + idx.month * 100 + idx.day).to_numpy().astype("int64")
        self._str = self._id.astype(str)
        self._date = np.array(idx.date, dtype=object)
        self._audit = (idx + pd.Timedelta(days=1, hours=4)).to_numpy()
        self._start = pd.Timestamp(cfg.sim_start_date)

    def _pos(self, i) -> np.ndarray:
        """Array positions for day indices; out-of-range indices raise instead of silently wrapping."""
        pos = np.asarray(i, dtype="int64") + self.PAD
        if pos.size and (pos.min() < 0 or pos.max() >= self._n):
            raise ValueError(f"day index outside the day lookup ({int(pos.min()) - self.PAD}..{int(pos.max()) - self.PAD})")
        return pos

    def ids(self, i) -> np.ndarray:
        return self._id[self._pos(i)]

    def strs(self, i) -> np.ndarray:
        return self._str[self._pos(i)]

    def dates(self, i) -> np.ndarray:
        return self._date[self._pos(i)]

    def nullable_dates(self, values) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        out = np.full(len(arr), None, dtype=object)
        ok = ~np.isnan(arr)
        out[ok] = self._date[self._pos(arr[ok].astype("int64"))]
        return out

    def audit(self, i) -> np.ndarray:
        return self._audit[self._pos(i)]

    def timestamps(self, i) -> np.ndarray:
        return (self._start + pd.to_timedelta(np.asarray(i, dtype="int64"), unit="D")).to_numpy()


def _stays(events: pd.DataFrame) -> pd.DataFrame:
    st = events[events["record_type"] == "STAY"].reset_index(drop=True)
    st = st.astype({"room": "int64", "seq": "int64", "arrival_idx": "int64", "nights": "int64",
                    "lead_days": "int64", "adults": "int64", "children": "int64", "date_shift": "int64",
                    "original_los": "int64"})
    st["base_id"] = st["bk_property_id"] + st["room"].astype(str).str.zfill(3) + st["seq"].astype(str).str.zfill(5)
    return st


def build_fact_actual_stay(events: pd.DataFrame, cfg: GenConfig, days: DayLookup) -> pd.DataFrame:
    as_idx, hist_idx = cfg.day_index(cfg.as_of_date), cfg.day_index(cfg.history_start_date)
    st = _stays(events)
    st = st[st["arrival_idx"] <= as_idx].reset_index(drop=True)
    arrival, nights = st["arrival_idx"].to_numpy(), st["nights"].to_numpy()
    consumed = np.minimum(nights, as_idx + 1 - arrival)
    rep = np.repeat(np.arange(len(st)), consumed)
    offset = np.arange(rep.size) - np.repeat(np.cumsum(consumed) - consumed, consumed)
    night = arrival[rep] + offset
    keep = night >= hist_idx
    rep, offset, night = rep[keep], offset[keep], night[keep]
    room_rev = st["rate"].to_numpy(dtype=float)[rep]
    other = (np.where(st["pets"].to_numpy(dtype=bool)[rep] & (offset < PET_FEE_MAX_NIGHTS), PET_FEE_PER_NIGHT, 0.0)
             + np.where(st["early_fee"].to_numpy(dtype=bool)[rep] & (offset == 0), EARLY_CHECKIN_FEE, 0.0))
    base = st["base_id"].to_numpy()
    room_lines = pd.DataFrame({
        "base_id": base[rep], "line_no": offset.astype(str), "kind": "N", "night": night,
        "bk_property_id": st["bk_property_id"].to_numpy()[rep], "bk_rate_segment_id": st["segment"].to_numpy()[rep],
        "bk_room_type_id": st["room_type"].to_numpy()[rep], "consumed_room_nights_count": 1,
        "room_revenue_amount": room_rev, "credit_revenue_amount": 0.0, "other_rooms_revenue": other,
    })
    departure = arrival + nights
    credit_amount = np.round(st["credit_factor"].to_numpy(dtype=float) * st["rate"].to_numpy(dtype=float) * nights, 2)
    with_credit = (st["credit"].to_numpy(dtype=bool) & (departure <= as_idx) & (departure >= hist_idx) & (credit_amount > 0))
    credit_lines = pd.DataFrame({
        "base_id": base[with_credit], "line_no": "999", "kind": "C", "night": departure[with_credit],
        "bk_property_id": st["bk_property_id"].to_numpy()[with_credit],
        "bk_rate_segment_id": st["segment"].to_numpy()[with_credit],
        "bk_room_type_id": st["room_type"].to_numpy()[with_credit], "consumed_room_nights_count": 0,
        "room_revenue_amount": 0.0, "credit_revenue_amount": credit_amount[with_credit], "other_rooms_revenue": 0.0,
    })
    lines = pd.concat([room_lines, credit_lines], ignore_index=True)
    date_str = days.strs(lines["night"].to_numpy())
    lines["fact_actual_stay_id"] = "R" + lines["base_id"] + "-" + date_str + "-" + lines["kind"]
    lines["entity_id"] = ENTITY_ID
    lines["hkpms_subledger_sid"] = lines["base_id"] + lines["line_no"].str.zfill(3)
    lines["bk_date_id"] = date_str
    lines["bk_reservation_id"] = "R" + lines["base_id"]
    for col in ("room_revenue_amount", "credit_revenue_amount", "other_rooms_revenue"):
        lines[col] = np.round(lines[col].to_numpy(dtype=float), 2)
    lines["net_room_revenue"] = np.round(lines["room_revenue_amount"] - lines["credit_revenue_amount"], 2)
    lines["total_room_revenue"] = np.round(lines["room_revenue_amount"] + lines["other_rooms_revenue"], 2)
    lines["consumed_room_nights_count"] = lines["consumed_room_nights_count"].astype("int64")
    audit = days.audit(lines["night"].to_numpy())
    out = lines[["fact_actual_stay_id", "entity_id", "hkpms_subledger_sid", "bk_property_id", "bk_date_id",
                 "bk_reservation_id", "bk_rate_segment_id", "bk_room_type_id", "consumed_room_nights_count",
                 "room_revenue_amount", "credit_revenue_amount", "other_rooms_revenue", "net_room_revenue",
                 "total_room_revenue"]]
    return with_meta(out, "HOTELKEY.PMS", audit, audit)


def build_fact_property_statistics(events: pd.DataFrame, prop: dict, cfg: GenConfig, days: DayLookup) -> pd.DataFrame:
    as_idx, hist_idx = cfg.day_index(cfg.as_of_date), cfg.day_index(cfg.history_start_date)
    n = cfg.day_index(cfg.horizon_end) + MAX_LOS + 2

    def coverage(starts, lengths) -> np.ndarray:
        diff = np.zeros(n + 1, dtype=np.int64)
        starts = np.asarray(starts, dtype=np.int64)
        np.add.at(diff, starts, 1)
        np.add.at(diff, np.minimum(starts + np.asarray(lengths, dtype=np.int64), n), -1)
        return np.cumsum(diff)[:n]

    st = _stays(events)
    ooo = events[events["record_type"] == "OOO"]
    occupied = coverage(st["arrival_idx"], st["nights"])
    comp = coverage(st.loc[st["comp"].astype(bool), "arrival_idx"], st.loc[st["comp"].astype(bool), "nights"])
    out_of_order = coverage(ooo["arrival_idx"].astype("int64"), ooo["nights"].astype("int64"))
    first = max(cfg.day_index(prop["start_date"]), hist_idx)
    rng_days = np.arange(first, as_idx + 1)
    available = int(prop["room_count"]) - out_of_order[rng_days]
    df = pd.DataFrame({
        "bk_property_id": prop["bk_property_id"], "bk_date_id": days.ids(rng_days),
        "available_rooms": available, "occupied_rooms": occupied[rng_days],
        "vacant_rooms": available - occupied[rng_days], "paid_rooms": occupied[rng_days] - comp[rng_days],
        "comp_rooms": comp[rng_days], "out_of_order_rooms": out_of_order[rng_days],
    })
    audit = days.audit(rng_days) + np.timedelta64(30, "m")
    return with_meta(df, "HOTELKEY.PMS.STATS", audit, audit)


def build_reservations(events: pd.DataFrame, cfg: GenConfig, days: DayLookup) -> tuple[pd.DataFrame, pd.DataFrame]:
    """fact_reservation_summary and dim_reservation rows, including cancellations, no-shows and date changes."""
    as_idx = cfg.day_index(cfg.as_of_date)
    st = _stays(events)
    st["booked_idx"] = st["arrival_idx"] - st["lead_days"]
    main = st[st["booked_idx"] <= as_idx].copy()
    main["kind"], main["suffix"] = "S", ""

    cancel = st[st["cancel_shadow"].astype(bool)].copy()
    lead_c = np.maximum(1, (cancel["lead_days"] * (0.5 + cancel["shadow_frac"])).astype("int64") + 1)
    cancel["booked_idx"] = cancel["arrival_idx"] - lead_c
    cancel["cancel_idx"] = cancel["booked_idx"] + ((cancel["arrival_idx"] - cancel["booked_idx"]) * cancel["shadow_frac"]).astype("int64")
    cancel = cancel[cancel["booked_idx"] <= as_idx]
    cancel["kind"], cancel["suffix"] = "C", "C"
    cancel["date_change"], cancel["date_shift"], cancel["original_los"] = False, 0, cancel["nights"]

    noshow = st[st["noshow_shadow"].astype(bool) & (st["booked_idx"] <= as_idx)].copy()
    noshow["kind"], noshow["suffix"] = "N", "N"
    noshow["date_change"], noshow["date_shift"], noshow["original_los"] = False, 0, noshow["nights"]

    res = pd.concat([main, cancel, noshow], ignore_index=True)
    res["cancel_idx"] = res["cancel_idx"].astype("float") if "cancel_idx" in res else np.nan
    kind = res["kind"].to_numpy()
    arrival = res["arrival_idx"].to_numpy(dtype="int64")
    nights = res["nights"].to_numpy(dtype="int64")
    rate = res["rate"].to_numpy(dtype=float)
    departure = arrival + nights
    orig_arrival = arrival + res["date_shift"].to_numpy(dtype="int64")
    orig_nights = res["original_los"].to_numpy(dtype="int64")
    booked = res["booked_idx"].to_numpy(dtype="int64")
    mod_idx = booked + ((np.minimum(arrival, orig_arrival) - booked).clip(0) * 0.5).astype("int64")
    changed = res["date_change"].to_numpy(dtype=bool) & (mod_idx <= as_idx) & (kind == "S")
    orig_arrival = np.where(changed, orig_arrival, arrival)
    cancelled = (kind == "C") & (np.nan_to_num(res["cancel_idx"].to_numpy(dtype=float), nan=1e9) <= as_idx)
    no_show = (kind == "N") & (arrival <= as_idx)
    stayed = kind == "S"
    actual_nights = np.where(stayed, np.clip(np.minimum(nights, as_idx + 1 - arrival), 0, None), 0)
    otb = np.where(cancelled | no_show, 0, nights - actual_nights)
    status = np.select(
        [cancelled, no_show, stayed & (departure <= as_idx), stayed & (arrival <= as_idx)],
        ["Cancelled", "No Show", "Checked Out", "In House"], default="Reserved")
    res_id = "R" + res["base_id"] + res["suffix"]
    current = pd.DataFrame({
        "fact_reservation_summary_id": res_id + np.where(changed, "-V2", "-V1"),
        "entity_id": ENTITY_ID, "bk_reservation_id": res_id, "bk_crm_account_id": res["account"].to_numpy(),
        "bk_property_id": res["bk_property_id"].to_numpy(), "bk_date_id": days.strs(booked),
        "bk_channel_id": res["channel"].to_numpy(),
        "bk_original_los_id": np.minimum(orig_nights, MAX_LOS).astype(str),
        "bk_current_los_id": np.minimum(nights, MAX_LOS).astype(str),
        "bk_otb_los_id": np.minimum(otb, MAX_LOS).astype(str),
        "bk_actual_los_id": np.minimum(actual_nights, MAX_LOS).astype(str),
        "bk_rate_segment_id": res["segment"].to_numpy(), "bk_room_type_id": res["room_type"].to_numpy(),
        "bk_promo_cd": res["promo"].to_numpy(), "booked_date": days.dates(booked),
        "original_arrival_date": days.dates(orig_arrival), "original_departure_date": days.dates(orig_arrival + orig_nights),
        "current_arrival_date": days.dates(arrival), "current_departure_date": days.dates(departure),
        "actual_arrival_date": days.nullable_dates(np.where(stayed & (arrival <= as_idx), arrival, np.nan)),
        "actual_departure_date": days.nullable_dates(np.where(stayed & (departure <= as_idx), departure, np.nan)),
        "original_room_nights_count": orig_nights, "current_room_nights_count": nights,
        "otb_room_nights_count": otb, "actual_room_nights_count": actual_nights,
        "original_room_revenue_amount": np.round(orig_nights * rate, 2),
        "current_room_revenue_amount": np.round(nights * rate, 2),
        "actual_room_revenue_amount": np.round(actual_nights * rate, 2),
        "affiliate_revenue_total_amount_before_tax": np.where(res["affiliate"].notna(), np.round(nights * rate, 2), 0.0),
        "reservation_cancel_flag": cancelled,
        "cancel_date": days.nullable_dates(np.where(cancelled, res["cancel_idx"].to_numpy(dtype=float), np.nan)),
        "pets_flag": res["pets"].to_numpy(dtype=bool),
    })
    booked_ts = days.timestamps(booked)
    mod_ts = days.timestamps(mod_idx)
    current_start = np.where(changed, mod_ts, booked_ts)
    prior = current[changed].copy()
    prior["fact_reservation_summary_id"] = prior["bk_reservation_id"] + "-V1"
    prior["current_arrival_date"] = prior["original_arrival_date"]
    prior["current_departure_date"] = prior["original_departure_date"]
    prior["current_room_nights_count"] = prior["original_room_nights_count"]
    prior["bk_current_los_id"] = prior["bk_original_los_id"]
    prior["current_room_revenue_amount"] = prior["original_room_revenue_amount"]
    prior["otb_room_nights_count"] = prior["original_room_nights_count"]
    prior["bk_otb_los_id"] = prior["bk_original_los_id"]
    for col in ("actual_room_nights_count", "actual_room_revenue_amount"):
        prior[col] = 0
    prior["bk_actual_los_id"] = "0"
    prior["actual_arrival_date"], prior["actual_departure_date"] = None, None
    load_ts = cfg.dimension_load_ts
    fact = pd.concat([
        with_meta(current, "HOTELKEY.CRS", load_ts, current_start),
        with_meta(prior, "HOTELKEY.CRS", load_ts, booked_ts[changed], mod_ts[changed], False),
    ], ignore_index=True)
    for col in ("original_room_nights_count", "current_room_nights_count", "otb_room_nights_count", "actual_room_nights_count"):
        fact[col] = fact[col].astype("int64")
    for col in ("actual_room_revenue_amount",):
        fact[col] = fact[col].astype(float)

    affiliate = res["affiliate"].to_numpy()
    dim = pd.DataFrame({
        "dim_reservation_id": "DR-" + res_id + np.where(changed, "-V2", "-V1"), "bk_reservation_id": res_id,
        "bk_property_id": res["bk_property_id"].to_numpy(),
        "confirmation_number": res["base_id"] + res["suffix"].map({"": "", "C": "1", "N": "2"}),
        "reservation_status": status, "reservation_source": res["channel"].map(RESERVATION_SOURCE).to_numpy(),
        "adults_count": res["adults"].to_numpy(dtype="int64"), "children_count": res["children"].to_numpy(dtype="int64"),
        "affiliate_cd": affiliate, "affiliate_name": [AFFILIATES.get(a) if a else None for a in affiliate],
    })
    dim_prior = dim[changed].copy()
    dim_prior["dim_reservation_id"] = "DR-" + dim_prior["bk_reservation_id"] + "-V1"
    dim_prior["reservation_status"] = "Reserved"
    dims = pd.concat([
        with_meta(dim, "HOTELKEY.CRS", load_ts, current_start),
        with_meta(dim_prior, "HOTELKEY.CRS", load_ts, booked_ts[changed], mod_ts[changed], False),
    ], ignore_index=True)
    return fact, dims
