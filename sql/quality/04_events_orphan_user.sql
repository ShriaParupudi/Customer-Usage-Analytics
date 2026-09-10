-- Same principle for events. A LEFT JOIN plus "WHERE right side IS NULL" is the
-- standard anti-join pattern for finding rows with no match - worth memorising.
SELECT
    'events_orphan_user'                            AS check_id,
    'events: user_id must exist in users'           AS check_name,
    'raw.product_usage_events'                      AS entity,
    'FAIL'                                          AS severity,
    count(*)                                        AS failed_rows,
    'events referencing a user_id that is not in raw.users' AS detail
FROM raw.product_usage_events e
LEFT JOIN raw.users u ON e.user_id = u.user_id
WHERE u.user_id IS NULL;
