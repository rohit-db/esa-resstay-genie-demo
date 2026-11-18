"""AI/BI dashboards built as Lakeview serialized JSON: the ResStay Dashboard and Occupancy Trend by Week.

Every dataset queries the certified metric views (names from the bundle target) and returns current-period and
same-window-last-year values per property, so the global filters (all property attributes) and the Time Period
parameter apply to every widget. tools/render.py writes build/dashboards/<key>.lvdash.json for the bundle.
"""

from __future__ import annotations

from dataclasses import dataclass

PERIODS = ("MTD", "QTD", "YTD", "Last 7 Days", "Last 28 Days")
VIEW_BY = ("District Manager", "RVP/RDO", "DVP")
FILTERS = (("brand", "Brand"), ("comp_status", "Comp Status"), ("dvp", "DVP"), ("rvp_rdo", "RVP/RDO"),
           ("district_manager", "District Manager"), ("market", "Market"), ("tiger_site", "Tiger Site"))
THEME = {
    "canvasBackgroundColor": {"light": "#F7F7F5", "dark": "#1F272D"},
    "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#11171C"},
    "widgetBorderColor": {"light": "#FFFFFF", "dark": "#11171C"},
    "fontColor": {"light": "#1B2A3A", "dark": "#E8ECF0"},
    "selectionColor": {"light": "#2272B4", "dark": "#8ACAFF"},
    "visualizationColors": ["#1D425C", "#F2A541", "#3C8DAD", "#C8553D", "#6A994E", "#8E7DBE", "#B0B7BF"],
    "widgetHeaderAlignment": "LEFT",
}
USD = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact",
       "decimalPlaces": {"type": "max", "places": 2}}
