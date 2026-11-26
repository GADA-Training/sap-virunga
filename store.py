"""Stockage de l'application SAP-Virunga.

Deux modes, choisis automatiquement :
- MySQL (TiDB Cloud) : si la section [mysql] existe dans .streamlit/secrets.toml
    (en local) ou dans les « Secrets » de Streamlit Community Cloud (en ligne) ;
- fichiers JSON dans data/ : sinon (comportement d'origine, utile hors ligne).

Les pages n'appellent que : lire_json, ecrire_json, journaliser, maintenant, et les
fonctions de dépôts / observations / réglages / photos / médias ci-dessous. Les noms
d'origine sont conservés.

Règles de sécurité :
- identifiants uniquement via st.secrets (jamais dans le code) ;
- connexion TLS avec vérification du certificat et du nom d'hôte ;
- si la base est injoignable, on LÈVE une erreur au lieu de renvoyer une valeur
    par défaut (sinon l'application pourrait recréer les comptes initiaux).
"""
import json
import pathlib
import shutil
import threading
import time
import datetime as dt

import pandas as pd
import streamlit as st

RACINE = pathlib.Path(__file__).resolve().parent
DATA = RACINE / "data"
ASSETS = RACINE / "assets"
PHOTOS = ASSETS / "profils"
FUSEAU = dt.timezone(dt.timedelta(hours=2))  # Goma : UTC+2
FORMAT_DATE = "%Y-%m-%d %H:%M"
COLONNES_OBS = ("site", "canal", "lat", "lon", "D", "qualite", "concordance", "persistance")


def maintenant():
    return dt.datetime.now(FUSEAU).strftime(FORMAT_DATE)


def mysql_actif():
    try:
        return "mysql" in st.secrets
    except Exception:
        return False


# =====================================================================
#  Connexion MySQL
# =====================================================================
_VERROU = threading.RLock()


@st.cache_resource(show_spinner=False)
def _connexion():
    import certifi
    import pymysql
    s = st.secrets["mysql"]
    return pymysql.connect(
        host=s["host"], port=int(s.get("port", 4000)),
        user=s["user"], password=s["password"],
        database=s.get("database", "sapvirunga"),
        ssl_ca=s.get("ssl_ca") or certifi.where(),
        ssl_verify_cert=True, ssl_verify_identity=True,
        charset="utf8mb4", autocommit=True,
        connect_timeout=15, read_timeout=30, write_timeout=30,
        cursorclass=pymysql.cursors.DictCursor,
    )


ATTENTES = (0, 2, 5)  # secondes d'attente avant chaque tentative (DNS ou réseau lent)


class BaseInjoignable(RuntimeError):
    pass


def _injoignable(exc):
    return BaseInjoignable(
        "Base de données injoignable (réseau ou DNS lent). Réessayez dans quelques secondes. "
        f"Détail : {exc}")


def _sql(sql, args=None, lire=False, plusieurs=False):
    """Exécute une requête. Réessaie 3 fois si la connexion est lente ou a été coupée."""
    import pymysql
    with _VERROU:
        derniere = None
        for attente in ATTENTES:
            if attente:
                time.sleep(attente)
            try:
                cx = _connexion()
                cx.ping(reconnect=True)
                with cx.cursor() as cur:
                    if plusieurs:
                        if args:
                            cur.executemany(sql, args)
                        return 0
                    cur.execute(sql, args)
                    return cur.fetchall() if lire else cur.rowcount
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError, OSError) as e:
                derniere = e
                _connexion.clear()
        raise _injoignable(derniere) from derniere


def _transaction(ordres):
    """ordres : liste de (sql, args, plusieurs). Tout réussit ou rien n'est écrit."""
    import pymysql
    with _VERROU:
        derniere = None
        for attente in ATTENTES:
            if attente:
                time.sleep(attente)
            try:
                cx = _connexion()
                cx.ping(reconnect=True)
                cx.begin()
                try:
                    with cx.cursor() as cur:
                        for sql, args, plusieurs in ordres:
                            if plusieurs:
                                if args:
                                    cur.executemany(sql, args)
                            else:
                                cur.execute(sql, args)
                    cx.commit()
                    return
                except Exception:
                    cx.rollback()
                    raise
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError, OSError) as e:
                derniere = e
                _connexion.clear()
        raise _injoignable(derniere) from derniere


