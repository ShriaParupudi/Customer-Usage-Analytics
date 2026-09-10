-- =============================================================================
-- STAGING RULE: make the data trustworthy. Typing, de-duplication, standardising
-- values, excluding rows that must never reach a metric.
-- NOT allowed here: joins across entities, aggregation, business judgement.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS staging;

CREATE OR REPLACE TABLE staging.stg_accounts AS
WITH deduped AS (
    -- Deterministic de-duplication. ROW_NUMBER() numbers the rows within each
    -- account_id; keeping rn = 1 keeps exactly one. The ORDER BY matters: it
    -- makes the choice REPRODUCIBLE. "Any row" is not an answer - two runs
    -- would disagree, and you would never work out why.
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY account_id
        ORDER BY record_loaded_at, account_name
    ) AS rn
    FROM raw.accounts
),

-- An explicit VALUE DOMAIN. Rather than hoping a string function tidies things
-- up, we state every accepted spelling and what it maps to. Anything not listed
-- falls through to the raw value AND is still caught by the
-- accounts_country_domain quality check - so a genuinely new value shows up as
-- a warning instead of being silently mangled.
industry_map(k, v) AS (
    VALUES ('TECHNOLOGY',            'Technology'),
           ('RETAIL',                'Retail'),
           ('HEALTHCARE',            'Healthcare'),
           ('FINANCIAL SERVICES',    'Financial Services'),
           ('MANUFACTURING',         'Manufacturing'),
           ('EDUCATION',             'Education'),
           ('NON-PROFIT',            'Non-profit'),
           ('PROFESSIONAL SERVICES', 'Professional Services')
),
country_map(k, v) AS (
    VALUES ('US',             'United States'),
           ('USA',            'United States'),
           ('UNITED STATES',  'United States'),
           ('UK',             'United Kingdom'),
           ('UNITED KINGDOM', 'United Kingdom'),
           ('CANADA',         'Canada'),
           ('GERMANY',        'Germany'),
           ('AUSTRALIA',      'Australia'),
           ('INDIA',          'India')
)

SELECT
    d.account_id,
    trim(d.account_name)                            AS account_name,

    -- ' Retail ', 'RETAIL' and 'retail' are one industry. Left alone they
    -- become three separate rows in every GROUP BY.
    coalesce(im.v, nullif(trim(d.industry), ''))    AS industry,

    -- Same idea for country: 'US' / 'USA' / 'u.s.a.' split the US market across
    -- three rows on a dashboard. Fixed ONCE, here.
    coalesce(cm.v, nullif(trim(d.country), ''))     AS country,

    d.employee_band,
    d.signup_date,
    d.acquisition_channel,
    d.csm_owner,                     -- legitimately NULL for self-serve accounts
    d.csm_owner IS NOT NULL          AS is_managed_account,
    date_trunc('month', d.signup_date)::DATE AS signup_month,
    d.record_loaded_at
FROM deduped d
LEFT JOIN industry_map im ON upper(trim(d.industry)) = im.k
LEFT JOIN country_map  cm ON upper(replace(trim(d.country), '.', '')) = cm.k
WHERE d.rn = 1
  -- Internal/demo accounts are excluded HERE, at the boundary, so that no
  -- downstream query can forget the filter. A filter that must be remembered
  -- in twelve places is a filter that will be forgotten in one of them.
  AND NOT d.is_internal_test;