USD_CENTS = {"type": "number-currency", "currencyCode": "USD", "decimalPlaces": {"type": "exact", "places": 2}}
COUNT = {"type": "number-plain", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
PCT = {"type": "number-percent", "decimalPlaces": {"type": "exact", "places": 1}}


@dataclass(frozen=True)
class Names:
    catalog: str
    mart: str
    semantic: str

    def fq(self, schema: str, name: str) -> str:
        return f"{self.catalog}.{getattr(self, schema)}.{name}"


# --- SQL -----------------------------------------------------------------------------------------------------------

def _props(n: Names) -> str:
    return f"""props AS (
  SELECT property_code, property_name AS property, brand_cd AS brand, comp_status, division_name AS division,
         region_name AS region, district_name AS district, dvp_name AS dvp, rvp_rdo_name AS rvp_rdo,
         dm_name AS district_manager, gm_name AS general_manager, market_name AS market,
         CASE WHEN tiger_site_flag THEN 'Tiger Site' ELSE 'Not Tiger Site' END AS tiger_site
  FROM {n.fq('mart', 'vw_dim_property')}
)"""


def _window(n: Names) -> str:
    """The selected period ends on the latest loaded stay date; last year is the same calendar window a year earlier."""
    return f"""latest AS (
  SELECT MEASURE(`Latest Stay Date`) AS d FROM {n.fq('semantic', 'resstay_metrics')}
),
win AS (
  SELECT CASE :period WHEN 'QTD' THEN trunc(d, 'QUARTER') WHEN 'YTD' THEN trunc(d, 'YEAR')
                      WHEN 'Last 7 Days' THEN date_sub(d, 6) WHEN 'Last 28 Days' THEN date_sub(d, 27)
                      ELSE trunc(d, 'MM') END AS cur_start,
         d AS cur_end
  FROM latest
),
w AS (
  SELECT cur_start, cur_end, add_months(cur_start, -12) AS ly_start, add_months(cur_end, -12) AS ly_end FROM win
)"""


def _between(column: str, which: str) -> str:
    return f"{column} BETWEEN (SELECT {which}_start FROM w) AND (SELECT {which}_end FROM w)"


def property_period_sql(n: Names) -> str:
    rs, oc = n.fq("semantic", "resstay_metrics"), n.fq("semantic", "occupancy_metrics")

    def stays(which):
        return (f"SELECT `Property Code` AS property_code, MEASURE(`Room Revenue`) AS rr, "
                f"MEASURE(`Net Room Revenue`) AS nrr, MEASURE(`Room Nights`) AS rn\n  FROM {rs}\n"
                f"  WHERE {_between('`Stay Date`', which)}\n  GROUP BY ALL")

    def occupancy(which):
        return (f"SELECT `Property Code` AS property_code, MEASURE(`Occupied Rooms`) AS occ, "
                f"MEASURE(`Available Rooms`) AS avail, MEASURE(`Room Revenue`) AS rev\n  FROM {oc}\n"
                f"  WHERE {_between('`Date`', which)}\n  GROUP BY ALL")
    return f"""WITH {_window(n)},
{_props(n)},
cur AS (
  {stays('cur')}
),
ly AS (
  {stays('ly')}
),
ocur AS (
  {occupancy('cur')}
),
oly AS (
  {occupancy('ly')}
),
joined AS (
  SELECT p.*,
         CASE :view_by WHEN 'DVP' THEN p.dvp WHEN 'RVP/RDO' THEN p.rvp_rdo ELSE p.district_manager END AS leader,
         coalesce(cur.rr, 0) AS room_revenue, coalesce(ly.rr, 0) AS room_revenue_ly,
         coalesce(cur.nrr, 0) AS net_room_revenue, coalesce(ly.nrr, 0) AS net_room_revenue_ly,
         coalesce(cur.rn, 0) AS room_nights, coalesce(ly.rn, 0) AS room_nights_ly,
         coalesce(ocur.occ, 0) AS occupied_rooms, coalesce(oly.occ, 0) AS occupied_rooms_ly,
         coalesce(ocur.avail, 0) AS available_rooms, coalesce(oly.avail, 0) AS available_rooms_ly,
         coalesce(ocur.rev, 0) AS occupancy_room_revenue, coalesce(oly.rev, 0) AS occupancy_room_revenue_ly
  FROM props p
  LEFT JOIN cur USING (property_code) LEFT JOIN ly USING (property_code)
  LEFT JOIN ocur USING (property_code) LEFT JOIN oly USING (property_code)
)
SELECT joined.*,
       (SELECT cur_start FROM w) AS period_start, (SELECT cur_end FROM w) AS period_end,
       try_divide(room_revenue - room_revenue_ly, room_revenue_ly) AS room_revenue_yoy,
       try_divide(room_revenue, room_nights) AS adr,
       try_divide(try_divide(room_revenue, room_nights) - try_divide(room_revenue_ly, room_nights_ly),
                  try_divide(room_revenue_ly, room_nights_ly)) AS adr_yoy,
       try_divide(occupied_rooms, available_rooms) AS occupancy,
       try_divide(occupied_rooms, available_rooms) - try_divide(occupied_rooms_ly, available_rooms_ly) AS occupancy_change,
       try_divide(occupancy_room_revenue, available_rooms) AS revpar,
       try_divide(try_divide(occupancy_room_revenue, available_rooms) -
                  try_divide(occupancy_room_revenue_ly, available_rooms_ly),
                  try_divide(occupancy_room_revenue_ly, available_rooms_ly)) AS revpar_yoy,
       try_divide(SUM(room_revenue) OVER (PARTITION BY district), SUM(room_nights) OVER (PARTITION BY district))
         AS district_adr,
       try_divide(SUM(occupied_rooms) OVER (PARTITION BY district), SUM(available_rooms) OVER (PARTITION BY district))
         AS district_occupancy,
       try_divide(SUM(occupancy_room_revenue) OVER (PARTITION BY district),
                  SUM(available_rooms) OVER (PARTITION BY district)) AS district_revpar
FROM joined
ORDER BY room_revenue DESC"""


def property_breakdown_sql(n: Names, dimension: str, alias: str) -> str:
    """Property x one metric-view dimension (LOS Tier or Channel), current period and last year."""
    rs = n.fq("semantic", "resstay_metrics")

    def part(which):
        return (f"SELECT `Property Code` AS property_code, `{dimension}` AS {alias}, MEASURE(`Room Revenue`) AS rr, "
                f"MEASURE(`Room Nights`) AS rn\n  FROM {rs}\n  WHERE {_between('`Stay Date`', which)}\n  GROUP BY ALL")
    return f"""WITH {_window(n)},
{_props(n)},
cur AS (
  {part('cur')}
),
ly AS (
  {part('ly')}
)
SELECT p.*, coalesce(b.{alias}, 'Unknown') AS {alias}, coalesce(b.cur_rr, 0) AS room_revenue,
       coalesce(b.ly_rr, 0) AS room_revenue_ly, coalesce(b.cur_rn, 0) AS room_nights, coalesce(b.ly_rn, 0) AS room_nights_ly
FROM (
  SELECT coalesce(cur.property_code, ly.property_code) AS property_code, coalesce(cur.{alias}, ly.{alias}) AS {alias},
         cur.rr AS cur_rr, ly.rr AS ly_rr, cur.rn AS cur_rn, ly.rn AS ly_rn
  FROM cur FULL OUTER JOIN ly ON cur.property_code = ly.property_code AND cur.{alias} <=> ly.{alias}
) b
JOIN props p USING (property_code)"""


def property_month_sql(n: Names) -> str:
    rs = n.fq("semantic", "resstay_metrics")
    return f"""WITH latest AS (
  SELECT MEASURE(`Latest Stay Date`) AS d FROM {rs}
),
{_props(n)},
m AS (
  SELECT `Property Code` AS property_code, `Stay Month` AS stay_month, `LOS Tier` AS los_tier,
         MEASURE(`Room Revenue`) AS room_revenue, MEASURE(`Net Room Revenue`) AS net_room_revenue,
         MEASURE(`Room Nights`) AS room_nights
  FROM {rs}
  WHERE `Stay Date` BETWEEN (SELECT add_months(trunc(d, 'MM'), -12) FROM latest) AND (SELECT d FROM latest)
  GROUP BY ALL
)
SELECT p.*, m.stay_month, coalesce(m.los_tier, 'Unknown') AS los_tier, m.room_revenue, m.net_room_revenue, m.room_nights
FROM m JOIN props p USING (property_code)
ORDER BY m.stay_month"""


def property_week_sql(n: Names) -> str:
    """Property x week for the latest 26 weeks, with the same weeks one year (364 days) earlier."""
    oc = n.fq("semantic", "occupancy_metrics")

    def part(shift):
        week = "`Week`" if shift == 0 else f"date_add(`Week`, {shift})"
        start = "date_sub(trunc(d, 'WEEK'), 175)" if shift == 0 else f"date_sub(date_sub(trunc(d, 'WEEK'), 175), {shift})"
        end = "d" if shift == 0 else f"date_sub(d, {shift})"
        return (f"SELECT `Property Code` AS property_code, {week} AS week, MEASURE(`Occupied Rooms`) AS occ, "
                f"MEASURE(`Available Rooms`) AS avail, MEASURE(`Out-of-Order Rooms`) AS ooo, "
                f"MEASURE(`Total Rooms`) AS total, MEASURE(`Room Revenue`) AS rev\n  FROM {oc}\n"
                f"  WHERE `Date` BETWEEN (SELECT {start} FROM latest) AND (SELECT {end} FROM latest)\n  GROUP BY ALL")
    return f"""WITH latest AS (
  SELECT MEASURE(`Latest Date`) AS d FROM {oc}
),
{_props(n)},
cur AS (
  {part(0)}
),
ly AS (
  {part(364)}
)
SELECT p.*, cur.week, (SELECT d FROM latest) AS latest_date,
       cur.week >= (SELECT date_sub(trunc(d, 'WEEK'), 21) FROM latest) AS in_last_4_weeks,
       cur.occ AS occupied_rooms, cur.avail AS available_rooms, cur.ooo AS out_of_order_rooms,
       cur.total AS total_rooms, cur.rev AS room_revenue,
       coalesce(ly.occ, 0) AS occupied_rooms_ly, coalesce(ly.avail, 0) AS available_rooms_ly,
       coalesce(ly.ooo, 0) AS out_of_order_rooms_ly, coalesce(ly.rev, 0) AS room_revenue_ly
FROM cur LEFT JOIN ly ON ly.property_code = cur.property_code AND ly.week = cur.week
JOIN props p ON p.property_code = cur.property_code
ORDER BY cur.week"""


# --- widgets -------------------------------------------------------------------------------------------------------

def _pos(x, y, w, h):
    return {"x": x, "y": y, "width": w, "height": h}


def _measure(name: str) -> dict:
    return {"name": f"measure({name})", "expression": f"MEASURE(`{name}`)"}


def _field(name: str) -> dict:
    return {"name": name, "expression": f"`{name}`"}


def text(name: str, markdown: str, pos: dict) -> dict:
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": [markdown]}}, "position": pos}


def counter(name: str, title: str, dataset: str, value: str, pos: dict, *, target: str | None = None,
            fmt: dict | None = None, description: str | None = None, filters: list[str] | None = None) -> dict:
    fields = [_measure(value)] + ([_measure(target)] if target else [])
    query = {"datasetName": dataset, "fields": fields, "disaggregated": False}
    if filters:
        query["filters"] = [{"expression": f} for f in filters]
    encodings = {"value": {"fieldName": f"measure({value})", "displayName": title, **({"format": fmt} if fmt else {})}}
    if target:
        encodings["target"] = {"fieldName": f"measure({target})", "displayName": "vs last year",
                               **({"format": fmt} if fmt else {})}
    frame = {"title": title, "showTitle": True}
    if description:
        frame.update(description=description, showDescription=True)
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": query}],
                       "spec": {"version": 2, "widgetType": "counter", "encodings": encodings, "frame": frame}},
            "position": pos}


