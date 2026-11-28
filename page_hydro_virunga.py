import glob
import io
import os
import tempfile
import zipfile
import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import streamlit as st
from streamlit_folium import st_folium

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HYDRO_DIR = os.path.join(BASE_DIR, "hydro_analyse")
WB_DIR = os.path.join(HYDRO_DIR, "sorties_whitebox_hydro")
MGH_DIR = os.path.join(HYDRO_DIR, "sorties_mghydro")
CSV_PATH = os.path.join(HYDRO_DIR, "points_arcgis.csv")
FACC_PATH = os.path.join(WB_DIR, "wb_d8_acc.tif")

FONDS_CARTE = {
    "Relief / Topographie": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri World Topo",
    },
    "Satellite (Esri)": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri World Imagery",
    },
    "OpenStreetMap": {
        "tiles": "OpenStreetMap",
        "attr": "OpenStreetMap",
    },
}

THEMES_VISUELS = {
    "Océan Virunga (Glass Dark)": {
        "bg_grad": "linear-gradient(135deg, rgba(10, 22, 68, 0.88) 0%, rgba(18, 46, 118, 0.84) 55%, rgba(11, 28, 78, 0.92) 100%)",
        "card_bg": "rgba(16, 36, 94, 0.65)",
        "card_border": "rgba(125, 175, 255, 0.28)",
        "neo_shadow": "8px 8px 20px rgba(4, 10, 32, 0.65), -5px -5px 14px rgba(66, 122, 225, 0.14)",
        "accent": "#38bdf8",
        "text": "#f8fafc",
        "muted": "#cbd5e1",
        "ws_color": "#38bdf8",
        "ws_fill": "#0284c7",
        "str_color": "#22d3ee",
        "mpl_bg": "#0b1942",
        "mpl_fg": "#e2e8f0",
    },
    "Nébuleuse Indigo (Néomorphisme)": {
        "bg_grad": "linear-gradient(135deg, rgba(16, 24, 76, 0.90) 0%, rgba(36, 48, 128, 0.84) 50%, rgba(13, 20, 62, 0.94) 100%)",
        "card_bg": "rgba(24, 35, 96, 0.68)",
        "card_border": "rgba(165, 180, 252, 0.30)",
        "neo_shadow": "10px 10px 22px rgba(6, 10, 34, 0.72), -6px -6px 16px rgba(99, 102, 241, 0.16)",
        "accent": "#818cf8",
        "text": "#f1f5f9",
        "muted": "#cbd5e1",
        "ws_color": "#60a5fa",
        "ws_fill": "#2563eb",
        "str_color": "#38bdf8",
        "mpl_bg": "#111b4d",
        "mpl_fg": "#f1f5f9",
    },
    "Émeraude Kivu (Topographie)": {
        "bg_grad": "linear-gradient(135deg, rgba(7, 42, 56, 0.90) 0%, rgba(14, 74, 86, 0.84) 55%, rgba(8, 34, 48, 0.94) 100%)",
        "card_bg": "rgba(11, 58, 72, 0.66)",
        "card_border": "rgba(94, 234, 212, 0.28)",
        "neo_shadow": "8px 8px 20px rgba(3, 18, 26, 0.68), -5px -5px 14px rgba(45, 212, 191, 0.14)",
        "accent": "#2dd4bf",
        "text": "#f0fdfa",
        "muted": "#ccfbf1",
        "ws_color": "#2dd4bf",
        "ws_fill": "#0d9488",
        "str_color": "#67e8f9",
        "mpl_bg": "#092c38",
        "mpl_fg": "#f0fdfa",
    },
}


