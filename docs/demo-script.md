# ESA ResStay demo: talk track (about 30 minutes)

All hotels, people, accounts, and figures are synthetic. The model, names, and reports mirror ESA's own `dev_gold.mart`
and the Tableau ResStay Dashboard, so everything here can later point at ESA's real tables (`-t esa`).

## Before the call (10 minutes)

1. `./.venv/bin/python tools/validate.py --profile esa-resstay-demo` passes. Genie One may report `review`; read those
   three answers once.
2. `./.venv/bin/python tools/demo_links.py` prints today's links (IDs change on every redeploy). Open in tabs:
   - the **ADR Page** (the "Find it, define it" entry point; never open the top-level Discover page or Manage Domains,
     because the sandbox account lists other teams' domains);
   - the **ResStay Dashboard**, the **Occupancy Trend by Week** dashboard, and both **Genie agents**;
   - **Catalog Explorer** on `dev_gold.mart.fact_actual_stay` and `dev_gold.semantic.resstay_metrics`.
3. Warm the warehouse: open the ResStay Dashboard once. The first load takes about 15 seconds; later loads are cached.
4. Confirm the persona is corporate: `./.venv/bin/python tools/set_persona.py --profile esa-resstay-demo --persona corporate`
   (prints `Visible hotels 600 (expected 600)`).
5. Data runs through the last night audit recorded by the deploy. With the nightly refresh paused, "month to date"
   means the first of the month through that date. `./deploy.sh ... --skip-data --nightly on` keeps it current.

## 1. Your model, described (4 minutes)

- Catalog Explorer, `dev_gold.mart`: the same 20 objects ESA has, with ESA's names and quirks, including the
  PascalCase `common.dim_date` and the string `bk_date_id`.
- Open `fact_actual_stay`: every table and column now has a **business description** (grain, units, join keys, the
  `is_current` rule) instead of only an AI-suggested one.
- Open `dev_gold.semantic.resstay_metrics`: a **certified metric view**. Room Revenue, Net Room Revenue, Room Nights,
  ADR, and Stays are defined once, with joins to the property, date, channel, and length-of-stay dimensions on current
  rows only. Dashboards, Genie, and SQL all read these definitions.

## 2. Your ResStay, on Databricks (6 minutes)

- **Overview:** the four KPI tiles against last year, each with a 13-month trend; LOS – Room Revenue by OTB 4 Tier;
  Brand; Channel; and the leader ranking by variance to last year (switch **View By** between DM, RVP/RDO, and DVP).
- Filter panel: Selected Time Period (MTD, QTD, YTD, last 7 or 28 days), Comp Status, Brand, DVP, RVP/RDO, District
  Manager, Market, Tiger Site. Set **Comp Status = Comp** to show like-for-like results.
- **Detailed View:** every hotel with the four KPIs plus Occupancy and RevPAR and their changes.
- **Property Comparison:** opens on Texas District 2; each hotel against its district average, with monthly trends.
- Story to land: the leader ranking's laggard is the Texas District 2 manager. Ask the room why, then go to Genie.

## 3. Ask it (6 minutes)

**ESA ResStay Revenue** agent (sample questions are on screen):
- "What is month-to-date room revenue vs last year by brand?" — all three brands up about 4–5%; show the generated
  SQL reading `resstay_metrics` with the MTD window ending on the latest night audit.
- "Which district managers grew room revenue the most vs last year this month?"
- "How did 7–14 night stays change year over year?" — the Stay 7+ promotion lifts that tier.

**ESA Property Operations** agent:
- "Which district has the highest out-of-order share over the last 4 weeks, and which of its hotels are under
  renovation?" — Texas District 2 at about 16%, four Dallas hotels in a full renovation.
- "Which Tiger Sites are below 70% occupancy month to date?"

## 4. Find it, define it (5 minutes)

- Start on the **ADR Page**: the definition, the formula, where it lives (the certified measure), and the banner
  "Demo definition — confirm with ESA".
- Use the breadcrumb to open the **ESA Revenue Management** domain → **ResStay** subdomain: its tables, the metric view,
  the ResStay Dashboard, the ResStay Revenue agent, and the Pages (Room Revenue, Net Room Revenue, LOS and OTB 4 Tier,
  Comp Status, Brand).
- Then **ESA Property Operations** → **Portfolio and Hierarchy**: the Tiger Site and ESA Org Hierarchy Pages.
- Point: business definitions, data, dashboards, and agents are organized the way ESA talks about the business.

## 5. Genie One across domains (5 minutes)

Ask these in order in one Genie One conversation (they are the validated hero prompts):

1. "Using the dev_gold catalog: what does ADR mean at ESA, and how is it trending month to date vs last year by
   brand?" — cites the ADR, Brand, and Selected Time Period Pages; ADR is up for all three brands.
2. "In dev_gold, which district has the biggest room revenue decline vs last year this month, and what is driving
   it?" — Texas District 2, down about 19%, driven by lost room nights at four Non-Comp Dallas hotels.
3. "For that district, which hotels are under renovation, and how many room nights did out-of-order rooms cost this
   month?" — the four Dallas hotels and thousands of out-of-order room nights against a few hundred last year.

Point: Genie One finds the right agents, metric views, and Pages on its own and cites them.

## 6. Same question, different role (4 minutes)

1. `./.venv/bin/python tools/set_persona.py --profile esa-resstay-demo --persona dm` (prints 10 visible hotels).
2. Refresh the ResStay Dashboard: every tile, chart, and ranking now covers only Texas District 2. Ask the ResStay
   Revenue agent the brand question again: the answer covers the same ten hotels.
3. Optional: `--persona rvp` (40 hotels, the Texas region) or `--persona dvp` (160 hotels, the South division).
4. **Reset:** `--persona corporate`. Always end here; the nightly data checks expect corporate access.

Point: one row filter in Unity Catalog governs the tables, the metric views, the dashboards, and Genie alike.

## If something goes wrong

- A dashboard tile is slow: the warehouse may be cold; wait for the first load.
- Genie phrasing differs from the script: the numbers come from the certified metric views; re-ask with the sample
  question wording.
- The persona looks wrong: run `set_persona.py --persona corporate` and refresh.
