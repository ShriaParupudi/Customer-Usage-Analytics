"""Load project configuration from config/config.yml.

Why this file exists: every threshold in this project (decline %, volume floor,
risk weights) is something a stakeholder might want to change. If those numbers
are scattered through the code as literals, changing one means hunting through
files and hoping you found them all. One config file, loaded once, referenced
everywhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Path(__file__) is this file. .parents[2] walks up: utils -> src -> project root.
# Deriving paths from the file's own location (rather than the current working
# directory) means the code works no matter which folder you run it from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_PATH = PROJECT_ROOT / "config" / "config.yml"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
WAREHOUSE_PATH = WAREHOUSE_DIR / "warehouse.duckdb"
SQL_DIR = PROJECT_ROOT / "sql"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Read config.yml into a plain Python dictionary."""
    path = path or CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def sql_params(cfg: dict[str, Any] | None = None) -> dict[str, str]:
    """Flatten config.yml into the $placeholders used inside the .sql files.

    Nested sections get a short prefix so the SQL stays readable:
        metrics.decline_threshold_mom      -> $decline_threshold_mom
        risk_weights.zero_usage_month      -> $rw_zero_usage_month
        risk_bands.high                    -> $band_high

    Every tunable number therefore has exactly one home - config.yml - and the
    SQL contains no magic numbers at all.
    """
    cfg = cfg or load_config()
    params: dict[str, str] = {}

    for section, prefix in (("metrics", ""), ("risk_weights", "rw_"), ("risk_bands", "band_")):
        for k, v in (cfg.get(section) or {}).items():
            if not isinstance(v, (dict, list)):
                params[f"{prefix}{k}"] = str(v)

    for k, v in (cfg.get("data_quality") or {}).items():
        if not isinstance(v, (dict, list)):
            params[k] = str(v)

    return params


def ensure_dirs() -> None:
    """Create the output folders if they don't exist yet.

    parents=True  -> create intermediate folders too
    exist_ok=True -> don't raise an error if it's already there (idempotent)
    """
    for d in (RAW_DIR, INTERIM_DIR, WAREHOUSE_DIR, OUTPUTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
