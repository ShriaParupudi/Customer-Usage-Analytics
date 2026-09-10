-- The big one. Every resolution here maps to an ACCEPTED defect in
-- outputs/dq_report.md - the report says what is wrong, this file says what we
-- did about it.
CREATE OR REPLACE TABLE staging.stg_usage_events AS
WITH deduped AS (
    -- Exact duplicate rows share an event_id. Keeping one per id is the whole
    -- fix; without it every usage metric is inflated by ~0.4% and nothing
    -- anywhere raises an error.
    SELECT *, ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY record_loaded_at) AS rn
    FROM raw.product_usage_events
)
SELECT
    e.event_id,
    e.account_id,
    e.user_id,
    -- Orphan user_ids are kept but FLAGGED. The event still tells us the
    -- account did something, which is what account-level metrics need; we just
    -- must not count that user in any distinct-user metric.
    (u.user_id IS NOT NULL)          AS has_known_user,
    e.event_ts,
    e.event_ts::DATE                 AS event_date,
    date_trunc('month', e.event_ts)::DATE AS event_month,
    e.event_name,

    -- The catalog is the source of truth for classification (assumptions #5).
    -- The event's own denormalised feature_area is deliberately discarded.
    f.feature_area,
    f.is_core_action,
    f.adoption_tier,

    e.surface,
    e.session_id,
    e.event_qty,
    nullif(e.duration_ms, 0)         AS duration_ms,
    e.record_loaded_at
FROM deduped e
-- INNER JOIN: an event we cannot classify cannot be counted as a core action,
-- so it must not silently enter the "active" definition.
JOIN staging.stg_feature_catalog f ON e.event_name = f.event_name
-- INNER JOIN to accounts: drops events belonging to excluded internal test
-- accounts, and events whose account_id does not resolve at all.
JOIN staging.stg_accounts a        ON e.account_id = a.account_id
LEFT JOIN staging.stg_users u      ON e.user_id = u.user_id
WHERE e.rn = 1
  -- Provably impossible rows, each one an ACCEPTED defect in the DQ report:
  AND e.event_ts >= a.signup_date        -- cannot act before the account existed
  AND e.event_ts <= current_timestamp    -- cannot act in the future
  AND e.event_qty > 0;                   -- negative usage would CANCEL real usage