def chart(kind: str, name: str, title: str, dataset: str, dim: tuple[str, str, str], measures: list[tuple[str, str]],
          pos: dict, *, fmt: dict | None = None, color: tuple[str, str] | None = None, horizontal: bool = False,
          grouped: bool = False, order: list[str] | None = None, sort_by_value: bool = False,
          filters: list[str] | None = None, description: str | None = None) -> dict:
    """A bar or line chart: one dimension (field, display name, scale type) against one or more measures."""
    field, dim_display, scale = dim
    fields = [_field(field)] + [_measure(m) for m, _ in measures] + ([_field(color[0])] if color else [])
    query = {"datasetName": dataset, "fields": fields, "disaggregated": False}
    if filters:
        query["filters"] = [{"expression": f} for f in filters]
    dim_scale = {"type": scale}
    if order:
        dim_scale["sort"] = {"by": "custom-order", "orderedValues": order}
    elif sort_by_value:
        dim_scale["sort"] = {"by": "value"}
    dim_enc = {"fieldName": field, "scale": dim_scale, "displayName": dim_display}
    if len(measures) == 1:
        value_enc = {"fieldName": f"measure({measures[0][0]})", "scale": {"type": "quantitative"},
                     "displayName": measures[0][1]}
    else:
        value_enc = {"scale": {"type": "quantitative"},
                     "fields": [{"fieldName": f"measure({m})", "displayName": d} for m, d in measures]}
    if fmt:
        value_enc["format"] = fmt
    encodings = {"x": value_enc, "y": dim_enc} if horizontal else {"x": dim_enc, "y": value_enc}
    if color:
        encodings["color"] = {"fieldName": color[0], "scale": {"type": "categorical"}, "displayName": color[1]}
    spec = {"version": 3, "widgetType": kind, "encodings": encodings, "frame": {"title": title, "showTitle": True}}
    if description:
        spec["frame"].update(description=description, showDescription=True)
    if grouped:
        spec["mark"] = {"layout": "group"}
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": query}], "spec": spec},
            "position": pos}


