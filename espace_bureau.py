import io
import json
import re
import zipfile
from urllib.parse import urlparse
import streamlit as st
import auth
import equipe
import store

POLICES_BLOG = {
    "Times New Roman": "'Times New Roman', Times, serif",
    "Georgia": "Georgia, serif",
    "Sans-serif moderne": "'Segoe UI', Roboto, Arial, sans-serif",
    "Monospace": "'Consolas', 'Courier New', monospace",
}

STYLES_ECRITURE_BLOG = {
    "Classique": "font-style: normal; font-weight: 400; line-height: 1.65;",
    "Italique éditorial": "font-style: italic; font-weight: 400; line-height: 1.7;",
    "Texte appuyé": "font-style: normal; font-weight: 500; line-height: 1.6;",
    "Citation encadrée": "font-style: italic; font-weight: 400; line-height: 1.65; border-left: 3px solid #38bdf8; padding-left: 14px;",
}

EXTENSIONS_AUTORISEES = [
    "png", "jpg", "jpeg", "webp", "gif",
    "shp", "shx", "dbf", "prj", "cpg", "geojson", "gpkg", "kml", "tif", "tiff",
    "py", "r", "rmd", "sql", "sh", "ps1",
    "csv", "xlsx", "xls", "docx", "doc", "pdf", "md", "txt", "json", "zip",
]


def _bureau_de_membre(uid: str, info: dict) -> str:
    if info.get("bureau"):
        return str(info["bureau"])
    if info.get("role") == "admin":
        return "Bureau Direction & Encadrement"
    canal_id = info.get("canal")
    if canal_id and canal_id in equipe.CANAUX:
        return f"Bureau Canal {canal_id} — {equipe.CANAUX[canal_id]['nom']}"
    return "Bureau Général"


def _nettoyer_liens(texte_liens: str) -> list[dict]:
    liens = []
    for ligne in (texte_liens or "").splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        if "|" in ligne:
            libelle, url = [p.strip() for p in ligne.split("|", 1)]
        else:
            libelle, url = ligne, ligne
        if url and not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            liens.append({"titre": libelle or url, "url": url})
    return liens


def peut_editer_bureau(u: dict | None, bureau: str) -> bool:
    if not u or u.get("role") == "visiteur":
        return False
    if u.get("role") == "admin":
        return True
    if u.get("role") == "stagiaire":
        return _bureau_de_membre(u.get("id", ""), u) == bureau
    return False


def peut_editer_fiche_membre(u: dict | None, membre_uid: str, membre_info: dict) -> bool:
    if not u or u.get("role") == "visiteur":
        return False
    if u.get("role") == "admin":
        return True
    if u.get("role") == "stagiaire":
        return u.get("id") == membre_uid or _bureau_de_membre(u.get("id", ""), u) == _bureau_de_membre(membre_uid, membre_info)
    return False


def _charger_donnees_collaboratives() -> dict:
    defaut = {"ressources": [], "articles": [], "bios_etendues": {}}
    data = store.lire_json("espace_collaboratif.json", defaut)
    if not isinstance(data, dict):
        return defaut
    data.setdefault("ressources", [])
    data.setdefault("articles", [])
    data.setdefault("bios_etendues", {})
    return data


def _sauvegarder_donnees_collaboratives(data: dict, auteur: str, action: str) -> None:
    store.ecrire_json("espace_collaboratif.json", data)
    store.journaliser(auteur, "collaboratif", action)


def _enregistrer_fichier_depot(uid: str, bureau: str, fichier_uploaded) -> dict:
    nom_fichier = fichier_uploaded.name
    contenu = fichier_uploaded.getvalue()
    ext = nom_fichier.rsplit(".", 1)[-1].lower() if "." in nom_fichier else "bin"

    dossier_local = store.RACINE / "data" / "depots_bureaux" / re.sub(r"[^a-zA-Z0-9_-]", "_", bureau)
    dossier_local.mkdir(parents=True, exist_ok=True)
    chemin_local = dossier_local / nom_fichier
    chemin_local.write_bytes(contenu)

    return {
        "id": f"res_{store.maintenant().replace(' ', '_').replace(':', '')}_{uid}_{len(contenu)}",
        "nom": nom_fichier,
        "extension": ext,
        "taille_ko": round(len(contenu) / 1024, 2),
        "bureau": bureau,
        "auteur": uid,
        "date": store.maintenant(),
        "chemin_relatif": str(chemin_local.relative_to(store.RACINE)),
        "est_image": ext in ("png", "jpg", "jpeg", "webp", "gif"),
    }


