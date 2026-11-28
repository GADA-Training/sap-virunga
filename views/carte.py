import sys, pathlib, base64
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import plotly.graph_objects as go
from PIL import Image
import pandas as pd
import pydeck as pdk
from moteur import charger, charger_fusion
from style import entete

entete("Carte des sites")
df    = charger()
sites = charger_fusion()

RACINE = pathlib.Path(__file__).resolve().parent.parent
DOSSIER_IMG = RACINE / "assets" / "sites"

# ------------------------------------------------------------------
# Vraies coordonnées (relevées sur Google Earth, WGS 84) + photo associée
# ------------------------------------------------------------------
SITES_INFO = {
    "Nyiragongo":  dict(lat=-(1 + 31/60 + 19.27/3600), lon=29 + 14/60 + 58.04/3600,
                        dms="1°31'19.27\" S · 29°14'58.04\" E", type="Volcan", img="nyiragongo",
                        legende="Volcan Nyiragongo"),
    "Nyamulagira": dict(lat=-(1 + 24/60 + 36.15/3600), lon=29 + 12/60 + 15.42/3600,
                        dms="1°24'36.15\" S · 29°12'15.42\" E", type="Volcan", img="nyamulagira",
                        legende="Volcan Nyamuragira"),
    "Shasha":      dict(lat=-(1 + 37/60 + 18.69/3600), lon=29 + 0/60 + 54.88/3600,
                        dms="1°37'18.69\" S · 29°0'54.88\" E", type="Rivière", img="shasha",
                        legende="Rivière Shasha"),
    "Kihira":      dict(lat=-(1 + 34/60 + 19.77/3600), lon=29 + 2/60 + 48.73/3600,
                        dms="1°34'19.77\" S · 29°2'48.73\" E", type="Rivière", img="kihira",
                        legende="Rivière Kihira"),
    "Renga":       dict(lat=-(1 + 40/60 + 43.34/3600), lon=29 + 0/60 + 51.51/3600,
                        dms="1°40'43.34\" S · 29°0'51.51\" E", type="Rivière", img="renga",
                        legende="Rivière Renga"),
}
# Point de référence (pas un site surveillé) : centre indicatif du parc (fiche Ramsar n°787)
REFERENCE = {
    "Parc National des Virunga": dict(lat=-1.25, lon=29.5, dms="1°15' S · 29°30' E (centre indicatif)",
                        type="Aire protégée", img="virunga",
                        legende="Parc National des Virunga — carte : Mongabay / Resource Watch (alertes GLAD 2015-2020)"),
}

@st.cache_data(show_spinner=False)
def _b64(chemin, mtime):
    return base64.b64encode(pathlib.Path(chemin).read_bytes()).decode()

def _data_uri(nom):
    p = DOSSIER_IMG / f"{nom}.jpg"
    return ("data:image/jpeg;base64," + _b64(str(p), p.stat().st_mtime)) if p.is_file() else ""

# --- Remplace les coordonnées du tableau par les vraies ---
for nom, info in SITES_INFO.items():
    sites.loc[sites.site == nom, ["lat", "lon"]] = [info["lat"], info["lon"]]

# --- Table d'affichage : sites surveillés + point de référence ---
carte_df = sites.copy()
carte_df["type"]    = carte_df.site.map(lambda s: SITES_INFO.get(s, {}).get("type", "Site"))
carte_df["dms"]     = carte_df.site.map(lambda s: SITES_INFO.get(s, {}).get("dms", ""))
carte_df["img"]     = carte_df.site.map(lambda s: SITES_INFO.get(s, {}).get("img", ""))
carte_df["legende"] = carte_df.site.map(lambda s: SITES_INFO.get(s, {}).get("legende", s))
carte_df["info"]    = carte_df.apply(lambda r: f"Niveau : {r.niveau} · Score : {r.score_site:.0f}/100", axis=1)
ref = pd.DataFrame([dict(site=n, lat=i["lat"], lon=i["lon"], niveau="Référence", type=i["type"],
                         dms=i["dms"], img=i["img"], legende=i["legende"], info="Point de référence")
                    for n, i in REFERENCE.items()])
carte_df = pd.concat([carte_df, ref], ignore_index=True)
carte_df["vignette"] = carte_df.img.map(lambda k: _data_uri(f"{k}_mini") if k else "")

fonds = {
    "Sombre (défaut)": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    "Clair": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    "Rues / Plan": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
}
choix = st.radio("Choisir le fond de carte :", list(fonds.keys()), horizontal=True)

RVB = {"Vert": [31, 138, 76], "Jaune": [236, 245, 83], "Orange": [245, 158, 11],
       "Rouge": [248, 0, 1], "Indéterminé": [139, 147, 201], "Référence": [90, 160, 255]}
