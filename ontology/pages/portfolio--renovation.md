---
display_name: Renovation
subdomain: portfolio
synonyms: [renovation, renovations, property renovation, capital project, soft goods refresh, brand conversion]
description: Renovation projects at a hotel, Full Renovation, Soft Goods Refresh or Brand Conversion, with phase, status and dates. Rooms out of order during the work appear in out-of-order rooms.
assumption: true
mentions: [mart.dim_property_renovation, mart.fact_property_renovation, mart.vw_dim_property, mart.fact_property_statistics, semantic.occupancy_metrics]
requires: []
---
## Definition
A renovation is a capital project at a hotel. Each has a type, phase, status, start and end dates, and a count of rooms in scope. The types are Full Renovation, Soft Goods Refresh and Brand Conversion. A Brand Conversion project is the renovation work. The brand change itself is kept as a history row on the property. Status is Planned, In Progress or Complete. Phases are Design, Phase 1 - Guest Rooms and Closeout.

## How it's calculated
Status is set as of the latest load: Planned if the start date is after it, Complete if the end date is before it, otherwise In Progress.
```
SELECT p.bk_property_id, r.renovation_type, r.renovation_status
FROM `{{catalog}}.{{mart}}.fact_property_renovation` AS p
JOIN `{{catalog}}.{{mart}}.dim_property_renovation` AS r
  ON r.bk_property_renovation_id = p.bk_property_renovation_id
WHERE p.member_flag AND p.is_current AND r.is_current
```

## Where it lives
Projects are in `{{catalog}}.{{mart}}.dim_property_renovation`. The bridge `{{catalog}}.{{mart}}.fact_property_renovation` links them to hotels. The current and prior project for each hotel appear on `{{catalog}}.{{mart}}.vw_dim_property` as `current_renovation_*` and `prior_renovation_*` columns, and `is_under_renovation_flag` is true when the current project is In Progress. Out-of-order rooms from the work are in `{{catalog}}.{{mart}}.fact_property_statistics`, reported through `{{catalog}}.{{semantic}}.occupancy_metrics`.

## Notes
- Renovation rooms come out of order in sequential batches across the project window. The effect shows up in out-of-order rooms, not as a separate figure.
- A Full Renovation in the trailing 13 months makes a hotel Non-Comp. See Comp Status.
- Soft Goods Refresh and Brand Conversion do not change Comp Status.
- `rooms_impacted_count` is the rooms in scope for the project. It is not the number out of order on a given night.
- Status reflects the latest load. Read it after each refresh.

## Related
Available vs Out-of-Order Rooms, Comp Status, Brand, Occupancy %, Current vs History Rows, Property Operations Q&A
