import json
import os
import time
import geopandas as gpd
import pandas as pd
import requests

CSV_PATH = "points_arcgis.csv"
OUT_DIR = "sorties_mghydro"
os.makedirs(OUT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "GADA-Training-HydroScript/1.0"}


def fetch_geojson(url: str) -> dict | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=45)
        if r.status_code != 200:
            print(f"  [HTTP {r.status_code}] Échec sur : {url}")
            return None
        data = r.json()
        if isinstance(data, dict) and data.get("type") == "FeatureCollection":
            return data
        print("  [Format inattendu] Réponse hors FeatureCollection GeoJSON.")
        return None
    except Exception as e:
        print(f"  [Erreur réseau/JSON] {e}")
        return None


df = pd.read_csv(CSV_PATH)
rivers_df = df[df["ID"].isin([34, 35, 36])].copy()

for _, row in rivers_df.iterrows():
    rid = int(row["ID"])
    nom_propre = str(row["Nom"]).strip().replace(" ", "_")
    lat = float(row["Latitude"])
    lon = float(row["Longitude"])

    print(f"\n=== ID {rid} : {row['Nom']} ({lat}, {lon}) ===")

    ws_url = f"https://mghydro.com/app/watershed_api?lat={lat}&lng={lon}&precision=high"
    ws_data = fetch_geojson(ws_url)
    if ws_data:
        ws_path = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_bassin.geojson")
        with open(ws_path, "w", encoding="utf-8") as f:
            json.dump(ws_data, f)
        gdf_ws = gpd.read_file(ws_path)
        print(f"  [OK] Bassin -> {ws_path} ({len(gdf_ws)} entité(s))")

    time.sleep(1.5)

    rv_url = f"https://mghydro.com/app/upstream_rivers_api?lat={lat}&lng={lon}&precision=high"
    rv_data = fetch_geojson(rv_url)
    if rv_data:
        rv_path = os.path.join(OUT_DIR, f"{rid}_{nom_propre}_rivieres.geojson")
        with open(rv_path, "w", encoding="utf-8") as f:
            json.dump(rv_data, f)
        gdf_rv = gpd.read_file(rv_path)
        print(f"  [OK] Rivières -> {rv_path} ({len(gdf_rv)} tronçon(s))")

    time.sleep(1.5)
