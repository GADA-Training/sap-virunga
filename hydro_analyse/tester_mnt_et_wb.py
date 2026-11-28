import os
import numpy as np
import rasterio
import whitebox

DEM_PATH = "Copernicus_DEM_30m.tif"
OUT_DIR = "sorties_whitebox_hydro"
os.makedirs(OUT_DIR, exist_ok=True)

with rasterio.open(DEM_PATH) as src:
    dem = src.read(1).astype(np.float64)
    nodata = src.nodata
    crs = src.crs
    res = src.res

valid = ~np.isnan(dem)
if nodata is not None:
    valid &= dem != nodata

print(f"CRS : {crs} | Résolution : {res} | Pixels valides : {int(valid.sum())}/{dem.size}")
if valid.any():
    print(f"Altitude min/max : {dem[valid].min():.1f} m / {dem[valid].max():.1f} m")

wb = whitebox.WhiteboxTools()
wb.verbose = False

dem_abs = os.path.abspath(DEM_PATH)
fdir_abs = os.path.abspath(os.path.join(OUT_DIR, "diag_d8_pntr.tif"))
facc_abs = os.path.abspath(os.path.join(OUT_DIR, "diag_d8_acc.tif"))

# Test avec fill_depressions en plus de breach_depressions
breached_abs = os.path.abspath(os.path.join(OUT_DIR, "diag_breach.tif"))
filled_abs = os.path.abspath(os.path.join(OUT_DIR, "diag_fill.tif"))

wb.breach_depressions(dem=dem_abs, output=breached_abs)
wb.fill_depressions(dem=breached_abs, output=filled_abs)
wb.d8_pointer(dem=filled_abs, output=fdir_abs)
wb.d8_flow_accumulation(i=fdir_abs, out_type="cells", output=facc_abs)

with rasterio.open(fdir_abs) as s_dir:
    d_arr = s_dir.read(1)
    vals_dir, counts_dir = np.unique(d_arr, return_counts=True)
    print("Valeurs uniques d8_pointer :", dict(zip(vals_dir.tolist(), counts_dir.tolist())))

with rasterio.open(facc_abs) as s_acc:
    a_arr = s_acc.read(1)
    a_valid = a_arr[a_arr != s_acc.nodata] if s_acc.nodata is not None else a_arr.ravel()
    print(f"Accumulation : min={a_valid.min()} | p50={np.percentile(a_valid, 50):.0f} | p99={np.percentile(a_valid, 99):.0f} | max={a_valid.max()}")