# Runbook

Every command passes `--profile` explicitly; ambient `DATABRICKS_*` variables are ignored. `.state/manifest.json`
records everything the repo created; keep it with the checkout.

## Deploy or refresh

```bash
./deploy.sh --profile esa-resstay-demo --target demo            # full: data, semantics, security, ontology, checks
./deploy.sh --profile esa-resstay-demo --target demo --skip-data  # everything except regenerating the data
./deploy.sh --profile esa-resstay-demo --target demo --skip-data --nightly on   # also schedule the 06:00 refresh
```

The full deploy takes about 45 minutes:

1. Host guard and login check.
2. Catalog `dev_gold`, bound to this workspace only.
3. Render `build/`: SQL, data checks, Genie spaces, dashboards.
4. Bundle deploy: warehouse, jobs, Genie agents, dashboards.
5. Setup job:
   - tables, then synthetic data, then loads;
   - then views and the materialized view;
   - then comments, metric views, and row security;
   - then data checks.
6. Discover ontology: governed tags, domains, asset tags, Pages.
7. Validation (about 15 minutes); see below.

**`--as-of`:** defaults to yesterday in America/New_York. It must be no earlier than the recorded story anchor and no
later than 30 days after it, because the planted renovation ends then.

**First deploy into an empty workspace:** run the deploy twice. The first run creates the Genie agents. The second run
links each dashboard's "Ask Genie" button to its agent.

## New workspace (the current sandbox expires 2026-12-01)

1. Create a new Databricks workspace on AWS whose account lets you create governed tags and domains.
2. Log in: `databricks auth login --host <url> --profile <name>`.
3. Update `targets.demo.workspace` (host and `workspace_id`) in `databricks.yml`.
4. Move the old `.state/` aside.
5. Run `./deploy.sh`.

The Discover objects (governed tags, domains, Pages) live in the old account. Remove them there first (see Cleanup),
or the new run will find the ESA names taken and stop.

## Personas (row-level security)

```bash
./.venv/bin/python tools/set_persona.py --profile esa-resstay-demo --persona dm   # corporate | dvp | rvp | dm | none
```

Only the operator's own row in `dev_gold.security.property_entitlements` changes. The DM, RVP/RDO, and DVP scopes
resolve to the renovation district and its region and division. Each run prints visible against expected hotels.

**Always reset to `corporate` after a demo.** The nightly data checks run as the operator. A deploy also resets the
operator to corporate.

## Validation

Run `./.venv/bin/python tools/validate.py --profile esa-resstay-demo [--sections a,b]`. It writes
`.state/validation.json` with statement IDs and Genie conversation IDs.

| Section | Checks |
|---|---|
| schema | Live columns, order, and types match `contract/dev_gold_mart.yml` |
| data | Generated key and rule checks plus the planted stories |
| semantics | Every contract column has a comment; metric views equal direct SQL to the cent |
| dashboards | Every dataset runs with default parameters and returns every column its widgets use |
| genie | Every example and benchmark SQL in both agents executes and returns rows |
| ontology | Strict verify: nothing to create or update, and nothing pending |
| security | Each persona sees exactly its scope's hotels; corporate is always restored |
| genie_one | The three hero prompts: only ESA Pages and `dev_gold` cited (else fail); missing facts or citations are `review` |

## Ontology alone

```bash
./.venv/bin/python tools/ontology.py plan   --profile esa-resstay-demo   # read-only
./.venv/bin/python tools/ontology.py apply  --profile esa-resstay-demo
./.venv/bin/python tools/ontology.py verify --profile esa-resstay-demo --strict
```

Edit `ontology/domains.yml` or `ontology/pages/*.md`, then apply. The tool changes only objects recorded in the
manifest. It stops if an ESA-named object it did not create already exists.

## UI-only steps (optional)

- A custom "Start here" section on the ESA domain pages: Discover → ESA domain → edit.
- Never edit the account-level Discover page or Manage Domains: they are shared with other teams.

## Cleanup

```bash
./.venv/bin/python tools/cleanup.py --profile esa-resstay-demo                  # dry run: prints the plan
./.venv/bin/python tools/cleanup.py --profile esa-resstay-demo --confirm        # delete
./.venv/bin/python tools/cleanup.py --profile esa-resstay-demo --confirm --keep-catalog
```

Deletion order:
1. Pages.
2. Subdomains, then domains.
3. Governed tags.
4. `bundle destroy`: jobs, warehouse, dashboards, and Genie agents.
5. `dev_gold` with cascade.

Each live object must still match its manifest record, or cleanup stops. The catalog must match its recorded storage
location and creation time. The tool never touches anything the manifest does not record.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `cannot authenticate` | `databricks auth login --host <url> --profile esa-resstay-demo` |
| Bundle says the workspace ID does not match | The profile's `workspace_id` in `~/.databrickscfg` is wrong; `databricks.yml` pins the right one |
| A persona sees the wrong count | Run `set_persona.py --persona corporate`; check `security.property_scope_lookup` has 600 rows |
| Ontology stops with "did not create" | Someone else owns an ESA-named object; rename ours in `ontology/domains.yml` or remove theirs |
| Dashboard shows "Ask Genie" disabled | Redeploy once more so the render picks up the Genie space IDs |