carte_df["couleur"] = carte_df.niveau.map(RVB)
st.caption("🟢 Vert · 🟡 Jaune · 🟠 Orange · 🔴 Rouge · 🟣 Indéterminé · 🔵 Point de référence — "
           "survolez un point pour voir sa photo, cliquez dessus pour l'agrandir.")

couche_points = pdk.Layer(
    "ScatterplotLayer", carte_df, id="sites", pickable=True, opacity=0.95, stroked=True, filled=True,
    radius_scale=10, radius_min_pixels=10, radius_max_pixels=20, line_width_min_pixels=2,
    get_position=["lon", "lat"], get_fill_color="couleur", get_line_color=[1, 8, 96],
)
couche_noms = pdk.Layer(
    "TextLayer", carte_df, id="noms", pickable=False, get_position=["lon", "lat"], get_text="site",
    get_size=13, get_color=[255, 255, 255, 230], get_pixel_offset=[0, -26], get_text_anchor="'middle'",
    outline_width=2, outline_color=[0, 0, 0, 220], font_settings={"sdf": True},
)
vue = pdk.ViewState(latitude=-1.45, longitude=29.25, zoom=8.6, pitch=0)
info_bulle = {
    "html": "<div style='width:170px'><b>{legende}</b><br><small>{type} · {dms}</small><br>"
            "<img src='{vignette}' style='width:170px;border-radius:6px;margin:4px 0'><br><small>{info}</small></div>",
    "style": {"backgroundColor": "rgba(1,8,96,.92)", "color": "white", "fontSize": "12px"},
}
evenement = st.pydeck_chart(
    pdk.Deck(layers=[couche_points, couche_noms], initial_view_state=vue,
             map_style=fonds[choix], tooltip=info_bulle),
    on_select="rerun", selection_mode="single-object", key="carte_sites",
)

# --- Site choisi : par clic sur la carte, sinon par la liste ---
liste = carte_df.site.tolist()
clic = None
try:
    objets = evenement.selection.get("objects", {}).get("sites", [])
    if objets:
        clic = objets[0].get("site")
except Exception:
    clic = None
if clic in liste:
    st.session_state["site_carte"] = clic
st.session_state.setdefault("site_carte", liste[0])
site_choisi = st.selectbox("Site affiché", liste, key="site_carte")
r = carte_df[carte_df.site == site_choisi].iloc[0]

# --- Photo : zoom avant/arrière, déplacement, plein écran, ouverture en grand, téléchargement ---
@st.dialog("Photo", width="large")
def agrandir(chemin, titre):
    st.image(str(chemin), caption=titre, width="stretch")

st.subheader(r.legende.split(" — ")[0])
st.caption(f"{r.type} · {r.dms} · {r['info']}")
chemin_img = DOSSIER_IMG / f"{r.img}.jpg" if r.img else None
if chemin_img is not None and chemin_img.is_file():
    larg, haut = Image.open(chemin_img).size
    fig = go.Figure()
    fig.add_layout_image(dict(source=_data_uri(r.img), xref="x", yref="y", x=0, y=haut,
                              sizex=larg, sizey=haut, sizing="stretch", opacity=1, layer="below"))
    fig.add_trace(go.Scatter(x=[0, larg], y=[0, haut], mode="markers", marker_opacity=0, hoverinfo="skip"))
    fig.update_xaxes(visible=False, range=[0, larg])
    fig.update_yaxes(visible=False, range=[0, haut], scaleanchor="x")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=520, dragmode="pan",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0b1a2e", showlegend=False)
    st.plotly_chart(fig, width="stretch", key=f"photo_{r.img}",
                    config={"scrollZoom": True, "displaylogo": False, "doubleClick": "reset",
                            "toImageButtonOptions": {"filename": r.img}})
    st.caption("Molette ou boutons + / − de la barre d'outils pour zoomer, glisser pour déplacer, "
               "double-clic pour réinitialiser, icône plein écran au survol.")
    c1, c2 = st.columns(2)
    if c1.button("🔍 Ouvrir la photo en grand", key=f"grand_{r.img}"):
        agrandir(chemin_img, r.legende.split(" — ")[0])
    c2.download_button("⬇ Télécharger la photo", data=chemin_img.read_bytes(),
                       file_name=f"{r.img}.jpg", mime="image/jpeg", key=f"dl_{r.img}")
else:
    st.info("Pas de photo associée à ce point.")

st.subheader("Sites surveillés (score fusionné)")
st.dataframe(
    sites[["site", "canal", "score_site", "n_canaux_actifs", "n_canaux", "niveau", "confiance"]],
    hide_index=True, width="stretch",
)

st.subheader("Détail par canal")
st.dataframe(
    df[["site", "canal", "D", "score", "qualite", "niveau"]],
    hide_index=True, width="stretch",
)
