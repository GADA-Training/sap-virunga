import datetime as dt
import io
import pathlib
import pandas as pd
import store
from store import DATA, FUSEAU, lire_json

RACINE = pathlib.Path(__file__).resolve().parent
COLONNES = ("site", "canal", "lat", "lon", "D", "qualite", "concordance", "persistance")
CANAUX_VALIDES = ("Déformation", "Surfaces", "Forêt", "Érosion")
NIVEAUX_PUBLICS = ("Orange", "Rouge")   # seuls niveaux qui appellent un message au public


def score(D):
    return min(100, 20 * D)


# Valeurs de départ (annexe B) : « 2 observations consécutives » pour orange et rouge.
# Dans le fichier CSV, la persistance (0 à 1) et la concordance (0 à 1) servent de repère :
PERSISTANCE_MIN = 0.5     # au moins deux observations consécutives au-dessus du seuil
CONCORDANCE_MIN = 0.5     # au moins deux sources qui s'accordent


def niveau(s, q, persistant=True, deux_sources=True):
    """Niveau d'alerte selon §4.4 du plan.

    Seuils de score : 40 (D ≥ 2), 60 (D ≥ 3), 80 (D ≥ 4).
    Orange : persistance sur deux observations consécutives, ou seuil jaune confirmé par une seconde source.
    Rouge  : persistance sur deux observations consécutives ET deux sources (ou cohérence spatiale).
    Une source isolée, observée une seule fois, ne peut jamais produire une alerte rouge.
    """
    if q < 0.4: return "Indéterminé"
    if s >= 80 and persistant and deux_sources: return "Rouge"
    if s >= 60 and (persistant or deux_sources): return "Orange"
    if s >= 40: return "Jaune"
    return "Vert"


def confiance(Q, K, P):
    return round(100 * (0.4 * Q + 0.3 * K + 0.3 * P))


def libelle_confiance(c):
    """§4.5 : faible en dessous de 50 %, moyenne de 50 à 75 %, élevée au-delà de 75 %."""
    if c < 50: return "faible"
    if c <= 75: return "moyenne"
    return "élevée"


def score_site(scores, seuil=40):
    """Fusion §4.6 du plan : score max + 5 pts par canal supplémentaire >= 40."""
    s = [x for x in scores if x is not None]
    if not s:
        return 0
    return min(100, max(s) + 5 * max(0, sum(x >= seuil for x in s) - 1))


def valider_df(df, canal=None):
    """Contrôle un fichier de données avant import ou dépôt. Renvoie la liste des erreurs (vide = valide)."""
    manq = [c for c in COLONNES if c not in df.columns]
    if manq:
        return [f"Colonnes manquantes : {', '.join(manq)}. Colonnes attendues : {', '.join(COLONNES)}."]
    if df.empty:
        return ["Le fichier ne contient aucune ligne."]
    err = []
    for c in ("lat", "lon", "D", "qualite", "concordance", "persistance"):
        num = pd.to_numeric(df[c], errors="coerce")
        if num.isna().any():
            lignes = (df.index[num.isna()] + 2).tolist()[:5]
            err.append(f"Colonne « {c} » : valeur vide ou non numérique (ligne(s) {lignes}).")
    if err:
        return err
    if (df.D < 0).any():
        err.append("Colonne « D » : l'écart standardisé ne peut pas être négatif (utiliser sa valeur absolue).")
    for c in ("qualite", "concordance", "persistance"):
        if ((df[c] < 0) | (df[c] > 1)).any():
            err.append(f"Colonne « {c} » : les valeurs doivent être comprises entre 0 et 1.")
    if not df.lat.between(-90, 90).all() or not df.lon.between(-180, 180).all():
        err.append("Coordonnées hors limites (lat −90 à 90, lon −180 à 180).")
    if df.site.isna().any() or (df.site.astype(str).str.strip() == "").any():
        err.append("Colonne « site » : nom de site manquant.")
    mauvais = sorted(set(df.canal.astype(str)) - set(CANAUX_VALIDES))
    if mauvais:
        err.append(f"Colonne « canal » : valeur(s) inconnue(s) {mauvais}. Attendu : {', '.join(CANAUX_VALIDES)}.")
    elif canal and set(df.canal) != {canal}:
        err.append(f"Ce fichier doit contenir uniquement le canal « {canal} ».")
    return err


