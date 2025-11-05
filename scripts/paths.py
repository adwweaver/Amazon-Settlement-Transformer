"""
Path configuration for all tracking and database files.
All tracking files live in the SharePoint directory.
"""

from pathlib import Path
import os


def get_sharepoint_base() -> Path:
    """Get the base SharePoint directory path."""
    return Path(os.path.expanduser(
        r"~\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL"
    ))


def get_settlement_history_path() -> Path:
    """Get path to settlement_history.csv"""
    base = get_sharepoint_base()
    base.mkdir(parents=True, exist_ok=True)
    return base / "settlement_history.csv"


def get_zoho_tracking_path() -> Path:
    """Get path to zoho_tracking.csv"""
    base = get_sharepoint_base()
    base.mkdir(parents=True, exist_ok=True)
    return base / "zoho_tracking.csv"


def get_action_items_path() -> Path:
    """Get path to action_items.csv"""
    base = get_sharepoint_base()
    base.mkdir(parents=True, exist_ok=True)
    return base / "action_items.csv"



