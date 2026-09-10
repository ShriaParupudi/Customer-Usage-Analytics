-- =============================================================================
-- fct_account_month - THE WORKHORSE TABLE
--
-- GRAIN: exactly one row per account per month in the reporting window.
--
-- Built from the SPINE (dim_account CROSS JOIN dim_month), not from the events.
-- That is the whole trick: an account with zero usage still gets a row, with
-- zeros in it. Without this, "which paying accounts used nothing last month?"
-- returns an empty result and looks like good news.
--
-- Facts only. No thresholds, no judgement, no "risk" - those belong to the
-- analytics layer, because they are opinions that will change.
-- =============================================================================

CREATE OR REPLACE TABLE marts.fct_account_month AS

WITH spine AS (
    -- Every account x every month. 500 x 24 = 12,000 cells, whether or not
    -- anything happened in them.
    SELECT
        a.account_id,
        m.month_start,
        m.month_end,
        m.month_label,
        m.month_index,
        m.days_in_month,
        a.signup_date
    FROM marts.dim_account a
    CROSS JOIN marts.dim_month m
),

subscription_coverage AS (
    -- POINT-IN-TIME JOIN. A subscription term is a validity interval, so we
    -- cannot join on equality - we join on OVERLAP: the term starts before the
    -- month ends AND ends after the month starts.
    --
    -- days_subscribed then measures how much of the month the term actually
    -- covered, which is what makes partial first and last months detectable
    -- instead of looking like collapses in usage.
    SELECT
        sp.account_id,
        sp.month_start,
        least(
            sum(greatest(0, date_diff('day',
                greatest(s.term_start_date, sp.month_start),
                least(s.term_end_date - INTERVAL 1 DAY, sp.month_end)
            ) + 1)),
            sp.days_in_month              -- cap: overlapping terms must not
        )                                 -- report 45 days in a 31-day month
                                    AS days_subscribed,
        -- arg_max picks the attribute from the most recently started term, so
        -- an account that upgrades mid-month is reported on its new plan.
        arg_max(s.plan_tier,      s.term_start_date) AS plan_tier,
        arg_max(s.seats_licensed, s.term_start_date) AS seats_licensed,
        arg_max(s.mrr_usd,        s.term_start_date) AS mrr_usd,
        max(s.term_end_date)                         AS term_end_date,
        bool_or(s.is_churn_term)                     AS term_is_churning
    FROM spine sp
    JOIN staging.stg_subscriptions s
      ON s.account_id       = sp.account_id
     AND s.term_start_date <= sp.month_end
     AND s.term_end_date   >  sp.month_start
    GROUP BY sp.account_id, sp.month_start, sp.days_in_month
),

usage AS (
    -- Aggregate the events. FILTER (WHERE ...) applies a condition to ONE
    -- aggregate rather than the whole query, which is how we count core actions
    -- and total events in a single pass.
    SELECT
        account_id,
        event_month AS month_start,
        count(*)                                             AS total_events,
        count(*) FILTER (WHERE is_core_action)               AS core_events,
        sum(event_qty) FILTER (WHERE is_core_action)         AS core_event_qty,
        -- Active users must exclude events from unresolvable user_ids, or the
        -- distinct count is inflated by a phantom user.
        count(DISTINCT user_id) FILTER (WHERE is_core_action AND has_known_user)
                                                             AS active_users,
        -- ENGAGEMENT FREQUENCY: distinct days with activity. This is what
        -- separates "used it every day" from "one big import on the 3rd".
        count(DISTINCT event_date) FILTER (WHERE is_core_action) AS active_days,
        count(DISTINCT session_id)                           AS sessions,
        count(DISTINCT feature_area) FILTER (WHERE is_core_action)  AS feature_areas_used,
        count(DISTINCT event_name)  FILTER (WHERE is_core_action)   AS distinct_features_used,
        count(*) FILTER (WHERE is_core_action AND adoption_tier = 'power')
                                                             AS power_feature_events,
        count(*) FILTER (WHERE is_core_action AND adoption_tier = 'advanced')
                                                             AS advanced_feature_events,
        max(event_date)                                      AS last_event_date
    FROM marts.fct_usage_events
    GROUP BY account_id, event_month
),

