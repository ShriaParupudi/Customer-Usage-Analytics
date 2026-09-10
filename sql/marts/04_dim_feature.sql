CREATE OR REPLACE TABLE marts.dim_feature AS
SELECT
    event_name,
    feature_area,
    is_core_action,
    adoption_tier,
    launched_date,
    -- Features launched mid-window must be measured from THEIR launch date, not
    -- from the start of the dataset, or adoption looks artificially poor.
    launched_date > (SELECT min(month_start) FROM marts.dim_month) AS launched_in_window,
    description
FROM staging.stg_feature_catalog;
