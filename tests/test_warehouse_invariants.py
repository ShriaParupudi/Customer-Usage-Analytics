"""Integration tests against the built warehouse.

Unit tests prove the logic patterns are right; these prove the ACTUAL tables
came out right. They are skipped when the warehouse has not been built, so a
fresh clone can still run `pytest` without a 2-minute pipeline run first.
"""

import duckdb
import pytest

from src.utils.config import WAREHOUSE_PATH

pytestmark = pytest.mark.skipif(
    not WAREHOUSE_PATH.exists(), reason="warehouse not built - run `make all` first"
)


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    yield c
    c.close()


def test_fct_account_month_grain_is_exactly_one_row_per_account_month(con):
    """The grain assertion. If a join ever fans out, every metric double-counts."""
    dupes = con.execute("""
        SELECT count(*) FROM (
            SELECT account_id, month_start FROM marts.fct_account_month
            GROUP BY 1, 2 HAVING count(*) > 1
        )
    """).fetchone()[0]
    assert dupes == 0

    accounts, months, rows = con.execute("""
        SELECT (SELECT count(*) FROM marts.dim_account),
               (SELECT count(*) FROM marts.dim_month),
               (SELECT count(*) FROM marts.fct_account_month)
    """).fetchone()
    assert rows == accounts * months, "the spine must be complete: accounts x months"


def test_no_internal_test_accounts_survive_staging(con):
    """Excluded once, at the boundary, so no downstream query can forget."""
    leaked = con.execute("""
        SELECT count(*) FROM staging.stg_accounts a
        JOIN raw.accounts r ON a.account_id = r.account_id
        WHERE r.is_internal_test
    """).fetchone()[0]
    assert leaked == 0


def test_zero_usage_months_exist_as_rows(con):
    """The finding the whole spine exists to make visible."""
    n = con.execute("""
        SELECT count(*) FROM marts.fct_account_month
        WHERE is_eligible_month AND core_events = 0
    """).fetchone()[0]
    assert n > 0, "zero-usage account-months must be rows, not absences"


def test_no_events_survive_before_signup_or_in_the_future(con):
    bad = con.execute("""
        SELECT count(*) FROM staging.stg_usage_events e
        JOIN staging.stg_accounts a ON e.account_id = a.account_id
        WHERE e.event_ts < a.signup_date OR e.event_ts > current_timestamp
    """).fetchone()[0]
    assert bad == 0


def test_no_duplicate_event_ids_survive_staging(con):
    dupes = con.execute("""
        SELECT count(*) FROM (
            SELECT event_id FROM staging.stg_usage_events GROUP BY 1 HAVING count(*) > 1
        )
    """).fetchone()[0]
    assert dupes == 0


def test_country_values_are_standardised(con):
    """'US' / 'USA' / 'u.s.a.' must have collapsed into one canonical value."""
    variants = con.execute("""
        SELECT count(*) FROM staging.stg_accounts
        WHERE country IN ('US', 'USA', 'u.s.a.', 'UK')
    """).fetchone()[0]
    assert variants == 0


def test_mom_change_is_null_below_the_volume_floor(con):
    """No percentage change may be reported on a base too small to mean anything."""
    violations = con.execute("""
        SELECT count(*) FROM analytics.account_month_metrics
        WHERE mom_change_pct IS NOT NULL AND prev_core_events < 20
    """).fetchone()[0]
    assert violations == 0


def test_seat_utilisation_is_never_negative_or_infinite(con):
    bad = con.execute("""
        SELECT count(*) FROM analytics.account_health_monthly
        WHERE seat_utilisation < 0 OR NOT isfinite(seat_utilisation)
    """).fetchone()[0]
    assert bad == 0


def test_risk_bands_match_their_configured_thresholds(con):
    """The band label must always agree with the score that produced it."""
    from src.utils.config import load_config
    cfg = load_config()
    hi, med = cfg["risk_bands"]["high"], cfg["risk_bands"]["medium"]
    bad = con.execute(f"""
        SELECT count(*) FROM analytics.account_health_monthly
        WHERE (risk_score >= {hi} AND risk_band <> 'High')
           OR (risk_score >= {med} AND risk_score < {hi} AND risk_band <> 'Medium')
           OR (risk_score < {med} AND risk_band <> 'Low')
    """).fetchone()[0]
    assert bad == 0


def test_every_high_risk_account_has_a_stated_reason(con):
    """A risk score with no explanation is a report nobody acts on."""
    unexplained = con.execute("""
        SELECT count(*) FROM analytics.account_health_current
        WHERE risk_band = 'High' AND (risk_reasons IS NULL OR risk_reasons = '')
    """).fetchone()[0]
    assert unexplained == 0


def test_current_table_holds_only_the_latest_month_per_account(con):
    dupes = con.execute("""
        SELECT count(*) FROM (
            SELECT account_id FROM analytics.account_health_current
            GROUP BY 1 HAVING count(*) > 1
        )
    """).fetchone()[0]
    assert dupes == 0
