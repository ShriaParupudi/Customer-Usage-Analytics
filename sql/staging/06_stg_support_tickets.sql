CREATE OR REPLACE TABLE staging.stg_support_tickets AS
SELECT
    t.ticket_id,
    t.account_id,
    t.user_id,
    t.created_ts,
    t.created_ts::DATE                     AS created_date,
    date_trunc('month', t.created_ts)::DATE AS created_month,
    t.resolved_ts,
    t.resolved_ts IS NULL                  AS is_open,
    CASE WHEN t.resolved_ts IS NOT NULL
         THEN date_diff('hour', t.created_ts, t.resolved_ts) END AS resolution_hours,
    lower(trim(t.priority))                AS priority,
    lower(trim(t.category))                AS category,
    t.priority IN ('high', 'urgent')       AS is_high_priority,
    t.csat_score,          -- mostly NULL by design: real surveys go unanswered
    t.record_loaded_at
FROM raw.support_tickets t
JOIN staging.stg_accounts a ON t.account_id = a.account_id;
