---
display_name: Selected Time Period (MTD and YoY)
subdomain: resstay
synonyms: [MTD, month to date, YoY, year over year, QTD, YTD, last 7 days]
description: How MTD, QTD, YTD and Last 7 Days are anchored to the latest loaded night audit, and how YoY uses the same calendar window one year earlier.
assumption: true
mentions: [mart.fact_actual_stay, common.dim_date, semantic.resstay_metrics]
requires: []
---
## Definition
Selected Time Period is the reporting window shared by ResStay and the Genie agents. Its anchor is the latest loaded date, the last completed night audit, not today's date. MTD is month to date, QTD is quarter to date, YTD is year to date, and Last 7 Days is the seven nights ending on the anchor. A custom range is also allowed. YoY compares the selected window with the same window one year earlier.

## How it's calculated
- Anchor: the maximum stay date in `{{catalog}}.{{mart}}.fact_actual_stay`, computed as `MAX(CAST(bk_date_id AS INT))`.
- MTD: from `Month_Start_Dt` of the anchor's month through the anchor.
- QTD: from the first day of the anchor's quarter (`Qtr_Nbr` within `Yr_Nbr`) through the anchor.
- YTD: from January 1 of the anchor's year (`Yr_Nbr`) through the anchor.
- Last 7 Days: the anchor minus six days through the anchor.
- YoY: each date in the window maps to `Same_Day_Last_Yr_Dt` in `{{catalog}}.{{common}}.dim_date`. Compare day for day, so a partial month is compared with the same partial prior-year window.

## Where it lives
Periods are not stored in the metric view. Dashboard datasets and Genie example SQL compute current-period and same-window-last-year sets over `{{catalog}}.{{semantic}}.resstay_metrics`, using the calendar fields on `{{catalog}}.{{common}}.dim_date`.

## Notes
- `Same_Day_Last_Yr_Dt` keeps the calendar date. `Same_Weekday_Last_Yr_Dt` (364 days back) keeps the weekday instead, and is the choice when weekday alignment matters.
- The anchor moves forward with each nightly refresh.
- Data before the synthetic history start is not loaded, so YoY is valid only for dates a full year or more after that start.
- Use the anchor, not the current clock date, when a question says "this month" or "last 7 days".

## Related
Room Revenue, Room Nights, Average Daily Rate (ADR), Occupancy %, RevPAR, Occupancy Trend by Week