def table(name: str, title: str, dataset: str, columns: list[tuple], pos: dict, *, aggregated: bool = False,
          filters: list[str] | None = None) -> dict:
    """columns: (field, display, format) for raw columns, or ("measure:<name>", display, format) for measures."""
    fields, encs = [], []
    for field, display, fmt in columns:
        spec_field = _measure(field.split(":", 1)[1]) if field.startswith("measure:") else _field(field)
        fields.append(spec_field)
        encs.append({"fieldName": spec_field["name"], "displayName": display, **({"format": fmt} if fmt else {})})
    query = {"datasetName": dataset, "fields": fields, "disaggregated": not aggregated}
    if filters:
        query["filters"] = [{"expression": f} for f in filters]
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": query}],
                       "spec": {"version": 2, "widgetType": "table", "encodings": {"columns": encs},
                                "frame": {"title": title, "showTitle": True}}},
            "position": pos}


def field_filter(name: str, title: str, field: str, datasets: list[str], pos: dict, *, single: bool = False,
                 default: str | None = None) -> dict:
    queries = [{"name": f"{ds}_{field}", "query": {"datasetName": ds, "fields": [_field(field)],
                                                   "disaggregated": False}} for ds in datasets]
    spec = {"version": 2, "widgetType": "filter-single-select" if single else "filter-multi-select",
            "encodings": {"fields": [{"fieldName": field, "displayName": title, "queryName": q["name"]}
                                     for q in queries]},
            "frame": {"title": title, "showTitle": True}}
    if default:
        spec["selection"] = {"defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": default}]}}}
    return {"widget": {"name": name, "queries": queries, "spec": spec}, "position": pos}


