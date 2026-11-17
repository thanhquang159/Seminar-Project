import struct

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import maps as maps_router
from app.services import maps


def _pmtiles_with_one_tile() -> bytes:
    data = bytearray(130)
    data[:8] = b"PMTiles\x03"
    struct.pack_into("<Q", data, 8, 127)
    struct.pack_into("<Q", data, 16, 3)
    struct.pack_into("<Q", data, 72, 1)
    struct.pack_into("<Q", data, 80, 1)
    struct.pack_into("<Q", data, 88, 1)
    data[127:130] = b"\x01\x00\x00"
    return bytes(data)


def test_manifest_omits_empty_pmtiles_placeholder(tmp_path, monkeypatch) -> None:
    scope_dir = tmp_path / "quan4"
    scope_dir.mkdir()
    (scope_dir / "style.json").write_text("{}", encoding="utf-8")
    (scope_dir / "quan4.pmtiles").write_bytes(b"PMTiles\x03" + bytes(120))
    monkeypatch.setattr(maps, "THU_MUC_MAPS", tmp_path)

    assert maps.manifest_scope("quan4")["files"] == []


def test_manifest_includes_valid_pmtiles_and_style(tmp_path, monkeypatch) -> None:
    scope_dir = tmp_path / "quan4"
    scope_dir.mkdir()
    (scope_dir / "style.json").write_text("{}", encoding="utf-8")
    (scope_dir / "quan4.pmtiles").write_bytes(_pmtiles_with_one_tile())
    (scope_dir / "quan4-boundary.geojson").write_text(
        '{"type":"Polygon","coordinates":[]}', encoding="utf-8"
    )
    font_dir = scope_dir / "fonts" / "Noto Sans Regular"
    font_dir.mkdir(parents=True)
    (font_dir / "0-255.pbf").write_bytes(b"glyphs")
    (scope_dir / "fonts" / "OFL.txt").write_text("font license", encoding="utf-8")
    monkeypatch.setattr(maps, "THU_MUC_MAPS", tmp_path)

    files = maps.manifest_scope("quan4")["files"]

    assert [item["file"] for item in files] == [
        "quan4/quan4.pmtiles",
        "quan4/style.json",
        "quan4/quan4-boundary.geojson",
        "quan4/fonts/Noto Sans Regular/0-255.pbf",
        "quan4/fonts/OFL.txt",
    ]


def test_pmtiles_rejects_directory_outside_file(tmp_path) -> None:
    data = bytearray(_pmtiles_with_one_tile())
    struct.pack_into("<Q", data, 16, 10)
    pack = tmp_path / "bad.pmtiles"
    pack.write_bytes(data)

    assert not maps.la_pmtiles_co_du_lieu(pack)


def test_pack_glyphs_supports_byte_range_requests(tmp_path, monkeypatch) -> None:
    scope_dir = tmp_path / "quan4" / "fonts" / "Noto Sans Regular"
    scope_dir.mkdir(parents=True)
    (scope_dir / "0-255.pbf").write_bytes(b"abcdef")
    monkeypatch.setattr(maps, "THU_MUC_MAPS", tmp_path)
    monkeypatch.setattr(maps_router, "THU_MUC_MAPS", tmp_path)
    app = FastAPI()
    app.include_router(maps_router.router)

    response = TestClient(app).get(
        "/maps/pack/quan4/fonts/Noto%20Sans%20Regular/0-255.pbf",
        headers={"Range": "bytes=1-3"},
    )

    assert response.status_code == 206
    assert response.content == b"bcd"
    assert response.headers["content-range"] == "bytes 1-3/6"


def test_pack_pmtiles_supports_byte_range_requests(tmp_path, monkeypatch) -> None:
    scope_dir = tmp_path / "quan4"
    scope_dir.mkdir()
    archive = _pmtiles_with_one_tile()
    (scope_dir / "quan4.pmtiles").write_bytes(archive)
    monkeypatch.setattr(maps, "THU_MUC_MAPS", tmp_path)
    monkeypatch.setattr(maps_router, "THU_MUC_MAPS", tmp_path)
    app = FastAPI()
    app.include_router(maps_router.router)

    response = TestClient(app).get(
        "/maps/pack/quan4/quan4.pmtiles",
        headers={"Range": "bytes=127-129"},
    )

    assert response.status_code == 206
    assert response.content == archive[127:130]
    assert response.headers["content-range"] == "bytes 127-129/130"


def test_pack_serves_font_license(tmp_path, monkeypatch) -> None:
    license_path = tmp_path / "quan4" / "fonts" / "OFL.txt"
    license_path.parent.mkdir(parents=True)
    license_path.write_text("font license", encoding="utf-8")
    monkeypatch.setattr(maps, "THU_MUC_MAPS", tmp_path)
    monkeypatch.setattr(maps_router, "THU_MUC_MAPS", tmp_path)
    app = FastAPI()
    app.include_router(maps_router.router)

    response = TestClient(app).get("/maps/pack/quan4/fonts/OFL.txt")

    assert response.status_code == 200
    assert response.text == "font license"
