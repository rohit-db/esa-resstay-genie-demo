---
display_name: Room Credits and Write-offs
subdomain: resstay
synonyms: [room credits, credits, write-offs, room write-offs, credit revenue, guest credits]
description: Amounts credited back against room revenue after a stay departs. Shown as Credit Revenue and deducted to reach Net Room Revenue.
assumption: true
mentions: [mart.fact_actual_stay, common.dim_date, semantic.resstay_metrics]
requires: []
---
## Definition
Room Credits and Write-offs are amounts taken back from room revenue after a stay, either credited to the guest or written off. This model records both in one field, `credit_revenue_amount`, so credits and write-offs cannot be reported separately. Credit Revenue is the total of that field.

## How it's calculated
```
Credit Revenue = SUM(credit_revenue_amount)
FROM `{{catalog}}.{{mart}}.fact_actual_stay`
```
Credit lines have `consumed_room_nights_count = 0`, so they add no room nights. Net Room Revenue is Room Revenue minus this total. Calendar filters join `{{catalog}}.{{common}}.dim_date` on the cast `bk_date_id`.

## Where it lives
Credit Revenue is a measure in `{{catalog}}.{{semantic}}.resstay_metrics`. Credit lines are rows in `{{catalog}}.{{mart}}.fact_actual_stay`.

## Notes
- A credit line is dated to the night the stay departed, so the credit falls in the period when the stay leaves, not when it was charged.
- Only stays that have departed by the latest load produce credit lines.
- Credits do not change ADR.
- If write-offs must be reported apart from credits, the model needs a separate column.

## Related
Room Revenue, Net Room Revenue, Average Daily Rate (ADR), Selected Time Period (MTD and YoY)
