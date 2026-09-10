-- One row per cleaned, in-window usage event.
--
-- Restricted to the reporting window declared in config.yml so that this table
-- and fct_account_month always reconcile. An event outside the window would sit
-- in the event fact but appear in no month of the spine, and the two tables
-- would disagree on total usage - the kind of discrepancy that costs an
-- afternoon to track down.
CREATE OR REPLACE TABLE marts.fct_usage_events AS
SELECT
    e.event_id,
    e.account_id,
    e.user_id,
    e.has_known_user,
    e.event_ts,
    e.event_date,
    e.event_month,
    e.event_name,
    e.feature_area,
    e.is_core_action,
    e.adoption_tier,
    e.surface,
    e.session_id,
    e.event_qty
FROM staging.stg_usage_events e
JOIN marts.dim_month m ON e.event_month = m.month_start;
