---
display_name: Cancellation
subdomain: booking
synonyms: [cancellations, cancellation rate, cancel rate, cancelled bookings, cancels]
description: A reservation cancelled on or before the latest load. Cancellation Rate is cancelled reservations divided by all reservations in the same booking window.
assumption: true
mentions: [mart.fact_reservation_summary, mart.fact_actual_stay, mart.dim_reservation, common.dim_date, semantic.booking_metrics]
requires: []
---
## Definition
A reservation is cancelled when `reservation_cancel_flag` is true. That requires the cancellation date to be on or before the latest load. A booking whose cancellation is dated after the latest load is still live. No-shows are not cancellations. They have their own status, `No Show`, in `dim_reservation`.

## How it's calculated
```
Cancellation Rate = SUM(CASE WHEN reservation_cancel_flag THEN 1 ELSE 0 END)
                    / COUNT(DISTINCT bk_reservation_id)
FROM `{{catalog}}.{{mart}}.fact_reservation_summary`
WHERE is_current
  AND booked_date BETWEEN window_start AND window_end
```
The denominator includes cancelled reservations. Use `booked_date` for the window. Calendar fields come from `{{catalog}}.{{common}}.dim_date`, joined on `CAST(bk_date_id AS INT)`.

## Where it lives
Cancellation Rate is a measure in `{{catalog}}.{{semantic}}.booking_metrics`. Rows come from `{{catalog}}.{{mart}}.fact_reservation_summary`. The status text (`Cancelled`, `No Show`) is on `{{catalog}}.{{mart}}.dim_reservation`, matched on `bk_reservation_id` with `is_current = true`.

## Notes
- Cancelled reservations are separate rows. They never appear as stays in `{{catalog}}.{{mart}}.fact_actual_stay`.
- No-shows count in the denominator but not in the numerator.
- A cancellation dated after the latest load is not counted yet.
- Filter on `reservation_cancel_flag` for cancellation counts, and on `dim_reservation.reservation_status` only when a report needs the status label.

## Related
On-the-Books and Booking Pace, Channel, Room Nights, CRM Account and Tier, Current vs History Rows
