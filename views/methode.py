import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import pandas as pd
from moteur import ACTION
from style import entete, verre, badge
entete("Méthode et seuils")
verre("<b>Score par canal</b><p>score = min(100, 20 × D)</p>"
      "<b>Confiance</b><p>100 × (0,4 × Qualité + 0,3 × Concordance + 0,3 × Persistance). "
      "Faible en dessous de 50 %, moyenne de 50 à 75 %, élevée au-delà de 75 %. Le message d'alerte la mentionne toujours.</p>"
      "<b>Conditions en D</b><p>Jaune : D ≥ 2 sur une observation ou une source. "
      "Orange : D ≥ 3 sur deux observations consécutives, ou seuil jaune confirmé par une seconde source. "
      "Rouge : D ≥ 4 sur deux observations consécutives, avec deux sources ou une cohérence spatiale "
      "de plusieurs cellules voisines.</p>"
      "<b>Confirmation</b><p>Les niveaux orange et rouge exigent une confirmation : persistance sur plusieurs "
      "observations ou concordance de plusieurs sources. Une source isolée, observée une seule fois, "
      "ne peut jamais produire une alerte rouge.</p>"
      "<b>Fusion par site</b><p>score du site = min(100, max des scores + 5 × (nombre de canaux ≥ 40 − 1))</p>")
st.subheader("Niveaux et actions")
for nv, txt in [("Vert", "score 0 à 39 · D < 2"), ("Jaune", "score 40 à 59 · D ≥ 2"),
                ("Orange", "score 60 à 79 · D ≥ 3, persistance sur deux observations"),
                ("Rouge", "score 80 à 100 · D ≥ 4, persistance sur deux observations et deux sources"),
                ("Indéterminé", "sans score · qualité < 0,4 ou données manquantes")]:
    verre(f"{badge(nv)} <small>{txt}</small><p>{ACTION[nv]}</p>")