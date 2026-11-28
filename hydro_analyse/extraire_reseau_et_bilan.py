import os
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import LineString
import whitebox

CSV_PATH = "points_arcgis.csv"
DEM_PATH = "Copernicus_DEM_30m.tif"
OUT_DIR = "sorties_whitebox_hydro"
MGH_DIR = "sorties_mghydro"

SEUIL_STREAM = 50       # ajustez (ex. 20, 50, 100) selon la densité du réseau
RAYON_SNAP_PX = 20

wb = whitebox.WhiteboxTools()
wb.verbose = False

dem_abs = os.path.abspath(DEM_PATH)
breach_abs = os.path.abspath(os.path.join(OUT_DIR, "dem_breached.tif"))
fdir_abs = os.path.abspath(os.path.join(OUT_DIR, "d8_pointer.tif"))
facc_abs = os.path.abspath(os.path.join(OUT_DIR, "d8_flow_acc.tif"))

# Recalcul propre si nécessaire
if not (os.path.exists(fdir_abs) and os.path.exists(facc_abs)):
    assert wb.breach_depressions(dem=dem_abs, output=breach_abs) == 0
    assert wb.d8_pointer(dem=breach_abs, output=fdir_abs) == 0
    assert wb.d8_flow_accumulation(i=fdir_abs, out_type="cells", output=facc_abs) == 0

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

# Correspondance des codes Whitebox D8 (1, 2, 4, 8, 16, 32, 64, 128) -> (d_row, d_col)
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

nrows, ncols = acc.shape
df = pd.read_csv(CSV_PATH)
rivers_df = df[df["ID"].isin([34, 35, 36])].copy()

print(f"Max flow accumulation sur le MNT : {acc.max():.0f} cellules | Seuil : {SEUIL_STREAM}")

for _, row in rivers_df.iterrows():
    rid = int(row["ID"])
    nom = str(row["Nom"]).strip()
    nom_propre = nom.replace(" ", "_")
    lat = float(row["Latitude"])
    lon = float(row["Longitude"])

    bassin_path = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_bassin_wb.geojson")
    if not os.path.exists(bassin_path):
        print(f"ID {rid} ({nom}) : bassin introuvable.")
        continue

    gdf_ws = gpd.read_file(bassin_path)
    minx, miny, maxx, maxy = gdf_ws.total_bounds
    touche_bord_mnt = (
        abs(minx - transform.c) < 1e-4
        or abs(maxx - (transform.c + ncols * transform.a)) < 1e-4
        or abs(maxy - transform.f) < 1e-4
        or abs(miny - (transform.f + nrows * transform.e)) < 1e-4
    )

    # Masque des pixels appartenant au bassin
    from rasterio.features import geometry_mask
    mask_ws = ~geometry_mask(
        gdf_ws.geometry, out_shape=(nrows, ncols), transform=transform, invert=False
    )

    # Calage de l'exutoire dans le bassin sur le pixel à plus forte accumulation
    r0, c0 = rasterio.transform.rowcol(transform, lon, lat)
    r0 = int(np.clip(r0, 0, nrows - 1))
    c0 = int(np.clip(c0, 0, ncols - 1))

    r_min = max(0, r0 - RAYON_SNAP_PX)
    r_max = min(nrows, r0 + RAYON_SNAP_PX + 1)
    c_min = max(0, c0 - RAYON_SNAP_PX)
    c_max = min(ncols, c0 + RAYON_SNAP_PX + 1)

    sub_acc = np.where(mask_ws[r_min:r_max, c_min:c_max], acc[r_min:r_max, c_min:c_max], -1.0)
    best_idx = int(np.argmax(sub_acc))
    snap_r, snap_c = np.unravel_index(best_idx, sub_acc.shape)
    snap_r += r_min
    snap_c += c_min
    snap_x, snap_y = rasterio.transform.xy(transform, snap_r, snap_c, offset="center")

    # Extraction du réseau (pixels du bassin avec acc >= SEUIL_STREAM reliés à leur pixel aval)
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

    long_km = 0.0
    if lines:
        gdf_str = gpd.GeoDataFrame(
            {"id": [rid] * len(lines), "nom": [nom] * len(lines), "geometry": lines},
            crs=crs or "EPSG:4326",
        )
        out_str = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_reseau_wb.geojson")
        gdf_str.to_file(out_str, driver="GeoJSON")
        long_km = float(gdf_str.to_crs("EPSG:32735").length.sum() / 1e3)

    aire_km2 = float(gdf_ws.to_crs("EPSG:32735").area.sum() / 1e6)
    print(
        f"ID {rid} ({nom}) | exutoire=({snap_x:.6f}, {snap_y:.6f}) acc={acc[snap_r, snap_c]:.0f} | "
        f"aire={aire_km2:.3f} km² | tronçons={len(lines)} | long={long_km:.3f} km | "
        f"touche_bord_mnt={touche_bord_mnt}"
    )