def _injecter_style_glass_neo(theme: dict) -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {theme["bg_grad"]};
            color: {theme["text"]};
        }}
        .hydro-glass-hero {{
            background: {theme["card_bg"]};
            backdrop-filter: blur(12px);
            border: 1px solid {theme["card_border"]};
            border-radius: 16px;
            padding: 16px 20px;
            margin-bottom: 14px;
            box-shadow: {theme["neo_shadow"]};
        }}
        .hydro-glass-hero h2 {{
            margin: 0 0 4px 0;
            font-weight: 700;
            color: {theme["text"]};
        }}
        .hydro-glass-hero p {{
            margin: 0;
            color: {theme["muted"]};
            font-size: 0.92rem;
        }}
        .hydro-neo-card {{
            background: {theme["card_bg"]};
            backdrop-filter: blur(10px);
            border: 1px solid {theme["card_border"]};
            border-radius: 14px;
            padding: 14px 16px;
            margin-bottom: 12px;
            box-shadow: {theme["neo_shadow"]};
        }}
        .hydro-metric-label {{
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {theme["muted"]};
        }}
        .hydro-metric-val {{
            font-size: 1.5rem;
            font-weight: 700;
            color: {theme["accent"]};
        }}
        .hydro-metric-sub {{
            font-size: 0.78rem;
            color: {theme["muted"]};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data
def charger_points() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    return df[df["ID"].isin([34, 35, 36])].copy()


@st.cache_data
def charger_couches_riviere(rid: int, nom: str):
    nom_propre = str(nom).strip().replace(" ", "_")
    bassin_wb_path = os.path.join(WB_DIR, f"{rid}_{nom_propre}_bassin_wb.geojson")
    reseau_wb_path = os.path.join(WB_DIR, f"{rid}_{nom_propre}_reseau_wb.geojson")

    gdf_bassin_wb = gpd.read_file(bassin_wb_path) if os.path.exists(bassin_wb_path) else None
    gdf_reseau_wb = gpd.read_file(reseau_wb_path) if os.path.exists(reseau_wb_path) else None

    mgh_matches = glob.glob(os.path.join(MGH_DIR, f"*{rid}*.geojson")) + glob.glob(
        os.path.join(MGH_DIR, f"*{nom_propre.lower()}*.geojson")
    )
    gdf_bassin_mgh = gpd.read_file(mgh_matches[0]) if mgh_matches else None

    for gdf in (gdf_bassin_wb, gdf_reseau_wb, gdf_bassin_mgh):
        if gdf is not None and len(gdf) > 0 and gdf.crs is None:
            gdf.set_crs("EPSG:4326", inplace=True)

    aire_wb = (
        float(gdf_bassin_wb.to_crs("EPSG:32735").area.sum() / 1e6)
        if gdf_bassin_wb is not None and len(gdf_bassin_wb) > 0
        else 0.0
    )
    aire_mgh = (
        float(gdf_bassin_mgh.to_crs("EPSG:32735").area.sum() / 1e6)
        if gdf_bassin_mgh is not None and len(gdf_bassin_mgh) > 0
        else None
    )

    if gdf_reseau_wb is not None and len(gdf_reseau_wb) > 0:
        gdf_reseau_wb = gdf_reseau_wb.copy()
        gdf_reseau_wb["long_km"] = gdf_reseau_wb.to_crs("EPSG:32735").length / 1e3
        if os.path.exists(FACC_PATH):
            with rasterio.open(FACC_PATH) as src_acc:
                acc_arr = src_acc.read(1)
                nodata = src_acc.nodata
                inv_transform = ~src_acc.transform
                nrows, ncols = acc_arr.shape
                mids = gdf_reseau_wb.geometry.interpolate(0.5, normalized=True)
                xs = mids.x.to_numpy()
                ys = mids.y.to_numpy()
                cols, rows = inv_transform * (xs, ys)
                r_idx = np.floor(rows).astype(np.int64)
                c_idx = np.floor(cols).astype(np.int64)
                valid = (r_idx >= 0) & (r_idx < nrows) & (c_idx >= 0) & (c_idx < ncols)
                acc_vals = np.zeros(len(gdf_reseau_wb), dtype=np.int64)
                v_vals = acc_arr[r_idx[valid], c_idx[valid]]
                if nodata is not None:
                    v_vals = np.where(v_vals == nodata, 0, v_vals)
                acc_vals[valid] = v_vals.astype(np.int64)
                gdf_reseau_wb["acc_estimee"] = acc_vals
        else:
            gdf_reseau_wb["acc_estimee"] = 100

    bassin_json = (
        gdf_bassin_wb.to_crs("EPSG:4326").__geo_interface__
        if gdf_bassin_wb is not None and len(gdf_bassin_wb) > 0
        else None
    )
    mgh_json = (
        gdf_bassin_mgh.to_crs("EPSG:4326").__geo_interface__
        if gdf_bassin_mgh is not None and len(gdf_bassin_mgh) > 0
        else None
    )

    return gdf_bassin_wb, gdf_reseau_wb, gdf_bassin_mgh, aire_wb, aire_mgh, bassin_json, mgh_json


@st.cache_data
def verifier_point_dans_bassin_cached(rid: int, nom: str, lon: float, lat: float) -> bool:
    gdf_bassin, _, _, _, _, _, _ = charger_couches_riviere(rid, nom)
    if gdf_bassin is None or len(gdf_bassin) == 0:
        return False
    pt_gdf = gpd.GeoDataFrame(geometry=gpd.points_from_xy([lon], [lat]), crs="EPSG:4326")
    return bool(gpd.sjoin(pt_gdf, gdf_bassin.to_crs("EPSG:4326"), predicate="within").shape[0] > 0)


@st.cache_data
def _figure_comparaison_bassins(theme_nom: str) -> plt.Figure:
    theme = THEMES_VISUELS[theme_nom]
    df_pts = charger_points()
    noms, aires_wb, aires_mgh = [], [], []
    for _, r in df_pts.iterrows():
        rid = int(r["ID"])
        nom = str(r["Nom"]).strip()
        noms.append(nom.replace("Riviere ", ""))
        _, _, _, a_wb, a_mgh, _, _ = charger_couches_riviere(rid, nom)
        aires_wb.append(a_wb)
        aires_mgh.append(a_mgh or 0.0)

    x = np.arange(len(noms))
    w = 0.36
    fig, ax = plt.subplots(figsize=(6.0, 3.1), dpi=115)
    fig.patch.set_facecolor(theme["mpl_bg"])
    ax.set_facecolor(theme["mpl_bg"])

    b1 = ax.bar(x - w / 2, aires_wb, width=w, label="Whitebox (DEM 30m)", color=theme["accent"])
    b2 = ax.bar(x + w / 2, aires_mgh, width=w, label="Référence mghydro", color="#34d399")

    ax.set_xticks(x)
    ax.set_xticklabels(noms, color=theme["mpl_fg"], fontsize=9)
    ax.set_ylabel("Superficie (km²)", color=theme["mpl_fg"], fontsize=9)
    ax.set_title("Superficies des bassins versants", color=theme["mpl_fg"], fontsize=10, pad=8)
    ax.tick_params(colors=theme["mpl_fg"], labelsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.22, color=theme["mpl_fg"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(theme["mpl_fg"])
    ax.spines["bottom"].set_color(theme["mpl_fg"])
    ax.legend(frameon=False, labelcolor=theme["mpl_fg"], fontsize=8)

    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + max(aires_wb + aires_mgh + [1]) * 0.02,
                f"{h:.1f}",
                ha="center",
                va="bottom",
                color=theme["mpl_fg"],
                fontsize=7.5,
            )
    fig.tight_layout()
    return fig


@st.cache_data
def _figure_profil_accumulation(rid: int, nom: str, seuil_acc: int, theme_nom: str) -> plt.Figure:
    theme = THEMES_VISUELS[theme_nom]
    _, gdf_reseau, _, _, _, _, _ = charger_couches_riviere(rid, nom)
    fig, ax = plt.subplots(figsize=(6.0, 3.1), dpi=115)
    fig.patch.set_facecolor(theme["mpl_bg"])
    ax.set_facecolor(theme["mpl_bg"])

    if gdf_reseau is not None and len(gdf_reseau) > 0 and "acc_estimee" in gdf_reseau.columns:
        vals = gdf_reseau["acc_estimee"].to_numpy()
        vals = vals[vals > 0]
        if len(vals) > 0:
            ax.hist(np.log10(vals), bins=20, color=theme["accent"], alpha=0.85, edgecolor=theme["mpl_bg"])
            ax.axvline(np.log10(max(1, seuil_acc)), color="#fbbf24", linestyle="--", linewidth=1.6, label=f"Seuil ({seuil_acc})")
            ax.set_xlabel("log10(Accumulation en cellules)", color=theme["mpl_fg"], fontsize=8.5)
            ax.set_ylabel("Tronçons", color=theme["mpl_fg"], fontsize=8.5)
            ax.set_title("Distribution hydraulique des tronçons", color=theme["mpl_fg"], fontsize=10, pad=8)
            ax.legend(frameon=False, labelcolor=theme["mpl_fg"], fontsize=8)
        else:
            ax.text(0.5, 0.5, "Aucun tronçon actif", ha="center", va="center", color=theme["mpl_fg"])
    else:
        ax.text(0.5, 0.5, "Données indisponibles", ha="center", va="center", color=theme["mpl_fg"])

    ax.tick_params(colors=theme["mpl_fg"], labelsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.22, color=theme["mpl_fg"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(theme["mpl_fg"])
    ax.spines["bottom"].set_color(theme["mpl_fg"])
    fig.tight_layout()
    return fig


def _gdf_to_shp_zip_bytes(gdf: gpd.GeoDataFrame, prefixe: str) -> bytes:
    gdf_4326 = gdf.to_crs("EPSG:4326").copy()
    rename_map = {}
    seen = set()
    for col in gdf_4326.columns:
        if col == "geometry":
            continue
        short = str(col)[:10]
        base_short = short
        idx = 1
        while short in seen:
            suffix = f"_{idx}"
            short = f"{base_short[: max(1, 10 - len(suffix))]}{suffix}"
            idx += 1
        seen.add(short)
        rename_map[col] = short
    gdf_4326 = gdf_4326.rename(columns=rename_map)

    mem_zip = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = os.path.join(tmpdir, f"{prefixe}.shp")
        gdf_4326.to_file(shp_path, driver="ESRI Shapefile")
        with zipfile.ZipFile(mem_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(tmpdir):
                if fname.startswith(f"{prefixe}."):
                    zf.write(os.path.join(tmpdir, fname), arcname=fname)
    mem_zip.seek(0)
    return mem_zip.getvalue()


def _gdf_to_ext_bytes(gdf: gpd.GeoDataFrame, driver: str, ext: str, layer_name: str = "couche") -> bytes:
    gdf_4326 = gdf.to_crs("EPSG:4326")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, f"export.{ext}")
        if driver == "GPKG":
            gdf_4326.to_file(out_path, driver=driver, layer=layer_name)
        else:
            gdf_4326.to_file(out_path, driver=driver)
        with open(out_path, "rb") as f:
            return f.read()


@st.cache_data
def preparer_exports_riviere(
    rid: int,
    nom: str,
    seuil_acc: int,
    lat_init: float,
    lon_init: float,
    dans_bassin: bool,
    aire_wb: float,
    aire_mgh: float | None,
    nb_troncons: int,
    long_km: float,
    densite_drainage: float,
):
    nom_propre = str(nom).strip().replace(" ", "_")
    prefixe = f"{rid}_{nom_propre}"
    gdf_bassin, gdf_reseau_all, gdf_mgh, _, _, _, _ = charger_couches_riviere(rid, nom)
    gdf_reseau = (
        gdf_reseau_all[gdf_reseau_all["acc_estimee"] >= seuil_acc]
        if gdf_reseau_all is not None and "acc_estimee" in gdf_reseau_all.columns
        else gdf_reseau_all
    )

    df_stats = pd.DataFrame([{
        "id": rid,
        "riviere": nom,
        "latitude": lat_init,
        "longitude": lon_init,
        "seuil_accumulation": seuil_acc,
        "point_dans_bassin": dans_bassin,
        "aire_whitebox_km2": round(aire_wb, 4),
        "aire_mghydro_km2": round(aire_mgh, 4) if aire_mgh is not None else None,
        "nb_troncons": nb_troncons,
        "longueur_reseau_km": round(long_km, 4),
        "densite_drainage_km_km2": round(densite_drainage, 4),
    }])

    csv_bytes = df_stats.to_csv(index=False).encode("utf-8-sig")
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        df_stats.to_excel(writer, index=False, sheet_name="Statistiques")
    xlsx_bytes = excel_buf.getvalue()

    exports = {"csv": csv_bytes, "xlsx": xlsx_bytes, "bassin": {}, "reseau": {}, "all_zip": b""}

    if gdf_bassin is not None and len(gdf_bassin) > 0:
        exports["bassin"]["shp_zip"] = _gdf_to_shp_zip_bytes(gdf_bassin, f"{prefixe}_bassin")
        exports["bassin"]["geojson"] = _gdf_to_ext_bytes(gdf_bassin, "GeoJSON", "geojson")
        for drv, ext, lyr in [("GPKG", "gpkg", "bassin"), ("KML", "kml", None)]:
            try:
                exports["bassin"][ext] = _gdf_to_ext_bytes(gdf_bassin, drv, ext, layer_name=lyr or "couche")
            except Exception:
                pass

    if gdf_reseau is not None and len(gdf_reseau) > 0:
        exports["reseau"]["shp_zip"] = _gdf_to_shp_zip_bytes(gdf_reseau, f"{prefixe}_cours_eau")
        exports["reseau"]["geojson"] = _gdf_to_ext_bytes(gdf_reseau, "GeoJSON", "geojson")
        for drv, ext, lyr in [("GPKG", "gpkg", "cours_eau"), ("KML", "kml", None)]:
            try:
                exports["reseau"][ext] = _gdf_to_ext_bytes(gdf_reseau, drv, ext, layer_name=lyr or "couche")
            except Exception:
                pass

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{prefixe}_statistiques.csv", csv_bytes)
        zf.writestr(f"{prefixe}_statistiques.xlsx", xlsx_bytes)
        for ext, b in exports["bassin"].items():
            name = f"{prefixe}_bassin_shapefile.zip" if ext == "shp_zip" else f"{prefixe}_bassin.{ext}"
            zf.writestr(name, b)
        for ext, b in exports["reseau"].items():
            name = f"{prefixe}_cours_eau_shapefile.zip" if ext == "shp_zip" else f"{prefixe}_cours_eau.{ext}"
            zf.writestr(name, b)
        if gdf_mgh is not None and len(gdf_mgh) > 0:
            zf.writestr(f"{prefixe}_reference_mghydro.geojson", _gdf_to_ext_bytes(gdf_mgh, "GeoJSON", "geojson"))
    mem_zip.seek(0)
    exports["all_zip"] = mem_zip.getvalue()
    return exports


def rendre_page_hydro():
    if not os.path.exists(CSV_PATH):
        st.error(f"Fichier introuvable : {CSV_PATH}")
        return

    df_pts = charger_points()
    choix_options = {f"ID {int(r['ID'])} — {r['Nom']}": r for _, r in df_pts.iterrows()}

    with st.sidebar:
        st.markdown("### Hydrologie Virunga")
        choix_label = st.selectbox("Cours d'eau", list(choix_options.keys()), key="hydro_riviere_sel")
        fond_nom = st.selectbox("Fond cartographique", list(FONDS_CARTE.keys()), key="hydro_fond_sel")
        seuil_acc = st.slider(
            "Seuil minimal d'accumulation (cellules)",
            min_value=10,
            max_value=5000,
            value=50,
            step=10,
            key="hydro_seuil_slider",
        )
        theme_nom = st.selectbox("Ambiance glass/néo", list(THEMES_VISUELS.keys()), key="hydro_theme_sel")
        afficher_mgh = st.checkbox("Superposer bassin mghydro", value=True, key="hydro_mgh_chk")
        afficher_visuels = st.checkbox("Afficher graphiques de mesures", value=True, key="hydro_vis_chk")

    theme = THEMES_VISUELS[theme_nom]
    fond = FONDS_CARTE[fond_nom]
    _injecter_style_glass_neo(theme)

    row = choix_options[choix_label]
    rid = int(row["ID"])
    nom = str(row["Nom"]).strip()
    nom_propre = nom.replace(" ", "_")
    prefixe = f"{rid}_{nom_propre}"
    lat_init = float(row["Latitude"])
    lon_init = float(row["Longitude"])

    st.markdown(
        f"""
        <div class="hydro-glass-hero">
            <h2>Hydrologie Locale — {nom} (ID {rid})</h2>
            <p>Copernicus DEM 30 m • Fond : {fond_nom} • Coordonnées initiales : {lat_init:.5f}, {lon_init:.5f}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, gdf_reseau_all, _, aire_wb, aire_mgh, bassin_json, mgh_json = charger_couches_riviere(rid, nom)
    dans_bassin = verifier_point_dans_bassin_cached(rid, nom, lon_init, lat_init)

    if not dans_bassin:
        st.warning("Alerte topologique : le point initial ne se trouve pas à l'intérieur du bassin versant extrait.")
    else:
        st.success("Validation topologique : point initial cohérent avec le bassin versant extrait.")

    if gdf_reseau_all is not None and len(gdf_reseau_all) > 0:
        reseau_filtre = gdf_reseau_all[gdf_reseau_all["acc_estimee"] >= seuil_acc]
        nb_troncons = int(len(reseau_filtre))
        long_km = float(reseau_filtre["long_km"].sum()) if nb_troncons > 0 else 0.0
    else:
        reseau_filtre = None
        nb_troncons = 0
        long_km = 0.0

    densite_drainage = (long_km / aire_wb) if aire_wb > 0 else 0.0

    m1, m2, m3, m4 = st.columns(4)
    for col, lbl, val, sub in [
        (m1, "Aire Whitebox", f"{aire_wb:.3f} km²", f"{aire_wb * 100:.0f} ha"),
        (m2, "Référence mghydro", f"{aire_mgh:.3f} km²" if aire_mgh is not None else "N/A", "Comparaison bassin"),
        (m3, "Longueur cours d'eau", f"{long_km:.2f} km", f"{nb_troncons} tronçons (acc ≥ {seuil_acc})"),
        (m4, "Densité de drainage", f"{densite_drainage:.2f} km/km²", "Réseau extrait / Aire"),
    ]:
        with col:
            st.markdown(
                f"""
                <div class="hydro-neo-card">
                    <div class="hydro-metric-label">{lbl}</div>
                    <div class="hydro-metric-val">{val}</div>
                    <div class="hydro-metric-sub">{sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="hydro-neo-card">', unsafe_allow_html=True)
    m = folium.Map(location=[lat_init, lon_init], zoom_start=11, tiles=None)
    folium.TileLayer(
        tiles=fond["tiles"],
        attr=fond["attr"],
        name=fond_nom,
        show=True,
        overlay=False,
        control=False,
    ).add_to(m)

    if bassin_json is not None:
        folium.GeoJson(
            bassin_json,
            name="Bassin Whitebox (DEM 30m)",
            style_function=lambda _, t=theme: {
                "color": t["ws_color"],
                "weight": 2.5,
                "fillColor": t["ws_fill"],
                "fillOpacity": 0.22,
            },
        ).add_to(m)

    if afficher_mgh and mgh_json is not None:
        folium.GeoJson(
            mgh_json,
            name="Bassin référence mghydro",
            style_function=lambda _: {
                "color": "#34d399",
                "weight": 2,
                "dashArray": "5, 5",
                "fillOpacity": 0.05,
            },
        ).add_to(m)

    if reseau_filtre is not None and len(reseau_filtre) > 0:
        folium.GeoJson(
            reseau_filtre.to_crs("EPSG:4326").__geo_interface__,
            name=f"Cours d'eau (acc ≥ {seuil_acc})",
            style_function=lambda _, t=theme: {"color": t["str_color"], "weight": 2},
        ).add_to(m)

    folium.Marker(
        location=[lat_init, lon_init],
        popup=f"{nom} (ID {rid})",
        tooltip=f"Point initial — {nom}",
        icon=folium.Icon(color="orange", icon="info-sign"),
    ).add_to(m)

    st_folium(m, width="100%", height=470, returned_objects=[])
    st.markdown("</div>", unsafe_allow_html=True)

    if afficher_visuels:
        g1, g2 = st.columns(2)
        with g1:
            st.markdown('<div class="hydro-neo-card">', unsafe_allow_html=True)
            fig_comp = _figure_comparaison_bassins(theme_nom)
            st.pyplot(fig_comp, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        with g2:
            st.markdown('<div class="hydro-neo-card">', unsafe_allow_html=True)
            fig_acc = _figure_profil_accumulation(rid, nom, seuil_acc, theme_nom)
            st.pyplot(fig_acc, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="hydro-neo-card">', unsafe_allow_html=True)
    st.markdown("### Exporter les données (Shapefile, Cours d'eau, GeoJSON, GPKG, KML, CSV, XLSX)")

    exp = preparer_exports_riviere(
        rid, nom, seuil_acc, lat_init, lon_init, dans_bassin, aire_wb, aire_mgh, nb_troncons, long_km, densite_drainage
    )

    c_exp1, c_exp2, c_exp3 = st.columns(3)

    with c_exp1:
        st.markdown("**Bassin versant**")
        if "shp_zip" in exp["bassin"]:
            st.download_button("Shapefile Bassin (.zip)", data=exp["bassin"]["shp_zip"], file_name=f"{prefixe}_bassin_shapefile.zip", mime="application/zip", key=f"exp_shp_ws_{rid}")
        if "geojson" in exp["bassin"]:
            st.download_button("GeoJSON Bassin (.geojson)", data=exp["bassin"]["geojson"], file_name=f"{prefixe}_bassin.geojson", mime="application/geo+json", key=f"exp_gj_ws_{rid}")
        for ext, lbl in [("gpkg", "GeoPackage Bassin (.gpkg)"), ("kml", "KML Bassin (.kml)")]:
            if ext in exp["bassin"]:
                st.download_button(lbl, data=exp["bassin"][ext], file_name=f"{prefixe}_bassin.{ext}", key=f"exp_{ext}_ws_{rid}")

    with c_exp2:
        st.markdown("**Cours d'eau / Réseau**")
        if "shp_zip" in exp["reseau"]:
            st.download_button("Shapefile Cours d'eau (.zip)", data=exp["reseau"]["shp_zip"], file_name=f"{prefixe}_cours_eau_shapefile.zip", mime="application/zip", key=f"exp_shp_str_{rid}_{seuil_acc}")
        if "geojson" in exp["reseau"]:
            st.download_button("GeoJSON Cours d'eau (.geojson)", data=exp["reseau"]["geojson"], file_name=f"{prefixe}_cours_eau.geojson", mime="application/geo+json", key=f"exp_gj_str_{rid}_{seuil_acc}")
        for ext, lbl in [("gpkg", "GeoPackage Cours d'eau (.gpkg)"), ("kml", "KML Cours d'eau (.kml)")]:
            if ext in exp["reseau"]:
                st.download_button(lbl, data=exp["reseau"][ext], file_name=f"{prefixe}_cours_eau.{ext}", key=f"exp_{ext}_str_{rid}_{seuil_acc}")
        if not exp["reseau"]:
            st.info("Aucun tronçon pour ce seuil.")

    with c_exp3:
        st.markdown("**Tableaux & Pack complet**")
        st.download_button("Statistiques (.csv)", data=exp["csv"], file_name=f"{prefixe}_statistiques.csv", mime="text/csv", key=f"exp_csv_{rid}_{seuil_acc}")
        st.download_button("Statistiques (.xlsx)", data=exp["xlsx"], file_name=f"{prefixe}_statistiques.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"exp_xlsx_{rid}_{seuil_acc}")
        st.download_button("Pack Tout-en-Un (.zip)", data=exp["all_zip"], file_name=f"{prefixe}_complet_hydro.zip", mime="application/zip", key=f"exp_all_{rid}_{seuil_acc}")

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    st.set_page_config(page_title="Hydrologie Virunga — SAP-Virunga", layout="wide")
    rendre_page_hydro()