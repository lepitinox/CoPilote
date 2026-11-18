"""Données composées partagées par l'API et les exports."""
import datetime as dt
import json

import calculs
import catalogue
import db
import finances
import meteo


# Éléments que l'interface et l'assistant (MCP) peuvent créer, modifier et supprimer.
EDITABLES = {"jalon", "livrable", "sprint", "risque", "decision", "compte_rendu",
             "lot", "lot_element", "story", "activite", "acteur", "instance", "raci", "metier",
             "estimation", "profil", "consommation", "depense", "facture", "attente"}
CHAMPS_JSON_MISSION = ("seuils", "raci_roles", "chiffrage")


def creer_element(table, corps, aujourdhui=None):
    """Création avec les règles de datage : un risque ou une décision porte sa date de création."""
    auj = (aujourdhui or dt.date.today()).isoformat()
    corps = dict(corps or {})
    if table in ("risque", "decision"):
        corps["cree_le"] = auj
    if table == "risque" and not corps.get("maj_le"):
        corps["maj_le"] = auj
    return db.creer(table, corps)


def modifier_element(table, ident, corps, aujourdhui=None):
    """Modification ; None si l'élément n'existe pas."""
    existant = db.lire(table, ident)
    if not existant:
        return None
    corps = dict(corps or {})
    # Toute modification d'un risque le date du jour, sauf date saisie à la main.
    if table == "risque" and corps.get("maj_le") in (None, "", existant.get("maj_le")):
        corps["maj_le"] = (aujourdhui or dt.date.today()).isoformat()
    return db.modifier(table, ident, corps)


def appliquer_bloc(ident, niveau, mode="detaille", lot="", quantite=1, libelle=None):
    """Ajoute au chiffrage les lignes d'un bloc du catalogue ; renvoie les lignes créées."""
    p = finances.parametres(db.mission())
    rang = max([e.get("rang") or 0 for e in db.lister("estimation")] or [0]) + 1
    crees = []
    for l in catalogue.lignes(ident, niveau, mode, lot, quantite, db.lister("profil"), libelle, p["marges"]):
        crees.append(db.creer("estimation", {**l, "rang": rang}))
    return crees


def modifier_fiche(corps):
    corps = dict(corps or {})
    for cle in CHAMPS_JSON_MISSION:
        if isinstance(corps.get(cle), (dict, list)):
            corps[cle] = json.dumps(corps[cle], ensure_ascii=False)
    db.modifier("mission", 1, corps)
    return db.mission()


def etat_mission():
    return (db.mission(), db.lister("jalon"), db.lister("livrable"), db.lister("sprint"),
            db.lister("risque"), db.lister("decision"))


def chiffrage():
    return finances.chiffrage(db.mission(), db.lister("estimation"), db.lister("profil"))


def budget(aujourdhui=None):
    m = db.mission()
    return finances.budget(m, db.lister("profil"), db.lister("consommation"), db.lister("depense"),
                           db.lister("facture"), db.lister("livrable"), chiffrage(), aujourdhui)


def suivi_attentes(aujourdhui=None):
    return finances.attentes(db.lister("attente"), db.journal("attente", limite=1000), aujourdhui)


def alertes_complementaires(aujourdhui=None):
    """Déclencheurs hors livraison agile : budget, attentes du client, reports de jalons."""
    import pilote  # import tardif : pilote s'appuie sur ce module
    return (budget(aujourdhui)["alertes"] + suivi_attentes(aujourdhui)["alertes"]
            + pilote.alertes_glissements(pilote.glissements(aujourdhui), db.mission(), aujourdhui))


def synthese(aujourdhui=None):
    auj = aujourdhui or dt.date.today()
    # Les déclencheurs du budget et des attentes du client s'ajoutent à ceux de la livraison.
    import pilote
    b, a = budget(auj), suivi_attentes(auj)
    d = meteo.donnees(*etat_mission(), auj, b["alertes"] + a["alertes"]
                      + pilote.alertes_glissements(pilote.glissements(auj), db.mission(), auj))
    return {
        "semaine": d["semaine"], "tendance": d["tendance_calculee"], "alertes": d["alertes"],
        "budget": {k: b[k] for k in ("reference", "reference_source", "consomme", "atterrissage", "ecart", "taux_consomme")},
        "attentes": {"total": len(a["attentes"]),
                     "insatisfaites": sum(1 for x in a["attentes"] if isinstance(x.get("satisfaction"), int) and x["satisfaction"] <= 2),
                     "a_recadrer": sum(1 for x in a["attentes"] if x.get("position") == "à recadrer")},
        "reponses": pilote.reponses(auj), "decisions_en_attente": pilote.decisions_en_attente(auj),
        "tendances": pilote.historique_tendance(),
        "kpi": d["kpi"], "atterrissage": d["atterrissage"],
        "seuils": calculs.seuils(db.mission()),
        "propositions_en_attente": len(db.lister("proposition", "statut = 'en attente'")),
        "risques_ouverts": len(d["risques_ouverts"]),
        "decisions_a_prendre": len(d["decisions_a_prendre"]),
    }


def suivi_risques(aujourdhui=None):
    """Registre avec l'évolution depuis la dernière session (dernière météo générée)."""
    reference, photo = None, None
    meteos = db.lister("meteo")  # la plus récente d'abord
    auj = (aujourdhui or dt.date.today()).isoformat()
    # Une météo générée aujourd'hui décrit la session en cours, pas la précédente.
    for m in [x for x in meteos if (x.get("cree_le") or "") < auj] or meteos:
        try:
            photo = json.loads(m.get("risques_instantane") or "null")
        except ValueError:
            photo = None
        if photo is not None:
            reference = {"semaine": m["semaine"], "date": m["cree_le"]}
            break
    return {"reference": reference, "risques": calculs.evolution(db.lister("risque"), photo)}


def colonnes_raci(mission=None, acteurs=None):
    """Colonnes du RACI : (clé, libellé, précision). Un métier liste les personnes qui l'exercent."""
    mission = mission or db.mission()
    acteurs = acteurs if acteurs is not None else db.lister("acteur")
    par_id = {str(a["id"]): a for a in acteurs}
    out = []
    for cle in mission.get("raci_roles") or []:
        genre, valeur = cle.split(":", 1)
        if genre == "acteur":
            a = par_id.get(valeur)
            out.append((cle, a["nom"] if a else "Personne supprimée",
                        (a.get("metier") or a.get("role") or "") if a else ""))
        else:
            noms = [a["nom"] for a in acteurs if a.get("metier") == valeur]
            out.append((cle, valeur, ", ".join(noms[:3]) + (f" +{len(noms) - 3}" if len(noms) > 3 else "")))
    return out
