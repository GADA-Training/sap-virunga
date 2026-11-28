import os
from collections import deque
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from scipy.ndimage import grey_closing
from shapely.geometry import LineString, shape

CSV_PATH = "points_arcgis.csv"
DEM_PATH = "Copernicus_DEM_30m.tif"
OUT_DIR = "sorties_hydro_mnt"
SEUIL_ACCUMULATION = 100  # nombre minimal de pixels amont pour définir un cours d'eau

os.makedirs(OUT_DIR, exist_ok=True)

# Voisinage D8 : (d_row, d_col, code_esri)
D8_NEIGHBORS = [
    (0, 1, 1),     # Est
    (1, 1, 2),     # Sud-Est
    (1, 0, 4),     # Sud
    (1, -1, 8),    # Sud-Ouest
    (0, -1, 16),   # Ouest
    (-1, -1, 32),  # Nord-Ouest
    (-1, 0, 64),   # Nord
    (-1, 1, 128),  # Nord-Est
]
DIST_FACTOR = {
    1: 1.0,
    2: np.sqrt(2),
    4: 1.0,
    8: np.sqrt(2),
    16: 1.0,
    32: np.sqrt(2),
    64: 1.0,
    128: np.sqrt(2),
}


def condition_dem(elev: np.ndarray) -> np.ndarray:
    """Conditionnement léger du MNT pour limiter les cuvettes isolées sans lisser les vallées."""
    valid = ~np.isnan(elev)
    if not np.any(valid):
        return elev.copy()
    filled_nan = np.where(valid, elev, np.nanmax(elev))
    closed = grey_closing(filled_nan, size=(3, 3))
    out = np.maximum(filled_nan, closed)
    return np.where(valid, out, np.nan)


def compute_d8_flow_dir(elev: np.ndarray) -> np.ndarray:
    """Calcule la direction d'écoulement D8 (codes 1, 2, 4, 8, 16, 32, 64, 128 ; 0 = exutoire/plat)."""
    nrows, ncols = elev.shape
    fdir = np.zeros((nrows, ncols), dtype=np.int32)
    for r in range(nrows):
        for c in range(ncols):
            z0 = elev[r, c]
            if np.isnan(z0):
                continue
            best_slope = 0.0
            best_code = 0
            for dr, dc, code in D8_NEIGHBORS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < nrows and 0 <= nc < ncols:
                    z1 = elev[nr, nc]
                    if not np.isnan(z1):
                        slope = (z0 - z1) / DIST_FACTOR[code]
                        if slope > best_slope:
                            best_slope = slope
                            best_code = code
            fdir[r, c] = best_code
    return fdir


def compute_flow_accumulation(fdir: np.ndarray) -> np.ndarray:
    """Calcule l'accumulation de flux (nombre de cellules amont + 1 cellule propre)."""
    nrows, ncols = fdir.shape
    in_deg = np.zeros((nrows, ncols), dtype=np.int32)
    target_r = np.full((nrows, ncols), -1, dtype=np.int32)
    target_c = np.full((nrows, ncols), -1, dtype=np.int32)

    code_to_delta = {code: (dr, dc) for dr, dc, code in D8_NEIGHBORS}

    for r in range(nrows):
        for c in range(ncols):
            code = int(fdir[r, c])
            if code in code_to_delta:
                dr, dc = code_to_delta[code]
                nr, nc = r + dr, c + dc
                if 0 <= nr < nrows and 0 <= nc < ncols:
                    target_r[r, c] = nr
                    target_c[r, c] = nc
                    in_deg[nr, nc] += 1

    acc = np.ones((nrows, ncols), dtype=np.int32)
    q = deque()
    for r in range(nrows):
        for c in range(ncols):
            if in_deg[r, c] == 0:
                q.append((r, c))

    while q:
        r, c = q.popleft()
        nr, nc = target_r[r, c], target_c[r, c]
        if nr >= 0 and nc >= 0:
            acc[nr, nc] += acc[r, c]
            in_deg[nr, nc] -= 1
            if in_deg[nr, nc] == 0:
                q.append((nr, nc))

    return acc


def trace_upstream_catchment(fdir: np.ndarray, start_r: int, start_c: int) -> np.ndarray:
    """Retourne un masque booléen du bassin versant amont convergeant vers (start_r, start_c)."""
    nrows, ncols = fdir.shape
    visited = np.zeros((nrows, ncols), dtype=bool)
    visited[start_r, start_c] = True
    q = deque([(start_r, start_c)])

    while q:
        r, c = q.popleft()
        for dr, dc, code in D8_NEIGHBORS:
            pr, pc = r - dr, c - dc
            if 0 <= pr < nrows and 0 <= pc < ncols and not visited[pr, pc]:
                if int(fdir[pr, pc]) == code:
                    visited[pr, pc] = True
                    q.append((pr, pc))
    return visited


with rasterio.open(DEM_PATH) as src:
    dem = src.read(1).astype(np.float64)
    transform = src.transform
    crs = src.crs
    nodata = src.nodata
    meta = src.meta.copy()
    if nodata is not None:
        dem[dem == nodata] = np.nan

dem_cond = condition_dem(dem)
fdir = compute_d8_flow_dir(dem_cond)
acc = compute_flow_accumulation(fdir)

# Export des rasters Flow Direction et Flow Accumulation
meta.update({"dtype": "int32", "count": 1, "nodata": -9999})
with rasterio.open(os.path.join(OUT_DIR, "flow_direction.tif"), "w", **meta) as dst:
    dst.write(fdir.astype(np.int32), 1)
