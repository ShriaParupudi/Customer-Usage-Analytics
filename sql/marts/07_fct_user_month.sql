-- GRAIN: one row per user per month in which that user was active.
-- NOT spined: a user-month with no activity is genuinely uninteresting, and
-- 19,000 users x 24 months would be 456,000 mostly-empty rows. Spine where
-- absence is the finding (accounts); skip it where absence is just noise.
CREATE OR REPLACE TABLE marts.fct_user_month AS
SELECT
    e.user_id,
    e.account_id,
    e.event_month AS month_start,
    count(*) FILTER (WHERE e.is_core_action)                AS core_events,
    count(DISTINCT e.event_date) FILTER (WHERE e.is_core_action) AS active_days,
    count(DISTINCT e.feature_area) FILTER (WHERE e.is_core_action) AS feature_areas_used,
    count(DISTINCT e.session_id)                            AS sessions,
    max(e.event_date)                                       AS last_event_date
FROM marts.fct_usage_events e
WHERE e.has_known_user
GROUP BY e.user_id, e.account_id, e.event_month;
