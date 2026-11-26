import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
from moteur import charger, charger_fusion, ACTION
from style import entete, verre, badge
entete("Alertes actuelles")
df    = charger()
sites = charger_fusion()
for _, r in sites.iterrows():
    concordance = ""
    if r.n_canaux_actifs >= 2:
        concordance = f"<br><small>{r.n_canaux_actifs} canaux concordants · fusion appliquée</small>"
    verre(
        f"{badge(r.niveau)} <b>{r.site}</b> · <small>{r.canal}</small>"
        f"<p>{ACTION[r.niveau]}</p>"
        f"<small>score fusionné {r.score_site:.0f}/100 · confiance {r.confiance} % ({r.libelle_confiance})</small>"
        f"{concordance}"
    )
st.subheader("Détail des canaux par site")
st.dataframe(
    df.sort_values(["site", "score"], ascending=[True, False])[["site", "canal", "score", "niveau"]],
    hide_index=True, width="stretch",
)