-- Impossible values. seats_licensed is the denominator of seat utilisation:
-- a zero would divide by zero, a negative would produce a negative percentage.
SELECT
    'subs_invalid_seats'                            AS check_id,
    'subscriptions: seats_licensed and mrr_usd must be positive' AS check_name,
    'raw.subscriptions'                             AS entity,
    'FAIL'                                          AS severity,
    count(*)                                        AS failed_rows,
    'offending ids: ' || coalesce(string_agg(subscription_id, ', '), 'none') AS detail
FROM raw.subscriptions
WHERE seats_licensed <= 0 OR mrr_usd < 0;