concentration AS (
    -- KEY-PERSON RISK. If one user generates almost all of an account's usage,
    -- that account is one resignation away from going dark - even while its
    -- headline numbers look healthy.
    SELECT
        account_id,
        month_start,
        max(user_events) * 1.0 / nullif(sum(user_events), 0) AS top_user_event_share
    FROM (
        SELECT account_id, event_month AS month_start, user_id,
               count(*) AS user_events
        FROM marts.fct_usage_events
        WHERE is_core_action AND has_known_user
        GROUP BY 1, 2, 3
    )
    GROUP BY account_id, month_start
),

tickets AS (
    SELECT
        account_id,
        created_month AS month_start,
        count(*)                                   AS tickets_opened,
        count(*) FILTER (WHERE is_high_priority)   AS high_priority_tickets,
        avg(csat_score)                            AS avg_csat
    FROM staging.stg_support_tickets
    GROUP BY account_id, created_month
)

SELECT
    sp.account_id,
    sp.month_start,
    sp.month_label,
    sp.month_index,
    sp.days_in_month,

    -- ---- commercial position -------------------------------------------
    coalesce(sc.days_subscribed, 0) AS days_subscribed,
    sc.plan_tier,
    sc.seats_licensed,
    sc.mrr_usd,
    sc.term_end_date,
    coalesce(sc.term_is_churning, FALSE) AS term_is_churning,

    -- ELIGIBILITY. The denominator for every rate in this project. A month in
    -- which the account was barely a customer is not a month it can be judged
    -- on: partial first and last months would otherwise register as fake
    -- growth and fake collapse. Threshold lives in config.yml.
    coalesce(sc.days_subscribed, 0) >= $min_days_active_for_eligible_month
                                    AS is_eligible_month,

    date_diff('month', sp.signup_date, sp.month_start) AS tenure_months,

    -- ---- usage (LEFT JOINed, so absence becomes an explicit zero) --------
    coalesce(u.total_events, 0)             AS total_events,
    coalesce(u.core_events, 0)              AS core_events,
    coalesce(u.core_event_qty, 0)           AS core_event_qty,
    coalesce(u.active_users, 0)             AS active_users,
    coalesce(u.active_days, 0)              AS active_days,
    coalesce(u.sessions, 0)                 AS sessions,
    coalesce(u.feature_areas_used, 0)       AS feature_areas_used,
    coalesce(u.distinct_features_used, 0)   AS distinct_features_used,
    coalesce(u.power_feature_events, 0)     AS power_feature_events,
    coalesce(u.advanced_feature_events, 0)  AS advanced_feature_events,
    u.last_event_date,

    -- ---- derived ratios --------------------------------------------------
    -- nullif(x, 0) turns a zero denominator into NULL, so the result is NULL
    -- ("unknown") rather than a divide-by-zero error.
    round(coalesce(u.active_users, 0) * 1.0 / nullif(sc.seats_licensed, 0), 4)
                                            AS seat_utilisation,
    round(coalesce(u.core_events, 0) * 1.0 / nullif(u.active_users, 0), 2)
                                            AS events_per_active_user,
    round(coalesce(c.top_user_event_share, 0), 4) AS top_user_event_share,

    -- ---- support ---------------------------------------------------------
    coalesce(t.tickets_opened, 0)        AS tickets_opened,
    coalesce(t.high_priority_tickets, 0) AS high_priority_tickets,
    round(t.avg_csat, 2)                 AS avg_csat

FROM spine sp
LEFT JOIN subscription_coverage sc ON sp.account_id = sc.account_id AND sp.month_start = sc.month_start
LEFT JOIN usage u                  ON sp.account_id = u.account_id  AND sp.month_start = u.month_start
LEFT JOIN concentration c          ON sp.account_id = c.account_id  AND sp.month_start = c.month_start
LEFT JOIN tickets t                ON sp.account_id = t.account_id  AND sp.month_start = t.month_start;
