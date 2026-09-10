-- =============================================================================
-- Phases 6 & 7 - Segmentation, feature adoption depth, and retention risk.
--
-- THIS is the opinionated layer. Everything above it was factual: "412 events
-- in March" will never change. Everything here is a judgement your VP will want
-- to retune next quarter, which is exactly why it lives in its own file with
-- every number coming from config.yml.
--
-- The risk score is deliberately a TRANSPARENT WEIGHTED SUM, not a model. A CSM
-- has to be able to see why an account surfaced. "Score 70" is useless;
-- "zero usage for 2 months and renews in 46 days" is a phone call.
-- =============================================================================

CREATE OR REPLACE TABLE analytics.account_health_monthly AS

WITH adoption AS (
    -- Adoption BREADTH (how many areas) and DEPTH (how deeply within them).
    -- Breadth alone rewards dabbling; depth alone misses a narrow power user.
    SELECT
        account_id,
        month_start,
        count(*) FILTER (WHERE is_adopted)                   AS areas_adopted,
        count(*)                                             AS areas_available,
        round(count(*) FILTER (WHERE is_adopted) * 1.0 / count(*), 3) AS adoption_breadth_pct
    FROM marts.fct_feature_month
    GROUP BY account_id, month_start
),

base AS (
    SELECT
        m.*,
        a.account_name,
        a.industry,
        a.country,
        a.employee_band,
        a.acquisition_channel,
        a.csm_owner,
        a.is_managed_account,
        a.signup_date,
        coalesce(ad.areas_adopted, 0)      AS feature_areas_adopted,
        coalesce(ad.adoption_breadth_pct, 0) AS adoption_breadth_pct
    FROM analytics.account_month_metrics m
    JOIN marts.dim_account a ON m.account_id = a.account_id
    LEFT JOIN adoption ad
           ON m.account_id = ad.account_id AND m.month_start = ad.month_start
),

flagged AS (
    SELECT
        b.*,

        -- ---- SEGMENTS: plain business rules, not clustering ---------------
        -- Rule-based segments first, because a CSM has to be able to read the
        -- label and know what it means. k-means would produce "cluster 3",
        -- which nobody can action and which shifts every time you refit.

        CASE
            WHEN b.plan_tier = 'enterprise' THEN 'Enterprise'
            WHEN b.plan_tier = 'business'   THEN 'Mid-Market'
            WHEN b.plan_tier = 'growth'     THEN 'SMB'
            ELSE 'Self-Serve'
        END AS size_segment,

        CASE
            WHEN b.tenure_months < 3  THEN 'Onboarding'
            WHEN b.tenure_months < 12 THEN 'Establishing'
            WHEN b.tenure_months < 24 THEN 'Established'
            ELSE 'Mature'
        END AS lifecycle_segment,

        -- Engagement combines FREQUENCY (active days) with REACH (seat
        -- utilisation). One user hammering the product daily and forty users
        -- touching it once are different problems.
        CASE
            WHEN b.core_events = 0 THEN 'Dormant'
            WHEN b.active_days >= 12 AND coalesce(b.seat_utilisation, 0) >= 0.5 THEN 'Power'
            WHEN b.active_days >= 8  THEN 'Engaged'
            WHEN b.active_days >= $engagement_low_active_days THEN 'Casual'
            ELSE 'Minimal'
        END AS engagement_segment,

        -- ---- RISK FLAGS: each one observable, each one explainable --------
        (b.core_events = 0)                                           AS flag_zero_usage,
        (b.consecutive_zero_usage_months >= 2)                        AS flag_dormant_2m,
        (b.mom_change_pct IS NOT NULL
             AND b.mom_change_pct <= $decline_threshold_mom)          AS flag_sharp_mom_decline,
        (b.rolling_3m_change_pct IS NOT NULL
             AND b.rolling_3m_change_pct <= $sustained_decline_threshold) AS flag_sustained_decline,
        (b.seat_utilisation IS NOT NULL
             AND b.seat_utilisation < $low_seat_utilisation_threshold) AS flag_low_seat_utilisation,
        -- Key-person risk: one resignation away from going dark.
        (b.active_users = 1 OR b.top_user_event_share >= 0.8)         AS flag_single_active_user,
        (b.feature_areas_adopted <= 1)                                AS flag_narrow_adoption,
        (b.core_events > 0 AND b.active_days < $engagement_low_active_days) AS flag_low_frequency,
        (b.high_priority_tickets >= 2)                                AS flag_support_pressure,
        (b.days_to_renewal IS NOT NULL AND b.days_to_renewal BETWEEN 0 AND 90) AS flag_renewal_soon

    FROM base b
),

