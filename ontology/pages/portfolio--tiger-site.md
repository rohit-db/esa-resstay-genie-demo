---
display_name: Tiger Site
subdomain: portfolio
synonyms: [Tiger Site, Tiger Sites, tiger property, tiger flag, focused performance program]
description: A hotel in the Program segment marked Tiger Site, meaning a focused performance program. The meaning is assumed for this demo and is exposed as a flag on the property view.
assumption: true
mentions: [mart.vw_dim_property, mart.dim_property_segment, mart.fact_property_segment, semantic.resstay_metrics, semantic.occupancy_metrics]
requires: []
---
## Definition
Tiger Site is a Program segment value that marks a hotel in a focused performance program. The meaning is an assumption for this demo and is not yet confirmed with ESA. Hotels outside the program carry the Program value Standard Operations.

## How it's calculated
A hotel is a Tiger Site when its Program segment is `Tiger Site`. The view exposes this as a flag:
```
SELECT bk_property_id, property_name
FROM `{{catalog}}.{{mart}}.vw_dim_property`
WHERE tiger_site_flag
```
Inside the view, `tiger_site_flag` is `segment3 = 'Tiger Site'`, where `segment3` is the Program segment for the hotel.

## Where it lives
The segment is in `{{catalog}}.{{mart}}.dim_property_segment` (segment_type `Program`, segment_name `Tiger Site`). It is linked to hotels by `{{catalog}}.{{mart}}.fact_property_segment`, where `member_flag` is true. The flag is `tiger_site_flag` on `{{catalog}}.{{mart}}.vw_dim_property`, and it is a filter on `{{catalog}}.{{semantic}}.resstay_metrics` and `{{catalog}}.{{semantic}}.occupancy_metrics`.

## Notes
- The data stores membership only. Nothing in the model defines what the program does.
- A hotel has one Program value at a time.
- Use the flag for filters. Do not infer Tiger Site status from occupancy or revenue.
- Filter `is_current = true` on dimension joins.

## Related
Property Segment, ESA Org Hierarchy (DVP, RVP/RDO, DM, GM), Occupancy %, Average Daily Rate (ADR)
