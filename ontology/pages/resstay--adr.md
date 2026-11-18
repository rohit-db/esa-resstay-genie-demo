---
display_name: Average Daily Rate (ADR)
subdomain: resstay
synonyms: [ADR, average daily rate, average rate, daily rate]
description: Room revenue per consumed room night; the headline price metric on the ResStay dashboard.
assumption: true
mentions: [mart.fact_actual_stay, common.dim_date, semantic.resstay_metrics]
requires: []
---
## Definition
Average Daily Rate (ADR) is the average gross room revenue earned per consumed room night. It is the price metric on the ResStay dashboard. ADR is always recomputed from period totals, so a month's ADR is that month's room revenue divided by that month's room nights.

## How it's calculated
```
ADR = SUM(room_revenue_amount) / NULLIF(SUM(consumed_room_nights_count), 0)
FROM `{{catalog}}.{{mart}}.fact_actual_stay`
```
The numerator is gross room revenue. Credit lines add nothing to either side. Calendar filters join `{{catalog}}.{{common}}.dim_date` on the cast `bk_date_id`. Compare periods using the window rules on Selected Time Period.

## Where it lives
The measure is defined as ADR in `{{catalog}}.{{semantic}}.resstay_metrics`, with source rows in `{{catalog}}.{{mart}}.fact_actual_stay`.

## Notes
- Complimentary nights count in the denominator with zero revenue, so they lower ADR. A paid-only rate is not defined in this model.
- Credits do not change ADR, because ADR uses gross revenue and Net Room Revenue is not in the calculation.
- ADR is a ratio of sums. Never average daily ADR values.
- Brand and channel ADR follow the joins described on the Brand, Channel and Current vs History Rows Pages.

## Related
Room Revenue, Room Nights, Net Room Revenue, Selected Time Period (MTD and YoY), Brand, Rate Segment, RevPAR
