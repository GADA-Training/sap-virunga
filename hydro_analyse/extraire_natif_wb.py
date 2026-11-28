import os
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape
import whitebox

CSV_PATH = "points_arcgis.csv"
DEM_PATH = "Copernicus_DEM_30m.tif"
OUT_DIR = "sorties_whitebox_hydro"

SEUIL_STREAM = 10       # seuil d'accumulation pour ExtractStreams (adapté à p99=10, max=43)
RAYON_SNAP_PX = 20

os.makedirs(OUT_DIR, exist_ok=True)

wb = whitebox.WhiteboxTools()
wb.verbose = False

dem_abs = os.path.abspath(DEM_PATH)
breached_abs = os.path.abspath(os.path.join(OUT_DIR, "wb_breached.tif"))
filled_abs = os.path.abspath(os.path.join(OUT_DIR, "wb_filled.tif"))
fdir_abs = os.path.abspath(os.path.join(OUT_DIR, "wb_d8_pntr.tif"))
facc_abs = os.path.abspath(os.path.join(OUT_DIR, "wb_d8_acc.tif"))
streams_tif = os.path.abspath(os.path.join(OUT_DIR, "wb_streams.tif"))
streams_shp = os.path.abspath(os.path.join(OUT_DIR, "wb_streams.shp"))

assert wb.breach_depressions(dem=dem_abs, output=breached_abs) == 0, "Échec breach_depressions"
assert wb.fill_depressions(dem=breached_abs, output=filled_abs) == 0, "Échec fill_depressions"
assert wb.d8_pointer(dem=filled_abs, output=fdir_abs) == 0, "Échec d8_pointer"
assert wb.d8_flow_accumulation(i=filled_abs, out_type="cells", output=facc_abs) == 0, "Échec d8_flow_accumulation"
assert wb.extract_streams(flow_accum=facc_abs, output=streams_tif, threshold=float(SEUIL_STREAM)) == 0, "Échec extract_streams"
wb.raster_streams_to_vector(streams=streams_tif, d8_pntr=fdir_abs, output=streams_shp)

with rasterio.open(facc_abs) as src_acc:
    acc = src_acc.read(1).astype(np.float64)
    transform = src_acc.transform
    crs = src_acc.crs
    meta_int = src_acc.meta.copy()
    if src_acc.nodata is not None:
        acc = np.where(acc == src_acc.nodata, 0.0, acc)

meta_int.update({"dtype": "int32", "count": 1, "nodata": 0})
nrows, ncols = acc.shape
print(f"Accumulation (i=filled_abs) : min={acc.min():.0f} | p99={np.percentile(acc, 99):.0f} | max={acc.max():.0f}")

gdf_streams_all = None
if os.path.exists(streams_shp):
    gdf_streams_all = gpd.read_file(streams_shp)
    if gdf_streams_all.crs is None and crs is not None:
        gdf_streams_all = gdf_streams_all.set_crs(crs)
    print(f"Tronçons vectorisés extraits : {len(gdf_streams_all)}")

df = pd.read_csv(CSV_PATH)
rivers_df = df[df["ID"].isin([34, 35, 36])].copy()

for _, row in rivers_df.iterrows():
    rid = int(row["ID"])
    nom = str(row["Nom"]).strip()
    nom_propre = nom.replace(" ", "_")
    lat = float(row["Latitude"])
    lon = float(row["Longitude"])

    r0, c0 = rasterio.transform.rowcol(transform, lon, lat)
    r0 = int(np.clip(r0, 0, nrows - 1))
    c0 = int(np.clip(c0, 0, ncols - 1))

    r_min = max(0, r0 - RAYON_SNAP_PX)
    r_max = min(nrows, r0 + RAYON_SNAP_PX + 1)
    c_min = max(0, c0 - RAYON_SNAP_PX)
    c_max = min(ncols, c0 + RAYON_SNAP_PX + 1)

    sub_acc = acc[r_min:r_max, c_min:c_max]
    best_idx = int(np.argmax(sub_acc))
    snap_r, snap_c = np.unravel_index(best_idx, sub_acc.shape)
    snap_r += r_min
    snap_c += c_min
    snap_x, snap_y = rasterio.transform.xy(transform, snap_r, snap_c, offset="center")

    pour_tif = os.path.abspath(os.path.join(OUT_DIR, f"pour_{rid}_{nom_propre}.tif"))
    ws_tif = os.path.abspath(os.path.join(OUT_DIR, f"ws_{rid}_{nom_propre}.tif"))

    pour_arr = np.zeros((nrows, ncols), dtype=np.int32)
    pour_arr[snap_r, snap_c] = 1
    with rasterio.open(pour_tif, "w", **meta_int) as dst:
        dst.write(pour_arr, 1)

    assert wb.watershed(d8_pntr=fdir_abs, pour_pts=pour_tif, output=ws_tif) == 0, f"Échec watershed {nom}"

    with rasterio.open(ws_tif) as src_ws:
        ws_arr = src_ws.read(1)
        mask_ws = (ws_arr > 0) & (ws_arr != src_ws.nodata if src_ws.nodata is not None else True)

    point_dans_bassin = bool(mask_ws[r0, c0])
    polys = [
        shape(geom)
        for geom, val in shapes(mask_ws.astype(np.uint8), mask=mask_ws, transform=transform)
        if val == 1
    ]

    aire_km2 = 0.0
    long_km = 0.0
    nb_troncons = 0

    if polys:
        gdf_ws = gpd.GeoDataFrame(
            {"id": [rid], "nom": [nom], "point_dans_bassin": [point_dans_bassin], "geometry": [polys[0]]},
            crs=crs or "EPSG:4326",
        )
        out_ws = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_bassin_wb.geojson")
        gdf_ws.to_file(out_ws, driver="GeoJSON")
        aire_km2 = float(gdf_ws.to_crs("EPSG:32735").area.sum() / 1e6)

        if gdf_streams_all is not None and len(gdf_streams_all) > 0:
            bassin_geom = gdf_ws.geometry.iloc[0]
            sub_str = gdf_streams_all[gdf_streams_all.intersects(bassin_geom)].copy()
            if len(sub_str) > 0:
                sub_str["geometry"] = sub_str.geometry.intersection(bassin_geom)
                sub_str = sub_str[~sub_str.geometry.is_empty]
                nb_troncons = len(sub_str)
                long_km = float(sub_str.to_crs("EPSG:32735").length.sum() / 1e3)
                out_str = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_reseau_wb.geojson")
                sub_str.to_file(out_str, driver="GeoJSON")

    print(
        f"ID {rid} ({nom}) | exutoire=({snap_x:.6f}, {snap_y:.6f}) acc={acc[snap_r, snap_c]:.0f} | "
        f"point_dans_bassin={point_dans_bassin} | aire={aire_km2:.3f} km² | "
        f"tronçons={nb_troncons} | long={long_km:.3f} km"
    )