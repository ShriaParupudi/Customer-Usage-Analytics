"""Phase 8b - Build the self-contained HTML dashboard.

Reads the analytics tables, assembles one JSON payload, and injects it into
dashboards/dashboard_template.html. The output is a single file with no external
dependencies - it opens in any browser, works offline, and can be committed to
the repo so a reviewer sees the result without running anything.

Run with:  python -m src.build_dashboard
"""

from __future__ import annotations

import json
import logging
import time

from src.utils.config import PROJECT_ROOT, load_config
from src.utils.db import connect
from src.utils.logging_config import setup_logging

log = logging.getLogger("dashboard")

TEMPLATE = PROJECT_ROOT / "dashboards" / "dashboard_template.html"
OUTPUT = PROJECT_ROOT / "dashboards" / "customer_health_dashboard.html"


def rows(con, query: str) -> list[dict]:
    """Run a query and return a list of dicts (JSON-ready)."""
    cur = con.execute(query)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def main() -> None:
    setup_logging()
    t0 = time.time()
    cfg = load_config()
    con = connect(read_only=True)

    monthly = rows(con, """
        SELECT month_label, eligible_accounts, monthly_active_accounts,
               monthly_active_users, total_core_events, zero_usage_accounts,
               declining_accounts, sustained_decline_accounts, high_risk_accounts,
               total_arr_usd, arr_at_high_risk_usd, pct_arr_at_high_risk,
               avg_seat_utilisation, avg_active_days, avg_feature_areas_adopted,
               events_mom_change, maa_mom_change
        FROM analytics.agg_monthly_kpis ORDER BY month_start
    """)

    risk_bands = rows(con, """
        SELECT risk_band, count(*) AS accounts, round(sum(arr_usd)) AS arr
        FROM analytics.account_health_current GROUP BY 1
    """)

    segments = rows(con, """
        SELECT engagement_segment AS segment, count(*) AS accounts,
               round(sum(arr_usd)) AS arr
        FROM analytics.account_health_current GROUP BY 1
    """)

    size_by_risk = rows(con, """
        SELECT size_segment, risk_band, count(*) AS accounts
        FROM analytics.account_health_current GROUP BY 1, 2
    """)

    adoption = rows(con, """
        SELECT feature_area, adoption_rate, adopting_accounts, eligible_accounts
        FROM analytics.feature_adoption_monthly
        WHERE month_start = (SELECT max(month_start) FROM analytics.feature_adoption_monthly)
        ORDER BY adoption_rate DESC
    """)

    features = rows(con, """
        SELECT event_name, feature_area, adoption_tier, pct_accounts_using,
               accounts_using, launched_in_window
        FROM analytics.feature_adoption_since_launch
        ORDER BY pct_accounts_using ASC LIMIT 8
    """)

    at_risk = rows(con, """
        SELECT account_name, industry, plan_tier, csm_owner, round(arr_usd) AS arr,
               risk_score, risk_band, core_events, active_users, active_days,
               consecutive_zero_usage_months AS dormant_months,
               days_to_renewal, risk_reasons
        FROM analytics.account_health_current
        WHERE risk_band = 'High'
        ORDER BY arr_usd DESC LIMIT 15
    """)

    # A SECOND action list. Dormant accounts and declining accounts are both
    # risky, but they are different jobs: a dormant account needs re-onboarding,
    # a declining one still has users to save. Blending them into a single
    # ranked list hides the account a CSM can actually still rescue.
    declining = rows(con, """
        SELECT account_name, industry, plan_tier, csm_owner, round(arr_usd) AS arr,
               risk_score, core_events, prev_core_events, active_users,
               round(100 * mom_change_pct) AS mom_pct,
               round(100 * rolling_3m_change_pct) AS trend_pct,
               days_to_renewal, seat_utilisation
        FROM analytics.account_health_current
        WHERE core_events > 0
          AND (flag_sustained_decline OR flag_sharp_mom_decline)
        ORDER BY arr_usd DESC LIMIT 12
    """)

    totals = con.execute("""
        SELECT count(*), round(sum(arr_usd)),
               (SELECT count(*) FROM marts.fct_usage_events),
               (SELECT max(month_label) FROM analytics.agg_monthly_kpis)
        FROM analytics.account_health_current
    """).fetchone()

    con.close()

    payload = {
        "generated_from": "analytics.account_health_current / agg_monthly_kpis",
        "latest_month": totals[3],
        "totals": {
            "accounts": totals[0],
            "arr": float(totals[1] or 0),
            "events": totals[2],
        },
        "thresholds": {
            "decline_mom": cfg["metrics"]["decline_threshold_mom"],
            "sustained": cfg["metrics"]["sustained_decline_threshold"],
            "volume_floor": cfg["metrics"]["mom_volume_floor_events"],
            "eligible_days": cfg["metrics"]["min_days_active_for_eligible_month"],
            "risk_high": cfg["risk_bands"]["high"],
            "risk_medium": cfg["risk_bands"]["medium"],
        },
        "monthly": monthly,
        "risk_bands": risk_bands,
        "segments": segments,
        "size_by_risk": size_by_risk,
        "adoption": adoption,
        "least_adopted_features": features,
        "at_risk": at_risk,
        "declining": declining,
    }

    html = TEMPLATE.read_text(encoding="utf-8")
    # default=str so DATE/DECIMAL values serialise without a custom encoder.
    html = html.replace("/*__DATA__*/{}", json.dumps(payload, default=str))
    OUTPUT.write_text(html, encoding="utf-8")

    log.info("dashboard written to %s (%.1fs)", OUTPUT.relative_to(PROJECT_ROOT), time.time() - t0)


if __name__ == "__main__":
    main()
