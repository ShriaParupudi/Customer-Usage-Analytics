-- Duplicate events inflate every usage metric. Because they are exact copies,
-- nothing errors - the numbers are simply wrong, which is far more dangerous.
SELECT
    'events_duplicate_pk'                           AS check_id,
    'product_usage_events: event_id must be unique' AS check_name,
    'raw.product_usage_events'                      AS entity,
    'FAIL'                                          AS severity,
    coalesce(count(*), 0)                           AS failed_rows,
    'distinct event_ids appearing more than once'   AS detail
FROM (
    SELECT event_id FROM raw.product_usage_events GROUP BY event_id HAVING count(*) > 1
);
