---
display_name: ResStay Revenue Q&A
subdomain: resstay
synonyms: [ResStay Revenue agent, revenue Genie, ResStay Q&A, revenue questions, ask about revenue]
description: The ESA ResStay Revenue Genie agent for room revenue, room nights, ADR, length of stay, brand, district, channel, promotion and account questions.
assumption: true
mentions: [genie:resstay_revenue, common.dim_date, mart.fact_actual_stay, mart.fact_reservation_summary, mart.vw_dim_property, mart.dim_channel, mart.dim_rate_segment, mart.dim_promotion, mart.dim_crm_account, mart.dim_los, mart.dim_room_type, semantic.resstay_metrics, semantic.booking_metrics]
requires: [genie:resstay_revenue]
---
## Definition
ResStay Revenue Q&A is the Genie agent for room revenue questions. It uses ESA vocabulary: Selected Time Period, YoY, the OTB 4 Tier, ESAS, ESSS and ESAP, Comp Status, DVP, RVP/RDO, DM and GM, net versus total revenue, and Tiger Site. It answers KPI questions from the metric views and shows the SQL it ran.

## How it's calculated
Sample questions:
- What was month-to-date room revenue versus last year, by brand?
- Which district managers grew room revenue the most versus last year this month?
- How did room nights in the 7 to 14 night tier change year over year?
- Which channels are declining year over year?
- Which corporate accounts booked the most room nights in the last 90 days?

Answers rely on the definitions on the linked Pages, including Room Revenue, Net Room Revenue, Room Nights, ADR, Selected Time Period, Length of Stay and OTB 4 Tier, Brand, Comp Status, Channel, Rate Segment, Promotion and Stay 7+, and CRM Account and Tier.

## Where it lives
[Open the ResStay Revenue agent]({{url_genie_resstay_revenue}})

KPIs come from `{{catalog}}.{{semantic}}.resstay_metrics` and `{{catalog}}.{{semantic}}.booking_metrics`. Base tables are `{{catalog}}.{{mart}}.fact_actual_stay`, `{{catalog}}.{{mart}}.fact_reservation_summary`, `{{catalog}}.{{mart}}.vw_dim_property`, `{{catalog}}.{{mart}}.dim_channel`, `{{catalog}}.{{mart}}.dim_rate_segment`, `{{catalog}}.{{mart}}.dim_promotion`, `{{catalog}}.{{mart}}.dim_crm_account`, `{{catalog}}.{{mart}}.dim_los`, `{{catalog}}.{{mart}}.dim_room_type` and `{{catalog}}.{{common}}.dim_date`.

## Notes
- Answers cite only these sources and the ESA Pages.
- Dimension joins filter `is_current = true`. The cast rule applies to `bk_date_id` in the stay and reservation facts.
- Check the generated SQL before quoting a figure.

## Related
Room Revenue, Net Room Revenue, Room Nights, Average Daily Rate (ADR), Selected Time Period (MTD and YoY), Length of Stay and OTB 4 Tier, Brand, Comp Status, Channel, Rate Segment, Promotion and Stay 7+, CRM Account and Tier, On-the-Books and Booking Pace, Cancellation, ResStay Dashboard at a Glance
