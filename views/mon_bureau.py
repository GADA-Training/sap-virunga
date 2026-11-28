import sys, pathlib, html
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
import streamlit as st
import pandas as pd
import auth, equipe, depots, store, espace_bureau
from moteur import charger, valider_df, COLONNES
from style import entete, verre, tuile

E = html.escape
u = auth.courant()

if u is None or u["role"] == "visiteur":
    entete("Mon bureau", "Espace de travail individuel")
    verre("🔐 Le bureau individuel est réservé aux encadreurs et aux stagiaires. "
          "Connectez-vous avec votre identifiant dans la barre latérale."
          if u is None else
          "Le compte visiteur consulte les pages publiques en lecture seule : il n'a pas de bureau individuel.")
    st.stop()

entete("Mon bureau", "Espace de travail individuel")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

est_stag = u["role"] == "stagiaire"
canal = equipe.CANAUX.get(u.get("canal")) if est_stag else None

# ---------- carte d'identité + prochaine séance ----------
a, b = st.columns([2, 1])
with a:
    detail = ""
    if est_stag:
        detail = (f"<p><b>Canal {u['canal']} · {E(canal['nom'])}</b> — {E(u['sujet'])}</p>")
    bio = f"<p><i>{E(u['bio'])}</i></p>" if u.get("bio") else ""
    verre(f"<div style='display:flex;gap:16px;align-items:center'>{auth.avatar_html(u, 88)}"
          f"<div><div class='eyebrow'>{E(u['titre'])}</div><h2 style='margin:0'>{E(u['nom'])}</h2>"
          f"<p>{E(u['email'])}</p>{detail}{bio}</div></div>")
with b:
    s = equipe.prochaine_seance()
    if s:
        quand = "aujourd'hui" if s["reste"] == 0 else f"dans {s['reste']} jour(s)"
        verre(f"<div class='eyebrow'>Prochaine séance · {s['code']}</div><b>{s['date'].strftime('%d/%m/%Y')}</b> ({quand})"
              f"<p>{E(s['travaux'])}</p><small>Résultat attendu : {E(s['resultat'])}</small>")
    else:
        verre("<div class='eyebrow'>Calendrier</div><p>Toutes les séances du stage sont passées.</p>")

noms = ["👤 Profil"]
if est_stag:
    noms += ["🎯 Mon canal", "✅ Mes tâches", "📥 Mes dépôts"]
noms += ["📓 Journal"]
T = dict(zip(noms, st.tabs(noms)))

# ---------- PROFIL ----------
with T["👤 Profil"]:
    c1, c2 = st.columns([1, 2])
    with c1:
        verre(f"<div style='display:flex;justify-content:center'>{auth.avatar_html(u, 150)}</div>")
        if u.get("photo") and st.button("Retirer ma photo"):
            auth.retirer_photo(u["id"])
            st.rerun()
    with c2:
        with st.form("profil"):
            nom = st.text_input("Nom affiché", u["nom"])
            email = st.text_input("E-mail", u["email"])
            tel = st.text_input("Téléphone (facultatif)", u.get("tel", ""))
            bio = st.text_area("Courte biographie (400 caractères maximum)", u.get("bio", ""), max_chars=400, height=120)
            photo = st.file_uploader("Photo de profil (PNG ou JPG)", type=["png", "jpg", "jpeg"])
            if st.form_submit_button("Enregistrer mon profil", type="primary"):
                ok, msg = auth.maj_profil(u["id"], nom, email, tel, bio)
                if ok and photo is not None:
                    try:
                        auth.enregistrer_photo(u["id"], photo)
                    except Exception:
                        ok, msg = False, "Image illisible : choisissez un fichier PNG ou JPG valide."
                if ok:
                    st.session_state.flash = msg
                    st.rerun()
                st.error(msg)
    with st.expander("🔑 Changer mon mot de passe"):
        with st.form("mdp"):
            ancien = st.text_input("Mot de passe actuel", type="password")
            nouveau = st.text_input("Nouveau mot de passe (8 caractères minimum)", type="password")
            conf = st.text_input("Confirmer", type="password")
            if st.form_submit_button("Mettre à jour"):
                ok, msg = auth.changer_mdp(u["id"], ancien, nouveau, conf)
                (st.success if ok else st.error)(msg)

