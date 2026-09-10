# Assumptions

Every analytics project rests on judgement calls. Writing them down is what
separates an analyst from someone who ran a query. If a stakeholder disagrees
with a number, the disagreement is almost always with one of these lines — not
with the SQL.

Status: all assumptions below are **design-time [SPEC]** until the code exists.

## Data assumptions

1. **The event stream is complete.** No client-side dropped events, no
   collection outages. Real telemetry has both; this dataset does not simulate
   them. A missing-data outage would look identical to a usage cliff, which is a
   genuine hazard in production risk scoring.
2. **`account_id` on an event is authoritative** where it disagrees with the
   user's account. Cross-field mismatches are flagged as a quality issue rather
   than silently repaired.
3. **Timestamps are UTC.** No timezone localisation, so "active days" for an
   APAC account may be off by one at the boundary. Immaterial at monthly grain.
4. **Users belong to exactly one account.** No multi-tenant users, no consultants
   working across customers.
5. **The feature catalog is the source of truth** for `feature_area` and
   `is_core_action`, overriding the denormalised value on the event row.

## Business-rule assumptions

6. **Activity = a core action, not a login.** Passive events are excluded from
   all active/usage metrics. This makes MAU lower than a login-based definition
   would — deliberately. Anyone comparing to a login-based number will see a gap;
   the definition, not the number, is the thing to align on.
7. **Monthly grain is the right cadence** because renewals and QBRs are monthly
   or quarterly. Weekly would add noise without adding decisions.
8. **A 15-day eligibility window** — an account-month counts only if the
   subscription was active for ≥ 15 days. Partial first and last months would
   otherwise register as fake declines.
9. **A 20-event volume floor** on MoM change. Below that, percentage change is
   statistically meaningless and generates false alarms that destroy trust in
   the report.
10. **−40% MoM = "declining", −25% on 3-month rolling average = "sustained
    decline".** Thresholds are configuration (`config/config.yml`), not
    hard-coded, precisely because a stakeholder will want to tune them.
11. **Seasonality is not automatically corrected for.** Education and retail
    accounts have genuine expected dips. The health table exposes industry so a
    human can apply that context; the pipeline does not attempt automatic
    deseasonalisation, because with 24 months of history you cannot separate a
    seasonal dip from a real decline with any confidence.
12. **Internal test accounts are excluded** from every metric at the staging
    layer, so no downstream query can forget to filter them.
13. **Risk score is a weighted rule-based sum, not a churn probability.** It is
    intentionally explainable: a CSM must be able to see *why* an account
    surfaced. A score of 70 does not mean "70% likely to churn".

## Synthetic-data assumptions

14. **Churn behaviour was authored by me**, so any model trained to predict it
    would just be recovering my own generator rules. This is why the project
    uses rule-based risk flags and explicitly does not claim predictive
    performance.
15. **Volumes are plausible but not benchmarked** against real SaaS data. Ratios
    (seats to active users, ticket rates) were chosen to be realistic, not
    validated against an industry source.
16. **A fixed random seed** makes the dataset reproducible. Anyone cloning the
    repo and running the generator gets identical numbers, so the findings in the
    README are verifiable.
