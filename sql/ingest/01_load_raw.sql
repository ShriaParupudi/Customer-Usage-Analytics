-- =============================================================================
-- Phase 2 - Ingestion into the `raw` schema
--
-- RULE FOR THIS LAYER: load the source exactly as it arrived. No cleaning, no
-- casting beyond what the reader infers, no filtering, no deduplication.
--
-- Why: when a number downstream looks wrong, the first question is always "is
-- the data wrong, or is our code wrong?" An untouched raw layer answers that in
-- thirty seconds. Teams that clean on ingest lose the ability to audit
-- themselves, and a bug fix becomes a re-request to the source system instead
-- of a re-run of staging.
--
-- The ONLY column we add is record_loaded_at - lineage, not content.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS raw;

-- CREATE OR REPLACE makes this idempotent: running it twice gives the same
-- result as running it once. If a step is not idempotent you cannot safely
-- re-run it after a fix - and you will need to, constantly.

-- sample_size = -1 tells DuckDB to scan the WHOLE file when inferring column
-- types instead of the first few thousand rows. Sampling is how you end up with
-- a column typed INTEGER that later hits a NULL or a stray string and blows up.
CREATE OR REPLACE TABLE raw.accounts AS
SELECT *, current_timestamp AS record_loaded_at
FROM read_csv_auto('data/raw/accounts.csv', sample_size = -1);

CREATE OR REPLACE TABLE raw.users AS
SELECT *, current_timestamp AS record_loaded_at
FROM read_csv_auto('data/raw/users.csv', sample_size = -1);

CREATE OR REPLACE TABLE raw.subscriptions AS
SELECT *, current_timestamp AS record_loaded_at
FROM read_csv_auto('data/raw/subscriptions.csv', sample_size = -1);

CREATE OR REPLACE TABLE raw.support_tickets AS
SELECT *, current_timestamp AS record_loaded_at
FROM read_csv_auto('data/raw/support_tickets.csv', sample_size = -1);

CREATE OR REPLACE TABLE raw.feature_catalog AS
SELECT *, current_timestamp AS record_loaded_at
FROM read_csv_auto('data/raw/feature_catalog.csv', sample_size = -1);

-- The events file is gzipped CSV (~3M rows). DuckDB decompresses it on the fly.
-- Note it is loaded exactly like the others: same rule, no exceptions for size.
CREATE OR REPLACE TABLE raw.product_usage_events AS
SELECT *, current_timestamp AS record_loaded_at
FROM read_csv_auto('data/raw/product_usage_events.csv.gz', sample_size = -1);
