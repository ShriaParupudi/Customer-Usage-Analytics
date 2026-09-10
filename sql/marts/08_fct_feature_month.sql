-- GRAIN: one row per account per feature_area per month.
-- Spined across feature areas so that NON-adoption is visible: an account that
-- never touches "automation" gets a row with zero, which is exactly the row a
-- product manager wants to count.
CREATE OR REPLACE TABLE marts.fct_feature_month AS
WITH areas AS (
    SELECT DISTINCT feature_area FROM marts.dim_feature WHERE is_core_action
),
spine AS (
    SELECT am.account_id, am.month_start, ar.feature_area, am.is_eligible_month
    FROM marts.fct_account_month am
    CROSS JOIN areas ar
),
usage AS (
    SELECT account_id, event_month AS month_start, feature_area,
           count(*)                        AS events,
           count(DISTINCT user_id) FILTER (WHERE has_known_user) AS users_using,
           count(DISTINCT event_name)      AS distinct_features
    FROM marts.fct_usage_events
    WHERE is_core_action
    GROUP BY 1, 2, 3
)
SELECT
    s.account_id,
    s.month_start,
    s.feature_area,
    s.is_eligible_month,
    coalesce(u.events, 0)            AS events,
    coalesce(u.users_using, 0)       AS users_using,
    coalesce(u.distinct_features, 0) AS distinct_features,
    coalesce(u.events, 0) > 0        AS is_adopted
FROM spine s
LEFT JOIN usage u
       ON s.account_id = u.account_id
      AND s.month_start = u.month_start
      AND s.feature_area = u.feature_area;