# ---------- petits convertisseurs ----------
def _s(v):
    if v is None:
        return ""
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime(FORMAT_DATE)
    return str(v)


def _n(v):
    """'' -> None (pour les colonnes DATETIME)."""
    return v if v not in ("", None) else None


def _js(v):
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8")
    return json.loads(v) if isinstance(v, str) else v


def _jd(v):
    return json.dumps(v, ensure_ascii=False) if v is not None else None


# =====================================================================
#  Lecteurs / écrivains MySQL (même forme que les anciens fichiers JSON)
# =====================================================================
def _lire_comptes():
    rows = _sql("SELECT uid,nom,role,titre,email,canal,sites,sujet,livrables,bio,tel,photo,"
                "sel,`hash`,doit_changer FROM comptes", lire=True)
    out = {}
    for r in rows:
        d = dict(nom=r["nom"], role=r["role"], titre=r["titre"] or "", email=r["email"] or "",
                 bio=r["bio"] or "", tel=r["tel"] or "", photo=r["photo"] or "",
                 sel=r["sel"], hash=r["hash"], doit_changer=bool(r["doit_changer"]))
        if r["canal"] is not None:
            d["canal"] = int(r["canal"])
        if r["sites"] is not None:
            d["sites"] = _js(r["sites"])
        for k in ("sujet", "livrables"):
            if r[k] is not None:
                d[k] = r[k]
        out[r["uid"]] = d
    return out


def _ecrire_comptes(c):
    lignes = [(uid, u.get("nom", ""), u.get("role", "stagiaire"), u.get("titre", ""), u.get("email", ""),
               u.get("canal"), _jd(u.get("sites")), u.get("sujet"), u.get("livrables"),
               u.get("bio", ""), u.get("tel", ""), u.get("photo", ""), u["sel"], u["hash"],
               1 if u.get("doit_changer") else 0) for uid, u in c.items()]
    _sql("INSERT INTO comptes (uid,nom,role,titre,email,canal,sites,sujet,livrables,bio,tel,photo,"
         "sel,`hash`,doit_changer) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
         "ON DUPLICATE KEY UPDATE nom=VALUES(nom),role=VALUES(role),titre=VALUES(titre),"
         "email=VALUES(email),canal=VALUES(canal),sites=VALUES(sites),sujet=VALUES(sujet),"
         "livrables=VALUES(livrables),bio=VALUES(bio),tel=VALUES(tel),photo=VALUES(photo),"
         "sel=VALUES(sel),`hash`=VALUES(`hash`),doit_changer=VALUES(doit_changer)",
         lignes, plusieurs=True)


def _lire_depots():
    rows = _sql("SELECT id,uid,canal,date_depot,lignes,sites,statut,commentaire,valideur,date_valid "
                "FROM depots ORDER BY date_depot, id", lire=True)
    return [dict(id=r["id"], uid=r["uid"], canal=r["canal"], date=_s(r["date_depot"]),
                 lignes=int(r["lignes"]), sites=_js(r["sites"]) or [], statut=r["statut"],
                 commentaire=r["commentaire"] or "", valideur=r["valideur"] or "",
                 date_valid=_s(r["date_valid"])) for r in rows]


def _lire_messages():
    rows = _sql("SELECT site,niveau,texte,statut,auteur,date_msg,valideur,date_valid FROM messages", lire=True)
    return {r["site"]: dict(niveau=r["niveau"], texte=r["texte"], statut=r["statut"],
                            auteur=r["auteur"] or "", date=_s(r["date_msg"]),
                            valideur=r["valideur"] or "", date_valid=_s(r["date_valid"])) for r in rows}


def _ecrire_messages(m):
    lignes = [(site, v["niveau"], v["texte"], v["statut"], v.get("auteur", ""), _n(v.get("date")),
               v.get("valideur", ""), _n(v.get("date_valid"))) for site, v in m.items()]
    _sql("INSERT INTO messages (site,niveau,texte,statut,auteur,date_msg,valideur,date_valid) "
         "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE niveau=VALUES(niveau),"
         "texte=VALUES(texte),statut=VALUES(statut),auteur=VALUES(auteur),date_msg=VALUES(date_msg),"
         "valideur=VALUES(valideur),date_valid=VALUES(date_valid)", lignes, plusieurs=True)


