"""Sinh manifest SHA-256 cho scope bản đồ từ tệp .pmtiles có sẵn (hoặc khởi tạo file mẫu nếu chưa có)."""

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.maps import SCOPES, THU_MUC_MAPS, manifest_scope


def khoi_tao_quan4_neu_thieu() -> None:
    thu_muc = THU_MUC_MAPS / "quan4"
    thu_muc.mkdir(parents=True, exist_ok=True)
    tep_pmtiles = thu_muc / "quan4.pmtiles"
    tep_style = thu_muc / "style.json"

    if not tep_pmtiles.exists():
        # PMTiles v3 hợp lệ (128 bytes): Magic "PMTiles\x03", rootDirectoryOffset=127, rootDirectoryLength=1
        header = bytearray(128)
        header[0:8] = b"PMTiles\x03"
        struct.pack_into("<Q", header, 8, 127)   # rootDirectoryOffset
        struct.pack_into("<Q", header, 16, 1)    # rootDirectoryLength
        header[127] = 0x00                       # varint 0 entries
        tep_pmtiles.write_bytes(header)
        print(f"Đã tạo {tep_pmtiles.name} chuẩn PMTiles v3.")

    if not tep_style.exists():
        style_content = {
            "version": 8,
            "name": "Bản đồ Offline Quận 4",
            "metadata": {
                "description": "Gói bản đồ số ngoại tuyến Quận 4"
            },
            "sources": {
                "quan4-offline": {
                    "type": "vector",
                    "url": "pmtiles://http://127.0.0.1:8000/maps/pack/quan4/quan4.pmtiles"
                }
            },
            "layers": [
                {
                    "id": "background",
                    "type": "background",
                    "paint": {
                        "background-color": "#f8fafc"
                    }
                }
            ]
        }
        tep_style.write_text(json.dumps(style_content, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Đã tạo {tep_style.name} cho MapLibre GL.")


def main() -> None:
    khoi_tao_quan4_neu_thieu()
    for scope in SCOPES:
        info = manifest_scope(scope)
        print(json.dumps(info, indent=2, ensure_ascii=False))
        print(f"Scope {scope}: {len(info['files'])} tệp.")


if __name__ == "__main__":
    main()
