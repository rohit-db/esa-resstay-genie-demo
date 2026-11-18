---
display_name: Promotion and Stay 7+
subdomain: booking
synonyms: [promotion, promo, promo code, Stay 7+, Stay 7+ and Save, promotion code]
description: The campaign or discount code on a reservation, including Stay 7+ and Save for 7 to 14 night stays. One code per reservation, with NONE when no promotion applies.
assumption: true
mentions: [mart.dim_promotion, mart.fact_reservation_summary, semantic.booking_metrics, common.dim_date]
requires: []
---
## Definition
Promotion is the campaign or discount code on a reservation. Each reservation carries one code in `bk_promo_cd`, and NONE means no promotion applies. The codes are NONE, STAY7 (Stay 7+ and Save), MONTH30 (Monthly Saver), APPONLY (App Exclusive Rate), BOOKEARLY (Book Early Discount), SENIOR (Senior Saver), RELO (Relocation Package) and WEEKEND (Weekend Getaway). Stay 7+ and Save applies to stays of 7 to 14 nights whose arrival falls inside the campaign window. It is not applied to every eligible stay.

## How it's calculated
Campaign windows are tested on the arrival date, and the length-of-stay range comes from the promotion row:
```
SELECT p.promotion_name, COUNT(DISTINCT r.bk_reservation_id)
FROM `{{catalog}}.{{mart}}.fact_reservation_summary` AS r
JOIN `{{catalog}}.{{mart}}.dim_promotion` AS p
  ON p.bk_promo_cd = r.bk_promo_cd AND p.is_current
WHERE r.is_current
  AND r.current_arrival_date BETWEEN p.promo_start_date AND p.promo_end_date
GROUP BY p.promotion_name
```
For a Stay 7+ view, also require `r.current_room_nights_count BETWEEN p.min_los_nights AND p.max_los_nights`.

## Where it lives
`{{catalog}}.{{mart}}.dim_promotion` holds promotion_name, campaign_name, discount_type, discount_value, min_los_nights, max_los_nights, promo_start_date and promo_end_date. The code is on each row of `{{catalog}}.{{mart}}.fact_reservation_summary`. Measures are in `{{catalog}}.{{semantic}}.booking_metrics`, and calendar fields come from `{{catalog}}.{{common}}.dim_date`.

## Notes
- The discount amount is stored on `dim_promotion`. This Page does not restate it.
- Discounts reduce the rate on the stay, so ADR moves with promotion mix.
- Promotion and Rate Segment are independent. A reservation has one of each.
- Filter `is_current = true` on joins.

## Related
Rate Segment, Length of Stay and OTB 4 Tier, Average Daily Rate (ADR), Channel, On-the-Books and Booking Pace
