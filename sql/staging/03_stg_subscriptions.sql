CREATE OR REPLACE TABLE staging.stg_subscriptions AS
SELECT
    s.subscription_id,
    s.account_id,
    lower(trim(s.plan_tier)) AS plan_tier,

    -- Impossible values become NULL rather than 0. NULL propagates through
    -- arithmetic and shows up as "unknown"; a 0 would silently produce a
    -- divide-by-zero or an infinite utilisation rate.
    CASE WHEN s.seats_licensed > 0 THEN s.seats_licensed END AS seats_licensed,
    CASE WHEN s.mrr_usd >= 0 THEN s.mrr_usd END              AS mrr_usd,

    s.billing_frequency,
    s.term_start_date,
    s.term_end_date,
    lower(trim(s.status))    AS status,
    s.cancel_reason,
    s.status = 'churned'     AS is_churn_term,
    date_diff('day', s.term_start_date, s.term_end_date) AS term_days,
    s.record_loaded_at
FROM raw.subscriptions s
JOIN staging.stg_accounts a ON s.account_id = a.account_id
-- Terms that end before they start describe no interval at all, so they cannot
-- participate in a point-in-time join. Dropped.
WHERE s.term_end_date > s.term_start_date;
