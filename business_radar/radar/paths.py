"""Every path business_radar reads or writes, resolved in one place.

Nine modules would otherwise each compute their own project root by counting `.parent` calls
back up the tree, and the first time one of them moved, its output would silently land
somewhere nobody looks. Worse for this project than for most: the thing that lands in the
wrong place is `data/radar.db`, and a second database with a different opt-out list is how a
business that unsubscribed gets mailed again.

`RADAR_HOME` lets the writable data live outside the clone, which matters if the repository is
a checkout that gets pulled over.
"""
from __future__ import annotations

import os
from pathlib import Path

# The project root: one level above this package.
ROOT: Path = Path(__file__).resolve().parent.parent

# Everything the application writes lives under here.
DATA_DIR: Path = Path(os.environ.get("RADAR_HOME") or (ROOT / "data")).resolve()

# --- inputs -----------------------------------------------------------------
CONFIG_PATH: Path = Path(os.environ.get("RADAR_CONFIG") or (ROOT / "config.yaml"))
CONFIG_EXAMPLE_PATH: Path = ROOT / "config.example.yaml"
CONFIG_DIR: Path = ROOT / "config"
ENV_PATH: Path = CONFIG_DIR / ".env"
ENV_EXAMPLE_PATH: Path = CONFIG_DIR / ".env.example"

# --- the database -----------------------------------------------------------
DB_PATH: Path = DATA_DIR / "radar.db"
MIGRATIONS_DIR: Path = Path(__file__).resolve().parent / "migrations"

# --- generated --------------------------------------------------------------
REPORTS_DIR: Path = DATA_DIR / "reports"        # exported self-contained HTML, CSV, XLSX
OUTBOX_DIR: Path = DATA_DIR / "outbox"          # rendered .eml files, one per approved message
CAPTURE_DIR: Path = DATA_DIR / "capture"        # raw fetched pages and raw LLM exchanges
LOGS_DIR: Path = ROOT / "logs"

# Directories the application creates on demand. DATA_DIR itself is first so a fresh clone with
# RADAR_HOME pointed somewhere new works without a mkdir by hand.
_WRITABLE: tuple[Path, ...] = (
    DATA_DIR,
    REPORTS_DIR,
    OUTBOX_DIR,
    CAPTURE_DIR,
    LOGS_DIR,
)


def ensure() -> None:
    """Create the writable directories. Safe to call repeatedly, and cheap.

    Called by load_config() and by migrate(), because both of them are the first thing that
    runs in their respective entry points and neither can do anything useful against a missing
    data directory.
    """
    for directory in _WRITABLE:
        directory.mkdir(parents=True, exist_ok=True)
