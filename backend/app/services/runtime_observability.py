"""Privacy-rounded location diagnostics stored in PostgreSQL hourly buckets."""

import json
import math
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.process_rate_limit import check_rate_limit

TOI_DA_THANH_TICH_KB = 16
KICH_THUOC_TOI_DA = TOI_DA_THANH_TICH_KB * 1024
GIOI_HAN_IP_MOT_PHUT = 60
GIOI_HAN_PHIEN_MOT_PHUT = 20
DO_CHINH_XAC_TOA_DO = 3
SO_MAU_TOI_DA = 120
TEN_METRIC = "location_samples"


def kich_thuoc_than(json_bytes: bytes) -> int:
    """Return the raw request size in bytes."""
    return len(json_bytes)


def lam_sach_mau(mau: dict) -> dict | None:
    """Keep only rounded coordinates and a short outcome; discard extra fields."""
    if not isinstance(mau, dict):
        return None
    try:
        lat = round(float(mau["lat"]), DO_CHINH_XAC_TOA_DO)
        lng = round(float(mau["lng"]), DO_CHINH_XAC_TOA_DO)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    accuracy = mau.get("accuracy")
    result = {
        "lat": lat,
        "lng": lng,
        "outcome": str(mau.get("outcome", "ok"))[:20],
    }
    if isinstance(accuracy, (int, float)) and not isinstance(accuracy, bool):
        if math.isfinite(accuracy):
            result["accuracy"] = min(round(float(accuracy), 1), 100000)
    return result


async def dam_bao_index(db: AsyncSession) -> None:
    """Compatibility no-op: database indexes are provisioned outside requests."""


async def ghi_vi_tri(db: AsyncSession, mau: list[dict]) -> int:
    """Aggregate valid samples into rounded cell/outcome hourly counters."""
    bucket = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    counts: Counter[tuple[str, str]] = Counter()
    for sample in mau:
        if sample is None:
            continue
        cell = f"{sample['lat']:.{DO_CHINH_XAC_TOA_DO}f},{sample['lng']:.{DO_CHINH_XAC_TOA_DO}f}"
        counts[(cell, sample["outcome"])] += 1
    if not counts:
        return 0

    statement = text(
        """
        INSERT INTO runtime_observability_hourly AS current (
            bucket_start, metric_name, metric_dimensions, sample_count
        )
        VALUES (
            :bucket_start, :metric_name, CAST(:metric_dimensions AS jsonb), :sample_count
        )
        ON CONFLICT (bucket_start, metric_name, metric_dimensions)
        DO UPDATE SET sample_count = current.sample_count + EXCLUDED.sample_count
        """
    )
    rows = [
        {
            "bucket_start": bucket,
            "metric_name": TEN_METRIC,
            "metric_dimensions": json.dumps({"cell": cell, "outcome": outcome}),
            "sample_count": count,
        }
        for (cell, outcome), count in counts.items()
    ]
    await db.execute(statement, rows)
    await db.commit()
    return sum(counts.values())


async def kiem_tra_tan_suat(db: AsyncSession, ip: str, session_id: str) -> tuple[bool, int]:
    """Apply per-IP and per-session process-local limits without external state."""
    del db
    allowed, retry = check_rate_limit(
        f"runtime:ip:{ip}",
        GIOI_HAN_IP_MOT_PHUT,
        60,
    )
    if not allowed:
        return False, retry
    return check_rate_limit(
        f"runtime:session:{session_id}",
        GIOI_HAN_PHIEN_MOT_PHUT,
        60,
    )


async def doc_cua_so(db: AsyncSession, window: str = "24h") -> dict:
    """Read sample totals, occupied cell-hours, and outcomes for 24h or 7d."""
    hours = 24 if window == "24h" else 7 * 24
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    base_params = {"cutoff": cutoff, "metric_name": TEN_METRIC}
    totals_result = await db.execute(
        text(
            """
            SELECT COALESCE(SUM(sample_count), 0) AS samples,
                COUNT(DISTINCT (bucket_start, metric_dimensions->>'cell')) AS cells
            FROM runtime_observability_hourly
            WHERE bucket_start >= :cutoff AND metric_name = :metric_name
                AND metric_dimensions ? 'cell'
            """
        ),
        base_params,
    )
    totals = dict(totals_result.mappings().one())
    outcome_result = await db.execute(
        text(
            """
            SELECT metric_dimensions->>'outcome' AS outcome,
                SUM(sample_count) AS sample_count
            FROM runtime_observability_hourly
            WHERE bucket_start >= :cutoff AND metric_name = :metric_name
                AND metric_dimensions ? 'outcome'
            GROUP BY metric_dimensions->>'outcome'
            """
        ),
        base_params,
    )
    outcomes = {
        row["outcome"]: int(row["sample_count"])
        for row in outcome_result.mappings().all()
        if row["outcome"] is not None
    }
    return {
        "window": window,
        "hours": hours,
        "samples": int(totals["samples"]),
        "cells": int(totals["cells"]),
        "outcomes": outcomes,
    }
