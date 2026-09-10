-- Value-domain check: is every value one we recognise? 'US', 'USA' and
-- 'United States' are the same country, but GROUP BY country treats them as
-- three - so a dashboard shows the US market split across three rows.
-- Catching this at ingest is how you avoid explaining a wrong chart later.
SELECT
    'accounts_country_domain'                       AS check_id,
    'accounts: country must be a recognised value'  AS check_name,
    'raw.accounts'                                  AS entity,
    'WARN'                                          AS severity,
    count(*)                                        AS failed_rows,
    'unrecognised values: ' || coalesce(string_agg(DISTINCT country, ' | '), 'none') AS detail
FROM raw.accounts
WHERE country NOT IN (
    'United States', 'United Kingdom', 'Canada', 'Germany', 'Australia', 'India'
);
