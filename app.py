from page_hydro_virunga import rendre_page_hydro
import streamlit as st
import auth
from style import config, barre_laterale, theme, entete, verre

config()
barre_laterale()
theme()

u = auth.courant()

# Première connexion : changement du mot de passe initial obligatoire
if u and u.get("doit_changer"):
    entete("Première connexion", f"Bienvenue {u['nom']}")
    verre("Pour la sécurité du système, remplacez le mot de passe initial avant de continuer.")
    with st.form("mdp_initial"):
        a = st.text_input("Mot de passe actuel (initial)", type="password")
        n = st.text_input("Nouveau mot de passe (8 caractères minimum)", type="password")
        c = st.text_input("Confirmer le nouveau mot de passe", type="password")
        if st.form_submit_button("Enregistrer", type="primary"):
            ok, msg = auth.changer_mdp(u["id"], a, n, c)
            if ok:
                st.rerun()
            st.error(msg)
    st.stop()

menu = {
    "Maison": [
        st.Page("views/accueil.py", title="Tableau de bord", icon="🏠", default=True),
    ],
    "Rapports": [
        st.Page("views/alertes.py", title="Alertes actuelles", icon="🚨"),
        st.Page("views/historique.py", title="Historique des scores", icon="📈"),
    ],
    "Base de données": [
        st.Page("views/carte.py", title="Carte des sites", icon="🗺️"),
        st.Page("views/detail_site.py", title="Détail d'un site", icon="🔎"),
        st.Page("views/qualite.py", title="Qualité des données", icon="✅"),
    ],
    "Galeries": [
        st.Page("views/galerie.py", title="Collections d'images", icon="🖼️"),
    ],
    "Ressources": [
        st.Page("views/message.py", title="Message à diffuser", icon="📣"),
        st.Page("views/methode.py", title="Méthode et seuils", icon="📘"),
    ],
    "Informations et contacts": [
        st.Page("views/apropos.py", title="À propos et contacts", icon="ℹ️"),
        st.Page("views/apparence.py", title="Apparence", icon="🎨"),
    ],
}

# Espaces de travail : visibles seulement une fois connecté, selon le rôle.
# Placés juste après « Maison » pour ne pas disparaître dans le menu « … more » des écrans étroits.
if u and u["role"] in ("stagiaire", "admin"):
    espace = [st.Page("views/mon_bureau.py", title="Mon bureau", icon="🗂️")]
    if auth.est_admin(u):
        espace.append(st.Page("views/bureau_encadreur.py", title="Bureau encadreur", icon="🧑‍🏫"))
    menu = {"Maison": menu["Maison"], "Mon espace": espace,
            **{k: v for k, v in menu.items() if k != "Maison"}}
if auth.est_admin(u):
    menu["Administration"] = [st.Page("views/admin.py", title="Panneau Admin", icon="⚙️")]

pg = st.navigation(menu, position="top")
pg.run()

# Accès direct à la page Hydrologie Virunga
if st.sidebar.toggle("Hydrologie Virunga", value=False, key="toggle_hydro_virunga"):
    rendre_page_hydro()
