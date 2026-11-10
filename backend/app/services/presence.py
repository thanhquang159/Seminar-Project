"""Consent-gated, process-local anonymous presence and origin checks.

Presence is intentionally volatile and single-process: this avoids requiring
Redis for the current API deployment. Counts reset at restart and are not
shared between multiple worker processes.
"""

import time

from app.core.config import settings

KHOA_ZSET = "quan4:analytics:presence"  # compatibility name; no Redis key is used
CUA_SO_GIOY = 300
TTL_GIOY = CUA_SO_GIOY * 2

_active_devices: dict[str, float] = {}


def _prune(now: float) -> None:
    cutoff = now - CUA_SO_GIOY
    for anonymous_id, seen_at in list(_active_devices.items()):
        if seen_at <= cutoff:
            _active_devices.pop(anonymous_id, None)


async def heartbeat(anonymous_id: str) -> int | None:
    """Refresh a consented device in the five-minute in-process window."""
    if not anonymous_id:
        return None
    now = time.monotonic()
    _prune(now)
    _active_devices[anonymous_id] = now
    return len(_active_devices)


async def dem_online() -> int | None:
    """Count active consented devices in this process."""
    _prune(time.monotonic())
    return len(_active_devices)


async def xoa_het() -> None:
    """Clear volatile presence state for tests or administrative reset."""
    _active_devices.clear()


async def xoa_thiet_bi(anonymous_id: str) -> None:
    """Remove only the device whose consent was withdrawn."""
    if anonymous_id:
        _active_devices.pop(anonymous_id, None)


async def origin_duoc_phep(origin: str | None) -> bool:
    """Accept only configured origins, using the same list as CORS."""
    if not origin:
        return True
    return origin in settings.CORS_ORIGINS