def _depots_valides():
    """[(enregistrement, DataFrame)] des dépôts validés (base MySQL ou fichiers), du plus ancien au plus récent."""
    return [(x, pd.read_csv(io.StringIO(texte))) for x, texte in store.depots_valides()]


def charger(fichier="data/demo.csv"):
    """Données actives = données de base + dépôts validés par l'encadreur.
    Un dépôt validé remplace les lignes de mêmes (canal, site)."""
    df = store.observations_lire()           # table MySQL `observations` (None en mode fichiers)
    if df is None or df.empty:
        df = pd.read_csv(RACINE / fichier)
    for col in COLONNES:
        if col not in df.columns:
            raise ValueError(f"Colonne '{col}' manquante dans {fichier}.")
    for _, n in _depots_valides():
        cles = set(zip(n.canal, n.site))
        df = df[[(c, s) not in cles for c, s in zip(df.canal, df.site)]]
        df = pd.concat([df, n[list(COLONNES)]], ignore_index=True)
    df = df.reset_index(drop=True)
    df["score"] = df.D.map(score)
    actifs = df.groupby("site").score.transform(lambda x: int((x >= 40).sum()))
    df["niveau"] = [niveau(s, q, p >= PERSISTANCE_MIN, k >= CONCORDANCE_MIN or a >= 2)
                    for s, q, p, k, a in zip(df.score, df.qualite, df.persistance, df.concordance, actifs)]
    return df


def charger_fusion(fichier="data/demo.csv"):
    """Renvoie un DataFrame agrégé par site (fusion §4.6 du plan)."""
    df = charger(fichier)
    lignes = []
    for site, g in df.groupby("site"):
        g = g.sort_values("D", ascending=False)
        scores = g.score.tolist()
        s_fusion = score_site(scores)
        q_min = g.qualite.min()
        r_dom = g.iloc[0]
        cf = confiance(r_dom.qualite, r_dom.concordance, r_dom.persistance)
        n_actifs = sum(1 for x in scores if x >= 40)
        niv = niveau(s_fusion, q_min, r_dom.persistance >= PERSISTANCE_MIN,
                     r_dom.concordance >= CONCORDANCE_MIN or n_actifs >= 2)
        lignes.append({
            "site": site, "canal": r_dom.canal, "lat": r_dom.lat, "lon": r_dom.lon,
            "score_site": s_fusion, "score_max": max(scores), "n_canaux": len(scores),
            "n_canaux_actifs": n_actifs, "persistant": bool(r_dom.persistance >= PERSISTANCE_MIN),
            "qualite_min": q_min, "niveau": niv, "confiance": cf,
            "libelle_confiance": libelle_confiance(cf),
        })
    return (pd.DataFrame(lignes).sort_values("score_site", ascending=False).reset_index(drop=True))


# ---------- dates : plus de « prochaine mise à jour » figée dans le code ----------
def derniere_maj():
    if store.mysql_actif():
        def lire_date(s):
            try:
                return dt.datetime.strptime(s, store.FORMAT_DATE).replace(tzinfo=FUSEAU)
            except Exception:
                return None
        dates = [lire_date(x.get("date_valid", "")) for x, _ in store.depots_valides()]
        dates.append(lire_date(store.base_maj_lire()))
        dates = [d for d in dates if d]
        return max(dates) if dates else dt.datetime.now(FUSEAU)
    fichiers = [RACINE / "data" / "demo.csv"]
    fichiers += [DATA / "valides" / f"{x['id']}.csv" for x, _ in store.depots_valides()]
    t = max(f.stat().st_mtime for f in fichiers if f.exists())
    return dt.datetime.fromtimestamp(t, FUSEAU)


