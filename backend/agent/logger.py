"""
Centralized logging configuration for the agent module.

Levels:
  - INFO  → General flow: agent lifecycle, tool routing, report generation
  - DEBUG → Raw LLM tokens, full payloads, intermediate data snapshots
  - ERROR → Tool execution failures, DB errors, file I/O errors
"""

import logging
import os
import sys

LOG_LEVEL = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()

# ── Configure root logger ONCE to avoid duplicate handlers ────────────────────
_root_configured = False


def _configure_root():
    global _root_configured
    if _root_configured:
        return
    _root_configured = True

    root = logging.getLogger()
    # Remove any pre-existing handlers (prevents duplicates from basicConfig)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger with a consistent format.
    Call once per module:  logger = get_logger(__name__)
    """
    _configure_root()
    return logging.getLogger(name)
