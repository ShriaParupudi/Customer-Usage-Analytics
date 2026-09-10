"""Phase 3 - The data quality gate.

Runs every check in sql/quality/, writes outputs/dq_report.md, and exits with a
non-zero status if any check has REGRESSED beyond its documented baseline.

Two design points worth defending in an interview:

1. Checks have SEVERITIES.
     FAIL - stop the pipeline. Duplicate keys, orphan foreign keys, impossible
            values. Continuing would produce numbers that are wrong rather than
            merely incomplete.
     WARN - log it and continue. A null rate above target, a few cross-field
            mismatches. Tolerable, tracked, resolved in staging.
   "Everything is FAIL" is as naive as "clean it silently". The first means the
   pipeline never runs; the second means nobody learns the source is broken.

2. Known defects have BASELINES, so the gate detects REGRESSION.
   A gate that fails every single run gets switched off, and then it protects
   nothing. Each known defect is recorded in config.yml with a row-count ceiling
   and a written resolution. The build breaks when the data gets *worse* than
   the state we knowingly signed off on.

Run with:  python -m src.quality_checks
"""

from __future__ import annotations

import logging
import sys
import time
from string import Template

from src.utils.config import OUTPUTS_DIR, PROJECT_ROOT, SQL_DIR, load_config
from src.utils.db import connect
from src.utils.logging_config import setup_logging
from src.utils.report import build_report, classify

log = logging.getLogger("quality")


def main() -> None:
    setup_logging()
    t0 = time.time()
    cfg = load_config()

    dq_cfg = cfg["data_quality"]
    accepted_cfg = dq_cfg.get("accepted_exceptions") or {}
    # Scalar thresholds are substituted into the SQL as $placeholders, so
    # config.yml stays the single source of truth for every tunable number.
    params = {k: str(v) for k, v in dq_cfg.items() if not isinstance(v, dict)}

    con = connect()
    files = sorted((SQL_DIR / "quality").glob("*.sql"))
    if not files:
        log.error("no check files found in sql/quality/")
        sys.exit(1)

    results = []
    for path in files:
        # safe_substitute leaves unknown $tokens alone rather than raising, so a
        # check that takes no parameters still works.
        sql = Template(path.read_text(encoding="utf-8")).safe_substitute(params)
        check_id, name, entity, severity, failed, detail = con.execute(sql).fetchone()
        failed = int(failed or 0)

        exc = accepted_cfg.get(check_id) or {}
        baseline = int(exc.get("max_rows", 0))
        status = classify(severity, failed, baseline)

        results.append({
            "check_id": check_id, "check_name": name, "entity": entity,
            "severity": severity, "failed_rows": failed, "detail": detail or "",
            "file": path.name, "status": status, "baseline": baseline,
            "resolution": exc.get("resolution", ""),
        })
        log.info("  %-8s %-32s %10s rows", status, check_id, f"{failed:,}")

    con.close()

    report_path = OUTPUTS_DIR / "dq_report.md"
    report_path.write_text(build_report(results), encoding="utf-8")
    log.info("report written to %s (%.1fs)", report_path.relative_to(PROJECT_ROOT), time.time() - t0)

    fails = [r for r in results if r["status"] == "FAIL"]
    if fails:
        log.error("=" * 72)
        log.error("DATA QUALITY GATE: %d check(s) REGRESSED beyond baseline", len(fails))
        for r in fails:
            log.error(
                "  %-30s %10s rows (baseline %s)",
                r["check_id"], f"{r['failed_rows']:,}", f"{r['baseline']:,}",
            )
        log.error("Pipeline stopped. This is the gate doing its job, not a crash.")
        log.error("See outputs/dq_report.md for detail.")
        log.error("=" * 72)
        sys.exit(1)

    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "ACCEPTED", "WARN")}
    log.info(
        "data quality gate PASSED | %d clean, %d accepted, %d warnings",
        counts["PASS"], counts["ACCEPTED"], counts["WARN"],
    )


if __name__ == "__main__":
    main()
