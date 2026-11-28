import glob
import os
import geopandas as gpd

UTM_EPSG = 32735  # UTM Zone 35S (à vérifier selon la zone exacte)

files = sorted(glob.glob(os.path.join("sorties_mghydro", "*.geojson")))
for fp in files:
    gdf = gpd.read_file(fp)
    if gdf.empty:
        print(f"{os.path.basename(fp)} -> VIDE")
        continue
    gdf_utm = gdf.to_crs(epsg=UTM_EPSG)
    geom_types = gdf.geom_type.value_counts().to_dict()
    if gdf_utm.geom_type.isin(["Polygon", "MultiPolygon"]).any():
        area_km2 = gdf_utm.area.sum() / 1e6
        print(
            f"{os.path.basename(fp)} | entités={len(gdf)} | "
            f"types={geom_types} | aire={area_km2:.3f} km²"
        )
    else:
        len_km = gdf_utm.length.sum() / 1e3
        print(
            f"{os.path.basename(fp)} | entités={len(gdf)} | "
            f"tronçons={len(gdf)} | types={geom_types} | long_totale={len_km:.3f} km"
        )