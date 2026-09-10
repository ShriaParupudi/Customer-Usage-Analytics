-- A primary key that is not unique breaks every join downstream: each duplicate
-- multiplies the rows on the other side of the join. This is non-negotiable.
SELECT
    'accounts_duplicate_pk'                         AS check_id,
    'accounts: account_id must be unique'           AS check_name,
    'raw.accounts'                                  AS entity,
    'FAIL'                                          AS severity,
    coalesce(count(*), 0)                           AS failed_rows,
    'duplicated ids: ' || coalesce(string_agg(account_id, ', '), 'none') AS detail
FROM (
    SELECT account_id FROM raw.accounts GROUP BY account_id HAVING count(*) > 1
);