# ---------- MON CANAL ----------
if est_stag:
    with T["🎯 Mon canal"]:
        verre(f"<div class='eyebrow'>Canal {u['canal']}</div><h2>{E(canal['titre'])}</h2>"
              f"<p><b>Zones :</b> {E(canal['zones'])}</p><p><b>Données :</b> {E(canal['donnees'])}</p>"
              f"<p><b>Indicateur principal :</b> {E(canal['indicateur'])}</p>"
              f"<p><b>Mise à jour :</b> {E(canal['maj'])}</p><p><b>Livrables :</b> {E(u['livrables'])}</p>")
        st.subheader("État actuel de mes sites")
        df = charger()
        mien = df[df.canal == canal["nom"]]
        if mien.empty:
            st.info("Aucune donnée active pour votre canal. Déposez un fichier dans l'onglet « Mes dépôts ».")
        else:
            cols = st.columns(min(4, len(mien)))
            for i, (_, r) in enumerate(mien.iterrows()):
                with cols[i % len(cols)]:
                    tuile(r.site, f"{r.score:.0f}", f"qualité {r.qualite:.2f}", r.niveau)
            st.dataframe(mien[["site", "canal", "D", "score", "qualite", "concordance", "persistance", "niveau"]],
                         hide_index=True, width="stretch")
        st.caption("Sites de votre périmètre : " + ", ".join(u["sites"]))

    # ---------- MES TÂCHES ----------
    with T["✅ Mes tâches"]:
        etapes = equipe.TACHES.get(u["id"], [])
        faits = set(store.lire_json("taches.json", {}).get(u["id"], []))
        st.caption("Étapes de votre chaîne de traitement (plan §6). Cochez au fur et à mesure : l'encadreur voit votre avancement.")
        prog = st.empty()
        nouveaux = set()
        for i, (titre, seance) in enumerate(etapes):
            if st.checkbox(f"**{i + 1}.** {titre} · _{seance}_", value=i in faits, key=f"t_{u['id']}_{i}"):
                nouveaux.add(i)
        prog.progress(len(nouveaux) / max(1, len(etapes)),
                      text=f"{len(nouveaux)} étape(s) terminée(s) sur {len(etapes)}")
        if nouveaux != faits:
            t = store.lire_json("taches.json", {})
            t[u["id"]] = sorted(nouveaux)
            store.ecrire_json("taches.json", t)
            store.journaliser(u["id"], "systeme", f"Avancement : {len(nouveaux)}/{len(etapes)} étapes")

    # ---------- MES DÉPÔTS ----------
    with T["📥 Mes dépôts"]:
        st.write(f"Déposez le fichier CSV de votre canal **{canal['nom']}**. L'encadreur le contrôle, puis le valide : "
                 "il alimente alors le moteur et le tableau de bord.")
        modele = pd.DataFrame([dict(site=s_, canal=canal["nom"], lat="", lon="", D="", qualite="",
                                    concordance="", persistance="") for s_ in u["sites"]])
        st.download_button("⬇️ Télécharger le modèle CSV", modele.to_csv(index=False).encode("utf-8"),
                           f"modele_canal{u['canal']}.csv", "text/csv")
        st.caption("Colonnes : " + ", ".join(COLONNES) + ". D ≥ 0 ; qualite, concordance, persistance entre 0 et 1.")
        f = st.file_uploader("Fichier CSV", type="csv", key="depot")
        if f is not None:
            try:
                d = pd.read_csv(f)
            except Exception as e:
                d = None
                st.error(f"Fichier illisible : {e}")
            if d is not None:
                erreurs = valider_df(d, canal["nom"])
                for e in erreurs:
                    st.error(e)
                if not erreurs:
                    st.success(f"Fichier conforme : {len(d)} ligne(s).")
                    st.dataframe(d.head(10), hide_index=True, width="stretch")
                    hors = sorted(set(d.site.astype(str)) - set(u["sites"]))
                    if hors:
                        st.warning(f"Sites hors de votre périmètre ({', '.join(u['sites'])}) : {', '.join(hors)}. "
                                   "L'encadreur décidera.")
                    if st.button("📤 Envoyer à l'encadreur pour validation", type="primary"):
                        depots.deposer(u["id"], canal["nom"], d)
                        st.session_state.flash = "Dépôt envoyé. Il apparaît ci-dessous avec le statut « En attente »."
                        st.rerun()
        st.subheader("Mes dépôts")
        mes = [x for x in depots.lister() if x["uid"] == u["id"]]
        if mes:
            st.dataframe(pd.DataFrame([{
                "Date": x["date"], "Lignes": x["lignes"], "Sites": ", ".join(x["sites"]),
                "Statut": depots.STATUTS[x["statut"]], "Commentaire de l'encadreur": x["commentaire"]}
                for x in reversed(mes)]), hide_index=True, width="stretch")
        else:
            st.caption("Aucun dépôt pour le moment.")

# ---------- JOURNAL ----------
with T["📓 Journal"]:
    st.caption("Traçabilité (plan §6) : chaque traitement est consigné avec sa date, l'outil et sa version, "
               "les paramètres et l'auteur. Le jeu brut n'est jamais modifié.")
    with st.form("journal", clear_on_submit=True):
        c1, c2 = st.columns(2)
        outil = c1.text_input("Outil (ex. SNAP, Python, ArcGIS Pro)")
        version = c2.text_input("Version")
        params = st.text_area("Paramètres utilisés", height=80)
        note = st.text_area("Ce qui a été fait / résultat", height=80)
        if st.form_submit_button("Ajouter au journal"):
            if outil.strip() and note.strip():
                store.journaliser(u["id"], "trace", note.strip()[:1000], outil=outil.strip()[:80],
                                  version=version.strip()[:40], parametres=params.strip()[:1000])
                st.session_state.flash = "Entrée ajoutée au journal."
                st.rerun()
            else:
                st.error("L'outil et le résultat sont obligatoires.")
    mes = [e for e in store.lire_json("journal.json", []) if e["uid"] == u["id"] and e["type"] == "trace"]
    if mes:
        st.dataframe(pd.DataFrame([{"Date": e["date"], "Outil": e.get("outil", ""), "Version": e.get("version", ""),
                                    "Paramètres": e.get("parametres", ""), "Résultat": e["texte"]}
                                   for e in reversed(mes)]), hide_index=True, width="stretch")
    else:
        st.caption("Journal vide.")


st.markdown("---")
t_org, t_dep, t_blog = st.tabs(["?? Equipe", "?? D?p?ts & Galerie", "?? Blog Markdown"])
with t_org:
    espace_bureau.afficher_organigramme_et_bios(u)
with t_dep:
    espace_bureau.afficher_depots_et_galerie_bureau(u, mode="bureau")
with t_blog:
    espace_bureau.afficher_blog_markdown(u)