with rasterio.open(os.path.join(OUT_DIR, "flow_accumulation.tif"), "w", **meta) as dst:
    dst.write(acc.astype(np.int32), 1)

df = pd.read_csv(CSV_PATH)
rivers_df = df[df["ID"].isin([34, 35, 36])].copy()
code_to_delta = {code: (dr, dc) for dr, dc, code in D8_NEIGHBORS}

for _, row in rivers_df.iterrows():
    rid = int(row["ID"])
    nom_propre = str(row["Nom"]).strip().replace(" ", "_")
    lat = float(row["Latitude"])
    lon = float(row["Longitude"])

    print(f"\n=== ID {rid} : {row['Nom']} ({lat}, {lon}) ===")

    r0, c0 = rasterio.transform.rowcol(transform, lon, lat)
    r0 = int(np.clip(r0, 0, acc.shape[0] - 1))
    c0 = int(np.clip(c0, 0, acc.shape[1] - 1))

    # Calage de l'exutoire sur le pixel d'accumulation >= seuil le plus proche
    mask_streams = acc >= SEUIL_ACCUMULATION
    sr, sc = np.where(mask_streams)
    if len(sr) > 0:
        dist2 = (sr - r0) ** 2 + (sc - c0) ** 2
        idx_min = int(np.argmin(dist2))
        snap_r, snap_c = int(sr[idx_min]), int(sc[idx_min])
    else:
        snap_r, snap_c = r0, c0

    snap_x, snap_y = rasterio.transform.xy(transform, snap_r, snap_c, offset="center")
    print(f"  Exutoire calé : lon={snap_x:.6f}, lat={snap_y:.6f} (acc={acc[snap_r, snap_c]})")

    catch_mask = trace_upstream_catchment(fdir, snap_r, snap_c)
    stream_mask = catch_mask & mask_streams

    # Export du bassin versant en GeoJSON
    polys = [
        shape(geom)
        for geom, val in shapes(
            catch_mask.astype(np.uint8), mask=catch_mask, transform=transform
        )
        if val == 1
    ]
    if polys:
        gdf_catch = gpd.GeoDataFrame(
            {"id": [rid], "nom": [row["Nom"]], "geometry": [polys[0]]},
            crs=crs or "EPSG:4326",
        )
        out_bassin = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_bassin_mnt.geojson")
        gdf_catch.to_file(out_bassin, driver="GeoJSON")
        print(f"  Bassin exporté : {out_bassin} ({int(catch_mask.sum())} pixels)")

    # Extraction des liens du réseau hydrographique jusqu'à l'exutoire
    lines = []
    rs, cs = np.where(stream_mask)
    for r, c in zip(rs, cs):
        code = int(fdir[r, c])
        if code in code_to_delta:
            dr, dc = code_to_delta[code]
            nr, nc = r + dr, c + dc
            if 0 <= nr < fdir.shape[0] and 0 <= nc < fdir.shape[1] and catch_mask[nr, nc]:
                x1, y1 = rasterio.transform.xy(transform, r, c, offset="center")
                x2, y2 = rasterio.transform.xy(transform, nr, nc, offset="center")
                lines.append(LineString([(x1, y1), (x2, y2)]))

    if lines:
        gdf_streams = gpd.GeoDataFrame(
            {"id": [rid] * len(lines), "nom": [row["Nom"]] * len(lines), "geometry": lines},
            crs=crs or "EPSG:4326",
        )
        out_geojson = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_reseau_mnt.geojson")
        gdf_streams.to_file(out_geojson, driver="GeoJSON")
        print(f"  Réseau exporté : {len(gdf_streams)} lien(s) -> {out_geojson}")

    # Carte de contrôle (Flow Accumulation + réseau + exutoire)
    br, bc = np.where(catch_mask)
    pad_px = 15
    r_min = max(0, int(br.min()) - pad_px)
    r_max = min(acc.shape[0], int(br.max()) + pad_px + 1)
    c_min = max(0, int(bc.min()) - pad_px)
    c_max = min(acc.shape[1], int(bc.max()) + pad_px + 1)

    sub_acc = acc[r_min:r_max, c_min:c_max]
    left, top = rasterio.transform.xy(transform, r_min, c_min, offset="ul")
    right, bottom = rasterio.transform.xy(transform, r_max, c_max, offset="lr")

    fig, ax = plt.subplots(figsize=(7, 7))
    im = ax.imshow(np.log1p(sub_acc), extent=[left, right, bottom, top], cmap="Blues")
    for line in lines:
        xs, ys = line.xy
        ax.plot(xs, ys, color="navy", linewidth=1.1)
    ax.scatter([snap_x], [snap_y], color="red", s=55, zorder=5, label="Exutoire calé")
    ax.scatter([lon], [lat], color="orange", marker="x", s=55, zorder=6, label="Point initial")
    ax.set_title(f"{row['Nom']} — Flow Accumulation & Réseau (seuil={SEUIL_ACCUMULATION})")
    ax.set_xlabel("Longitude (°)")
    ax.set_ylabel("Latitude (°)")
    ax.legend(loc="best")
    plt.colorbar(im, ax=ax, label="log(1 + Accumulation)")
    plt.tight_layout()
    out_png = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_flow_acc.png")
    plt.savefig(out_png, dpi=200)
    plt.close(fig)
    print(f"  Aperçu enregistré -> {out_png}")