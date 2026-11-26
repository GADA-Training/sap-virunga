import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
from style import entete, verre, ASSETS
entete("Collections d'images", "Images satellites, photos de terrain, cartes")
DOSSIER = ASSETS / "galerie"
DOSSIER.mkdir(parents=True, exist_ok=True)
ajout = st.file_uploader("Ajouter des images", type=["png", "jpg", "jpeg"],
                         accept_multiple_files=True)
if ajout and st.button("Enregistrer dans la galerie"):
    for f in ajout:
        (DOSSIER / f.name).write_bytes(f.getvalue())
    st.rerun()
images = sorted(p for p in DOSSIER.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
if not images:
    verre("La galerie est vide. Ajoutez vos premières images ci-dessus.")
else:
    cols = st.columns(3)
    for i, p in enumerate(images):
        with cols[i % 3]:
            st.image(str(p), caption=p.stem, width="stretch")