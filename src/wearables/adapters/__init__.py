"""Wearable device adapters for Vitalis.

Each adapter implements the WearableAdapter ABC and handles:
- OAuth authentication and token refresh
- Fetching daily summaries, sleep, and activities from the device API
- Normalizing device-specific JSON into canonical Vitalis models
- Historical backfill with rate limiting

Available adapters:
    GarminAdapter     — Garmin Connect Health API (OAuth 1.0a)
    OuraAdapter       — Oura API v2 (OAuth2 / Personal Token)
    AppleHealthAdapter — Apple HealthKit (web import via JSON/XML export)
    WhoopAdapter      — Whoop API v1 (OAuth2)
"""

from src.wearables.adapters.garmin import GarminAdapter
from src.wearables.adapters.oura import OuraAdapter
from src.wearables.adapters.apple_health import AppleHealthAdapter
from src.wearables.adapters.whoop import WhoopAdapter

__all__ = [
    "GarminAdapter",
    "OuraAdapter",
    "AppleHealthAdapter",
    "WhoopAdapter",
]

# Registry: source_id → adapter class
ADAPTER_REGISTRY: dict[str, type] = {
    "garmin": GarminAdapter,
    "oura": OuraAdapter,
    "apple_health": AppleHealthAdapter,
    "whoop": WhoopAdapter,
}


def get_adapter(source_id: str) -> "type":
    """Return the adapter class for a given source slug.

    Args:
        source_id: e.g. 'garmin', 'oura', 'apple_health', 'whoop'

    Returns:
        The adapter class (not an instance).

    Raises:
        KeyError: If the source_id is not registered.
    """
    if source_id not in ADAPTER_REGISTRY:
        raise KeyError(
            f"No adapter registered for source '{source_id}'. "
            f"Available: {list(ADAPTER_REGISTRY)}"
        )
    return ADAPTER_REGISTRY[source_id]