def parameter_filter(name: str, title: str, keyword: str, options_dataset: str, option_field: str,
                     datasets: list[str], default: str, pos: dict) -> dict:
    """A single-select whose values come from a small options dataset and whose choice sets a dataset parameter."""
    queries = [{"name": f"{options_dataset}_{option_field}", "query": {
        "datasetName": options_dataset, "fields": [_field(option_field)], "disaggregated": False}}]
    queries += [{"name": f"{ds}_{keyword}", "query": {"datasetName": ds, "parameters": [
        {"name": keyword, "keyword": keyword}], "disaggregated": False}} for ds in datasets]
    fields = [{"fieldName": option_field, "displayName": title, "queryName": queries[0]["name"]}]
    fields += [{"parameterName": keyword, "queryName": q["name"]} for q in queries[1:]]
    spec = {"version": 2, "widgetType": "filter-single-select", "encodings": {"fields": fields},
            "selection": {"defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": default}]}}},
            "frame": {"title": title, "showTitle": True}}
    return {"widget": {"name": name, "queries": queries, "spec": spec}, "position": pos}


def _sql_dataset(name: str, display: str, sql: str, *, columns: list[tuple[str, str, str]] = (),
                 parameters: list[tuple[str, str]] = ()) -> dict:
    lines = [line + "\n" for line in sql.strip().splitlines()]
    ds = {"name": name, "displayName": display, "queryLines": lines}
    if columns:
        ds["columns"] = [{"displayName": d, "description": desc, "expression": e} for d, e, desc in columns]
    if parameters:
        ds["parameters"] = [{"displayName": k, "keyword": k, "dataType": "STRING",
                             "defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": v}]}}}
                            for k, v in parameters]
    return ds


def _options_dataset(name: str, column: str, values: tuple[str, ...]) -> dict:
    rows = ", ".join(f"('{v}', {i})" for i, v in enumerate(values))
    return _sql_dataset(name, column.replace("_", " ").title(),
                        f"SELECT {column} FROM VALUES {rows} AS t({column}, sort_order) ORDER BY sort_order")


def _ratio(num: str, den: str) -> str:
    return f"try_divide(SUM(`{num}`), SUM(`{den}`))"


REVENUE_MEASURES = [
    ("Room Revenue", "SUM(`room_revenue`)", "Room revenue in the selected period (USD)"),
    ("Room Revenue LY", "SUM(`room_revenue_ly`)", "Room revenue in the same window last year (USD)"),
    ("Room Revenue YoY", "try_divide(SUM(`room_revenue`) - SUM(`room_revenue_ly`), SUM(`room_revenue_ly`))",
     "Room revenue change vs last year"),
    ("Room Revenue Variance", "SUM(`room_revenue`) - SUM(`room_revenue_ly`)", "Room revenue minus last year (USD)"),
]


