-- Company-level KPIs: one row per month. The trend line on the dashboard.
CREATE OR REPLACE TABLE analytics.agg_monthly_kpis AS
WITH m AS (
    SELECT * FROM analytics.account_health_monthly
),
per_month AS (
    SELECT
        month_start,
        month_label,
        count(*)                                        AS eligible_accounts,
        count(*) FILTER (WHERE core_events > 0)         AS monthly_active_accounts,
        sum(active_users)                               AS monthly_active_users,
        sum(core_events)                                AS total_core_events,
        count(*) FILTER (WHERE core_events = 0)         AS zero_usage_accounts,
        count(*) FILTER (WHERE flag_sharp_mom_decline)  AS declining_accounts,
        count(*) FILTER (WHERE flag_sustained_decline)  AS sustained_decline_accounts,
        count(*) FILTER (WHERE risk_band = 'High')      AS high_risk_accounts,
        count(*) FILTER (WHERE risk_band = 'Medium')    AS medium_risk_accounts,
        round(sum(arr_usd), 2)                          AS total_arr_usd,
        round(sum(arr_usd) FILTER (WHERE risk_band = 'High'), 2) AS arr_at_high_risk_usd,
        round(avg(seat_utilisation), 4)                 AS avg_seat_utilisation,
        round(avg(active_days), 2)                      AS avg_active_days,
        round(avg(feature_areas_adopted), 2)            AS avg_feature_areas_adopted
    FROM m
    GROUP BY month_start, month_label
)
SELECT
    p.*,
    round(monthly_active_accounts * 1.0 / nullif(eligible_accounts, 0), 4) AS active_account_rate,
    round(arr_at_high_risk_usd / nullif(total_arr_usd, 0), 4)              AS pct_arr_at_high_risk,
    -- MoM movement on the headline numbers, for the KPI tiles.
    round((total_core_events - lag(total_core_events) OVER (ORDER BY month_start))
          * 1.0 / nullif(lag(total_core_events) OVER (ORDER BY month_start), 0), 4) AS events_mom_change,
    round((monthly_active_accounts - lag(monthly_active_accounts) OVER (ORDER BY month_start))
          * 1.0 / nullif(lag(monthly_active_accounts) OVER (ORDER BY month_start), 0), 4) AS maa_mom_change
FROM per_month p;
