-- Not every NULL is a defect. Some columns are legitimately optional (csm_owner
-- is NULL for self-serve accounts by design). What matters is whether the null
-- RATE exceeds what we agreed is tolerable - so this check is a threshold, not
-- a zero-tolerance rule. The threshold comes from config.yml.
SELECT
    'accounts_null_industry'                        AS check_id,
    'accounts: industry null rate within tolerance' AS check_name,
    'raw.accounts'                                  AS entity,
    'WARN'                                          AS severity,
    CASE WHEN avg(CASE WHEN industry IS NULL THEN 1.0 ELSE 0.0 END) > $max_null_rate_industry
         THEN count(*) FILTER (WHERE industry IS NULL)
         ELSE 0 END                                 AS failed_rows,
    'null rate ' || round(100 * avg(CASE WHEN industry IS NULL THEN 1.0 ELSE 0.0 END), 2)
        || '% vs tolerance ' || round(100 * $max_null_rate_industry, 2) || '%' AS detail
FROM raw.accounts;
