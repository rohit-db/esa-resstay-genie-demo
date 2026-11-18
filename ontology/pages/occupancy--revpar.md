---
display_name: RevPAR
subdomain: occupancy
synonyms: [RevPAR, revenue per available room, revenue per room, rev par]
description: Room revenue divided by available rooms for the same period. Combines price and occupancy in one figure, with out-of-order rooms excluded from the denominator.
assumption: true
mentions: [mart.fact_actual_stay, mart.fact_property_statistics, common.dim_date, semantic.occupancy_metrics]
requires: []
---
## Definition
RevPAR is room revenue per available room. It combines price and occupancy: a hotel with high occupancy at a low rate can post the same RevPAR as one with a high rate and lower occupancy. Room revenue here is gross Room Revenue. Available rooms exclude out-of-order rooms.

## How it's calculated
Room revenue is summed per property and night, then divided by available rooms over the same period:
```
RevPAR = SUM(room revenue for the property-days) / NULLIF(SUM(available_rooms), 0)
```
The stay side is `SUM(room_revenue_amount)` grouped by `bk_property_id` and `CAST(bk_date_id AS INT)` from `{{catalog}}.{{mart}}.fact_actual_stay`. Join it to `{{catalog}}.{{mart}}.fact_property_statistics` on `bk_property_id` and on the cast date key, which matches the INT `bk_date_id` in that table.

## Where it lives
RevPAR is a measure in `{{catalog}}.{{semantic}}.occupancy_metrics`, which uses a helper view in the semantic schema to total room revenue per property-day. Calendar fields come from `{{catalog}}.{{common}}.dim_date`.

## Notes
- RevPAR uses gross room revenue. Net Room Revenue is not used.
- It is a ratio of period sums, not an average of daily RevPAR values.
- Complimentary nights carry zero revenue, so they pull RevPAR down while still counting as occupied rooms.
- Filter `is_current = true` on dimension joins.

## Related
Room Revenue, Occupancy %, Available vs Out-of-Order Rooms, Average Daily Rate (ADR), Brand, Selected Time Period (MTD and YoY)
