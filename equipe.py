"""Données statiques tirées du plan « SAP-Virunga » (OVG-GVO × UEA, nov. 2026) :
équipe, canaux, étapes de travail par stagiaire (§6), calendrier (§8.2)."""
import datetime as dt

MDP_INITIAL = "Virunga2026!"   # à changer à la première connexion (imposé par l'application)

CANAUX = {
    1: dict(nom="Déformation", titre="Déformation du sol",
            zones="Nyiragongo · Renga · Shasha",
            donnees="InSAR Sentinel-1 et GNSS",
            indicateur="Vitesse et cumul de déformation (mm)",
            maj="À chaque acquisition satellitaire ; en continu pour le GNSS"),
    2: dict(nom="Surfaces", titre="Surfaces volcaniques et habitat",
            zones="Nyamulagira, secteur Mikeno",
            donnees="Optique (Landsat, Sentinel-2) et radar",
            indicateur="Surface modifiée, distance au cratère, exposition de l'habitat",
            maj="À chaque image exploitable"),
    3: dict(nom="Forêt", titre="Paysage forestier",
            zones="Parc national des Virunga",
            donnees="Cartes d'occupation du sol 2000–2025",
            indicateur="Fragmentation et connectivité structurelle",
            maj="Annuelle ou après un épisode éruptif"),
    4: dict(nom="Érosion", titre="Érosion hydrique",
            zones="Bassins de Kihira et de Shasha",
            donnees="Pluie satellitaire, relief, sols, occupation du sol",
            indicateur="Perte de sol potentielle et cumul de pluie",
            maj="Pluie : quotidienne ; sensibilité : saisonnière"),
}

# role : admin (encadreur, droits d'administration) · stagiaire · visiteur (lecture seule)
MEMBRES_INITIAUX = {
    "arsene.fazili": dict(nom="FAZILI BAGALWA Arsène", role="admin", titre="Encadreur",
                          email="faziliarsene2@gmail.com"),
    "monfort.bagalwa": dict(nom="BAGALWA RUKEZA Monfort", role="admin", titre="Encadreur",
                            email="montfortbagalwa2024@gmail.com"),
    "valentin.chishesa": dict(
        nom="CHISHESA MUGISHO Valentin", role="stagiaire", titre="Stagiaire · Master 1 UEA",
        email="arielchishesa@gmail.com", canal=1, sites=["Nyiragongo"],
        sujet="Déformation du sol au Nyiragongo et modèle de détection d'anomalies",
        livrables="Interférogramme et carte de déformation (n° 5) ; prototype (n° 8)"),
    "lygie.wenoka": dict(
        nom="W'ENOKA HWABA Lygie", role="stagiaire", titre="Stagiaire · Master 1 UEA",
        email="hwabalygie@gmail.com", canal=1, sites=["Renga", "Shasha"],
        sujet="Déformations du sol dans les bassins de Renga et de Shasha ; chaîne automatique et interface",
        livrables="Prototype (n° 8) ; rapport (n° 10)"),
    "christelle.cibalonza": dict(
        nom="CIBALONZA Christelle Bagula", role="stagiaire", titre="Stagiaire · Master 1 UEA",
        email="bagulachristelle24@gmail.com", canal=2, sites=["Nyamulagira"],
        sujet="Changements de surface liés au Nyamulagira et habitat du gorille de montagne (Mikeno, 2010–2025)",
        livrables="Carte thématique (n° 6) ; analyse (n° 7)"),
    "grace.kahindo": dict(
        nom="KAHINDO Grâce", role="stagiaire", titre="Stagiaire · Master 1 UEA",
        email="Theresakahindograce@gmail.com", canal=3, sites=["Nyamulagira"],
        sujet="Perturbations du Nyamulagira, fragmentation et connectivité des forêts (2000–2025)",
        livrables="Analyse avec graphique ou tableau (n° 7)"),
    "ornella.owene": dict(
        nom="OWENE Ornella Mukome", role="stagiaire", titre="Stagiaire · Master 1 UEA",
        email="oweneornellamukome@gmail.com", canal=4, sites=["Kihira", "Shasha"],
        sujet="Érosion hydrique dans les bassins de Kihira et de Shasha (2015–2025)",
        livrables="Carte thématique (n° 6) ; fiche de communication (n° 9)"),
    "visiteur": dict(nom="Observateur", role="visiteur", titre="Visiteur (lecture seule)",
                     email="", mdp="visiteur"),
}

