import sqlite3

from scripts.extract_mbtiles_region import extract_region


def _create_mbtiles(path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE metadata (name TEXT, value TEXT);
        CREATE TABLE tiles (
            zoom_level INTEGER,
            tile_column INTEGER,
            tile_row INTEGER,
            tile_data BLOB
        );
        """
    )
    connection.executemany(
        "INSERT INTO metadata (name, value) VALUES (?, ?)",
        [("minzoom", "0"), ("maxzoom", "2"), ("bounds", "-180,-85,180,85")],
    )
    connection.executemany(
        "INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) VALUES (?, ?, ?, ?)",
        [
            (1, 0, 0, b"inside"),
            (1, 3, 0, b"outside"),
            (2, 1, 1, b"inside"),
            (2, 1, 0, b"outside"),
        ],
    )
    connection.commit()
    connection.close()


def test_extract_region_copies_only_tiles_inside_buffered_bounds(tmp_path) -> None:
    source = tmp_path / "source.mbtiles"
    output = tmp_path / "region.mbtiles"
    _create_mbtiles(source)

    stats = extract_region(source, output, (-10, -10, 10, 10))

    assert stats["tile_count"] == 2
    result = sqlite3.connect(output)
    try:
        tiles = result.execute(
            "SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles ORDER BY zoom_level"
        ).fetchall()
        metadata = dict(result.execute("SELECT name, value FROM metadata"))
    finally:
        result.close()
    assert tiles == [(1, 0, 0, b"inside"), (2, 1, 1, b"inside")]
    assert metadata["bounds"] == "-10,-10,10,10"
    assert metadata["minzoom"] == "1"
    assert metadata["maxzoom"] == "2"
