# Business Problem

## 1. The company (fictional, for context)

**Northwind Workspace** is a fictional B2B SaaS company selling a collaborative
workspace product (documents, dashboards, integrations, automations) to other
businesses. Customers buy an **account-level subscription** with a fixed number
of licensed seats. Roughly 500 customer accounts, subscriptions renew annually
or monthly.

This is a *fictional* company and *synthetic* data. Nothing in this repository
comes from a real employer or a real customer.

## 2. Who has the problem

| Stakeholder | What keeps them up at night |
|---|---|
| VP Customer Success | "Which of my accounts are quietly dying before renewal?" |
| Head of Product | "Are customers actually adopting the features we shipped?" |
| Revenue / Finance | "How much ARR is sitting in accounts that stopped using us?" |
| CSM (front line) | "I own 60 accounts. Which 5 do I call this week?" |

## 3. The core problem statement

> Northwind can see **who is paying** (billing data) and **who logged in**
> (product data), but nobody has joined those two worlds together. As a result,
> churn is discovered at renewal — 30 days too late to fix it.

In renewals-driven B2B SaaS, usage decline precedes churn by months. The signal
exists in the product event stream long before it shows up in the revenue
numbers. The business is not missing data; it is missing a **model** that turns
raw events into an account-level view of health.

## 4. The decision this pipeline supports

The pipeline exists to produce one artifact: a **monthly customer health table**,
one row per account per month, that a CSM or exec can act on.

Concretely it should let someone answer, without writing any code:

1. How many accounts and users were active last month, and is that trending up or down?
2. Which paying accounts had **zero usage** last month?
3. Which accounts dropped more than X% month-over-month?
4. Which accounts are trending down over a sustained window (not just one noisy month)?
5. Which segment does each account belong to, and how do segments differ?
6. Which features are adopted, by whom, and which shipped features nobody touched?
7. What share of ARR sits in at-risk accounts?

## 5. Success criteria for the *project* (not invented business results)

This is a portfolio project, so "success" means the artifact is defensible, not
that it saved a company money. The pipeline succeeds if:

- [ ] It runs end-to-end from a single command on a clean machine.
- [ ] Every metric has a written definition, and the SQL matches that definition.
- [ ] Data quality checks run automatically and **fail loudly** on bad input.
- [ ] Row counts and totals reconcile between layers (no silent row loss).
- [ ] Every table has a stated **grain** (what one row means).
- [ ] Assumptions and limitations are written down honestly.
- [ ] A dashboard reads from the final table with no extra transformation.

## 6. Explicit non-goals

Stating what you deliberately did *not* do is a senior-analyst habit, and it is
an easy interview win.

- **No ML churn model.** Rule-based, explainable risk flags first. A logistic
  regression on synthetic data whose labels I generated myself would be circular
  and meaningless.
- **No real-time streaming.** Monthly batch matches the decision cadence
  (renewals, QBRs). Real-time would be engineering theater.
- **No cloud warehouse.** DuckDB runs the same SQL locally for free. Cloud gets
  added only if the data outgrows a laptop, which 500 accounts will not.
- **No revenue forecasting.** Out of scope; usage health only.

## 7. Key metric definitions (locked in Phase 0, on purpose)

Defining metrics *before* writing SQL is the single most important habit in this
project. Undefined metrics are how two dashboards end up disagreeing.

| Term | Definition used in this project |
|---|---|
| **Qualifying event** | A usage event whose `event_name` is flagged `is_core_action = true` in the feature catalog. Passive events (e.g. `session_start`) are excluded so that merely logging in does not count as "using the product". |
| **Active user (month)** | A user with ≥ 1 qualifying event in the calendar month. |
| **Active account (month)** | An account with ≥ 1 qualifying event from ≥ 1 user in the calendar month. |
| **MAU / MAA** | Count of distinct active users / accounts in a calendar month. |
| **Usage volume** | Count of qualifying events. Not sessions, not minutes. |
| **Seat utilisation** | distinct active users in month ÷ `seats_licensed`. |
| **Zero-usage account** | Account with an active subscription for the whole month and 0 qualifying events. |
| **Eligible account-month** | An account-month where the subscription was active for ≥ 15 days. This is the denominator for all rates — it prevents pre-signup and post-churn months from polluting the metrics. |
| **MoM change** | (this month − prior month) ÷ prior month, evaluated only when the prior month had ≥ 20 events (a **volume floor** to stop 2 → 1 events reading as "-50%, critical"). |
| **Declining account** | MoM change ≤ −40% for the current month, above the volume floor. |
| **Sustained decline** | 3-month rolling average below the prior 3-month rolling average by ≥ 25%. |
| **Feature adoption** | An account has "adopted" a feature area if ≥ 1 qualifying event in that area in the month. Depth = share of that account's active users who used it. |
| **Engagement frequency** | Distinct active days per account per month (0–31). Frequency separates "one big batch import" from "used daily". |

> **Why the volume floor and the eligibility window matter:** these are the two
> things a hiring manager will probe. Without them, your "at-risk" list fills
> with brand-new accounts and tiny accounts, the CSM team ignores the report,
> and the project is dead. Being able to explain *that* is worth more than the
> SQL itself.

## 8. Timeframe

24 months of synthetic history, ~500 accounts. Long enough for cohort and
sustained-trend analysis; small enough to regenerate in seconds while learning.
