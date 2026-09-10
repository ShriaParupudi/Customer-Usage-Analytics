-- Same threshold pattern for a column we expect to be patchy in real life.
SELECT
    'users_null_department'                         AS check_id,
    'users: department null rate within tolerance'  AS check_name,
    'raw.users'                                     AS entity,
    'WARN'                                          AS severity,
    CASE WHEN avg(CASE WHEN department IS NULL THEN 1.0 ELSE 0.0 END) > $max_null_rate_department
         THEN count(*) FILTER (WHERE department IS NULL)
         ELSE 0 END                                 AS failed_rows,
    'null rate ' || round(100 * avg(CASE WHEN department IS NULL THEN 1.0 ELSE 0.0 END), 2)
        || '% vs tolerance ' || round(100 * $max_null_rate_department, 2) || '%' AS detail
FROM raw.users;
