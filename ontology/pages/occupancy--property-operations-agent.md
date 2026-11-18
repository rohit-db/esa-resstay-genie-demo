---
display_name: Property Operations Q&A
subdomain: occupancy
synonyms: [property operations agent, operations Genie, occupancy Q&A, hotel operations questions, property questions]
description: The ESA Property Operations Genie agent for occupancy, out-of-order rooms, renovations, RevPAR, Tiger Site and Comp Status questions.
assumption: true
mentions: [genie:property_operations, common.dim_date, mart.fact_property_statistics, mart.vw_dim_property, mart.dim_property_renovation, mart.fact_property_renovation, mart.dim_property_hierarchy, mart.dim_property_segment, semantic.occupancy_metrics]
requires: [genie:property_operations]
---
## Definition
Property Operations Q&A is the Genie agent for hotel operations questions. It covers occupancy, available and out-of-order rooms, renovations, RevPAR, Tiger Sites and Comp Status. It uses the ESA vocabulary from the linked Pages and takes KPIs from the occupancy metric view.

## How it's calculated
Sample questions:
- Which districts lost the most occupancy versus last year over the last four weeks?
- How did weekly occupancy for hotels under renovation compare with the rest of their district?
- Which Tiger Sites are below target occupancy month to date?
- What was RevPAR by brand and market last quarter?

Answers rely on the definitions on Occupancy %, Available vs Out-of-Order Rooms, RevPAR, Paid vs Comp Rooms, Renovation, Property Segment, ESA Org Hierarchy, Comp Status and Selected Time Period.

## Where it lives
[Open the Property Operations Q&A agent]({{url_genie_property_operations}})

KPIs come from `{{catalog}}.{{semantic}}.occupancy_metrics`. Base tables are `{{catalog}}.{{mart}}.fact_property_statistics`, `{{catalog}}.{{mart}}.vw_dim_property`, `{{catalog}}.{{mart}}.dim_property_renovation`, `{{catalog}}.{{mart}}.fact_property_renovation`, `{{catalog}}.{{mart}}.dim_property_hierarchy`, `{{catalog}}.{{mart}}.dim_property_segment` and `{{catalog}}.{{common}}.dim_date`.

## Notes
- Answers cite only these sources and the ESA Pages.
- `bk_date_id` in `fact_property_statistics` is an integer, so no cast is needed there. Dimension joins filter `is_current = true`.
- Check the generated SQL before quoting a figure.

## Related
Occupancy %, Available vs Out-of-Order Rooms, RevPAR, Paid vs Comp Rooms, Renovation, Tiger Site, Property Segment, ESA Org Hierarchy, Comp Status, Selected Time Period (MTD and YoY), Occupancy Trend by Week
