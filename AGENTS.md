# AGENTS.md: how to work in this repo

This repo builds a complete, synthetic Databricks demo on a replica of Extended Stay America's (ESA) gold model
(`dev_gold.mart`). It covers:
- data, business descriptions, and certified metric views;
- two AI/BI dashboards and two Genie agents;
- Discover domains, subdomains, and Pages;
- hierarchy row-level security.

Everything is generated from files in this repo and deployed with one command. Read this file before you change
anything; `README.md` is the human overview and `docs/runbook.md` the operator's guide.

## Ground rules

1. **Always pass `--profile <name>`.** Every tool refuses to run without it and ignores `DATABRICKS_*` variables. The
   tools also refuse a profile whose host differs from `targets.<target>.workspace.host` in `databricks.yml`.
2. **Only touch what the manifest records.** `.state/manifest.json` records every object this repo created: catalog,
   jobs, dashboards, Genie spaces, governed tags, domains, and Pages. Never modify or delete anything else.
3. **The Discover account is shared with other teams.** Governed tags, domains, and Pages are account-level. Ours
   are all named `ESA ...`. If `tools/ontology.py` stops with "did not create", someone else owns that name: report
   it, never adopt or delete their object.
4. **Ask a human first** before:
   - `databricks bundle deploy --force`, which overwrites UI edits to dashboards;
   - `tools/cleanup.py --confirm`;
   - dropping the catalog;
   - creating objects in a new account.
5. **Never commit `.state/` or `build/`** (both are git-ignored). Keep `.state/` with the checkout; it is how reruns
   stay safe.
6. **Synthetic content only.** No real people, emails, or real ESA figures in data, Pages, descriptions, or Genie
   instructions. Page content is replicated globally.
7. **Reset the persona** with `tools/set_persona.py --persona corporate` after any persona work.
8. **Respect the story window.** The planted stories are anchored to `story_anchor_date` in the manifest, so
   `--as-of` must fall within 30 days after it.
9. **Generated objects are overwritten on every deploy.** Edit the source files, not the live objects. If someone
   edits a dashboard in the UI, port the edit into `tools/lib/dashboards.py`, then ask before `--force`.

