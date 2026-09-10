"""Phase 4b - Build the dimensional model: the month spine, dims and facts.

Run with:  python -m src.build_marts
"""

from __future__ import annotations

import logging
import sys
import time

from src.utils.config import SQL_DIR, sql_params
from src.utils.db import connect, run_sql_dir, table_row_counts
from src.utils.logging_config import setup_logging

log = logging.getLogger("marts")


def main() -> None:
    setup_logging()
    t0 = time.time()
    con = connect()
    run_sql_dir(con, SQL_DIR / "marts", sql_params())

    for t, n in sorted(table_row_counts(con, "marts").items()):
        log.info("  %-22s %12s rows", t, f"{n:,}")

    # GRAIN ASSERTION. fct_account_month must be exactly one row per account per
    # month. If a join ever fans out, every downstream metric silently
    # double-counts - so we assert the grain instead of hoping.
    accounts, months, rows = con.execute("""
        SELECT (SELECT count(*) FROM marts.dim_account),
               (SELECT count(*) FROM marts.dim_month),
               (SELECT count(*) FROM marts.fct_account_month)
    """).fetchone()
    dupes = con.execute("""
        SELECT count(*) FROM (
            SELECT account_id, month_start FROM marts.fct_account_month
            GROUP BY 1, 2 HAVING count(*) > 1
        )
    """).fetchone()[0]
    con.close()

    if rows != accounts * months or dupes:
        log.error("GRAIN VIOLATION: expected %d x %d = %d rows, got %d (%d duplicate keys)",
                  accounts, months, accounts * months, rows, dupes)
        sys.exit(1)

    log.info("grain assertion passed: %d accounts x %d months = %s rows, no duplicates",
             accounts, months, f"{rows:,}")
    log.info("marts built in %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()
