---
display_name: Occupancy %
subdomain: occupancy
synonyms: [occupancy, occupancy rate, occ, occupancy percent, percent occupied]
description: Occupied rooms divided by available rooms for a period. Available rooms exclude out-of-order rooms, so occupancy is measured on rooms that can be sold.
assumption: true
mentions: [mart.fact_property_statistics, mart.vw_dim_property, common.dim_date, semantic.occupancy_metrics]
requires: []
---
## Definition
Occupancy % is the share of sellable rooms that were occupied. Occupied rooms are paid rooms plus comp rooms, so complimentary stays count toward occupancy. Available rooms exclude rooms that are out of order. The measure is built from property-day rows and then summed over the period.

## How it's calculated
```
Occupancy % = SUM(occupied_rooms) / NULLIF(SUM(available_rooms), 0)
FROM `{{catalog}}.{{mart}}.fact_property_statistics`
```
Per property-day: `occupied_rooms = paid_rooms + comp_rooms`, and `available_rooms = room_count - out_of_order_rooms`. The hotel's `room_count` comes from `{{catalog}}.{{mart}}.vw_dim_property`.

## Where it lives
The measure is defined in `{{catalog}}.{{semantic}}.occupancy_metrics`. Rows come from `{{catalog}}.{{mart}}.fact_property_statistics`, which is a materialized view with one row per property per day. Hotel attributes join on `bk_property_id`. Calendar fields come from `{{catalog}}.{{common}}.dim_date`.

## Notes
- `bk_date_id` is an integer in this table, so no cast is needed. The cast rule applies to the stay and reservation facts only.
- Average across a period by summing both sides. Never average daily percentages.
- A hotel contributes only from its first day in the data.
- Filter `is_current = true` on property joins.

## Related
Available vs Out-of-Order Rooms, Paid vs Comp Rooms, RevPAR, Brand, Occupancy Trend by Week, Selected Time Period (MTD and YoY)
