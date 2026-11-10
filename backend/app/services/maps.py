"""Gói offline: đường dẫn an toàn, manifest SHA-256, tùy chọn tải."""

import hashlib
from pathlib import Path
from urllib.parse import unquote

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

THU_MUC_MAPS = Path(__file__).resolve().parents[2] / "static" / "maps"

# Hai scope theo plan: Quận 4 gọn nhẹ, TP.HCM đầy đủ hơn.
SCOPES = ("quan4", "hcm")


def duong_an_toan(ten_tep: str) -> Path:
    """Giải mã phần trăm rồi chuẩn hóa, còn trong gốc mới cho qua."""
    giai_ma = unquote(unquote(ten_tep))
    base = THU_MUC_MAPS.resolve()
    dich = (base / giai_ma).resolve()
    if dich != base and base not in dich.parents:
        raise HTTPException(status_code=400, detail="Đường dẫn không hợp lệ")
    return dich


def sha256_tep(tep: Path) -> str:
    h = hashlib.sha256()
    with tep.open("rb") as f:
        for mieng in iter(lambda: f.read(65536), b""):
            h.update(mieng)
    return h.hexdigest()


def manifest_scope(scope: str) -> dict:
    """Manifest một scope: danh sách tệp kèm hash để client kiểm toàn vẹn."""
    thu_muc = THU_MUC_MAPS / scope
    tep_list = []
    if thu_muc.is_dir():
        for tep in sorted([*thu_muc.glob("*.pmtiles"), *thu_muc.glob("*.json")]):
            tep_list.append(
                {
                    "file": f"{scope}/{tep.name}",
                    "sha256": sha256_tep(tep),
                    "bytes": tep.stat().st_size,
                }
            )
    fingerprint = hashlib.sha256(
        str([(t["file"], t["sha256"]) for t in tep_list]).encode()
    ).hexdigest()
    return {"scope": scope, "files": tep_list, "fingerprint": fingerprint}


async def manifest_audio_pack(db: AsyncSession, lang: str) -> dict:
    """Manifest các audio asset thuộc pack đã publish trong PostgreSQL."""
    result = await db.execute(
        text(
            """
            SELECT a.storage_key AS url,
                   rtrim(a.checksum_sha256::text) AS sha256,
                   a.size_bytes AS bytes
            FROM offline_pack_assets AS a
            JOIN offline_packs AS p ON p.id = a.offline_pack_id
            WHERE a.asset_type = 'audio'
              AND (
                  a.language_code = :lang
                  OR (
                      a.language_code IS NULL
                      AND (p.language_code IS NULL OR p.language_code = :lang)
                  )
              )
              AND p.status = 'published'
              AND (p.language_code IS NULL OR p.language_code = :lang)
            ORDER BY p.pack_code, a.storage_key
            """
        ),
        {"lang": lang},
    )
    return {"lang": lang, "files": [dict(row) for row in result.mappings().all()]}