# (étape, séance) — plan §6.1 à §6.5
TACHES = {
    "valentin.chishesa": [
        ("Inventorier les piles Sentinel-1 et les séries GNSS", "S4"),
        ("Former les interférogrammes (SNAP : TOPS Split → déroulement → géocodage)", "S7–S9"),
        ("Convertir la phase en déformation LOS ; séries D1 et D2", "S9"),
        ("Traiter le GNSS et le projeter dans la ligne de visée", "S8"),
        ("Intégrer InSAR et GNSS (moyenne pondérée) ; accord A", "S9"),
        ("Calibrer : médiane et MAD sur la période calme", "S8–S9"),
        ("Valider les seuils puis tester les trois variantes (InSAR, GNSS, intégré)", "S10–S12"),
        ("Calculer Q, z, D, score et confiance ; exporter canal1_nyiragongo", "S10–S11"),
    ],
    "lygie.wenoka": [
        ("Délimiter les bassins ; réunir ≥ 30 acquisitions Sentinel-1", "S4"),
        ("Produire les interférogrammes (HyP3 ou SNAP en ligne de commande)", "S7–S9"),
        ("Construire la série temporelle par inversion SBAS ; masque de cohérence", "S9"),
        ("Réduire l'atmosphère et le bruit", "S9"),
        ("Cartographier les anomalies (z, D, zones connexes)", "S9–S10"),
        ("Examiner les anomalies persistantes sur les versants", "S10"),
        ("Automatiser la chaîne Python et R (run_all, journal)", "S10–S11"),
        ("Tester la généralisation des paramètres de Valentin", "S11–S12"),
        ("Brancher la chaîne sur l'application ; fiche de description du prototype", "S10–S11"),
    ],
    "christelle.cibalonza": [
        ("Définir zone, périodes, classes de changement ; plan d'échantillonnage", "S4"),
        ("Préparer les images optiques Landsat et Sentinel-2", "S5–S7"),
        ("Ajouter le radar : rapport logarithmique avant/après", "S7–S8"),
        ("Détecter les changements par trois méthodes comparées", "S8–S9"),
        ("Évaluer : ≥ 50 points par classe, exactitude globale, kappa", "S9"),
        ("Mesurer la surface modifiée (S1) et la distance au cratère (S2)", "S9–S10"),
        ("Modéliser l'habitat favorable du gorille (MaxEnt) avec et sans perturbation", "S9–S10"),
        ("Calculer l'exposition (S3), le gain d'AUC (S4) et l'indice d'abondance", "S10"),
        ("Calculer Q et exporter canal2_nyamulagira", "S10–S11"),
    ],
    "grace.kahindo": [
        ("Harmoniser les cartes d'occupation du sol 2000–2025", "S4–S6"),
        ("Extraire le masque forestier et les empreintes de perturbation", "S6–S7"),
        ("Mesurer la fragmentation (F1, F2)", "S7–S8"),
        ("Évaluer forme et isolement des taches ; classement", "S8"),
        ("Calculer la connectivité structurelle (F3) à 100 m, 500 m, 1 000 m", "S8–S9"),
        ("Désigner les secteurs prioritaires (dPC)", "S9–S10"),
        ("Détecter les tendances : Mann-Kendall et pente de Sen", "S10"),
        ("Calibrer (bootstrap) et exporter canal3_virunga", "S10–S11"),
    ],
    "ornella.owene": [
        ("Délimiter les bassins de Kihira et de Shasha ; grille de 30 m", "S4–S5"),
        ("Préparer la pluie CHIRPS 2015–2025", "S5"),
        ("Calculer R (érosivité)", "S7"),
        ("Calculer K (érodibilité)", "S7"),
        ("Calculer LS (facteur topographique)", "S7"),
        ("Établir C et P pour 2015, 2020 et 2025", "S6–S7"),
        ("Calculer A (RUSLE) et cartographier les zones prioritaires", "S8–S9"),
        ("Déclencheur pluviométrique E2 (cumul 3 jours > P90)", "S8–S10"),
        ("Couverture de sol nu E3", "S9"),
        ("Valider par le terrain : taux de capture des ravines", "S6, S10–S12"),
        ("Exporter canal4_kihira_shasha", "S10–S11"),
    ],
}

# (code, date, travaux, résultat) — plan §8.2
SEANCES = [
    ("S4", "2026-11-10", "Cadrage ; inventaire des données ; choix de l'indicateur central", "Liste des données et des indicateurs"),
    ("S5", "2026-11-12", "Contrôle qualité des jeux de données ; premiers calculs de standardisation", "Rapport de qualité par jeu"),
    ("S6", "2026-11-14", "Observation de terrain ou exercice équivalent", "Fiches d'observation (n° 3)"),
    ("S7", "2026-11-17", "Prise en main de SNAP et du SIG ; premiers interférogrammes", "Données prêtes pour la calibration"),
    ("S8", "2026-11-19", "InSAR (1/2) ; début de la calibration des situations normales", "Médiane et MAD estimés"),
    ("S9", "2026-11-21", "InSAR (2/2) ; première carte ; calibration du canal 1 achevée", "Interférogramme (n° 5) ; carte v1"),
    ("S10", "2026-11-24", "Validation ; réglage des seuils ; fusion par site ; développement de l'interface", "Seuils validés"),
    ("S11", "2026-11-26", "Prototype fonctionnel ; test des trois scénarios ; fiches de description et de communication", "Livrables n° 8 et n° 9"),
    ("S12", "2026-11-28", "Mesure finale des performances ; rédaction du rapport", "Résultats consolidés"),
    ("S13", "2026-12-01", "Finalisation ; répétition de la démonstration", "Rapport provisoire"),
    ("S14", "2026-12-03", "Présentation orale avec démonstration ; remise du rapport final", "Livrables n° 10 et n° 11"),
]


def prochaine_seance(aujourdhui=None):
    """Première séance dont la date est aujourd'hui ou plus tard (None si terminé)."""
    j = aujourdhui or dt.datetime.now(dt.timezone(dt.timedelta(hours=2))).date()
    for code, d, travaux, res in SEANCES:
        dd = dt.date.fromisoformat(d)
        if dd >= j:
            return dict(code=code, date=dd, travaux=travaux, resultat=res, reste=(dd - j).days)
    return None
