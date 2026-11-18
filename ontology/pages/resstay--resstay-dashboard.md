---
display_name: ResStay Dashboard at a Glance
subdomain: resstay
synonyms: [ResStay dashboard, ResStay report, revenue dashboard, ResStay overview, ResStay KPIs]
description: The AI/BI ResStay dashboard with Overview, Detailed View and Property Comparison tabs for room revenue, ADR, room nights, occupancy and RevPAR.
assumption: true
mentions: [dashboard:resstay, common.dim_date, mart.vw_dim_property, semantic.resstay_metrics, semantic.occupancy_metrics]
requires: [dashboard:resstay]
---
## Definition
The ResStay Dashboard is the AI/BI version of ESA's ResStay reporting. Use it to see how room revenue, ADR, room nights and occupancy are moving, and where. Its figures are the same ones the ResStay Revenue agent quotes.

## How it's calculated
What is on it:
- Global filters: Selected Time Period, Comp Status, Brand, DVP, RVP or RDO, District Manager, Market and Tiger Site.
- Overview: KPI tiles for Room Revenue, Net Room Revenue, Room Nights and ADR, each with year-over-year change and a 12-month trend. Also Room Revenue by OTB 4 Tier, by brand, by District Manager (switchable to DM, RVP/RDO or DVP) and by channel.
- Detailed View: a property table with the four KPIs, plus Occupancy % and RevPAR with their year-over-year change.
- Property Comparison: selected properties, or one property against its district or market average.

Each measure is defined on its own Page. The dashboard adds no separate definitions.

## Where it lives
Datasets query `{{catalog}}.{{semantic}}.resstay_metrics` and `{{catalog}}.{{semantic}}.occupancy_metrics`. Hotel attributes come from `{{catalog}}.{{mart}}.vw_dim_property`, and period logic uses `{{catalog}}.{{common}}.dim_date`.

[Open the ResStay Dashboard]({{url_dashboard_resstay}})

## Notes
- Each viewer sees only the hotels their row-level access allows.
- Periods are anchored to the latest loaded night audit.
- Tiles compare with the same window a year earlier.

## Related
Room Revenue, Net Room Revenue, Room Nights, Average Daily Rate (ADR), Length of Stay and OTB 4 Tier, Brand, Comp Status, Selected Time Period (MTD and YoY), Occupancy %, RevPAR, ResStay Revenue Q&A
