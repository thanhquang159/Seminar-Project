"""Extract a buffered geographic tile range from an MBTiles archive."""

import argparse
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

MAX_MERCATOR_LAT = 85.05112878


def _x_tile(longitude: float, zoom: int) -> int:
    count = 1 << zoom
    return max(0, min(count - 1, math.floor((longitude + 180) / 360 * count)))


def _y_tile(latitude: float, zoom: int) -> int:
    bounded = max(-MAX_MERCATOR_LAT, min(MAX_MERCATOR_LAT, latitude))
    radians = math.radians(bounded)
    count = 1 << zoom
    y = (1 - math.asinh(math.tan(radians)) / math.pi) / 2 * count
    return max(0, min(count - 1, math.floor(y)))


def _tile_range(bbox: tuple[float, float, float, float], zoom: int) -> tuple[int, int, int, int]:
    min_lon, min_lat, max_lon, max_lat = bbox
    count = 1 << zoom
    min_x = _x_tile(min_lon, zoom)
    max_x = _x_tile(max_lon, zoom)
    north_y = _y_tile(max_lat, zoom)
    south_y = _y_tile(min_lat, zoom)
    return min_x, max_x, count - 1 - south_y, count - 1 - north_y


def _read_metadata(source: sqlite3.Connection) -> dict[str, str]:
    rows = source.execute("SELECT name, value FROM metadata").fetchall()
    return {name: value for name, value in rows}


def extract_region(
    source_path: Path,
    output_path: Path,
    bbox: tuple[float, float, float, float],
    dry_run: bool = False,
) -> dict[str, Any]:
    min_lon, min_lat, max_lon, max_lat = bbox
    if not (-180 <= min_lon < max_lon <= 180 and -90 <= min_lat < max_lat <= 90):
        raise ValueError(f"Invalid geographic bounds: {bbox}")
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if output_path.exists() and not dry_run:
        raise FileExistsError(output_path)

    source = sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        metadata = _read_metadata(source)
        if not metadata:
            raise ValueError("MBTiles archive has no metadata table")
        try:
            min_zoom = int(metadata.get("minzoom", "0"))
            max_zoom = int(metadata["maxzoom"])
        except (KeyError, ValueError) as error:
            raise ValueError("MBTiles metadata must contain a valid maxzoom") from error

        ranges = {
            zoom: _tile_range(bbox, zoom)
            for zoom in range(min_zoom, max_zoom + 1)
        }
        selected: list[tuple[int, int, int, int, int]] = []
        count = 0
        tile_bytes = 0
        for zoom, (min_x, max_x, min_row, max_row) in ranges.items():
            zoom_count, zoom_bytes = source.execute(
                """
                SELECT count(*), coalesce(sum(length(tile_data)), 0)
                FROM tiles
                WHERE zoom_level = ?
                  AND tile_column BETWEEN ? AND ?
                  AND tile_row BETWEEN ? AND ?
                """,
                (zoom, min_x, max_x, min_row, max_row),
            ).fetchone()
            if zoom_count:
                selected.append((zoom, min_x, max_x, min_row, max_row))
            count += zoom_count
            tile_bytes += zoom_bytes

        stats = {
            "bbox": list(bbox),
            "tile_count": count,
            "tile_bytes": tile_bytes,
            "minzoom": min((item[0] for item in selected), default=None),
            "maxzoom": max((item[0] for item in selected), default=None),
        }
        if dry_run:
            return stats
        if count == 0:
            raise ValueError(f"No tiles intersect the requested bounds: {bbox}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        destination = sqlite3.connect(output_path)
        try:
            destination.executescript(
                """
                PRAGMA journal_mode = OFF;
                PRAGMA synchronous = OFF;
                CREATE TABLE metadata (name TEXT, value TEXT);
                CREATE TABLE tiles (
                    zoom_level INTEGER,
                    tile_column INTEGER,
                    tile_row INTEGER,
                    tile_data BLOB
                );
                CREATE UNIQUE INDEX tiles_idx
                    ON tiles (zoom_level, tile_column, tile_row);
                """
            )
            metadata["bounds"] = ",".join(str(value) for value in bbox)
            metadata["center"] = (
                f"{(min_lon + max_lon) / 2},"
                f"{(min_lat + max_lat) / 2},"
                f"{stats['maxzoom']}"
            )
            metadata["minzoom"] = str(stats["minzoom"])
            metadata["maxzoom"] = str(stats["maxzoom"])
            destination.executemany(
                "INSERT INTO metadata (name, value) VALUES (?, ?)",
                metadata.items(),
            )

            for zoom, min_x, max_x, min_row, max_row in selected:
                cursor = source.execute(
                    """
                    SELECT zoom_level, tile_column, tile_row, tile_data
                    FROM tiles
                    WHERE zoom_level = ?
                      AND tile_column BETWEEN ? AND ?
                      AND tile_row BETWEEN ? AND ?
                    """,
                    (zoom, min_x, max_x, min_row, max_row),
                )
                while batch := cursor.fetchmany(250):
                    destination.executemany(
                        """
                        INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data)
                        VALUES (?, ?, ?, ?)
                        """,
                        batch,
                    )
            destination.commit()
        finally:
            destination.close()
        return stats
    finally:
        source.close()


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    try:
        parts = tuple(float(part) for part in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Bounds must be min_lon,min_lat,max_lon,max_lat") from error
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Bounds must be min_lon,min_lat,max_lon,max_lat")
    return parts[0], parts[1], parts[2], parts[3]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Input MBTiles archive")
    parser.add_argument("output", type=Path, help="Output regional MBTiles archive")
    parser.add_argument(
        "--bbox",
        required=True,
        type=_parse_bbox,
        help="Buffered bounds: min_lon,min_lat,max_lon,max_lat",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report selected tiles without writing")
    args = parser.parse_args()
    print(json.dumps(extract_region(args.source, args.output, args.bbox, args.dry_run), indent=2))


if __name__ == "__main__":
    main()
