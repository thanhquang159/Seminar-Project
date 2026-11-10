"""Consent-gated analytics writes against the existing PostgreSQL schema."""

import base64
import hashlib
import hmac
import json
import math
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.process_rate_limit import check_rate_limit

# Only accept events from this allowlist; unknown names do not create metrics.
SU_KIEN_CHO_PHEP = (
    "session_started",
    "page_viewed",
    "page_engaged",
    "search",
    "audio_played",
    "poi_viewed",
)

DAU_BOT = ("bot", "crawler", "spider", "headless", "curl", "wget", "python-requests", "postman")
KHOA_CAM = (
    "email",
    "phone",
    "cccd",
    "cmnd",
    "password",
    "matkhau",
    "token",
    "authorization",
    "cookie",
    "ip",
    "address",
    "ten_dang_nhap",
)

TOI_DA_THUOC_TINH = 8
TOI_DA_DO_DAI_CHUOI = 200
LECH_GIOI_HAN_GIAY = 86400
GIOI_HAN_ANON = 60
GIOI_HAN_IP = 600
CUA_SO_PHUT = 10
HAN_RECEIPT_NGAY = 365
POLICY_VERSION = "1"

MA_ANON = re.compile(r"^[a-zA-Z0-9_-]{16,64}$")


def hop_le(anonymous_id: str) -> bool:
    """anonymous_id is a random client key, not an account identifier."""
    return bool(MA_ANON.match(anonymous_id or ""))


def _bimat() -> bytes:
    return settings.JWT_SECRET.encode()


def _noi_dung_receipt(anonymous_id: str, het_han: int) -> bytes:
    return f"{anonymous_id}|{het_han}".encode()


def lam_receipt(anonymous_id: str) -> str:
    """Issue a one-year HMAC receipt proving that consent was granted."""
    het_han = int((datetime.now(UTC) + timedelta(days=HAN_RECEIPT_NGAY)).timestamp())
    chu_ky = hmac.new(
        _bimat(), _noi_dung_receipt(anonymous_id, het_han), hashlib.sha256
    ).hexdigest()
    raw = base64.urlsafe_b64encode(f"{anonymous_id}|{het_han}|{chu_ky}".encode()).decode()
    return raw.rstrip("=")


def doc_receipt(receipt: str) -> dict | None:
    """Validate receipt signature and expiry; malformed or expired receipts return None."""
    if not receipt or len(receipt) > 512:
        return None
    try:
        phuc = base64.urlsafe_b64decode(receipt + "=" * (-len(receipt) % 4)).decode()
        anonymous_id, het_han, chu_ky = phuc.split("|")
        het_han = int(het_han)
    except (ValueError, UnicodeDecodeError):
        return None
    ky_dung = hmac.new(
        _bimat(), _noi_dung_receipt(anonymous_id, het_han), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(ky_dung, chu_ky):
        return None
    if het_han < datetime.now(UTC).timestamp() or not hop_le(anonymous_id):
        return None
    return {"anonymous_id": anonymous_id, "het_han": het_han}


def ly_do_loc(user_agent: str) -> str | None:
    """Filter crawlers before they can consume rate-limit or consent work."""
    ua = (user_agent or "").lower()
    for dau in DAU_BOT:
        if dau in ua:
            return f"bot:{dau}"
    return None


def chuan_hoa_thoi_gian(gia_tri: object) -> datetime:
    """Normalize client milliseconds; timestamps more than one day away use server time."""
    if not isinstance(gia_tri, (int, float)) or isinstance(gia_tri, bool):
        return datetime.now(UTC)
    try:
        moc = datetime.fromtimestamp(gia_tri / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return datetime.now(UTC)
    if abs((datetime.now(UTC) - moc).total_seconds()) > LECH_GIOI_HAN_GIAY:
        return datetime.now(UTC)
    return moc


def lam_sach(thuoc_tinh: object) -> dict:
    """Keep only short primitive values and drop identifying property names."""
    if not isinstance(thuoc_tinh, dict):
        return {}
    ket_qua: dict = {}
    for khoa, gia_tri in list(thuoc_tinh.items())[:TOI_DA_THUOC_TINH]:
        ten = str(khoa)[:60]
        if ten.lower() in KHOA_CAM:
            continue
        if isinstance(gia_tri, bool) or isinstance(gia_tri, int):
            ket_qua[ten] = gia_tri
        elif isinstance(gia_tri, float) and math.isfinite(gia_tri):
            ket_qua[ten] = gia_tri
        elif isinstance(gia_tri, str):
            ket_qua[ten] = gia_tri[:TOI_DA_DO_DAI_CHUOI]
    return ket_qua


def khoa_su_kien(metric_date: str, metric_hour: int) -> str:
    """Compatibility helper for callers that still construct hourly labels."""
    return f"{metric_date}T{metric_hour:02d}"


async def dam_bao_index(db: AsyncSession) -> None:
    """Compatibility no-op: schema/index management is external to this API."""


async def dat_consent(db: AsyncSession, anonymous_id: str, granted: bool) -> None:
    """Persist consent; withdrawn consent maps to the schema's ``withdrawn`` value."""
    status = "granted" if granted else "withdrawn"
    now = datetime.now(UTC)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:visitor, 0))"),
        {"visitor": anonymous_id},
    )
    existing = await db.execute(
        text(
            "SELECT id FROM analytics_consents "
            "WHERE anonymous_visitor_id = :visitor "
            "ORDER BY updated_at DESC, created_at DESC, id DESC "
            "LIMIT 1 FOR UPDATE"
        ),
        {"visitor": anonymous_id},
    )
    consent = existing.mappings().first()
    if consent:
        await db.execute(
            text(
                "UPDATE analytics_consents SET consent_status = :status, "
                "policy_version = :policy_version, "
                "consented_at = CASE WHEN :granted THEN COALESCE("
                "consented_at, CAST(:now AS TIMESTAMPTZ)) "
                "ELSE consented_at END, "
                "withdrawn_at = CASE WHEN :granted THEN NULL "
                "ELSE CAST(:now AS TIMESTAMPTZ) END, "
                "updated_at = :now WHERE id = :consent_id"
            ),
            {
                "status": status,
                "policy_version": POLICY_VERSION,
                "granted": granted,
                "now": now,
                "consent_id": consent["id"],
            },
        )
    else:
        await db.execute(
            text(
                "INSERT INTO analytics_consents "
                "(anonymous_visitor_id, consent_status, policy_version, "
                "consented_at, withdrawn_at) "
                "VALUES (:visitor, :status, :policy_version, "
                "CASE WHEN :granted THEN CAST(:now AS TIMESTAMPTZ) ELSE NULL END, "
                "CASE WHEN :granted THEN NULL ELSE CAST(:now AS TIMESTAMPTZ) END)"
            ),
            {
                "visitor": anonymous_id,
                "status": status,
                "policy_version": POLICY_VERSION,
                "granted": granted,
                "now": now,
            },
        )
    await db.commit()


