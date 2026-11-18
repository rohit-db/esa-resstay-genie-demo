---
display_name: Length of Stay and OTB 4 Tier
subdomain: resstay
synonyms: [length of stay, LOS, LOS tier, OTB 4 tier, stay length tier, stay tiers]
description: Reservation length in nights and its four-band OTB 4 Tier grouping of 0-6, 7-14, 15-29 and 30+ nights. Band 1 of the LOS banding in the LOS dimension.
assumption: true
mentions: [mart.dim_los, mart.fact_reservation_summary, mart.fact_actual_stay, semantic.resstay_metrics]
requires: []
---
## Definition
Length of stay (LOS) is the number of nights in a reservation. The OTB 4 Tier groups LOS into four bands: 0 to 6 nights, 7 to 14 nights, 15 to 29 nights, and 30 nights or more. The ResStay dashboard shows Room Revenue by these four tiers.

## How it's calculated
Revenue is tiered by joining stay lines to their reservation, then to the LOS dimension, and reading band 1:
```
SELECT l.los_band_1, SUM(s.room_revenue_amount)
FROM `{{catalog}}.{{mart}}.fact_actual_stay` AS s
JOIN `{{catalog}}.{{mart}}.fact_reservation_summary` AS r
  ON r.bk_reservation_id = s.bk_reservation_id AND r.is_current
JOIN `{{catalog}}.{{mart}}.dim_los` AS l
  ON l.bk_los_id = r.bk_actual_los_id AND l.is_current
GROUP BY l.los_band_1
```

## Where it lives
`{{catalog}}.{{mart}}.dim_los` has one row per night count from 0 to 365, with ten bandings. Only `los_band_1` is the OTB 4 Tier. The ResStay metric view `{{catalog}}.{{semantic}}.resstay_metrics` applies the same tiers as a dimension.

## Notes
- The band 1 labels are exactly `0-6`, `7-14`, `15-29` and `30+`.
- LOS keys are text. `bk_actual_los_id` joins to `bk_los_id` directly, with no cast.
- The name says OTB, but the ResStay tiers use the reservation's actual LOS (`bk_actual_los_id`). Use `bk_otb_los_id` for on-the-books tiers.
- The other nine bands on `dim_los` answer other questions. The ResStay dashboard uses only band 1.
- Filter `is_current = true` on every dimension join.

## Related
Room Revenue, Room Nights, Promotion and Stay 7+, On-the-Books and Booking Pace, Selected Time Period (MTD and YoY)
