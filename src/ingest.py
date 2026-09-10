"""Phase 2 - Load the raw files into DuckDB and reconcile the row counts.

Run with:  python -m src.ingest
"""

from __future__ import annotations

import gzip
import logging
import sys
import time
from pathlib import Path

from src.utils.config import RAW_DIR, SQL_DIR, WAREHOUSE_PATH
from src.utils.db import connect, run_sql_dir, table_row_counts
from src.utils.logging_config import setup_logging

log = logging.getLogger("ingest")

# Which file feeds which table. Used for reconciliation.
FILE_TO_TABLE = {
    "accounts.csv": "accounts",
    "users.csv": "users",
    "subscriptions.csv": "subscriptions",
    "support_tickets.csv": "support_tickets",
    "feature_catalog.csv": "feature_catalog",
    "product_usage_events.csv.gz": "product_usage_events",
}


def count_file_rows(path: Path) -> int:
    """Count data rows in a CSV (or gzipped CSV), excluding the header.

    Deliberately counts the FILE, not the table. Comparing a number derived from
    the source against a number derived from the database is what makes the
    reconciliation meaningful - if we counted the table twice we would only
    prove that DuckDB can count.
    """
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as fh:
        return max(0, sum(1 for _ in fh) - 1)


def main() -> None:
    setup_logging()
    t0 = time.time()

    missing = [f for f in FILE_TO_TABLE if not (RAW_DIR / f).exists()]
    if missing:
        log.error("missing raw files: %s", ", ".join(missing))
        log.error("run `python -m src.generate_data` first")
        sys.exit(1)

    con = connect()
    run_sql_dir(con, SQL_DIR / "ingest")

    # ---- reconciliation -------------------------------------------------
    # Silent row loss is one of the nastiest failure modes in data work,
    # because everything still "runs". A malformed quote in a CSV can drop
    # thousands of rows without raising anything. Counting both sides and
    # comparing is cheap insurance, so we do it on every single load.
    log.info("reconciling file row counts against loaded tables ...")
    table_counts = table_row_counts(con, "raw")
    ok = True
    for fname, table in FILE_TO_TABLE.items():
        file_rows = count_file_rows(RAW_DIR / fname)
        db_rows = table_counts.get(table, -1)
        status = "OK" if file_rows == db_rows else "MISMATCH"
        if file_rows != db_rows:
            ok = False
        log.info(
            "  %-28s file=%9s  table=%9s  %s",
            table, f"{file_rows:,}", f"{db_rows:,}", status,
        )

    con.close()

    if not ok:
        log.error("row count reconciliation FAILED - rows were lost or added during load")
        sys.exit(1)

    log.info("ingestion complete in %.1fs -> %s", time.time() - t0, WAREHOUSE_PATH)


if __name__ == "__main__":
    main()
