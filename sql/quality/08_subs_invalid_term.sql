-- An interval that ends before it starts is impossible, and it breaks the
-- overlap join used to answer "what plan was this account on in March?"
SELECT
    'subs_invalid_term'                             AS check_id,
    'subscriptions: term_end_date must be after term_start_date' AS check_name,
    'raw.subscriptions'                             AS entity,
    'FAIL'                                          AS severity,
    count(*)                                        AS failed_rows,
    'offending ids: ' || coalesce(string_agg(subscription_id, ', '), 'none') AS detail
FROM raw.subscriptions
WHERE term_end_date < term_start_date;
