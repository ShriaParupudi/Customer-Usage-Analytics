"""Consistent logging for every script in the pipeline.

Why logging instead of print(): logs carry a timestamp, a severity level and the
name of the module that emitted them. When a pipeline step takes 90 seconds you
want to see where the time went, and when it fails you want to know which step
failed without guessing.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,  # replace any handler a notebook may have installed
    )
    return logging.getLogger("pipeline")
