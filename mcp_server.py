"""Serveur MCP du co-pilote : un LLM lit et met à jour les missions avec les mêmes règles que l'interface.

Lancement : python mcp_server.py           (stdio : Claude Code, Claude Desktop…)
            python mcp_server.py --http    (Streamable HTTP sur http://127.0.0.1:8766/mcp)

Les données sont celles du serveur web (dossier des missions). Chaque écriture faite par
l'assistant est inscrite à l'historique avec l'origine « assistant (MCP) » et peut être
annulée depuis l'interface ou avec l'outil annuler_modification.
"""
import argparse
import contextlib
import datetime as dt
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

import agenda  # noqa: E402
import pilote  # noqa: E402
import catalogue  # noqa: E402
import changements  # noqa: E402
import modeles_mission  # noqa: E402
import db  # noqa: E402
import donnees  # noqa: E402
import finances  # noqa: E402

ORIGINE = "assistant (MCP)"
LISIBLES = donnees.EDITABLES | {"proposition", "meteo"}

DESCRIPTIONS = {
    "mission": "Fiche de la mission (une seule ligne, id 1) : objectifs et porteurs business / solution / projet, "
               "hypothèses, date cible, durée des sprints, budget vendu, paramètres du chiffrage, colonnes du RACI.",
    "lot": "Lot de livraison (V1, V2…) : titre, période affichée, date de livraison, statut (à venir | en cours | livré | à arbitrer).",
    "lot_element": "Contenu d'un lot. axe : contenu | prerequis | pour_qui | comment | quoi | fonctionnalite ; lot = nom du lot.",
    "story": "Story de la story map : étape du parcours (colonne), rang de l'étape, lot, irritant (0/1), innovation (0/1).",
    "activite": "Barre du macro-planning : piste (ligne), libellé, début et fin (dates AAAA-MM-JJ).",
    "metier": "Catalogue des métiers (UX / UI, Développeur…), utilisé par l'organisation et le RACI.",
    "acteur": "Personne ou équipe de l'organisation : rôle, métier, cercle (équipe projet | métier | IT | externe), entité, adhérence, e-mail.",
    "instance": "Réunion de gouvernance : objectifs, participants_ids (liste d'id d'acteurs), récurrence "
                "(quotidienne | hebdomadaire | debut_sprint | fin_sprint | deux_sprints | mensuelle | ponctuelle), "
                "première séance, heure (HH:MM), durée en minutes.",
    "raci": "Activité du RACI. valeurs : objet {colonne: lettre}, colonne = \"metier:<nom>\" ou \"acteur:<id>\", "
            "lettre R | A | C | I. Une seule A et au moins un R par ligne.",
    "jalon": "Jalon : libellé, date, version (lot), statut (à venir | atteint | en retard).",
    "livrable": "Livrable de pilotage : chantier, avancement (0 à 100), statut en une ligne, tendance (vert | orange | rouge).",
    "sprint": "Sprint : numéro, date de fin, capacité, points prévus / réalisés / ajoutés, reste à faire, anomalies, moral (1 à 5).",
    "risque": "Risque ou adhérence (nature : risque | adherence) : probabilité et impact (1 à 3), état (ouvert | en traitement | clos), "
              "porteur, échéance, lot impacté, plan d'action.",
    "decision": "Décision ou action (nature : decision | action) : statut (à prendre | prise | à faire | faite), porteur, échéance, instance.",
    "compte_rendu": "Compte rendu de réunion : date, titre, texte.",
    "proposition": "Proposition extraite d'un compte rendu, en attente de validation (lecture seule ici).",
    "meteo": "Météo hebdomadaire générée (lecture seule ici).",
    "estimation": "Élément chiffré. mode : macro (taille XS | S | M | L | XL et confiance forte | moyenne | faible) "
                  "ou detaille (profil et jours_bas / jours_probable / jours_haut). lot, libellé, hypothèses.",
    "profil": "Profil vendu : TJM de vente, coût journalier, reste à faire en jours.",
    "consommation": "Temps consommé : mois (AAAA-MM), profil (nom), jours.",
    "depense": "Dépense hors temps passé : montant, catégorie, statut (prévue | engagée | payée).",
    "facture": "Échéance de facturation : montant, date prévue, statut (à facturer | facturée | payée), jalon déclencheur.",
    "changement": "Demande de changement : titre, description, demandeur, décideur, origine (attente | hypothese | "
                  "risque | directe, avec origine_id), lot, statut (à instruire | chiffrée | présentée | acceptée | refusée | "
                  "reportée), décalage des jalons en jours et jalons_ids touchés. Utiliser les outils dédiés pour créer, "
                  "chiffrer, présenter et décider.",
    "hypothese": "Hypothèse suivie (planning, chiffrage, périmètre, organisation, technique, données, budget) : "
                 "statut à vérifier | confirmée | invalidée, porteur qui doit la confirmer, échéance de vérification, "
                 "impact si elle est invalidée. Passer une hypothèse à « invalidée » crée le risque correspondant (risque_id).",
    "attente": "Attente du client : partie prenante, catégorie (délai | périmètre | qualité | coût | relation | communication), "
               "priorité (1 forte à 3), satisfaction (1 à 5), position (alignée | à recadrer | hors périmètre), "
               "réponse, prochaine action, échéance, date de dernière revue.",
}

