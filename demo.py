"""Mission de démonstration, entièrement fictive, datée par rapport à aujourd'hui."""
import datetime as dt
import json

import db
import demo_cadre


def charger(aujourdhui=None):
    """Remplace la mission courante par la démonstration (sans inscrire l'historique)."""
    with db.sans_journal():
        _charger(aujourdhui)


def _charger(aujourdhui):
    auj = aujourdhui or dt.date.today()

    def j(n):
        return (auj + dt.timedelta(days=n)).isoformat()

    db.vider()
    db.modifier("mission", 1, {
        "nom": "Portail partenaires", "client": "Mutuelle Horizon (fictif)",
        "objectif_business": "Passer de 35 % à 70 % de demandes partenaires traitées en ligne.",
        "objectif_solution": "Portail responsive, temps de réponse inférieur à 2 s, exploitable par l'IT interne.",
        "objectif_projet": "Mise en service de la V1 à la date cible, dans le budget.",
        "porteur_business": "Responsable réseau partenaires", "porteur_solution": "Tech lead",
        "porteur_projet": "Pilote de mission",
        "hypotheses": "Équipe de 4 développeurs complète ; API contrats livrée par l'équipe SI Contrats avant la recette.",
        "date_cible": j(84), "duree_sprint_jours": 14, "seuils": json.dumps({}),
    })
    # Date de référence : l'engagement initial. Les tests utilisateurs ont déjà glissé de trois
    # semaines, à cause de l'API contrats.
    for lib, d, ref, v, s in [
        ("Dossier d'architecture validé", j(-40), j(-47), "V1", "atteint"),
        ("Lancement des tests utilisateurs", j(35), j(14), "V1", "à venir"),
        ("Mise en service V1", j(84), j(84), "V1", "à venir"),
        ("Ouverture du parcours mobile", j(170), j(170), "V2", "à venir"),
    ]:
        db.creer("jalon", {"libelle": lib, "date": d, "date_initiale": ref, "version": v, "statut": s})
    for ch, lib, av, st, t in [
        ("Produit", "Backlog V1", 90, "Affiné jusqu'au sprint 9", "vert"),
        ("Produit", "Maquettes", 100, "Validées", "vert"),
        ("Solution", "Dossier d'architecture", 100, "Validé en comité", "vert"),
        ("Solution", "Intégration API contrats", 20, "En attente de la livraison SI Contrats", "orange"),
        ("Projet", "Plan de recette", 40, "Stratégie rédigée, cas de test à écrire", "orange"),
        ("Change", "Kit de formation partenaires", 10, "Non démarré côté métier", "orange"),
    ]:
        db.creer("livrable", {"chantier": ch, "libelle": lib, "avancement": av,
                              "statut": st, "tendance": t})
    #        n°  prévu réalisé ajouté reste créées corrigées moral
    for i, (n, p, r, a, re, ac, ak, m) in enumerate([
        (1, 90, 84, 20, 456, 4, 4, 4),
        (2, 95, 91, 25, 390, 6, 5, 4),
        (3, 95, 88, 30, 332, 5, 6, 4),
        (4, 100, 74, 45, 303, 9, 5, 4),
        (5, 100, 68, 50, 285, 11, 6, 3),
        (6, 95, 61, 48, 272, 12, 7, 2),
    ]):
        db.creer("sprint", {"numero": n, "date_fin": j(-3 - 14 * (5 - i)), "capacite": 38,
                            "prevu": p, "realise": r, "ajoute": a, "reste": re,
                            "anomalies_creees": ac, "anomalies_corrigees": ak, "moral": m})
    for nat, titre, desc, pr, im, etat, evo, porteur, ech, lot, plan, maj in [
        ("risque", "Vélocité insuffisante pour tenir la V1",
         "Départ d'un développeur au sprint 4 non remplacé ; la vélocité est passée sous 70 points.",
         3, 3, "ouvert", "hausse", "", "", "V1", "", j(-20)),
        ("adherence", "Livraison de l'API contrats",
         "L'équipe SI Contrats doit livrer l'API de consultation avant le début de la recette.",
         2, 3, "ouvert", "stable", "Tech lead", j(21), "V1",
         "Point hebdomadaire avec SI Contrats.", j(-7)),
        ("risque", "Dérive de périmètre sur le parcours de souscription",
         "Demandes d'évolution du métier intégrées directement en sprint, sans arbitrage.",
         3, 2, "ouvert", "hausse", "PO", "", "V1", "", j(-10)),
        ("risque", "Validation conformité des écrans de collecte",
         "La conformité n'a pas encore revu les écrans de collecte de données personnelles.",
         2, 2, "en traitement", "stable", "Référent conformité", j(28), "V1",
         "Revue planifiée.", j(-5)),
        ("adherence", "Environnement de recette", "Mise à disposition par l'IT interne.",
         1, 2, "clos", "baisse", "IT manager", j(-15), "V1", "Livré.", j(-15)),
    ]:
        db.creer("risque", {"nature": nat, "titre": titre, "description": desc,
                            "probabilite": pr, "impact": im, "etat": etat, "evolution": evo,
                            "porteur": porteur, "echeance": ech, "lot": lot,
                            "plan_action": plan, "cree_le": j(-60), "maj_le": maj})
    for nat, titre, detail, statut, porteur, ech, inst in [
        ("decision", "Remplacer le développeur parti ou réduire le périmètre V1",
         "Sans renfort, la V1 ne tient pas la date cible.", "à prendre",
         "Sponsor IT", j(-4), "Comité sponsor"),
        ("decision", "Report du parcours mobile en V2", "Acté pour sécuriser la V1.",
         "prise", "Sponsor métier", j(-30), "Comité sponsor"),
        ("action", "Obtenir une date engagée pour l'API contrats", "", "à faire",
         "Tech lead", j(5), "Synchro hebdo"),
        ("action", "Planifier la revue conformité des écrans", "", "à faire",
         "PO", j(-2), "Synchro hebdo"),
    ]:
        db.creer("decision", {"nature": nat, "titre": titre, "detail": detail,
                              "statut": statut, "porteur": porteur, "echeance": ech,
                              "instance": inst, "cree_le": j(-14)})
    db.creer("compte_rendu", {
        "date": j(-1), "titre": "Synchro hebdo",
        "texte": (
            "Participants : pilote, PO, tech lead, responsable SI Contrats, référent conformité.\n\n"
            "1. API contrats. Le responsable SI Contrats annonce que la livraison de l'API "
            "de consultation glisse de deux semaines à cause d'une montée de version de leur "
            "socle. Il ne peut pas encore s'engager sur une date ferme et reviendra vers nous "
            "vendredi.\n\n"
            "2. Recette. Le tech lead signale que les jeux de données de recette ne sont pas "
            "anonymisés ; tant que ce n'est pas fait, la recette métier ne peut pas démarrer. "
            "Personne n'est identifié pour s'en charger.\n\n"
            "3. Conformité. La revue des écrans de collecte est fixée à jeudi prochain. "
            "Le PO envoie les maquettes au référent conformité d'ici mardi.\n\n"
            "4. Périmètre. Le métier demande l'ajout de la signature électronique en V1. "
            "Le PO estime la demande à environ 60 points. Il est convenu de présenter la "
            "demande au prochain comité sponsor plutôt que de l'intégrer au sprint.\n"
        ),
    })
    demo_cadre.charger(j)
    finances_demo(auj, j)
    hypotheses_demo(j)
    changements_demo(auj, j)


