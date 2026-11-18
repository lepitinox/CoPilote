"""Modèles de mission fournis : projet agile, projet data / IA, mission de conseil.

Les personnes sont des rôles (à renommer), les dates sont en jours depuis le lancement, les
charges viennent du catalogue de blocs. Ce sont des points de départ à adapter, pas des normes.
"""
import json


def _acteurs(liste):
    """(nom, rôle, cercle, entité, métier, adhérence) -> acteurs numérotés à partir de 1."""
    return [{"id": i, "nom": n, "role": r, "cercle": c, "entite": e, "metier": m, "adherence": a, "email": ""}
            for i, (n, r, c, e, m, a) in enumerate(liste, 1)]


def _instances(liste):
    """(nom, chantier, objectifs, récurrence, durée en minutes, participants) -> instances."""
    return [{"id": i, "nom": n, "chantier": ch, "objectifs": o, "recurrence": rec, "duree_min": d,
             "participants_ids": json.dumps(p), "rang": i} for i, (n, ch, o, rec, d, p) in enumerate(liste, 1)]


def _profils(liste):
    return [{"nom": n, "metier": m, "tjm": t, "cout_journalier": round(t * 0.65), "rang": i} for i, (n, m, t) in enumerate(liste)]


def _raci(liste):
    """(domaine, activité, {colonne: lettre}) -> lignes du RACI."""
    return [{"domaine": d, "activite": a, "valeurs": json.dumps(v, ensure_ascii=False), "rang": i} for i, (d, a, v) in enumerate(liste)]


def _hyp(liste):
    return [{"libelle": l, "categorie": c, "impact": i, "lot": lot, "source": "modèle"} for l, c, i, lot in liste]


def _risques(liste):
    return [{"nature": n, "titre": t, "description": d, "probabilite": p, "impact": i, "lot": lot, "plan_action": pa}
            for n, t, d, p, i, lot, pa in liste]


def _blocs(liste):
    return [{"bloc": b, "niveau": n, "lot": l, "quantite": q} for b, n, l, q in liste]


SP, PP, PO, BA, AR, TL, DEV, UX, QA, OPS, SEC, DATA = (
    "metier:Sponsor", "metier:Pilotage de projet", "metier:Product owner", "metier:Business analyst",
    "metier:Architecte", "metier:Tech lead", "metier:Développeur", "metier:UX / UI", "metier:QA",
    "metier:DevOps", "metier:Sécurité", "metier:Data")

