"""Dashboard analytics read directly from the existing PostgreSQL event table."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.presence import dem_online


async def thong_ke(db: AsyncSession, metric_date: str, so_ngay: int = 7) -> dict:
    """Return dashboard totals and rankings without Mongo read-model collections."""
    day_start = datetime.strptime(metric_date, "%Y-%m-%d").replace(tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    period_start = day_start - timedelta(days=max(1, min(so_ngay, 30)) - 1)
    params = {"day_start": day_start, "day_end": day_end}

    totals_result = await db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_name = 'page_viewed') AS views,
                COUNT(*) FILTER (WHERE event_name = 'audio_played') AS audio_plays,
                COUNT(*) FILTER (WHERE event_name = 'search') AS searches,
                COUNT(*) FILTER (WHERE event_name = 'page_engaged') AS page_engaged,
                COUNT(DISTINCT anonymous_visitor_id) AS devices
            FROM analytics_events
            WHERE occurred_at >= :day_start AND occurred_at < :day_end
            """
        ),
        params,
    )
    totals = dict(totals_result.mappings().one())

    daily_result = await db.execute(
        text(
            """
            SELECT to_char((occurred_at AT TIME ZONE 'UTC')::date, 'YYYY-MM-DD') AS metric_date,
                COUNT(*) FILTER (WHERE event_name = 'page_viewed') AS views,
                COUNT(*) FILTER (WHERE event_name = 'audio_played') AS audio_plays,
                COUNT(*) FILTER (WHERE event_name = 'search') AS searches
            FROM analytics_events
            WHERE occurred_at >= :period_start AND occurred_at < :day_end
            GROUP BY (occurred_at AT TIME ZONE 'UTC')::date
            ORDER BY (occurred_at AT TIME ZONE 'UTC')::date
            """
        ),
        {"period_start": period_start, "day_end": day_end},
    )
    daily = [dict(row) for row in daily_result.mappings().all()]

    poi_result = await db.execute(
        text(
            """
            WITH poi_metrics AS (
                SELECT event_properties->>'poi_id' AS poi_id,
                    COUNT(*) FILTER (WHERE event_name = 'page_viewed') AS views,
                    COUNT(*) FILTER (WHERE event_name = 'audio_played') AS audio_plays
                FROM analytics_events
                WHERE occurred_at >= :day_start AND occurred_at < :day_end
                    AND event_name IN ('page_viewed', 'audio_played')
                    AND NULLIF(event_properties->>'poi_id', '') IS NOT NULL
                GROUP BY event_properties->>'poi_id'
            )
            SELECT metrics.poi_id, COALESCE(p.name, metrics.poi_id) AS name,
                metrics.views, metrics.audio_plays
            FROM poi_metrics AS metrics
            LEFT JOIN pois AS p ON p.id::text = metrics.poi_id
            ORDER BY metrics.views DESC, metrics.audio_plays DESC, metrics.poi_id
            LIMIT 5
            """
        ),
        params,
    )
    top_pois = [dict(row) for row in poi_result.mappings().all()]

    search_result = await db.execute(
        text(
            """
            SELECT LEFT(LOWER(BTRIM(event_properties->>'query')), 120) AS query,
                COUNT(*) AS count
            FROM analytics_events
            WHERE occurred_at >= :day_start AND occurred_at < :day_end
                AND event_name = 'search'
                AND NULLIF(BTRIM(event_properties->>'query'), '') IS NOT NULL
            GROUP BY LEFT(LOWER(BTRIM(event_properties->>'query')), 120)
            ORDER BY count DESC, query
            LIMIT 5
            """
        ),
        params,
    )
    top_searches = [dict(row) for row in search_result.mappings().all()]
    online = await dem_online()

    return {
        "metric_date": metric_date,
        "today_views": totals["views"],
        "audio_plays": totals["audio_plays"],
        "searches": totals["searches"],
        "page_engaged": totals["page_engaged"],
        "devices_today": totals["devices"],
        # analytics_events has no session_id; exact session counts are unsupported.
        "sessions_today": None,
        "sessions_available": False,
        "tracked_online_users": online,
        "presence_available": online is not None,
        "top_pois": top_pois,
        "top_searches": top_searches,
        "daily": daily,
    }
