import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import auth
import espace_bureau
from style import entete

entete("Collections & Dépôts par bureau", "Images, shapefiles, scripts, CSV, Word et liens utiles")
u = auth.courant()
espace_bureau.afficher_depots_et_galerie_bureau(u, mode="galerie")