async def trang_thai_consent(db: AsyncSession, anonymous_id: str) -> str:
    """Return granted/revoked/unknown using the latest consent record."""
    result = await db.execute(
        text(
            "SELECT consent_status FROM analytics_consents "
            "WHERE anonymous_visitor_id = :visitor "
            "ORDER BY updated_at DESC, created_at DESC, id DESC LIMIT 1"
        ),
        {"visitor": anonymous_id},
    )
    consent = result.mappings().first()
    if not consent:
        return "unknown"
    status = consent["consent_status"]
    return "granted" if status == "granted" else "revoked"


async def co_consent(db: AsyncSession, anonymous_id: str) -> bool:
    return await trang_thai_consent(db, anonymous_id) == "granted"


async def ghi_su_kien(
    db: AsyncSession,
    anonymous_id: str,
    session_id: str,
    ten: str,
    thuoc_tinh: object,
    thoi_diem: object,
) -> bool:
    """Insert a filtered event only while a matching granted consent still exists.

    The existing event schema deliberately has no session-id column, so session
    counts cannot be reconstructed from PostgreSQL without a schema change.
    """
    del session_id  # accepted for API compatibility; not persisted by this schema
    luc = chuan_hoa_thoi_gian(thoi_diem)
    result = await db.execute(
        text(
            "INSERT INTO analytics_events "
            "(consent_id, anonymous_visitor_id, event_name, event_properties, occurred_at) "
            "SELECT c.id, c.anonymous_visitor_id, :event_name, "
            "CAST(:event_properties AS jsonb), :occurred_at "
            "FROM analytics_consents AS c "
            "WHERE c.anonymous_visitor_id = :visitor AND c.consent_status = 'granted' "
            "ORDER BY c.updated_at DESC, c.created_at DESC, c.id DESC LIMIT 1 "
            "RETURNING id"
        ),
        {
            "visitor": anonymous_id,
            "event_name": ten,
            "event_properties": json.dumps(lam_sach(thuoc_tinh), ensure_ascii=False),
            "occurred_at": luc,
        },
    )
    inserted = result.mappings().first()
    if inserted:
        await db.commit()
        return True
    await db.rollback()
    return False


async def cho_phep_luong(db: AsyncSession, anonymous_id: str, ip: str) -> tuple[bool, int]:
    """Apply anonymous-device and IP limits in this process without Redis/Mongo."""
    del db  # no persistent rate-limit table is part of the existing schema
    allowed, retry = check_rate_limit(
        f"analytics:anonymous:{anonymous_id}",
        GIOI_HAN_ANON,
        CUA_SO_PHUT * 60,
    )
    if not allowed:
        return False, retry
    return check_rate_limit(
        f"analytics:ip:{ip}",
        GIOI_HAN_IP,
        CUA_SO_PHUT * 60,
    )


async def xep_viec_tong_hop(db: AsyncSession, metric_date: str) -> None:
    """Compatibility no-op: dashboard metrics are queried directly from events."""
    del db, metric_date