INSTRUCTIONS = """Co-pilote de mission : pilotage d'une mission de conseil (cadrage, gouvernance, risques,
décisions, chiffrage, budget, attentes du client). Plusieurs missions coexistent ; chaque outil prend
un paramètre `mission` (clé, voir lister_missions) et utilise sinon la dernière mission ouverte.

Règles :
- Les chiffres (KPI, atterrissage, budget, alertes) sont calculés par l'outil : lisez-les avec
  synthese, budget, chiffrage… ne les recalculez pas et n'en inventez pas.
- N'inventez aucune donnée : un champ inconnu reste vide. Les dates sont au format AAAA-MM-JJ.
- Chaque écriture est inscrite à l'historique (origine « assistant (MCP) ») et peut être annulée
  avec annuler_modification. Confirmez avec l'utilisateur avant une suppression ou une série
  d'écritures déduites d'un document.
- decrire_modele donne les tables, leurs champs et les valeurs admises."""

serveur = MCPServer("copilote", title="Co-pilote de mission", instructions=INSTRUCTIONS, version="0.1")
LECTURE = ToolAnnotations(read_only_hint=True, open_world_hint=False)
ECRITURE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
SUPPRESSION = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)


def _auj():
    return dt.date.today()


@contextlib.contextmanager
def _sur(mission):
    """Ouvre la mission demandée (ou la dernière) ; les écritures portent l'origine de l'assistant.

    Les erreurs attendues sont levées en ToolError : leur message parvient à l'assistant (une autre
    exception n'arrive que sous la forme « Error executing tool … »)."""
    cle = (mission or "").strip() or db.derniere()
    if not cle or not db.existe(cle):
        raise ToolError(f"Mission introuvable : {mission!r}. Utilisez lister_missions pour connaître les clés.")
    with db.dans(cle), db.origine(ORIGINE):
        yield cle


def _table(table, ecriture=True):
    autorisees = donnees.EDITABLES if ecriture else LISIBLES
    if table not in autorisees:
        raise ToolError(f"Table « {table} » non prise en charge. Tables possibles : {', '.join(sorted(autorisees))}.")


def _champs(table, champs):
    """Valeurs prêtes à stocker (objets et listes en JSON) et champs inconnus."""
    if not isinstance(champs, dict) or not champs:
        raise ToolError("`champs` doit être un objet non vide {champ: valeur}.")
    connus = db.TABLES[table]
    propres = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
               for k, v in champs.items() if k in connus}
    return propres, sorted(k for k in champs if k not in connus)


