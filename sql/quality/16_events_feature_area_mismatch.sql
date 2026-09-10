-- The events table carries a denormalised feature_area. The catalog is the
-- source of truth (see docs/assumptions.md #5). Disagreement is a WARN because
-- staging resolves it by taking the catalog value - but we want it VISIBLE
-- rather than silently overwritten, because a rising mismatch rate means the
-- producing service and the catalog have drifted apart.
SELECT
    'events_feature_area_mismatch'                  AS check_id,
    'events: feature_area must match the feature_catalog' AS check_name,
    'raw.product_usage_events'                      AS entity,
    'WARN'                                          AS severity,
    count(*)                                        AS failed_rows,
    'rows where the event''s feature_area disagrees with the catalog' AS detail
FROM raw.product_usage_events e
JOIN raw.feature_catalog f ON e.event_name = f.event_name
WHERE e.feature_area <> f.feature_area;
