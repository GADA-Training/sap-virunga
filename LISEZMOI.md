# SAP-Virunga — prototype complété (OVG-GVO × UEA, Goma)

## Lancer
```
pip install -r requirements.txt
streamlit run app.py
```
Au premier lancement, `data/comptes.json` est créé avec les 7 comptes de l'équipe (mots de passe **chiffrés**).
Mot de passe initial de tous : `Virunga2026!` — **changement obligatoire à la première connexion**.

| Identifiant | Personne | Rôle |
|---|---|---|
| arsene.fazili | FAZILI BAGALWA Arsène | Encadreur (admin) |
| monfort.bagalwa | BAGALWA RUKEZA Monfort | Encadreur (admin) |
| valentin.chishesa | CHISHESA MUGISHO Valentin | Stagiaire · canal 1 (Nyiragongo) |
| lygie.wenoka | W'ENOKA HWABA Lygie | Stagiaire · canal 1 (Renga, Shasha) |
| christelle.cibalonza | CIBALONZA Christelle Bagula | Stagiaire · canal 2 (Nyamulagira) |
| grace.kahindo | KAHINDO Grâce | Stagiaire · canal 3 (forêt) |
| ornella.owene | OWENE Ornella Mukome | Stagiaire · canal 4 (Kihira, Shasha) |
| visiteur / visiteur | Observateur | Lecture seule |

## Architecture : qui appelle quoi
```
 CSV (data/demo.csv)  +  dépôts validés (data/valides/*.csv)
              │
        moteur.py  ── score = min(100, 20·D) → niveau (vert/jaune/orange/rouge/indéterminé)
              │       → fusion par site (+5 pts/canal ≥ 40) → confiance
              ▼
   pages (views/*.py) ◄── style.py (thème verre/relief, assistant, barre latérale)
              ▲
   app.py  : menu selon le rôle ── auth.py (comptes, profils) ── store.py (JSON + journal)
```
| Fichier | Rôle |
|---|---|
| `app.py` | Point d'entrée : connexion, mot de passe initial, menu par rôle |
| `moteur.py` | Calcul du score, niveau, confiance, fusion ; contrôle des CSV ; dates dynamiques |
| `auth.py` | Comptes chiffrés (PBKDF2), profil (nom, e-mail, tél., bio, photo), mot de passe |
| `equipe.py` | Équipe, canaux, étapes par stagiaire (plan §6), calendrier S4–S14 (plan §8.2) |
| `depots.py` | Dépôt d'un CSV par un stagiaire → validation/rejet par l'encadreur |
| `diffusion.py` | Messages publics : brouillon → soumis → validé ; liens WhatsApp/SMS ; fiche 1 page |
| `store.py` | Lecture/écriture JSON et journal commun (remplaçable par SQLite plus tard) |
| `style.py` | Thème, barre latérale, assistant virtuel |
| `views/` | 14 pages (12 d'origine + **Mon bureau** + **Bureau encadreur**) |

## Les bureaux
**Mon bureau** (stagiaire) : Profil (photo, nom, bio, e-mail, tél., mot de passe) · Mon canal (ses scores en direct) ·
Mes tâches (étapes du plan, avancement) · Mes dépôts (modèle CSV, contrôle automatique, statut) · Journal de traçabilité.
**Mon bureau** (encadreur) : Profil · Journal.
**Bureau encadreur** : Équipe (avancement, activité) · Dépôts à valider/rejeter · Messages à valider ·
Journal complet · Comptes (réinitialisation de mot de passe).

Circuit des données : le stagiaire dépose → contrôle automatique des colonnes et des valeurs → l'encadreur valide →
les lignes de même (canal, site) remplacent celles de la base → tableau de bord, carte et alertes se mettent à jour.
Circuit des messages : aucun message public n'apparaît (accueil, page Message, assistant) tant que l'encadreur ne l'a pas
validé ; une validation ne vaut que pour le niveau en cours.

## Corrections apportées au code d'origine
- Mots de passe en clair dans le code (`admin123`) → comptes chiffrés, changement obligatoire, blocage après 5 essais.
- Le mode jour/nuit était partagé par **tous** les utilisateurs (fichier commun) → désormais propre à chaque session.
- « Prochaine mise à jour 12/11 » figée dans le code → calculée (08h45 heure de Goma).
- L'import CSV de l'admin plantait sur un mauvais fichier → contrôle complet + sauvegarde de l'ancien.
- Carte : points tous jaunes → couleur du niveau. Détail du site : jauge ajoutée. Qualité : qualité globale ajoutée.
- Le changement de mot de passe était simulé → réel.

## Limites connues (à traiter ensuite)
1. **Stockage** : fichiers JSON/CSV. Sur Streamlit Community Cloud, le disque est effacé à chaque redémarrage
   (comptes, dépôts, photos perdus). Il faut un hébergement avec disque persistant ou la base SQLite prévue par le plan (§3.3).
2. **Moteur incomplet par rapport au plan §4** : il reçoit `D` déjà calculé. Restent à coder : contrôle qualité Q,
   standardisation z robuste (médiane/MAD), moyenne mobile EWMA, calibration/validation/test.
3. **Règle de confirmation** : le plan interdit un rouge à source unique observée une seule fois ; le code applique seulement les seuils de score.
4. **Historique** : courbe simulée ; il faut enregistrer un instantané des scores à chaque mise à jour.
5. Pas encore : SMS/WhatsApp envoyés automatiquement (liens à ouvrir seulement), PDF natif de la fiche (HTML imprimable), mode hors-ligne.
6. Les stagiaires ne sont **pas** administrateurs (le plan parlait de « sept administrateurs ») : seul l'encadreur valide. Pour changer : `role` dans `equipe.py`.
