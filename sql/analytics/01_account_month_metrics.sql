-- =============================================================================
-- Phase 5 - Trend metrics per account-month.
--
-- This is where window functions earn their keep. A window function computes a
-- value for each row using OTHER rows nearby, without collapsing the result the
-- way GROUP BY does. That is exactly what a trend is: this month compared to
-- the months around it.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE OR REPLACE TABLE analytics.account_month_metrics AS

WITH eligible AS (
    -- Only eligible months take part in trend maths. A month where the account
    -- was a customer for 4 days is not a month it can be judged on.
    SELECT * FROM marts.fct_account_month WHERE is_eligible_month
),

windowed AS (
    SELECT
        e.*,

        -- LAG() reaches back to the previous row in the window. Here that is
        -- the account's previous eligible month.
        lag(e.core_events)  OVER w AS prev_core_events,
        lag(e.active_users) OVER w AS prev_active_users,
        lag(e.month_start)  OVER w AS prev_month_start,

        -- Rolling 3-month average INCLUDING this month. ROWS BETWEEN 2
        -- PRECEDING AND CURRENT ROW is the frame - literally "these three rows".
        avg(e.core_events) OVER (
            PARTITION BY e.account_id ORDER BY e.month_start
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS rolling_3m_events,

        -- The 3 months BEFORE those three. Comparing block-to-block instead of
        -- month-to-month is what separates a real trend from one noisy month.
        avg(e.core_events) OVER (
            PARTITION BY e.account_id ORDER BY e.month_start
            ROWS BETWEEN 5 PRECEDING AND 3 PRECEDING
        ) AS prior_3m_events,

        count(*) OVER (
            PARTITION BY e.account_id ORDER BY e.month_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS eligible_months_so_far,

        -- Gaps-and-islands set-up: a running count of ACTIVE months. Rows that
        -- share the same value of this counter form one unbroken run of zero-
        -- usage months, which lets us measure the length of a dormancy streak.
        sum(CASE WHEN e.core_events > 0 THEN 1 ELSE 0 END) OVER (
            PARTITION BY e.account_id ORDER BY e.month_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS active_run_id

    FROM eligible e
    WINDOW w AS (PARTITION BY e.account_id ORDER BY e.month_start)
),

streaks AS (
    SELECT
        w.*,
        -- Is the previous eligible month the immediately preceding calendar
        -- month? If an account lapsed and came back, comparing across the gap
        -- would be meaningless, so we refuse to compute a change at all.
        (w.prev_month_start IS NOT NULL
         AND date_diff('month', w.prev_month_start, w.month_start) = 1) AS is_contiguous,

        CASE WHEN w.core_events = 0
             THEN row_number() OVER (
                 PARTITION BY w.account_id, w.active_run_id ORDER BY w.month_start
             )
             ELSE 0
        END AS consecutive_zero_usage_months
    FROM windowed w
)

SELECT
    s.account_id,
    s.month_start,
    s.month_label,
    s.month_index,
    s.tenure_months,
    s.plan_tier,
    s.seats_licensed,
    s.mrr_usd,
    round(s.mrr_usd * 12, 2) AS arr_usd,
    s.term_end_date,
    s.days_subscribed,

    s.core_events,
    s.total_events,
    s.active_users,
    s.active_days,
    s.sessions,
    s.feature_areas_used,
    s.distinct_features_used,
    s.power_feature_events,
    s.advanced_feature_events,
    s.seat_utilisation,
    s.events_per_active_user,
    s.top_user_event_share,
    s.tickets_opened,
    s.high_priority_tickets,
    s.avg_csat,
    s.last_event_date,

    s.prev_core_events,
    s.rolling_3m_events,
    s.prior_3m_events,
    s.is_contiguous,
    s.consecutive_zero_usage_months,

    -- ---- MONTH-OVER-MONTH CHANGE ----------------------------------------
    -- The VOLUME FLOOR is the important bit. Going from 2 events to 1 is -50%,
    -- which is mathematically true and analytically worthless. Without this
    -- guard the at-risk list fills with noise, the CSM team stops opening the
    -- report, and the project is dead. NULL means "not meaningful", which is
    -- honest; 0 would be a lie.
    CASE
        WHEN NOT s.is_contiguous THEN NULL
        WHEN s.prev_core_events IS NULL THEN NULL
        WHEN s.prev_core_events < $mom_volume_floor_events THEN NULL
        ELSE round((s.core_events - s.prev_core_events) * 1.0 / s.prev_core_events, 4)
    END AS mom_change_pct,

    -- ---- SUSTAINED TREND -------------------------------------------------
    CASE
        WHEN s.prior_3m_events IS NULL THEN NULL
        WHEN s.prior_3m_events < $mom_volume_floor_events THEN NULL
        ELSE round((s.rolling_3m_events - s.prior_3m_events) / s.prior_3m_events, 4)
    END AS rolling_3m_change_pct,

    -- ---- RENEWAL PROXIMITY ----------------------------------------------
    date_diff('day', s.month_start, s.term_end_date) AS days_to_renewal

FROM streaks s;
