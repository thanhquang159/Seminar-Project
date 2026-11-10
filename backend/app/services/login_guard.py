"""Persistent login throttling backed by the existing PostgreSQL audit log."""

import json
import math
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DUONG_DAN = "/admin/auth/login"
CUA_SO_PHUT = 15
SAI_TOI_DA_TAI_KHOAN = 5
SAI_TOI_DA_MOT_IP = 20
THONG_BAO_KHOA = "Quá nhiều lần đăng nhập sai, thử lại sau"

TIEN_TO_TEN = "ten:"
TIEN_TO_IP = "ip:"


def moc_cu_thoi_diem(phut: int) -> datetime:
    """Return a UTC cutoff; retained for callers/tests of the former helper."""
    return datetime.now(UTC) - timedelta(minutes=phut)


def _dimension(khoa: str) -> tuple[str, dict[str, str]]:
    if khoa.startswith(TIEN_TO_TEN):
        return "username", {"username": khoa[len(TIEN_TO_TEN) :].casefold()}
    if khoa.startswith(TIEN_TO_IP):
        return "ip", {"ip": khoa[len(TIEN_TO_IP) :]}
    raise ValueError("Unsupported login throttle key")


def _predicate(kind: str) -> str:
    if kind == "username":
        return "lower(after_data ->> 'username') = lower(:username)"
    return "ip_address = CAST(:ip AS inet)"


async def _con(db: AsyncSession, khoa: str, gioi_han: int) -> tuple[bool, int]:
    """Count recent failed-login events since the most recent success marker."""
    kind, values = _dimension(khoa)
    predicate = _predicate(kind)
    result = await db.execute(
        text(
            f"""
            SELECT COUNT(*) AS attempts, MIN(failed.created_at) AS oldest
            FROM audit_logs AS failed
            WHERE failed.action = 'auth:login_failed'
              AND failed.created_at >= now() - make_interval(mins => :window_minutes)
              AND {predicate.replace("after_data", "failed.after_data").replace("ip_address", "failed.ip_address")}
              AND failed.created_at > COALESCE(
                    (
                        SELECT MAX(succeeded.created_at)
                        FROM audit_logs AS succeeded
                        WHERE succeeded.action = 'auth:login_succeeded'
                          AND {predicate.replace("after_data", "succeeded.after_data").replace("ip_address", "succeeded.ip_address")}
                    ),
                    '-infinity'::timestamptz
              )
            """
        ),
        {**values, "window_minutes": CUA_SO_PHUT},
    )
    row = result.mappings().one()
    attempts = int(row["attempts"])
    oldest = row["oldest"]
    if attempts < gioi_han:
        return True, 0
    if oldest is None:
        return False, CUA_SO_PHUT * 60
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    wait_seconds = math.ceil(
        (oldest + timedelta(minutes=CUA_SO_PHUT) - datetime.now(UTC)).total_seconds()
    )
    return False, max(1, wait_seconds)


async def kiem_tra(db: AsyncSession, username: str, ip: str) -> None:
    """Block before bcrypt when either the username or address reached its limit."""
    ok_name, wait_name = await _con(db, TIEN_TO_TEN + username, SAI_TOI_DA_TAI_KHOAN)
    ok_ip, wait_ip = await _con(db, TIEN_TO_IP + ip, SAI_TOI_DA_MOT_IP)
    if not (ok_name and ok_ip):
        raise HTTPException(
            status_code=429,
            detail=THONG_BAO_KHOA,
            headers={"Retry-After": str(max(wait_name, wait_ip))},
        )


async def _ghi_su_kien(db: AsyncSession, action: str, username: str, ip: str) -> None:
    await db.execute(
        text(
            """
            INSERT INTO audit_logs
                (actor_user_id, action, resource_type, ip_address, after_data)
            VALUES (
                (SELECT id FROM users WHERE lower(email) = lower(:username) LIMIT 1),
                :action,
                'auth_user',
                CAST(:ip AS inet),
                CAST(:after_data AS jsonb)
            )
            """
        ),
        {
            "action": action,
            "username": username,
            "ip": ip,
            "after_data": json.dumps({"username": username.casefold()}),
        },
    )


async def ghi_nhan_that_bai(db: AsyncSession, username: str, ip: str) -> None:
    """Append one failed-attempt audit event and commit it before login returns 401."""
    await _ghi_su_kien(db, "auth:login_failed", username, ip)
    await db.commit()


async def xoa_that_bai(db: AsyncSession, username: str, ip: str) -> None:
    """Append a success marker that resets both sliding-window counters."""
    await _ghi_su_kien(db, "auth:login_succeeded", username, ip)
    await db.commit()
