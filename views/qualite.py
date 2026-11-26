import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
from moteur import charger
from style import entete, verre
entete("Qualité des données")
df = charger()
glob = round(100 * df.qualite.mean())
verre(f"<div class='eyebrow'>Qualité globale</div><div class='grand'>{glob} %</div>"
      f"<p>{'Fiable' if glob >= 75 else 'Moyenne' if glob >= 50 else 'Faible'} · moyenne de {len(df)} série(s)</p>")
for _, r in df.iterrows():
    st.write(f"**{r.site}** · {r.canal} · qualité **{r.qualite:.2f}**")
    st.progress(float(r.qualite))
    if r.qualite < 0.4:
        st.warning("Indéterminé : demander une nouvelle acquisition")