AGILE = {
    "format": "copilote-modele", "version": 1, "nom": "Projet agile de développement",
    "description": "Une application construite en sprints de deux semaines : MVP puis seconde version, avec "
                   "équipe produit, rituels agiles et comité mensuel.",
    "cadre": {
        "acteur": _acteurs([
            ("Sponsor", "Sponsor métier", "métier", "Direction métier", "Sponsor", ""),
            ("Product owner", "Product owner", "équipe projet", "Équipe produit", "Product owner", ""),
            ("Pilote de mission", "Pilote", "équipe projet", "Équipe produit", "Pilotage de projet", ""),
            ("Tech lead", "Tech lead", "équipe projet", "Équipe de réalisation", "Tech lead", ""),
            ("Équipe de développement", "Développeurs", "équipe projet", "Équipe de réalisation", "Développeur", ""),
            ("Designer", "UX / UI", "équipe projet", "Équipe produit", "UX / UI", ""),
            ("Testeur", "QA", "équipe projet", "Équipe de réalisation", "QA", ""),
            ("Référent sécurité", "Sécurité", "IT", "DSI", "Sécurité", "Valide l'architecture et l'homologation."),
            ("Exploitation", "Exploitation", "IT", "DSI", "DevOps", "Fournit les environnements et met en production."),
        ]),
        "instance": _instances([
            ("Mêlée quotidienne", "Équipe", "Avancement de la veille\nPlan du jour\nPoints bloquants", "quotidienne", 15, [2, 3, 4, 5, 6, 7]),
            ("Planification de sprint", "Équipe", "Sélectionner les stories du sprint\nEstimer et s'engager", "debut_sprint", 90, [2, 3, 4, 5, 6, 7]),
            ("Affinage du backlog", "Équipe", "Préparer les stories des prochains sprints\nVérifier la définition de prêt", "hebdomadaire", 60, [2, 4, 6]),
            ("Démonstration", "Produit", "Montrer l'incrément\nRecueillir les retours", "fin_sprint", 60, [1, 2, 3, 4, 5, 6, 7]),
            ("Rétrospective", "Équipe", "Ce qui a marché\nCe qui est à améliorer\nActions", "deux_sprints", 60, [2, 3, 4, 5, 6, 7]),
            ("Comité de pilotage", "Pilotage", "Trajectoire, budget, risques\nDécisions à prendre", "mensuelle", 60, [1, 2, 3]),
        ]),
        "profil": _profils([("Pilote de mission", "Pilotage de projet", 950), ("Product owner", "Product owner", 850),
                            ("Tech lead", "Tech lead", 900), ("Développeur", "Développeur", 700),
                            ("UX / UI", "UX / UI", 750), ("QA", "QA", 650)]),
        "raci": _raci([
            ("Produit", "Priorisation du backlog", {PO: "R", SP: "A", PP: "I", TL: "C"}),
            ("Produit", "Maquettes et parcours", {UX: "R", PO: "A", DEV: "C"}),
            ("Réalisation", "Développement des stories", {DEV: "R", TL: "A", PO: "C"}),
            ("Réalisation", "Choix d'architecture", {TL: "R", SEC: "C", PP: "I", PO: "A"}),
            ("Qualité", "Recette des stories", {QA: "R", PO: "A", DEV: "C"}),
            ("Mise en production", "Mise en production", {OPS: "R", TL: "C", PO: "A", PP: "I"}),
            ("Pilotage", "Suivi budgétaire et reporting", {PP: "R", SP: "A", PO: "C"}),
        ]),
        "raci_roles": [SP, PP, PO, TL, DEV, UX, QA, SEC, OPS], "chiffrage": {}, "duree_sprint_jours": 14,
    },
    "squelette": {
        "lot": [{"nom": "V1", "titre": "Produit minimum viable", "rang": 0, "decalage": 120},
                {"nom": "V2", "titre": "Seconde version", "rang": 1, "decalage": 200}],
        "lot_element": [
            {"lot": "V1", "axe": "contenu", "libelle": "Parcours principal de bout en bout", "detail": "Le MVP utilisable par les premiers utilisateurs"},
            {"lot": "V1", "axe": "prerequis", "libelle": "Environnements de développement et de recette", "detail": "Fournis par l'exploitation"},
            {"lot": "V1", "axe": "prerequis", "libelle": "Accès aux systèmes à intégrer", "detail": "API ou données des systèmes existants"},
            {"lot": "V2", "axe": "contenu", "libelle": "Parcours complémentaires", "detail": "Selon les retours du MVP"},
        ],
        "jalon": [{"libelle": "Cadrage validé", "version": "V1", "decalage": 21}, {"libelle": "Fin du sprint 0", "version": "V1", "decalage": 35},
                  {"libelle": "Démonstration du MVP", "version": "V1", "decalage": 100}, {"libelle": "Mise en service V1", "version": "V1", "decalage": 120},
                  {"libelle": "Mise en service V2", "version": "V2", "decalage": 200}],
        "activite": [{"piste": "Cadrage", "libelle": "Cadrage et sprint 0", "debut": 0, "fin": 35},
                     {"piste": "Réalisation", "libelle": "Sprints V1", "debut": 35, "fin": 105},
                     {"piste": "Recette", "libelle": "Recette et mise en service V1", "debut": 100, "fin": 120},
                     {"piste": "Réalisation", "libelle": "Sprints V2", "debut": 125, "fin": 195}],
        "hypothese": _hyp([
            ("Équipe de réalisation complète dès le sprint 1", "organisation", "Moins de capacité : le MVP glisse ou se réduit.", "V1"),
            ("Product owner disponible au moins à mi-temps", "organisation", "Backlog mal préparé, arbitrages tardifs.", "V1"),
            ("Environnements fournis avant la fin du sprint 0", "technique", "Les premiers sprints ne livrent rien de déployable.", "V1"),
            ("Socle technique et authentification du client réutilisables", "technique", "Chantier socle à ajouter au chiffrage.", "V1"),
        ]),
        "risque": _risques([
            ("risque", "Disponibilité du product owner", "Arbitrages tardifs, stories mal préparées.", 2, 2, "V1", ""),
            ("risque", "Dérive de périmètre", "Ajouts au backlog supérieurs à la marge, sprint après sprint.", 2, 3, "V1", "Passer les ajouts en demandes de changement."),
            ("adherence", "Dépendance aux systèmes à intégrer", "Les API ou données des systèmes existants arrivent tard.", 2, 3, "V1", ""),
        ]),
        "story": [{"etape": e, "rang_etape": i, "libelle": l, "lot": "V1", "irritant": 0, "innovation": 0}
                  for i, (e, l) in enumerate([("Découvrir", "Présentation du service"), ("S'inscrire", "Création de compte"),
                                              ("Utiliser", "Parcours principal"), ("Suivre", "Suivi et notifications")])],
        "blocs": _blocs([("cadrage-besoin", "moyen", "V1", 1), ("architecture", "moyen", "V1", 1), ("maquettes-ux", "moyen", "V1", 3),
                         ("ecran-standard", "moyen", "V1", 10), ("api-exposee", "moyen", "V1", 3), ("authentification", "rapide", "V1", 1),
                         ("ci-cd", "moyen", "V1", 1), ("strategie-recette", "moyen", "V1", 1), ("recette", "moyen", "V1", 1),
                         ("mise-en-production", "moyen", "V1", 1), ("pilotage-mois", "moyen", "V1", 4),
                         ("ecran-standard", "moyen", "V2", 6), ("recette", "moyen", "V2", 1), ("pilotage-mois", "moyen", "V2", 3)]),
    },
}

