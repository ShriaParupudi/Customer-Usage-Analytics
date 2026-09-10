"""DuckDB connection helpers and a SQL-file runner.

Why transformations live in .sql files rather than inside Python strings:
  - they are reviewable in a pull request as SQL, not as escaped text
  - they can be run by hand in the DuckDB CLI while debugging
  - it is the analytics-engineering convention (and how dbt works)

Python's job here is orchestration - open a connection, run files in order,
report what happened. It is deliberately thin.
"""

from __future__ import annotations

import logging
from pathlib import Path
from string import Template

import duckdb

from src.utils.config import PROJECT_ROOT, WAREHOUSE_PATH, ensure_dirs

log = logging.getLogger("db")


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the warehouse. Creates the file on first use.

    All SQL in this project uses paths relative to the project root (e.g.
    'data/raw/accounts.csv'), so we make sure the process is anchored there.
    """
    ensure_dirs()
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=read_only)
    # Anchor relative file paths to the project root regardless of where the
    # user launched python from.
    con.execute(f"SET file_search_path = '{PROJECT_ROOT}'")
    return con


def run_sql_file(
    con: duckdb.DuckDBPyConnection, path: Path, params: dict[str, str] | None = None
) -> None:
    """Execute every statement in one .sql file, substituting $placeholders.

    safe_substitute leaves unknown $tokens alone instead of raising, so a file
    that uses no parameters still runs unchanged.
    """
    sql = path.read_text(encoding="utf-8")
    if params:
        sql = Template(sql).safe_substitute(params)
    log.info("running %s", path.relative_to(PROJECT_ROOT))
    con.execute(sql)


def run_sql_dir(
    con: duckdb.DuckDBPyConnection, folder: Path, params: dict[str, str] | None = None
) -> list[Path]:
    """Execute every .sql file in a folder, in filename order.

    Filename prefixes (01_, 02_, ...) are this project's dependency ordering.
    It is crude compared to dbt's ref() graph, but it is explicit and
    inspectable - see docs/limitations.md.
    """
    files = sorted(folder.glob("*.sql"))
    if not files:
        raise FileNotFoundError(f"no .sql files found in {folder}")
    for f in files:
        run_sql_file(con, f, params)
    return files


def table_row_counts(con: duckdb.DuckDBPyConnection, schema: str) -> dict[str, int]:
    """Row count for every table in a schema - used for reconciliation."""
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = ? ORDER BY table_name",
        [schema],
    ).fetchall()
    return {
        t[0]: con.execute(f'SELECT count(*) FROM {schema}."{t[0]}"').fetchone()[0]
        for t in tables
    }
