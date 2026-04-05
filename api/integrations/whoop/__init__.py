"""Whoop API integration for Soma.

Provides OAuth2 authentication and data sync from Whoop's REST API.
"""

from .client import WhoopClient
from .mapping import WHOOP_TO_SOMA, transform_whoop_data
from .sync import sync_whoop_data

__all__ = [
    "WhoopClient",
    "WHOOP_TO_SOMA",
    "transform_whoop_data",
    "sync_whoop_data",
]
