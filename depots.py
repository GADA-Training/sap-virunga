"""Dépôts de données des stagiaires et validation par l'encadreur.

Circuit : le stagiaire dépose un CSV de son canal (format contrôlé) → statut
« en_attente » → l'encadreur valide ou rejette. Un dépôt validé remplace, dans
les données actives, les lignes de mêmes (canal, site) : voir moteur.charger().

Le stockage (table MySQL `depots`, ou fichiers en mode hors ligne) est géré par store.py.
"""
import io
import uuid

import pandas as pd

import store
from store import lire_json, maintenant, journaliser

STATUTS = {"en_attente": "⏳ En attente", "valide": "✅ Validé", "rejete": "❌ Rejeté"}


def lister():
    return lire_json("depots.json", [])


def deposer(uid, canal, df):
    did = uuid.uuid4().hex[:10]
    rec = dict(id=did, uid=uid, canal=canal, date=maintenant(), lignes=int(len(df)),
               sites=sorted(df.site.astype(str).unique().tolist()),
               statut="en_attente", commentaire="", valideur="", date_valid="")
    store.depot_ajouter(rec, df.to_csv(index=False))
    journaliser(uid, "systeme", f"Dépôt {did} ({canal}, {len(df)} lignes) envoyé pour validation")
    return did


def lire_depot(did):
    texte = store.depot_csv(did)
    if texte is None:
        raise FileNotFoundError(f"Dépôt {did} introuvable.")
    return pd.read_csv(io.StringIO(texte))


def decider(did, valideur, accepte, commentaire=""):
    d = next((x for x in lister() if x["id"] == did), None)
    if not d or not store.depot_decider(did, accepte, commentaire.strip(), valideur):
        return False
    journaliser(valideur, "systeme", f"Dépôt {did} ({d['canal']}) {'validé' if accepte else 'rejeté'}")
    return True
