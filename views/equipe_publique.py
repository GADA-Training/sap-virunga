import streamlit as st
import auth
import espace_bureau
from style import entete

entete("Equipe", "Organigramme et fiches des membres SAP-Virunga")
espace_bureau.afficher_organigramme_et_bios(auth.courant())