def _lire_taches():
    out = {}
    for r in _sql("SELECT uid,etape FROM taches ORDER BY uid,etape", lire=True):
        out.setdefault(r["uid"], []).append(int(r["etape"]))
    return out


def _ecrire_taches(t):
    paires = [(uid, int(e)) for uid, etapes in t.items() for e in sorted(set(etapes))]
    _transaction([("DELETE FROM taches", None, False),
                  ("INSERT INTO taches (uid,etape) VALUES (%s,%s)", paires, True)])


def _lire_journal():
    rows = _sql("SELECT date_evt,uid,type,texte,extra FROM (SELECT id,date_evt,uid,type,texte,extra "
                "FROM journal ORDER BY id DESC LIMIT 3000) t ORDER BY id", lire=True)
    out = []
    for r in rows:
        e = {"date": _s(r["date_evt"]), "uid": r["uid"], "type": r["type"], "texte": r["texte"]}
        e.update(_js(r["extra"]) or {})
        out.append(e)
    return out


_LECTEURS = {"comptes.json": _lire_comptes, "depots.json": _lire_depots, "messages.json": _lire_messages,
             "taches.json": _lire_taches, "journal.json": _lire_journal}
_ECRIVAINS = {"comptes.json": _ecrire_comptes, "messages.json": _ecrire_messages,
              "taches.json": _ecrire_taches}


@st.cache_data(ttl=30, show_spinner=False)
def _lire_mysql(nom):
    return _LECTEURS[nom]()


# =====================================================================
#  API d'origine : lire_json / ecrire_json / journaliser
# =====================================================================
def lire_json(nom, defaut):
    if mysql_actif() and nom in _LECTEURS:
        return _lire_mysql(nom)  # erreur propagée si la base est injoignable (voulu)
    try:
        return json.loads((DATA / nom).read_text(encoding="utf-8"))
    except Exception:
        return defaut


