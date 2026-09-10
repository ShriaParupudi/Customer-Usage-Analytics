# Architecture

## Diagrams

- Pipeline flow: [`architecture.mermaid`](architecture.mermaid)
- Entity relationships: [`erd.mermaid`](erd.mermaid)

Both render natively on GitHub inside a ```` ```mermaid ```` fence — see the README.

---

## The layered design (and why it exists)

The pipeline is organised into layers, each with **one job**. This is the
"medallion" / staging-marts pattern used by dbt, Databricks and essentially every
modern analytics stack. The value is not the folder names — it is that each layer
has a rule about what is and is not allowed to happen inside it.

```
generate → raw → [DQ gate] → staging → marts → analytics → reporting
```

| Layer | Job | **Allowed** | **Not allowed** |
|---|---|---|---|
| **raw** | Preserve the source exactly as received | Loading, adding `record_loaded_at` | Any cleaning, casting, filtering, deduping |
| **staging** | Make it trustworthy | Typing, dedupe, trim/case standardisation, value-domain mapping, excluding test accounts, renaming to conventions | Joins across entities, aggregation, business logic |
| **marts** | Model the business | Joins, conformed dimensions, the month spine, aggregation to a stated grain | Opinionated thresholds ("risk", "at-risk") |
| **analytics** | Apply business rules | Segments, thresholds, risk scoring, KPIs | Re-cleaning data |
| **reporting** | Present | Exports, dashboards | Any transformation logic |

### Why keep a raw layer you never query?

Because when a number looks wrong, the first question is always *"is the data
wrong, or is our code wrong?"* An untouched raw layer lets you answer that in
thirty seconds. It also means a bug fix is a re-run of staging, not a re-request
of the source data. Teams that clean on ingest lose the ability to audit
themselves.

### Why a separate staging layer instead of cleaning inside the marts?

Because cleaning logic gets duplicated otherwise. If `country` standardisation
lives in three different mart queries, they will drift, and one dashboard will
show 42 accounts in the US while another shows 47. One cleaning rule, one place,
every downstream consumer inherits it.

### Why is "risk" in analytics and not in marts?

Marts should be **factual**; analytics should be **opinionated**. "This account
had 412 events in March" is a fact and will never change. "This account is
high-risk" is a judgement based on a threshold your VP will want to change from
40% to 30% next quarter. Keeping judgement in its own layer means changing the
threshold touches one file, not your whole warehouse.

---

## The data-quality gate

Checks run **between raw and staging**, and each check has a severity:

- **FAIL** — the pipeline stops with a non-zero exit code (e.g. duplicate primary
  keys, orphan foreign keys above tolerance, negative quantities).
- **WARN** — logged to the report, pipeline continues (e.g. null rate on
  `industry` above 5%).

Every run writes `outputs/dq_report.md` with per-check row counts and examples.

> **Why a gate rather than "clean it and move on":** silently fixing bad data
> hides a broken upstream system. Failing loudly is what makes an analyst
> trustworthy. The nuance a hiring manager wants to hear is that you distinguish
> *tolerable* from *fatal* — not everything should stop the build.

---

## Technology choices, and the honest reason for each

| Choice | Why | What I would use at real scale |
|---|---|---|
| **DuckDB** | A real SQL engine in a single file, no server. Reads Parquet/CSV directly, columnar and fast on millions of rows, and the SQL is close enough to Snowflake/BigQuery that the code transfers. | Snowflake / BigQuery / Databricks |
| **Python + Pandas** | Data generation, orchestration, quality checks, exports. | Same, plus Airflow/Dagster |
| **SQL for all transformations** | Transformation logic lives in `.sql` files, version-controlled and reviewable. This is the analytics-engineering habit — Python calls the SQL, it does not replace it. | dbt |
| **Parquet for events** | Columnar, compressed, typed. A 3M-row CSV is ~400 MB; the Parquet is ~40 MB and loads far faster. Also a chance to explain columnar storage in an interview. | Same |
| **CSV for small tables** | Human-readable and diffable in git for ~500-row tables. | Same |
| **Plain Python orchestration** | Airflow for a 6-step local pipeline is résumé-driven development. `make all` is honest. | Airflow / Dagster / Prefect |

### Why not dbt?

dbt is the industry-standard tool for exactly this layering, and adding it later
is a natural v2. Building the pattern by hand first means you understand *what dbt
is doing for you* — refs, tests, DAG ordering — rather than only how to type
`dbt run`. That is a defensible answer, and `docs/limitations.md` records it as a
known next step rather than pretending hand-rolled SQL is superior.

---

## Execution flow

```
make all
 ├─ 1. python -m src.generate_data     → data/raw/*.csv, *.parquet
 ├─ 2. python -m src.ingest            → warehouse.duckdb  [raw schema]
 ├─ 3. python -m src.quality_checks    → outputs/dq_report.md  (exit 1 on FAIL)
 ├─ 4. python -m src.build_staging     → [staging schema]   (runs sql/staging/*.sql)
 ├─ 5. python -m src.build_marts       → [marts schema]     (runs sql/marts/*.sql)
 ├─ 6. python -m src.build_analytics   → [analytics schema] (runs sql/analytics/*.sql)
 └─ 7. python -m src.export_bi         → outputs/*.csv
```

Idempotent by design: every step is `CREATE OR REPLACE`, so re-running from
scratch produces an identical warehouse. If a step is not idempotent, you cannot
safely re-run it after a fix — and you will need to, constantly.

Ordering within a layer is controlled by filename prefixes
(`01_stg_accounts.sql`, `02_...`), which is a crude but transparent DAG.

---

## Repository structure

```
customer-usage-analytics/
├── README.md                  # front door: problem, architecture, how to run, findings
├── Makefile                   # make all / make data / make dq / make marts
├── requirements.txt
├── .gitignore                 # data/ and warehouse are NOT committed
├── config/
│   └── config.yml             # thresholds, row counts, seeds — no magic numbers in code
├── data/
│   ├── raw/                   # generated, gitignored
│   ├── interim/               # scratch, gitignored
│   └── warehouse/             # warehouse.duckdb, gitignored
├── src/
│   ├── generate_data.py       # Phase 1
│   ├── ingest.py              # Phase 2
│   ├── quality_checks.py      # Phase 3
│   ├── build_staging.py       # Phase 4
│   ├── build_marts.py         # Phase 4
│   ├── build_analytics.py     # Phases 5-7
│   ├── export_bi.py           # Phase 8
│   └── utils/
│       ├── db.py              # connection + SQL file runner
│       └── logging_config.py
├── sql/
│   ├── staging/               # 01_stg_accounts.sql ...
│   ├── marts/                 # dims, spine, facts
│   ├── analytics/             # metrics, segments, risk, health table
│   └── quality/               # each DQ check as its own .sql
├── tests/                     # pytest: metric logic on tiny fixtures
├── notebooks/                 # exploration only — never the pipeline
├── outputs/                   # dq_report.md, BI exports, charts
├── dashboards/                # screenshots + dashboard notes
└── docs/
    ├── business_problem.md
    ├── architecture.md
    ├── architecture.mermaid
    ├── erd.mermaid
    ├── data_dictionary.md
    ├── assumptions.md
    └── limitations.md
```

### Two structural rules worth defending in an interview

1. **Data is never committed to git.** `data/` and `*.duckdb` are gitignored.
   The *generator* is committed, so anyone can reproduce the dataset exactly from
   a seed. Committing a 400 MB parquet file is the most common beginner mistake
   in a portfolio repo, and reviewers notice.
2. **Notebooks are not the pipeline.** Notebooks explore; `src/` and `sql/`
   produce. Hidden execution order in a notebook is unreproducible, and "it works
   if you run the cells in the right order" is not a pipeline.
