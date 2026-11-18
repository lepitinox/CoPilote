"""Catalogue de blocs de chiffrage types, chacun à trois niveaux de connaissance du sujet.

- rapide : simple et clair ;
- moyen  : compliqué mais chemin clair ;
- long   : aucune information.

Un bloc donne, pour chaque niveau, des jours par rôle type et un critère de choix (situation
type et ce que couvre la charge, voir catalogue_criteres.py). Appliqué à une mission, il crée des
lignes de chiffrage : une par rôle en mode détaillé (rôle rapproché des profils de la mission),
une seule en mode macro. Les valeurs par défaut sont un point de départ à calibrer : les blocs
personnalisés (enregistrés dans le dossier des missions, communs à toutes) les remplacent.
"""
import json
import os
import re

import db
from catalogue_criteres import CRITERES

NIVEAUX = {
    "rapide": {"libelle": "Simple et clair", "duree": "Rapide", "confiance": "forte"},
    "moyen": {"libelle": "Compliqué mais chemin clair", "duree": "Moyen", "confiance": "moyenne"},
    "long": {"libelle": "Aucune information", "duree": "Long", "confiance": "faible"},
}
# Rôles types des blocs. Rapprochés des profils de la mission par nom, puis par métier.
ROLES = ["Pilotage de projet", "Business analyst", "Architecte", "Tech lead", "Développeur",
         "Data engineer", "Data scientist", "UX / UI", "QA", "DevOps", "Sécurité", "Change"]
METIER_DU_ROLE = {"Data engineer": "Data", "Data scientist": "Data"}

PP, BA, AR, TL, DEV = "Pilotage de projet", "Business analyst", "Architecte", "Tech lead", "Développeur"
DE, DS, UX, QA, OPS, SEC, CHG = "Data engineer", "Data scientist", "UX / UI", "QA", "DevOps", "Sécurité", "Change"


def _b(ident, famille, nom, unite, description, rapide, moyen, long_):
    return {"id": ident, "famille": famille, "nom": nom, "unite": unite, "description": description,
            "niveaux": {"rapide": rapide, "moyen": moyen, "long": long_}}


