import sys, pathlib, time
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from style import entete

entete("Historique des scores")

# --- Données de démonstration sur 10 jours ---
dates = pd.date_range("2026-11-01", periods=10, freq="1D")
hist = pd.DataFrame({
    "Date": dates,
    "Shasha": [31, 35, 45, 40, 52, 58, 61, 68, 73, 73],
    "Nyiragongo": [20, 21, 22, 23, 25, 24, 26, 24, 24, 31],
    "Renga": [40, 42, 42, 45, 48, 50, 52, 52, 55, 52]
}).set_index("Date")

# --- Options d'affichage ---
col1, col2 = st.columns([1, 2])
with col1:
    type_graph = st.selectbox(
        "Type de graphique", 
        ["Courbe d'évolution (Ligne)", "Histogramme (Barres)", "Aire (Surface)"]
    )
with col2:
    st.write("") # Pour l'alignement
    st.write("") # Pour l'alignement
    mode_demo = st.toggle("▶️ Lancer la démonstration (progression)")

# --- Configuration des couleurs pour Plotly ---
couleurs = {"Shasha": "#ECF553", "Nyiragongo": "#9fb0ff", "Renga": "#F59E0B"}
couleur_theme = "rgba(0,0,0,0)" # Fond transparent pour voir le verre (glassmorphisme) derrière

def creer_graphique(df, type_g):
    # On remodèle les données pour Plotly (format "long")
    df_long = df.reset_index().melt(id_vars="Date", var_name="Site", value_name="Score")
    
    if type_g == "Courbe d'évolution (Ligne)":
        fig = px.line(df_long, x="Date", y="Score", color="Site", markers=True,
                      color_discrete_map=couleurs)
        fig.update_traces(line=dict(width=3), marker=dict(size=8))
    elif type_g == "Histogramme (Barres)":
        fig = px.bar(df_long, x="Date", y="Score", color="Site", barmode="group",
                     color_discrete_map=couleurs)
    else:
        fig = px.area(df_long, x="Date", y="Score", color="Site",
                      color_discrete_map=couleurs)
        fig.update_traces(line=dict(width=2))
        
    # Style pro + transparent
    fig.update_layout(
        paper_bgcolor=couleur_theme,
        plot_bgcolor=couleur_theme,
        font_color="#FFFFFF",
        legend_title_text="Sites",
        margin=dict(l=20, r=20, t=20, b=20),
        hovermode="x unified"
    )
    # Grille de fond discrète
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.1)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.1)', range=[0, 100])
    
    return fig

# --- Logique de l'animation (Démo automatique) ---
if mode_demo:
    placeholder = st.empty()
    # On affiche les données jour par jour
    for i in range(1, len(hist) + 1):
        df_partiel = hist.iloc[:i]
        fig = creer_graphique(df_partiel, type_graph)
        with placeholder.container():
            st.plotly_chart(fig, width="stretch")
        time.sleep(0.6) # Pause de 0.6 seconde entre chaque jour
else:
    # Affichage normal (toutes les données d'un coup)
    fig = creer_graphique(hist, type_graph)
    st.plotly_chart(fig, width="stretch")

st.caption("Score d'alerte (0 à 100) · Survolez les courbes pour voir les détails · La progression illustre la persistance de l'alerte.")
st.caption("⚠️ Données de démonstration (10 jours simulés) : l'enregistrement automatique de l'historique réel reste à brancher.")