def prochaine():
    """Prochaine mise à jour quotidienne à 08h45 (heure de Goma)."""
    now = dt.datetime.now(FUSEAU)
    c = now.replace(hour=8, minute=45, second=0, microsecond=0)
    if c <= now:
        c += dt.timedelta(days=1)
    return c.strftime("%d/%m à %Hh%M")


ACTION = {
    "Vert": "Surveillance de routine",
    "Jaune": "Vérifier les données ; informer l'encadreur",
    "Orange": "Analyse approfondie ; avis de l'OVG",
    "Rouge": "Transmission à l'OVG ; message public après validation",
    "Indéterminé": "Demander une nouvelle acquisition",
}

# --- Messages d'alerte (§7.5 du plan) : un texte public et un texte interne pour chaque niveau ---
PUBLIC = {
    "Vert": "Aucun message : situation normale",
    "Jaune": "Aucun message public ; information de l’encadreur",
    "Orange": ("Orange · {site} : déformation persistante du sol et risque "
               "élevé d’érosion. Évitez les pentes dégarnies et les berges "
               "instables. Prochaine mise à jour : {prochaine}."),
    "Rouge": ("Rouge · {site} : anomalie majeure confirmée par deux sources. "
              "Suivez uniquement les consignes officielles des autorités et "
              "de l’OVG."),
    "Indéterminé": "Aucun message public",
}

_ECART = {"Déformation": "déformation légèrement supérieure à la normale",
          "Surfaces": "changement de surface légèrement supérieur à la normale",
          "Forêt": "perturbation forestière légèrement supérieure à la normale",
          "Érosion": "érosion légèrement supérieure à la normale"}
_NOMBRES = {2: "deux", 3: "trois", 4: "quatre"}


def _virgule(x):
    return f"{x:.2f}".replace(".", ",")


def texte_public(niv, site, confiance_pct=None):
    """Texte modèle du message au public (brouillon : il doit être validé par l’encadreur).
    §4.5 : le message d'alerte mentionne toujours la confiance, avec son libellé."""
    t = PUBLIC.get(niv, "").format(site=site, prochaine=prochaine())
    if confiance_pct is not None and niv in NIVEAUX_PUBLICS:
        t += f" Confiance : {libelle_confiance(confiance_pct)} ({confiance_pct} %)."
    return t


def texte_interne(r):
    """Message interne (plus technique) pour une ligne de la fusion par site (§7.5)."""
    niv, site, sc, cf = r.niveau, r.site, round(r.score_site), r.confiance
    lib = libelle_confiance(cf)
    n = int(r.n_canaux_actifs)
    if niv == "Vert":
        return f"Situation normale à {site}, score {sc} ; prochaine mise à jour le {prochaine()}"
    if niv == "Jaune":
        ecart = _ECART.get(r.canal, "écart légèrement supérieur à la normale")
        obs = "plusieurs acquisitions" if r.persistant else "une seule acquisition"
        return f"Jaune à {site} : {ecart} sur {obs} ; vérification en cours"
    if niv == "Orange":
        accord = f"{_NOMBRES.get(n, n)} canaux concordants" if n >= 2 else "anomalie persistante"
        return f"Orange à {site}, score {sc}, confiance {cf} % ({lib}) ; {accord} ; avis de l’OVG demandé"
    if niv == "Rouge":
        accord = ("InSAR et GNSS concordants" if r.canal == "Déformation" and n < 2
                  else f"{_NOMBRES.get(n, n)} canaux concordants" if n >= 2 else "sources concordantes")
        return (f"Rouge, score {sc}, confiance {cf} % ({lib}) ; {accord} ; "
                "transmission à la hiérarchie de l’OVG")
    return (f"Données insuffisantes (qualité {_virgule(r.qualite_min)}) : aucune conclusion ; "
            "nouvelle acquisition attendue")
