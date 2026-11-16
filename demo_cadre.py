"""Cadre de la mission de démonstration : lots, story map, planning, organisation,
gouvernance et RACI. Tout est fictif."""
import json

import calculs
import db

ROLES = ["Sponsor", "PM", "PO", "BA", "Design", "Architecte", "Tech lead", "Dev", "QA"]


def charger(j):
    """`j(n)` renvoie la date ISO à n jours d'aujourd'hui."""
    db.modifier("mission", 1, {"raci_roles": json.dumps(ROLES)})

    for rang, (nom, titre, periode, date, statut) in enumerate([
        ("V1", "Portail courtiers", "Février 2027", j(84), "en cours"),
        ("V2", "Souscription et mobile", "T2 2027", j(170), "à venir"),
        ("V3", "Ouverture aux entreprises", "Fin 2027", j(330), "à venir"),
        ("Backlog", "Non planifié", "À arbitrer", "", "à arbitrer"),
    ]):
        db.creer("lot", {"nom": nom, "titre": titre, "periode": periode, "date": date,
                         "statut": statut, "rang": rang})

    for lot, axe, libelle, detail in [
        ("V1", "contenu", "Espace courtier connecté", ""),
        ("V1", "contenu", "Consultation des contrats", ""),
        ("V1", "contenu", "Dépôt et suivi des demandes en ligne", ""),
        ("V1", "prerequis", "API contrats", "Livrée par l'équipe SI Contrats avant la recette"),
        ("V1", "prerequis", "Environnement de recette", "Fourni par l'IT interne — livré"),
        ("V1", "prerequis", "Validation conformité des écrans", "Revue des écrans de collecte"),
        ("V1", "pour_qui", "Courtiers actifs", "Environ 1 200 cabinets"),
        ("V1", "pour_qui", "Gestionnaires back-office", ""),
        ("V1", "comment", "Portail web responsive", ""),
        ("V1", "quoi", "Contrats santé individuels", ""),
        ("V1", "fonctionnalite", "Connexion sécurisée", ""),
        ("V1", "fonctionnalite", "Tableau de bord", ""),
        ("V1", "fonctionnalite", "Dépôt de pièces", ""),
        ("V1", "fonctionnalite", "Suivi des demandes", ""),
        ("V2", "contenu", "Souscription en ligne", ""),
        ("V2", "contenu", "Parcours mobile", ""),
        ("V2", "prerequis", "API de souscription", "À livrer par SI Contrats"),
        ("V2", "prerequis", "Solution de signature électronique", "Choix de l'éditeur à arbitrer"),
        ("V2", "pour_qui", "Nouveaux courtiers", "Entrée en relation"),
        ("V2", "comment", "Application mobile", ""),
        ("V2", "quoi", "Contrats prévoyance", ""),
        ("V2", "fonctionnalite", "Devis et souscription", ""),
        ("V2", "fonctionnalite", "Signature électronique", ""),
        ("V2", "fonctionnalite", "Notifications", ""),
        ("V3", "contenu", "Espace entreprise", ""),
        ("V3", "contenu", "Gestion des adhésions collectives", ""),
        ("V3", "prerequis", "Référentiel entreprises", ""),
        ("V3", "prerequis", "API cotisations", ""),
        ("V3", "pour_qui", "Entreprises adhérentes", ""),
        ("V3", "comment", "API ouvertes aux partenaires", ""),
        ("V3", "quoi", "Contrats collectifs", ""),
        ("V3", "fonctionnalite", "Gestion des adhésions", ""),
        ("V3", "fonctionnalite", "Tableaux de bord avancés", ""),
        ("Backlog", "fonctionnalite", "Synthèse client par IA", "En discovery"),
        ("Backlog", "fonctionnalite", "Connexion biométrique", "En discovery"),
        ("Backlog", "quoi", "Épargne retraite", "À confirmer"),
    ]:
        db.creer("lot_element", {"lot": lot, "axe": axe, "libelle": libelle, "detail": detail})

    for rang, etape, stories in [
        (1, "Accès", [("Connexion", "V1", 0, 0), ("Récupération du mot de passe", "V1", 1, 0),
                      ("Première connexion guidée", "V1", 0, 0),
                      ("Connexion biométrique", "Backlog", 1, 1)]),
        (2, "Tableau de bord", [("Synthèse du portefeuille", "V1", 0, 0),
                                ("Indicateurs de pilotage", "V1", 1, 0),
                                ("Accès rapides personnalisés", "V2", 0, 0),
                                ("Synthèse client par IA", "Backlog", 0, 1)]),
        (3, "Consultation", [("Liste des contrats", "V1", 0, 0), ("Fiche contrat", "V1", 0, 0),
                             ("Téléchargement de documents", "V1", 1, 0),
                             ("Historique des opérations", "V2", 0, 0),
                             ("Contrats collectifs", "V3", 0, 0)]),
        (4, "Demandes", [("Dépôt d'une demande", "V1", 0, 0), ("Dépôt de pièces", "V1", 1, 0),
                         ("Suivi des demandes", "V1", 1, 0),
                         ("Lecture automatique des pièces", "V2", 0, 1)]),
        (5, "Souscription", [("Devis", "V2", 0, 0), ("Souscription en ligne", "V2", 1, 0),
                             ("Signature électronique", "V2", 0, 0),
                             ("Adhésions collectives", "V3", 0, 0)]),
        (6, "Administration", [("Gestion des comptes", "V1", 0, 0), ("Habilitations", "V1", 0, 0),
                               ("Notifications", "V2", 0, 0),
                               ("Délégation aux entreprises", "V3", 0, 0)]),
    ]:
        for libelle, lot, irritant, innovation in stories:
            db.creer("story", {"etape": etape, "rang_etape": rang, "libelle": libelle,
                               "lot": lot, "irritant": irritant, "innovation": innovation})

    for piste, libelle, debut, fin in [
        ("Conception", "Conception fonctionnelle et technique", j(-150), j(-40)),
        ("Réalisation", "Front", j(-95), j(30)),
        ("Réalisation", "Middle et back", j(-95), j(40)),
        ("Tests et corrections", "Recette utilisateur", j(35), j(65)),
        ("Tests et corrections", "Tests de performance", j(45), j(60)),
        ("Déploiement", "Pilote courtiers", j(70), j(84)),
        ("Déploiement", "Déploiement national", j(84), j(115)),
        ("Change", "Formation des courtiers pilotes", j(55), j(70)),
        ("Change", "Formation nationale", j(75), j(105)),
    ]:
        db.creer("activite", {"piste": piste, "libelle": libelle, "debut": debut, "fin": fin})

    for nom, role, cercle, entite, adherence in [
        ("Camille R.", "Pilote de mission (PM)", "équipe projet", "Pilotage", ""),
        ("Idriss B.", "Product owner", "équipe projet", "Pilotage", ""),
        ("Léa T.", "Business analyst", "équipe projet", "Pilotage", ""),
        ("Noé V.", "Tech lead", "équipe projet", "Technique", ""),
        ("Sarah K.", "Architecte solutions", "équipe projet", "Technique", ""),
        ("Équipe de 3", "Développeurs", "équipe projet", "Technique", ""),
        ("Inès D.", "UX / UI", "équipe projet", "Design", ""),
        ("Hugo P.", "QA", "équipe projet", "Technique", ""),
        ("Marc L.", "Sponsor métier", "métier", "Direction réseau partenaires", ""),
        ("Julie F.", "Responsable réseau partenaires", "métier", "Direction réseau partenaires",
         "Porte la dimension business ; mobilise les courtiers pilotes"),
        ("Pierre G.", "Référent conformité", "métier", "Conformité",
         "Revue des écrans de collecte avant la recette"),
        ("Anne S.", "Juriste", "métier", "Juridique", "Conditions d'utilisation du portail"),
        ("Tom E.", "Offre et marketing", "métier", "Marketing", ""),
        ("Nadia O.", "Sponsor IT", "IT", "Direction des systèmes d'information", ""),
        ("Équipe SI Contrats", "Responsable SI Contrats", "IT", "SI Contrats",
         "Livre l'API contrats, prérequis de la V1"),
        ("Pôle architecture", "Architecte d'entreprise", "IT", "Architecture",
         "Valide le dossier d'architecture"),
        ("Pôle intégration", "Responsable intégration", "IT", "Intégration",
         "Fournit les environnements"),
        ("Homologation", "Responsable homologation", "IT", "Homologation",
         "Organise la recette et l'automatisation des tests"),
        ("Sécurité", "RSSI", "IT", "Sécurité", "Étude de sécurité du portail"),
        ("Éditeur de signature", "Fournisseur", "externe", "Éditeur",
         "Solution de signature électronique, prérequis de la V2"),
        ("Courtiers pilotes", "Utilisateurs", "externe", "Réseau", "Tests utilisateurs et pilote"),
    ]:
        db.creer("acteur", {"nom": nom, "role": role, "cercle": cercle, "entite": entite,
                            "adherence": adherence})

    for rang, (nom, chantier, objectifs, participants, frequence, duree) in enumerate([
        ("Mêlée quotidienne", "Pilotage opérationnel du delivery",
         "Échanger sur l'avancement des tâches\nIdentifier les points bloquants",
         "Équipe projet (ouvert à tous)", "Quotidienne", "15 min"),
        ("Planification de sprint", "Pilotage des sprints",
         "Définir les fonctionnalités et les tâches du sprint\nEstimer l'effort",
         "Équipe projet, expertises transverses si besoin", "À chaque début de sprint", "1 h 30"),
        ("Affinage du backlog", "Pilotage des sprints",
         "Revoir et affiner les items du backlog\nVérifier le respect de la DoR",
         "Équipe projet", "À la demande pendant le sprint", "2 × 1 h"),
        ("Démonstration", "Pilotage des sprints",
         "Montrer les développements du sprint\nPrésenter les indicateurs et le planning\n"
         "Recueillir le feedback des parties prenantes",
         "Démo publique : équipe projet et parties prenantes", "À chaque fin de sprint", "1 h"),
        ("Rétrospective", "Pilotage des sprints",
         "Faire le point sur le fonctionnement de l'équipe\n"
         "Identifier des axes d'amélioration et des plans d'action",
         "Équipe projet", "Tous les deux sprints", "1 h 30"),
        ("Synchro hebdo", "Suivi du projet",
         "Partager les avancées et les points de blocage\n"
         "Reconfirmer le planning et les impacts des dépendances\n"
         "Identifier ce qui remonte au comité sponsor",
         "Équipe projet, SI Contrats, conformité, homologation", "Hebdomadaire", "30 min à 1 h"),
        ("Comité sponsor", "Gouvernance",
         "Piloter l'activité et le delivery\nValider les orientations métier et techniques\n"
         "Arbitrer les décisions structurantes : périmètre, priorités, architecture, staffing",
         "Quorum resserré : sponsors métier et IT, pilote, PO", "Mensuelle", "1 h"),
    ]):
        db.creer("instance", {"nom": nom, "chantier": chantier, "objectifs": objectifs,
                              "participants": participants, "frequence": frequence,
                              "duree": duree, "rang": rang})

    #                                  Spo  PM   PO   BA   Des  Arc  TL   Dev  QA
    for rang, (domaine, activite, v) in enumerate([
        ("Métier", "Expression de besoin",       "A C R R C C I I I"),
        ("Métier", "Feuille de route produit",   "A C R C I C I I I"),
        ("Métier", "Validation des maquettes",   "C I A R R I I I I"),
        ("Pilotage", "Planning",                 "I A R C I C C I I"),
        ("Pilotage", "Gestion du backlog",       "I C A R I C C I I"),
        ("Pilotage", "Animation des cérémonies", "I A R C I I I C I"),
        ("Pilotage", "Pilotage du budget",       "A R I - - - - - -"),
        ("Pilotage", "Suivi des risques",        "I A R C I C R I I"),
        ("Mise en œuvre", "Étude de faisabilité technique", "I I C I I A R R I"),
        ("Mise en œuvre", "Conception des maquettes",       "I I A C R I I I I"),
        ("Mise en œuvre", "Développement",                  "I I C I I C A R I"),
        ("Mise en œuvre", "Validation technique",           "- I I - - C A R R"),
        ("Mise en œuvre", "Stratégie de recette",           "I C A R - - C I R"),
        ("Mise en œuvre", "Recette métier",                 "I I A R - - I C R"),
        ("Transverse", "Continuous discovery",              "I C A R R C I I I"),
    ]):
        valeurs = {r: x for r, x in zip(ROLES, v.split()) if x != "-"}
        db.creer("raci", {"domaine": domaine, "activite": activite, "rang": rang,
                          "valeurs": json.dumps(valeurs, ensure_ascii=False)})

    # Session précédente fictive, pour que l'évolution des risques ait un point de comparaison.
    risques = db.lister("risque")
    photo = calculs.instantane(risques)
    par_titre = {r["titre"]: str(r["id"]) for r in risques}

    def avant(debut_titre, criticite=None, etat=None, absent=False):
        cle = next(v for t, v in par_titre.items() if t.startswith(debut_titre))
        if absent:
            del photo[cle]
            return
        if criticite is not None:
            photo[cle]["criticite"] = criticite
        if etat:
            photo[cle]["etat"] = etat

    avant("Vélocité insuffisante", criticite=6)
    avant("Dérive de périmètre", absent=True)
    avant("Validation conformité", criticite=6)
    avant("Environnement de recette", etat="ouvert")
    db.creer("meteo", {
        "semaine": "Semaine précédente (démonstration)", "cree_le": j(-7),
        "contenu": "# Météo de la semaine précédente\n\n**Tendance globale : ORANGE — à risque**\n\n"
                   "Entrée fictive de démonstration : elle sert de point de comparaison pour "
                   "l'évolution des risques.\n",
        "tendance_calculee": "orange", "tendance": "orange", "motif_derogation": "",
        "alertes": "[]", "remarques": "[]", "statut": "diffusée", "source": "gabarit",
        "risques_instantane": json.dumps(photo),
    })
