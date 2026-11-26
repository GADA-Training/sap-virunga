import sys, pathlib, html
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import pandas as pd
import auth, equipe, depots, diffusion, store
from moteur import charger_fusion, NIVEAUX_PUBLICS
from style import entete, verre, badge

E = html.escape
u = auth.courant()
if not auth.est_admin(u):
    st.error("🚫 Accès refusé : cette page est réservée aux encadreurs.")
    st.stop()

entete("Bureau encadreur", "Supervision de l'équipe, validations, journal")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

cptes = auth.comptes()
stagiaires = {k: v for k, v in cptes.items() if v["role"] == "stagiaire"}
liste_depots = depots.lister()
attente = [d for d in liste_depots if d["statut"] == "en_attente"]
sites = charger_fusion()
a_valider = []
for _, r in sites.iterrows():
    if r.niveau in NIVEAUX_PUBLICS:
        st_, _, _ = diffusion.etat(r.site, r.niveau, r.confiance)
        if st_ != "valide":
            a_valider.append(r.site)

c1, c2, c3 = st.columns(3)
c1.metric("Dépôts en attente", len(attente))
c2.metric("Messages à valider", len(a_valider))
c3.metric("Stagiaires", len(stagiaires))

T = st.tabs(["👥 Équipe", f"📥 Dépôts ({len(attente)})", f"📣 Messages ({len(a_valider)})", "📓 Journal", "🔑 Comptes"])

# ---------- ÉQUIPE ----------
with T[0]:
    taches = store.lire_json("taches.json", {})
    journal = store.lire_json("journal.json", [])
    lignes = []
    for uid, c in stagiaires.items():
        n = len(equipe.TACHES.get(uid, []))
        f = len(taches.get(uid, []))
        derniers = [e["date"] for e in journal if e["uid"] == uid]
        mes = [d for d in liste_depots if d["uid"] == uid]
        lignes.append({"Stagiaire": c["nom"], "Canal": f"{c['canal']} · {equipe.CANAUX[c['canal']]['nom']}",
                       "Avancement": f"{f}/{n} ({round(100 * f / n) if n else 0} %)",
                       "Dépôts validés": sum(d["statut"] == "valide" for d in mes),
                       "En attente": sum(d["statut"] == "en_attente" for d in mes),
                       "Dernière activité": max(derniers) if derniers else "—", "E-mail": c["email"]})
    st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
    st.subheader("Livrables par stagiaire")
    for uid, c in stagiaires.items():
        verre(f"<div style='display:flex;gap:12px;align-items:center'>{auth.avatar_html({**c, 'id': uid}, 48)}"
              f"<div><b>{E(c['nom'])}</b> · canal {c['canal']}<br><small>{E(c['sujet'])}</small><br>"
              f"<small>Livrables : {E(c['livrables'])}</small></div></div>")

# ---------- DÉPÔTS ----------
with T[1]:
    if not attente:
        st.info("Aucun dépôt en attente.")
    for d in attente:
        auteur = cptes.get(d["uid"], {}).get("nom", d["uid"])
        with st.expander(f"{auteur} · {d['canal']} · {d['lignes']} ligne(s) · {d['date']}", expanded=True):
            st.dataframe(depots.lire_depot(d["id"]), hide_index=True, width="stretch")
            com = st.text_input("Commentaire (obligatoire en cas de rejet)", key=f"com_{d['id']}")
            b1, b2 = st.columns(2)
            if b1.button("✅ Valider et intégrer au moteur", key=f"ok_{d['id']}", type="primary"):
                depots.decider(d["id"], u["id"], True, com)
                st.session_state.flash = "Dépôt validé : les données actives sont mises à jour."
                st.rerun()
            if b2.button("❌ Rejeter", key=f"ko_{d['id']}"):
                if com.strip():
                    depots.decider(d["id"], u["id"], False, com)
                    st.session_state.flash = "Dépôt rejeté."
                    st.rerun()
                else:
                    st.error("Indiquez un commentaire pour que le stagiaire sache quoi corriger.")
    deja = [d for d in liste_depots if d["statut"] != "en_attente"]
    if deja:
        st.subheader("Historique")
        st.dataframe(pd.DataFrame([{
            "Date": d["date"], "Stagiaire": cptes.get(d["uid"], {}).get("nom", d["uid"]), "Canal": d["canal"],
            "Sites": ", ".join(d["sites"]), "Statut": depots.STATUTS[d["statut"]],
            "Par": d["valideur"], "Commentaire": d["commentaire"]} for d in reversed(deja)]),
            hide_index=True, width="stretch")

