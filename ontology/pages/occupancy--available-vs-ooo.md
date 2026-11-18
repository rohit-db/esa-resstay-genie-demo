---
display_name: Available vs Out-of-Order Rooms
subdomain: occupancy
synonyms: [available rooms, out of order rooms, OOO, OOO rooms, rooms out of service, out of service]
description: Available rooms are a hotel's room count less the rooms out of order that night. Out-of-order rooms are taken out of service for renovation or maintenance.
assumption: true
mentions: [mart.fact_property_statistics, mart.vw_dim_property, common.dim_date, semantic.occupancy_metrics]
requires: []
---
## Definition
Available rooms are the rooms that can be sold on a night: the hotel's room count less the rooms out of order that night. Out-of-order rooms are rooms taken out of service for one or more nights, for renovation work or for maintenance. A room that is out of order is neither available nor occupied.

## How it's calculated
```
SUM(available_rooms), SUM(out_of_order_rooms)
FROM `{{catalog}}.{{mart}}.fact_property_statistics`
```
Per property-day: `available_rooms = room_count - out_of_order_rooms`, so `available_rooms + out_of_order_rooms` equals the `room_count` on `{{catalog}}.{{mart}}.vw_dim_property`. Use that equality as a quick check. Calendar fields come from `{{catalog}}.{{common}}.dim_date`.

## Where it lives
The measures are in `{{catalog}}.{{semantic}}.occupancy_metrics`. Rows come from `{{catalog}}.{{mart}}.fact_property_statistics`. Room count comes from `{{catalog}}.{{mart}}.vw_dim_property`.

## Notes
- The mart does not split out-of-order rooms by reason. The figure includes rooms out for renovation and rooms out for maintenance.
- Rooms in a renovation come out in sequential batches across the project window. See Renovation.
- Out-of-order is counted per night, not per part of a day.
- Occupancy % and RevPAR both divide by available rooms, so out-of-order rooms affect both.

## Related
Occupancy %, RevPAR, Renovation, Paid vs Comp Rooms, Occupancy Trend by Week
