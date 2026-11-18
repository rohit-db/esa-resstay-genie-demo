---
display_name: Rate Segment
subdomain: booking
synonyms: [rate segment, rate type, rate category, rate plan, corporate rate, negotiated rate, BAR]
description: The pricing category a stay was sold under, such as Best Available Rate, Corporate Negotiated, Government, OTA Merchant or Complimentary. Carries the rate category and rate type.
assumption: true
mentions: [mart.dim_rate_segment, mart.fact_actual_stay, mart.fact_reservation_summary, semantic.resstay_metrics]
requires: []
---
## Definition
Rate Segment is the pricing category a stay is sold under. The ten segments are Best Available Rate, Weekly Rate, Monthly Rate, Corporate Negotiated, Government / Military, AAA / Senior, OTA Merchant, Airline Crew, Relocation / Insurance and Complimentary. Each has a rate category: Transient, Extended Stay, Corporate, Government, Discount, Wholesale, Contract or Complimentary. Each has a rate type: Public, Negotiated, Qualified, Merchant, Contract or Non-Revenue.

## How it's calculated
The segment sits on each stay line and on each reservation:
```
SELECT rs.rate_category, SUM(s.room_revenue_amount), SUM(s.consumed_room_nights_count)
FROM `{{catalog}}.{{mart}}.fact_actual_stay` AS s
JOIN `{{catalog}}.{{mart}}.dim_rate_segment` AS rs
  ON rs.bk_rate_segment_id = s.bk_rate_segment_id AND rs.is_current
GROUP BY rs.rate_category
```

## Where it lives
`{{catalog}}.{{mart}}.dim_rate_segment` holds rate_segment_name, rate_category, rate_code, rate_type and rate_partner. The segment key is on `{{catalog}}.{{mart}}.fact_actual_stay` and on `{{catalog}}.{{mart}}.fact_reservation_summary`. Measures roll up in `{{catalog}}.{{semantic}}.resstay_metrics`.

## Notes
- Complimentary has rate type Non-Revenue. Its nights carry zero room revenue and are reported as comp rooms (see Paid vs Comp Rooms).
- Rate Segment is the price basis. Promotion is a separate code, so a reservation has one segment and at most one promotion code.
- Rate partner is blank for public segments.
- Filter `is_current = true` on dimension joins.

## Related
Promotion and Stay 7+, Channel, Average Daily Rate (ADR), Paid vs Comp Rooms, CRM Account and Tier
