import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import pydeck as pdk
from moteur import charger, charger_fusion
from style import entete

entete("Carte des sites")
df    = charger()
sites = charger_fusion()

# --- AJOUT : Menu pour choisir le fond de carte (Styles gratuits Carto) ---
fonds = {
    "Sombre (défaut)": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    "Clair": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    "Rues / Plan": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
}
choix = st.radio("Choisir le fond de carte :", list(fonds.keys()), horizontal=True)
style_map = fonds[choix]

RVB = {"Vert": [31, 138, 76], "Jaune": [236, 245, 83], "Orange": [245, 158, 11],
       "Rouge": [248, 0, 1], "Indéterminé": [139, 147, 201]}
sites["couleur"] = sites.niveau.map(RVB)
st.caption("🟢 Vert · 🟡 Jaune · 🟠 Orange · 🔴 Rouge · 🟣 Indéterminé — la couleur est celle du niveau du site.")
# --- Création des points sur la carte ---
layer = pdk.Layer(
    "ScatterplotLayer",
    sites,
    pickable=True,
    opacity=0.9,
    stroked=True,
    filled=True,
    radius_scale=10,
    radius_min_pixels=10,
    radius_max_pixels=20,
    line_width_min_pixels=2,
    get_position=["lon", "lat"],
    get_fill_color="couleur",
    get_line_color=[1, 8, 96],          # Bordure bleu nuit
)

# --- Centrage de la carte sur Goma ---
view_state = pdk.ViewState(
    latitude=-1.6,
    longitude=29.2,
    zoom=9.5,
    pitch=0,
)

# --- Affichage de la carte interactive ---
st.pydeck_chart(pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style=style_map,
    tooltip={"text": "{site}\nNiveau : {niveau}\nScore : {score_site}/100"}
))

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