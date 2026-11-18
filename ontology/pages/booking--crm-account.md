---
display_name: CRM Account and Tier
subdomain: booking
synonyms: [CRM account, corporate account, account tier, key account, parent account, B2B account]
description: The Salesforce business account a reservation is booked under, with its tier, status and parent and ultimate parent for roll-ups.
assumption: true
mentions: [mart.dim_crm_account, mart.fact_reservation_summary, semantic.booking_metrics]
requires: []
---
## Definition
A CRM account is the business account a reservation is booked under, such as a corporate customer, a staffing agency or a government body. Account Tier is one of Platinum, Gold, Silver or Bronze. Platinum marks key accounts, which carry `key_account_flag = true`. Tier is a CRM attribute. It is not a revenue rank calculated in this model. Account type is one of Corporate, Insurance / Relocation, Staffing Agency, Government, Airline or Travel Management Company. Status is Active, Inactive or Prospect.

## How it's calculated
Roll reservations up to their top-level account with the ultimate parent:
```
SELECT COALESCE(a.ultimate_parent_account_name, a.account_name) AS account_group,
       SUM(r.actual_room_nights_count) AS room_nights
FROM `{{catalog}}.{{mart}}.fact_reservation_summary` AS r
JOIN `{{catalog}}.{{mart}}.dim_crm_account` AS a
  ON a.bk_crm_account_id = r.bk_crm_account_id AND a.is_current
WHERE r.is_current
GROUP BY 1
```

## Where it lives
`{{catalog}}.{{mart}}.dim_crm_account` holds account_name, account_type, account_status, account_tier, key_account_flag, the parent and ultimate parent columns, merged_into_account_id, industry_name and preferred_rate_segment_id. Each reservation links through `bk_crm_account_id` on `{{catalog}}.{{mart}}.fact_reservation_summary`. Measures are in `{{catalog}}.{{semantic}}.booking_metrics`.

## Notes
- Merged accounts carry status Inactive and point to their successor in `merged_into_account_id`. Report them under the successor.
- Account owner name and email are personal data. Do not show them in answers.
- Blank `bk_crm_account_id` means the reservation has no account, which is normal for leisure bookings.
- Filter `is_current = true` on joins.

## Related
Rate Segment, Channel, Room Nights, On-the-Books and Booking Pace, Cancellation