# ---------------------------------------------------------------- lecture

@serveur.tool(annotations=LECTURE)
def lister_missions() -> dict[str, Any]:
    """Liste les missions (clé, nom, client, dernière modification) et la dernière ouverte."""
    return {"missions": db.missions(), "derniere": db.derniere()}


@serveur.tool(annotations=LECTURE)
def decrire_modele() -> dict[str, Any]:
    """Décrit les tables de la mission : rôle, champs et valeurs admises. À lire avant d'écrire."""
    return {"tables": {t: {"description": DESCRIPTIONS.get(t, ""), "champs": list(cols),
                           "modifiable": t in donnees.EDITABLES}
                       for t, cols in db.TABLES.items()},
            "tailles_macro": finances.TAILLES, "recurrences": agenda.RECURRENCES}


@serveur.tool(annotations=LECTURE)
def fiche_mission(mission: str | None = None) -> dict[str, Any]:
    """Fiche de la mission : objectifs, porteurs, hypothèses, date cible, budget vendu, paramètres."""
    with _sur(mission) as cle:
        return {"cle": cle, **db.mission()}


@serveur.tool(annotations=LECTURE)
def synthese(mission: str | None = None) -> dict[str, Any]:
    """Synthèse calculée : réponses aux trois questions du sponsor (délai, budget, client) avec leur état,
    décisions à obtenir, tendance et son historique, alertes de niveau projet (2) et sponsor (3),
    KPI des sprints, atterrissage."""
    with _sur(mission) as cle:
        return {"cle": cle, **donnees.synthese(_auj())}  # inclut reponses (délai, budget, client)


@serveur.tool(annotations=LECTURE)
def lister_elements(table: str, mission: str | None = None, recherche: str | None = None) -> dict[str, Any]:
    """Liste les éléments d'une table (voir decrire_modele). `recherche` filtre sur le texte, sans casse."""
    _table(table, ecriture=False)
    with _sur(mission):
        lignes = db.lister(table)
    if recherche:
        r = recherche.lower()
        lignes = [l for l in lignes if any(r in str(v).lower() for v in l.values() if v is not None)]
    return {"table": table, "nombre": len(lignes), "elements": lignes}


@serveur.tool(annotations=LECTURE)
def lire_element(table: str, id: int, mission: str | None = None) -> dict[str, Any]:
    """Lit un élément par son identifiant."""
    _table(table, ecriture=False)
    with _sur(mission):
        e = db.lire(table, id)
    if not e:
        raise ToolError(f"Aucun élément {id} dans « {table} ».")
    return e


@serveur.tool(annotations=LECTURE)
def suivi_risques(mission: str | None = None) -> dict[str, Any]:
    """Registre des risques avec criticité et évolution depuis la dernière session (dernière météo)."""
    with _sur(mission):
        return donnees.suivi_risques(_auj())


@serveur.tool(annotations=LECTURE)
def chiffrage(mission: str | None = None) -> dict[str, Any]:
    """Chiffrage en deux modes (macro et détaillé) : lignes valorisées, majorations, totaux,
    fourchettes, comparaison par lot et mode retenu."""
    with _sur(mission):
        return donnees.chiffrage()


@serveur.tool(annotations=LECTURE)
def budget(mission: str | None = None) -> dict[str, Any]:
    """Budget : vendu, consommé, reste à faire, atterrissage, écart, marge, facturation, consommation
    mensuelle, détail par profil et alertes."""
    with _sur(mission):
        return donnees.budget(_auj())


@serveur.tool(annotations=LECTURE)
def attentes_client(mission: str | None = None) -> dict[str, Any]:
    """Attentes du client avec satisfaction, évolution (tirée de l'historique), revue due et alertes."""
    with _sur(mission):
        return donnees.suivi_attentes(_auj())


