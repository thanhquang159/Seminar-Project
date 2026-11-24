"""Đọc lịch sử và lý do chặn duyệt của một tài khoản; không duyệt/từ chối hoặc sửa dữ liệu."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException

from app.postgres import AsyncSessionLocal, engine
from app.routers import owner


async def main(username):
    engine.echo = False
    user = {"username": username, "role": "admin"}
    try:
        async with asyncio.timeout(30), AsyncSessionLocal() as db:
            for label, function in (
                ("history", owner.submission_cua_toi),
                ("pending", owner.submission_cho_duyet),
            ):
                try:
                    rows = await function(db, user)
                    result = [
                        {
                            key: row.get(key)
                            for key in (
                                "id",
                                "username",
                                "name",
                                "status",
                                "submission_type",
                                "can_approve",
                                "approval_blockers",
                            )
                        }
                        | {
                            "name": row["data"].get("name"),
                            "lat": row["data"].get("lat"),
                            "lng": row["data"].get("lng"),
                        }
                        for row in rows
                    ]
                    print(json.dumps({label: result}, ensure_ascii=False))
                except HTTPException as exc:
                    print(
                        json.dumps(
                            {label: {"status": exc.status_code, "detail": exc.detail}},
                            ensure_ascii=False,
                        )
                    )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    asyncio.run(main(parser.parse_args().username))
