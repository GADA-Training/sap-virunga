"""Messages d'alerte : brouillon → soumis → validé par l'encadreur → diffusable.

Règle du plan (§9.2) : aucun message public n'est diffusé sans validation de
l'encadreur de l'OVG. Une validation ne vaut que pour le niveau pour lequel elle
a été donnée : si le niveau du site change, le message est à revalider.
"""
import html
import urllib.parse

from moteur import NIVEAUX_PUBLICS, texte_public, ACTION
from store import lire_json, ecrire_json, maintenant, journaliser

STATUTS = {"modele": "Modèle non enregistré", "brouillon": "Brouillon", "soumis": "En attente de validation",
           "valide": "Validé par l'encadreur", "sans": "Aucun message public à ce niveau"}


def etat(site, niveau, confiance_pct=None):
    """(statut, texte, enregistrement)"""
    if niveau not in NIVEAUX_PUBLICS:
        return "sans", "", None
    rec = lire_json("messages.json", {}).get(site)
    if rec and rec["niveau"] == niveau:
        return rec["statut"], rec["texte"], rec
    return "modele", texte_public(niveau, site, confiance_pct), None


def enregistrer(site, niveau, texte, uid, statut, valideur=""):
    msgs = lire_json("messages.json", {})
    msgs[site] = dict(niveau=niveau, texte=texte.strip(), statut=statut, auteur=uid, date=maintenant(),
                      valideur=valideur, date_valid=maintenant() if valideur else "")
    ecrire_json("messages.json", msgs)
    journaliser(valideur or uid, "systeme", f"Message {site} ({niveau}) : {statut}")


def public(site, niveau):
    """Texte à montrer au public, ou None s'il n'est pas validé."""
    statut, texte, _ = etat(site, niveau)
    return texte if statut == "valide" else None


def lien_whatsapp(texte):
    return "https://wa.me/?text=" + urllib.parse.quote(texte)


def lien_sms(texte):
    return "sms:?body=" + urllib.parse.quote(texte)


def fiche_html(r, texte, rec):
    """Fiche d'une page (HTML imprimable → PDF depuis le navigateur)."""
    e = html.escape
    valide = (f"Validé par {e(rec['valideur'])} le {e(rec['date_valid'])}" if rec and rec.get("valideur")
              else "NON VALIDÉ — ne pas diffuser")
    return f"""<!doctype html><html lang="fr"><meta charset="utf-8"><title>Fiche {e(r.site)}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;max-width:720px;margin:30px auto;color:#010860}}
h1{{margin:0}}.n{{display:inline-block;padding:4px 14px;border-radius:14px;background:#ECF553;font-weight:700}}
.b{{border:2px solid #010860;border-radius:12px;padding:14px;margin:14px 0}}small{{color:#555}}</style>
<h1>SAP-Virunga · Fiche d'alerte</h1><p><span class="n">{e(r.niveau)}</span> <b>{e(r.site)}</b></p>
<div class="b"><b>Score fusionné :</b> {r.score_site:.0f}/100 · <b>Confiance :</b> {r.confiance} % ({e(r.libelle_confiance)})<br>
<b>Canaux actifs :</b> {r.n_canaux_actifs} sur {r.n_canaux}<br><b>Action :</b> {e(ACTION[r.niveau])}</div>
<div class="b"><b>Message au public</b><p>{e(texte)}</p><small>{valide}</small></div>
<p><small>Prototype pédagogique OVG-GVO × UEA · aucune alerte officielle. Édité le {maintenant()}.</small></p></html>"""
