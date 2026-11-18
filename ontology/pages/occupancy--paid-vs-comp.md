---
display_name: Paid vs Comp Rooms
subdomain: occupancy
synonyms: [paid rooms, comp rooms, complimentary rooms, paid occupancy, comp nights, paid nights]
description: Occupied rooms split into paid rooms and comp rooms, which are rooms on complimentary stays. Comp rooms are not hotels with Comp Status.
assumption: true
mentions: [mart.fact_property_statistics, mart.fact_actual_stay, mart.dim_rate_segment, semantic.occupancy_metrics]
requires: []
---
## Definition
Paid rooms are occupied rooms sold at a rate. Comp rooms are occupied rooms on complimentary stays, which use the Complimentary rate segment and carry no room revenue. Occupied rooms equal paid rooms plus comp rooms. This is a different meaning from Comp Status, which classifies hotels.

## How it's calculated
Per property-day in the statistics table:
```
paid_rooms = occupied_rooms - comp_rooms
```
Totals and shares use sums:
```
SUM(paid_rooms), SUM(comp_rooms)
FROM `{{catalog}}.{{mart}}.fact_property_statistics`
```
Comp rooms are the stays on the Complimentary segment for that night. A stay's segment is on `{{catalog}}.{{mart}}.fact_actual_stay`, and the segment's rate type is on `{{catalog}}.{{mart}}.dim_rate_segment`, where Complimentary is `Non-Revenue`.

## Where it lives
`paid_rooms` and `comp_rooms` are on `{{catalog}}.{{mart}}.fact_property_statistics`. Measures are in `{{catalog}}.{{semantic}}.occupancy_metrics`.

## Notes
- Comp rooms are counted as occupied in Occupancy %, so a complimentary stay raises occupancy.
- Comp rooms and Comp Status are different things. Do not filter this measure by Comp Status.
- If paid occupancy is shown, its numerator is `paid_rooms` over `available_rooms`.
- Filter `is_current = true` on joins.

## Related
Occupancy %, Available vs Out-of-Order Rooms, Rate Segment, Comp Status, Room Nights
