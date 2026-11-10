"""Authentication helpers backed by PostgreSQL users, roles and auth_sessions."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.postgres import AsyncSessionLocal, get_db

ACCESS_PHUT = 30
REFRESH_NGAY = 7
SO_PHIEN_MAC_DINH = 1
DbSession = Depends(get_db)


def bam_mat_khau(mat_khau: str) -> str:
    """Hash a password with bcrypt and a random salt."""
    return bcrypt.hashpw(mat_khau.encode(), bcrypt.gensalt()).decode()


def dung_mat_khau(mat_khau: str, bam: str) -> bool:
    """Compare a password safely; malformed stored hashes fail closed."""
    try:
        return bcrypt.checkpw(mat_khau.encode(), bam.encode())
    except (ValueError, TypeError):
        return False


def tao_token(
    username: str,
    role: str,
    loai: str,
    quyen: list[str] | None = None,
    so_phien: int = 1,
    session_id: UUID | str | None = None,
) -> str:
    """Create an access or refresh JWT; ``session_id`` binds it to auth_sessions."""
    if loai not in {"access", "refresh"}:
        raise ValueError("Unsupported token type")
    lifetime = timedelta(minutes=ACCESS_PHUT) if loai == "access" else timedelta(days=REFRESH_NGAY)
    secret = settings.JWT_SECRET if loai == "access" else settings.REFRESH_TOKEN_SECRET
    claims = {
        "sub": username,
        "role": role,
        "permissions": quyen or [],
        "type": loai,
        "sv": so_phien,
        "exp": datetime.now(UTC) + lifetime,
    }
    if session_id is not None:
        claims["sid"] = str(session_id)
    return jwt.encode(claims, secret, algorithm="HS256")


def doc_token(token: str, loai: str) -> dict:
    """Validate signature, expiration and token type without leaking details."""
    secret = settings.JWT_SECRET if loai == "access" else settings.REFRESH_TOKEN_SECRET
    try:
        data = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ") from None
    if data.get("type") != loai:
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    return data


def kiem_tra_phien(data: dict, user: dict) -> None:
    """Reject revoked legacy versions and tokens whose role no longer matches."""
    version = user.get("phi_en_ver")
    if version is not None and data.get("sv") != version:
        raise HTTPException(status_code=401, detail="Phiên không còn hiệu lực")
    if data.get("role") != user.get("role", "user"):
        raise HTTPException(status_code=401, detail="Phiên không còn hiệu lực")


def _role_ung_dung(role_code: str) -> str:
    """Translate persisted PostgreSQL role codes to the API's stable role names."""
    return {
        "admin": "admin",
        "owner": "poi_owner",
    }.get(role_code.lower(), role_code.lower())


async def _lay_user(db: AsyncSession, username: str) -> dict | None:
    result = await db.execute(
        text(
            """
            SELECT u.id, u.email, u.password_hash, u.account_status,
                   u.owner_verified_at, COALESCE(r.code, 'user') AS role
            FROM users AS u
            LEFT JOIN user_roles AS ur ON ur.user_id = u.id
            LEFT JOIN roles AS r ON r.id = ur.role_id
            WHERE lower(u.email) = lower(:username)
            ORDER BY r.code NULLS LAST
            LIMIT 1
            """
        ),
        {"username": username},
    )
    row = result.mappings().first()
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["email"],
        "email": row["email"],
        "password_hash": row["password_hash"],
        "account_status": row["account_status"],
        "role": _role_ung_dung(row["role"]),
        "is_poi_owner_verified": row["owner_verified_at"] is not None,
    }


async def lay_user_theo_ten(username: str, db: AsyncSession | None = None) -> dict | None:
    """Look up the legacy username against the PostgreSQL users.email field.

    The optional session preserves the old one-argument helper for unported
    callers while routes in this migration pass their request-scoped session.
    """
    if db is not None:
        return await _lay_user(db, username)
    async with AsyncSessionLocal() as session:
        return await _lay_user(session, username)


async def quyen_hien_tai(
    username: str,
    role: str,
    token_quyen: list[str],
    db: AsyncSession | None = None,
) -> list[str]:
    """Read current grants from PostgreSQL; token permissions are not trusted."""
    from app.permissions import quyen_cua_user

    if db is None:
        if token_quyen:
            return token_quyen
        async with AsyncSessionLocal() as session:
            return await quyen_cua_user(session, username)
    return await quyen_cua_user(db, username)


def _session_uuid(data: dict) -> UUID:
    try:
        return UUID(str(data["sid"]))
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ") from None


