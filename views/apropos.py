import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
from style import entete, verre
entete("À propos et contacts")
a, b = st.columns(2)
with a:
    verre("<div class='eyebrow'>À propos</div>"
          "<p>SAP-Virunga est un prototype pédagogique de système d'alerte précoce "
          "développé avec l'OVG et l'UEA à Goma.</p>")
    verre("<div class='eyebrow'>Conditions d'utilisation</div>"
          "<p>Données de démonstration. Aucune alerte officielle n'est émise par ce site. "
          "Tout message public passe par la validation de l'encadreur OVG.</p>")
with b:
    verre("<div class='eyebrow'>Contactez-nous</div>"
          "<p>Les coordonnées de l'équipe et de l'OVG sont communiquées par l'encadreur de l'OVG.</p>")
    verre("<div class='eyebrow'>Comment citer</div>"
          "<p>SAP-Virunga (2026). Prototype de système d'alerte précoce, OVG × UEA, Goma.</p>")