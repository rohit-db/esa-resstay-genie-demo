# ESA ResStay Genie demo

A synthetic replica of Extended Stay America's `dev_gold` gold model (20 objects from `dev_gold.mart`, plus
`dim_date`) for an end-to-end Databricks demo:
- business descriptions and certified metric views;
- the ResStay and Occupancy dashboards;
- two Genie agents, Discover domains and Pages, and Genie One;
- hierarchy row-level security with switchable personas.

All hotels, people, accounts, and figures are synthetic.

- **Run the demo:** `docs/demo-script.md`
- **Operate it:** `docs/runbook.md` (deploy, personas, validation, guarded cleanup)
- **Change it (agents and contributors):** `AGENTS.md`

## Prerequisites

- Databricks CLI 1.22 or later, and `uv`
- A Databricks CLI profile for the target workspace. The `demo` target in `databricks.yml` points at the original
  sandbox; set `targets.demo.workspace` (host and `workspace_id`) to your own workspace, which needs account-level
  rights for governed tags and Discover domains.

## Set up and test

    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python -r requirements-dev.txt
    .venv/bin/python -m pytest -q

## Deploy

    ./deploy.sh --profile esa-resstay-demo --target demo [--as-of YYYY-MM-DD] [--nightly on|off] [--skip-data]
    .venv/bin/python tools/demo_links.py        # today's links to every demo asset

Deploy runs these steps:
1. Creates `dev_gold` in this workspace's storage and binds it to this workspace only.
2. Deploys the bundle: a Medium serverless SQL warehouse, setup and nightly jobs, both Genie agents, and both
   dashboards.
3. Generates about 33 million stay lines.
4. Applies comments, metric views, and row security.
5. Publishes the Discover ontology.
6. Validates everything (`docs/runbook.md#validation`).

It takes about 45 minutes, and reruns are safe. The first deploy's as-of date becomes the story anchor. Deploys more
than 30 days later are refused, because the planted renovation ends then.

## What is where

| Layer | Source | Live objects |
|---|---|---|
| Data | `contract/dev_gold_mart.yml`, `src/esa_resstay_demo/` | `dev_gold.mart`, `dev_gold.common`, `dev_gold.staging` |
| Semantics | `contract/descriptions.yml`, `src/sql/50_metric_views.sql.tmpl` | UC comments; `dev_gold.semantic.*_metrics` |
| Security | `src/sql/60_security.sql.tmpl`, `security/personas.yml` | `dev_gold.security`; row filters on nine objects |
| Dashboards | `tools/lib/dashboards.py`, `resources/dashboards.yml` | ResStay Dashboard, Occupancy Trend by Week |
| Genie | `genie/*.yml`, `resources/genie_spaces.yml` | ESA ResStay Revenue, ESA Property Operations |
| Ontology | `ontology/domains.yml`, `ontology/pages/*.md` | Two ESA domains, four subdomains, 28 Pages |

ESA's quirks are kept on purpose:
- `bk_date_id` is a string in the stay and reservation facts but an int in `fact_property_statistics` and `dim_date`.
- `dim_date` uses PascalCase and lives in a separate schema.
- History rows mean `is_current = true` matters.

## Safety

Every command needs an explicit `--profile`, and deploy refuses any workspace other than the target's host.
Everything created is recorded in `.state/manifest.json`, and nothing outside it is modified. Discover objects live in
a sandbox account shared with other teams. Every one of them is named `ESA ...` and is changed only if this repo
created it.
