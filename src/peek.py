"""A quick look at whatever is currently in the warehouse.

Not part of the pipeline - a convenience tool for when you want to check that
something really is there without opening a SQL client.

Run with:  python -m src.peek           (all schemas)
           python -m src.peek raw       (one schema)
"""

from __future__ import annotations

import sys

from src.utils.db import connect


def main() -> None:
    wanted = sys.argv[1] if len(sys.argv) > 1 else None
    con = connect(read_only=True)

    schemas = con.execute(
        "SELECT DISTINCT table_schema FROM information_schema.tables "
        "WHERE table_schema NOT IN ('information_schema','pg_catalog') ORDER BY 1"
    ).fetchall()

    for (schema,) in schemas:
        if wanted and schema != wanted:
            continue
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = ? ORDER BY 1", [schema],
        ).fetchall()
        print(f"\n{'=' * 70}\nSCHEMA: {schema}\n{'=' * 70}")
        for (t,) in tables:
            n = con.execute(f'SELECT count(*) FROM {schema}."{t}"').fetchone()[0]
            print(f"\n-- {schema}.{t}  ({n:,} rows)")
            print(con.execute(f'SELECT * FROM {schema}."{t}" LIMIT 3').df().to_string(index=False))

    con.close()


if __name__ == "__main__":
    main()
