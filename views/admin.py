import sys, pathlib, shutil
RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(RACINE))
import streamlit as st
import pandas as pd
import auth, store
from moteur import valider_df, COLONNES
from style import entete, verre, lire, enregistrer_image

u = auth.courant()
if not auth.est_admin(u):
    st.error("🚫 Accès refusé. Vous devez être encadreur (administrateur) pour voir cette page.")
    st.stop()

entete("Panneau d'Administration")
st.success(f"Bienvenue **{u['nom']}**.")
st.write("Import de données, apparence du site. Votre profil est dans **Mon bureau** ; "
         "la validation des dépôts et des messages dans **Bureau encadreur**.")

onglet_data, onglet_param = st.tabs(["📥 Importation de données", "⚙️ Paramètres du site"])

with onglet_data:
    st.subheader("Remplacer les données de base (démonstration)")
    st.write("Colonnes exigées : " + ", ".join(f"`{c}`" for c in COLONNES) + ". "
             "Les dépôts de stagiaires déjà validés restent appliqués par-dessus.")
    fichier = st.file_uploader("Choisir un fichier CSV", type="csv")
    if fichier is not None:
        try:
            df = pd.read_csv(fichier)
        except Exception as e:
            df = None
            st.error(f"Fichier illisible : {e}")
        if df is not None:
            erreurs = valider_df(df)
            for e in erreurs:
                st.error(e)
            if not erreurs:
                st.dataframe(df.head(), width="stretch")
                if st.button("Remplacer les données de base", type="primary"):
                    if store.mysql_actif():
                        store.observations_remplacer(df)
                        store.base_maj_ecrire()
                        store.journaliser(u["id"], "systeme", f"Données de base remplacées ({len(df)} lignes)")
                        st.success("Données de base mises à jour dans la base MySQL.")
                    else:
                        cible = RACINE / "data" / "demo.csv"
                        shutil.copy(cible, RACINE / "data" / "demo_sauvegarde.csv")  # filet de sécurité
                        df.to_csv(cible, index=False)
                        store.journaliser(u["id"], "systeme", f"Données de base remplacées ({len(df)} lignes)")
                        st.success("Données mises à jour (ancienne version : data/demo_sauvegarde.csv).")
                    st.rerun()

with onglet_param:
    st.subheader("Apparence du site")
    r = lire()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Image d'arrière-plan")
        fond = st.file_uploader("Changer le fond d'écran", type=["png", "jpg", "jpeg"], key="admin_fond")
        if fond and st.button("Appliquer ce fond"):
            enregistrer_image("fond", fond)
            st.rerun()
        st.markdown("#### Image d'accueil")
        acc = st.file_uploader("Changer l'image de l'accueil", type=["png", "jpg", "jpeg"], key="admin_acc")
        if acc and st.button("Appliquer à l'accueil"):
            enregistrer_image("accueil", acc)
            st.rerun()
    with col2:
        st.markdown("#### Maintenance")
        if st.button("🔄 Vider le cache de l'application"):
            st.cache_data.clear()
            st.success("Cache vidé.")
