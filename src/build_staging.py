"""Phase 4a - Build the staging layer (cleaned, typed, deduplicated).

Run with:  python -m src.build_staging
"""

from __future__ import annotations

import logging
import time

from src.utils.config import SQL_DIR, sql_params
from src.utils.db import connect, run_sql_dir, table_row_counts
from src.utils.logging_config import setup_logging

log = logging.getLogger("staging")


def main() -> None:
    setup_logging()
    t0 = time.time()
    con = connect()
    run_sql_dir(con, SQL_DIR / "staging", sql_params())

    raw_counts = table_row_counts(con, "raw")
    stg_counts = table_row_counts(con, "staging")
    log.info("row counts raw -> staging (drops are intentional; see dq_report.md):")
    for stg_table, n in sorted(stg_counts.items()):
        src = stg_table.replace("stg_", "")
        src = "product_usage_events" if src == "usage_events" else src
        before = raw_counts.get(src)
        if before:
            log.info("  %-24s %10s -> %10s  (%+.2f%%)", src, f"{before:,}", f"{n:,}",
                     100 * (n - before) / before)
    con.close()
    log.info("staging built in %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
