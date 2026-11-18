---
display_name: Comp Status
subdomain: resstay
synonyms: [comp status, comparable status, comparable hotels, non-comp hotels, non-comp]
description: Whether a hotel is Comp or Non-Comp for like-for-like comparisons. Non-Comp if acquired within about 13 months or under a Full Renovation in that window. Not the same as comp rooms.
assumption: true
mentions: [mart.dim_property_extended, mart.vw_dim_property, semantic.resstay_metrics]
requires: []
---
## Definition
Comp Status classifies each hotel as `Comp` or `Non-Comp` for like-for-like comparison. A hotel is `Non-Comp` if it was acquired less than 13 months before the latest load, or if a Full Renovation overlaps that same 13-month window. Every other hotel is `Comp`. Comp Status describes the hotel. It is unrelated to comp rooms, which are complimentary stays.

## How it's calculated
With the latest load date as the reference, and 13 months taken as 395 days:
```
comp_status = 'Non-Comp' if acquisition_date > latest_load_date - 395 days
comp_status = 'Non-Comp' if a Full Renovation has
                          renovation_start_date <= latest_load_date
                          and renovation_end_date >= latest_load_date - 395 days
comp_status = 'Comp'     otherwise
```
The reason is written to `comp_status_reason` as "Acquired within 13 months" or "Full renovation in comparison window".

## Where it lives
`comp_status` and `comp_status_reason` are on `{{catalog}}.{{mart}}.dim_property_extended`. They appear on `{{catalog}}.{{mart}}.vw_dim_property`, and the ResStay metric view `{{catalog}}.{{semantic}}.resstay_metrics` uses them as a filter.

## Notes
- The status is evaluated at the latest load, so each hotel carries one status for every period on the dashboard.
- Only Full Renovation projects count. Soft Goods Refresh and Brand Conversion projects do not change status.
- The acquisition rule uses the acquisition date only. The open date is not used.
- Do not filter Paid vs Comp Rooms by Comp Status. The two words describe different things.
- Filter `is_current = true` on property joins.

## Related
Renovation, Property Segment, Brand, Paid vs Comp Rooms, Selected Time Period (MTD and YoY), Occupancy %
