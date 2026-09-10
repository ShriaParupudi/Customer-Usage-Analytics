-- Referential integrity: every user must belong to an account that exists.
-- An orphan user silently disappears from any INNER JOIN to accounts, so its
-- usage vanishes from account-level metrics without anyone noticing.
SELECT
    'users_orphan_account'                          AS check_id,
    'users: account_id must exist in accounts'      AS check_name,
    'raw.users'                                     AS entity,
    'FAIL'                                          AS severity,
    count(*)                                        AS failed_rows,
    'orphan account_ids: ' || coalesce(string_agg(DISTINCT u.account_id, ', '), 'none') AS detail
FROM raw.users u
LEFT JOIN raw.accounts a ON u.account_id = a.account_id
WHERE a.account_id IS NULL;
