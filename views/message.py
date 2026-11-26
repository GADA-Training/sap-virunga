import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import auth, diffusion
from moteur import charger, charger_fusion, NIVEAUX_PUBLICS, PUBLIC, texte_interne
from style import entete, badge, verre

entete("Message à diffuser")
u = auth.courant()
df = charger()
sites = charger_fusion()
site = st.selectbox("Site", sorted(df.site.unique()))
r = sites[sites.site == site].iloc[0]
st.markdown(badge(r.niveau), unsafe_allow_html=True)
statut, texte, rec = diffusion.etat(site, r.niveau, r.confiance)
peut_ecrire = u is not None and u["role"] in ("stagiaire", "admin")

st.code(f"Message interne : {texte_interne(r)}", language=None)

if r.niveau not in NIVEAUX_PUBLICS:
    verre(f"<b>Message au public :</b> {PUBLIC[r.niveau]}")
    st.stop()

verre(f"<b>Statut :</b> {diffusion.STATUTS[statut]}"
      + (f" · validé par {rec['valideur']} le {rec['date_valid']}" if statut == "valide" else ""))

if peut_ecrire:
    msg = st.text_area("Message public (SMS / WhatsApp)", value=texte, height=130)
    c1, c2 = st.columns(2)
    if c1.button("💾 Enregistrer le brouillon"):
        diffusion.enregistrer(site, r.niveau, msg, u["id"], "brouillon")
        st.rerun()
    if c2.button("📨 Soumettre à l'encadreur"):
        diffusion.enregistrer(site, r.niveau, msg, u["id"], "soumis")
        st.rerun()
    if u["role"] == "admin":
        st.caption("En tant qu'encadreur, validez les messages dans « Bureau encadreur ».")
else:
    st.text_area("Message public", value=texte if statut == "valide" else "", height=130, disabled=True)

if statut == "valide":
    st.success("Message validé : il peut être diffusé.")
    b1, b2, b3 = st.columns(3)
    b1.link_button("WhatsApp", diffusion.lien_whatsapp(texte), width="stretch")
    b2.link_button("SMS", diffusion.lien_sms(texte), width="stretch")
    b3.download_button("Fiche 1 page", diffusion.fiche_html(r, texte, rec), f"fiche_{site}.html",
                       "text/html", width="stretch")
    st.caption("La fiche s'ouvre dans le navigateur ; « Imprimer → Enregistrer en PDF » la convertit.")
    st.code(texte, language=None)
else:
    st.warning("Diffusion bloquée : le message doit d'abord être validé par l'encadreur de l'OVG."
               + (" Le niveau Rouge exige une validation systématique." if r.niveau == "Rouge" else ""))
