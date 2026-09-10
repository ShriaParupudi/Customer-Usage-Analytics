-- Phase 6 - Feature adoption across the customer base, by month and area.
-- Answers the product question: what did we ship that nobody uses?
CREATE OR REPLACE TABLE analytics.feature_adoption_monthly AS
SELECT
    f.month_start,
    m.month_label,
    f.feature_area,
    count(*)                                       AS eligible_accounts,
    count(*) FILTER (WHERE f.is_adopted)           AS adopting_accounts,
    round(count(*) FILTER (WHERE f.is_adopted) * 1.0 / count(*), 4) AS adoption_rate,
    sum(f.events)                                  AS events,
    sum(f.users_using)                             AS users_using
FROM marts.fct_feature_month f
JOIN marts.dim_month m ON f.month_start = m.month_start
WHERE f.is_eligible_month
GROUP BY f.month_start, m.month_label, f.feature_area;

-- Per-feature (not just per-area) adoption, measured SINCE LAUNCH. A feature
-- released in month 18 must not be judged on 24 months of history.
CREATE OR REPLACE TABLE analytics.feature_adoption_since_launch AS
WITH per_feature AS (
    SELECT
        e.event_name,
        count(DISTINCT e.account_id) AS accounts_using,
        count(DISTINCT e.user_id) FILTER (WHERE e.has_known_user) AS users_using,
        count(*) AS events,
        min(e.event_date) AS first_used_date
    FROM marts.fct_usage_events e
    WHERE e.is_core_action
    GROUP BY e.event_name
)
SELECT
    d.event_name,
    d.feature_area,
    d.adoption_tier,
    d.launched_date,
    d.launched_in_window,
    coalesce(p.accounts_using, 0) AS accounts_using,
    coalesce(p.users_using, 0)    AS users_using,
    coalesce(p.events, 0)         AS events,
    round(coalesce(p.accounts_using, 0) * 1.0
          / (SELECT count(*) FROM marts.dim_account), 4) AS pct_accounts_using,
    p.first_used_date,
    greatest(0, date_diff('month',
        greatest(d.launched_date, (SELECT min(month_start) FROM marts.dim_month)),
        (SELECT max(month_start) FROM marts.dim_month))) AS months_available_in_window
FROM marts.dim_feature d
LEFT JOIN per_feature p ON d.event_name = p.event_name
WHERE d.is_core_action;
