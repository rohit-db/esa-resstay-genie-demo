---
display_name: Property Segment
subdomain: portfolio
synonyms: [property segment, segment, location type, service level, hotel segment, property category]
description: Three segment types on each hotel (Location, Service Level and Program). They are read from the segment bridge or from the segment columns on the property view.
assumption: true
mentions: [mart.dim_property_segment, mart.fact_property_segment, mart.vw_dim_property, semantic.occupancy_metrics]
requires: []
---
## Definition
A property segment groups each hotel on three axes. **Location** is the hotel's setting: Airport, Interstate, Urban, Suburban or Small Metro/Town. **Service Level** is the brand's service tier: Economy Extended Stay, Value Extended Stay or Midscale Extended Stay. **Program** is program membership: Tiger Site or Standard Operations.

## How it's calculated
Segments link to hotels through the bridge, with one row per hotel per segment type:
```
SELECT b.bk_property_id, s.segment_type, s.segment_name
FROM `{{catalog}}.{{mart}}.fact_property_segment` AS b
JOIN `{{catalog}}.{{mart}}.dim_property_segment` AS s
  ON s.bk_property_segment_id = b.bk_property_segment_id AND s.is_current
WHERE b.member_flag AND b.is_current
```

## Where it lives
Segment values are in `{{catalog}}.{{mart}}.dim_property_segment`, and the hotel links are in `{{catalog}}.{{mart}}.fact_property_segment`. On `{{catalog}}.{{mart}}.vw_dim_property`, the three types appear as `segment1` (Location), `segment2` (Service Level) and `segment3` (Program). Occupancy filters are in `{{catalog}}.{{semantic}}.occupancy_metrics`.

## Notes
- Each hotel has exactly one value per segment type. The view columns are fixed by type.
- Segments are not versioned, so every segment row is current.
- Service Level follows the brand, so it adds no information beyond Brand.
- Segment labels are the demo's own values. Confirm them with ESA before quoting.

## Related
Tiger Site, Brand, Comp Status, ESA Org Hierarchy (DVP, RVP/RDO, DM, GM), Occupancy %