def _generer_html_article(article: dict) -> str:
    police = POLICES_BLOG.get(article.get("police", "Times New Roman"), "'Times New Roman', serif")
    style_var = STYLES_ECRITURE_BLOG.get(article.get("style_ecriture", "Classique"), "")
    taille = int(article.get("taille_px", 16))
    liens_html = "".join(
        f'<li><a href="{l["url"]}" target="_blank" rel="noopener">{l["titre"]}</a></li>'
        for l in article.get("liens", [])
    )
    bloc_liens = f"<h3>Liens utiles</h3><ul>{liens_html}</ul>" if liens_html else ""
    corps_pre = (
        article.get("contenu_md", "")
        .replace("&", "&")
        .replace("<", "<")
        .replace(">", ">")
    )
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{article.get("titre", "Article")}</title>
<style>
  body {{ font-family: {police}; font-size: {taille}px; max-width: 820px; margin: 40px auto; padding: 0 20px; }}
  .meta {{ color: #555; font-size: 0.9em; margin-bottom: 20px; }}
  .corps {{ {style_var} white-space: pre-wrap; }}
</style>
</head>
<body>
  <h1>{article.get("titre", "Sans titre")}</h1>
  <div class="meta">Bureau : {article.get("bureau", "")} • Auteur : {article.get("auteur", "")} • {article.get("date", "")}</div>
  <div class="corps">{corps_pre}</div>
  {bloc_liens}
</body>
</html>"""


def afficher_organigramme_et_bios(u: dict | None):
    st.subheader("Organigramme de l'équipe et biographies")
    st.caption("Cliquez sur un membre pour lire sa biographie complète. Les visiteurs consultent en lecture seule ; seuls l'encadreur (admin) ou le stagiaire/membre concerné selon son bureau peuvent modifier.")

    comptes_map = auth.comptes()
    etat = _charger_donnees_collaboratives()
    bios_etendues = etat.get("bios_etendues", {})

    membres_actifs = [
        (uid, info) for uid, info in comptes_map.items()
        if info.get("role") in ("admin", "stagiaire")
    ]

    if "membre_selectionne" not in st.session_state:
        st.session_state.membre_selectionne = membres_actifs[0][0] if membres_actifs else None

    cols = st.columns(min(4, max(1, len(membres_actifs))))
    for idx, (uid, info) in enumerate(membres_actifs):
        bureau = _bureau_de_membre(uid, info)
        with cols[idx % len(cols)]:
            st.markdown("<div style='border:1px solid rgba(148,163,184,0.35);border-radius:12px;padding:10px;text-align:center;margin-bottom:10px;'>", unsafe_allow_html=True)
            if info.get("photo"):
                st.markdown(f"<div style='display:flex;justify-content:center;margin-bottom:8px;'>{auth.avatar_html({**info, 'id': uid}, 96)}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='height:96px;display:flex;align-items:center;justify-content:center;opacity:0.65;'>Photo non définie</div>", unsafe_allow_html=True)
            st.markdown(f"**{info.get('nom', uid)}**  \n<small>{info.get('titre', info.get('role', ''))} · {bureau}</small>", unsafe_allow_html=True)
            if st.button("Lire la bio", key=f"btn_bio_{uid}", width="stretch"):
                st.session_state.membre_selectionne = uid
            st.markdown("</div>", unsafe_allow_html=True)

    sel_uid = st.session_state.get("membre_selectionne")
    if sel_uid and sel_uid in comptes_map:
        m_info = comptes_map[sel_uid]
        bureau_m = _bureau_de_membre(sel_uid, m_info)
        bio_data = bios_etendues.get(sel_uid, {})
        bio_texte = bio_data.get("bio_complete") or m_info.get("bio") or "Biographie en cours de renseignement."
        liens_membre = bio_data.get("liens", [])

        st.markdown("---")
        st.markdown(f"### Fiche détaillée — {m_info.get('nom', sel_uid)}")
        c_left, c_right = st.columns([1, 2])
        with c_left:
            st.markdown(auth.avatar_html({**m_info, "id": sel_uid}, 130), unsafe_allow_html=True)
            st.markdown(f"**Rôle :** {m_info.get('role')}  \n**Bureau :** {bureau_m}")
            if m_info.get("sujet"):
                st.markdown(f"**Sujet :** {m_info.get('sujet')}")
        with c_right:
            st.markdown("**Biographie complète**")
            st.write(bio_texte)
            if liens_membre:
                st.markdown("**Liens cliquables**")
                for l in liens_membre:
                    st.markdown(f"- [{l['titre']}]({l['url']})")

        if peut_editer_fiche_membre(u, sel_uid, m_info):
            with st.expander("Modifier cette fiche et sa biographie"):
                with st.form(f"form_bio_{sel_uid}"):
                    nouvelle_bio = st.text_area("Biographie complète", value=bio_texte, height=150)
                    texte_liens = st.text_area(
                        "Liens cliquables (un par ligne, format Titre | URL ou URL)",
                        value="\n".join(f"{l['titre']} | {l['url']}" for l in liens_membre),
                        height=80,
                    )
                    if st.form_submit_button("Enregistrer la biographie", type="primary"):
                        etat["bios_etendues"][sel_uid] = {
                            "bio_complete": nouvelle_bio.strip(),
                            "liens": _nettoyer_liens(texte_liens),
                            "maj_par": u["id"],
                            "date_maj": store.maintenant(),
                        }
                        _sauvegarder_donnees_collaboratives(etat, u["id"], f"Mise à jour bio de {sel_uid}")
                        st.success("Biographie enregistrée.")
                        st.rerun()


def afficher_depots_et_galerie_bureau(u: dict | None, mode: str = "complet"):
    comptes_map = auth.comptes()
    bureaux_dispo = sorted({
        _bureau_de_membre(uid, info)
        for uid, info in comptes_map.items()
        if info.get("role") in ("admin", "stagiaire")
    }) or ["Bureau Général"]

    bureau_filtre = st.selectbox("Filtrer par bureau", ["Tous les bureaux"] + bureaux_dispo, key=f"filtre_bureau_{mode}")
    etat = _charger_donnees_collaboratives()
    ressources = etat.get("ressources", [])
    if bureau_filtre != "Tous les bureaux":
        ressources = [r for r in ressources if r.get("bureau") == bureau_filtre]

    bureau_cible = _bureau_de_membre(u["id"], u) if (u and u.get("role") in ("admin", "stagiaire")) else bureaux_dispo[0]
    if u and u.get("role") == "admin" and bureau_filtre != "Tous les bureaux":
        bureau_cible = bureau_filtre

    if peut_editer_bureau(u, bureau_cible):
        st.markdown(f"#### Déposer des ressources dans le bureau : **{bureau_cible}**")
        with st.form(f"form_depot_{bureau_cible}_{mode}", clear_on_submit=True):
            fichiers = st.file_uploader(
                "Fichiers (images, shapefiles .shp/.shx/.dbf/.prj/.zip, scripts, CSV, Word, PDF, etc.)",
                type=EXTENSIONS_AUTORISEES,
                accept_multiple_files=True,
            )
            description = st.text_input("Description / contexte (optionnel)")
            liens_txt = st.text_area("Liens cliquables associés (un par ligne : Titre | URL)", height=70)
            if st.form_submit_button("Publier dans le bureau", type="primary"):
                if not fichiers:
                    st.warning("Sélectionnez au moins un fichier.")
                else:
                    liens_parses = _nettoyer_liens(liens_txt)
                    for f_up in fichiers:
                        meta = _enregistrer_fichier_depot(u["id"], bureau_cible, f_up)
                        meta["description"] = description.strip()
                        meta["liens"] = liens_parses
                        etat["ressources"].insert(0, meta)
                    _sauvegarder_donnees_collaboratives(etat, u["id"], f"Dépôt de {len(fichiers)} fichier(s) dans {bureau_cible}")
                    st.success("Ressources enregistrées.")
                    st.rerun()
    else:
        st.info("Mode lecture seule : seuls l'encadreur ou le stagiaire/membre rattaché à un bureau peuvent déposer ou modifier des ressources dans ce bureau.")

    st.markdown("#### Galerie visuelle (images déposées)")
    images = [r for r in ressources if r.get("est_image")]
    if not images:
        st.caption("Aucune image déposée pour ce filtre.")
    else:
        g_cols = st.columns(3)
        for idx, img_meta in enumerate(images):
            chemin_abs = store.RACINE / img_meta.get("chemin_relatif", "")
            with g_cols[idx % 3]:
                if chemin_abs.exists():
                    st.image(str(chemin_abs), caption=f"{img_meta['nom']} ({img_meta['bureau']})", width="stretch")
                st.caption(f"Par {img_meta.get('auteur')} · {img_meta.get('date')}")
                for l in img_meta.get("liens", []):
                    st.markdown(f"- [{l['titre']}]({l['url']})")

    st.markdown("#### Tous les fichiers et ressources du bureau (toutes extensions)")
    if not ressources:
        st.caption("Aucune ressource enregistrée.")
        return

    for r in ressources:
        chemin_abs = store.RACINE / r.get("chemin_relatif", "")
        c1, c2, c3 = st.columns([4, 2, 2])
        with c1:
            st.markdown(f"**{r['nom']}** (`.{r.get('extension', '')}`, {r.get('taille_ko', 0)} Ko)")
            st.caption(f"Bureau : {r.get('bureau')} · Auteur : {r.get('auteur')} · {r.get('date')}")
            if r.get("description"):
                st.write(r["description"])
            for l in r.get("liens", []):
                st.markdown(f"- [{l['titre']}]({l['url']})")
        with c2:
            if chemin_abs.exists():
                st.download_button(
                    "Télécharger",
                    data=chemin_abs.read_bytes(),
                    file_name=r["nom"],
                    key=f"dl_{r['id']}_{mode}",
                )
        with c3:
            if peut_editer_bureau(u, r.get("bureau", "")):
                if st.button("Supprimer", key=f"del_{r['id']}_{mode}"):
                    etat["ressources"] = [x for x in etat["ressources"] if x.get("id") != r.get("id")]
                    if chemin_abs.exists():
                        chemin_abs.unlink(missing_ok=True)
                    _sauvegarder_donnees_collaboratives(etat, u["id"], f"Suppression de {r['nom']}")
                    st.rerun()


def afficher_blog_markdown(u: dict | None):
    st.subheader("Blog collaboratif (Markdown, polices, styles et liens cliquables)")
    comptes_map = auth.comptes()
    bureaux_dispo = sorted({
        _bureau_de_membre(uid, info)
        for uid, info in comptes_map.items()
        if info.get("role") in ("admin", "stagiaire")
    }) or ["Bureau Général"]

    etat = _charger_donnees_collaboratives()
    bureau_defaut = _bureau_de_membre(u["id"], u) if (u and u.get("role") in ("admin", "stagiaire")) else bureaux_dispo[0]

    if u and u.get("role") != "visiteur":
        st.markdown("#### Rédiger ou importer un article Markdown")
        fichier_md = st.file_uploader("Importer un brouillon (.md ou .txt)", type=["md", "txt"], key="import_md_blog")
        contenu_importe = fichier_md.getvalue().decode("utf-8", errors="replace") if fichier_md is not None else ""

        with st.form("form_blog_md", clear_on_submit=True):
            bureau_art = st.selectbox("Bureau de publication", bureaux_dispo, index=bureaux_dispo.index(bureau_defaut) if bureau_defaut in bureaux_dispo else 0)
            titre = st.text_input("Titre de l'article")
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                police = st.selectbox("Police", list(POLICES_BLOG.keys()), index=0)
            with col_p2:
                taille_px = st.slider("Taille de police (px)", min_value=13, max_value=22, value=16)
            with col_p3:
                style_ecriture = st.selectbox("Variante d'écriture", list(STYLES_ECRITURE_BLOG.keys()), index=0)

            contenu_md = st.text_area(
                "Contenu Markdown",
                value=contenu_importe,
                height=220,
                placeholder="## Titre de section\n\nRédigez votre article en **Markdown**, avec *italique*, `code` ou listes...",
            )
            liens_txt = st.text_area("Liens cliquables (un par ligne : Titre | URL)", height=70)

            if st.form_submit_button("Publier l'article", type="primary"):
                if not peut_editer_bureau(u, bureau_art):
                    st.error("Vous n'avez pas les droits de publication pour ce bureau.")
                elif not titre.strip() or not contenu_md.strip():
                    st.warning("Renseignez un titre et un contenu.")
                else:
                    article = {
                        "id": f"art_{store.maintenant().replace(' ', '_').replace(':', '')}_{u['id']}",
                        "titre": titre.strip(),
                        "bureau": bureau_art,
                        "auteur": u.get("nom", u["id"]),
                        "auteur_id": u["id"],
                        "date": store.maintenant(),
                        "police": police,
                        "taille_px": taille_px,
                        "style_ecriture": style_ecriture,
                        "contenu_md": contenu_md,
                        "liens": _nettoyer_liens(liens_txt),
                    }
                    etat["articles"].insert(0, article)
                    _sauvegarder_donnees_collaboratives(etat, u["id"], f"Publication blog : {article['titre']}")
                    st.success("Article publié.")
                    st.rerun()
    else:
        st.info("Mode visiteur : lecture seule des articles publiés.")

    st.markdown("---")
    st.markdown("#### Articles publiés")
    articles = etat.get("articles", [])
    if not articles:
        st.caption("Aucun article publié pour le moment.")
        return

    for art in articles:
        police_css = POLICES_BLOG.get(art.get("police", "Times New Roman"), "'Times New Roman', serif")
        style_css = STYLES_ECRITURE_BLOG.get(art.get("style_ecriture", "Classique"), "")
        taille_css = int(art.get("taille_px", 16))
        with st.container(border=True):
            st.markdown(f"### {art.get('titre')}")
            st.caption(f"Bureau : {art.get('bureau')} · Auteur : {art.get('auteur')} · {art.get('date')} · Police : {art.get('police')} ({taille_css} px)")
            st.markdown(
                f"<div style=\"font-family:{police_css};font-size:{taille_css}px;{style_css}\">",
                unsafe_allow_html=True,
            )
            st.markdown(art.get("contenu_md", ""))
            st.markdown("</div>", unsafe_allow_html=True)

            for l in art.get("liens", []):
                st.markdown(f"- [{l['titre']}]({l['url']})")

            c_dl1, c_dl2, c_del = st.columns([2, 2, 2])
            with c_dl1:
                st.download_button(
                    "Télécharger (.md)",
                    data=art.get("contenu_md", "").encode("utf-8"),
                    file_name=f"{art.get('id', 'article')}.md",
                    mime="text/markdown",
                    key=f"dl_md_{art['id']}",
                )
            with c_dl2:
                st.download_button(
                    "Télécharger (.html)",
                    data=_generer_html_article(art).encode("utf-8"),
                    file_name=f"{art.get('id', 'article')}.html",
                    mime="text/html",
                    key=f"dl_html_{art['id']}",
                )
            with c_del:
                if u and (u.get("role") == "admin" or (u.get("id") == art.get("auteur_id") and peut_editer_bureau(u, art.get("bureau", "")))):
                    if st.button("Supprimer l'article", key=f"del_art_{art['id']}"):
                        etat["articles"] = [a for a in etat["articles"] if a.get("id") != art.get("id")]
                        _sauvegarder_donnees_collaboratives(etat, u["id"], f"Suppression article : {art.get('titre')}")
                        st.rerun()