# ---------- MESSAGES ----------
with T[2]:
    st.caption("Aucun message public n'est diffusé sans votre validation (plan §9.2). "
               "Une validation ne vaut que pour le niveau en cours : si le niveau change, le message est à revalider.")
    vus = 0
    for _, r in sites.iterrows():
        if r.niveau not in NIVEAUX_PUBLICS:
            continue
        vus += 1
        statut, texte, rec = diffusion.etat(r.site, r.niveau, r.confiance)
        verre(f"{badge(r.niveau)} <b>{E(r.site)}</b> · score {r.score_site:.0f}/100 · confiance {r.confiance} % ({r.libelle_confiance})"
              f"<br><small>Statut : {diffusion.STATUTS[statut]}"
              + (f" · par {E(rec['valideur'])} le {E(rec['date_valid'])}" if rec and rec.get("valideur") else "")
              + "</small>")
        nouveau = st.text_area("Texte du message public", texte, key=f"m_{r.site}", height=110)
        b1, b2 = st.columns(2)
        if b1.button("✅ Valider ce message", key=f"vm_{r.site}", type="primary", disabled=not nouveau.strip()):
            diffusion.enregistrer(r.site, r.niveau, nouveau, u["id"], "valide", valideur=u["id"])
            st.session_state.flash = f"Message de {r.site} validé : il est maintenant diffusable."
            st.rerun()
        if b2.button("↩️ Renvoyer en brouillon", key=f"bm_{r.site}"):
            diffusion.enregistrer(r.site, r.niveau, nouveau, u["id"], "brouillon")
            st.session_state.flash = f"Message de {r.site} renvoyé en brouillon."
            st.rerun()
    if not vus:
        st.info("Aucun site n'est au niveau Orange ou Rouge : aucun message public n'est nécessaire.")

# ---------- JOURNAL ----------
with T[3]:
    journal = store.lire_json("journal.json", [])
    qui = {k: v["nom"] for k, v in cptes.items()}
    f1, f2 = st.columns(2)
    type_ = f1.selectbox("Type", ["Tout", "Traçabilité (stagiaires)", "Système (connexions, validations)"])
    pers = f2.selectbox("Personne", ["Toutes"] + sorted(qui.values()))
    rows = []
    for e in reversed(journal):
        if type_.startswith("Traça") and e["type"] != "trace": continue
        if type_.startswith("Syst") and e["type"] != "systeme": continue
        if pers != "Toutes" and qui.get(e["uid"], e["uid"]) != pers: continue
        rows.append({"Date": e["date"], "Personne": qui.get(e["uid"], e["uid"]), "Type": e["type"],
                     "Outil": e.get("outil", ""), "Version": e.get("version", ""),
                     "Paramètres": e.get("parametres", ""), "Détail": e["texte"]})
    st.dataframe(pd.DataFrame(rows[:500]), hide_index=True, width="stretch")

# ---------- COMPTES ----------
with T[4]:
    st.dataframe(pd.DataFrame([{"Identifiant": k, "Nom": v["nom"], "Rôle": auth.ROLES[v["role"]], "E-mail": v["email"],
                                "Mot de passe initial à changer": "oui" if v.get("doit_changer") else "non"}
                               for k, v in cptes.items()]), hide_index=True, width="stretch")
    st.subheader("Réinitialiser un mot de passe")
    st.caption("Utile si quelqu'un a oublié le sien : il reprend le mot de passe initial et devra en choisir un nouveau à sa prochaine connexion.")
    cible = st.selectbox("Compte", [k for k in cptes if k != "visiteur"], format_func=lambda k: f"{cptes[k]['nom']} ({k})")
    if st.checkbox("Je confirme la réinitialisation") and st.button("Réinitialiser"):
        auth.reinitialiser_mdp(cible, u["id"])
        st.success(f"Mot de passe de {cptes[cible]['nom']} réinitialisé.")
