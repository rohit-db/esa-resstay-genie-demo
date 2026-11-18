---
display_name: Current vs History Rows
subdomain: portfolio
synonyms: [current rows, history rows, is_current, prior version, active row, versions]
description: Every table has a current flag that marks the active version. Prior versions from brand conversions, DM changes and date changes stay as history rows. Filter on the current flag in joins.
assumption: false
mentions: [mart.dim_property, mart.dim_property_hierarchy, mart.dim_reservation, mart.fact_reservation_summary, mart.vw_dim_property]
requires: []
---
## Definition
Every table and view carries the same history columns. `is_current` marks the active version of a row. A dimension row that changes keeps its old version with `is_current = false`. `active_start_date_time` and `active_end_date_time` give the range each version was active, and an open version ends at 9999-12-31 23:59:59. `is_deleted` is false on every row in this model.

## How it's calculated
Add `is_current = true` to every dimension join:
```
JOIN `{{catalog}}.{{mart}}.dim_property` AS p
  ON p.bk_property_id = s.bk_property_id AND p.is_current
```
The view `{{catalog}}.{{mart}}.vw_dim_property` already returns current rows only.

Versions that exist in this model:
- `dim_property`: a brand conversion keeps the prior brand as a history row.
- `dim_property_hierarchy`: a DM change keeps the prior leader as a history row.
- `fact_reservation_summary` and `dim_reservation`: a date change keeps the prior version of the reservation. The prior version's id ends in `-V1`.

## Where it lives
The columns are `is_current`, `is_deleted`, `active_start_date_time`, `active_end_date_time`, `record_source`, `etl_id`, `load_date_time`, `dq_status` and `hash_diff`. Versioned tables are `{{catalog}}.{{mart}}.dim_property`, `{{catalog}}.{{mart}}.dim_property_hierarchy`, `{{catalog}}.{{mart}}.dim_reservation` and `{{catalog}}.{{mart}}.fact_reservation_summary`.

## Notes
- Ignoring `is_current` double-counts reservations with a date change, and hotels with a brand conversion or a DM change.
- The `bk_reservation_id` is the same on both versions of a reservation, so a join from stays to reservations needs `is_current = true`.
- Stay lines in `fact_actual_stay` are always current.
- `hash_diff` is for change detection only. Do not use it as a key.

## Related
Brand, ESA Org Hierarchy (DVP, RVP/RDO, DM, GM), On-the-Books and Booking Pace, Cancellation, Renovation