## Setup and tests

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest -q          # about 50 seconds; no workspace needed
```

Tests never call Databricks. CLI calls go through `tools/lib/dbcli.Cli`, which tests replace with the `fake_cli`
fixture in `tests/conftest.py`. Write the failing test first, then the change.

## Commands

| Task | Command |
|---|---|
| Full deploy (data, semantics, security, ontology, validation; about 45 minutes) | `./deploy.sh --profile P --target demo` |
| Redeploy without regenerating data | `./deploy.sh --profile P --target demo --skip-data` |
| Render templates into `build/` (no workspace) | `.venv/bin/python tools/render.py --target demo` |
| Re-apply one rendered SQL file | `.venv/bin/python tools/run_sql.py --profile P build/sql/50_metric_views.sql` |
| Validate (all, or `--sections a,b`) | `.venv/bin/python tools/validate.py --profile P` |
| Discover ontology | `.venv/bin/python tools/ontology.py plan\|apply\|verify --profile P` |
| Switch persona | `.venv/bin/python tools/set_persona.py --profile P --persona corporate\|dvp\|rvp\|dm\|none` |
| Print current links | `.venv/bin/python tools/demo_links.py` |
| Cleanup plan (dry run) | `.venv/bin/python tools/cleanup.py --profile P` |

## How the pieces fit

1. **`contract/dev_gold_mart.yml`** is the single table contract: names, types, keys, and join targets. The rest of
   the stack is generated from it:
   - `tools/lib/sqlgen.py` generates the DDL, the staging-to-mart loads, and the materialized view;
   - `tools/lib/checks.py` generates the data checks;
   - the generator (`src/esa_resstay_demo/`) reads it to write the staging tables.
2. **`contract/descriptions.yml`** holds the business description of every table and column. `tools/lib/comments.py`
   turns it into `COMMENT` statements.
3. **Templates** in `src/sql/*.sql.tmpl` use `{{catalog}}`, `{{mart}}`, `{{common}}`, `{{semantic}}`, `{{staging}}`,
   and `{{security}}`, filled from the bundle target's variables. `tools/render.py` writes everything into `build/`,
   including the Genie spaces and the dashboard JSON.
4. **The bundle** (`databricks.yml`, `resources/`) deploys the warehouse, the setup and nightly jobs, both Genie
   spaces, and both dashboards. The setup job runs these tasks in order:
   1. schemas;
   2. generate (wheel);
   3. tables;
   4. load;
   5. views and the materialized view;
   6. comments, metric views, and security;
   7. data checks.
5. **`tools/deploy.py`** guards the host, creates the catalog, renders, and deploys. It records the bundle IDs in the
   manifest, runs the setup job, applies the ontology, and validates.
6. **`tools/ontology.py`** reconciles `ontology/domains.yml` and `ontology/pages/*.md` with the account. It reads
   dashboard and Genie IDs from the manifest, and `plan` is read-only.

## Making common changes

**Column or table:**
1. Edit `contract/dev_gold_mart.yml`, plus `contract/descriptions.yml` (a test requires every column to be
   described).
2. Run pytest.
3. Run a full deploy (tables are recreated).

**Business description:**
1. Edit `contract/descriptions.yml`.
2. Run `tools/render.py`.
3. Run `tools/run_sql.py ... build/sql/35_comments.sql`.

**Metric or measure:**
1. Edit `src/sql/50_metric_views.sql.tmpl`: one fact source per metric view, dimension joins on `is_current = true`,
   and a comment, display name, and synonyms on everything. Avoid `}}` in YAML; use block style for `format`.
2. Render, then `run_sql.py build/sql/50_metric_views.sql`.
3. Run `validate.py --sections semantics`.
4. Run `tools/ontology.py apply`, because recreating a view drops its tags.

**Page or domain:**
1. Add `ontology/pages/<subdomain>--<slug>.md` with frontmatter: `display_name`, `subdomain`, `synonyms`,
   `description` (at most 280 characters), `assumption`, `mentions`, and `requires`.
   - In the body, write object names as `` `{{catalog}}.{{mart}}.<table>` ``.
   - Every mention must appear in the body.
   - Set `assumption: true` to add the "confirm with ESA" banner.
2. Run pytest.
3. Run `tools/ontology.py plan`, then `apply`.

**Genie agent:**
1. Edit `genie/<key>.yml`. Example and benchmark SQL must return raw values, with no `ROUND` and no `* 100`, because
   Genie's evaluation compares result sets. Keep formatting rules in the instructions.
2. Render, then run `validate.py --sections genie`, which executes every query.
3. Run `deploy.sh --skip-data`.
4. Optionally run a benchmark evaluation with `databricks genie genie-create-eval-run <space_id>`.

**Dashboard:**
1. Edit `tools/lib/dashboards.py`. Every dataset reads the metric views, filters need their field in every dataset
   they apply to, and the widget versions are counter/table 2 and bar/line 3.
2. Run pytest (structure checks).
3. Run `validate.py --sections dashboards`, which runs every dataset.
4. Run `deploy.sh --skip-data`.

**Row security:**
1. Edit `src/sql/60_security.sql.tmpl` or `security/personas.yml`.
2. Render, then run `run_sql.py build/sql/60_security.sql`.
3. Run `validate.py --sections security`, which always restores corporate.

## Validation sections

The data, schema, semantics, dashboards, genie, ontology, and security sections are deterministic and must pass.

`genie_one` replays the hero prompts in `genie/one/hero_prompts.yml`:
- an answer that cites anything outside the ESA Pages or `dev_gold` fails;
- a missing fact or citation is reported as `review`, which still passes but needs a human read.

Evidence goes to `.state/validation.json`.

## Live API facts this code depends on

- The Pages API (`/api/2.0/knowledge/pages`) stores synonyms sorted, has no domain filter on list, and links as
  `/one/discover/pages/<id>`.
- A subdomain's governed tag key is `<parent key>/<name>`. Tables are tagged key-only. Workspace tag assignments for
  Genie spaces and dashboards accept the `/` in that key.
- Statement API DDL results have no schema. `COMMENT ON TABLE` and `COMMENT ON COLUMN` work on tables, views, and
  materialized views.
- `INSERT OVERWRITE` and `REFRESH MATERIALIZED VIEW` keep row filters. `CREATE OR REPLACE VIEW` drops tags, and
  `CREATE OR REPLACE TABLE` keeps them.
- `databricks genie ask -o json` returns `status` in lowercase and each tool call's `arguments` as a JSON string.
- The bundle refuses to deploy a dashboard that was edited in the UI unless you pass `--force`.

## Repository map

```
databricks.yml, resources/   bundle: targets, warehouse, jobs, dashboards, Genie spaces
contract/                    table contract and business descriptions
src/esa_resstay_demo/        synthetic data generator (wheel)
src/sql/                     SQL templates (schemas, views, checks, metric views, security)
genie/                       Genie agent specs; genie/one/ holds the Genie One hero prompts
ontology/                    domains.yml and pages/*.md
security/personas.yml        demo personas
tools/                       deploy, render, validate, ontology, set_persona, run_sql, demo_links, cleanup
tools/lib/                   contract, SQL generation, comments, dashboards, genie, ontology, personas, live checks
tests/                       pytest suite (no workspace access)
docs/                        runbook.md (operations), demo-script.md (talk track)
```
