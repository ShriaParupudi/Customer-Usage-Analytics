"""Tests for the metric rules that are easiest to get subtly wrong.

Each test builds a tiny fixture in an in-memory DuckDB and asserts the same
expression the production SQL uses. Hand-built fixtures are the point: with
four rows you can compute the right answer in your head, so a failure means the
LOGIC is wrong rather than the data being weird.
"""

import duckdb
import pytest


@pytest.fixture()
def con():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


def test_month_spine_creates_rows_for_zero_usage_months(con):
    """The core idea of the whole project.

    An account with no events in a month must still get a row, with 0 - otherwise
    "which accounts used nothing?" silently returns nothing.
    """
    con.execute("CREATE TABLE accounts AS SELECT 'A1' AS account_id")
    con.execute("""
        CREATE TABLE months AS
        SELECT unnest(generate_series(DATE '2026-01-01', DATE '2026-03-01', INTERVAL 1 MONTH))::DATE AS month_start
    """)
    # Usage in January and March only. February is the month that must not vanish.
    con.execute("""
        CREATE TABLE usage AS
        SELECT * FROM (VALUES ('A1', DATE '2026-01-01', 10), ('A1', DATE '2026-03-01', 5))
        AS t(account_id, month_start, events)
    """)
    rows = con.execute("""
        SELECT m.month_start, coalesce(u.events, 0) AS events
        FROM accounts a CROSS JOIN months m
        LEFT JOIN usage u ON u.account_id = a.account_id AND u.month_start = m.month_start
        ORDER BY m.month_start
    """).fetchall()

    assert len(rows) == 3, "the spine must produce one row per month regardless of usage"
    assert [r[1] for r in rows] == [10, 0, 5]

    # ...and the naive version silently loses February, which is the bug.
    naive = con.execute("SELECT count(*) FROM usage GROUP BY account_id").fetchone()[0]
    assert naive == 2


def test_mom_change_suppressed_below_volume_floor(con):
    """2 events -> 1 event is -50% and completely meaningless.

    Below the floor the change must be NULL ("not meaningful"), never 0 or a
    percentage, or the at-risk list fills with noise and gets ignored.
    """
    con.execute("""
        CREATE TABLE m AS SELECT * FROM (VALUES
            ('A1', DATE '2026-01-01', 2),    -- tiny: below the floor
            ('A1', DATE '2026-02-01', 1),
            ('B1', DATE '2026-01-01', 100),  -- real volume: above the floor
            ('B1', DATE '2026-02-01', 50)
        ) AS t(account_id, month_start, core_events)
    """)
    rows = con.execute("""
        WITH w AS (
            SELECT *, lag(core_events) OVER (PARTITION BY account_id ORDER BY month_start) AS prev
            FROM m
        )
        SELECT account_id,
               CASE WHEN prev IS NULL OR prev < 20 THEN NULL
                    ELSE round((core_events - prev) * 1.0 / prev, 4) END AS mom
        FROM w WHERE month_start = DATE '2026-02-01' ORDER BY account_id
    """).fetchall()

    assert rows[0] == ("A1", None), "below the volume floor MoM must be NULL"
    assert rows[1] == ("B1", -0.5), "above the floor a real 50% drop must be reported"


def test_eligibility_excludes_partial_months(con):
    """A month the account was barely a customer for is not a month to judge it on."""
    con.execute("""
        CREATE TABLE am AS SELECT * FROM (VALUES
            ('A1', 31), ('B1', 15), ('C1', 14), ('D1', 0)
        ) AS t(account_id, days_subscribed)
    """)
    eligible = con.execute(
        "SELECT account_id FROM am WHERE days_subscribed >= 15 ORDER BY 1"
    ).fetchall()
    assert [r[0] for r in eligible] == ["A1", "B1"], "the 15-day threshold is inclusive"


def test_deduplication_is_deterministic(con):
    """Keeping 'any' duplicate is not an answer - two runs would disagree."""
    con.execute("""
        CREATE TABLE ev AS SELECT * FROM (VALUES
            ('E1', TIMESTAMP '2026-01-01 10:00:00'),
            ('E1', TIMESTAMP '2026-01-01 10:00:00'),
            ('E2', TIMESTAMP '2026-01-02 10:00:00')
        ) AS t(event_id, loaded_at)
    """)
    sql = """
        SELECT event_id FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY loaded_at) AS rn FROM ev
        ) WHERE rn = 1 ORDER BY event_id
    """
    first = con.execute(sql).fetchall()
    second = con.execute(sql).fetchall()
    assert [r[0] for r in first] == ["E1", "E2"]
    assert first == second, "de-duplication must be reproducible across runs"


def test_overlap_join_matches_the_right_term(con):
    """Point-in-time joins use OVERLAP, not equality.

    A term that starts before the month ends and ends after the month starts
    covers that month - and must be matched exactly once.
    """
    con.execute("""
        CREATE TABLE subs AS SELECT * FROM (VALUES
            ('S1', DATE '2025-01-01', DATE '2026-01-01', 'starter'),
            ('S2', DATE '2026-01-01', DATE '2027-01-01', 'growth')
        ) AS t(subscription_id, term_start_date, term_end_date, plan_tier)
    """)
    plan = con.execute("""
        SELECT plan_tier FROM subs
        WHERE term_start_date <= DATE '2025-06-30' AND term_end_date > DATE '2025-06-01'
    """).fetchall()
    assert [p[0] for p in plan] == ["starter"], "June 2025 belongs to the first term only"

    plan2 = con.execute("""
        SELECT plan_tier FROM subs
        WHERE term_start_date <= DATE '2026-03-31' AND term_end_date > DATE '2026-03-01'
    """).fetchall()
    assert [p[0] for p in plan2] == ["growth"], "March 2026 belongs to the renewed term"


def test_impossible_values_become_null_not_zero(con):
    """seats_licensed is a denominator: 0 divides by zero, NULL reads as unknown."""
    con.execute("CREATE TABLE s AS SELECT * FROM (VALUES (10), (0), (-5)) AS t(seats)")
    rows = con.execute("""
        SELECT seats, CASE WHEN seats > 0 THEN seats END AS cleaned,
               5.0 / nullif(CASE WHEN seats > 0 THEN seats END, 0) AS utilisation
        FROM s ORDER BY seats DESC
    """).fetchall()
    assert rows[0][1] == 10
    assert rows[1][1] is None and rows[1][2] is None, "zero seats must not divide"
    assert rows[2][1] is None, "negative seats must not produce a negative rate"
