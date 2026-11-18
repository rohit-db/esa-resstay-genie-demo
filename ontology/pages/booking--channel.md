---
display_name: Channel
subdomain: booking
synonyms: [channel, booking channel, sales channel, distribution channel, OTA, booking source]
description: The route a reservation was booked through, such as Brand Web, Call Center, Walk-In, GDS or an OTA, grouped as Direct or Indirect.
assumption: true
mentions: [mart.dim_channel, mart.fact_actual_stay, mart.fact_reservation_summary, semantic.booking_metrics, semantic.resstay_metrics]
requires: []
---
## Definition
Channel is the route a reservation was booked through. The channels are Brand Web, Mobile App, Call Center, Walk-In, OTA - Expedia, OTA - Booking.com, GDS and Corporate Sales. Each channel rolls up to a network: Direct or Indirect. Indirect covers the two OTA channels and GDS. Corporate Sales is Direct.

## How it's calculated
A stay has no channel of its own. Room revenue by channel goes through the reservation:
```
SELECT c.channel_network, c.channel_name, SUM(s.room_revenue_amount)
FROM `{{catalog}}.{{mart}}.fact_actual_stay` AS s
JOIN `{{catalog}}.{{mart}}.fact_reservation_summary` AS r
  ON r.bk_reservation_id = s.bk_reservation_id AND r.is_current
JOIN `{{catalog}}.{{mart}}.dim_channel` AS c
  ON c.bk_channel_id = r.bk_channel_id AND c.is_current
GROUP BY c.channel_network, c.channel_name
```

## Where it lives
Channel attributes are on `{{catalog}}.{{mart}}.dim_channel`, which holds channel_network, channel_name, channel_platform and channel_partner. The booking measures are in `{{catalog}}.{{semantic}}.booking_metrics`. Room revenue by channel is in `{{catalog}}.{{semantic}}.resstay_metrics`.

## Notes
- The channel is set when the reservation is booked, and every stay keeps the channel of its reservation.
- Report on `channel_name`. The `bk_channel_id` codes are keys and are not for display.
- Booking counts include cancelled reservations unless they are filtered out. See Cancellation.

## Related
Rate Segment, Promotion and Stay 7+, CRM Account and Tier, On-the-Books and Booking Pace, Cancellation, Room Revenue, Average Daily Rate (ADR)