def resstay_dashboard(n: Names, genie_space_id: str | None = None, comparison_district: str | None = None) -> dict:
    period_params = [("period", "MTD")]
    datasets = [
        _sql_dataset("ds_property", "Properties - selected period vs last year", property_period_sql(n),
                     parameters=period_params + [("view_by", "District Manager")], columns=REVENUE_MEASURES + [
                         ("Net Room Revenue", "SUM(`net_room_revenue`)", "Net room revenue, selected period (USD)"),
                         ("Net Room Revenue LY", "SUM(`net_room_revenue_ly`)", "Net room revenue last year (USD)"),
                         ("Room Nights", "SUM(`room_nights`)", "Consumed room nights, selected period"),
                         ("Room Nights LY", "SUM(`room_nights_ly`)", "Consumed room nights last year"),
                         ("ADR", _ratio("room_revenue", "room_nights"), "Room revenue / room nights (USD)"),
                         ("ADR LY", _ratio("room_revenue_ly", "room_nights_ly"), "ADR last year (USD)"),
                         ("Occupancy", _ratio("occupied_rooms", "available_rooms"), "Occupied / available rooms"),
                         ("Occupancy LY", _ratio("occupied_rooms_ly", "available_rooms_ly"), "Occupancy last year"),
                         ("RevPAR", _ratio("occupancy_room_revenue", "available_rooms"),
                          "Room revenue / available rooms (USD)"),
                         ("RevPAR LY", _ratio("occupancy_room_revenue_ly", "available_rooms_ly"), "RevPAR last year")]),
        _sql_dataset("ds_los", "Length-of-stay tiers - selected period vs last year",
                     property_breakdown_sql(n, "LOS Tier", "los_tier"), parameters=period_params,
                     columns=REVENUE_MEASURES),
        _sql_dataset("ds_channel", "Channels - selected period vs last year",
                     property_breakdown_sql(n, "Channel", "channel"), parameters=period_params,
                     columns=REVENUE_MEASURES),
        _sql_dataset("ds_month", "Last 13 months by property and length-of-stay tier", property_month_sql(n), columns=[
            ("Room Revenue", "SUM(`room_revenue`)", "Room revenue (USD)"),
            ("Net Room Revenue", "SUM(`net_room_revenue`)", "Net room revenue (USD)"),
            ("Room Nights", "SUM(`room_nights`)", "Consumed room nights"),
            ("ADR", _ratio("room_revenue", "room_nights"), "Room revenue / room nights (USD)")]),
        _options_dataset("ds_period_options", "time_period", PERIODS),
        _options_dataset("ds_view_by_options", "view_by", VIEW_BY),
    ]
    all_data = ["ds_property", "ds_los", "ds_channel", "ds_month"]
    filters = [parameter_filter("filter-period", "Selected Time Period", "period", "ds_period_options", "time_period",
                                ["ds_property", "ds_los", "ds_channel"], "MTD", _pos(0, 0, 2, 2))]
    for i, (field, title) in enumerate(FILTERS, start=1):
        filters.append(field_filter(f"filter-{field.replace('_', '-')}", title, field, all_data, _pos(0, 2 * i, 2, 2)))
    filters.append(parameter_filter("filter-view-by", "View By (ranking)", "view_by", "ds_view_by_options", "view_by",
                                    ["ds_property"], "District Manager", _pos(0, 2 * (len(FILTERS) + 1), 2, 2)))

    kpis = [("Room Revenue", "Room Revenue LY", USD), ("Net Room Revenue", "Net Room Revenue LY", USD),
            ("Room Nights", "Room Nights LY", COUNT), ("ADR", "ADR LY", USD_CENTS)]
    overview = [   # one two-line header, as edited in the workspace on 2026-11-18
        text("title", "# ResStay Dashboard\nSelected time period vs. the same calendar window last year, through the "
                      "latest night audit. Use the filter panel for period, comp status, brand, and leadership.\n",
             _pos(0, 0, 12, 2)),
    ]
    for i, (value, target, fmt) in enumerate(kpis):
        slug = value.lower().replace(" ", "-")
        overview.append(counter(f"kpi-{slug}", value, "ds_property", value, _pos(3 * i, 2, 3, 3), target=target,
                                fmt=fmt))
        overview.append(chart("bar", f"trend-{slug}", f"{value} - last 13 months", "ds_month",
                              ("stay_month", "Month", "temporal"), [(value, value)], _pos(3 * i, 5, 3, 3), fmt=fmt))
    overview += [
        chart("bar", "los-revenue", "LOS - Room Revenue (OTB 4 Tier)", "ds_los", ("los_tier", "LOS tier", "categorical"),
              [("Room Revenue", "Selected period"), ("Room Revenue LY", "Last year")], _pos(0, 8, 6, 6), fmt=USD,
              grouped=True, order=["0-6", "7-14", "15-29", "30+"]),
        chart("line", "los-trend", "LOS - Room Revenue by month", "ds_month", ("stay_month", "Month", "temporal"),
              [("Room Revenue", "Room Revenue")], _pos(6, 8, 6, 6), fmt=USD, color=("los_tier", "LOS tier")),
        chart("bar", "brand-revenue", "Brand - Room Revenue", "ds_property", ("brand", "Brand", "categorical"),
              [("Room Revenue", "Selected period"), ("Room Revenue LY", "Last year")], _pos(0, 14, 4, 6), fmt=USD,
              grouped=True, order=["ESAS", "ESSS", "ESAP"]),
        chart("bar", "channel-revenue", "Channel - Room Revenue", "ds_channel", ("channel", "Channel", "categorical"),
              [("Room Revenue", "Selected period"), ("Room Revenue LY", "Last year")], _pos(4, 14, 8, 6), fmt=USD,
              grouped=True, sort_by_value=True),
        chart("bar", "leader-variance", "Room Revenue variance to last year by leader", "ds_property",
              ("leader", "Leader", "categorical"), [("Room Revenue Variance", "Variance to last year")],
              _pos(0, 20, 12, 10), fmt=USD, horizontal=True, sort_by_value=True,
              description="Leader level follows the View By filter: District Manager, RVP/RDO, or DVP."),
    ]
    pct = PCT
    detail = [
        text("detail-title", "# Detailed View\n", _pos(0, 0, 12, 1)),
        table("property-table", "Properties - selected period vs last year", "ds_property", [
            ("property", "Property", None), ("district", "District", None), ("district_manager", "DM", None),
            ("brand", "Brand", None), ("comp_status", "Comp Status", None),
            ("room_revenue", "Room Revenue", USD), ("room_revenue_yoy", "Room Revenue YoY", pct),
            ("net_room_revenue", "Net Room Revenue", USD), ("room_nights", "Room Nights", None),
            ("adr", "ADR", USD_CENTS), ("adr_yoy", "ADR YoY", pct), ("occupancy", "Occupancy", pct),
            ("occupancy_change", "Occupancy change (pts)", pct), ("revpar", "RevPAR", USD_CENTS),
            ("revpar_yoy", "RevPAR YoY", pct)], _pos(0, 1, 12, 16)),
    ]
    comparison = [
        text("comparison-title", "# Property Comparison\n", _pos(0, 0, 12, 1)),
        field_filter("filter-comparison-district", "District", "district", ["ds_property", "ds_month"],
                     _pos(0, 1, 4, 2), single=True, default=comparison_district),
        field_filter("filter-comparison-property", "Properties", "property", ["ds_property", "ds_month"],
                     _pos(4, 1, 8, 2)),
        table("comparison-table", "Each property against its district", "ds_property", [
            ("property", "Property", None), ("adr", "ADR", USD_CENTS), ("district_adr", "District ADR", USD_CENTS),
            ("occupancy", "Occupancy", pct), ("district_occupancy", "District occupancy", pct),
            ("revpar", "RevPAR", USD_CENTS), ("district_revpar", "District RevPAR", USD_CENTS),
            ("room_revenue", "Room Revenue", USD), ("room_revenue_yoy", "Room Revenue YoY", pct)],
              _pos(0, 3, 12, 7)),
        chart("line", "comparison-revenue", "Room Revenue by month", "ds_month", ("stay_month", "Month", "temporal"),
              [("Room Revenue", "Room Revenue")], _pos(0, 10, 6, 6), fmt=USD, color=("property", "Property")),
        chart("line", "comparison-adr", "ADR by month", "ds_month", ("stay_month", "Month", "temporal"),
              [("ADR", "ADR")], _pos(6, 10, 6, 6), fmt=USD_CENTS, color=("property", "Property")),
    ]
    ui = {"theme": THEME}
    if genie_space_id:
        ui["genieSpace"] = {"isEnabled": True, "overrideId": genie_space_id, "enablementMode": "ENABLED"}
    return {"datasets": datasets, "pages": [
        {"name": "overview", "displayName": "Overview", "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1",
         "layout": overview},
        {"name": "detailed", "displayName": "Detailed View", "pageType": "PAGE_TYPE_CANVAS",
         "layoutVersion": "GRID_V1", "layout": detail},
        {"name": "comparison", "displayName": "Property Comparison", "pageType": "PAGE_TYPE_CANVAS",
         "layoutVersion": "GRID_V1", "layout": comparison},
        {"name": "filters", "displayName": "Filters", "pageType": "PAGE_TYPE_GLOBAL_FILTERS",
         "layoutVersion": "GRID_V1", "layout": filters},
    ], "uiSettings": ui}


