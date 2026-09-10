# Data Dictionary

Status legend: **[SPEC]** = designed, not built yet · **[BUILT]** = generated.

All tables in this document are **[BUILT]**. Row counts are actuals from the
last pipeline run, not estimates.

---

## How to read this document

Every table starts with a **grain statement**: a one-sentence answer to *"what
does one row of this table mean?"* If you cannot write that sentence, you do not
understand the table yet, and every aggregate you build on it will eventually be
wrong (usually by double-counting after a join).

Naming conventions used throughout:

- `*_id` — identifier column
- `*_date` — calendar date, no time component
- `*_ts` — timestamp, UTC
- `is_*` / `has_*` — boolean
- `raw_*` schema — as-loaded, untouched · `stg_*` — cleaned · `dim_*` / `fct_*` — modelled

---

## 1. `accounts` (raw)

**Grain:** one row per customer account (company).
**Primary key:** `account_id`
**Actual rows:** 507 (504 real + 3 internal test)

| Column | Type | Description | Notes |
|---|---|---|---|
| `account_id` | string | `ACC-00001`. Business key. | PK |
| `account_name` | string | Company name | |
| `industry` | string | Retail, Healthcare, Financial Services, Technology, Manufacturing, Education, Non-profit | ~4% NULL by design |
| `country` | string | Billing country | Inconsistent codes by design (`US` / `USA` / `United States`) |
| `employee_band` | string | `1-50`, `51-200`, `201-1000`, `1000+` | Proxy for company size |
| `signup_date` | date | Date the account was created | Anchors all "no events before signup" checks |
| `acquisition_channel` | string | `inbound`, `outbound`, `partner`, `self_serve`, `referral` | For segment analysis |
| `csm_owner` | string | Assigned CSM name | NULL for self-serve accounts — a *legitimate* NULL, not a defect |
| `is_internal_test` | boolean | Internal/demo account | Must be excluded from all metrics |
| `record_loaded_at` | timestamp | Ingestion timestamp | Added at load |

---

## 2. `users` (raw)

**Grain:** one row per user (seat) provisioned inside an account.
**Primary key:** `user_id` · **Foreign key:** `account_id → accounts.account_id`
**Actual rows:** 19,120 (avg ~38 users/account, heavily skewed by plan tier)

| Column | Type | Description | Notes |
|---|---|---|---|
| `user_id` | string | `USR-000001` | PK |
| `account_id` | string | Owning account | FK; a few orphans injected on purpose |
| `user_created_date` | date | When the seat was provisioned | Should be ≥ account `signup_date` |
| `deactivated_date` | date | When the seat was removed | NULL = still active |
| `role` | string | `admin`, `editor`, `viewer` | Drives expected usage intensity |
| `department` | string | Engineering, Marketing, Sales, Ops, Finance, Other | ~8% NULL |
| `email_domain` | string | Domain part of the work email | Used to sanity-check account mapping |
| `invited_by_user_id` | string | Self-referencing FK | NULL for the first admin |

---

## 3. `subscriptions` (raw)

**Grain:** one row per **subscription term** per account. An account that renews
twice has three rows. **This is the table most people model wrong** — they assume
one row per account, then double-count revenue after joining.
**Primary key:** `subscription_id` · **Foreign key:** `account_id`
**Actual rows:** 1,490 (~3 terms per account)

| Column | Type | Description | Notes |
|---|---|---|---|
| `subscription_id` | string | `SUB-00001` | PK |
| `account_id` | string | FK to accounts | |
| `plan_tier` | string | `starter`, `growth`, `business`, `enterprise` | Can change between terms (upgrade/downgrade) |
| `seats_licensed` | integer | Seats purchased for this term | Denominator for seat utilisation; a few 0/negative injected |
| `mrr_usd` | decimal | Monthly recurring revenue for this term | Annual contracts stored as monthly-equivalent |
| `billing_frequency` | string | `monthly`, `annual` | |
| `term_start_date` | date | Term start (inclusive) | |
| `term_end_date` | date | Term end (exclusive) | A few < start injected on purpose |
| `status` | string | `active`, `renewed`, `churned`, `downgraded` | Status of *this term*, not the account |
| `cancel_reason` | string | Free-text-ish reason | NULL unless churned |

