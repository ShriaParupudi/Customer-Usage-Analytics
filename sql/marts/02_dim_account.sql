-- One row per account, with its CURRENT attributes plus its latest commercial
-- position. Note the limitation recorded in docs/limitations.md: this is a
-- Type-1 dimension, so an industry change overwrites history. Point-in-time
-- PLAN is still answerable, because subscription terms carry their own dates.
CREATE OR REPLACE TABLE marts.dim_account AS
WITH latest_sub AS (
    -- arg_max(x, y) returns the x from the row with the largest y. It is the
    -- concise way to say "the plan from the most recent term" without a
    -- self-join or a ROW_NUMBER() subquery.
    SELECT
        account_id,
        arg_max(plan_tier,      term_start_date) AS current_plan_tier,
        arg_max(seats_licensed, term_start_date) AS current_seats_licensed,
        arg_max(mrr_usd,        term_start_date) AS current_mrr_usd,
        arg_max(status,         term_start_date) AS current_status,
        max(term_end_date)                       AS current_term_end_date,
        min(term_start_date)                     AS first_term_start_date,
        count(*)                                 AS total_terms,
        bool_or(is_churn_term)                   AS has_ever_churned
    FROM staging.stg_subscriptions
    GROUP BY account_id
),
user_counts AS (
    SELECT account_id,
           count(*)                        AS total_users_ever,
           count(*) FILTER (WHERE is_active_seat) AS active_seats
    FROM staging.stg_users
    GROUP BY account_id
)
SELECT
    a.account_id,
    a.account_name,
    a.industry,
    a.country,
    a.employee_band,
    a.signup_date,
    a.signup_month,
    a.acquisition_channel,
    a.csm_owner,
    a.is_managed_account,
    s.current_plan_tier,
    s.current_seats_licensed,
    s.current_mrr_usd,
    round(s.current_mrr_usd * 12, 2) AS current_arr_usd,
    s.current_status,
    s.current_term_end_date,
    s.total_terms,
    s.has_ever_churned,
    coalesce(u.total_users_ever, 0)  AS total_users_ever,
    coalesce(u.active_seats, 0)      AS active_seats,
    date_diff('month', a.signup_date, current_date) AS tenure_months
FROM staging.stg_accounts a
LEFT JOIN latest_sub  s ON a.account_id = s.account_id
LEFT JOIN user_counts u ON a.account_id = u.account_id;
