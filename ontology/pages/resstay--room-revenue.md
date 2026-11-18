---
display_name: Room Revenue
subdomain: resstay
synonyms: [room revenue, room sales, gross room revenue, rooms revenue, room income]
description: Gross charges for occupied room nights before credits, other rooms revenue and fees. The top-line revenue measure on the ResStay dashboard.
assumption: true
mentions: [mart.fact_actual_stay, common.dim_date, semantic.resstay_metrics]
requires: []
---
## Definition
Room Revenue is the gross room charge earned for consumed room nights. It excludes credits, which Net Room Revenue deducts, and other rooms revenue, which holds pet and early check-in fees. It is the top-line revenue measure behind the ResStay KPI tiles.

## How it's calculated
```
Room Revenue = SUM(room_revenue_amount)
FROM `{{catalog}}.{{mart}}.fact_actual_stay`
```
Each row is one consumed night, so the stay date is the night itself. To filter or group by calendar, cast `bk_date_id` to INT and join `{{catalog}}.{{common}}.dim_date` on `BK_Date_Dim_Id`. Period totals are sums of nights, never averages of daily totals.

## Where it lives
The measure is defined once in the ResStay metric view `{{catalog}}.{{semantic}}.resstay_metrics`, so the ResStay dashboard and the ResStay Revenue agent return the same number. Source rows are in `{{catalog}}.{{mart}}.fact_actual_stay`.

## Notes
- Credit lines have `consumed_room_nights_count = 0` and no room revenue, so they do not change this measure.
- Complimentary nights carry zero room revenue and count in the total at zero.
- Each stay line is dated by its night of stay, not by its booking date.
- Dimension joins filter `is_current = true`.

## Related
Net Room Revenue, Room Credits and Write-offs, Room Nights, Average Daily Rate (ADR), Selected Time Period (MTD and YoY), Brand, Rate Segment
