"""Static reference data: brands, geography, channels, rates, promotions, room types, LOS, accounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from esa_resstay_demo.data.config import OPEN_ENDED, GenConfig
from esa_resstay_demo.data.frames import with_meta
from esa_resstay_demo.data.names import company_name, email_for, person_names

REFERENCE_VERSION_START = datetime(2015, 1, 1)

BRANDS = {
    "ESAS": {"brand_name": "Extended Stay America Suites", "share": 0.60, "adr": 75.0, "rooms": (90, 130),
             "chain_scale": "Economy", "str_class": "Economy Class", "service_level": "Economy Extended Stay"},
    "ESSS": {"brand_name": "Extended Stay America Select Suites", "share": 0.30, "adr": 60.0, "rooms": (80, 120),
             "chain_scale": "Economy", "str_class": "Economy Class", "service_level": "Value Extended Stay"},
    "ESAP": {"brand_name": "Extended Stay America Premier Suites", "share": 0.10, "adr": 95.0, "rooms": (100, 140),
             "chain_scale": "Midscale", "str_class": "Midscale Class", "service_level": "Midscale Extended Stay"},
}

DIVISIONS = ("East", "Central", "South", "West")

# (market, state, latitude, longitude, time zone, zip3, ADR factor)
REGIONS = (
    ("Northeast", "East", "RVP", (("Boston", "MA", 42.36, -71.06, "America/New_York", "021", 1.30),
                                  ("Hartford", "CT", 41.76, -72.68, "America/New_York", "061", 1.05),
                                  ("Providence", "RI", 41.82, -71.41, "America/New_York", "029", 1.05),
                                  ("Albany", "NY", 42.65, -73.75, "America/New_York", "122", 0.95))),
    ("Mid-Atlantic", "East", "RVP", (("Philadelphia", "PA", 39.95, -75.17, "America/New_York", "191", 1.10),
                                     ("Baltimore", "MD", 39.29, -76.61, "America/New_York", "212", 1.00),
                                     ("Arlington", "VA", 38.88, -77.10, "America/New_York", "222", 1.25),
                                     ("Newark", "NJ", 40.74, -74.17, "America/New_York", "071", 1.20))),
    ("Southeast", "East", "RDO", (("Atlanta", "GA", 33.75, -84.39, "America/New_York", "303", 1.00),
                                  ("Charlotte", "NC", 35.23, -80.84, "America/New_York", "282", 0.98),
                                  ("Raleigh", "NC", 35.78, -78.64, "America/New_York", "276", 1.00),
                                  ("Nashville", "TN", 36.16, -86.78, "America/Chicago", "372", 1.08))),
    ("Florida", "East", "RDO", (("Orlando", "FL", 28.54, -81.38, "America/New_York", "328", 1.02),
                                ("Tampa", "FL", 27.95, -82.46, "America/New_York", "336", 1.00),
                                ("Jacksonville", "FL", 30.33, -81.66, "America/New_York", "322", 0.92),
                                ("Miami", "FL", 25.76, -80.19, "America/New_York", "331", 1.22))),
    ("Great Lakes", "Central", "RVP", (("Chicago", "IL", 41.88, -87.63, "America/Chicago", "606", 1.12),
                                       ("Detroit", "MI", 42.33, -83.05, "America/Detroit", "482", 0.92),
                                       ("Milwaukee", "WI", 43.04, -87.91, "America/Chicago", "532", 0.90),
                                       ("Indianapolis", "IN", 39.77, -86.16, "America/Indiana/Indianapolis", "462", 0.92))),
    ("Ohio Valley", "Central", "RDO", (("Columbus", "OH", 39.96, -83.00, "America/New_York", "432", 0.93),
                                       ("Cincinnati", "OH", 39.10, -84.51, "America/New_York", "452", 0.92),
                                       ("Cleveland", "OH", 41.50, -81.69, "America/New_York", "441", 0.90),
                                       ("Louisville", "KY", 38.25, -85.76, "America/Kentucky/Louisville", "402", 0.90))),
    ("Heartland", "Central", "RDO", (("Kansas City", "MO", 39.10, -94.58, "America/Chicago", "641", 0.90),
                                     ("St. Louis", "MO", 38.63, -90.20, "America/Chicago", "631", 0.92),
                                     ("Omaha", "NE", 41.26, -95.93, "America/Chicago", "681", 0.88),
                                     ("Oklahoma City", "OK", 35.47, -97.52, "America/Chicago", "731", 0.86))),
    ("Upper Midwest", "Central", "RVP", (("Minneapolis", "MN", 44.98, -93.27, "America/Chicago", "554", 1.00),
                                         ("Des Moines", "IA", 41.59, -93.62, "America/Chicago", "503", 0.86),
                                         ("Madison", "WI", 43.07, -89.40, "America/Chicago", "537", 0.92),
                                         ("Sioux Falls", "SD", 43.55, -96.73, "America/Chicago", "571", 0.84))),
    ("Texas", "South", "RVP", (("Dallas", "TX", 32.78, -96.80, "America/Chicago", "752", 1.00),
                               ("Fort Worth", "TX", 32.76, -97.33, "America/Chicago", "761", 0.95),
                               ("Austin", "TX", 30.27, -97.74, "America/Chicago", "787", 1.10),
                               ("San Antonio", "TX", 29.42, -98.49, "America/Chicago", "782", 0.92))),
    ("Gulf Coast", "South", "RDO", (("Houston", "TX", 29.76, -95.37, "America/Chicago", "770", 0.98),
                                    ("New Orleans", "LA", 29.95, -90.07, "America/Chicago", "701", 1.02),
                                    ("Baton Rouge", "LA", 30.45, -91.15, "America/Chicago", "708", 0.88),
                                    ("Corpus Christi", "TX", 27.80, -97.40, "America/Chicago", "784", 0.85))),
    ("Mid-South", "South", "RDO", (("Memphis", "TN", 35.15, -90.05, "America/Chicago", "381", 0.86),
                                   ("Birmingham", "AL", 33.52, -86.80, "America/Chicago", "352", 0.86),
                                   ("Little Rock", "AR", 34.75, -92.29, "America/Chicago", "722", 0.84),
                                   ("Jackson", "MS", 32.30, -90.18, "America/Chicago", "392", 0.82))),
    ("Desert Southwest", "South", "RVP", (("Phoenix", "AZ", 33.45, -112.07, "America/Phoenix", "850", 1.00),
                                          ("Tucson", "AZ", 32.22, -110.97, "America/Phoenix", "857", 0.90),
                                          ("Albuquerque", "NM", 35.08, -106.65, "America/Denver", "871", 0.88),
                                          ("El Paso", "TX", 31.76, -106.49, "America/Denver", "799", 0.84))),
    ("Mountain", "West", "RVP", (("Denver", "CO", 39.74, -104.99, "America/Denver", "802", 1.08),
                                 ("Salt Lake City", "UT", 40.76, -111.89, "America/Denver", "841", 1.00),
                                 ("Boise", "ID", 43.62, -116.20, "America/Boise", "837", 0.92),
                                 ("Colorado Springs", "CO", 38.83, -104.82, "America/Denver", "809", 0.92))),
    ("Pacific Northwest", "West", "RDO", (("Seattle", "WA", 47.61, -122.33, "America/Los_Angeles", "981", 1.30),
                                          ("Portland", "OR", 45.52, -122.68, "America/Los_Angeles", "972", 1.08),
                                          ("Spokane", "WA", 47.66, -117.43, "America/Los_Angeles", "992", 0.88),
                                          ("Tacoma", "WA", 47.25, -122.44, "America/Los_Angeles", "984", 1.05))),
    ("California", "West", "RVP", (("Los Angeles", "CA", 34.05, -118.24, "America/Los_Angeles", "900", 1.35),
                                   ("San Diego", "CA", 32.72, -117.16, "America/Los_Angeles", "921", 1.25),
                                   ("Sacramento", "CA", 38.58, -121.49, "America/Los_Angeles", "958", 1.05),
                                   ("San Jose", "CA", 37.34, -121.89, "America/Los_Angeles", "951", 1.40))),
)
MARKET_WEIGHTS = (0.35, 0.25, 0.22, 0.18)
RENOVATION_REGION = "Texas"
DM_CHANGE_REGION = "Great Lakes"
RAMP_MARKET = "Phoenix"

AREAS = (
    "North", "Airport", "Downtown", "Medical Center", "University", "Business Park", "Convention Center",
    "Uptown", "Lakeside", "Tech Center", "Riverside", "Southpoint", "Northwest", "Galleria", "Midtown",
    "Industrial Park", "Interstate", "East", "West", "South",
)
URBAN_AREAS = {"Downtown", "Midtown", "Uptown", "Convention Center"}
STREETS = (
    "Commerce", "Park Center", "Gateway", "Corporate", "Meridian", "Executive", "Technology", "Medical",
    "University", "Airport", "Lakeview", "Harbor", "Summit", "Crossroads", "Industrial", "Riverwalk",
    "Northpoint", "Westgate", "Eastgate", "Southpark",
)
STREET_SUFFIXES = ("Dr", "Blvd", "Pkwy", "Way", "Ave", "Rd")

# Channels: (bk, network, name, platform, partner, base share, annual drift, mean lead days,
#            cancel rate, reservation source, LOS-tier affinity for 0-6 / 7-14 / 15-29 / 30+)
CHANNELS = (
    ("CH01", "Direct", "Brand Web", "Web", "ESA", 0.24, 0.05, 9, 0.10, "Brand Web", (1.1, 1.0, 0.9, 0.8)),
    ("CH02", "Direct", "Mobile App", "App", "ESA", 0.10, 0.06, 6, 0.08, "Mobile App", (1.1, 1.0, 0.9, 0.8)),
    ("CH03", "Direct", "Call Center", "Voice", "ESA Reservations", 0.18, -0.05, 5, 0.10, "CRS", (0.8, 1.0, 1.2, 1.4)),
    ("CH04", "Direct", "Walk-In", "Property", "ESA", 0.08, -0.02, 0, 0.0, "HotelKey PMS", (1.3, 0.9, 0.7, 0.6)),
    ("CH05", "Indirect", "OTA - Expedia", "Web", "Expedia Group", 0.14, 0.01, 12, 0.20, "OTA Connect", (1.3, 0.8, 0.5, 0.3)),
    ("CH06", "Indirect", "OTA - Booking.com", "Web", "Booking Holdings", 0.08, 0.01, 14, 0.20, "OTA Connect", (1.3, 0.8, 0.5, 0.3)),
    ("CH07", "Indirect", "GDS", "GDS", "Sabre / Amadeus", 0.05, -0.02, 16, 0.12, "GDS", (1.1, 1.0, 0.8, 0.6)),
    ("CH08", "Direct", "Corporate Sales", "Sales", "ESA Corporate Sales", 0.13, 0.02, 20, 0.08, "CRS", (0.5, 1.0, 1.5, 2.0)),
)
CHANNEL_INDEX = {row[0]: i for i, row in enumerate(CHANNELS)}

# Rate segments: (bk, name, category, code, type, partner, ADR multiplier)
RATE_SEGMENTS = (
    ("RS01", "Best Available Rate", "Transient", "BAR", "Public", None, 1.10),
    ("RS02", "Weekly Rate", "Extended Stay", "WKLY", "Public", None, 0.95),
    ("RS03", "Monthly Rate", "Extended Stay", "MNTH", "Public", None, 0.86),
    ("RS04", "Corporate Negotiated", "Corporate", "CORP", "Negotiated", "Corporate Accounts", 0.90),
    ("RS05", "Government / Military", "Government", "GOV", "Qualified", "Per Diem Programs", 0.88),
    ("RS06", "AAA / Senior", "Discount", "AAA", "Qualified", "AAA / AARP", 0.92),
    ("RS07", "OTA Merchant", "Wholesale", "OTAM", "Merchant", "Online Travel Agencies", 1.05),
    ("RS08", "Airline Crew", "Contract", "CREW", "Contract", "Airline Crew Programs", 0.80),
    ("RS09", "Relocation / Insurance", "Contract", "RELO", "Contract", "Relocation & Insurance Partners", 0.93),
    ("RS10", "Complimentary", "Complimentary", "COMP", "Non-Revenue", None, 0.0),
)
SEGMENT_INDEX = {row[0]: i for i, row in enumerate(RATE_SEGMENTS)}
COMP_SEGMENT = "RS10"
COMP_SHARE = 0.004
# Weights by channel group and LOS tier.
SEGMENT_WEIGHTS = {
    "ota": {"RS07": 0.80, "RS01": 0.20},
    "corporate": {"RS04": 0.55, "RS09": 0.30, "RS08": 0.10, "RS05": 0.05},
    "gds": {"RS04": 0.50, "RS01": 0.35, "RS05": 0.15},
    "direct": (
        {"RS01": 0.62, "RS06": 0.15, "RS05": 0.10, "RS04": 0.08, "RS08": 0.05},
        {"RS02": 0.58, "RS01": 0.15, "RS04": 0.15, "RS05": 0.07, "RS06": 0.05},
        {"RS02": 0.48, "RS03": 0.12, "RS04": 0.22, "RS05": 0.13, "RS09": 0.05},
        {"RS03": 0.55, "RS04": 0.20, "RS09": 0.17, "RS05": 0.08},
    ),
}
# Segments whose stays carry a CRM account, and the industries eligible for each.
ACCOUNT_SEGMENTS = {
    "RS03": ("Healthcare Staffing", "Construction", "Energy", "Rail"),
    "RS04": ("Construction", "Rail", "Energy", "Technology", "Manufacturing", "Logistics",
             "Healthcare Staffing", "Travel Management"),
    "RS05": ("Government",),
    "RS08": ("Airline",),
    "RS09": ("Insurance", "Relocation"),
}
MONTHLY_ACCOUNT_SHARE = 0.30   # share of RS03 stays booked through an account

# Promotions: (code, name, campaign, discount type, value, min LOS, max LOS, start/end offset days from anchor)
PROMOTIONS = (
    ("NONE", "No Promotion", "None", "None", 0.0, None, None, None, None),
    ("STAY7", "Stay 7+ and Save", "Extended Stay Value 2026", "Percent", 15.0, 7, 14, -120, 60),
    ("MONTH30", "Monthly Saver", "Long-Term Living", "Percent", 10.0, 30, None, -900, 365),
    ("APPONLY", "App Exclusive Rate", "Mobile First", "Percent", 8.0, 1, None, -900, 365),
    ("BOOKEARLY", "Book Early Discount", "Advance Purchase", "Percent", 12.0, 1, 6, -700, -200),
    ("SENIOR", "Senior Saver", "Seasoned Traveler", "Percent", 10.0, 1, None, -900, 365),
    ("RELO", "Relocation Package", "Moving Made Easy", "Amount", 150.0, 30, None, -900, 365),
    ("WEEKEND", "Weekend Getaway", "Leisure Weekends", "Percent", 10.0, 1, 3, -600, -300),
)

# Room types: (bk, code, name, class, bed type, bed count, accessible, ADR multiplier)
ROOM_TYPES = (
    ("RT01", "SQ", "Studio Queen", "Standard", "Queen", 1, False, 1.00),
    ("RT02", "SQQ", "Studio Two Queens", "Standard", "Queen", 2, False, 1.06),
    ("RT03", "SK", "Studio King", "Standard", "King", 1, False, 1.03),
    ("RT04", "DSK", "Deluxe Studio King", "Deluxe", "King", 1, False, 1.12),
    ("RT05", "1BR", "One Bedroom Suite", "Suite", "King", 1, False, 1.30),
    ("RT06", "ASQ", "Accessible Studio Queen", "Standard", "Queen", 1, True, 1.00),
)
ROOM_MIX = {
    "ESAS": (("RT01", 0.45), ("RT02", 0.25), ("RT03", 0.25), ("RT06", 0.05)),
    "ESSS": (("RT01", 0.50), ("RT02", 0.25), ("RT03", 0.20), ("RT06", 0.05)),
    "ESAP": (("RT04", 0.40), ("RT05", 0.20), ("RT01", 0.25), ("RT02", 0.10), ("RT06", 0.05)),
}

# Length of stay: tier probabilities per stay (0-6, 7-14, 15-29, 30+) before and during Stay 7+.
TIER_PROBS = (0.720, 0.140, 0.040, 0.100)
TIER_PROBS_PROMO = (0.7004, 0.1596, 0.040, 0.100)
TIER0_WEIGHTS = (0.30, 0.22, 0.17, 0.13, 0.10, 0.08)                 # 1..6 nights
TIER1_WEIGHTS = (0.22, 0.14, 0.12, 0.11, 0.10, 0.10, 0.10, 0.11)     # 7..14 nights
LONG_STAY_EXTRA_MEAN = 25.0                                          # 30+ = 30 + geometric
MAX_LOS = 365

# Industries: (industry, account type, weight, SIC, NAICS, name words)
INDUSTRIES = (
    ("Construction", "Corporate", 0.16, "1542", "236220", ("Builders", "Construction", "Contracting", "Civil Works")),
    ("Insurance", "Insurance / Relocation", 0.10, "6411", "524210", ("Insurance Group", "Mutual", "Claims Services")),
    ("Healthcare Staffing", "Staffing Agency", 0.12, "7363", "561320", ("Nurse Staffing", "Medical Staffing", "Travel Clinicians")),
    ("Rail", "Corporate", 0.04, "4011", "482111", ("Rail Services", "Railway Maintenance", "Track Systems")),
    ("Energy", "Corporate", 0.08, "1389", "213112", ("Energy Services", "Pipeline Services", "Wind Services")),
    ("Government", "Government", 0.08, "9199", "921190", ("Public Works Authority", "Transit District", "Regional Services Agency")),
    ("Airline", "Airline", 0.03, "4512", "481111", ("Air Crew Services", "Airways Crew Operations")),
    ("Relocation", "Insurance / Relocation", 0.06, "4214", "484210", ("Relocation Partners", "Corporate Housing")),
    ("Technology", "Corporate", 0.10, "7373", "541512", ("Systems", "Technologies", "Data Services")),
    ("Manufacturing", "Corporate", 0.10, "3599", "332710", ("Manufacturing", "Industries", "Fabrication")),
    ("Logistics", "Corporate", 0.08, "4731", "488510", ("Logistics", "Freight", "Distribution")),
    ("Travel Management", "Travel Management Company", 0.05, "4724", "561510", ("Travel Management", "Corporate Travel")),
)
KEY_ACCOUNTS = (
    ("Ironwood Data Center Builders", "Construction"),
    ("Granite State Infrastructure", "Construction"),
    ("Harbor Point Insurance Group", "Insurance"),
    ("Lakeshore Mutual Claims Services", "Insurance"),
    ("Meridian Travel Clinicians", "Healthcare Staffing"),
    ("Summit Nurse Staffing", "Healthcare Staffing"),
    ("Keystone Railway Maintenance", "Rail"),
    ("Prairie Pipeline Services", "Energy"),
    ("North Star Wind Services", "Energy"),
    ("Beacon Corporate Housing", "Relocation"),
)
RAMP_ACCOUNT_ID = "CRM00001"
RAMP_ACCOUNT_SHARE = 0.35
CRM_ACCOUNT_COUNT = 3000
KEY_ACCOUNT_WEIGHT = 30.0
KEY_ACCOUNT_LONG_STAY_BOOST = 3.0
PREFERRED_SEGMENT = {
    "Corporate": "RS04", "Insurance / Relocation": "RS09", "Airline": "RS08", "Government": "RS05",
    "Staffing Agency": "RS03", "Travel Management Company": "RS04",
}
AFFILIATES = {"AAA": "American Automobile Association", "AARP": "AARP", "USAA": "USAA"}
PET_FEE_PER_NIGHT = 25.0
PET_FEE_MAX_NIGHTS = 30
EARLY_CHECKIN_FEE = 15.0


def los_tier(nights: int) -> int:
    return 0 if nights <= 6 else 1 if nights <= 14 else 2 if nights <= 29 else 3


def los_bands(nights: int) -> list[str]:
    """The ten LOS bandings on dim_los. Band 1 is the ResStay 'OTB 4 Tier'."""
    n = nights
    band1 = ("0-6", "7-14", "15-29", "30+")[los_tier(n)]
    band2 = "0-6" if n <= 6 else "7-13" if n <= 13 else "14-20" if n <= 20 else "21-27" if n <= 27 else "28+"
    band3 = "Transient (0-6)" if n <= 6 else "Extended (7+)"
    band4 = "0-3" if n <= 3 else "4-6" if n <= 6 else "7-13" if n <= 13 else "14-29" if n <= 29 else "30-59" if n <= 59 else "60+"
    band5 = "Nightly (0-6)" if n <= 6 else "Weekly (7-29)" if n <= 29 else "Monthly (30+)"
    band6 = "Short (0-3)" if n <= 3 else "Medium (4-13)" if n <= 13 else "Long (14+)"
    band7 = f"{n // 7} wk" if n < 28 else "4+ wk"
    band8 = "Under 30" if n < 30 else "30-89" if n < 90 else "90-179" if n < 180 else "180+"
    band9 = "Day Use" if n == 0 else "Single Night" if n == 1 else "2-6 Nights" if n <= 6 else "7+ Nights"
    band10 = "Hotel Stay (0-29)" if n <= 29 else "Extended Tenancy (30+)"
    return [band1, band2, band3, band4, band5, band6, band7, band8, band9, band10]


def _reference_meta(df: pd.DataFrame, cfg: GenConfig, source: str) -> pd.DataFrame:
    return with_meta(df, source, cfg.dimension_load_ts, REFERENCE_VERSION_START)


def build_dim_channel(cfg: GenConfig) -> pd.DataFrame:
    df = pd.DataFrame(
        [{"dim_channel_id": f"DCH-{bk}", "bk_channel_id": bk, "channel_network": network, "channel_name": name,
          "channel_platform": platform, "channel_partner": partner}
         for bk, network, name, platform, partner, *_ in CHANNELS]
    )
    return _reference_meta(df, cfg, "ESA.REF.CHANNEL")


def build_dim_rate_segment(cfg: GenConfig) -> pd.DataFrame:
    df = pd.DataFrame(
        [{"dim_rate_segment_id": f"DRS-{bk}", "bk_rate_segment_id": bk, "rate_segment_name": name,
          "rate_category": category, "rate_code": code, "rate_type": rate_type, "rate_partner": partner}
         for bk, name, category, code, rate_type, partner, _ in RATE_SEGMENTS]
    )
    return _reference_meta(df, cfg, "ESA.REF.RATE")


def promotion_window(cfg: GenConfig, code: str) -> tuple[date | None, date | None]:
    for row in PROMOTIONS:
        if row[0] == code:
            start, end = row[7], row[8]
            if start is None:
                return None, None
            anchor = cfg.story_anchor_date
            return anchor + timedelta(days=start), anchor + timedelta(days=end)
    raise KeyError(code)


def build_dim_promotion(cfg: GenConfig) -> pd.DataFrame:
    rows = []
    for code, name, campaign, discount_type, value, min_los, max_los, _, _ in PROMOTIONS:
        start, end = promotion_window(cfg, code)
        rows.append({"dim_promotion_id": f"DPR-{code}", "bk_promo_cd": code, "promotion_name": name,
                     "campaign_name": campaign, "discount_type": discount_type, "discount_value": value,
                     "min_los_nights": min_los, "max_los_nights": max_los,
                     "promo_start_date": start, "promo_end_date": end})
    df = pd.DataFrame(rows)
    for col in ("min_los_nights", "max_los_nights"):
        df[col] = df[col].astype("Int64")
    return _reference_meta(df, cfg, "ESA.REF.PROMOTION")


def build_dim_room_type(cfg: GenConfig) -> pd.DataFrame:
    df = pd.DataFrame(
        [{"dim_room_type_id": f"DRT-{bk}", "bk_room_type_id": bk, "room_type_cd": code, "room_type_name": name,
          "room_class": room_class, "bed_type": bed, "bed_count": beds, "accessible_flag": accessible,
          "smoking_flag": False}
         for bk, code, name, room_class, bed, beds, accessible, _ in ROOM_TYPES]
    )
    return _reference_meta(df, cfg, "ESA.REF.ROOMTYPE")


def build_dim_los(cfg: GenConfig) -> pd.DataFrame:
    rows = []
    for n in range(MAX_LOS + 1):
        row = {"dim_los_id": f"DLOS-{n:03d}", "bk_los_id": str(n), "los_nights": n}
        row.update({f"los_band_{i}": band for i, band in enumerate(los_bands(n), start=1)})
        rows.append(row)
    return _reference_meta(pd.DataFrame(rows), cfg, "ESA.REF.LOS")


def build_dim_crm_account(cfg: GenConfig) -> pd.DataFrame:
    """3,000 synthetic B2B accounts: ten key accounts first, then a long tail."""
    rng = np.random.default_rng([cfg.seed, 301])
    industries = [row[0] for row in INDUSTRIES]
    by_industry = {row[0]: row for row in INDUSTRIES}
    weights = np.array([row[2] for row in INDUSTRIES])
    owners = person_names(np.random.default_rng([cfg.seed, 302]), 40)
    markets = [(m[0], m[1], region[1]) for region in REGIONS for m in region[3]]
    used: set[str] = set(name for name, _ in KEY_ACCOUNTS)
    rows = []
    for i in range(CRM_ACCOUNT_COUNT):
        bk = f"CRM{i + 1:05d}"
        if i < len(KEY_ACCOUNTS):
            name, industry = KEY_ACCOUNTS[i]
            tier, key = "Platinum", True
        else:
            industry = industries[rng.choice(len(industries), p=weights / weights.sum())]
            name = company_name(rng, by_industry[industry][5], used)
            pct = i / CRM_ACCOUNT_COUNT
            tier = "Gold" if pct < 0.05 else "Silver" if pct < 0.25 else "Bronze"
            key = False
        _, account_type, _, sic, naics, _ = by_industry[industry]
        city, state, division = markets[rng.integers(len(markets))]
        employees = int(np.exp(rng.normal(6.0 if not key else 9.0, 1.2)))
        created = date(2005, 1, 1) + timedelta(days=int(rng.integers(0, 7300)))
        owner = owners[rng.integers(len(owners))]
        status_draw = rng.random()
        status = "Active" if key or status_draw < 0.92 else "Inactive" if status_draw < 0.97 else "Prospect"
        rows.append({
            "dim_crm_account_id": f"DCA-{bk}", "bk_crm_account_id": bk, "account_number": f"A{700000 + i:07d}",
            "account_name": name, "account_type": account_type, "account_status": status, "account_tier": tier,
            "parent_account_id": None, "parent_account_name": None, "ultimate_parent_account_id": None,
            "ultimate_parent_account_name": None, "merged_into_account_id": None, "industry_name": industry,
            "sic_cd": sic, "naics_cd": naics, "dnb_duns_number": f"{100000000 + int(rng.integers(0, 899999999)):09d}",
            "dnb_business_name": name.upper(), "dnb_employee_count": employees,
            "dnb_annual_revenue_amount": round(employees * float(rng.uniform(90_000, 260_000)), 2),
            "dnb_hq_city_name": city, "dnb_hq_state_cd": state, "dnb_hq_country_cd": "US",
            "dnb_risk_score": int(rng.integers(1, 101)), "account_owner_name": owner,
            "account_owner_email": email_for(owner), "sales_region_name": division,
            "billing_city_name": city, "billing_state_cd": state,
            "billing_postal_cd": f"{int(rng.integers(10000, 99999)):05d}", "billing_country_cd": "US",
            "website_domain": name.lower().replace("&", "and").replace(".", "").replace(" ", "-") + ".example.com",
            "payment_terms": ("Net 30", "Net 45", "Direct Bill", "Credit Card")[int(rng.integers(4))],
            "credit_limit_amount": float(rng.choice([5_000, 10_000, 25_000, 50_000, 100_000, 250_000])),
            "account_created_date": created,
            "last_activity_date": cfg.story_anchor_date - timedelta(days=int(rng.integers(1, 400))),
            "contract_start_date": created + timedelta(days=int(rng.integers(30, 900))) if tier != "Bronze" else None,
            "contract_end_date": cfg.story_anchor_date + timedelta(days=int(rng.integers(60, 720))) if tier != "Bronze" else None,
            "preferred_rate_segment_id": PREFERRED_SEGMENT[account_type], "key_account_flag": key,
        })
    df = pd.DataFrame(rows)
    # Parents (15% of the long tail roll up to one of the first 300 accounts) and merges (3%).
    for i in range(len(KEY_ACCOUNTS), CRM_ACCOUNT_COUNT):
        draw = rng.random()
        if draw < 0.15:
            parent = int(rng.integers(0, 300))
            if parent != i:
                df.at[i, "parent_account_id"] = df.at[parent, "bk_crm_account_id"]
                df.at[i, "parent_account_name"] = df.at[parent, "account_name"]
        elif draw < 0.18:
            target = int(rng.integers(len(KEY_ACCOUNTS), 300))
            if target != i:
                df.at[i, "merged_into_account_id"] = df.at[target, "bk_crm_account_id"]
                df.at[i, "account_status"] = "Inactive"
    parent_of = dict(zip(df["bk_crm_account_id"], df["parent_account_id"]))
    name_of = dict(zip(df["bk_crm_account_id"], df["account_name"]))
    ultimate = []
    for bk in df["bk_crm_account_id"]:
        node, top = bk, None
        for _ in range(5):
            up = parent_of.get(node)
            if not up:
                break
            top, node = up, up
        ultimate.append(top)
    df["ultimate_parent_account_id"] = ultimate
    df["ultimate_parent_account_name"] = [name_of[u] if u else None for u in ultimate]
    df["dnb_employee_count"] = df["dnb_employee_count"].astype("int64")
    df["dnb_risk_score"] = df["dnb_risk_score"].astype("int64")
    return _reference_meta(df, cfg, "SALESFORCE.CRM")


def _cdf(weights) -> np.ndarray:
    cdf = np.cumsum(np.asarray(weights, dtype=float))
    cdf /= cdf[-1]
    cdf[-1] = 1.0
    return cdf


def geometric_extra(u: float, mean: float) -> int:
    """Inverse-CDF draw from a geometric distribution on {0, 1, 2, ...} with the given mean."""
    if mean <= 0:
        return 0
    p = 1.0 / (1.0 + mean)
    return int(np.floor(np.log(max(u, 1e-12)) / np.log(1.0 - p)))


@dataclass(frozen=True)
class SimReference:
    """Arrays the room simulation reads; built once and shipped to every Spark task."""
    tier_cdf: np.ndarray
    tier_cdf_promo: np.ndarray
    tier0_cdf: np.ndarray
    tier1_cdf: np.ndarray
    mean_los: float
    mean_los_promo: float
    channel_ids: tuple[str, ...]
    channel_base: np.ndarray        # [8]
    channel_drift: np.ndarray       # [8]
    channel_affinity: np.ndarray    # [4, 8]
    channel_lead: np.ndarray        # [8]
    channel_cancel: np.ndarray      # [8]
    segment_ids: tuple[str, ...]
    segment_cdf: np.ndarray         # [8 channels, 4 tiers, 10 segments]
    segment_adr: np.ndarray         # [10]
    account_ids: tuple[str, ...]
    account_cdf: dict               # (segment, long_stay) -> (indices, cdf)
    room_type_adr: dict


def _mean_los(tier_probs) -> float:
    t0 = sum((i + 1) * w for i, w in enumerate(TIER0_WEIGHTS)) / sum(TIER0_WEIGHTS)
    t1 = sum((i + 7) * w for i, w in enumerate(TIER1_WEIGHTS)) / sum(TIER1_WEIGHTS)
    t2 = 22.0
    t3 = 30.0 + LONG_STAY_EXTRA_MEAN
    return float(np.dot(tier_probs, (t0, t1, t2, t3)))


def build_sim_reference(accounts: pd.DataFrame) -> SimReference:
    segment_ids = tuple(row[0] for row in RATE_SEGMENTS)
    seg_cdf = np.zeros((len(CHANNELS), 4, len(segment_ids)))
    for c, row in enumerate(CHANNELS):
        group = {"CH05": "ota", "CH06": "ota", "CH07": "gds", "CH08": "corporate"}.get(row[0], "direct")
        for tier in range(4):
            weights = SEGMENT_WEIGHTS[group] if group != "direct" else SEGMENT_WEIGHTS["direct"][tier]
            vector = np.array([weights.get(s, 0.0) for s in segment_ids])
            seg_cdf[c, tier] = _cdf(vector)
    active = accounts[accounts["account_status"] == "Active"].reset_index(drop=True)
    account_ids = tuple(active["bk_crm_account_id"])
    rank_weight = 1.0 / np.power(np.arange(1, len(active) + 1), 0.9)
    account_cdf = {}
    for segment, industries in ACCOUNT_SEGMENTS.items():
        # The ramp account only books through the Phoenix ramp-up, so its growth stands out.
        mask = (active["industry_name"].isin(industries) & (active["bk_crm_account_id"] != RAMP_ACCOUNT_ID)).to_numpy()
        idx = np.flatnonzero(mask)
        for long_stay in (False, True):
            w = rank_weight[idx].copy()
            key = active["key_account_flag"].to_numpy()[idx]
            w[key] *= KEY_ACCOUNT_WEIGHT * (KEY_ACCOUNT_LONG_STAY_BOOST if long_stay else 1.0)
            account_cdf[(segment, long_stay)] = (idx, _cdf(w))
    return SimReference(
        tier_cdf=_cdf(TIER_PROBS), tier_cdf_promo=_cdf(TIER_PROBS_PROMO),
        tier0_cdf=_cdf(TIER0_WEIGHTS), tier1_cdf=_cdf(TIER1_WEIGHTS),
        mean_los=_mean_los(TIER_PROBS), mean_los_promo=_mean_los(TIER_PROBS_PROMO),
        channel_ids=tuple(row[0] for row in CHANNELS),
        channel_base=np.array([row[5] for row in CHANNELS]),
        channel_drift=np.array([row[6] for row in CHANNELS]),
        channel_affinity=np.array([[row[10][t] for row in CHANNELS] for t in range(4)]),
        channel_lead=np.array([row[7] for row in CHANNELS], dtype=float),
        channel_cancel=np.array([row[8] for row in CHANNELS]),
        segment_ids=segment_ids, segment_cdf=seg_cdf,
        segment_adr=np.array([row[6] for row in RATE_SEGMENTS]),
        account_ids=account_ids, account_cdf=account_cdf,
        room_type_adr={row[0]: row[7] for row in ROOM_TYPES},
    )
