---
display_name: Room Nights
subdomain: resstay
synonyms: [room nights, nights sold, occupied room nights, consumed nights, room night count]
description: Consumed room nights, one per occupied room per night. Complimentary nights count and credit lines do not. The denominator for ADR.
assumption: true
mentions: [mart.fact_actual_stay, mart.dim_room_type, common.dim_date, semantic.resstay_metrics]
requires: []
---
## Definition
Room Nights is the number of rooms consumed on a night. A five-night stay in one room gives five room nights. It is the volume measure in ResStay and the denominator for ADR. Rooms can be split by room class, which takes the values Standard, Deluxe or Suite.

## How it's calculated
```
Room Nights = SUM(consumed_room_nights_count)
FROM `{{catalog}}.{{mart}}.fact_actual_stay` AS s
JOIN `{{catalog}}.{{mart}}.dim_room_type` AS rt
  ON rt.bk_room_type_id = s.bk_room_type_id AND rt.is_current
```
Room lines carry a count of 1 and credit lines carry 0, so the sum counts only occupied nights. Calendar filters join `{{catalog}}.{{common}}.dim_date` on the cast `bk_date_id`.

## Where it lives
The measure is defined in `{{catalog}}.{{semantic}}.resstay_metrics`. Stay lines are in `{{catalog}}.{{mart}}.fact_actual_stay`, and room class is on `{{catalog}}.{{mart}}.dim_room_type`.

## Notes
- Complimentary nights are counted. They carry zero room revenue, which lowers ADR.
- Future bookings are not Room Nights. Booked nights appear under On-the-Books and Booking Pace until the stay occurs.
- Room nights are dated by night of stay.

## Related
Room Revenue, Average Daily Rate (ADR), On-the-Books and Booking Pace, Paid vs Comp Rooms, Brand