async def _kiem_tra_auth_session(
    db: AsyncSession, data: dict, user: dict, loai: str, token: str
) -> UUID:
    session_id = _session_uuid(data)
    result = await db.execute(
        text(
            """
            SELECT refresh_token_hash
            FROM auth_sessions
            WHERE id = CAST(:session_id AS uuid)
              AND user_id = CAST(:user_id AS uuid)
              AND revoked_at IS NULL
              AND expires_at > now()
            """
        ),
        {"session_id": str(session_id), "user_id": str(user["id"])},
    )
    stored_hash = result.scalar_one_or_none()
    if stored_hash is None:
        raise HTTPException(status_code=401, detail="Phiên không còn hiệu lực")
    if loai == "refresh":
        supplied_hash = hashlib.sha256(token.encode()).hexdigest()
        if not hmac.compare_digest(str(stored_hash), supplied_hash):
            raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    return session_id


async def tao_auth_session(
    db: AsyncSession,
    user_id: UUID | str,
    refresh_token: str,
    ip_address: str | None,
    session_id: UUID | None = None,
) -> UUID:
    """Persist only the refresh JWT digest in the existing auth_sessions table."""
    new_session_id = session_id or uuid4()
    await db.execute(
        text(
            """
            INSERT INTO auth_sessions
                (id, user_id, refresh_token_hash, ip_address, expires_at)
            VALUES (
                CAST(:session_id AS uuid),
                CAST(:user_id AS uuid),
                :refresh_token_hash,
                CAST(:ip_address AS inet),
                :expires_at
            )
            """
        ),
        {
            "session_id": str(new_session_id),
            "user_id": str(user_id),
            "refresh_token_hash": hashlib.sha256(refresh_token.encode()).hexdigest(),
            "ip_address": ip_address,
            "expires_at": datetime.now(UTC) + timedelta(days=REFRESH_NGAY),
        },
    )
    return new_session_id


async def lay_user_hien_tai(
    request: Request,
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = DbSession,
) -> dict:
    """Read the access token from its httpOnly cookie or a Bearer header."""
    token = access_token
    if token is None:
        bearer = request.headers.get("Authorization", "")
        if bearer.startswith("Bearer "):
            token = bearer[7:]
    if token is None:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    data = doc_token(token, "access")
    username = data.get("sub")
    if not isinstance(username, str):
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    user = await lay_user_theo_ten(username, db)
    if user is None or user["account_status"] != "active":
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    kiem_tra_phien(data, user)
    await _kiem_tra_auth_session(db, data, user, "access", token)
    permissions = await quyen_hien_tai(
        user["username"], user["role"], list(data.get("permissions", [])), db
    )
    return {
        "username": user["username"],
        "role": user["role"],
        "permissions": permissions,
    }


YeuCauDangNhap = Depends(lay_user_hien_tai)


def doi_quyen(ten_quyen: str):
    """Create a dependency that enforces a persisted permission grant."""

    async def kiem(user: dict = YeuCauDangNhap) -> dict:
        if ten_quyen not in user.get("permissions", []):
            raise HTTPException(status_code=403, detail="Không đủ quyền")
        return user

    return Depends(kiem)


async def doi_owner_da_duyet(
    user: dict = YeuCauDangNhap,
    db: AsyncSession = DbSession,
) -> dict:
    """Reject unverified POI owners using the existing users.owner_verified_at."""
    if user.get("role") == "poi_owner":
        doc = await lay_user_theo_ten(user["username"], db)
        if not doc or not doc["is_poi_owner_verified"]:
            raise HTTPException(status_code=403, detail="Tài khoản chủ quán chưa được duyệt")
    return user


YeuCauOwnerDuyet = Depends(doi_owner_da_duyet)


async def lay_user_refresh(
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = DbSession,
) -> dict:
    """Validate a refresh JWT against its stored hash and active session."""
    token = refresh_token
    if token is None:
        bearer = request.headers.get("Authorization", "")
        if bearer.startswith("Bearer "):
            token = bearer[7:]
    if token is None:
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    data = doc_token(token, "refresh")
    username = data.get("sub")
    if not isinstance(username, str):
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    user = await lay_user_theo_ten(username, db)
    if user is None or user["account_status"] != "active":
        raise HTTPException(status_code=401, detail="Phiên không hợp lệ")
    kiem_tra_phien(data, user)
    session_id = await _kiem_tra_auth_session(db, data, user, "refresh", token)
    permissions = await quyen_hien_tai(user["username"], user["role"], [], db)
    return {
        "username": user["username"],
        "role": user["role"],
        "permissions": permissions,
        "phi_en_ver": SO_PHIEN_MAC_DINH,
        "session_id": session_id,
    }


YeuCauRefresh = Depends(lay_user_refresh)