def changements_demo(auj, j):
    """Une demande acceptée (déjà incluse dans le budget vendu) et une demande chiffrée à présenter."""
    import changements
    jalons = {x["libelle"]: x["id"] for x in db.lister("jalon")}
    acceptee = changements.creer({"titre": "Export Excel des contrats pour les courtiers", "origine_type": "directe",
                                  "demandeur": "Marc L.", "decideur": "Marc L.", "lot": "V1",
                                  "description": "Les courtiers veulent extraire leur portefeuille pour leurs propres outils."}, auj)
    changements.chiffrer_avec_bloc(acceptee["id"], "generation-documents", "moyen")
    montant = changements.chiffrage(acceptee["id"])["montant"]
    db.modifier("changement", acceptee["id"], {"statut": "acceptée", "montant_applique": montant, "cree_le": j(-50),
                                               "decide_le": j(-35), "avenant_le": j(-35), "motif": "Validé au comité sponsor"})
    attente = next(a for a in db.lister("attente") if a["libelle"].startswith("Signature électronique"))
    cr = changements.creer({"origine_type": "attente", "origine_id": attente["id"], "decideur": "Marc L.", "lot": "V1",
                            "impact_delai_jours": 21, "jalons_ids": json.dumps([jalons["Mise en service V1"]])}, auj)
    changements.chiffrer_avec_bloc(cr["id"], "interface-tiers", "moyen", libelle="Intégration de la solution de signature")
    changements.chiffrer_avec_bloc(cr["id"], "ecran-standard", "moyen", 2, "Écrans de signature et de suivi")
    db.modifier("changement", cr["id"], {"cree_le": j(-4)})


