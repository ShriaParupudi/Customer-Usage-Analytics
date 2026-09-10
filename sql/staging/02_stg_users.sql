CREATE OR REPLACE TABLE staging.stg_users AS
WITH deduped AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY record_loaded_at) AS rn
    FROM raw.users
)
SELECT
    u.user_id,
    u.account_id,
    u.user_created_date,
    u.deactivated_date,
    u.deactivated_date IS NULL AS is_active_seat,
    lower(trim(u.role))        AS role,
    nullif(trim(u.department), '') AS department,
    lower(trim(u.email_domain))   AS email_domain,
    u.invited_by_user_id,
    u.record_loaded_at
FROM deduped u
-- Orphan users are DROPPED: a user whose account does not exist cannot be
-- attributed to anything, so keeping it would only create a phantom segment.
-- (This INNER JOIN also removes users of excluded internal test accounts.)
JOIN staging.stg_accounts a ON u.account_id = a.account_id
WHERE u.rn = 1;
