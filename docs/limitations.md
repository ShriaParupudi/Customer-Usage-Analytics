# Limitations

Written up front so the project stays honest, and so that "what would you do
differently?" has a real answer in an interview.

## Data limitations

- **Synthetic data.** Patterns are authored, not observed. Findings demonstrate
  that the pipeline works; they are not insights about any real market.
- **No ground-truth churn labels** independent of the generator, so no model
  accuracy, precision or recall can be honestly reported.
- **No marketing, sales, product-release or pricing data**, all of which would
  materially explain usage changes in reality.
- **No account-hierarchy modelling** (parent/child orgs, resellers), which is a
  major real-world complication in enterprise SaaS.
- **24 months only** — enough for MoM and short cohort views, not enough to
  separate seasonality from trend with confidence.

## Methodological limitations

- **Rule-based risk, not predictive.** Thresholds are informed judgement, not
  optimised against outcomes. No claim is made that they maximise anything.
- **Event count is a crude usage proxy.** Ten clicks is not ten times the value
  of one. Value-weighted usage (weighting by feature importance) is a real
  improvement not attempted here.
- **Correlation only.** Nothing in this project establishes that low usage
  *causes* churn.
- **Survivorship bias in cohort views** — churned accounts stop generating
  events, so late-tenure cohorts skew healthy.
- **No statistical significance testing** on segment differences.

## Engineering limitations

- **Single-machine batch.** No distributed compute, no incremental loads; each
  run is a full rebuild. Fine at this scale, wrong at 100× the data.
- **No orchestrator.** No retries, no scheduling, no alerting, no lineage
  tracking. `make` is the DAG.
- **Filename-prefix ordering** instead of true dependency resolution. dbt's
  `ref()` would be the correct fix and is the most valuable v2 upgrade.
- **No slowly-changing-dimension history on `dim_account`.** Current attributes
  only; a plan tier change rewrites history. Subscriptions carry term dates, so
  point-in-time plan is still answerable — but industry/country changes are not.
- **Tests cover metric logic and warehouse invariants**, not every SQL file.
  The unit tests assert the logic *patterns* against hand-built fixtures rather
  than executing the production `.sql` files directly; the integration tests
  assert properties of the built tables. A change to a SQL file that preserves
  every asserted invariant could still be wrong.

## Decisions made during the build, and why

- **Risk weights were retuned once, deliberately and on the record.** The first
  weighting put every dormant account in the High band and left actively
  declining accounts in Medium. Rather than tune the score until the output
  looked the way I wanted — which is how you talk yourself into a wrong model —
  chronic dormancy was separated from a single quiet month, and the dashboard
  ships **two ranked lists** instead of one blended score, because a dormant
  account and a declining account need opposite responses. The reason is written
  into `config/config.yml` beside the weights.
- **The reporting window is config, not inferred from the data.** An early build
  derived the month spine from `min(event_ts)` and a handful of deliberately
  mis-dated rows stretched every trend chart back to 2022.
- **Risk and revenue are kept as separate axes.** The score says how worried to
  be; ARR says how much it costs. Multiplying them into one "priority" number
  would hide which of the two is driving the ranking.

## Known future work

| Idea | Why it would add value |
|---|---|
| Port transformations to dbt | Real lineage, built-in tests, docs site |
| Incremental event loading | Removes the full-rebuild cost |
| Value-weighted usage score | Better proxy for realised customer value |
| Cohort retention curves | Ties usage health to actual retention |
| Alerting on new high-risk accounts | Turns a dashboard into a workflow |
| Great Expectations / dbt tests | More expressive DQ than hand-rolled SQL |
