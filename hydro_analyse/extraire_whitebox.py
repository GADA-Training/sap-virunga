import os
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask, shapes
from shapely.geometry import LineString, shape
import whitebox

CSV_PATH = "points_arcgis.csv"
DEM_PATH = "Copernicus_DEM_30m.tif"
OUT_DIR = "sorties_whitebox_hydro"

SEUIL_STREAM = 30       # seuil minimal d'accumulation (en cellules) pour les tronçons de réseau
RAYON_SNAP_PX = 20      # rayon de recherche (en pixels) autour du point initial pour caler l'exutoire

# Codes Whitebox D8 (1, 2, 4, 8, 16, 32, 64, 128) -> (d_row, d_col)
WB_D8_DELTA = {
    1: (0, 1),
    2: (1, 1),
    4: (1, 0),
    8: (1, -1),
    16: (0, -1),
    32: (-1, -1),
    64: (-1, 0),
    128: (-1, 1),
}

os.makedirs(OUT_DIR, exist_ok=True)

wb = whitebox.WhiteboxTools()
wb.verbose = False

dem_abs = os.path.abspath(DEM_PATH)
breach_abs = os.path.abspath(os.path.join(OUT_DIR, "dem_breached.tif"))
fdir_abs = os.path.abspath(os.path.join(OUT_DIR, "d8_pointer.tif"))
facc_abs = os.path.abspath(os.path.join(OUT_DIR, "d8_flow_acc.tif"))

# 1. Conditionnement, directions D8 et accumulation de flux sur le MNT élargi
assert wb.breach_depressions(dem=dem_abs, output=breach_abs) == 0, "Échec BreachDepressions"
assert wb.d8_pointer(dem=breach_abs, output=fdir_abs) == 0, "Échec D8Pointer"
assert wb.d8_flow_accumulation(i=fdir_abs, out_type="cells", output=facc_abs) == 0, "Échec D8FlowAccumulation"

with rasterio.open(facc_abs) as src_acc:
    acc = src_acc.read(1).astype(np.float64)
    transform = src_acc.transform
    crs = src_acc.crs
    meta_int = src_acc.meta.copy()
    if src_acc.nodata is not None:
        acc = np.where(acc == src_acc.nodata, 0.0, acc)

with rasterio.open(fdir_abs) as src_fdir:
    fdir = src_fdir.read(1)
    if src_fdir.nodata is not None:
        fdir = np.where(fdir == src_fdir.nodata, 0, fdir)

nrows, ncols = acc.shape
meta_int.update({"dtype": "int32", "count": 1, "nodata": 0})

print(f"MNT : {nrows}x{ncols} pixels | Max flow accumulation : {acc.max():.0f} cellules")

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

    # Calage de l'exutoire sur le pixel de plus forte accumulation dans une fenêtre locale
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

    # Délimitation du bassin versant amont via Whitebox Watershed
    pour_tif = os.path.abspath(os.path.join(OUT_DIR, f"pour_{rid}_{nom_propre}.tif"))
    ws_tif = os.path.abspath(os.path.join(OUT_DIR, f"ws_{rid}_{nom_propre}.tif"))

    pour_arr = np.zeros((nrows, ncols), dtype=np.int32)
    pour_arr[snap_r, snap_c] = 1
    with rasterio.open(pour_tif, "w", **meta_int) as dst:
        dst.write(pour_arr, 1)

    status_ws = wb.watershed(d8_pntr=fdir_abs, pour_pts=pour_tif, output=ws_tif)
    assert status_ws == 0, f"Échec Watershed pour {nom}"

    with rasterio.open(ws_tif) as src_ws:
        ws_arr = src_ws.read(1)
        mask_ws = (ws_arr != 0) & (ws_arr != src_ws.nodata if src_ws.nodata is not None else True)

    point_dans_bassin = bool(mask_ws[r0, c0])

    polys = [
        shape(geom)
        for geom, val in shapes(mask_ws.astype(np.uint8), mask=mask_ws, transform=transform)
        if val == 1
    ]

    aire_km2 = 0.0
    touche_bord_mnt = False
    long_km = 0.0
    nb_troncons = 0

    if polys:
        gdf_ws = gpd.GeoDataFrame(
            {"id": [rid], "nom": [nom], "point_dans_bassin": [point_dans_bassin], "geometry": [polys[0]]},
            crs=crs or "EPSG:4326",
        )
        out_ws_geojson = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_bassin_wb.geojson")
        gdf_ws.to_file(out_ws_geojson, driver="GeoJSON")
        aire_km2 = float(gdf_ws.to_crs("EPSG:32735").area.sum() / 1e6)

        minx, miny, maxx, maxy = gdf_ws.total_bounds
        touche_bord_mnt = (
            abs(minx - transform.c) < 1e-4
            or abs(maxx - (transform.c + ncols * transform.a)) < 1e-4
            or abs(maxy - transform.f) < 1e-4
            or abs(miny - (transform.f + nrows * transform.e)) < 1e-4
        )

        # Extraction du réseau hydrographique dans le bassin versant
        stream_mask = mask_ws & (acc >= SEUIL_STREAM)
        rs, cs = np.where(stream_mask)
        lines = []
        for r, c in zip(rs, cs):
            code = int(fdir[r, c])
            if code in WB_D8_DELTA:
                dr, dc = WB_D8_DELTA[code]
                nr, nc = r + dr, c + dc
                if 0 <= nr < nrows and 0 <= nc < ncols and mask_ws[nr, nc]:
                    x1, y1 = rasterio.transform.xy(transform, r, c, offset="center")
                    x2, y2 = rasterio.transform.xy(transform, nr, nc, offset="center")
                    lines.append(LineString([(x1, y1), (x2, y2)]))

        if lines:
            gdf_str = gpd.GeoDataFrame(
                {"id": [rid] * len(lines), "nom": [nom] * len(lines), "geometry": lines},
                crs=crs or "EPSG:4326",
            )
            out_str_geojson = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_reseau_wb.geojson")
            gdf_str.to_file(out_str_geojson, driver="GeoJSON")
            long_km = float(gdf_str.to_crs("EPSG:32735").length.sum() / 1e3)
            nb_troncons = len(lines)

    print(
        f"ID {rid} ({nom}) | exutoire=({snap_x:.6f}, {snap_y:.6f}) acc={acc[snap_r, snap_c]:.0f} | "
        f"point_dans_bassin={point_dans_bassin} | aire={aire_km2:.3f} km² | "
        f"tronçons={nb_troncons} | long={long_km:.3f} km | touche_bord_mnt={touche_bord_mnt}"
    )