scored AS (
    SELECT
        f.*,
        -- Weighted sum. Every weight is in config.yml so a stakeholder can
        -- retune the model by editing one file, with no SQL changes at all.
        (
              CASE WHEN f.flag_zero_usage            THEN $rw_zero_usage_month      ELSE 0 END
            + CASE WHEN f.flag_dormant_2m            THEN $rw_dormant_2m            ELSE 0 END
            + CASE WHEN f.flag_sustained_decline     THEN $rw_sustained_decline     ELSE 0 END
            + CASE WHEN f.flag_sharp_mom_decline     THEN $rw_sharp_mom_decline     ELSE 0 END
            + CASE WHEN f.flag_low_seat_utilisation  THEN $rw_low_seat_utilisation  ELSE 0 END
            + CASE WHEN f.flag_single_active_user    THEN $rw_single_active_user    ELSE 0 END
            + CASE WHEN f.flag_narrow_adoption       THEN $rw_narrow_feature_adoption ELSE 0 END
            + CASE WHEN f.flag_low_frequency         THEN $rw_low_engagement_frequency ELSE 0 END
            + CASE WHEN f.flag_support_pressure      THEN $rw_high_priority_tickets ELSE 0 END
            + CASE WHEN f.flag_renewal_soon          THEN $rw_renewal_within_90_days ELSE 0 END
        ) AS risk_score
    FROM flagged f
)

SELECT
    s.*,
    CASE
        WHEN s.risk_score >= $band_high   THEN 'High'
        WHEN s.risk_score >= $band_medium THEN 'Medium'
        ELSE 'Low'
    END AS risk_band,

    -- A human-readable reason string. This is the difference between a report
    -- a CSM acts on and a report a CSM ignores: the number tells you to look,
    -- the reason tells you what to say on the call.
    nullif(concat_ws('; ',
        CASE WHEN s.flag_dormant_2m            THEN 'no usage for ' || s.consecutive_zero_usage_months || ' months' END,
        CASE WHEN s.flag_zero_usage AND NOT s.flag_dormant_2m THEN 'zero usage this month' END,
        CASE WHEN s.flag_sustained_decline     THEN 'sustained decline ' || round(100 * s.rolling_3m_change_pct) || '%' END,
        CASE WHEN s.flag_sharp_mom_decline     THEN 'MoM drop ' || round(100 * s.mom_change_pct) || '%' END,
        CASE WHEN s.flag_single_active_user AND NOT s.flag_zero_usage
                                               THEN 'usage concentrated in one user' END,
        CASE WHEN s.flag_low_seat_utilisation AND NOT s.flag_zero_usage
                                               THEN 'only ' || round(100 * s.seat_utilisation) || '% of seats active' END,
        CASE WHEN s.flag_narrow_adoption AND NOT s.flag_zero_usage
                                               THEN 'uses ' || s.feature_areas_adopted || ' of 6 feature areas' END,
        CASE WHEN s.flag_low_frequency         THEN 'active on only ' || s.active_days || ' days' END,
        CASE WHEN s.flag_support_pressure      THEN s.high_priority_tickets || ' high-priority tickets' END,
        CASE WHEN s.flag_renewal_soon          THEN 'renews in ' || s.days_to_renewal || ' days' END
    ), '') AS risk_reasons
FROM scored s;
