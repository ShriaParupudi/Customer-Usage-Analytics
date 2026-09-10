-- Every event must be classifiable. An unknown event_name means either the
-- product shipped something the catalog does not know about, or the event
-- stream is corrupted. Either way, those events cannot be counted as core
-- actions, so they would silently vanish from the "active" definition.
SELECT
    'events_unknown_event_name'                     AS check_id,
    'events: event_name must exist in feature_catalog' AS check_name,
    'raw.product_usage_events'                      AS entity,
    'FAIL'                                          AS severity,
    count(*)                                        AS failed_rows,
    'unknown names: ' || coalesce(string_agg(DISTINCT e.event_name, ', '), 'none') AS detail
FROM raw.product_usage_events e
LEFT JOIN raw.feature_catalog f ON e.event_name = f.event_name
WHERE f.event_name IS NULL;