def hypotheses_demo(j):
    db.modifier("mission", 1, {"hypotheses_reprises": 1})
    etats = {"API contrats": "bloquant", "Environnement de recette": "obtenu",
             "Validation conformité des écrans": "en attente", "API de souscription": "en attente",
             "Solution de signature électronique": "en attente"}
    for e in db.lister("lot_element", "axe = 'prerequis'"):
        if e["libelle"] in etats:
            db.modifier("lot_element", e["id"], {"statut": etats[e["libelle"]]})
    for lib, cat, st, porteur, ech, impact, lot, source in [
        ("Équipe de 4 développeurs complète jusqu'à la V1", "organisation", "invalidée", "Pilote de mission", j(-10),
         "Un départ non remplacé fait perdre environ 25 % de la capacité.", "V1", "proposition commerciale"),
        ("API contrats livrée par l'équipe SI Contrats avant la recette", "planning", "à vérifier", "Responsable SI Contrats",
         j(-2), "Sans l'API, pas de recette de bout en bout : la mise en service glisse.", "V1", "comité de lancement"),
        ("Le SSO du client est réutilisable pour l'espace courtier", "technique", "confirmée", "Tech lead", j(-30),
         "Sinon, prévoir un chantier d'authentification de 15 à 25 jours.", "V1", "atelier d'architecture"),
        ("Six types de demandes au maximum dans le dépôt en ligne", "périmètre", "à vérifier", "Product owner", j(5),
         "Au-delà, le chiffrage du dépôt et suivi des demandes est à reprendre.", "V1", "ateliers de cadrage"),
        ("Les données de recette peuvent être anonymisées par l'IT", "données", "à vérifier", "", "",
         "Sinon, la recette métier ne peut pas démarrer.", "V1", "synchro hebdo")]:
        db.creer("hypothese", {"libelle": lib, "categorie": cat, "statut": st, "porteur": porteur, "echeance": ech,
                               "impact": impact, "lot": lot, "source": source, "cree_le": j(-60),
                               "verifiee_le": ech if st != "à vérifier" else None})
    # L'hypothèse d'équipe complète, invalidée par un départ, a fait naître le risque de vélocité.
    velocite = next((r for r in db.lister("risque") if r["titre"].startswith("Vélocité")), None)
    invalidee = next(h for h in db.lister("hypothese") if h["statut"] == "invalidée")
    if velocite:
        db.modifier("hypothese", invalidee["id"], {"risque_id": velocite["id"]})