BLOCS_DEFAUT = [
    # ---- Cadrage et conception
    _b("cadrage-besoin", "Cadrage et conception", "Ateliers de cadrage et expression du besoin", "par domaine",
       "Ateliers avec le métier, formalisation des besoins, priorisation et validation.",
       {BA: 2, PP: 1}, {BA: 5, PP: 2, AR: 1}, {BA: 10, PP: 4, AR: 3}),
    _b("specifications", "Cadrage et conception", "Spécifications fonctionnelles", "par module",
       "Règles de gestion, cas d'usage, critères d'acceptation, validation par le métier.",
       {BA: 3}, {BA: 8, TL: 1}, {BA: 15, TL: 3, PP: 2}),
    _b("architecture", "Cadrage et conception", "Dossier d'architecture", "par solution",
       "Architecture applicative et technique, choix structurants, passage en comité d'architecture.",
       {AR: 3}, {AR: 8, TL: 2}, {AR: 15, TL: 5, SEC: 2}),
    _b("maquettes-ux", "Cadrage et conception", "Maquettes et parcours utilisateur", "par parcours",
       "Parcours cible, maquettes interactives, itérations avec les utilisateurs.",
       {UX: 3}, {UX: 8, BA: 2}, {UX: 15, BA: 5}),
    _b("poc-technique", "Cadrage et conception", "Étude de faisabilité ou POC technique", "par sujet",
       "Lever une incertitude technique avec un prototype jetable et une recommandation.",
       {TL: 3, DEV: 2}, {TL: 6, DEV: 6}, {TL: 10, DEV: 12, AR: 3}),
    # ---- Données
    _b("recuperation-data", "Données", "Récupération de la data", "par source",
       "Identifier la source et son propriétaire, obtenir les accès, extraire, contrôler la complétude.",
       {DE: 2, BA: 0.5}, {DE: 6, BA: 2, PP: 1}, {DE: 12, BA: 5, PP: 3}),
    _b("qualite-donnees", "Données", "Nettoyage et qualité des données", "par jeu de données",
       "Profilage, règles de qualité, corrections, indicateurs de qualité partagés avec le métier.",
       {DE: 2}, {DE: 6, BA: 2}, {DE: 12, BA: 4, DS: 2}),
    _b("modelisation-donnees", "Données", "Modélisation des données", "par domaine",
       "Modèle de données cible (entrepôt, lac, schéma applicatif) et dictionnaire.",
       {DE: 4}, {DE: 10, AR: 2}, {DE: 20, AR: 5, BA: 4}),
    _b("pipeline-donnees", "Données", "Pipeline d'alimentation industrialisé", "par flux",
       "Ingestion planifiée, transformations, reprise sur erreur, supervision.",
       {DE: 4, OPS: 1}, {DE: 10, OPS: 3, QA: 2}, {DE: 18, OPS: 5, QA: 4, AR: 2}),
    _b("reporting", "Données", "Tableau de bord ou reporting", "par tableau",
       "Indicateurs définis avec le métier, préparation des données, restitution.",
       {DE: 2, BA: 1}, {DE: 5, BA: 3, UX: 1}, {DE: 10, BA: 6, UX: 2}),
    _b("migration-donnees", "Données", "Migration de données", "par domaine",
       "Correspondances, scripts de reprise, migrations à blanc, contrôles de réconciliation.",
       {DE: 4, QA: 1}, {DE: 12, QA: 4, BA: 2}, {DE: 25, QA: 8, BA: 5, PP: 3}),
    # ---- IA
    _b("poc-ia-generative", "Intelligence artificielle", "POC d'IA générative", "par cas d'usage",
       "Prompting, intégration d'un modèle, jeu d'exemples, démonstration au métier.",
       {DS: 4, DEV: 2}, {DS: 10, DEV: 5, BA: 2}, {DS: 20, DEV: 10, BA: 5, AR: 2}),
    _b("modele-ml", "Intelligence artificielle", "Modèle de machine learning", "par modèle",
       "Préparation des variables, entraînement, évaluation, choix du modèle.",
       {DS: 5, DE: 2}, {DS: 12, DE: 5}, {DS: 25, DE: 10, BA: 4}),
    _b("evaluation-ia", "Intelligence artificielle", "Évaluation et garde-fous d'un modèle", "par cas d'usage",
       "Jeu de test de référence, métriques, seuils d'acceptation, garde-fous et surveillance des dérives.",
       {DS: 3}, {DS: 8, BA: 2}, {DS: 15, BA: 5, SEC: 2}),
    _b("mlops", "Intelligence artificielle", "Industrialisation d'un modèle (MLOps)", "par modèle",
       "Packaging, déploiement, réentraînement, supervision en production.",
       {DS: 2, OPS: 3}, {DS: 4, OPS: 8, DE: 3}, {DS: 8, OPS: 15, DE: 6, AR: 3}),
    _b("rag-documents", "Intelligence artificielle", "Recherche augmentée sur des documents (RAG)", "par corpus",
       "Collecte et découpage du corpus, indexation, recherche, réponse sourcée, évaluation.",
       {DS: 4, DE: 2}, {DS: 8, DE: 5, BA: 2}, {DS: 15, DE: 10, BA: 4, SEC: 2}),
    # ---- Développement
    _b("ecran-standard", "Développement", "Écran ou formulaire standard", "par écran",
       "Écran de saisie ou de consultation avec contrôles, sur un socle existant.",
       {DEV: 2, QA: 0.5}, {DEV: 5, QA: 1, UX: 1}, {DEV: 10, QA: 2, UX: 3, BA: 2}),
    _b("regle-gestion", "Développement", "Règle de gestion ou moteur de calcul", "par règle",
       "Implémentation d'une règle métier, jeux de tests, validation des cas limites.",
       {DEV: 2, BA: 1}, {DEV: 6, BA: 3, QA: 2}, {DEV: 12, BA: 6, QA: 4}),
    _b("api-exposee", "Développement", "API exposée", "par API",
       "Contrat d'interface, implémentation, sécurité, documentation, tests.",
       {DEV: 3}, {DEV: 6, TL: 1, QA: 1}, {DEV: 12, TL: 3, QA: 3, AR: 1}),
    _b("authentification", "Développement", "Authentification et habilitations", "par application",
       "Connexion unique (SSO), rôles et droits, journalisation des accès.",
       {DEV: 3}, {DEV: 8, SEC: 2}, {DEV: 15, SEC: 5, AR: 2}),
    _b("notifications", "Développement", "Notifications et e-mails", "par famille de messages",
       "Déclencheurs, modèles de messages, envoi et suivi.",
       {DEV: 2}, {DEV: 4, QA: 1}, {DEV: 8, QA: 2, BA: 2}),
    _b("generation-documents", "Développement", "Génération de documents ou d'exports", "par document",
       "Production de PDF, Excel ou courriers à partir des données, mise en forme.",
       {DEV: 2}, {DEV: 5, QA: 1}, {DEV: 10, QA: 2, BA: 2}),
    # ---- Intégration
    _b("interface-tiers", "Intégration", "Interface avec un système tiers", "par interface",
       "Connecteur vers un système externe : contrat, développement, tests de bout en bout avec l'éditeur.",
       {DEV: 3, QA: 1}, {DEV: 8, TL: 2, QA: 2}, {DEV: 15, TL: 4, QA: 4, PP: 2}),
    _b("retro-ingenierie", "Intégration", "Reprise d'un existant (rétro-ingénierie)", "par composant",
       "Comprendre un code ou un système non documenté avant de le faire évoluer.",
       {TL: 2, DEV: 2}, {TL: 5, DEV: 6}, {TL: 10, DEV: 12, BA: 4}),
    # ---- Qualité et production
    _b("strategie-recette", "Qualité et mise en production", "Stratégie et plan de recette", "par projet",
       "Périmètre, jeux de données, cas de test, organisation de la recette métier.",
       {QA: 2}, {QA: 5, BA: 2}, {QA: 10, BA: 4, PP: 1}),
    _b("recette", "Qualité et mise en production", "Recette fonctionnelle", "par lot",
       "Exécution des cas de test, suivi des anomalies, non-régression, procès-verbal.",
       {QA: 4, BA: 1}, {QA: 10, BA: 3}, {QA: 20, BA: 6}),
    _b("tests-performance", "Qualité et mise en production", "Tests de performance", "par campagne",
       "Scénarios de charge, exécution, analyse et optimisations.",
       {QA: 2, OPS: 1}, {QA: 5, OPS: 3}, {QA: 10, OPS: 6, AR: 2}),
    _b("ci-cd", "Qualité et mise en production", "Environnements et chaîne CI/CD", "par application",
       "Environnements de développement, recette et production, déploiement automatisé.",
       {OPS: 3}, {OPS: 8, TL: 1}, {OPS: 15, TL: 3, SEC: 2}),
    _b("mise-en-production", "Qualité et mise en production", "Mise en production et hypercare", "par mise en production",
       "Plan de bascule, répétition, mise en production, support renforcé les premières semaines.",
       {OPS: 1, TL: 1, PP: 1}, {OPS: 3, TL: 3, PP: 2}, {OPS: 6, TL: 5, PP: 4, QA: 3}),
    # ---- Sécurité et conformité
    _b("risques-securite-rgpd", "Sécurité et conformité", "Analyse de risques sécurité et RGPD", "par traitement",
       "Analyse de risques, registre de traitement, mesures de protection des données.",
       {SEC: 2}, {SEC: 5, BA: 1}, {SEC: 10, BA: 3, AR: 2}),
    _b("homologation", "Sécurité et conformité", "Homologation et revue de conformité", "par application",
       "Dossier d'homologation, tests d'intrusion à piloter, levée des réserves.",
       {SEC: 1, PP: 1}, {SEC: 3, PP: 2}, {SEC: 6, PP: 4, AR: 2}),
    # ---- Accompagnement et pilotage
    _b("conduite-changement", "Accompagnement et pilotage", "Conduite du changement et formation", "par population",
       "Analyse d'impacts, plan de communication, supports et sessions de formation.",
       {CHG: 2}, {CHG: 6, BA: 2}, {CHG: 12, BA: 4, PP: 2}),
    _b("documentation-transfert", "Accompagnement et pilotage", "Documentation et transfert de compétences", "par équipe",
       "Documentation d'exploitation et de maintenance, sessions de passation.",
       {TL: 1, DEV: 1}, {TL: 3, DEV: 3}, {TL: 6, DEV: 6, BA: 3}),
    _b("pilotage-mois", "Accompagnement et pilotage", "Pilotage de projet", "par mois",
       "Planification, comités, suivi des risques, budget et reporting au client.",
       {PP: 4}, {PP: 8}, {PP: 12, BA: 2}),
]

