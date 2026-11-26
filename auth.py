"""Comptes, mots de passe chiffrés, profils (nom, bio, photo).

Les mots de passe ne sont JAMAIS écrits en clair : PBKDF2-SHA256 avec sel
aléatoire (200 000 itérations). Les comptes vivent dans data/comptes.json et
sont créés au premier lancement à partir de equipe.MEMBRES_INITIAUX.
"""
import base64
import hashlib
import hmac
import html
import io
import re
import secrets

import streamlit as st
from PIL import Image, ImageOps

from equipe import MEMBRES_INITIAUX, MDP_INITIAL
import store
from store import RACINE, lire_json, ecrire_json, journaliser

PHOTOS = RACINE / "assets" / "profils"
ITERATIONS = 200_000
ROLES = {"admin": "Encadreur", "stagiaire": "Stagiaire", "visiteur": "Visiteur"}


def _hash(mdp, sel_hex):
    return hashlib.pbkdf2_hmac("sha256", mdp.encode("utf-8"), bytes.fromhex(sel_hex), ITERATIONS).hex()


def _empreinte(mdp):
    sel = secrets.token_hex(16)
    return sel, _hash(mdp, sel)


def comptes():
    c = lire_json("comptes.json", None)
    if c:
        return c
    c = {}
    for uid, m in MEMBRES_INITIAUX.items():
        sel, h = _empreinte(m.get("mdp", MDP_INITIAL))
        base = {k: v for k, v in m.items() if k != "mdp"}
        c[uid] = {**base, "bio": "", "tel": "", "photo": "", "sel": sel, "hash": h,
                  "doit_changer": m["role"] != "visiteur"}
    ecrire_json("comptes.json", c)
    return c


def courant():
    """Compte connecté (dict) ou None. Relu à chaque exécution : un profil modifié apparaît aussitôt."""
    uid = st.session_state.get("uid")
    c = comptes().get(uid) if uid else None
    return {**c, "id": uid} if c else None


def est_admin(u=None):
    u = u or courant()
    return bool(u and u["role"] == "admin")


def connecter(identifiant, mdp):
    uid = (identifiant or "").strip().lower()
    c = comptes().get(uid)
    if c and hmac.compare_digest(_hash(mdp or "", c["sel"]), c["hash"]):
        st.session_state.uid = uid
        journaliser(uid, "systeme", "Connexion")
        return True
    return False


def deconnecter():
    st.session_state.pop("uid", None)


def changer_mdp(uid, ancien, nouveau, confirmer):
    c = comptes()
    if not hmac.compare_digest(_hash(ancien or "", c[uid]["sel"]), c[uid]["hash"]):
        return False, "L'ancien mot de passe est incorrect."
    if nouveau != confirmer:
        return False, "Les deux nouveaux mots de passe ne correspondent pas."
    if len(nouveau) < 8:
        return False, "Le nouveau mot de passe doit contenir au moins 8 caractères."
    if nouveau == MDP_INITIAL or nouveau == ancien:
        return False, "Choisissez un mot de passe différent de l'ancien et du mot de passe initial."
    c[uid]["sel"], c[uid]["hash"] = _empreinte(nouveau)
    c[uid]["doit_changer"] = False
    ecrire_json("comptes.json", c)
    journaliser(uid, "systeme", "Mot de passe modifié")
    return True, "Mot de passe modifié."


def reinitialiser_mdp(uid, par):
    c = comptes()
    c[uid]["sel"], c[uid]["hash"] = _empreinte(MDP_INITIAL)
    c[uid]["doit_changer"] = True
    ecrire_json("comptes.json", c)
    journaliser(par, "systeme", f"Mot de passe de {uid} réinitialisé")


def maj_profil(uid, nom, email, tel, bio):
    nom, email, tel, bio = nom.strip(), email.strip(), tel.strip(), bio.strip()
    if not nom:
        return False, "Le nom ne peut pas être vide."
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False, "Adresse e-mail invalide."
    c = comptes()
    c[uid].update(nom=nom[:80], email=email[:120], tel=tel[:30], bio=bio[:400])
    ecrire_json("comptes.json", c)
    journaliser(uid, "systeme", "Profil mis à jour")
    return True, "Profil enregistré."


def enregistrer_photo(uid, fichier):
    img = ImageOps.exif_transpose(Image.open(fichier)).convert("RGB")
    tampon = io.BytesIO()
    ImageOps.fit(img, (400, 400)).save(tampon, "JPEG", quality=85)
    store.photo_ecrire(uid, tampon.getvalue())      # en base (MySQL) ou dans assets/profils
    c = comptes()
    c[uid]["photo"] = f"{uid}.jpg"
    ecrire_json("comptes.json", c)


def retirer_photo(uid):
    store.photo_supprimer(uid)
    c = comptes()
    c[uid]["photo"] = ""
    ecrire_json("comptes.json", c)


def avatar_html(u, taille=64):
    """Photo ronde, ou initiales si pas de photo. Tout texte utilisateur est échappé."""
    style = f"width:{taille}px;height:{taille}px;border-radius:50%;flex:none;"
    octets = store.photo_lire(u["id"]) if u.get("photo") else None
    if octets:
        b = base64.b64encode(octets).decode()
        return f'<img src="data:image/jpeg;base64,{b}" style="{style}object-fit:cover">'
    mots = u["nom"].replace("’", " ").replace("'", " ").split()
    ini = html.escape((mots[0][0] + (mots[-1][0] if len(mots) > 1 else "")).upper())
    return (f'<div style="{style}background:#ECF553;color:#010860;display:flex;align-items:center;'
            f'justify-content:center;font-weight:800;font-size:{int(taille * .38)}px">{ini}</div>')
