import os
from collections import deque
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from shapely.geometry import LineString, shape
import whitebox

CSV_PATH = "points_arcgis.csv"
DEM_PATH = "Copernicus_DEM_30m.tif"
OUT_DIR = "sorties_whitebox_hydro"

SEUIL_STREAM = 5        # seuil adapté à l'échelle d'accumulation actuelle (ajustable)
RAYON_SNAP_PX = 20

# Codes directionnels standard D8 (1..128) -> (d_row, d_col)
D8_DELTA = {
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

assert wb.breach_depressions(dem=dem_abs, output=breach_abs) == 0, "Échec BreachDepressions"
assert wb.d8_pointer(dem=breach_abs, output=fdir_abs) == 0, "Échec D8Pointer"
assert wb.d8_flow_accumulation(i=fdir_abs, out_type="cells", output=facc_abs) == 0, "Échec D8FlowAccumulation"

with rasterio.open(facc_abs) as src_acc:
    acc = src_acc.read(1).astype(np.float64)
    transform = src_acc.transform
    crs = src_acc.crs
    if src_acc.nodata is not None:
        acc = np.where(acc == src_acc.nodata, 0.0, acc)

with rasterio.open(fdir_abs) as src_fdir:
    fdir = src_fdir.read(1)
    if src_fdir.nodata is not None:
        fdir = np.where(fdir == src_fdir.nodata, 0, fdir)

nrows, ncols = acc.shape
print(
    f"Raster : {nrows}x{ncols} | min={acc.min():.0f} | p95={np.percentile(acc, 95):.0f} | "
    f"p99={np.percentile(acc, 99):.0f} | max={acc.max():.0f}"
)


def tracer_amont(fdir_arr: np.ndarray, start_r: int, start_c: int) -> np.ndarray:
    """Remonte tous les pixels qui s'écoulent vers (start_r, start_c) selon D8_DELTA."""
    mask = np.zeros((nrows, ncols), dtype=bool)
    mask[start_r, start_c] = True
    q = deque([(start_r, start_c)])
    while q:
        r, c = q.popleft()
        for code, (dr, dc) in D8_DELTA.items():
            # Voisin amont (pr, pc) qui pointe vers (r, c) via (dr, dc)
            pr, pc = r - dr, c - dc
            if 0 <= pr < nrows and 0 <= pc < ncols and not mask[pr, pc]:
                if int(fdir_arr[pr, pc]) == code:
                    mask[pr, pc] = True
                    q.append((pr, pc))
    return mask


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

    mask_ws = tracer_amont(fdir, snap_r, snap_c)
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

        stream_mask = mask_ws & (acc >= SEUIL_STREAM)
        rs, cs = np.where(stream_mask)
        lines = []
        for r, c in zip(rs, cs):
            code = int(fdir[r, c])
            if code in D8_DELTA:
                dr, dc = D8_DELTA[code]
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
            out_str = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_reseau_wb.geojson")
            gdf_str.to_file(out_str, driver="GeoJSON")
            long_km = float(gdf_str.to_crs("EPSG:32735").length.sum() / 1e3)
            nb_troncons = len(lines)

    print(
        f"ID {rid} ({nom}) | exutoire=({snap_x:.6f}, {snap_y:.6f}) acc={acc[snap_r, snap_c]:.0f} | "
        f"point_dans_bassin={point_dans_bassin} | aire={aire_km2:.3f} km² | "
        f"tronçons={nb_troncons} | long={long_km:.3f} km"
    )