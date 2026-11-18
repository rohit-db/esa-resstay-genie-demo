---
display_name: Occupancy Trend by Week
subdomain: occupancy
synonyms: [occupancy trend, weekly occupancy, occupancy dashboard, occupancy trend dashboard, weekly trend]
description: The AI/BI dashboard of weekly occupancy this year versus last year by brand and district, with an out-of-order rooms overlay and RevPAR.
assumption: true
mentions: [dashboard:occupancy, common.dim_date, mart.vw_dim_property, semantic.occupancy_metrics]
requires: [dashboard:occupancy]
---
## Definition
Occupancy Trend by Week is the AI/BI dashboard for weekly occupancy. It compares each week with the same week last year, by brand and by district, and overlays out-of-order rooms. Use it to see whether occupancy is moving and where, then open the Pages that define each measure.

## How it's calculated
What is on it:
- Weekly Occupancy % this year versus last year, by brand and by district.
- An out-of-order rooms overlay for the same weeks.
- RevPAR for the same weeks.

Weeks run from `Week_Start_Dt` to `Week_End_Dt` in `{{catalog}}.{{common}}.dim_date`. The prior-year comparison uses `Same_Day_Last_Yr_Dt`, as defined on Selected Time Period.

## Where it lives
Datasets query `{{catalog}}.{{semantic}}.occupancy_metrics`. Brand and district attributes come from `{{catalog}}.{{mart}}.vw_dim_property`.

[Open the Occupancy Trend by Week dashboard]({{url_dashboard_occupancy}})

## Notes
- Because `Same_Day_Last_Yr_Dt` moves a date by one calendar year, the prior-year week can start on a different weekday. `Same_Weekday_Last_Yr_Dt` keeps weekdays aligned if the layout changes.
- The current week is partial until the latest load covers it.
- Each viewer sees only the hotels their row-level access allows.

## Related
Occupancy %, Available vs Out-of-Order Rooms, RevPAR, Selected Time Period (MTD and YoY), Brand, Property Operations Q&A
