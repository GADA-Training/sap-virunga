import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import plotly.graph_objects as go
from moteur import charger, charger_fusion, confiance
from style import entete, badge, verre
entete("Détail d'un site")
df    = charger()
sites = charger_fusion()
site = st.selectbox("Site", sorted(df.site.unique()))
r    = sites[sites.site == site].iloc[0]
bonus = r.n_canaux_actifs
detail = f"{r.score_max:.0f} + 5×{bonus - 1}" if bonus >= 2 else f"{r.score_max:.0f}"
verre(
    f"{badge(r.niveau)} <b>{site}</b>"
    f"<p>Score fusionné {r.score_site:.0f}/100 · confiance {r.confiance} % ({r.libelle_confiance})</p>"
    f"<small>fusion : {detail} · {r.n_canaux_actifs} canal(aux) ≥ 40 sur {r.n_canaux}</small>"
)
jauge = go.Figure(go.Indicator(
    mode="gauge+number", value=float(r.score_site), number={"suffix": " / 100"},
    title={"text": f"{r.niveau} · confiance {r.libelle_confiance} ({r.confiance} %)"},
    gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#ECF553"}, "steps": [
        {"range": [0, 40], "color": "#1F8A4C"}, {"range": [40, 60], "color": "#B8C23A"},
        {"range": [60, 80], "color": "#F59E0B"}, {"range": [80, 100], "color": "#F80001"}]}))
jauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#888", height=260, margin=dict(l=30, r=30, t=60, b=10))
st.plotly_chart(jauge, width="stretch")
st.subheader("Canaux de ce site")
for _, row in df[df.site == site].sort_values("D", ascending=False).iterrows():
    cf = confiance(row.qualite, row.concordance, row.persistance)
    verre(f"{badge(row.niveau)} <b>{row.canal}</b><p>score {row.score:.0f}/100 · confiance {cf} %</p>")
    c1, c2, c3 = st.columns(3)
    c1.metric("Écart D",  f"{row.D:.2f}")
    c2.metric("Qualité",  f"{row.qualite:.2f}")
    c3.metric("Confiance", f"{cf} %")