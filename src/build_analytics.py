"""Phases 5-7 - Metrics, segmentation, feature adoption and risk scoring.

Run with:  python -m src.build_analytics
"""

from __future__ import annotations

import logging
import time

from src.utils.config import SQL_DIR, sql_params
from src.utils.db import connect, run_sql_dir, table_row_counts
from src.utils.logging_config import setup_logging

log = logging.getLogger("analytics")


def main() -> None:
    setup_logging()
    t0 = time.time()
    con = connect()
    run_sql_dir(con, SQL_DIR / "analytics", sql_params())

    for t, n in sorted(table_row_counts(con, "analytics").items()):
        log.info("  %-32s %12s rows", t, f"{n:,}")

    band = con.execute("""
        SELECT risk_band, count(*), round(sum(arr_usd)) FROM analytics.account_health_current
        GROUP BY 1 ORDER BY 1
    """).fetchall()
    for b, n, arr in band:
        log.info("  risk band %-8s %4d accounts | $%s ARR", b, n, f"{int(arr or 0):,}")
    con.close()
    log.info("analytics built in %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