_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,59}")


def _fichier():
    return os.path.join(db.DOSSIER, "catalogue-chiffrage.json")


def _personnalises():
    try:
        with open(_fichier(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def total(niveau):
    return round(sum(niveau.values()), 2)


def catalogue():
    """Blocs par défaut, remplacés ou complétés par les blocs personnalisés."""
    perso = _personnalises()
    blocs = []
    for b in BLOCS_DEFAUT:
        blocs.append({**(perso.get(b["id"]) or b), "id": b["id"], "origine": "personnalisé" if b["id"] in perso else "défaut"})
        if not any((blocs[-1].get("criteres") or {}).values()):  # critères d'origine si non personnalisés
            blocs[-1]["criteres"] = dict(zip(NIVEAUX, CRITERES.get(b["id"], ("", "", ""))))
    ids = {b["id"] for b in BLOCS_DEFAUT}
    blocs += [{**b, "id": i, "origine": "personnalisé"} for i, b in perso.items() if i not in ids]
    for b in blocs:
        b.setdefault("criteres", {n: "" for n in NIVEAUX})
        b["totaux"] = {n: total(b["niveaux"].get(n) or {}) for n in NIVEAUX}
    return {"niveaux": NIVEAUX, "roles": ROLES, "blocs": blocs}


def bloc(ident):
    b = next((x for x in catalogue()["blocs"] if x["id"] == ident), None)
    if not b:
        raise ValueError(f"Bloc inconnu : {ident}.")
    return b


def valider(b):
    if not isinstance(b, dict) or not str(b.get("nom") or "").strip():
        raise ValueError("Un bloc a un nom.")
    niveaux = b.get("niveaux")
    if not isinstance(niveaux, dict) or set(niveaux) != set(NIVEAUX):
        raise ValueError("Un bloc a les trois niveaux : rapide, moyen et long.")
    propre = {}
    for n, roles in niveaux.items():
        if not isinstance(roles, dict) or not roles:
            raise ValueError(f"Niveau « {NIVEAUX[n]['libelle']} » vide.")
        propre[n] = {}
        for r, j in roles.items():
            if not str(r).strip() or not isinstance(j, (int, float)) or isinstance(j, bool) or j < 0:
                raise ValueError(f"Charge invalide pour « {r} » : un nombre de jours positif est attendu.")
            propre[n][str(r).strip()] = j
    criteres = b.get("criteres") if isinstance(b.get("criteres"), dict) else {}
    return {"famille": str(b.get("famille") or "Mes blocs").strip(), "nom": str(b["nom"]).strip(),
            "unite": str(b.get("unite") or "").strip(), "description": str(b.get("description") or "").strip(),
            "niveaux": propre, "criteres": {n: str(criteres.get(n) or "").strip() for n in NIVEAUX}}


def enregistrer(ident, b):
    """Crée ou remplace un bloc personnalisé (un bloc par défaut est ainsi surchargé)."""
    if not ident:
        ident = db.slug(b.get("nom") if isinstance(b, dict) else "")
        existants = {x["id"] for x in catalogue()["blocs"]}
        base, n = ident, 1
        while ident in existants:
            n += 1
            ident = f"{base}-{n}"
    if not _ID.fullmatch(ident):
        raise ValueError("Identifiant de bloc invalide.")
    perso = _personnalises()
    perso[ident] = valider(b)
    os.makedirs(db.DOSSIER, exist_ok=True)
    with open(_fichier(), "w", encoding="utf-8") as f:
        json.dump(perso, f, ensure_ascii=False, indent=1)
    return bloc(ident)


def retirer(ident):
    """Supprime un bloc personnalisé ; un bloc par défaut retrouve ses valeurs d'origine."""
    perso = _personnalises()
    if ident not in perso:
        raise ValueError("Ce bloc n'est pas personnalisé : rien à retirer.")
    del perso[ident]
    with open(_fichier(), "w", encoding="utf-8") as f:
        json.dump(perso, f, ensure_ascii=False, indent=1)


def profil_pour(role, profils):
    """Profil de la mission correspondant à un rôle type : même nom, sinon même métier."""
    for cle in ("nom", "metier"):
        for p in profils:
            if (p.get(cle) or "") in (role, METIER_DU_ROLE.get(role)):
                return p["nom"]
    return role


def lignes(ident, niveau, mode="detaille", lot="", quantite=1, profils=(), libelle=None, marges=None):
    """Lignes d'estimation produites par un bloc, prêtes à enregistrer."""
    if niveau not in NIVEAUX:
        raise ValueError("Niveau inconnu : rapide, moyen ou long.")
    if mode not in ("macro", "detaille"):
        raise ValueError("Mode inconnu : macro ou detaille.")
    if not isinstance(quantite, (int, float)) or quantite <= 0:
        raise ValueError("La quantité est un nombre positif.")
    b = bloc(ident)
    roles = b["niveaux"][niveau]
    n = NIVEAUX[niveau]
    marge = (marges or {}).get(n["confiance"], {"forte": 0.15, "moyenne": 0.3, "faible": 0.5}[n["confiance"]])
    nom = (libelle or b["nom"]) + (f" × {quantite:g}" if quantite != 1 else "")
    hyp = f"Bloc « {b['nom']} » ({b['unite'] or 'unité'}), niveau {n['libelle'].lower()}."
    if (b.get("criteres") or {}).get(niveau):
        hyp += " " + b["criteres"][niveau]
    commun = {"mode": mode, "lot": lot or "", "libelle": nom, "hypothese": hyp, "confiance": n["confiance"],
              "bloc": b["id"], "niveau": niveau}

    def trois(j):
        j = round(j * quantite, 2)
        return {"jours_bas": round(j * (1 - marge), 2), "jours_probable": j, "jours_haut": round(j * (1 + marge), 2)}

    if mode == "macro":
        return [{**commun, **trois(total(roles))}]
    return [{**commun, "profil": profil_pour(r, profils), **trois(j)} for r, j in roles.items() if j]
