"""PostgreSQL-backed public POI router export."""

from collections.abc import Mapping

from app.api.pois import router as router


def doi_poi(doc: Mapping[str, object]) -> dict:
    """Map a PostgreSQL POI row to the legacy write-route response shape."""
    return {
        "id": str(doc["id"]),
        "name": doc["name"],
        "description": doc.get("description") or "",
        "lat": float(doc["lat"]),
        "lng": float(doc["lng"]),
        "trigger_radius": doc.get("trigger_radius", 30),
        "audio_priority": doc.get("audio_priority", 0),
    }