@serveur.tool(annotations=LECTURE)
def gouvernance(mission: str | None = None) -> dict[str, Any]:
    """Instances de gouvernance et calendrier type des deux prochaines semaines."""
    with _sur(mission):
        return {"instances": db.lister("instance"), "calendrier": agenda.calendrier(_auj())}


@serveur.tool(annotations=LECTURE)
def historique(mission: str | None = None, table: str | None = None, limite: int = 50) -> dict[str, Any]:
    """Dernières modifications (état avant / après, origine), les plus récentes d'abord."""
    if table:
        _table(table, ecriture=False)
    with _sur(mission):
        return {"entrees": db.journal(table or None, max(1, min(limite, 500)))}


@serveur.tool(annotations=LECTURE)
def exporter_mission(mission: str | None = None) -> dict[str, Any]:
    """Export complet de la mission (format copilote-mission : toutes les tables et l'historique)."""
    with _sur(mission):
        return db.exporter_mission()


@serveur.tool(annotations=LECTURE)
def a_traiter(mission: str | None = None) -> dict[str, Any]:
    """Ce que le pilote doit faire, classé : maintenant (retards, points critiques), cette semaine
    (échéances, réunions à préparer, saisies attendues), à surveiller. Chaque élément indique la table
    et l'id concernés, et les modifications directes possibles (champs à écrire avec modifier_element)."""
    with _sur(mission):
        return pilote.a_traiter(_auj())


@serveur.tool(annotations=LECTURE)
def preparer_seance(instance: int, mission: str | None = None) -> dict[str, Any]:
    """Ordre du jour minuté d'une instance de gouvernance (id de la table instance), adapté à son
    type (comité, point de suivi, rituel agile), avec le contenu de chaque point et les messages clés."""
    with _sur(mission):
        try:
            return pilote.preparer_seance(instance, _auj())
        except ValueError as e:
            raise ToolError(str(e)) from None


@serveur.tool(annotations=LECTURE)
def glissements(mission: str | None = None) -> dict[str, Any]:
    """Jalons et lots avec leur date de référence (engagement), l'écart en jours et le nombre de reports."""
    with _sur(mission):
        return pilote.glissements(_auj())


@serveur.tool(annotations=LECTURE)
def catalogue_chiffrage(recherche: str | None = None) -> dict[str, Any]:
    """Catalogue des blocs de chiffrage types (récupération de la data, API, recette…). Chaque bloc a
    trois niveaux : rapide (simple et clair), moyen (compliqué mais chemin clair), long (aucune
    information), avec les jours par rôle et le total. `recherche` filtre sur le nom, la famille ou
    la description."""
    c = catalogue.catalogue()
    if recherche:
        r = recherche.lower()
        c["blocs"] = [b for b in c["blocs"] if r in f"{b['nom']} {b['famille']} {b['description']}".lower()]
    return c


# ---------------------------------------------------------------- écriture

@serveur.tool(annotations=LECTURE)
def suivi_changements(mission: str | None = None) -> dict[str, Any]:
    """Demandes de changement avec leur origine, leur chiffrage (jours, montant, fourchette), leur statut,
    et le cumul accepté (montant, part du budget initial, décalage)."""
    with _sur(mission):
        return changements.suivi(_auj())


def _cr(fn, *args):
    try:
        return fn(*args)
    except changements.ErreurChangement as e:
        raise ToolError(str(e)) from None


@serveur.tool(annotations=ECRITURE)
def creer_changement(titre: str = "", origine_type: str = "directe", origine_id: int | None = None,
                     champs: dict[str, Any] | None = None, mission: str | None = None) -> dict[str, Any]:
    """Crée une demande de changement. origine_type : attente | hypothese | risque | directe ; avec une
    origine, le titre, le demandeur, le lot et la description sont repris de l'élément d'origine.
    champs : description, demandeur, decideur, lot, impact_delai_jours, jalons_ids (liste d'id)."""
    corps = {k: (json.dumps(v) if isinstance(v, list) else v) for k, v in (champs or {}).items()}
    corps.update({k: v for k, v in (("titre", titre), ("origine_type", origine_type), ("origine_id", origine_id)) if v})
    with _sur(mission):
        return _cr(changements.creer, corps, _auj())


