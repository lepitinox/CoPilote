"""Mission de démonstration, entièrement fictive, datée par rapport à aujourd'hui."""
import datetime as dt
import json

import db


def charger(aujourdhui=None):
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
    for lib, d, v, s in [
        ("Dossier d'architecture validé", j(-40), "V1", "atteint"),
        ("Lancement des tests utilisateurs", j(35), "V1", "à venir"),
        ("Mise en service V1", j(84), "V1", "à venir"),
        ("Ouverture du parcours mobile", j(170), "V2", "à venir"),
    ]:
        db.creer("jalon", {"libelle": lib, "date": d, "version": v, "statut": s})
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
