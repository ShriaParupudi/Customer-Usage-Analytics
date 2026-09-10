CREATE OR REPLACE TABLE marts.dim_user AS
SELECT
    u.user_id,
    u.account_id,
    a.account_name,
    a.current_plan_tier,
    u.role,
    u.department,
    u.user_created_date,
    u.deactivated_date,
    u.is_active_seat,
    date_trunc('month', u.user_created_date)::DATE AS created_month
FROM staging.stg_users u
JOIN marts.dim_account a ON u.account_id = a.account_id;
