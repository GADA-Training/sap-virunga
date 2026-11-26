import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import plotly.express as px
from moteur import charger, charger_fusion, ACTION, prochaine, derniere_maj
import diffusion
from style import entete, badge, verre, tuile, hero, pied

entete("SAP-Virunga")
df    = charger()
sites = charger_fusion()
top   = sites.iloc[0]

# Image principale + points saillants
g, d = st.columns([2, 1])
with g:
    hero(f"{top.site} · niveau {top.niveau}")
with d:
    lignes = "".join(
        f"<div style='margin-bottom:8px'>{badge(r.niveau)} <b>{r.site}</b> "
        f"<small>· {r.score_site:.0f}/100</small></div>"
        for _, r in sites.iterrows()
    )
    verre("<div class='eyebrow'>Points saillants</div>" + lignes)
    verre(
        "<div class='eyebrow'>Situation</div>"
        f"<p>Sites suivis : <b>{len(sites)}</b></p>"
        f"<p>Alertes orange : <b>{int((sites.niveau == 'Orange').sum())}</b> · "
        f"rouges : <b>{int((sites.niveau == 'Rouge').sum())}</b></p>"
        f"<p>Qualité moyenne : <b>{int(df.qualite.mean() * 100)} %</b></p>"
        f"<p>Dernière mise à jour des données : <b>{derniere_maj().strftime('%d/%m à %Hh%M')}</b></p>"
        f"<p>Prochaine mise à jour : <b>{prochaine()}</b></p>"
    )

verre("Le SAP-Virunga rassemble, par site, les signaux de plusieurs canaux "
      "(déformation, érosion, surfaces, forêt) pour produire un score d'alerte "
      "de 0 à 100, un niveau de couleur et un indice de confiance.")

# Panneau d'alerte
c1, c2 = st.columns([1.3, 1])
with c1:
    verre(f"<div class='eyebrow'>Alerte la plus élevée</div>"
          f"{badge(top.niveau)}<h2>{top.site}</h2><p>{top.canal}</p>")
with c2:
    bonus = top.n_canaux_actifs
    detail = f"{top.score_max:.0f} + 5×{bonus - 1}" if bonus >= 2 else f"{top.score_max:.0f}"
    verre(f"<div class='grand'>{top.score_site:.0f}</div>"
          f"<p>sur 100 · confiance {top.confiance} % ({top.libelle_confiance})</p><small>fusion : {detail}</small>")

# Rapports récents + Réponses rapides
a, b = st.columns(2)
with a:
    st.subheader("Rapports récents")
    for _, r in sites.iterrows():
        verre(f"{badge(r.niveau)} <b>{r.site}</b><p>{ACTION[r.niveau]}</p>")
with b:
    st.subheader("Réponses rapides")
    with st.expander("Comment le score est-il calculé ?"):
        st.write("score = min(100, 20 × D), où D est l'écart mesuré sur un canal. "
                 "Par site, on garde le canal le plus fort et on ajoute 5 points "
                 "par canal supplémentaire dépassant 40.")
    with st.expander("Que signifient les couleurs ?"):
        st.write("Vert < 40 · Jaune 40-59 · Orange 60-79 · Rouge ≥ 80. "
                 "Indéterminé si la qualité des données est inférieure à 0,4.")
    with st.expander("Qui valide les messages publics ?"):
        st.write("L'encadreur OVG. Aucun message n'est diffusé sans validation.")

st.subheader("Canaux de surveillance")
cols = st.columns(4)
for i, row in df.iterrows():
    with cols[i % 4]:
        tuile(row.canal, f"{row.score:.0f}", row.site, row.niveau)

# ==============================================================
# GRAPHIQUE PROFESSIONNEL AVEC PLOTLY (remplace st.bar_chart)
# ==============================================================
st.subheader("Écart D par canal (valeur max)")

# Préparation des données pour Plotly
df_canal = df.groupby("canal")["D"].max().reset_index().sort_values("D", ascending=False)

# Création du graphique
fig = px.bar(
    df_canal, 
    x="canal", 
    y="D",
    text_auto='.2f', # Affiche la valeur au-dessus de chaque barre
    color_discrete_sequence=["#ECF553"] # Couleur jaune de ta charte
)

# Configuration du style pour qu'il soit transparent et pro
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", # Fond transparent
    plot_bgcolor="rgba(0,0,0,0)",  # Fond transparent
    font_color="#FFFFFF",          # Texte en blanc
    margin=dict(l=20, r=20, t=30, b=20),
    xaxis_title=None,
    yaxis_title=None,
    height=350,
    bargap=0.4                     # Espacement entre les barres (plus pro)
)

# Amélioration des barres et de la grille
fig.update_traces(
    marker_line_width=0,
    textfont_size=14,
    textposition='outside',        # Place la valeur au-dessus de la barre
    hovertemplate="<b>%{x}</b><br>Écart D : %{y:.2f}<extra></extra>"
)
fig.update_xaxes(showgrid=False)
fig.update_yaxes(
    showgrid=True, 
    gridcolor='rgba(255,255,255,0.1)', 
    range=[0, df_canal["D"].max() * 1.2] # Laisse de la place au-dessus
)

st.plotly_chart(fig, width="stretch")

# ==============================================================

st.subheader("Message public")
if top.niveau in ("Orange", "Rouge"):
    m = diffusion.public(top.site, top.niveau)
    verre(m if m else f"Alerte {top.niveau} à {top.site} : le message public est en attente de validation par l'encadreur de l'OVG.")
else:
    verre("Aucun message public : situation normale ou information réservée à l'encadreur.")
pied()