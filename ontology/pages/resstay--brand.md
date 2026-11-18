---
display_name: Brand (ESAS, ESSS, ESAP)
subdomain: resstay
synonyms: [brand, brand code, ESAS, ESSS, ESAP, Extended Stay America Suites]
description: The ESA brand code for each hotel, ESAS, ESSS or ESAP, with its brand name. Brand reporting uses the hotel's current brand.
assumption: true
mentions: [mart.fact_actual_stay, mart.vw_dim_property, mart.dim_property, semantic.resstay_metrics]
requires: []
---
## Definition
Brand is the ESA brand a hotel operates under. The codes are `ESAS` (Extended Stay America Suites), `ESSS` (Extended Stay America Select Suites) and `ESAP` (Extended Stay America Premier Suites). The brand belongs to the hotel, not to each stay, so brand reporting joins stays to the property.

## How it's calculated
Brand revenue is room revenue grouped by the hotel's current brand:
```
SELECT p.brand_cd, SUM(s.room_revenue_amount)
FROM `{{catalog}}.{{mart}}.fact_actual_stay` AS s
JOIN `{{catalog}}.{{mart}}.vw_dim_property` AS p
  ON p.bk_property_id = s.bk_property_id
GROUP BY p.brand_cd
```

## Where it lives
`brand_cd` and `brand_name` are on `{{catalog}}.{{mart}}.vw_dim_property`, which returns the current version of each row in `{{catalog}}.{{mart}}.dim_property`. The ResStay metric view `{{catalog}}.{{semantic}}.resstay_metrics` exposes brand as a dimension.

## Notes
- Brand is a current attribute. Revenue from before a brand conversion is reported under the hotel's current brand. To report by the brand in force at the time, join to the history rows of `{{catalog}}.{{mart}}.dim_property` by date.
- Use `brand_cd` for filters and `brand_name` for display.
- The brand codes are exactly ESAS, ESSS and ESAP.

## Related
Room Revenue, Average Daily Rate (ADR), RevPAR, Current vs History Rows, Property Segment, Occupancy %