> **Concept — validity intervals.** Because subscriptions have start/end dates,
> "what plan was this account on in March 2025?" is a *point-in-time* question.
> You answer it by joining a month spine to subscriptions on
> `month_start < term_end_date AND month_end >= term_start_date` — an overlap
> join, not an equality join. This is the same pattern as a Type-2 slowly
> changing dimension, and it comes up constantly in real analytics work.

---

## 4. `product_usage_events` (raw)

**Grain:** one row per product event emitted by one user at one moment.
**Primary key:** `event_id` · **FKs:** `account_id`, `user_id`
**Actual rows:** 2,959,700 over 24 months

| Column | Type | Description | Notes |
|---|---|---|---|
| `event_id` | string | UUID | PK; ~0.4% exact duplicate rows injected |
| `account_id` | string | Denormalised for query speed | Must reconcile with `users.account_id` |
| `user_id` | string | Actor | Some orphans injected |
| `event_ts` | timestamp | UTC event time | A few pre-signup and future-dated rows injected |
| `event_name` | string | e.g. `doc_created`, `report_run` | Joins to `feature_catalog` |
| `feature_area` | string | `documents`, `reporting`, `collaboration`, `integrations`, `automation`, `admin` | Denormalised; deliberately disagrees with the catalog on a few rows |
| `surface` | string | `web`, `mobile`, `api` | |
| `session_id` | string | Groups events into a session | |
| `event_qty` | integer | Usually 1; >1 for batched API events | Negative values injected — an "impossible value" check |
| `duration_ms` | integer | Client-reported duration | Nullable; some absurd outliers |

### Realistic behavioural patterns baked into the generator

Random uniform data teaches you nothing, because every metric comes out flat.
The generator will deliberately produce:

- **Weekly seasonality** — weekday usage far above weekend.
- **Onboarding ramp** — new accounts start slow, peak around month 2–4.
- **Healthy accounts** — stable or growing with noise.
- **Slow decliners** — gradual multi-month decay ending in churn.
- **Cliff decliners** — a champion leaves; usage drops ~80% in one month.
- **Seasonal accounts** — education/retail accounts with real, *expected* dips.
  These exist to punish a naive "any decline = risk" rule.
- **Zero-usage accounts** — paying, never activated. The core finding.
- **Power accounts** — heavy, multi-feature, multi-department adoption.
- **Single-user accounts** — one champion doing all the work = key-person risk.

---

## 5. `support_tickets` (raw)

**Grain:** one row per support ticket.
**Primary key:** `ticket_id` · **FKs:** `account_id`, `user_id` (nullable)
**Actual rows:** 6,000

| Column | Type | Description |
|---|---|---|
| `ticket_id` | string | PK |
| `account_id` | string | FK |
| `user_id` | string | Requester; nullable |
| `created_ts` | timestamp | Ticket opened |
| `resolved_ts` | timestamp | Ticket resolved; NULL if open |
| `priority` | string | `low`, `medium`, `high`, `urgent` |
| `category` | string | `bug`, `how_to`, `billing`, `feature_request`, `outage` |
| `csat_score` | integer | 1–5; mostly NULL (low survey response rate, as in real life) |

Included so that risk scoring uses more than one signal — a real health score
blends usage, support and commercial data.

---

## 6. `feature_catalog` (seed / reference)

**Grain:** one row per `event_name`. A hand-maintained reference table (21 rows).
Its source of truth is the `FEATURE_CATALOG` constant in `src/generate_data.py`,
which IS committed — it is configuration, not data.

