-- Cross-field consistency: the event carries a denormalised account_id, which
-- must agree with the account the acting user actually belongs to. WARN rather
-- than FAIL because a small mismatch rate is common in real telemetry (users
-- moving between workspaces) and we resolve it explicitly in staging.
SELECT
    'events_account_mismatch'                       AS check_id,
    'events: account_id must match the user''s account' AS check_name,
    'raw.product_usage_events'                      AS entity,
    'WARN'                                          AS severity,
    count(*)                                        AS failed_rows,
    'events whose account_id contradicts users.account_id' AS detail
FROM raw.product_usage_events e
JOIN raw.users u ON e.user_id = u.user_id
WHERE e.account_id <> u.account_id;
