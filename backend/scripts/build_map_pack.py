"""Kiểm tra và in manifest cho các PMTiles có dữ liệu đã được cung cấp."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.maps import SCOPES, manifest_scope


def main() -> None:
    for scope in SCOPES:
        info = manifest_scope(scope)
        if info["files"]:
            print(json.dumps(info, indent=2, ensure_ascii=False))
            print(f"Scope {scope}: {len(info['files'])} tệp hợp lệ.")
        else:
            print(f"Scope {scope}: chưa có PMTiles hợp lệ; không tạo tệp mẫu.")


if __name__ == "__main__":
    main()
