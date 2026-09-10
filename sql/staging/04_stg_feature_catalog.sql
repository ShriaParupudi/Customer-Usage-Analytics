CREATE OR REPLACE TABLE staging.stg_feature_catalog AS
SELECT
    event_name,
    feature_area,
    is_core_action,
    adoption_tier,
    launched_date,
    description
FROM raw.feature_catalog;
