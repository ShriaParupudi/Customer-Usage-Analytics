-- A negative event quantity is physically meaningless and, because usage is
-- summed, it silently CANCELS OUT real usage elsewhere in the same account.
SELECT
    'events_negative_qty'                           AS check_id,
    'events: event_qty must be positive'            AS check_name,
    'raw.product_usage_events'                      AS entity,
    'FAIL'                                          AS severity,
    count(*)                                        AS failed_rows,
    'most negative value seen: ' || coalesce(min(event_qty)::VARCHAR, 'none') AS detail
FROM raw.product_usage_events
WHERE event_qty <= 0;
