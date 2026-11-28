import glob
import os
import geopandas as gpd
import pandas as pd

WB_DIR = "sorties_whitebox_hydro"
MGH_DIR = "sorties_mghydro"
CSV_PATH = "points_arcgis.csv"

df_pts = pd.read_csv(CSV_PATH)
rivers_df = df_pts[df_pts["ID"].isin([34, 35, 36])].copy()

rows = []
for _, r in rivers_df.iterrows():
    rid = int(r["ID"])
    nom = str(r["Nom"]).strip()
    nom_propre = nom.replace(" ", "_")

    wb_bassin = os.path.join(WB_DIR, f"{rid}_{nom_propre}_bassin_wb.geojson")
    wb_reseau = os.path.join(WB_DIR, f"{rid}_{nom_propre}_reseau_wb.geojson")

    aire_wb = None
    if os.path.exists(wb_bassin):
        gdf_wb = gpd.read_file(wb_bassin)
        aire_wb = float(gdf_wb.to_crs("EPSG:32735").area.sum() / 1e6)

    # Recherche d'un GeoJSON correspondant dans sorties_mghydro
    mgh_matches = glob.glob(os.path.join(MGH_DIR, f"*{rid}*.geojson")) + glob.glob(
        os.path.join(MGH_DIR, f"*{nom_propre.lower()}*.geojson")
    )
    aire_mgh = None
    iou = None
    if mgh_matches and os.path.exists(wb_bassin):
        gdf_mgh = gpd.read_file(mgh_matches[0])
        if gdf_mgh.crs is None:
            gdf_mgh = gdf_mgh.set_crs("EPSG:4326")
        aire_mgh = float(gdf_mgh.to_crs("EPSG:32735").area.sum() / 1e6)

        g1 = gdf_wb.to_crs("EPSG:32735").geometry.union_all()
        g2 = gdf_mgh.to_crs("EPSG:32735").geometry.union_all()
        inter = g1.intersection(g2).area
        union = g1.union(g2).area
        iou = float(inter / union) if union > 0 else 0.0

    nb_str = len(gpd.read_file(wb_reseau)) if os.path.exists(wb_reseau) else 0
    rows.append({
        "ID": rid,
        "Rivière": nom,
        "Aire_WB_km2": round(aire_wb, 3) if aire_wb is not None else None,
        "Aire_MGH_km2": round(aire_mgh, 3) if aire_mgh is not None else None,
        "IoU_Bassin": round(iou, 3) if iou is not None else None,
        "Troncons_WB": nb_str,
    })

res_df = pd.DataFrame(rows)
print(res_df.to_string(index=False))