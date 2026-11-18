---
display_name: On-the-Books and Booking Pace
subdomain: booking
synonyms: [on the books, OTB, on-the-books nights, booking pace, future bookings, pickup]
description: Room nights already booked for stay nights after the latest load, and how reservations booked against the same stay dates compare with last year.
assumption: true
mentions: [mart.fact_reservation_summary, common.dim_date, semantic.booking_metrics]
requires: []
---
## Definition
On-the-Books (OTB) room nights are the nights of a reservation that fall after the latest load and remain booked. Cancelled and no-show nights are zero, so they are never OTB. Booking Pace counts reservations or nights booked by a given date for a given stay window, and compares that with the same measure last year.

## How it's calculated
```
OTB Room Nights = SUM(otb_room_nights_count)
FROM `{{catalog}}.{{mart}}.fact_reservation_summary`
WHERE is_current AND reservation_cancel_flag = false
```
Booking pace on a date D for a stay window:
```
COUNT(DISTINCT bk_reservation_id)
WHERE is_current AND reservation_cancel_flag = false
  AND booked_date <= D
  AND current_arrival_date BETWEEN window_start AND window_end
```
`booked_date` is already a DATE. Calendar joins to `{{catalog}}.{{common}}.dim_date` use `CAST(bk_date_id AS INT)`.

## Where it lives
Measures are in `{{catalog}}.{{semantic}}.booking_metrics`. Rows come from `{{catalog}}.{{mart}}.fact_reservation_summary`. Calendar fields come from `{{catalog}}.{{common}}.dim_date`.

## Notes
- The table holds the position as of the latest load. Earlier positions are not stored, so pace uses `booked_date` and does not restore cancellations or changes as they stood on that date.
- A date change keeps the prior version with `is_current = false`. Count only current rows.
- OTB nights are not Room Nights. Nights become Room Nights only once the stay occurs.
- Compare with the same stay window last year, using the rules on Selected Time Period.

## Related
Room Nights, Cancellation, Channel, Selected Time Period (MTD and YoY), Current vs History Rows, Length of Stay and OTB 4 Tier
