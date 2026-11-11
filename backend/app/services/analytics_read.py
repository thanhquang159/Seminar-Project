"""POI view and audio-play dashboard analytics from PostgreSQL events."""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.presence import dem_online

TZ_VIETNAM = timezone(timedelta(hours=7))


async def thong_ke(db: AsyncSession, metric_date: str, so_ngay: int = 7) -> dict:
    """Return period totals, a zero-filled daily series, and top POIs."""
    ngay_cuoi = date.fromisoformat(metric_date)
    so_ngay = max(1, min(so_ngay, 30))
    ngay_dau = ngay_cuoi - timedelta(days=so_ngay - 1)
    ngay_ke_tiep = ngay_cuoi + timedelta(days=1)
    moc_dau = datetime.combine(ngay_dau, time.min, tzinfo=TZ_VIETNAM)
    moc_hom_nay = datetime.combine(ngay_cuoi, time.min, tzinfo=TZ_VIETNAM)
    moc_cuoi = datetime.combine(ngay_ke_tiep, time.min, tzinfo=TZ_VIETNAM)
    params = {
        "period_start": moc_dau,
        "period_start_date": ngay_dau,
        "metric_date": ngay_cuoi,
        "today_start": moc_hom_nay,
        "period_end": moc_cuoi,
    }

    totals_result = await db.execute(
        text(
            """
            SELECT
                COUNT(*) FILTER (WHERE event_name = 'poi_viewed') AS period_views,
                COUNT(*) FILTER (WHERE event_name = 'audio_played') AS period_audio_plays,
                COUNT(*) FILTER (
                    WHERE event_name = 'poi_viewed' AND occurred_at >= :today_start
                ) AS today_views,
                COUNT(*) FILTER (
                    WHERE event_name = 'audio_played' AND occurred_at >= :today_start
                ) AS today_audio_plays
            FROM analytics_events
            WHERE occurred_at >= :period_start AND occurred_at < :period_end
                AND event_name IN ('poi_viewed', 'audio_played')
            """
        ),
        params,
    )
    totals = dict(totals_result.mappings().one())

    daily_result = await db.execute(
        text(
            """
            WITH days AS (
                SELECT generated_day::date AS metric_day
                FROM generate_series(
                    :period_start_date,
                    :metric_date,
                    INTERVAL '1 day'
                ) AS generated(generated_day)
            ),
            event_totals AS (
                SELECT (occurred_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS metric_day,
                    COUNT(*) FILTER (WHERE event_name = 'poi_viewed') AS views,
                    COUNT(*) FILTER (WHERE event_name = 'audio_played') AS audio_plays
                FROM analytics_events
                WHERE occurred_at >= :period_start AND occurred_at < :period_end
                    AND event_name IN ('poi_viewed', 'audio_played')
                GROUP BY (occurred_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
            )
            SELECT to_char(days.metric_day, 'YYYY-MM-DD') AS metric_date,
                COALESCE(event_totals.views, 0) AS views,
                COALESCE(event_totals.audio_plays, 0) AS audio_plays
            FROM days
            LEFT JOIN event_totals USING (metric_day)
            ORDER BY days.metric_day
            """
        ),
        params,
    )
    daily = [dict(row) for row in daily_result.mappings().all()]

    poi_result = await db.execute(
        text(
            """
            SELECT event_properties->>'poi_id' AS poi_id,
                COALESCE(p.name, event_properties->>'poi_id') AS name,
                COUNT(*) FILTER (WHERE event_name = 'poi_viewed') AS views,
                COUNT(*) FILTER (WHERE event_name = 'audio_played') AS audio_plays
            FROM analytics_events AS events
            LEFT JOIN pois AS p ON p.id::text = events.event_properties->>'poi_id'
            WHERE events.occurred_at >= :period_start AND events.occurred_at < :period_end
                AND events.event_name IN ('poi_viewed', 'audio_played')
                AND NULLIF(events.event_properties->>'poi_id', '') IS NOT NULL
            GROUP BY event_properties->>'poi_id', p.name
            ORDER BY COUNT(*) DESC,
                COUNT(*) FILTER (WHERE event_name = 'poi_viewed') DESC,
                event_properties->>'poi_id'
            LIMIT 10
            """
        ),
        params,
    )
    top_pois = [dict(row) for row in poi_result.mappings().all()]
    online = await dem_online()

    return {
        "metric_date": metric_date,
        "period_start": ngay_dau.isoformat(),
        "period_days": so_ngay,
        "period_views": totals["period_views"],
        "period_audio_plays": totals["period_audio_plays"],
        "today_views": totals["today_views"],
        "today_audio_plays": totals["today_audio_plays"],
        "tracked_online_users": online,
        "daily": daily,
        "top_pois": top_pois,
    }