def occupancy_dashboard(n: Names, genie_space_id: str | None = None) -> dict:
    last4 = ["`in_last_4_weeks`"]
    datasets = [_sql_dataset("ds_week", "Weekly property statistics - last 26 weeks vs last year",
                             property_week_sql(n), columns=[
        ("Occupancy", _ratio("occupied_rooms", "available_rooms"), "Occupied / available rooms"),
        ("Occupancy LY", _ratio("occupied_rooms_ly", "available_rooms_ly"), "Occupancy, same weeks last year"),
        ("RevPAR", _ratio("room_revenue", "available_rooms"), "Room revenue / available rooms (USD)"),
        ("RevPAR LY", _ratio("room_revenue_ly", "available_rooms_ly"), "RevPAR, same weeks last year (USD)"),
        ("Out-of-Order Rooms", "SUM(`out_of_order_rooms`)", "Out-of-order room nights"),
        ("Out-of-Order Rooms LY", "SUM(`out_of_order_rooms_ly`)", "Out-of-order room nights last year"),
        ("Out-of-Order Share", _ratio("out_of_order_rooms", "total_rooms"), "Out-of-order / total rooms")])]
    filters = [field_filter(f"filter-{f.replace('_', '-')}", t, f, ["ds_week"], _pos(0, 2 * i, 2, 2))
               for i, (f, t) in enumerate(FILTERS + (("district", "District"),))]
    overview = [
        text("title", "# Occupancy Trend by Week\nWeekly occupancy vs. the same weeks last year (364 days earlier, so "
                      "weekdays align), with out-of-order rooms and RevPAR. Headline numbers cover the last 4 weeks.\n",
             _pos(0, 0, 12, 2)),
        counter("kpi-occupancy", "Occupancy - last 4 weeks", "ds_week", "Occupancy", _pos(0, 2, 4, 3),
                target="Occupancy LY", fmt=PCT, filters=last4),
        counter("kpi-revpar", "RevPAR - last 4 weeks", "ds_week", "RevPAR", _pos(4, 2, 4, 3), target="RevPAR LY",
                fmt=USD_CENTS, filters=last4),
        counter("kpi-ooo", "Out-of-order rooms - last 4 weeks", "ds_week", "Out-of-Order Rooms", _pos(8, 2, 4, 3),
                target="Out-of-Order Rooms LY", fmt=COUNT, filters=last4),
        chart("line", "occupancy-trend", "Weekly occupancy: this year vs last year", "ds_week",
              ("week", "Week starting", "temporal"), [("Occupancy", "This year"), ("Occupancy LY", "Last year")],
              _pos(0, 5, 12, 6), fmt=PCT),
        chart("bar", "ooo-trend", "Out-of-order rooms by week", "ds_week", ("week", "Week starting", "temporal"),
              [("Out-of-Order Rooms", "This year"), ("Out-of-Order Rooms LY", "Last year")], _pos(0, 11, 6, 6),
              fmt=COUNT, grouped=True),
        chart("line", "revpar-trend", "Weekly RevPAR: this year vs last year", "ds_week",
              ("week", "Week starting", "temporal"), [("RevPAR", "This year"), ("RevPAR LY", "Last year")],
              _pos(6, 11, 6, 6), fmt=USD_CENTS),
        chart("bar", "brand-occupancy", "Occupancy by brand - last 4 weeks", "ds_week", ("brand", "Brand", "categorical"),
              [("Occupancy", "This year"), ("Occupancy LY", "Last year")], _pos(0, 17, 5, 7), fmt=PCT, grouped=True,
              order=["ESAS", "ESSS", "ESAP"], filters=last4),
        table("district-table", "Districts - last 4 weeks", "ds_week", [
            ("district", "District", None), ("district_manager", "DM", None),
            ("measure:Occupancy", "Occupancy", PCT), ("measure:Occupancy LY", "Occupancy LY", PCT),
            ("measure:Out-of-Order Share", "Out-of-order share", PCT), ("measure:RevPAR", "RevPAR", USD_CENTS)],
              _pos(5, 17, 7, 7), aggregated=True, filters=last4),
    ]
    ui = {"theme": THEME}
    if genie_space_id:
        ui["genieSpace"] = {"isEnabled": True, "overrideId": genie_space_id, "enablementMode": "ENABLED"}
    return {"datasets": datasets, "pages": [
        {"name": "overview", "displayName": "Occupancy Trend by Week", "pageType": "PAGE_TYPE_CANVAS",
         "layoutVersion": "GRID_V1", "layout": overview},
        {"name": "filters", "displayName": "Filters", "pageType": "PAGE_TYPE_GLOBAL_FILTERS",
         "layoutVersion": "GRID_V1", "layout": filters},
    ], "uiSettings": ui}


def dataset_queries(dashboard: dict) -> list[tuple[str, str, dict]]:
    """(name, SQL, default parameters) for every dataset, for live validation."""
    out = []
    for ds in dashboard["datasets"]:
        params = {p["keyword"]: p["defaultSelection"]["values"]["values"][0]["value"] for p in ds.get("parameters", [])}
        out.append((ds["name"], "".join(ds["queryLines"]), params))
    return out