@serveur.tool(annotations=ECRITURE)
def chiffrer_changement(changement: int, bloc: str, niveau: str, quantite: float = 1,
                        mission: str | None = None) -> dict[str, Any]:
    """Ajoute un bloc du catalogue (niveau rapide | moyen | long) au chiffrage d'une demande de changement."""
    with _sur(mission):
        lignes = _cr(changements.chiffrer_avec_bloc, changement, bloc, niveau, quantite)
        return {"lignes_creees": lignes, "chiffrage": changements.chiffrage(changement)}


@serveur.tool(annotations=ECRITURE)
def presenter_changement(changement: int, instance: str | None = None, echeance: str | None = None,
                         mission: str | None = None) -> dict[str, Any]:
    """Crée la décision « à prendre » d'une demande (rattachée au comité par défaut) : elle figure alors à
    l'ordre du jour de la séance."""
    with _sur(mission):
        return _cr(changements.presenter, changement, instance, echeance, _auj())


@serveur.tool(annotations=SUPPRESSION)
def decider_changement(changement: int, choix: str, motif: str = "", mission: str | None = None) -> dict[str, Any]:
    """Enregistre la décision : accepter (avenant : budget vendu, reste à faire et jalons mis à jour),
    refuser ou reporter. À n'appeler qu'avec la décision effective du client ou du comité."""
    with _sur(mission):
        return _cr(changements.decider, changement, choix, motif, _auj())


@serveur.tool(annotations=ECRITURE)
def chiffrer_avec_bloc(bloc: str, niveau: str, mode: str = "detaille", lot: str = "", quantite: float = 1,
                       libelle: str | None = None, mission: str | None = None) -> dict[str, Any]:
    """Ajoute au chiffrage un bloc du catalogue. niveau : rapide | moyen | long ; mode : detaille (une
    ligne par rôle, rapproché des profils de la mission) ou macro (une ligne) ; quantite : nombre
    d'unités du bloc (par exemple 3 sources de données) ; libelle remplace le nom du bloc."""
    with _sur(mission):
        try:
            crees = donnees.appliquer_bloc(bloc, niveau, mode, lot, quantite, libelle)
        except ValueError as e:
            raise ToolError(str(e)) from None
    return {"lignes_creees": crees}


@serveur.tool(annotations=ECRITURE)
def creer_element(table: str, champs: dict[str, Any], mission: str | None = None) -> dict[str, Any]:
    """Crée un élément (risque, décision, jalon, attente, estimation…). Les champs inconnus sont
    signalés et ignorés ; un risque ou une décision est daté du jour."""
    _table(table)
    propres, ignores = _champs(table, champs)
    with _sur(mission):
        element = donnees.creer_element(table, propres, _auj())
    return {"element": element, "champs_ignores": ignores}


@serveur.tool(annotations=ECRITURE)
def modifier_element(table: str, id: int, champs: dict[str, Any], mission: str | None = None) -> dict[str, Any]:
    """Modifie les champs donnés d'un élément ; les autres restent inchangés."""
    _table(table)
    propres, ignores = _champs(table, champs)
    with _sur(mission):
        element = donnees.modifier_element(table, id, propres, _auj())
    if element is None:
        raise ToolError(f"Aucun élément {id} dans « {table} ».")
    return {"element": element, "champs_ignores": ignores}


@serveur.tool(annotations=SUPPRESSION)
def supprimer_element(table: str, id: int, mission: str | None = None) -> dict[str, Any]:
    """Supprime un élément. Réversible : l'historique garde son contenu (annuler_modification)."""
    _table(table)
    with _sur(mission):
        if not db.lire(table, id):
            raise ToolError(f"Aucun élément {id} dans « {table} ».")
        db.supprimer(table, id)
        entree = db.journal(table, 1)[0]
    return {"supprime": id, "entree_historique": entree["id"]}


