import html
import re
from urllib.parse import urlparse
import streamlit as st
import auth
import equipe
import store

POLICES_DOC = {
    "Times New Roman": "'Times New Roman', Times, serif",
    "Calibri / Sans-serif": "Calibri, 'Segoe UI', Roboto, Arial, sans-serif",
    "Georgia": "Georgia, serif",
    "Consolas / Code": "Consolas, 'Courier New', monospace",
}

ALIGNEMENTS_DOC = {
    "Gauche": "left",
    "Centré": "center",
    "Justifié": "justify",
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


def _charger_donnees() -> dict:
    defaut = {
        "ressources": [],
        "articles": [],
        "bios_etendues": {},
        "feuilles_sections": {
            "ressources": [],
            "informations": [],
        },
    }
    data = store.lire_json("espace_collaboratif.json", defaut)
    if not isinstance(data, dict):
        return defaut
    data.setdefault("ressources", [])
    data.setdefault("articles", [])
    data.setdefault("bios_etendues", {})
    data.setdefault("feuilles_sections", {"ressources": [], "informations": []})
    data["feuilles_sections"].setdefault("ressources", [])
    data["feuilles_sections"].setdefault("informations", [])
    return data


def _sauvegarder_donnees(data: dict, auteur: str, action: str) -> None:
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


def _rendre_feuille_document(
    titre_general: str,
    sous_titre: str,
    description: str,
    contenu_md: str,
    police_nom: str = "Times New Roman",
    taille_px: int = 16,
    alignement_nom: str = "Gauche",
    gras_global: bool = False,
    italique_global: bool = False,
    souligne_global: bool = False,
    liens: list[dict] | None = None,
    meta_ligne: str = "",
) -> None:
    font_css = POLICES_DOC.get(police_nom, "'Times New Roman', Times, serif")
    align_css = ALIGNEMENTS_DOC.get(alignement_nom, "left")
    poids_css = "700" if gras_global else "400"
    style_css = "italic" if italique_global else "normal"
    deco_css = "underline" if souligne_global else "none"

    st.markdown(
        f"""
        <div style="
            background:#ffffff;
            color:#111827;
            border:1px solid #cbd5e1;
            border-radius:10px;
            padding:24px 28px;
            margin:10px 0 12px 0;
            box-shadow:0 8px 24px rgba(15,23,42,0.18);
            font-family:{font_css};
            font-size:{int(taille_px)}px;
            text-align:{align_css};
            font-weight:{poids_css};
            font-style:{style_css};
            text-decoration:{deco_css};
        ">
            <div style="font-size:1.5em;font-weight:700;color:#0f172a;margin-bottom:4px;">
                {html.escape(titre_general or "Sans titre")}
            </div>
            {f'<div style="font-size:1.1em;font-weight:600;color:#334155;margin-bottom:8px;">{html.escape(sous_titre)}</div>' if sous_titre else ''}
            {f'<div style="font-size:0.95em;color:#475569;background:#f8fafc;border-left:4px solid #2563eb;padding:10px 14px;border-radius:4px;margin-bottom:12px;">{html.escape(description)}</div>' if description else ''}
            {f'<div style="font-size:0.8em;color:#64748b;border-bottom:1px solid #e2e8f0;padding-bottom:8px;">{html.escape(meta_ligne)}</div>' if meta_ligne else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown(contenu_md or "")
        if liens:
            st.markdown("**Liens cliquables**")
            for l in liens:
                st.markdown(f"- [{l['titre']}]({l['url']})")


def _generer_html_feuille(
    titre_general: str,
    sous_titre: str,
    description: str,
    contenu_md: str,
    police_nom: str,
    taille_px: int,
    alignement_nom: str,
    liens: list[dict],
) -> str:
    font_css = POLICES_DOC.get(police_nom, "'Times New Roman', serif")
    align_css = ALIGNEMENTS_DOC.get(alignement_nom, "left")
    liens_html = "".join(
        f'<li><a href="{html.escape(l["url"])}" target="_blank" rel="noopener">{html.escape(l["titre"])}</a></li>'
        for l in (liens or [])
    )
    bloc_liens = f"<h3>Liens cliquables</h3><ul>{liens_html}</ul>" if liens_html else ""
    corps_esc = html.escape(contenu_md or "")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(titre_general or "Document")}</title>
<style>
  body {{ font-family: {font_css}; font-size: {int(taille_px)}px; text-align: {align_css}; max-width: 860px; margin: 36px auto; padding: 28px; color: #111827; background: #f8fafc; }}
  .feuille {{ background: #ffffff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 32px; }}
  .sous-titre {{ font-size: 1.15em; color: #334155; margin-bottom: 10px; font-weight: 600; }}
  .desc {{ background: #f1f5f9; border-left: 4px solid #2563eb; padding: 10px 14px; margin-bottom: 18px; color: #334155; }}
  .corps {{ white-space: pre-wrap; line-height: 1.65; }}
</style>
</head>
<body>
  <div class="feuille">
    <h1>{html.escape(titre_general or "Sans titre")}</h1>
    {f'<div class="sous-titre">{html.escape(sous_titre)}</div>' if sous_titre else ''}
    {f'<div class="desc">{html.escape(description)}</div>' if description else ''}
    <div class="corps">{corps_esc}</div>
    {bloc_liens}
  </div>
</body>
</html>"""


def _editeur_type_word_markdown(
    cle_prefixe: str,
    bureau_defaut: str,
    bureaux_dispo: list[str],
    permettre_choix_bureau: bool = True,
    titre_bouton: str = "Publier la feuille",
):
    etat = _charger_donnees()
    st.markdown("#### Feuille d'édition style Word & Markdown")
    st.caption("Renseignez le titre général, le sous-titre et la description, puis collez ou rédigez votre texte en Markdown.")

    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        titre_general = st.text_input("Titre général", key=f"{cle_prefixe}_titre_gen")
        sous_titre = st.text_input("Sous-titre", key=f"{cle_prefixe}_sous_titre")
    with col_meta2:
        if permettre_choix_bureau and bureaux_dispo:
            idx_b = bureaux_dispo.index(bureau_defaut) if bureau_defaut in bureaux_dispo else 0
            bureau_sel = st.selectbox("Bureau rattaché", bureaux_dispo, index=idx_b, key=f"{cle_prefixe}_bureau")
        else:
            bureau_sel = bureau_defaut
        description = st.text_input("Description / résumé", key=f"{cle_prefixe}_desc")

    st.markdown("**Barre de style (insertion rapide)**")
    b1, b2, b3, b4, b5, b6, b7 = st.columns(7)
    cle_texte = f"{cle_prefixe}_corps_md"
    if cle_texte not in st.session_state:
        st.session_state[cle_texte] = ""

    def _inserer(snippet: str):
        courant_txt = st.session_state.get(cle_texte, "")
        sep = "\n\n" if courant_txt and not courant_txt.endswith("\n") else ""
        st.session_state[cle_texte] = courant_txt + sep + snippet

    if b1.button("Titre 1", key=f"{cle_prefixe}_h1", width="stretch"):
        _inserer("# Titre de section")
    if b2.button("Titre 2", key=f"{cle_prefixe}_h2", width="stretch"):
        _inserer("## Sous-section")
    if b3.button("Gras", key=f"{cle_prefixe}_gras", width="stretch"):
        _inserer("**texte en gras**")
    if b4.button("Italique", key=f"{cle_prefixe}_ital", width="stretch"):
        _inserer("*texte en italique*")
    if b5.button("Liste", key=f"{cle_prefixe}_liste", width="stretch"):
        _inserer("- Élément 1\n- Élément 2")
    if b6.button("Citation", key=f"{cle_prefixe}_cit", width="stretch"):
        _inserer("> Citation ou note importante")
    if b7.button("Lien", key=f"{cle_prefixe}_lien", width="stretch"):
        _inserer("[Libellé du lien](https://exemple.org)")

    f1, f2, f3, f4, f5, f6 = st.columns([2, 1.2, 1.5, 0.8, 0.8, 1])
    with f1:
        police_nom = st.selectbox("Police", list(POLICES_DOC.keys()), index=0, key=f"{cle_prefixe}_police")
    with f2:
        taille_px = st.slider("Taille (px)", min_value=13, max_value=24, value=16, key=f"{cle_prefixe}_taille")
    with f3:
        alignement_nom = st.selectbox("Alignement", list(ALIGNEMENTS_DOC.keys()), index=0, key=f"{cle_prefixe}_align")
    with f4:
        gras_global = st.checkbox("G", help="Gras", key=f"{cle_prefixe}_g_chk")
    with f5:
        ital_global = st.checkbox("I", help="Italique", key=f"{cle_prefixe}_i_chk")
    with f6:
        soul_global = st.checkbox("S", help="Souligné", key=f"{cle_prefixe}_s_chk")

    f_imp = st.file_uploader("Importer un fichier (.md ou .txt)", type=["md", "txt"], key=f"{cle_prefixe}_import")
    if f_imp is not None and st.button("Charger dans la feuille", key=f"{cle_prefixe}_btn_imp"):
        st.session_state[cle_texte] = f_imp.getvalue().decode("utf-8", errors="replace")
        st.rerun()

    contenu_md = st.text_area(
        "Texte de la feuille (copier-coller ou saisie Markdown)",
        height=240,
        key=cle_texte,
        placeholder="Collez ici votre texte ou rédigez en Markdown (# Titre, **gras**, *italique*, - liste, [lien](https://...))...",
    )
    liens_txt = st.text_area("Liens cliquables (un par ligne : Titre | URL)", height=70, key=f"{cle_prefixe}_liens")

    st.markdown("**Aperçu en direct sur feuille**")
    _rendre_feuille_document(
        titre_general=titre_general,
        sous_titre=sous_titre,
        description=description,
        contenu_md=contenu_md,
        police_nom=police_nom,
        taille_px=taille_px,
        alignement_nom=alignement_nom,
        gras_global=gras_global,
        italique_global=ital_global,
        souligne_global=soul_global,
        liens=_nettoyer_liens(liens_txt),
        meta_ligne=f"Bureau : {bureau_sel} • Police : {police_nom} ({taille_px} px) • Alignement : {alignement_nom}",
    )

    if not st.button(titre_bouton, type="primary", key=f"{cle_prefixe}_publier"):
        return None

    return {
        "titre_general": titre_general.strip(),
        "sous_titre": sous_titre.strip(),
        "description": description.strip(),
        "bureau": bureau_sel,
        "police": police_nom,
        "taille_px": taille_px,
        "alignement": alignement_nom,
        "gras": gras_global,
        "italique": ital_global,
        "souligne": soul_global,
        "contenu_md": contenu_md,
        "liens": _nettoyer_liens(liens_txt),
        "etat": etat,
    }


def afficher_feuilles_personnalisables(section_cle: str, titre_section: str, u: dict | None):
    est_admin_actif = bool(u and u.get("role") == "admin")
    etat = _charger_donnees()
    feuilles = etat["feuilles_sections"].get(section_cle, [])

    st.markdown(f"### {titre_section} — Feuilles personnalisées")
    if est_admin_actif:
        st.caption("Mode Encadreur (Admin) : créez, modifiez ou supprimez les feuilles de cette section.")
        with st.expander("Créer une nouvelle feuille personnalisée", expanded=len(feuilles) == 0):
            res = _editeur_type_word_markdown(
                cle_prefixe=f"feuille_new_{section_cle}",
                bureau_defaut="Bureau Direction & Encadrement",
                bureaux_dispo=["Bureau Direction & Encadrement"],
                permettre_choix_bureau=False,
                titre_bouton="Enregistrer la feuille",
            )
            if res is not None:
                if not res["titre_general"] or not res["contenu_md"].strip():
                    st.warning("Renseignez au moins un titre général et un contenu.")
                else:
                    nouvelle = {
                        "id": f"feuille_{section_cle}_{store.maintenant().replace(' ', '_').replace(':', '')}_{len(feuilles)+1}",
                        "titre_general": res["titre_general"],
                        "sous_titre": res["sous_titre"],
                        "description": res["description"],
                        "police": res["police"],
                        "taille_px": res["taille_px"],
                        "alignement": res["alignement"],
                        "gras": res["gras"],
                        "italique": res["italique"],
                        "souligne": res["souligne"],
                        "contenu_md": res["contenu_md"],
                        "liens": res["liens"],
                        "auteur": u.get("nom", u["id"]),
                        "date": store.maintenant(),
                    }
                    etat["feuilles_sections"][section_cle].insert(0, nouvelle)
                    _sauvegarder_donnees(etat, u["id"], f"Création feuille {section_cle} : {nouvelle['titre_general']}")
                    st.success("Feuille enregistrée.")
                    st.rerun()
    else:
        st.caption("Lecture seule : feuilles publiées par l'équipe d'encadrement.")

    if not feuilles:
        st.info("Aucune feuille personnalisée enregistrée pour le moment.")
        return

    for f_item in feuilles:
        _rendre_feuille_document(
            titre_general=f_item.get("titre_general", ""),
            sous_titre=f_item.get("sous_titre", ""),
            description=f_item.get("description", ""),
            contenu_md=f_item.get("contenu_md", ""),
            police_nom=f_item.get("police", "Times New Roman"),
            taille_px=f_item.get("taille_px", 16),
            alignement_nom=f_item.get("alignement", "Gauche"),
            gras_global=f_item.get("gras", False),
            italique_global=f_item.get("italique", False),
            souligne_global=f_item.get("souligne", False),
            liens=f_item.get("liens", []),
            meta_ligne=f"Par {f_item.get('auteur', '')} • {f_item.get('date', '')}",
        )
        c_exp1, c_exp2, c_mod, c_sup = st.columns([2, 2, 2, 2])
        with c_exp1:
            st.download_button(
                "Télécharger (.md)",
                data=f_item.get("contenu_md", "").encode("utf-8"),
                file_name=f"{f_item.get('id', 'feuille')}.md",
                mime="text/markdown",
                key=f"dl_f_md_{section_cle}_{f_item['id']}",
            )
        with c_exp2:
            st.download_button(
                "Télécharger (.html)",
                data=_generer_html_feuille(
                    f_item.get("titre_general", ""),
                    f_item.get("sous_titre", ""),
                    f_item.get("description", ""),
                    f_item.get("contenu_md", ""),
                    f_item.get("police", "Times New Roman"),
                    f_item.get("taille_px", 16),
                    f_item.get("alignement", "Gauche"),
                    f_item.get("liens", []),
                ).encode("utf-8"),
                file_name=f"{f_item.get('id', 'feuille')}.html",
                mime="text/html",
                key=f"dl_f_html_{section_cle}_{f_item['id']}",
            )
        if est_admin_actif:
            with c_mod:
                with st.popover("Modifier"):
                    new_tg = st.text_input("Titre général", value=f_item.get("titre_general", ""), key=f"ed_tg_{f_item['id']}")
                    new_st = st.text_input("Sous-titre", value=f_item.get("sous_titre", ""), key=f"ed_st_{f_item['id']}")
                    new_ds = st.text_input("Description", value=f_item.get("description", ""), key=f"ed_ds_{f_item['id']}")
                    new_md = st.text_area("Contenu Markdown", value=f_item.get("contenu_md", ""), height=180, key=f"ed_md_{f_item['id']}")
                    if st.button("Valider la modification", key=f"save_ed_{f_item['id']}"):
                        for item in etat["feuilles_sections"][section_cle]:
                            if item["id"] == f_item["id"]:
                                item["titre_general"] = new_tg.strip()
                                item["sous_titre"] = new_st.strip()
                                item["description"] = new_ds.strip()
                                item["contenu_md"] = new_md
                                item["date"] = store.maintenant()
                        _sauvegarder_donnees(etat, u["id"], f"Modification feuille {section_cle} : {new_tg}")
                        st.rerun()
            with c_sup:
                if st.button("Supprimer", key=f"del_f_{section_cle}_{f_item['id']}"):
                    etat["feuilles_sections"][section_cle] = [
                        x for x in etat["feuilles_sections"][section_cle] if x["id"] != f_item["id"]
                    ]
                    _sauvegarder_donnees(etat, u["id"], f"Suppression feuille {section_cle} : {f_item.get('titre_general')}")
                    st.rerun()


def afficher_organigramme_et_bios(u: dict | None):
    st.subheader("Organigramme de l'équipe et biographies")
    st.caption("Cliquez sur un membre pour lire sa biographie complète. Les visiteurs consultent en lecture seule ; seuls l'encadreur (admin) ou le stagiaire/membre concerné selon son bureau peuvent modifier.")

    comptes_map = auth.comptes()
    etat = _charger_donnees()
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
                        _sauvegarder_donnees(etat, u["id"], f"Mise à jour bio de {sel_uid}")
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
    etat = _charger_donnees()
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
                    _sauvegarder_donnees(etat, u["id"], f"Dépôt de {len(fichiers)} fichier(s) dans {bureau_cible}")
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
                    _sauvegarder_donnees(etat, u["id"], f"Suppression de {r['nom']}")
                    st.rerun()


def afficher_blog_markdown(u: dict | None):
    st.subheader("Blog professionnel — Feuilles style Word & Markdown")
    comptes_map = auth.comptes()
    bureaux_dispo = sorted({
        _bureau_de_membre(uid, info)
        for uid, info in comptes_map.items()
        if info.get("role") in ("admin", "stagiaire")
    }) or ["Bureau Général"]

    etat = _charger_donnees()
    bureau_defaut = _bureau_de_membre(u["id"], u) if (u and u.get("role") in ("admin", "stagiaire")) else bureaux_dispo[0]

    if u and u.get("role") != "visiteur":
        res = _editeur_type_word_markdown(
            cle_prefixe="blog_pro",
            bureau_defaut=bureau_defaut,
            bureaux_dispo=bureaux_dispo,
            permettre_choix_bureau=True,
            titre_bouton="Publier l'article sur le blog",
        )
        if res is not None:
            if not peut_editer_bureau(u, res["bureau"]):
                st.error("Vous n'avez pas les droits de publication pour ce bureau.")
            elif not res["titre_general"] or not res["contenu_md"].strip():
                st.warning("Renseignez au moins un titre général et un contenu.")
            else:
                article = {
                    "id": f"art_{store.maintenant().replace(' ', '_').replace(':', '')}_{u['id']}",
                    "titre": res["titre_general"],
                    "titre_general": res["titre_general"],
                    "sous_titre": res["sous_titre"],
                    "description": res["description"],
                    "bureau": res["bureau"],
                    "auteur": u.get("nom", u["id"]),
                    "auteur_id": u["id"],
                    "date": store.maintenant(),
                    "police": res["police"],
                    "taille_px": res["taille_px"],
                    "alignement": res["alignement"],
                    "gras": res["gras"],
                    "italique": res["italique"],
                    "souligne": res["souligne"],
                    "contenu_md": res["contenu_md"],
                    "liens": res["liens"],
                }
                etat["articles"].insert(0, article)
                _sauvegarder_donnees(etat, u["id"], f"Publication blog : {article['titre_general']}")
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
        _rendre_feuille_document(
            titre_general=art.get("titre_general") or art.get("titre", ""),
            sous_titre=art.get("sous_titre", ""),
            description=art.get("description", ""),
            contenu_md=art.get("contenu_md", ""),
            police_nom=art.get("police", "Times New Roman"),
            taille_px=art.get("taille_px", 16),
            alignement_nom=art.get("alignement", "Gauche"),
            gras_global=art.get("gras", False),
            italique_global=art.get("italique", False),
            souligne_global=art.get("souligne", False),
            liens=art.get("liens", []),
            meta_ligne=f"Bureau : {art.get('bureau', '')} • Auteur : {art.get('auteur', '')} • {art.get('date', '')}",
        )
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
                data=_generer_html_feuille(
                    art.get("titre_general") or art.get("titre", ""),
                    art.get("sous_titre", ""),
                    art.get("description", ""),
                    art.get("contenu_md", ""),
                    art.get("police", "Times New Roman"),
                    art.get("taille_px", 16),
                    art.get("alignement", "Gauche"),
                    art.get("liens", []),
                ).encode("utf-8"),
                file_name=f"{art.get('id', 'article')}.html",
                mime="text/html",
                key=f"dl_html_{art['id']}",
            )
        with c_del:
            if u and (u.get("role") == "admin" or (u.get("id") == art.get("auteur_id") and peut_editer_bureau(u, art.get("bureau", "")))):
                if st.button("Supprimer l'article", key=f"del_art_{art['id']}"):
                    etat["articles"] = [a for a in etat["articles"] if a.get("id") != art.get("id")]
                    _sauvegarder_donnees(etat, u["id"], f"Suppression article : {art.get('titre_general') or art.get('titre')}")
                    st.rerun()