DATA_IA = {
    "format": "copilote-modele", "version": 1, "nom": "Projet data / IA",
    "description": "Un POC sur les données du client, une décision d'industrialiser, puis la mise en production : "
                   "accès aux données, modélisation, évaluation, intégration au logiciel cible.",
    "cadre": {
        "acteur": _acteurs([
            ("Sponsor métier", "Sponsor", "métier", "Direction métier", "Sponsor", ""),
            ("Porteur projet client", "Porteur projet", "métier", "Direction métier", "Métier", ""),
            ("Pilote de mission", "Pilote", "équipe projet", "Équipe projet", "Pilotage de projet", ""),
            ("Data scientist", "Data scientist", "équipe projet", "Équipe projet", "Data", ""),
            ("Data engineer", "Data engineer", "équipe projet", "Équipe projet", "Data", ""),
            ("Architecte", "Architecte", "équipe projet", "Équipe projet", "Architecte", ""),
            ("Propriétaires des données", "Fournisseurs des extractions", "IT", "DSI", "IT", "Fournissent les accès et les extractions."),
            ("Référent sécurité et RGPD", "Sécurité", "IT", "DSI", "Sécurité", "Valide l'usage des données et des modèles."),
            ("Éditeur du logiciel cible", "Éditeur", "externe", "Éditeur", "Prestataire", "Fournit l'API d'intégration."),
        ]),
        "instance": _instances([
            ("Point d'avancement", "Projet", "Avancement de la semaine\nAccès et extractions\nPoints bloquants", "hebdomadaire", 45, [2, 3, 4, 5]),
            ("Revue des résultats du modèle", "Data", "Performances mesurées\nCas d'erreur\nProchaines expérimentations", "deux_sprints", 60, [2, 3, 4, 5]),
            ("Comité de pilotage", "Pilotage", "Résultats, budget, risques\nDécision d'industrialiser", "mensuelle", 60, [1, 2, 3]),
            ("Atelier données", "Data", "Comprendre les sources\nValider les règles de qualité", "ponctuelle", 90, [2, 4, 5, 7]),
        ]),
        "profil": _profils([("Pilote de mission", "Pilotage de projet", 1000), ("Data scientist", "Data", 850),
                            ("Data engineer", "Data", 800), ("Architecte", "Architecte", 1000)]),
        "raci": _raci([
            ("Données", "Accès et extractions", {"metier:IT": "R", PP: "A", DATA: "C"}),
            ("Données", "Qualité des données", {DATA: "R", "metier:Métier": "C", PP: "A"}),
            ("Modèle", "Modélisation et évaluation", {DATA: "R", PP: "A", "metier:Métier": "C"}),
            ("Modèle", "Validation de l'usage (sécurité, RGPD)", {SEC: "A", DATA: "C", PP: "R"}),
            ("Industrialisation", "Décision d'industrialiser", {SP: "A", PP: "R", "metier:Métier": "C"}),
            ("Industrialisation", "Intégration au logiciel cible", {AR: "R", "metier:Prestataire": "C", PP: "A"}),
        ]),
        "raci_roles": [SP, "metier:Métier", PP, DATA, AR, "metier:IT", SEC, "metier:Prestataire"], "chiffrage": {},
        "duree_sprint_jours": 14,
    },
    "squelette": {
        "lot": [{"nom": "POC", "titre": "Preuve de concept sur données réelles", "rang": 0, "decalage": 90},
                {"nom": "Indus", "titre": "Industrialisation", "rang": 1, "decalage": 180}],
        "lot_element": [
            {"lot": "POC", "axe": "contenu", "libelle": "Modèle évalué sur données réelles", "detail": "Performances mesurées sur l'historique"},
            {"lot": "POC", "axe": "prerequis", "libelle": "Accès aux données historiques", "detail": "Extractions complètes des sources"},
            {"lot": "POC", "axe": "prerequis", "libelle": "Environnement de calcul", "detail": "Plateforme du client ou hébergement validé"},
            {"lot": "Indus", "axe": "prerequis", "libelle": "Décision d'industrialiser", "detail": "Comité de pilotage, sur les résultats du POC"},
            {"lot": "Indus", "axe": "prerequis", "libelle": "API du logiciel cible", "detail": "Fournie par l'éditeur"},
            {"lot": "Indus", "axe": "contenu", "libelle": "Pipeline en production et supervision", "detail": ""},
        ],
        "jalon": [{"libelle": "Accès aux données obtenus", "version": "POC", "decalage": 21}, {"libelle": "Premiers résultats", "version": "POC", "decalage": 56},
                  {"libelle": "Fin du POC et décision d'industrialiser", "version": "POC", "decalage": 90},
                  {"libelle": "Mise en production", "version": "Indus", "decalage": 180}],
        "activite": [{"piste": "Données", "libelle": "Collecte et qualité des données", "debut": 0, "fin": 35},
                     {"piste": "Modèle", "libelle": "Modélisation", "debut": 21, "fin": 80},
                     {"piste": "Modèle", "libelle": "Évaluation et restitution", "debut": 70, "fin": 90},
                     {"piste": "Industrialisation", "libelle": "Industrialisation et intégration", "debut": 100, "fin": 175}],
        "hypothese": _hyp([
            ("Accès aux données obtenus sous trois semaines", "données", "Le POC démarre en retard ou sur un échantillon.", "POC"),
            ("Historique suffisant et exploitable (au moins un an)", "données", "Performances non mesurables ou peu fiables.", "POC"),
            ("Environnement de calcul disponible au lancement", "technique", "Retard de démarrage, coût d'hébergement à ajouter.", "POC"),
            ("Usage du modèle et des données validé par la sécurité", "organisation", "POC bloqué ou limité à des données anonymisées.", "POC"),
            ("API d'intégration fournie par l'éditeur", "technique", "Industrialisation impossible sans contournement.", "Indus"),
        ]),
        "risque": _risques([
            ("adherence", "Extractions de données incomplètes", "Champs manquants ou historique partiel : performances non représentatives.", 2, 3, "POC", ""),
            ("risque", "Dérive du modèle en production", "La performance baisse quand les données évoluent.", 2, 3, "Indus", "Prévoir la supervision et le réentraînement."),
            ("adherence", "Dépendance à l'éditeur du logiciel cible", "Planning de l'API hors de notre maîtrise.", 2, 3, "Indus", ""),
            ("risque", "Refus d'usage par la sécurité ou le RGPD", "Données sensibles ou hébergement du modèle non validés.", 1, 3, "POC", ""),
        ]),
        "story": [],
        "blocs": _blocs([("cadrage-besoin", "moyen", "POC", 1), ("recuperation-data", "long", "POC", 2), ("qualite-donnees", "moyen", "POC", 2),
                         ("modele-ml", "moyen", "POC", 1), ("evaluation-ia", "moyen", "POC", 1), ("risques-securite-rgpd", "moyen", "POC", 1),
                         ("pilotage-mois", "moyen", "POC", 3), ("pipeline-donnees", "moyen", "Indus", 2), ("mlops", "moyen", "Indus", 1),
                         ("interface-tiers", "long", "Indus", 1), ("mise-en-production", "moyen", "Indus", 1), ("pilotage-mois", "moyen", "Indus", 3)]),
    },
}