@serveur.tool(annotations=ECRITURE)
def modifier_fiche_mission(champs: dict[str, Any], mission: str | None = None) -> dict[str, Any]:
    """Modifie la fiche mission (objectifs, porteurs, hypothèses, date_cible, budget_vendu,
    chiffrage = paramètres du chiffrage, raci_roles = colonnes du RACI…)."""
    propres, ignores = _champs("mission", champs)
    with _sur(mission):
        return {"mission": donnees.modifier_fiche(propres), "champs_ignores": ignores}


@serveur.tool(annotations=ECRITURE)
def annuler_modification(entree: int, mission: str | None = None) -> dict[str, Any]:
    """Défait une entrée de l'historique (création, modification ou suppression), si l'élément
    n'a pas changé depuis."""
    with _sur(mission):
        try:
            return {"element": db.annuler(entree)}
        except (db.Conflit, db.Introuvable) as e:
            raise ToolError(str(e)) from None  # message transmis tel quel à l'assistant


@serveur.tool(annotations=ECRITURE)
def proposer_creneaux(tout: bool = False, mission: str | None = None) -> dict[str, Any]:
    """Pose les réunions sans créneau (ou toutes si `tout`) à partir du rythme des sprints,
    sans chevauchement, hors week-end et pause de midi."""
    with _sur(mission):
        return {"instances": agenda.proposer(tout, _auj())}


@serveur.tool(annotations=ECRITURE)
def creer_mission(nom: str, client: str = "", fiche: dict[str, Any] | None = None, modele: str | None = None,
                  reprendre_de: str | None = None, reprendre: list[str] | None = None) -> dict[str, Any]:
    """Crée une mission et renvoie sa clé. fiche : autres champs de la fiche (objectif_business,
    objectif_solution, objectif_projet, porteurs, date_debut, date_cible, duree_sprint_jours, budget_vendu…).
    modele : clé d'un modèle de mission (voir lister_modeles_mission) — cadre et squelette, dates
    calculées depuis fiche.date_debut. Sinon reprendre_de : clé d'une mission existante dont reprendre
    le cadre ; reprendre : parties parmi organisation, gouvernance, profils, raci, chiffrage."""
    try:
        cle = db.creer_mission_complete({**(fiche or {}), "nom": nom, "client": client}, reprendre_de, reprendre or [], modele)
    except (ValueError, db.Introuvable) as e:
        raise ToolError(str(e)) from None
    with db.dans(cle):
        return {"cle": cle, "demarrage": pilote.demarrage()}


@serveur.tool(annotations=LECTURE)
def lister_modeles_mission() -> dict[str, Any]:
    """Modèles de mission (fournis et personnels) : description et contenu (acteurs, instances, profils,
    lots, jalons, hypothèses, risques, blocs de chiffrage)."""
    return {"modeles": modeles_mission.lister()}


@serveur.tool(annotations=ECRITURE)
def enregistrer_modele_mission(nom: str, description: str = "", anonymiser: bool = True,
                               mission: str | None = None) -> dict[str, Any]:
    """Enregistre la mission comme modèle réutilisable : cadre et squelette, dates en relatif.
    anonymiser (par défaut) : les personnes deviennent leur rôle, sans e-mail."""
    with _sur(mission):
        modele = modeles_mission.depuis_mission(nom, description, anonymiser)
    try:
        return modeles_mission.enregistrer(modele)
    except ValueError as e:
        raise ToolError(str(e)) from None


@serveur.tool(annotations=LECTURE)
def demarrage_mission(mission: str | None = None) -> dict[str, Any]:
    """Étapes de cadrage d'une mission (fiche, lots, jalons, organisation, gouvernance, hypothèses,
    chiffrage ou budget, attentes, risques) et ce qu'il reste à faire."""
    with _sur(mission):
        return pilote.demarrage()


