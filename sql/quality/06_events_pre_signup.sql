-- Temporal consistency: an account cannot generate product events before it
-- existed. These rows would land in months the account was not a customer,
-- polluting cohort analysis and inflating early-tenure usage.
SELECT
    'events_pre_signup'                             AS check_id,
    'events: event_ts must be on or after the account signup_date' AS check_name,
    'raw.product_usage_events'                      AS entity,
    'FAIL'                                          AS severity,
    count(*)                                        AS failed_rows,
    'earliest offending event: ' || coalesce(min(e.event_ts)::VARCHAR, 'none') AS detail
FROM raw.product_usage_events e
JOIN raw.accounts a ON e.account_id = a.account_id
WHERE e.event_ts < a.signup_date;
