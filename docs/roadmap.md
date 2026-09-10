# Project Roadmap & Status

**This file is the single source of truth for what is real.**
Update the status column as you finish each phase — and do not update it early.
Everything in the README's "Findings" section must trace back to a phase marked
✅ here.

Legend: ✅ Done · 🔨 In progress · ⬜ Planned

| Phase | Deliverable | Status |
|---|---|---|
| **0** | Business problem, dataset design, architecture, repo scaffold | ✅ |
| **1** | Synthetic data generator with behavioural patterns + injected defects | ✅ |
| **2** | Ingestion into DuckDB `raw` schema | ✅ |
| **3** | Data quality framework (16 checks, severities, baselines, DQ report) | ✅ |
| **4** | Staging + dimensional model (spine, dims, facts) | ✅ |
| **5** | Core SQL metrics (MAA, MAU, usage, MoM, zero-usage, decliners) | ✅ |
| **6** | Feature adoption + engagement frequency analysis | ✅ |
| **7** | Segmentation + rule-based retention-risk scoring + health table | ✅ |
| **8** | Reporting layer: BI exports + dashboard | ✅ |
| **9** | Testing, documentation polish, README findings | ✅ |
| **10** | Git history cleanup, publish, and *then* resume bullets | 🔨 |

---

## Phase detail

### Phase 0 — Foundation ✅
Define the business problem and stakeholders, lock metric definitions before
writing SQL, design six raw datasets with stated grain and keys, specify fifteen
data-quality defects to inject, design the layered architecture, scaffold the
repo.
*Demonstrates:* scoping, data modelling, metric governance, project structure.

### Phase 1 — Synthetic data generation ✅
Simulate 24 months of behaviour for ~500 accounts: weekly seasonality,
onboarding ramps, healthy/declining/seasonal/zero-usage/power archetypes, then
inject the fifteen defect classes. Seeded and reproducible.
*Demonstrates:* Python, NumPy/Pandas, simulation design, reproducibility.

### Phase 2 — Ingestion ✅
Load files into DuckDB `raw` with no transformation, adding lineage columns.
Reconcile row counts file-vs-table.
*Demonstrates:* ETL basics, Parquet vs CSV, idempotent loads, DuckDB.

### Phase 3 — Data quality ✅
16 checks, one SQL file each, a runner that collects results, severity handling
(FAIL / WARN), documented baselines so the gate detects *regression* rather than
failing every run, and a generated `dq_report.md`.
*Demonstrates:* the skill that most distinguishes analysts — validating before
analysing.

### Phase 4 — Modelling ✅
Staging models, then `dim_month` spine, conformed dims, and `fct_account_month`
built by LEFT JOINing usage onto the account × month grid so zero-usage months
exist as rows.
*Demonstrates:* dimensional modelling, grain discipline, spine/gap-filling,
window functions.

### Phase 5 — Core metrics ✅
MAA/MAU, usage by account, MoM change with a volume floor, zero-usage
identification, decline detection, sustained-decline via rolling averages.
*Demonstrates:* analytical SQL, `LAG`, rolling windows, metric edge cases.

### Phase 6 — Adoption & engagement ✅
Feature-area adoption breadth and depth, adoption since launch date, active-days
frequency, power-user concentration and key-person risk.
*Demonstrates:* product analytics thinking.

### Phase 7 — Segmentation & risk ✅
Business-rule segments (size × engagement × tenure), a transparent weighted risk
score, and the final `account_health_monthly` / `account_health_current` tables.
*Demonstrates:* translating business logic into code, explainable scoring.

### Phase 8 — Reporting ✅
Exports plus a dashboard: KPI trend, at-risk account list, segment breakdown,
feature adoption, MoM movers.
*Demonstrates:* BI, stakeholder communication, dashboard design.

### Phase 9 — Testing & docs ✅
pytest over metric logic with hand-built fixtures, README findings written from
actual query output, docs finalised.
*Demonstrates:* testing analytics code, technical writing.

### Phase 10 — Publish 🔨
Clean commit history, meaningful messages, tagged release. **Only then** write
resume bullets, and only for work that is ✅ above.
