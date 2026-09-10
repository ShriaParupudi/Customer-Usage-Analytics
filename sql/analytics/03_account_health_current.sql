-- The latest eligible month per account: the table a dashboard connects to.
-- Materialised rather than left as a view so the BI tool reads one small table
-- instead of scanning 10,000 rows and filtering.
CREATE OR REPLACE TABLE analytics.account_health_current AS
WITH latest AS (
    SELECT account_id, max(month_start) AS month_start
    FROM analytics.account_health_monthly
    GROUP BY account_id
)
SELECT h.*
FROM analytics.account_health_monthly h
JOIN latest l ON h.account_id = l.account_id AND h.month_start = l.month_start;