| Column | Type | Description |
|---|---|---|
| `event_name` | string | PK |
| `feature_area` | string | Canonical area — the source of truth when events disagree |
| `is_core_action` | boolean | Counts toward "qualifying event" / active definitions |
| `adoption_tier` | string | `basic`, `advanced`, `power` — supports a depth-of-adoption score |
| `launched_date` | date | Feature GA date — lets you measure adoption *since launch* |
| `description` | string | Plain-English meaning |

---

## 7. Deliberately injected data-quality defects

These are planted in Phase 1 so that the Phase 3 checks have something real to
catch. Every defect maps to a check.

| # | Defect | Where | Check it should trigger |
|---|---|---|---|
| 1 | Exact duplicate event rows (~0.4%) | events | Duplicate PK / full-row duplicate |
| 2 | Duplicate `account_id` rows | accounts | Uniqueness of PK |
| 3 | NULLs in `industry`, `department`, `csat_score` | accounts, users, tickets | Null-rate threshold (some are acceptable) |
| 4 | Events dated **before** the account's `signup_date` | events | Referential/temporal consistency |
| 5 | Events dated in the **future** | events | Max-date sanity check |
| 6 | `term_end_date` < `term_start_date` | subscriptions | Interval validity |
| 7 | Overlapping subscription terms for one account | subscriptions | No-overlap check (breaks point-in-time joins) |
| 8 | `user_id` in events not present in users | events | Orphan FK |
| 9 | `account_id` in users not present in accounts | users | Orphan FK |
| 10 | Event `account_id` ≠ that user's `account_id` | events | Cross-field consistency |
| 11 | Negative `event_qty`, `seats_licensed` ≤ 0, `mrr_usd` < 0 | events, subs | Impossible-value range check |
| 12 | Casing/whitespace variants (`" Retail "`, `RETAIL`) | accounts | Standardisation |
| 13 | Country stored as `US` / `USA` / `United States` | accounts | Value-domain mapping |
| 14 | Mixed date formats in one raw CSV column | subscriptions | Parse-failure check |
| 15 | Internal test account with absurd volume | accounts, events | Exclusion rule, outlier check |

> **Interview framing:** "I didn't write validation against clean data I made
> myself. I injected fifteen specific defect classes I have actually seen in
> production data, then wrote checks that catch each one, and the pipeline fails
> the build on the critical ones." That is a much stronger answer than "I used
> `df.dropna()`."

---

## 8. Modelled tables

All built. Row counts from the last run in brackets.

### Staging (`stg_`) — cleaned, typed, deduplicated; still 1:1 with source
`stg_accounts`, `stg_users`, `stg_subscriptions`, `stg_usage_events`, `stg_support_tickets`

### Marts
| Table | Grain |
|---|---|
| `dim_date` | one row per calendar date |
| `dim_month` | one row per calendar month (the **spine**) [24] |
| `dim_account` | one row per account, with current plan attributes [500] |
| `dim_user` | one row per user |
| `dim_feature` | one row per event_name |
| `fct_usage_events` | one row per cleaned in-window event [2,631,708] |
| `fct_account_month` | **one row per account per month** ← the workhorse [12,000 = 500 x 24] |
| `fct_user_month` | one row per user per month active [236,081] |
| `fct_feature_month` | one row per account per feature_area per month [72,000] |

### Analytics
| Table | Grain |
|---|---|
| `agg_monthly_kpis` | one row per month (company-level KPIs) [24] |
| `account_health_monthly` | one row per account per eligible month: usage, trend, segment, risk flags, risk score [10,300] |
| `account_health_current` | latest month per account — the table the dashboard connects to [496] |

> **Why `fct_account_month` must come from a month spine, not from the events.**
> If you build it with `GROUP BY account, month` over events, an account with
> zero usage in March produces **no row at all** — and your "zero-usage
> accounts" report silently returns nothing. You must generate the full
> account × month grid first (spine), then LEFT JOIN usage onto it, so absence
> becomes an explicit `0`. This one idea is the backbone of the whole project.
