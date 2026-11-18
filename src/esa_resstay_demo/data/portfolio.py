"""The synthetic hotel portfolio: property dimensions, org hierarchy, segments, renovations, sim inputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from esa_resstay_demo.data.config import ADR_GROWTH, OPEN_ENDED, GenConfig
from esa_resstay_demo.data.frames import with_meta
from esa_resstay_demo.data.names import person_names
from esa_resstay_demo.data.reference import (
    AREAS, BRANDS, DIVISIONS, DM_CHANGE_REGION, MARKET_WEIGHTS, RAMP_MARKET, REGIONS, RENOVATION_REGION,
    STREET_SUFFIXES, STREETS, URBAN_AREAS,
)

DEFAULT_VERSION_START = datetime(2015, 1, 1)
NON_COMP_ACQUISITION_DAYS = 395          # roughly 13 months
ACQUISITION_SHARE = 0.03
CONVERSION_SHARE = 0.013
TIGER_SHARE = 0.05
SOFT_GOODS_SHARE = 0.10
PLANNED_RENOVATION_SHARE = 0.03
STORY_RENOVATION_HOTELS = 4
RENOVATION_DISTRICT_GROWTH = 0.02
GROWTH_MIN, GROWTH_MAX = -0.08, 0.20
EMPTY_LEVELS = {f"level_{k}_{part}": None for k in range(5, 11) for part in ("name", "value")}


@dataclass(frozen=True)
class Portfolio:
    dim_property: pd.DataFrame
    dim_property_extended: pd.DataFrame
    dim_property_hierarchy: pd.DataFrame
    fact_property_hierarchy: pd.DataFrame
    dim_property_segment: pd.DataFrame
    fact_property_segment: pd.DataFrame
    dim_property_renovation: pd.DataFrame
    fact_property_renovation: pd.DataFrame
    sim_inputs: pd.DataFrame
    districts: pd.DataFrame

    def frames(self) -> dict[str, pd.DataFrame]:
        return {name: getattr(self, name) for name in (
            "dim_property", "dim_property_extended", "dim_property_hierarchy", "fact_property_hierarchy",
            "dim_property_segment", "fact_property_segment", "dim_property_renovation", "fact_property_renovation",
        )}


def allocate(total: int, weights) -> list[int]:
    """Split `total` into integer parts proportional to `weights` (largest-remainder method)."""
    w = np.asarray(weights, dtype=float)
    raw = total * w / w.sum()
    base = np.floor(raw).astype(int)
    order = np.argsort(-(raw - base), kind="stable")
    base[order[: total - base.sum()]] += 1
    return base.tolist()


def _layout(cfg: GenConfig) -> list[dict]:
    """Assign every property to a region, market, and district."""
    props = []
    region_counts = allocate(cfg.scale_properties, [1] * len(REGIONS))
    for (region, division, leader_title, markets), n_region in zip(REGIONS, region_counts):
        if n_region == 0:
            continue
        slots = []
        for market, n_market in zip(markets, allocate(n_region, MARKET_WEIGHTS)):
            slots.extend((market, k) for k in range(n_market))
        n_districts = max(1, round(n_region / 10))
        for d, chunk in enumerate(np.array_split(np.arange(n_region), n_districts)):
            for j in chunk:
                market, k = slots[j]
                props.append({"division_name": division, "region_name": region, "leader_title": leader_title,
                              "district_name": f"{region} District {d + 1}", "market": market[0],
                              "market_info": market, "market_slot": k})
    for i, p in enumerate(props):
        p["prop_index"] = i
        p["bk_property_id"] = str(1001 + i)
    return props


def _renovation_status(start: date, end: date, as_of: date) -> str:
    return "Planned" if start > as_of else "Complete" if end < as_of else "In Progress"


def build_portfolio(cfg: GenConfig) -> Portfolio:
    rng = np.random.default_rng([cfg.seed, 101])
    stories = cfg.stories
    props = _layout(cfg)
    n = len(props)

    brand_codes = []
    for code, count in zip(BRANDS, allocate(n, [b["share"] for b in BRANDS.values()])):
        brand_codes.extend([code] * count)
    brand_codes = list(rng.permutation(brand_codes))

    districts = sorted({p["district_name"] for p in props})
    reno_candidates = sorted(d for d in districts if d.startswith(RENOVATION_REGION + " "))
    reno_district = reno_candidates[min(1, len(reno_candidates) - 1)] if reno_candidates else districts[0]
    dm_candidates = sorted(d for d in districts if d.startswith(DM_CHANGE_REGION + " ") and d != reno_district)
    dm_change_district = dm_candidates[0] if dm_candidates else None
    reno_hotels = [p["prop_index"] for p in props if p["district_name"] == reno_district][:STORY_RENOVATION_HOTELS]
    others = [p["prop_index"] for p in props if p["district_name"] != reno_district]
    acquired = set(rng.choice(others, size=min(len(others), round(n * ACQUISITION_SHARE)), replace=False).tolist()) if others else set()
    esss = [i for i in others if brand_codes[i] == "ESSS" and i not in acquired]
    converted = set(rng.choice(esss, size=min(len(esss), round(n * CONVERSION_SHARE)), replace=False).tolist()) if esss else set()

    # District revenue growth: a spread from about -8% to +20% with clear leaders and laggards.
    growth = {d: GROWTH_MIN + (GROWTH_MAX - GROWTH_MIN) * float(rng.beta(2.4, 3.0)) for d in districts}
    ranked = sorted((d for d in districts if d != reno_district), key=growth.get)
    if len(ranked) >= 2:
        growth[ranked[0]], growth[ranked[-1]] = GROWTH_MIN, GROWTH_MAX
    growth[reno_district] = RENOVATION_DISTRICT_GROWTH

    leaders = iter(person_names(np.random.default_rng([cfg.seed, 102]), len(DIVISIONS) + len(REGIONS) + len(districts) + 1 + n))
    dvp = {d: next(leaders) for d in DIVISIONS}
    rvp = {r[0]: next(leaders) for r in REGIONS}
    dm = {d: next(leaders) for d in districts}
    replacement_dm = next(leaders)

    for p in props:
        i = p["prop_index"]
        brand = "ESAS" if i in converted else brand_codes[i]
        p["brand_cd"], p["original_brand_cd"] = brand, brand_codes[i]
        info = BRANDS[brand]
        _, state, lat, lon, tz, zip3, adr_factor = p["market_info"]
        lo, hi = BRANDS[p["original_brand_cd"]]["rooms"]
        area = AREAS[(p["market_slot"] + i) % len(AREAS)]
        if p["market_slot"] >= len(AREAS):
            area = f"{area} II"
        p.update({
            "city": p["market"], "state": state, "tz": tz, "zip3": zip3, "adr_factor": adr_factor,
            "room_count": int(rng.integers(lo, hi + 1)), "area": area,
            "latitude": round(lat + float(rng.uniform(-0.12, 0.12)), 5),
            "longitude": round(lon + float(rng.uniform(-0.12, 0.12)), 5),
            "address": f"{int(rng.integers(100, 9900))} {STREETS[int(rng.integers(len(STREETS)))]} "
                       f"{STREET_SUFFIXES[int(rng.integers(len(STREET_SUFFIXES)))]}",
            "postal": f"{zip3}{int(rng.integers(0, 100)):02d}",
            "ownership": "Franchised" if rng.random() < 0.45 else "Owned",
            "base_occ": float(np.clip(rng.normal(0.72, 0.06), 0.55, 0.88)),
            "adr_noise": float(rng.normal(1.0, 0.05)),
            "open_date": date(1997, 1, 1) + timedelta(days=int(rng.integers(0, 8000))),
            "gm": next(leaders),
        })
        p["base_adr"] = round(info["adr"] * adr_factor * p["adr_noise"], 2)
        p["location_type"] = ("Airport" if area.startswith("Airport") else "Urban" if area.split(" II")[0] in URBAN_AREAS
                              else "Interstate" if area.startswith("Interstate")
                              else "Small Metro/Town" if adr_factor < 0.88 else "Suburban")
        p["acquisition_date"] = (cfg.story_anchor_date - timedelta(days=int(rng.integers(30, 361)))) if i in acquired else None
        p["start_date"] = max(cfg.sim_start_date, p["acquisition_date"]) if p["acquisition_date"] else cfg.sim_start_date
        p["dm_name"] = dm[p["district_name"]]

    tiger_count = max(1, round(n * TIGER_SHARE)) if n >= 20 else 0
    tiger = set(sorted((p["prop_index"] for p in props if p["prop_index"] not in acquired),
                       key=lambda i: props[i]["base_occ"])[:tiger_count])

    # Renovation projects per property: (type, start, end, room batches, demand factor, capex per room).
    projects: dict[int, list[tuple]] = {p["prop_index"]: [] for p in props}
    for i in reno_hotels:
        projects[i].append(("Full Renovation", stories.renovation_start, stories.renovation_end, 3, 0.88, 18000.0))
    for i in converted:
        projects[i].append(("Brand Conversion", stories.brand_conversion - timedelta(days=30), stories.brand_conversion, 10, 0.95, 8000.0))
    eligible = [p["prop_index"] for p in props if p["prop_index"] not in set(reno_hotels) | converted | acquired]
    soft = rng.choice(eligible, size=min(len(eligible), round(n * SOFT_GOODS_SHARE)), replace=False).tolist() if eligible else []
    latest_soft_start = cfg.story_anchor_date - timedelta(days=150)
    soft_window = max(1, (latest_soft_start - (cfg.history_start_date + timedelta(days=30))).days)
    for i in soft:
        start = cfg.history_start_date + timedelta(days=30 + int(rng.integers(0, soft_window)))
        projects[i].append(("Soft Goods Refresh", start, start + timedelta(days=21), 10, 0.97, 3500.0))
    remaining = [i for i in eligible if i not in set(soft)]
    planned = rng.choice(remaining, size=min(len(remaining), round(n * PLANNED_RENOVATION_SHARE)), replace=False).tolist() if remaining else []
    for i in planned:
        start = cfg.story_anchor_date + timedelta(days=int(rng.integers(45, 121)))
        projects[i].append(("Soft Goods Refresh", start, start + timedelta(days=21), 10, 0.97, 3500.0))

    as_of = cfg.as_of_date
    load_ts = cfg.dimension_load_ts
    property_rows, extended_rows, hierarchy_rows, bridge_h, bridge_s, reno_rows, bridge_r, sim_rows = ([] for _ in range(8))
    segment_names = {}
    for p in props:
        i, pid = p["prop_index"], p["bk_property_id"]
        info = BRANDS[p["brand_cd"]]
        versions = [(p["original_brand_cd"], DEFAULT_VERSION_START, datetime.combine(stories.brand_conversion, datetime.min.time()), False)] if i in converted else []
        start_current = datetime.combine(stories.brand_conversion, datetime.min.time()) if i in converted else DEFAULT_VERSION_START
        versions.append((p["brand_cd"], start_current, OPEN_ENDED, True))
        for v, (brand, v_start, v_end, current) in enumerate(versions, start=1):
            b = BRANDS[brand]
            property_rows.append({
                "dim_property_id": f"DP-{pid}-{v}", "bk_property_id": pid, "property_code": pid,
                "property_name": f"{b['brand_name']} - {p['city']} - {p['area']}", "brand_cd": brand,
                "brand_name": b["brand_name"], "market_name": p["market"], "submarket_name": f"{p['city']} {p['area']}",
                "ownership_type": p["ownership"], "address_line_1": p["address"], "city_name": p["city"],
                "state_cd": p["state"], "postal_cd": p["postal"], "country_cd": "US", "latitude": p["latitude"],
                "longitude": p["longitude"], "time_zone_name": p["tz"], "room_count": p["room_count"],
                "property_status": "Open", "_version_start": v_start, "_version_end": v_end, "_is_current": current,
            })
        full_reno_window = any(t == "Full Renovation" and e >= as_of - timedelta(days=395) and s <= as_of
                               for t, s, e, *_ in projects[i])
        if p["acquisition_date"] and (as_of - p["acquisition_date"]).days < NON_COMP_ACQUISITION_DAYS:
            comp, reason = "Non-Comp", "Acquired within 13 months"
        elif full_reno_window:
            comp, reason = "Non-Comp", "Full renovation in comparison window"
        else:
            comp, reason = "Comp", None
        franchised = p["ownership"] == "Franchised"
        extended_rows.append({
            "dim_property_extended_id": f"DPX-{pid}", "bk_property_id": pid, "open_date": p["open_date"],
            "acquisition_date": p["acquisition_date"], "disposition_date": None,
            "str_property_id": f"STR{60000 + i}", "str_market_name": f"{p['market']}, {p['state']}",
            "str_submarket_name": f"{p['city']} {p['area']}", "str_chain_scale": info["chain_scale"],
            "str_class": info["str_class"], "str_location_type": p["location_type"], "comp_status": comp,
            "comp_status_reason": reason, "pet_fee_amount": 25.0,
            "franchise_fee_pct": round(float(rng.uniform(5.0, 6.5)), 2) if franchised else None,
            "management_fee_pct": 3.0 if franchised else None,
        })
        ops = {"dim_property_hierarchy_id": f"DPH-OPS-{pid}-1", "bk_property_hierarchy_id": f"OPS-{pid}",
               "hierarchy_name": "Operations", "level_1_name": "Division", "level_1_value": p["division_name"],
               "level_2_name": "Region", "level_2_value": p["region_name"], "level_3_name": "District",
               "level_3_value": p["district_name"], "level_4_name": "Property",
               "level_4_value": property_rows[-1]["property_name"], **EMPTY_LEVELS,
               "_version_start": DEFAULT_VERSION_START, "_version_end": OPEN_ENDED, "_is_current": True}
        hierarchy_rows.append(ops)
        leader_versions = [(p["dm_name"], DEFAULT_VERSION_START, OPEN_ENDED, True)]
        if p["district_name"] == dm_change_district:
            change = datetime.combine(stories.dm_change, datetime.min.time())
            leader_versions = [(p["dm_name"], DEFAULT_VERSION_START, change, False), (replacement_dm, change, OPEN_ENDED, True)]
        for v, (dm_name, v_start, v_end, current) in enumerate(leader_versions, start=1):
            hierarchy_rows.append({
                "dim_property_hierarchy_id": f"DPH-LDR-{pid}-{v}", "bk_property_hierarchy_id": f"LDR-{pid}",
                "hierarchy_name": "Leadership", "level_1_name": "DVP", "level_1_value": dvp[p["division_name"]],
                "level_2_name": p["leader_title"], "level_2_value": rvp[p["region_name"]], "level_3_name": "DM",
                "level_3_value": dm_name, "level_4_name": "GM", "level_4_value": p["gm"], **EMPTY_LEVELS,
                "_version_start": v_start, "_version_end": v_end, "_is_current": current})
        for kind in ("OPS", "LDR"):
            bridge_h.append({"fact_property_hierarchy_id": f"FPH-{pid}-{kind}", "bk_property_id": pid,
                             "bk_property_hierarchy_id": f"{kind}-{pid}", "member_flag": True})
        for seg_type, seg_name in (("Location", p["location_type"]), ("Service Level", info["service_level"]),
                                   ("Program", "Tiger Site" if i in tiger else "Standard Operations")):
            seg_id = "SEG-" + "".join(w[0] for w in seg_type.split()) + "-" + seg_name.upper().replace("/", "-").replace(" ", "-")
            segment_names[seg_id] = (seg_type, seg_name)
            bridge_s.append({"fact_property_segment_id": f"FPS-{pid}-{seg_id}", "bk_property_id": pid,
                             "bk_property_segment_id": seg_id, "member_flag": True})
        renos = []
        for k, (kind, start, end, batches, demand, capex) in enumerate(sorted(projects[i], key=lambda r: r[1]), start=1):
            rid = f"REN-{pid}-{k}"
            status = _renovation_status(start, end, as_of)
            reno_rows.append({
                "dim_property_renovation_id": f"DPRN-{rid}", "bk_property_renovation_id": rid,
                "renovation_type": kind,
                "renovation_phase": {"Planned": "Design", "In Progress": "Phase 1 - Guest Rooms", "Complete": "Closeout"}[status],
                "renovation_status": status, "renovation_start_date": start, "renovation_end_date": end,
                "rooms_impacted_count": p["room_count"], "capex_budget_amount": round(capex * p["room_count"], 2)})
            bridge_r.append({"fact_property_renovation_id": f"FPR-{pid}-{k}", "bk_property_id": pid,
                             "bk_property_renovation_id": rid, "member_flag": True})
            renos.append([cfg.day_index(start), cfg.day_index(end), batches, demand])
        r_d = growth[p["district_name"]]
        sim_rows.append({
            "bk_property_id": pid, "prop_index": i, "room_count": p["room_count"], "brand_cd": p["brand_cd"],
            "market_name": p["market"], "district_name": p["district_name"], "start_date": p["start_date"],
            "base_occ": p["base_occ"], "base_adr": p["base_adr"],
            "occ_growth": (1 + r_d) / (1 + ADR_GROWTH) - 1, "adr_growth": ADR_GROWTH,
            "ramp_market": p["market"] == RAMP_MARKET, "renos_json": json.dumps(renos),
        })

    segment_rows = [{"dim_property_segment_id": f"D{sid}", "bk_property_segment_id": sid, "segment_type": t,
                     "segment_name": name, "segment_desc": f"{t} segment: {name}"}
                    for sid, (t, name) in sorted(segment_names.items())]

    def finish(rows, source, versioned=False):
        df = pd.DataFrame(rows)
        if versioned:
            meta = df[["_version_start", "_version_end", "_is_current"]]
            df = with_meta(df.drop(columns=list(meta.columns)), source, load_ts, meta["_version_start"].to_numpy(),
                           meta["_version_end"].to_numpy(), meta["_is_current"].to_numpy())
        else:
            df = with_meta(df, source, load_ts, DEFAULT_VERSION_START)
        return df

    dim_property = finish(property_rows, "ESA.MDM.PROPERTY", versioned=True)
    dim_property["room_count"] = dim_property["room_count"].astype("int64")
    extended = finish(extended_rows, "ESA.MDM.PROPERTY")
    hierarchy = finish(hierarchy_rows, "ESA.MDM.HIERARCHY", versioned=True)
    reno = finish(reno_rows, "ESA.CAPEX.RENOVATION") if reno_rows else pd.DataFrame()
    district_frame = pd.DataFrame([
        {"district_name": d, "region_name": next(p["region_name"] for p in props if p["district_name"] == d),
         "division_name": next(p["division_name"] for p in props if p["district_name"] == d),
         "dm_name": dm[d] if d != dm_change_district else replacement_dm, "revenue_growth": growth[d],
         "is_renovation_district": d == reno_district, "is_dm_change_district": d == dm_change_district,
         "hotel_count": sum(p["district_name"] == d for p in props)} for d in districts])
    return Portfolio(
        dim_property=dim_property, dim_property_extended=extended, dim_property_hierarchy=hierarchy,
        fact_property_hierarchy=finish(bridge_h, "ESA.MDM.HIERARCHY"),
        dim_property_segment=finish(segment_rows, "ESA.MDM.SEGMENT"),
        fact_property_segment=finish(bridge_s, "ESA.MDM.SEGMENT"),
        dim_property_renovation=reno, fact_property_renovation=finish(bridge_r, "ESA.CAPEX.RENOVATION") if bridge_r else pd.DataFrame(),
        sim_inputs=pd.DataFrame(sim_rows), districts=district_frame,
    )