# ---------------------------------------------------------------- ressources

@serveur.resource("copilote://missions", name="missions", mime_type="application/json",
                  description="Liste des missions")
def ressource_missions() -> str:
    return json.dumps(lister_missions(), ensure_ascii=False)


@serveur.resource("copilote://modele", name="modele", mime_type="application/json",
                  description="Tables, champs et valeurs admises")
def ressource_modele() -> str:
    return json.dumps(decrire_modele(), ensure_ascii=False)


@serveur.resource("copilote://mission/{cle}/synthese", name="synthese", mime_type="application/json",
                  description="Synthèse calculée d'une mission")
def ressource_synthese(cle: str) -> str:
    return json.dumps(synthese(cle), ensure_ascii=False, default=str)


# ---------------------------------------------------------------- prompts

@serveur.prompt(title="Revue hebdomadaire")
def revue_hebdomadaire(mission: str = "") -> str:
    """Prépare la revue de la semaine : état, alertes, risques, attentes, budget, décisions à faire prendre."""
    return (f"Fais la revue hebdomadaire de la mission {mission or '(dernière ouverte)'} avec les outils du co-pilote.\n"
            "1. Lis synthese, suivi_risques, attentes_client et budget.\n"
            "2. Rédige une météo en cinq parties : tendance et pourquoi (en citant les alertes), "
            "faits marquants, risques en hausse ou nouveaux, attentes du client à recadrer, "
            "décisions à faire prendre et par qui.\n"
            "3. Liste les incohérences repérées (risque sans porteur, attente à recadrer sans action, "
            "facture en retard…) et propose les modifications, sans les appliquer avant mon accord.\n"
            "N'invente aucun chiffre : reprends ceux des outils.")


@serveur.prompt(title="Intégrer un compte rendu")
def integrer_compte_rendu(texte: str, mission: str = "") -> str:
    """Transforme un compte rendu en risques, décisions, actions et attentes du client, après validation."""
    return (f"Voici le compte rendu d'une réunion de la mission {mission or '(dernière ouverte)'} :\n\n{texte}\n\n"
            "1. Lis les risques, décisions et attentes existants (lister_elements) pour éviter les doublons.\n"
            "2. Propose sous forme de tableau : nouveaux éléments et mises à jour d'éléments existants "
            "(table, id le cas échéant, champs), chacun avec la phrase du compte rendu qui le justifie.\n"
            "3. Attends ma validation, puis enregistre le compte rendu (creer_element, table compte_rendu) "
            "et les éléments validés. Laisse vide ce que le texte ne dit pas.")


@serveur.prompt(title="Préparer un comité")
def preparer_comite(mission: str = "", instance: str = "Comité de pilotage") -> str:
    """Prépare l'ordre du jour et les messages clés d'un comité."""
    return (f"Prépare le {instance} de la mission {mission or '(dernière ouverte)'}.\n"
            "Lis synthese, budget, attentes_client, suivi_risques et les décisions à prendre (lister_elements, "
            "table decision). Produis : ordre du jour minuté, trois messages clés, décisions à obtenir avec "
            "options et recommandation, points d'attention budgétaires, attentes à recadrer et le message "
            "proposé pour chacune.")


def main():
    p = argparse.ArgumentParser(description="Serveur MCP du co-pilote de mission")
    p.add_argument("--http", action="store_true", help="Streamable HTTP au lieu de stdio")
    p.add_argument("--port", type=int, default=int(os.environ.get("COPILOTE_MCP_PORT", "8766")))
    args = p.parse_args()
    db.demarrer()
    if args.http:
        serveur.run("streamable-http", host="127.0.0.1", port=args.port)
    else:
        serveur.run()


if __name__ == "__main__":
    main()
