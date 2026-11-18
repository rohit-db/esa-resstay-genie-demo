---
display_name: ESA Org Hierarchy (DVP, RVP/RDO, DM, GM)
subdomain: portfolio
synonyms: [org hierarchy, operating hierarchy, DVP, RVP, RDO, district manager, DM, GM, general manager]
description: The ESA operating hierarchy. Operations runs Division, Region, District and Property. Leadership runs DVP, RVP or RDO, DM and GM. Used for hierarchy filters and row access.
assumption: true
mentions: [mart.vw_dim_property, mart.dim_property_hierarchy, mart.fact_property_hierarchy, semantic.resstay_metrics, semantic.occupancy_metrics]
requires: []
---
## Definition
Each hotel sits in two parallel hierarchies. **Operations** runs Division, Region, District and Property. **Leadership** runs DVP (division), RVP or RDO (region), DM (district) and GM (hotel). Each region is led by either an RVP or an RDO, and the column `rvp_rdo_name` holds whichever applies.

## How it's calculated
Each hotel has one current row in each hierarchy. The bridge `{{catalog}}.{{mart}}.fact_property_hierarchy` links hotels to hierarchy rows where `member_flag` is true. The view `{{catalog}}.{{mart}}.vw_dim_property` puts the levels into named columns:
- Operations: `division_name`, `region_name`, `district_name`.
- Leadership: `dvp_name`, `rvp_name` or `rdo_name`, `rvp_rdo_name`, `dm_name`, `gm_name`.
- Paths: `ops_hierarchy_path` and `leadership_path`.

Roll-ups group by these columns, for example `GROUP BY district_name`.

## Where it lives
Hierarchy rows are in `{{catalog}}.{{mart}}.dim_property_hierarchy`, with one row per hotel per hierarchy version. Named columns are on `{{catalog}}.{{mart}}.vw_dim_property`. The same attributes are filters on `{{catalog}}.{{semantic}}.resstay_metrics` and `{{catalog}}.{{semantic}}.occupancy_metrics`.

## Notes
- Use the named columns in `{{catalog}}.{{mart}}.vw_dim_property`, not the generic `level_1_value` to `level_10_value` columns on the hierarchy dimension.
- A DM change keeps the prior leader as a history row with `is_current = false`. Current leaders use `is_current = true`.
- Leader names are personal data. Do not list them in answers beyond what a filter returns.
- Row-level access follows this hierarchy, so each viewer sees the hotels in their scope.

## Related
Brand, Renovation, Tiger Site, Property Segment, Current vs History Rows, Comp Status, Occupancy %
