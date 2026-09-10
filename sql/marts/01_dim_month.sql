-- =============================================================================
-- THE MONTH SPINE - the single most important table in this project.
--
-- Why it exists: if you build monthly usage with GROUP BY account, month over
-- the events table, an account with ZERO usage in March produces NO ROW AT ALL.
-- Your "zero-usage accounts" report then returns nothing, and it looks like it
-- worked. Absence of data is not the same as data showing absence.
--
-- The fix: generate the complete list of months first, CROSS JOIN it to the
-- complete list of accounts to get every account x month cell, then LEFT JOIN
-- usage onto that grid. Missing usage becomes an explicit 0.
--
-- The window comes from config.yml, NOT from min/max of the event data. Infer
-- it from the data and one mis-dated event stretches every trend chart
-- backwards by years. The reporting window is a business decision.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS marts;

CREATE OR REPLACE TABLE marts.dim_month AS
WITH months AS (
    -- generate_series builds the calendar out of nothing - no source table
    -- needed, which is the point: the spine must not depend on whether data
    -- happens to exist for a given month.
    SELECT unnest(generate_series(
        DATE '$analysis_start_month',
        DATE '$analysis_end_month',
        INTERVAL 1 MONTH
    ))::DATE AS month_start
)
SELECT
    month_start,
    (month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY)::DATE AS month_end,
    year(month_start)                                        AS year,
    month(month_start)                                       AS month_num,
    strftime(month_start, '%Y-%m')                           AS month_label,
    date_diff('day', month_start,
              (month_start + INTERVAL 1 MONTH)::DATE)        AS days_in_month,
    ROW_NUMBER() OVER (ORDER BY month_start) - 1             AS month_index
FROM months;
