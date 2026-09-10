"""Unit tests for the data-quality classification rules.

These need no database: classify() is a pure function, which is exactly why it
was pulled out of quality_checks.py into src/utils/report.py. Logic you want to
test should not be entangled with I/O.
"""

from src.utils.report import build_report, classify


def test_no_failures_is_pass():
    assert classify("FAIL", 0, 0) == "PASS"
    assert classify("WARN", 0, 0) == "PASS"


def test_warn_never_fails_the_build():
    # A WARN is tolerable by design - it must never be escalated by row count.
    assert classify("WARN", 1, 0) == "WARN"
    assert classify("WARN", 10_000_000, 0) == "WARN"


def test_known_defect_within_baseline_is_accepted():
    assert classify("FAIL", 12, 12) == "ACCEPTED"
    assert classify("FAIL", 5, 12) == "ACCEPTED"


def test_regression_beyond_baseline_fails():
    # One row worse than the state we signed off on is a regression.
    assert classify("FAIL", 13, 12) == "FAIL"


def test_fail_with_no_baseline_fails_immediately():
    assert classify("FAIL", 1, 0) == "FAIL"


def test_report_marks_regressions_and_counts_statuses():
    results = [
        dict(check_id="a", check_name="A", entity="t", severity="FAIL",
             failed_rows=0, detail="", file="a.sql", status="PASS",
             baseline=0, resolution=""),
        dict(check_id="b", check_name="B", entity="t", severity="FAIL",
             failed_rows=5, detail="", file="b.sql", status="ACCEPTED",
             baseline=10, resolution="deduped in staging"),
        dict(check_id="c", check_name="C", entity="t", severity="FAIL",
             failed_rows=99, detail="", file="c.sql", status="FAIL",
             baseline=10, resolution=""),
    ]
    md = build_report(results)
    assert "Clean: **1**" in md
    assert "Accepted: **1**" in md
    assert "Regressions: **1**" in md
    assert "Regressions (pipeline stopped)" in md
    assert "deduped in staging" in md
