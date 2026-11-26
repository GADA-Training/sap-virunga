"""Copie les données actuelles (fichiers JSON, dépôts, photos) vers la base MySQL.

Usage (dossier du projet, environnement virtuel activé) :
    python migrer_json_vers_mysql.py

Lit les identifiants dans .streamlit/secrets.toml. Peut être relancé sans danger :
comptes, messages, tâches, réglages et dépôts sont « upsertés » ; le journal n'est copié
que si la table journal est vide. Les mots de passe restent hachés (jamais en clair).
"""
import json
import pathlib
import sys

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib
import certifi
import pymysql

RACINE = pathlib.Path(__file__).resolve().parent
DATA = RACINE / "data"


def lire(nom, defaut):
    try:
        return json.loads((DATA / nom).read_text(encoding="utf-8"))
    except Exception:
        return defaut


def n(v):
    return v if v not in ("", None) else None


def jd(v):
    return json.dumps(v, ensure_ascii=False) if v is not None else None


def main():
    chemin = RACINE / ".streamlit" / "secrets.toml"
    if not chemin.is_file():
        sys.exit("Fichier .streamlit/secrets.toml introuvable (voir secrets.toml.example).")
    s = tomllib.loads(chemin.read_text(encoding="utf-8"))["mysql"]
    cx = pymysql.connect(host=s["host"], port=int(s.get("port", 4000)), user=s["user"],
                         password=s["password"], database=s.get("database", "sapvirunga"),
                         ssl_ca=s.get("ssl_ca") or certifi.where(), ssl_verify_cert=True,
                         ssl_verify_identity=True, charset="utf8mb4", autocommit=False)
    cur = cx.cursor()

    comptes = lire("comptes.json", {})
    for uid, u in comptes.items():
        cur.execute(
            "INSERT INTO comptes (uid,nom,role,titre,email,canal,sites,sujet,livrables,bio,tel,photo,sel,`hash`,doit_changer)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE nom=VALUES(nom),"
            "role=VALUES(role),titre=VALUES(titre),email=VALUES(email),canal=VALUES(canal),sites=VALUES(sites),"
            "sujet=VALUES(sujet),livrables=VALUES(livrables),bio=VALUES(bio),tel=VALUES(tel),photo=VALUES(photo),"
            "sel=VALUES(sel),`hash`=VALUES(`hash`),doit_changer=VALUES(doit_changer)",
            (uid, u.get("nom", ""), u.get("role", "stagiaire"), u.get("titre", ""), u.get("email", ""),
             u.get("canal"), jd(u.get("sites")), u.get("sujet"), u.get("livrables"), u.get("bio", ""),
             u.get("tel", ""), u.get("photo", ""), u["sel"], u["hash"], 1 if u.get("doit_changer") else 0))
    print(f"Comptes : {len(comptes)}")

    nb = 0
    for f in (RACINE / "assets" / "profils").glob("*.jpg"):
        cur.execute("UPDATE comptes SET photo_data=%s WHERE uid=%s", (f.read_bytes(), f.stem))
        nb += cur.rowcount
    print(f"Photos : {nb}")

    taches = lire("taches.json", {})
    for uid, etapes in taches.items():
        if uid in comptes:
            cur.execute("DELETE FROM taches WHERE uid=%s", (uid,))
            for e in sorted(set(etapes)):
                cur.execute("INSERT INTO taches (uid,etape) VALUES (%s,%s)", (uid, int(e)))
    print(f"Tâches : {len(taches)} compte(s)")

    messages = lire("messages.json", {})
    for site, v in messages.items():
        cur.execute(
            "INSERT INTO messages (site,niveau,texte,statut,auteur,date_msg,valideur,date_valid) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
            " ON DUPLICATE KEY UPDATE niveau=VALUES(niveau),texte=VALUES(texte),statut=VALUES(statut),auteur=VALUES(auteur),"
            "date_msg=VALUES(date_msg),valideur=VALUES(valideur),date_valid=VALUES(date_valid)",
            (site, v["niveau"], v["texte"], v["statut"], v.get("auteur", ""), n(v.get("date")),
             v.get("valideur", ""), n(v.get("date_valid"))))
    print(f"Messages : {len(messages)}")

    depots = lire("depots.json", [])
    ignores = 0
    for d in depots:
        csv = None
        for dossier in ("depots", "valides"):
            p = DATA / dossier / f"{d['id']}.csv"
            if p.is_file():
                csv = p.read_text(encoding="utf-8")
                break
        if csv is None:
            ignores += 1
            continue
        cur.execute(
            "INSERT INTO depots (id,uid,canal,date_depot,lignes,sites,statut,commentaire,valideur,date_valid,contenu_csv)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE statut=VALUES(statut),"
            "commentaire=VALUES(commentaire),valideur=VALUES(valideur),date_valid=VALUES(date_valid)",
            (d["id"], d["uid"], d["canal"], d["date"], d["lignes"], jd(d.get("sites", [])), d["statut"],
             d.get("commentaire", ""), d.get("valideur", ""), n(d.get("date_valid")), csv))
    print(f"Dépôts : {len(depots) - ignores} copié(s), {ignores} ignoré(s) (CSV introuvable)")

    reglages = lire("reglages.json", {})
    for k, v in reglages.items():
        cur.execute("INSERT INTO reglages (cle,valeur) VALUES (%s,%s) ON DUPLICATE KEY UPDATE valeur=VALUES(valeur)",
                    (k, json.dumps(v, ensure_ascii=False)))
    print(f"Réglages : {len(reglages)}")

    cur.execute("SELECT COUNT(*) FROM journal")
    if cur.fetchone()[0] == 0:
        j = lire("journal.json", [])
        for e in j:
            extra = {k: v for k, v in e.items() if k not in ("date", "uid", "type", "texte")}
            cur.execute("INSERT INTO journal (date_evt,uid,type,texte,extra) VALUES (%s,%s,%s,%s,%s)",
                        (e["date"], e.get("uid"), e["type"], e["texte"], jd(extra) if extra else None))
        print(f"Journal : {len(j)} entrée(s)")
    else:
        print("Journal : table déjà remplie, rien copié.")

    cur.execute("INSERT INTO reglages (cle,valeur) VALUES ('_base_maj',%s) ON DUPLICATE KEY UPDATE valeur=VALUES(valeur)",
                (__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),))
    cx.commit()
    cx.close()
    print("Migration terminée.")


if __name__ == "__main__":
    main()