def ecrire_json(nom, objet):
    if mysql_actif():
        if nom not in _ECRIVAINS:
            raise ValueError(f"« {nom} » n'est pas écrit via ecrire_json en mode MySQL.")
        _ECRIVAINS[nom](objet)
        _lire_mysql.clear()
        return
    DATA.mkdir(exist_ok=True)
    tmp = DATA / (nom + ".tmp")
    tmp.write_text(json.dumps(objet, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DATA / nom)  # écriture atomique


def journaliser(uid, type_, texte, **extra):
    """type_ : 'systeme' (actions automatiques) ou 'trace' (journal de traçabilité
    saisi par un stagiaire : outil, version, paramètres)."""
    if mysql_actif():
        _sql("INSERT INTO journal (date_evt,uid,type,texte,extra) VALUES (%s,%s,%s,%s,%s)",
             (maintenant(), uid, type_, texte, _jd(extra) if extra else None))
        _lire_mysql.clear()
        return
    j = lire_json("journal.json", [])
    j.append({"date": maintenant(), "uid": uid, "type": type_, "texte": texte, **extra})
    ecrire_json("journal.json", j[-3000:])


# =====================================================================
#  Dépôts (le CSV est conservé dans la base : le disque du cloud est éphémère)
# =====================================================================
def depot_ajouter(rec, csv_texte):
    if mysql_actif():
        _sql("INSERT INTO depots (id,uid,canal,date_depot,lignes,sites,statut,commentaire,valideur,"
             "date_valid,contenu_csv) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
             (rec["id"], rec["uid"], rec["canal"], rec["date"], rec["lignes"], _jd(rec["sites"]),
              rec["statut"], rec["commentaire"], rec["valideur"], _n(rec["date_valid"]), csv_texte))
        _lire_mysql.clear()
        _depots_valides_mysql.clear()
        return
    (DATA / "depots").mkdir(parents=True, exist_ok=True)
    (DATA / "depots" / f"{rec['id']}.csv").write_text(csv_texte, encoding="utf-8")
    liste = lire_json("depots.json", [])
    liste.append(rec)
    ecrire_json("depots.json", liste)


def depot_csv(did):
    """Texte CSV d'un dépôt (ou None)."""
    if mysql_actif():
        r = _sql("SELECT contenu_csv FROM depots WHERE id=%s", (did,), lire=True)
        return r[0]["contenu_csv"] if r else None
    p = DATA / "depots" / f"{did}.csv"
    return p.read_text(encoding="utf-8") if p.is_file() else None


def depot_decider(did, accepte, commentaire, valideur):
    """Passe un dépôt « en_attente » à valide/rejete. Renvoie True si la décision a été prise."""
    statut = "valide" if accepte else "rejete"
    date = maintenant()
    if mysql_actif():
        n = _sql("UPDATE depots SET statut=%s,commentaire=%s,valideur=%s,date_valid=%s "
                 "WHERE id=%s AND statut='en_attente'", (statut, commentaire, valideur, date, did))
        _lire_mysql.clear()
        _depots_valides_mysql.clear()
        return n == 1
    liste = lire_json("depots.json", [])
    for d in liste:
        if d["id"] == did and d["statut"] == "en_attente":
            d.update(statut=statut, commentaire=commentaire, valideur=valideur, date_valid=date)
            if accepte:
                (DATA / "valides").mkdir(parents=True, exist_ok=True)
                shutil.copy(DATA / "depots" / f"{did}.csv", DATA / "valides" / f"{did}.csv")
            ecrire_json("depots.json", liste)
            return True
    return False


@st.cache_data(ttl=30, show_spinner=False)
def _depots_valides_mysql():
    rows = _sql("SELECT id,date_valid,contenu_csv FROM depots WHERE statut='valide' "
                "ORDER BY date_valid, id", lire=True)
    return [({"id": r["id"], "date_valid": _s(r["date_valid"])}, r["contenu_csv"]) for r in rows]


def depots_valides():
    """[(enregistrement, texte_csv)] des dépôts validés, du plus ancien au plus récent."""
    if mysql_actif():
        return _depots_valides_mysql()
    d = [x for x in lire_json("depots.json", []) if x.get("statut") == "valide"]
    d.sort(key=lambda x: x.get("date_valid", ""))
    out = []
    for x in d:
        p = DATA / "valides" / f"{x['id']}.csv"
        if p.is_file():
            out.append((x, p.read_text(encoding="utf-8")))
    return out


# =====================================================================
#  Observations (données de base) : table MySQL, ou data/demo.csv hors ligne
# =====================================================================
@st.cache_data(ttl=30, show_spinner=False)
def _obs_mysql():
    rows = _sql("SELECT site,canal,lat,lon,D,qualite,concordance,persistance FROM observations ORDER BY id",
                lire=True)
    return pd.DataFrame(rows, columns=list(COLONNES_OBS))


def observations_lire():
    """DataFrame des observations de base en mode MySQL ; None en mode fichiers."""
    return _obs_mysql() if mysql_actif() else None


def observations_remplacer(df):
    df = df[list(COLONNES_OBS)].drop_duplicates(["canal", "site"], keep="last")
    lignes = [tuple(None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in row)
              for row in df.itertuples(index=False, name=None)]
    _transaction([("DELETE FROM observations", None, False),
                  ("INSERT INTO observations (site,canal,lat,lon,D,qualite,concordance,persistance) "
                   "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", lignes, True)])
    _obs_mysql.clear()


# =====================================================================
#  Réglages d'apparence et date de la dernière mise à jour des données de base
# =====================================================================
def reglages_lire():
    """dict en mode MySQL ; None en mode fichiers (style.py lit alors le fichier)."""
    if not mysql_actif():
        return None
    out = {}
    for r in _sql("SELECT cle,valeur FROM reglages", lire=True):
        if r["cle"].startswith("_"):
            continue
        try:
            out[r["cle"]] = json.loads(r["valeur"])
        except Exception:
            out[r["cle"]] = r["valeur"] or ""
    return out


def reglages_ecrire(r):
    lignes = [(k, json.dumps(v, ensure_ascii=False)) for k, v in r.items() if not k.startswith("_")]
    _sql("INSERT INTO reglages (cle,valeur) VALUES (%s,%s) ON DUPLICATE KEY UPDATE valeur=VALUES(valeur)",
         lignes, plusieurs=True)


def base_maj_lire():
    r = _sql("SELECT valeur FROM reglages WHERE cle='_base_maj'", lire=True)
    return r[0]["valeur"] if r else ""


def base_maj_ecrire():
    _sql("INSERT INTO reglages (cle,valeur) VALUES ('_base_maj',%s) ON DUPLICATE KEY UPDATE valeur=VALUES(valeur)",
         (maintenant(),))


# =====================================================================
#  Photos de profil (en base : le disque du cloud est éphémère)
# =====================================================================
@st.cache_data(ttl=120, show_spinner=False)
def _photo_mysql(uid):
    r = _sql("SELECT photo_data FROM comptes WHERE uid=%s", (uid,), lire=True)
    return bytes(r[0]["photo_data"]) if r and r[0]["photo_data"] else None


def photo_lire(uid):
    if mysql_actif():
        return _photo_mysql(uid)
    p = PHOTOS / f"{uid}.jpg"
    return p.read_bytes() if p.is_file() else None


def photo_ecrire(uid, octets):
    if mysql_actif():
        _sql("UPDATE comptes SET photo_data=%s WHERE uid=%s", (octets, uid))
        _photo_mysql.clear()
        return
    PHOTOS.mkdir(parents=True, exist_ok=True)
    (PHOTOS / f"{uid}.jpg").write_bytes(octets)


def photo_supprimer(uid):
    if mysql_actif():
        _sql("UPDATE comptes SET photo_data=NULL WHERE uid=%s", (uid,))
        _photo_mysql.clear()
        return
    p = PHOTOS / f"{uid}.jpg"
    if p.exists():
        p.unlink()


# =====================================================================
#  Médias (fond, accueil, galerie : persistés dans TiDB Cloud)
# =====================================================================
@st.cache_data(ttl=120, show_spinner=False)
def _media_mysql(cle):
    r = _sql("SELECT data, mime_type FROM medias WHERE cle=%s", (cle,), lire=True)
    if not r or not r[0].get("data"):
        return None
    return bytes(r[0]["data"]), (r[0].get("mime_type") or "image/jpeg")


def media_lire_detail(cle):
    """Retourne (octets, mime_type) ou None."""
    if mysql_actif():
        return _media_mysql(cle)
    for candidat in (DATA / cle, ASSETS / cle):
        if candidat.is_file():
            mime = "image/png" if candidat.suffix.lower() == ".png" else "image/jpeg"
            return candidat.read_bytes(), mime
    return None


def media_ecrire(cle, categorie, octets, nom_fich="", legende="", mime_type="image/jpeg"):
    """Enregistre ou met à jour une image ('fond', 'accueil', 'galerie') en base."""
    if mysql_actif():
        _sql(
            "INSERT INTO medias (cle,categorie,nom_fich,legende,mime_type,data) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE categorie=VALUES(categorie),nom_fich=VALUES(nom_fich),"
            "legende=VALUES(legende),mime_type=VALUES(mime_type),data=VALUES(data)",
            (cle, categorie, nom_fich, legende, mime_type, octets),
        )
        _media_mysql.clear()
        _galerie_mysql.clear()
        return
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / cle).write_bytes(octets)


@st.cache_data(ttl=120, show_spinner=False)
def _galerie_mysql():
    rows = _sql(
        "SELECT cle,nom_fich,legende,mime_type,data FROM medias "
        "WHERE categorie='galerie' ORDER BY maj_le DESC",
        lire=True,
    )
    out = []
    for r in rows:
        if r.get("data"):
            out.append({
                "cle": r["cle"],
                "nom_fich": r["nom_fich"],
                "legende": r["legende"],
                "mime_type": r["mime_type"] or "image/jpeg",
                "data": bytes(r["data"]),
            })
    return out


def galerie_liste():
    """Retourne la liste des médias de catégorie 'galerie'."""
    return _galerie_mysql() if mysql_actif() else []


def media_supprimer(cle):
    if mysql_actif():
        _sql("DELETE FROM medias WHERE cle=%s", (cle,))
        _media_mysql.clear()
        _galerie_mysql.clear()
        return
    for candidat in (DATA / cle, ASSETS / cle):
        if candidat.exists():
            candidat.unlink()