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


def la_pmtiles_co_du_lieu(tep: Path) -> bool:
    """Reject empty or truncated PMTiles files before publishing an offline pack."""
    kich_thuoc = tep.stat().st_size
    if kich_thuoc < 128:
        return False

    with tep.open("rb") as f:
        header = f.read(127)
        f.seek(127)
        byte_dau_thu_muc = f.read(1)

    if len(header) != 127 or header[:8] != b"PMTiles\x03" or not byte_dau_thu_muc:
        return False

    root_offset = int.from_bytes(header[8:16], "little")
    root_length = int.from_bytes(header[16:24], "little")
    addressed_tiles = int.from_bytes(header[72:80], "little")
    tile_entries = int.from_bytes(header[80:88], "little")
    tile_contents = int.from_bytes(header[88:96], "little")
    if (
        root_offset < 127
        or root_length == 0
        or root_offset + root_length > kich_thuoc
        or addressed_tiles == 0
        or tile_entries == 0
        or tile_contents == 0
    ):
        return False

    # PMTiles directory entry count is the first unsigned varint in the root directory.
    so_muc = 0
    shift = 0
    with tep.open("rb") as f:
        f.seek(root_offset)
        while shift < 70:
            byte = f.read(1)
            if not byte:
                return False
            so_muc |= (byte[0] & 0x7F) << shift
            if byte[0] < 0x80:
                return so_muc > 0
            shift += 7
    return False


def manifest_scope(scope: str) -> dict:
    """Manifest một scope: danh sách tệp kèm hash để client kiểm toàn vẹn."""
    thu_muc = THU_MUC_MAPS / scope
    tep_list = []
    if thu_muc.is_dir():
        tep_pmtiles = [
            tep for tep in sorted(thu_muc.glob("*.pmtiles")) if la_pmtiles_co_du_lieu(tep)
        ]
        tep_style = sorted(thu_muc.glob("style.json")) if tep_pmtiles else []
        if not tep_style:
            tep_pmtiles = []
        tep_geojson = sorted(thu_muc.glob("*.geojson")) if tep_pmtiles else []
        tep_fonts = sorted((thu_muc / "fonts").rglob("*.pbf")) if tep_pmtiles else []
        tep_font_license = (
            [thu_muc / "fonts" / "OFL.txt"]
            if tep_pmtiles and (thu_muc / "fonts" / "OFL.txt").is_file()
            else []
        )
        for tep in [*tep_pmtiles, *tep_style, *tep_geojson, *tep_fonts, *tep_font_license]:
            tep_list.append(
                {
                    "file": f"{scope}/{tep.relative_to(thu_muc).as_posix()}",
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
