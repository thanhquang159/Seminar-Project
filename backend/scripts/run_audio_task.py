"""Chạy một tác vụ audio chỉ định và in kết quả; không công khai hay khôi phục POI."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.postgres import engine
from app.services.tasks import QuanLyTasks


async def main(task_id, recover=False):
    engine.echo = False
    manager = QuanLyTasks()
    try:
        async with asyncio.timeout(120):
            if recover:
                await manager.khoi_phuc()
                ids = list(manager._runners)
                await asyncio.gather(*list(manager._runners.values()))
            else:
                ids = [task_id]
                await manager._chay(task_id)
            results = [await manager._doc(item) for item in ids]
            print(json.dumps(results, ensure_ascii=False, default=str))
            return all(item.get("status") == "done" for item in results)
    finally:
        await manager.stop()
        await engine.dispose()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id", nargs="?")
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    if bool(args.task_id) == args.recover:
        parser.error("Chọn một task_id hoặc --recover")
    raise SystemExit(0 if asyncio.run(main(args.task_id, args.recover)) else 1)
