---
display_name: Net Room Revenue
subdomain: resstay
synonyms: [net room revenue, net room sales, room revenue after credits, net rooms revenue]
description: Room revenue less room credits and write-offs on the same stay lines. Shown beside Room Revenue on the ResStay dashboard.
assumption: true
mentions: [mart.fact_actual_stay, common.dim_date, semantic.resstay_metrics]
requires: []
---
## Definition
Net Room Revenue is Room Revenue less the credits posted against it. Credits are amounts taken back from room charges after a stay. Net Room Revenue is the room revenue that remains after those credits.

## How it's calculated
```
Net Room Revenue = SUM(room_revenue_amount) - SUM(credit_revenue_amount)
FROM `{{catalog}}.{{mart}}.fact_actual_stay`
```
On each line, the column `net_room_revenue` equals `room_revenue_amount - credit_revenue_amount`, so `SUM(net_room_revenue)` gives the same total. Always sum the columns; never average per-line ratios. Filter by calendar through `{{catalog}}.{{common}}.dim_date`, joining on the cast `bk_date_id`.

## Where it lives
The measure is defined in the ResStay metric view `{{catalog}}.{{semantic}}.resstay_metrics`. Stay lines come from `{{catalog}}.{{mart}}.fact_actual_stay`.

## Notes
- Credit lines are separate rows with `consumed_room_nights_count = 0`. Each is dated to the night the stay departed, and it appears only once the stay has departed by the latest load.
- Net Room Revenue does not feed ADR. ADR uses gross Room Revenue.
- Use this measure when a question asks for revenue after credits. Use Room Revenue when it asks for gross charges.

## Related
Room Revenue, Room Credits and Write-offs, Average Daily Rate (ADR), Selected Time Period (MTD and YoY), Room Nights
