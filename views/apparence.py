import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
from style import (entete, verre, lire, ecrire, enregistrer_image, retirer_image)
entete("Apparence", "Image de fond, lisibilité, mode jour / nuit")
r = lire()
verre("Le mode jour / nuit se change avec l'interrupteur dans la barre latérale (à gauche).")
st.subheader("Image d'arrière-plan")
fond = st.file_uploader("Choisir une image de fond", type=["png", "jpg", "jpeg"], key="up_fond")
c1, c2 = st.columns(2)
if fond and c1.button("Appliquer comme fond"):
    enregistrer_image("fond", fond)
    st.rerun()
if r["fond"] and c2.button("Retirer l'image de fond"):
    retirer_image("fond")
    st.rerun()
voile = st.slider("Voile sur l'image (plus haut = texte plus lisible)", 0, 90, int(r["voile"]))
flou  = st.slider("Flou du verre (glassmorphisme)", 0, 30, int(r["flou"]))
if voile != r["voile"] or flou != r["flou"]:
    r["voile"], r["flou"] = voile, flou
    ecrire(r)
    st.rerun()
st.subheader("Image principale de l'accueil")
acc = st.file_uploader("Image du bandeau d'accueil", type=["png", "jpg", "jpeg"], key="up_acc")
d1, d2 = st.columns(2)
if acc and d1.button("Appliquer à l'accueil"):
    enregistrer_image("accueil", acc)
    st.rerun()
if r["accueil"] and d2.button("Retirer l'image d'accueil"):
    retirer_image("accueil")
    st.rerun()