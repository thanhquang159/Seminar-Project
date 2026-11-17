# Quận 4 Offline Map Pack

This directory contains the real, OSM-derived `quan4` map pack:

- `quan4.pmtiles`: PMTiles v3 vector archive clipped to Quận 4 and an approximately 300 m buffer.
- `style.json`: MapLibre style using the verified Shortbread 1.0 source-layer names.
- `quan4-boundary.geojson`: OSM relation 2778323, used for the Quận 4 outline.
- `fonts/Noto Sans Regular/*.pbf`: offline glyph ranges; `fonts/OFL.txt` contains the font license.

The style does not use sprites or external tile, font, or image URLs. The backend manifest includes the PMTiles, style, boundary, glyph, and font-license files; the frontend verifies and caches each file before activating the pack. The map attribution control credits OpenStreetMap contributors and Geofabrik. OpenStreetMap data is available under the Open Database License (ODbL) 1.0.

## Data source and limits

The current archive was made from Geofabrik's Vietnam Shortbread 1.0 MBTiles dataset, an OpenStreetMap-derived vector-tile dataset:

<https://download.geofabrik.de/asia/vietnam-shortbread-1.0.mbtiles>

It is a practical regional build from pre-generated MBTiles; it is **not** generated from a raw `.osm.pbf` with Planetiler. The source snapshot used for this pack was 687,448,064 bytes with ETag `"28f9a000-6605cedb4ec5f"`; Geofabrik may replace the download, so record the retrieval date, ETag, and SHA-256 for each future update. Its PMTiles archive has native tiles through zoom 14. The `streets`, `buildings`, and `pois` layers start at zoom 14 in this regional dataset. Zooming further only overzooms those tiles; it does not add detail. For true street/building detail beyond zoom 14, build a higher-zoom archive from a current OSM PBF with Planetiler and validate its schema before updating this style.

Shortbread's `boundaries` layer represents country/state boundaries, not Quận 4. The district outline therefore comes from the separate OSM relation GeoJSON. The project POI demo coordinates near `106.7641, 10.7569` are outside the Quận 4 boundary; the offline camera is centered on the actual district and the pack is not expanded to include those demo coordinates.

## Rebuild

Run from the repository root in PowerShell. Install the official `pmtiles` CLI separately and keep the downloaded source and intermediate MBTiles outside the repository.

```powershell
$work = Join-Path $env:TEMP "quan4-map-build"
New-Item -ItemType Directory -Force $work | Out-Null
curl.exe -L "https://download.geofabrik.de/asia/vietnam-shortbread-1.0.mbtiles" `
  -o (Join-Path $work "vietnam-shortbread-1.0.mbtiles")

python backend\scripts\extract_mbtiles_region.py `
  (Join-Path $work "vietnam-shortbread-1.0.mbtiles") `
  (Join-Path $work "quan4-clipped.mbtiles") `
  --bbox 106.683672,10.748997,106.725030,10.772470

pmtiles convert (Join-Path $work "quan4-clipped.mbtiles") (Join-Path $work "quan4.pmtiles")
pmtiles verify (Join-Path $work "quan4.pmtiles")
pmtiles show --metadata (Join-Path $work "quan4.pmtiles")
```

The buffered bounds are based on the OSM relation's bbox `[106.6864219, 10.7517073, 106.7222803, 10.7697601]`. They include approximately 300 m around the district. If the boundary changes, review `quan4-boundary.geojson` and recompute the buffered bounds rather than silently widening the pack.

Before replacing the checked-in archive:

1. Confirm `pmtiles show --metadata` reports PMTiles v3, vector tiles, the expected bounds, and the source-layer IDs used by `style.json`.
2. Confirm `pmtiles verify` succeeds and read sample tiles around the district center at z11–z14. For the current center, tile coordinates are `1631/962`, `3262/1924`, `6524/3849`, and `13048/7699`, respectively; `pmtiles tile <archive> <z> <x> <y>` reads a sample.
3. Replace `backend\static\maps\quan4\quan4.pmtiles` only after those checks. Review the style against the new metadata and keep all glyph/boundary assets local.
4. Run the tests after the update:

   ```powershell
   Set-Location backend
   python -m pytest tests\test_map_packs.py tests\test_extract_mbtiles_region.py -q
   Set-Location ..\frontend
   $env:PW_CHANNEL = "chrome"
   npm run test:e2e:pwa
   ```

   The PWA test builds production assets and requires Google Chrome installed locally. Install the pack, disable networking, then verify the map after reload and pan/zoom.

The backend hashes the current files when building the manifest, so changing a pack asset automatically changes its fingerprint. No manifest or quota code needs a manual update.

## Source layers used

The archive metadata lists these exact Shortbread layers used by the style:

`land`, `water_polygons`, `water_lines`, `street_polygons`, `streets`, `buildings`, `place_labels`, `boundaries`, `boundary_labels`, `water_lines_labels`, `street_labels`, `water_polygons_labels`, and `pois`.

The Quận 4 boundary is the separate GeoJSON source, not a PMTiles source-layer.
