-- Future-dated events usually mean a broken client clock or a timezone bug.
-- They quietly corrupt "last 30 days" style metrics and always look like growth.
SELECT
    'events_future_dated'                           AS check_id,
    'events: event_ts must not be in the future'    AS check_name,
    'raw.product_usage_events'                      AS entity,
    'FAIL'                                          AS severity,
    count(*)                                        AS failed_rows,
    'latest offending event: ' || coalesce(max(event_ts)::VARCHAR, 'none') AS detail
FROM raw.product_usage_events
WHERE event_ts > current_timestamp;