CONSEIL = {
    "format": "copilote-modele", "version": 1, "nom": "Mission de conseil ou de cadrage",
    "description": "Une mission courte : diagnostic par entretiens, ateliers de recommandations, feuille de route "
                   "restituée en comité.",
    "cadre": {
        "acteur": _acteurs([
            ("Sponsor", "Sponsor", "métier", "Direction", "Sponsor", ""),
            ("Directeur de mission", "Directeur de mission", "équipe projet", "Cabinet", "Pilotage de projet", ""),
            ("Consultant", "Consultant", "équipe projet", "Cabinet", "Business analyst", ""),
            ("Interlocuteurs métier", "Personnes interviewées", "métier", "Directions métier", "Métier", "Disponibilité pour les entretiens et ateliers."),
            ("DSI", "DSI", "IT", "DSI", "IT", "Fournit la cartographie et la documentation."),
        ]),
        "instance": _instances([
            ("Point hebdomadaire", "Mission", "Avancement\nEntretiens réalisés et à planifier\nPremiers constats", "hebdomadaire", 45, [1, 2, 3]),
            ("Comité de pilotage", "Pilotage", "Restitution des constats\nValidation des orientations", "mensuelle", 60, [1, 2, 3]),
            ("Atelier de recommandations", "Mission", "Partager les constats\nConstruire les recommandations", "ponctuelle", 120, [2, 3, 4]),
        ]),
        "profil": _profils([("Directeur de mission", "Pilotage de projet", 1400), ("Consultant senior", "Business analyst", 1000),
                            ("Consultant", "Business analyst", 750)]),
        "raci": _raci([
            ("Diagnostic", "Entretiens", {BA: "R", PP: "A", "metier:Métier": "C"}),
            ("Recommandations", "Ateliers", {BA: "R", PP: "A", "metier:Métier": "C", SP: "I"}),
            ("Restitution", "Feuille de route", {PP: "R", SP: "A", BA: "C", "metier:IT": "C"}),
        ]),
        "raci_roles": [SP, PP, BA, "metier:Métier", "metier:IT"], "chiffrage": {}, "duree_sprint_jours": 14,
    },
    "squelette": {
        "lot": [{"nom": "Diagnostic", "titre": "Diagnostic de l'existant", "rang": 0, "decalage": 30},
                {"nom": "Reco", "titre": "Recommandations", "rang": 1, "decalage": 55},
                {"nom": "Feuille", "titre": "Feuille de route", "rang": 2, "decalage": 75}],
        "lot_element": [
            {"lot": "Diagnostic", "axe": "prerequis", "libelle": "Liste et agenda des interlocuteurs", "detail": "Fournis par le sponsor la première semaine"},
            {"lot": "Diagnostic", "axe": "prerequis", "libelle": "Documentation existante", "detail": "Organisation, processus, cartographie"},
            {"lot": "Feuille", "axe": "contenu", "libelle": "Feuille de route chiffrée et priorisée", "detail": ""},
        ],
        "jalon": [{"libelle": "Lancement", "version": "Diagnostic", "decalage": 0}, {"libelle": "Restitution du diagnostic", "version": "Diagnostic", "decalage": 30},
                  {"libelle": "Comité des recommandations", "version": "Reco", "decalage": 55},
                  {"libelle": "Livraison de la feuille de route", "version": "Feuille", "decalage": 75}],
        "activite": [{"piste": "Diagnostic", "libelle": "Entretiens", "debut": 0, "fin": 25}, {"piste": "Diagnostic", "libelle": "Analyse", "debut": 15, "fin": 30},
                     {"piste": "Recommandations", "libelle": "Ateliers", "debut": 35, "fin": 55},
                     {"piste": "Feuille de route", "libelle": "Construction de la feuille de route", "debut": 55, "fin": 75}],
        "hypothese": _hyp([
            ("Interlocuteurs disponibles aux dates d'entretien", "organisation", "Le diagnostic glisse.", "Diagnostic"),
            ("Documentation fournie la première semaine", "données", "Analyse fondée sur les seuls entretiens.", "Diagnostic"),
            ("Périmètre limité aux directions nommées au lancement", "périmètre", "Charge d'entretiens à revoir.", "Diagnostic"),
        ]),
        "risque": _risques([
            ("risque", "Disponibilité des interlocuteurs", "Entretiens reportés, diagnostic incomplet.", 2, 2, "Diagnostic", ""),
            ("risque", "Attentes divergentes entre sponsors", "Recommandations contestées en comité.", 2, 3, "Reco", "Faire valider les orientations en cours de route."),
        ]),
        "story": [],
        "blocs": _blocs([("cadrage-besoin", "moyen", "Diagnostic", 3), ("conduite-changement", "rapide", "Reco", 1),
                         ("documentation-transfert", "rapide", "Feuille", 1), ("pilotage-mois", "rapide", "Feuille", 3)]),
    },
}

MODELES_FOURNIS = {"projet-agile": AGILE, "projet-data-ia": DATA_IA, "mission-conseil": CONSEIL}