def finances_demo(auj, j):
    """Chiffrage, budget et attentes du client de la mission fictive."""
    db.modifier("mission", 1, {"budget_vendu": 420000, "chiffrage": json.dumps({"mode_retenu": "detaille"})})
    for i, (nom, metier, tjm, cout, raf) in enumerate([
        ("Pilote de mission", "Pilotage de projet", 950, 620, 30), ("Product owner", "Product owner", 850, 560, 35),
        ("Tech lead", "Tech lead", 900, 600, 40), ("Développeur", "Développeur", 700, 450, 120),
        ("UX / UI", "UX / UI", 750, 480, 12), ("QA", "QA", 650, 420, 45)]):
        db.creer("profil", {"nom": nom, "metier": metier, "tjm": tjm, "cout_journalier": cout, "raf_jours": raf, "rang": i})
    # Macro : fait en avant-vente, avec peu d'informations.
    for rang, (lot, lib, taille, conf) in enumerate([
        ("V1", "Espace courtier connecté", "L", "moyenne"), ("V1", "Consultation des contrats", "M", "moyenne"),
        ("V1", "Dépôt et suivi des demandes", "XL", "faible"), ("V1", "Intégration API contrats", "L", "faible"),
        ("V2", "Souscription en ligne", "XL", "faible"), ("V2", "Parcours mobile", "L", "moyenne"),
        ("V3", "Espace entreprise", "XL", "faible")]):
        db.creer("estimation", {"mode": "macro", "lot": lot, "libelle": lib, "taille": taille, "confiance": conf, "rang": rang})
    # Détaillé : refait après les ateliers de cadrage, par profil.
    for rang, (lot, lib, profil, b, p, h, hyp) in enumerate([
        ("V1", "Espace courtier connecté", "Développeur", 18, 24, 34, "SSO du client réutilisé"),
        ("V1", "Espace courtier connecté", "UX / UI", 6, 8, 12, ""),
        ("V1", "Consultation des contrats", "Développeur", 10, 14, 20, "API de consultation disponible"),
        ("V1", "Dépôt et suivi des demandes", "Développeur", 40, 55, 80, "Six types de demandes, pièces jointes"),
        ("V1", "Dépôt et suivi des demandes", "QA", 10, 14, 20, ""),
        ("V1", "Intégration API contrats", "Tech lead", 15, 20, 35, "Dépend de l'équipe SI Contrats"),
        ("V1", "Pilotage et cérémonies V1", "Pilote de mission", 25, 30, 35, ""),
        ("V1", "Backlog et recette métier V1", "Product owner", 25, 30, 38, "")]):
        db.creer("estimation", {"mode": "detaille", "lot": lot, "libelle": lib, "profil": profil, "jours_bas": b,
                                "jours_probable": p, "jours_haut": h, "hypothese": hyp, "rang": rang})
    mois = [f"{(auj.year * 12 + auj.month - 1 - k) // 12}-{(auj.month - 1 - k) % 12 + 1:02d}" for k in (3, 2, 1, 0)]
    for m, jours in zip(mois, [(10, 8, 8, 20, 6, 0), (10, 9, 9, 36, 5, 4), (10, 9, 10, 40, 3, 8), (6, 5, 6, 24, 1, 5)]):
        for (nom, *_), jr in zip([("Pilote de mission",), ("Product owner",), ("Tech lead",), ("Développeur",),
                                  ("UX / UI",), ("QA",)], jours):
            if jr:
                db.creer("consommation", {"mois": m, "profil": nom, "jours": jr})
    for d, lib, cat, montant, st in [
        (j(-60), "Licences outil de maquettage", "logiciel", 2400, "payée"),
        (j(-20), "Déplacements atelier Lyon", "déplacement", 1850, "payée"),
        (j(30), "Audit d'accessibilité", "sous-traitance", 9500, "prévue")]:
        db.creer("depense", {"date": d, "libelle": lib, "categorie": cat, "montant": montant, "statut": st})
    for lib, d, montant, st, jalon in [
        ("Acompte à la commande (20 %)", j(-90), 84000, "payée", ""),
        ("Validation du dossier d'architecture (20 %)", j(-38), 84000, "facturée", "Dossier d'architecture validé"),
        ("Lancement des tests utilisateurs (20 %)", j(-5), 84000, "à facturer", "Lancement des tests utilisateurs"),
        ("Mise en service V1 (40 %)", j(84), 168000, "à facturer", "Mise en service V1")]:
        db.creer("facture", {"libelle": lib, "date_prevue": d, "montant": montant, "statut": st, "jalon": jalon})
    for pp, lib, cat, prio, sat, pos, rep, action, ech, revue in [
        ("Marc L.", "Mise en service V1 avant la convention partenaires", "délai", 1, 3, "alignée",
         "Date cible tenue si l'API contrats arrive avant la recette", "Point d'étape au comité sponsor", j(84), j(-6)),
        ("Marc L.", "Signature électronique dès la V1", "périmètre", 2, 2, "à recadrer",
         "Estimée à ~60 points : arbitrage V1 / V2 à faire en comité", "", j(14), j(-6)),
        ("Camille R.", "Être informée chaque semaine des glissements", "communication", 1, 4, "alignée",
         "Météo hebdomadaire envoyée le vendredi", "", "", j(-3)),
        ("Équipe SI Contrats", "Pas de charge supplémentaire avant leur montée de version", "relation", 2, 2, "à recadrer",
         "Besoin d'une date ferme pour l'API", "Atelier de planification commun", j(10), j(-45)),
        ("Marc L.", "Rester dans l'enveloppe vendue", "coût", 1, 4, "alignée",
         "Atterrissage présenté chaque mois", "", "", j(-6))]:
        db.creer("attente", {"partie_prenante": pp, "libelle": lib, "categorie": cat, "priorite": prio,
                             "satisfaction": sat, "position": pos, "reponse": rep, "prochaine_action": action,
                             "echeance": ech, "revue_le": revue})
