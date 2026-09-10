"""Phase 8a - Export analytics tables as CSV for any BI tool.

Why a flat CSV export rather than pointing the BI tool at DuckDB: Looker Studio,
Tableau Public and Power BI all read CSV without a driver, and the export is a
stable contract - the dashboard cannot accidentally depend on an internal
staging table that gets restructured next week.

The reporting layer does NO transformation. Everything a dashboard needs was
already computed in the analytics layer. If a dashboard needs a calculated
field, that is a signal the calculation belongs upstream, where it can be
tested and reused.

Run with:  python -m src.export_bi
"""

from __future__ import annotations

import logging
import time

from src.utils.config import OUTPUTS_DIR
from src.utils.db import connect
from src.utils.logging_config import setup_logging

log = logging.getLogger("export")

EXPORTS = {
    # filename: query
    "account_health_current.csv": "SELECT * FROM analytics.account_health_current ORDER BY risk_score DESC, arr_usd DESC",
    "account_health_monthly.csv": "SELECT * FROM analytics.account_health_monthly ORDER BY account_id, month_start",
    "monthly_kpis.csv": "SELECT * FROM analytics.agg_monthly_kpis ORDER BY month_start",
    "feature_adoption_monthly.csv": "SELECT * FROM analytics.feature_adoption_monthly ORDER BY month_start, feature_area",
    "feature_adoption_since_launch.csv": "SELECT * FROM analytics.feature_adoption_since_launch ORDER BY accounts_using DESC",
    "at_risk_accounts.csv": """
        SELECT account_id, account_name, industry, csm_owner, plan_tier, arr_usd,
               risk_band, risk_score, risk_reasons, core_events, active_users,
               active_days, seat_utilisation, feature_areas_adopted,
               consecutive_zero_usage_months, days_to_renewal
        FROM analytics.account_health_current
        WHERE risk_band IN ('High', 'Medium')
        ORDER BY risk_score DESC, arr_usd DESC
    """,
}


def main() -> None:
    setup_logging()
    t0 = time.time()
    con = connect(read_only=True)

    for filename, query in EXPORTS.items():
        path = OUTPUTS_DIR / filename
        # COPY ... TO writes the file straight from the engine - no pandas round
        # trip, so a multi-million-row export never has to fit in memory.
        con.execute(f"COPY ({query}) TO '{path}' (HEADER, DELIMITER ',')")
        n = con.execute(f"SELECT count(*) FROM ({query})").fetchone()[0]
        log.info("  %-36s %8s rows", filename, f"{n:,}")

    con.close()
    log.info("exports written to outputs/ in %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
