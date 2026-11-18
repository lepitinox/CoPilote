"""Exports PowerPoint et Excel des vues, à partir de modèles modifiables.

Chaque vue est d'abord décrite de façon neutre : une liste de diapositives, chacune avec
un titre et des éléments (tableau, colonnes, planning, graphique, tuiles, texte). Deux
moteurs la rendent : python-pptx pour PowerPoint, openpyxl pour Excel.

Modèles, du plus spécifique au plus général :
  modeles/<vue>.pptx|xlsx, puis modeles/commun.pptx|xlsx, puis le modèle par défaut.
PowerPoint : le masque et les dispositions du modèle donnent l'apparence ; les diapositives
qu'il contient (page de garde) sont conservées. Excel : la première feuille sert de gabarit,
la cellule {{contenu}} indique où écrire et donne le style des en-têtes, la cellule
au-dessous celui des lignes. Jetons remplacés partout : {{titre}}, {{mission}}, {{date}}.
"""
import copy as copie
import datetime as dt
import io
import math
import os
import re

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_MARKER_STYLE
from pptx.enum.dml import MSO_LINE_DASH_STYLE, MSO_THEME_COLOR
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

import agenda
import calculs
import db
import donnees
import finances

DOSSIER = os.environ.get(
    "COPILOTE_MODELES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "modeles"))

LIBELLES = {
    "route": "Feuille de route", "lotissement": "Lotissement détaillé", "storymap": "Story map",
    "planning": "Macro-planning", "organisation": "Organisation", "gouvernance": "Gouvernance",
    "sprintkpi": "Sprint et KPI", "raci": "RACI", "mission": "Fiche mission",
    "synthese": "Synthèse", "kpi": "Indicateurs", "risques": "Suivi des risques",
    "decisions": "Décisions et actions", "meteo": "Météo hebdomadaire", "sprints": "Sprints",
    "chiffrage": "Chiffrage", "budget": "Budget", "attentes": "Attentes du client",
    "seance": "Préparation de séance",
}
SANS_EXCEL = {"meteo"}
TAILLE_MAX_MODELE = 25 * 1024 * 1024

ENCRE, DOUX, TRAIT = "1C2430", "5D6878", "D0D5DC"
SERIE_1, SERIE_1_CLAIR, SERIE_2 = "2A78D6", "9EC5F4", "EB6834"
FONDS_LOTS = ["E3EEFB", "FDE9DF", "DCF3EA", "EEF0F3"]
VERT, ORANGE, ROUGE = ("E3F4EB", "1E7D4F"), ("FDF0DC", "A35A00"), ("FBE7E5", "B3261E")
RACI_COULEURS = {"R": ("1F5F8B", "FFFFFF"), "A": ("1C2430", "FFFFFF"),
                 "C": ("E8F1F7", "1F5F8B"), "I": ("EEF0F3", "5D6878")}
MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.",
               "oct.", "nov.", "déc."]


class ErreurExport(Exception):
    pass


fr = calculs.fr


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


# ---------------------------------------------------------------- description neutre

def diapo(titre, *elements, sous="", disposition="pile"):
    return {"titre": titre, "sous": sous, "elements": list(elements), "disposition": disposition}


def tableau(entetes, lignes, styles=None, largeurs=None, taille=10):
    """styles : {(ligne, colonne): {"fond", "texte", "gras", "centre"}} ; colonne None = toute la ligne."""
    return {"type": "tableau", "entetes": entetes,
            "lignes": [[("" if v is None else v) for v in l] for l in lignes],
            "styles": styles or {}, "largeurs": largeurs, "taille": taille}


def colonnes(cols):
    """cols : [{"titre", "sous", "items": [(texte, precision, genre)]}] ;
    genre : "" | "groupe" | "prerequis" | "adherence" | "vide"."""
    return {"type": "colonnes", "colonnes": cols}


def graphe(titre, genre, categories, series, maximum=None, pointilles=(), superposer=False):
    """series : [(nom, valeurs, couleur)] ; genre : "ligne" | "barre"."""
    return {"type": "graphe", "titre": titre, "genre": genre, "categories": categories,
            "series": series, "max": maximum, "pointilles": set(pointilles), "superposer": superposer}


def tuiles(liste):
    return {"type": "tuiles", "tuiles": liste}


def texte(paragraphes):
    return {"type": "texte", "paragraphes": [p for p in paragraphes if p]}


def _style(couple, gras=True, centre=False):
    return {"fond": couple[0], "texte": couple[1], "gras": gras, "centre": centre}


# ---------------------------------------------------------------- vues

def _lots():
    lots = db.lister("lot")
    return lots, {l["nom"]: i for i, l in enumerate(lots)}


def v_route():
    lots, elements = db.lister("lot"), db.lister("lot_element")
    if not lots:
        return [diapo("Feuille de route", texte(["Aucun lot défini."]))]
    cols = []
    for l in lots:
        def rubrique(axe, genre):
            liste = [(e["libelle"], e.get("detail") or "", genre)
                     for e in elements if e["lot"] == l["nom"] and e["axe"] == axe]
            return liste or [("Aucun", "", "vide")]
        sous = f"{l['nom']} · {l.get('titre') or ''}"
        if l.get("date"):
            sous += f" — livraison le {fr(l['date'])}"
        cols.append({"titre": l.get("periode") or "—", "sous": sous,
                     "items": [("Livré dans ce lot", "", "groupe")] + rubrique("contenu", "")
                     + [("Prérequis", "", "groupe")] + rubrique("prerequis", "prerequis")})
    return [diapo("Feuille de route", colonnes(cols),
                  sous="Ce que chaque lot livre, quand, et ce dont il dépend.")]


AXES = [("pour_qui", "Pour qui ?"), ("comment", "Comment ? (canaux)"),
        ("quoi", "Quoi ? (produits)"), ("fonctionnalite", "Grâce à quoi ? (fonctionnalités)"),
        ("prerequis", "Sous quels prérequis ?")]


def v_lotissement():
    lots, elements = db.lister("lot"), db.lister("lot_element")
    entetes = [""] + [f"{l['nom']} — {l.get('titre') or ''}\n{l.get('periode') or ''}" for l in lots]
    lignes, styles = [], {}
    for i, (axe, question) in enumerate(AXES):
        ligne = [question]
        for l in lots:
            items = [e["libelle"] + (f" ({e['detail']})" if e.get("detail") else "")
                     for e in elements if e["lot"] == l["nom"] and e["axe"] == axe]
            ligne.append("\n".join("• " + x for x in items))
        lignes.append(ligne)
        styles[(i, 0)] = {"gras": True}
    return [diapo("Lotissement détaillé", tableau(entetes, lignes, styles, [1.4] + [2] * len(lots)),
                  sous="Pour qui, comment, quoi, grâce à quoi — et sous quels prérequis.")]


def v_storymap():
    lots, rang = _lots()
    stories = db.lister("story")
    etapes = list(dict.fromkeys(s["etape"] for s in stories))
    noms = [l["nom"] for l in lots] + [n for n in dict.fromkeys(s["lot"] for s in stories)
                                       if n not in rang]
    lignes, styles = [], {}
    for i, nom in enumerate(noms):
        periode = next((l.get("periode") for l in lots if l["nom"] == nom), "") or ""
        ligne = [f"{nom}\n{periode}".strip()]
        for e in etapes:
            items = [s["libelle"] + (" ●" if s.get("irritant") else "") + (" ★" if s.get("innovation") else "")
                     for s in stories if s["etape"] == e and s["lot"] == nom]
            ligne.append("\n".join("• " + x for x in items))
        lignes.append(ligne)
        styles[(i, None)] = {"fond": FONDS_LOTS[min(rang.get(nom, 3), 3)], "texte": ENCRE}
        styles[(i, 0)] = {"fond": FONDS_LOTS[min(rang.get(nom, 3), 3)], "texte": ENCRE, "gras": True}
    return [diapo("Story map", tableau(["Lot"] + etapes, lignes, styles, [1] + [1.6] * len(etapes), taille=9),
                  sous=f"{len(stories)} stories · ● répond à un irritant · ★ innovation")]


def v_planning(aujourdhui=None):
    activites, jalons = db.lister("activite"), db.lister("jalon")
    dates = [d for a in activites for d in (calculs.date(a.get("debut")), calculs.date(a.get("fin"))) if d]
    dates += [d for d in (calculs.date(j.get("date")) for j in jalons) if d]
    if not dates:
        return [diapo("Macro-planning", texte(["Aucune activité ni jalon daté."]))]
    debut = min(dates).replace(day=1)
    dernier = max(dates)
    fin = dt.date(dernier.year + dernier.month // 12, dernier.month % 12 + 1, 1)
    mois, d = [], debut
    while d < fin:
        mois.append(d)
        d = dt.date(d.year + d.month // 12, d.month % 12 + 1, 1)
    pistes = []
    for a in activites:
        da, fa = calculs.date(a.get("debut")), calculs.date(a.get("fin"))
        if not (da and fa):
            continue
        nom = a.get("piste") or "Autres"
        if nom not in [p[0] for p in pistes]:
            pistes.append((nom, []))
        next(p for p in pistes if p[0] == nom)[1].append((a["libelle"], da, fa))
    gantt = {"type": "gantt", "debut": debut, "fin": fin, "mois": mois,
             "aujourdhui": aujourdhui or dt.date.today(),
             "jalons": [(j["libelle"], calculs.date(j["date"]), j.get("statut") == "atteint")
                        for j in jalons if calculs.date(j.get("date"))],
             "pistes": pistes}
    hyp = db.mission().get("hypotheses")
    return [diapo("Macro-planning", gantt, sous=f"Hypothèses : {hyp}" if hyp else "")]


CERCLES = [("métier", "Métier"), ("équipe projet", "Équipe projet"), ("IT", "IT"), ("externe", "Externes")]


def v_organisation():
    acteurs = db.lister("acteur")
    cols = []
    for cle, titre in CERCLES:
        membres = [a for a in acteurs if a.get("cercle") == cle]
        items = []
        for entite in dict.fromkeys(a.get("entite") or "" for a in membres):
            if entite:
                items.append((entite, "", "groupe"))
            for a in [x for x in membres if (x.get("entite") or "") == entite]:
                precision = " · ".join(x for x in (a.get("nom"), a.get("metier")) if x)
                if a.get("adherence"):
                    precision += f"\nAdhérence : {a['adherence']}"
                items.append((a.get("role") or a.get("nom") or "—", precision,
                              "adherence" if a.get("adherence") else ""))
        n_adh = sum(1 for a in membres if a.get("adherence"))
        cols.append({"titre": titre, "sous": f"{len(membres)} acteur(s), dont {n_adh} en adhérence",
                     "items": items or [("Aucun", "", "vide")]})
    liste = tableau(["Cercle", "Entité", "Nom", "Rôle", "Métier", "E-mail", "Adhérence avec l'équipe projet"],
                    [[a.get("cercle"), a.get("entite"), a.get("nom"), a.get("role"), a.get("metier"),
                      a.get("email"), a.get("adherence")] for a in acteurs],
                    largeurs=[1, 1.4, 1.2, 1.5, 1.1, 1.6, 2.4], taille=9)
    return [diapo("Organisation", colonnes(cols),
                  sous="L'équipe projet et les entités en adhérence (encadrées en orange)."),
            diapo("Organisation — annuaire", liste)]


def creneau(inst):
    p = calculs.date(inst.get("premiere"))
    if not p or not inst.get("heure"):
        return "À poser"
    code = inst.get("recurrence")
    if code == "quotidienne":
        return f"Chaque jour ouvré à {inst['heure']}"
    quand = agenda.RECURRENCES.get(code, "")
    return f"{agenda.JOURS[p.weekday()].capitalize()} {inst['heure']} · {quand.lower()} (dès le {fr(p)})"


def v_gouvernance(aujourdhui=None):
    instances = db.lister("instance")
    acteurs = {a["id"]: a for a in db.lister("acteur")}
    lignes = []
    for i in instances:
        noms = [acteurs[x]["nom"] for x in db.ids(i.get("participants_ids")) if x in acteurs]
        participants = "\n".join(x for x in (", ".join(noms), i.get("participants")) if x)
        objectifs = "\n".join("• " + o for o in (i.get("objectifs") or "").split("\n") if o.strip())
        duree = i.get("duree") or (f"{i['duree_min']} min" if i.get("duree_min") else "")
        lignes.append([i.get("chantier"), i.get("nom"), objectifs, participants,
                       i.get("frequence") or agenda.RECURRENCES.get(i.get("recurrence"), ""),
                       duree, creneau(i)])
    d1 = diapo("Gouvernance", tableau(
        ["Chantier", "Instance", "Objectifs", "Participants", "Fréquence", "Durée", "Créneau"],
        lignes, {(k, 1): {"gras": True} for k in range(len(lignes))},
        [1.1, 1.2, 2.8, 2.2, 1.2, 0.7, 1.6], taille=9))
    cal = agenda.calendrier(aujourdhui)
    semaines = {}
    for j in cal["jours"]:
        d = calculs.date(j["date"])
        lundi = d - dt.timedelta(days=d.weekday())
        semaines.setdefault(lundi, {})[d.weekday()] = "\n".join(
            f"{s['debut']} {s['nom']}" for s in j["seances"])
    lignes_cal = [[f"Semaine du {fr(l)}"] + [jours.get(k, "") for k in range(5)]
                  for l, jours in sorted(semaines.items())]
    notes = []
    if cal["hors_sprint"]:
        notes.append("Hors de ce sprint : " + " ; ".join(
            f"{h['nom']} le {fr(h['date'])} à {h['heure']}" for h in cal["hors_sprint"]))
    if cal["non_planifiees"]:
        notes.append("Sans créneau : " + ", ".join(n["nom"] for n in cal["non_planifiees"]))
    d2 = diapo("Calendrier type d'un sprint",
               tableau(["", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"], lignes_cal,
                       {(k, 0): {"gras": True} for k in range(len(lignes_cal))},
                       [1.1, 1.6, 1.6, 1.6, 1.6, 1.6], taille=10),
               sous=f"Sprint du {fr(cal['debut'])} au {fr(cal['fin'])}. " + " ".join(notes))
    return [d1, d2]


KPI_A_COLLECTER = [
    ("Backlog projet", "Stock de user stories dans leurs différents états.", "Outil de tickets"),
    ("Backlog du lot", "Stock de stories restant à réaliser pour le lot en cours, en story points.", "Reste à faire du sprint"),
    ("Vélocité", "Story points réalisés pendant le sprint, comparés au prévu.", "Points prévus et réalisés"),
    ("Capacité", "Jours-homme réalisables sur le sprint, selon les jours ouvrés et les absences.", "Capacité du sprint"),
    ("Qualité", "Anomalies créées et corrigées ; temps de correction rapporté au temps de développement.", "Anomalies créées et corrigées"),
    ("Prédictibilité", "Taux de réalisation moyen sur les derniers sprints.", "Calculé"),
    ("Moral", "État d'esprit de l'équipe, de 1 à 5, et demandes éventuelles.", "Moral du sprint"),
    ("Périmètre", "Points ajoutés au backlog pendant le sprint, comparés à la marge prévue.", "Points ajoutés"),
]


def v_sprintkpi():
    instances = db.lister("instance")
    semaines = round((db.mission().get("duree_sprint_jours") or 14) / 7)

    def duree(motif, defaut):
        i = next((x for x in instances if re.search(motif, x.get("nom") or "", re.I)), None)
        return (i or {}).get("duree") or defaut

    def rite(nom, texte_, d):
        return (f"{nom} ({d})" if d else nom, texte_, "")
    cols = [
        {"titre": "Début de sprint", "sous": "", "items": [
            rite("Planification de sprint", "Définir le travail du sprint et estimer l'effort.", duree("planif", "1 h 30"))]},
        {"titre": "Pendant le sprint", "sous": "", "items": [
            rite("Mêlée quotidienne", "Travail de la veille, du jour, points bloquants.", duree("mêlée|daily", "15 min")),
            rite("Affinage du backlog", "Affiner les stories à venir, vérifier la DoR.", duree("affinage|refinement", "2 × 1 h")),
            rite("Synchro hebdo", "Alignement avec les équipes en adhérence.", duree("synchro|weekly", "30 min à 1 h"))]},
        {"titre": "Fin de sprint", "sous": "", "items": [
            rite("Collecte des KPI", "Relever les chiffres avant la démonstration.", ""),
            rite("Démonstration", "Travaux, indicateurs, planning ; feedback.", duree("démo", "1 h")),
            rite("Rétrospective", "Fonctionnement de l'équipe, plans d'action.", duree("rétro", "1 h 30"))]},
        {"titre": "Hors sprint", "sous": "", "items": [
            rite("Comité sponsor", "Orientations métier et techniques, arbitrages structurants.", duree("comité|sponsor", "1 h"))]},
    ]
    return [diapo("Déroulé d'un sprint", colonnes(cols),
                  sous=f"Un sprint dure {semaines} semaines. Les KPI se collectent en fin de sprint."),
            diapo("KPI à collecter à chaque sprint",
                  tableau(["KPI", "Définition", "Où il est saisi"], [list(k) for k in KPI_A_COLLECTER],
                          {(i, 0): {"gras": True} for i in range(len(KPI_A_COLLECTER))}, [1.2, 4, 1.6]))]


def v_raci():
    cols = donnees.colonnes_raci()
    lignes_raci = db.lister("raci")
    if not cols or not lignes_raci:
        return [diapo("RACI", texte(["Aucune colonne ou aucune activité définie."]))]
    entetes = ["Domaine", "Activité"] + [f"{lib}\n{prec}" if prec else lib for _, lib, prec in cols] + ["Contrôle"]
    lignes, styles = [], {}
    for i, l in enumerate(lignes_raci):
        v = db.valeurs_raci(l)
        lettres = [v.get(cle, "") for cle, _, _ in cols]
        n_a, n_r = lettres.count("A"), lettres.count("R")
        souci = (f"{n_a} approbateurs" if n_a > 1 else "Aucun approbateur" if not n_a
                 else "Aucun réalisateur" if not n_r else "")
        lignes.append([l.get("domaine"), l.get("activite")] + lettres + [souci or "OK"])
        for j, x in enumerate(lettres):
            if x in RACI_COULEURS:
                styles[(i, j + 2)] = _style(RACI_COULEURS[x], centre=True)
        styles[(i, len(entetes) - 1)] = _style(ORANGE if souci else VERT)
    return [diapo("RACI", tableau(entetes, lignes, styles, [1, 2.2] + [0.8] * len(cols) + [1.1], taille=9),
                  sous="R : réalise · A : approuve · C : est consulté · I : est informé")]


def v_mission():
    m = db.mission()
    champs = [("Mission", m.get("nom")), ("Client", m.get("client")),
              ("Objectif business", m.get("objectif_business")), ("Porteur business", m.get("porteur_business")),
              ("Objectif solution", m.get("objectif_solution")), ("Porteur solution", m.get("porteur_solution")),
              ("Objectif projet", m.get("objectif_projet")), ("Porteur projet", m.get("porteur_projet")),
              ("Hypothèses du planning", m.get("hypotheses")), ("Date cible", fr(m.get("date_cible"))),
              ("Durée d'un sprint", f"{m.get('duree_sprint_jours') or 14} jours")]
    livrables = db.lister("livrable")
    return [diapo("Fiche mission", tableau(["Champ", "Valeur"], [list(c) for c in champs],
                                           {(i, 0): {"gras": True} for i in range(len(champs))}, [1.4, 5])),
            diapo("Livrables de pilotage", tableau(
                ["Chantier", "Livrable", "Avancement", "Statut", "Tendance"],
                [[l.get("chantier"), l.get("libelle"),
                  f"{l['avancement']} %" if l.get("avancement") is not None else "",
                  l.get("statut"), l.get("tendance")] for l in livrables],
                {(i, 4): _style({"vert": VERT, "orange": ORANGE, "rouge": ROUGE}.get(l.get("tendance"), ("FFFFFF", ENCRE)))
                 for i, l in enumerate(livrables)}, [1.1, 2, 1, 3, 0.9]))]


ETATS = {"vert": ("Vert", VERT), "orange": ("Orange", ORANGE), "rouge": ("Rouge", ROUGE),
         "inconnu": ("Non mesurable", ("EEF0F3", DOUX))}


def v_synthese(aujourdhui=None):
    s = donnees.synthese(aujourdhui)
    rep, k, a = s["reponses"], s["kpi"], s["atterrissage"]
    lignes = [[t, ETATS[rep[c]["etat"]][0], rep[c]["phrase"], " · ".join(rep[c]["details"])]
              for c, t in (("delai", "Délai"), ("budget", "Budget"), ("client", "Client"))]
    styles = {(i, 1): _style(ETATS[rep[c]["etat"]][1], centre=True) for i, c in enumerate(("delai", "budget", "client"))}
    dec = s["decisions_en_attente"]
    diapos = [diapo("Synthèse", tableau(["Question", "État", "Réponse", "Détail"], lignes, styles, [0.9, 1, 3.2, 3]),
                    tableau(["Décision à obtenir", "Décideur", "Échéance", "En attente depuis"],
                            [[d["titre"], d.get("porteur") or "À désigner", fr(d.get("echeance")) + (" — en retard" if d["en_retard"] else ""),
                              f"{d['age_jours']} j" if d.get("age_jours") is not None else ""] for d in dec],
                            {(i, 2): _style(ROUGE) for i, d in enumerate(dec) if d["en_retard"]}, [3.4, 1.6, 1.6, 1.2])
                    if dec else texte(["Aucune décision en attente."]),
                    sous=f"{s['semaine']} — tendance calculée : {s['tendance']}")]
    if k:
        if a["atteignable"]:
            fin = fr(a["date_fin_estimee"])
            note = ("Pas de date cible" if a["ecart_sprints"] is None else "Dans la cible" if a["ecart_sprints"] == 0
                    else f"+{a['ecart_sprints']} sprints après la cible")
        else:
            fin, note = "Non calculable", "Le backlog ne se vide pas assez vite"
        taux = f"{round(k['taux_realisation'] * 100)} %" if k["taux_realisation"] is not None else "—"
        diapos.append(diapo("Synthèse — livraison", tuiles([
            ("Fin estimée", fin, note),
            (f"Sprint {k['sprint']} : réalisé / prévu", f"{_fmt(k['realise'])} / {_fmt(k['prevu'])}", taux),
            ("Reste à faire", f"{_fmt(k['reste'])} pts", f"{_fmt(a['consommation_nette'])} pts nets par sprint"),
            ("Points ajoutés", _fmt(k["ajoute"]), f"marge : {_fmt(s['seuils']['marge_ajout'])}"),
            ("Moral", f"{k['moral']} / 5" if k["moral"] else "—", "")])))
    diapos.append(diapo("Synthèse — alertes", _alertes(s["alertes"]) if s["alertes"] else texte(["Aucun déclencheur atteint."])))
    return diapos


def v_seance(instance_id=None, aujourdhui=None):
    import pilote
    if instance_id is None:
        candidates = [i for i in db.lister("instance") if pilote.type_seance(i) != "melee"]
        if not candidates:
            return [diapo("Préparation de séance", texte(["Aucune instance à préparer."]))]
        instance_id = candidates[0]["id"]
    s = pilote.preparer_seance(instance_id, aujourdhui)
    quand = (f"{fr(s['date'])}" + (f" à {s['instance']['heure']}" if s["instance"].get("heure") else "")) if s["date"] else "date à fixer"
    qui = ", ".join(p for p in s["participants"] + [s["autres_participants"]] if p) or "—"
    ordre = tableau(["Durée", "Point"], [[f"{p['minutes']} min" if p["minutes"] else "", p["titre"]] for p in s["ordre_du_jour"]],
                    None, [0.9, 6])
    diapos = [diapo(f"{s['instance']['nom']} — ordre du jour", ordre,
                    texte(["Messages clés :"] + ["• " + m for m in s["messages_cles"]]) if s["messages_cles"] else texte([]),
                    sous=f"{s['type_libelle']} · {quand} · {s['duree']} min · {qui}")]
    for p in s["ordre_du_jour"]:
        if p["contenu"] and p["cle"] != "ouverture":
            diapos.append(diapo(p["titre"], texte(["• " + c for c in p["contenu"]]), sous=f"{p['minutes']} min"))
    return diapos

def v_kpi():
    sprints = db.lister("sprint")
    s = donnees.synthese()
    k, a = s["kpi"], s["atterrissage"]
    if not sprints:
        return [diapo("Indicateurs", texte(["Aucun sprint saisi."]))]
    cat = [f"S{x['numero']}" for x in sprints]

    def col(cle):
        return [x.get(cle) if isinstance(x.get(cle), (int, float)) else None for x in sprints]
    cat_a, reel, proj = list(cat), col("reste"), [None] * len(cat)
    if a["atteignable"] and a["consommation_nette"] > 0:
        r, dernier = a["reste"] - a["consommation_nette"], sprints[-1]["numero"]
        for i in range(1, 15):
            cat_a.append(f"S{dernier + i}")
            reel.append(None)
            proj.append(max(round(r), 0))
            if r <= 0:
                break
            r -= a["consommation_nette"]
    seuil = round(s["seuils"]["taux_realisation_min"] * 100)
    taux = [round(x["realise"] / x["prevu"] * 100) if (x.get("prevu") or 0) > 0 and isinstance(x.get("realise"), (int, float))
            else None for x in sprints]
    fin = fr(a["date_fin_estimee"]) if a["atteignable"] else "non calculable"
    tu = tuiles([("Vélocité moyenne", f"{_fmt(k['velocite_moyenne'])} pts", f"{k['nb_sprints_moyenne']} derniers sprints"),
                 ("Prédictibilité", f"{round((k['predictibilite'] or 0) * 100)} %", "réalisé / prévu, en moyenne"),
                 ("Fin estimée", fin, f"cible : {fr(a['date_cible'])}"),
                 ("Anomalies en stock", _fmt(k["solde_anomalies"]), "créées moins corrigées")])
    return [
        diapo("Indicateurs", tu, graphe(f"Atterrissage — reste à faire en points (cible : {fr(a['date_cible'])})",
                                       "barre", cat_a, [("Reste à faire", reel, SERIE_1), ("Projection", proj, SERIE_1_CLAIR)],
                                       superposer=True)),
        diapo("Indicateurs — vélocité", graphe("Vélocité — points prévus et réalisés", "ligne", cat,
                                               [("Réalisé", col("realise"), SERIE_1), ("Prévu", col("prevu"), SERIE_2)]),
              graphe(f"Taux de réalisation (seuil : {seuil} %)", "ligne", cat,
                     [("Taux de réalisation", taux, SERIE_1), ("Seuil", [seuil] * len(cat), DOUX)], pointilles=["Seuil"]),
              disposition="cote"),
        diapo("Indicateurs — périmètre et qualité",
              graphe(f"Périmètre — points ajoutés (marge : {_fmt(s['seuils']['marge_ajout'])})", "barre", cat,
                     [("Points ajoutés", col("ajoute"), SERIE_1)]),
              graphe("Qualité — anomalies par sprint", "barre", cat,
                     [("Corrigées", col("anomalies_corrigees"), SERIE_1), ("Créées", col("anomalies_creees"), SERIE_2)]),
              disposition="cote"),
        diapo("Indicateurs — moral", graphe("Moral de l'équipe (1 à 5)", "ligne", cat,
                                            [("Moral", col("moral"), SERIE_1)], maximum=5)),
    ]


EVOLUTIONS = {"hausse": ("↗ En hausse", ROUGE), "baisse": ("↘ En baisse", VERT), "stable": ("→ Stable", ("EEF0F3", DOUX)),
              "nouveau": ("✚ Nouveau", ORANGE), "clos": ("✓ Clos", VERT)}


def _criticite(c):
    return ROUGE if c >= 6 else ORANGE if c >= 3 else VERT


def v_risques(aujourdhui=None):
    s = donnees.suivi_risques(aujourdhui)
    risques = s["risques"]
    ouverts = [r for r in risques if r.get("etat") != "clos"]
    clos = [r for r in risques if r.get("etat") == "clos"]
    lettres = {r["id"]: chr(65 + i % 26) for i, r in enumerate(ouverts)}
    entetes = ["ID", "Risque", "Nature", "État", "Évolution depuis la dernière session", "Criticité",
               "Lot", "Porteur", "Échéance", "Plan d'action"]

    def lignes_de(liste):
        lignes, styles = [], {}
        for i, r in enumerate(liste):
            libelle, couleurs = EVOLUTIONS.get(r["evolution_session"], EVOLUTIONS["stable"])
            detail = ("saisie manuelle" if r["evolution_source"] == "saisie"
                      else f"criticité {r['criticite_precedente']} → {r['criticite']}"
                      if r.get("criticite_precedente") is not None and r["criticite_precedente"] != r["criticite"] else "")
            description = (r.get("description") or "").split("\n")[0]
            lignes.append([lettres.get(r["id"], "—"), r["titre"] + (f"\n{description}" if description else ""),
                           "Adhérence" if r.get("nature") == "adherence" else "Risque", r.get("etat"),
                           libelle + (f"\n{detail}" if detail else ""),
                           f"{r['criticite']} / 9" if r["criticite"] else "—", (r.get("lot") or "").strip(),
                           r.get("porteur") or "Sans porteur", fr(r.get("echeance")), r.get("plan_action")])
            styles[(i, 4)] = _style(couleurs)
            if r["criticite"]:
                styles[(i, 5)] = _style(_criticite(r["criticite"]), centre=True)
            if not r.get("porteur"):
                styles[(i, 7)] = _style(ORANGE)
            styles[(i, 0)] = {"gras": True, "centre": True}
        return lignes, styles
    largeurs = [0.4, 2.8, 0.9, 0.9, 1.5, 0.8, 0.5, 1.1, 1, 2]
    ref = (f"Évolution par rapport à la dernière session : {s['reference']['semaine']}, météo du {fr(s['reference']['date'])}."
           if s["reference"] else "Pas de session précédente : évolution saisie à la main.")
    lignes, styles = lignes_de(ouverts)
    diapos = [diapo("Suivi des risques", tableau(entetes, lignes, styles, largeurs, taille=9), sous=ref)]
    noms = ["faible", "moyen", "fort"]
    matrice, mstyles = [], {}
    for k, imp in enumerate([3, 2, 1]):
        ligne = [f"Impact {noms[imp - 1]}"]
        for p in (1, 2, 3):
            ligne.append(", ".join(lettres[r["id"]] for r in ouverts
                                   if r.get("probabilite") == p and r.get("impact") == imp))
            mstyles[(k, p)] = _style(_criticite(p * imp), centre=True)
        matrice.append(ligne)
        mstyles[(k, 0)] = {"gras": True}
    legende = [f"{lettres[r['id']]} : {r['titre']}" for r in ouverts]
    diapos.append(diapo("Matrice probabilité × impact",
                        tableau(["", "Probabilité faible", "Probabilité moyenne", "Probabilité forte"],
                                matrice, mstyles, [1.2, 1.4, 1.4, 1.4], taille=14),
                        texte(legende), disposition="cote"))
    if clos:
        lignes, styles = lignes_de(clos)
        diapos.append(diapo("Risques clos", tableau(entetes, lignes, styles, largeurs, taille=9)))
    return diapos


def v_decisions(aujourdhui=None):
    auj = (aujourdhui or dt.date.today()).isoformat()
    toutes = db.lister("decision")
    diapos = []
    for nature, titre in (("decision", "Décisions"), ("action", "Actions")):
        liste = [d for d in toutes if (d.get("nature") == "decision") == (nature == "decision")]
        lignes, styles = [], {}
        for i, d in enumerate(liste):
            ouverte = d.get("statut") in ("à prendre", "à faire")
            retard = ouverte and d.get("echeance") and d["echeance"] < auj
            lignes.append([d.get("titre"), d.get("statut"), d.get("porteur") or "Non désigné",
                           fr(d.get("echeance")) + (" — en retard" if retard else ""), d.get("instance"), d.get("detail")])
            if retard:
                styles[(i, 3)] = _style(ROUGE)
            if not d.get("porteur"):
                styles[(i, 2)] = _style(ORANGE)
        diapos.append(diapo(titre, tableau(["Titre", "Statut", "Décideur ou porteur", "Échéance", "Instance", "Détail"],
                                           lignes, styles, [2.4, 0.9, 1.3, 1.3, 1.2, 2.4])))
    return diapos


def v_sprints():
    sprints = db.lister("sprint")
    lignes = [[x.get("numero"), fr(x.get("date_fin")), x.get("capacite"), x.get("prevu"), x.get("realise"),
               f"{round(x['realise'] / x['prevu'] * 100)} %" if (x.get("prevu") or 0) > 0 and x.get("realise") is not None else "",
               x.get("ajoute"), x.get("reste"), x.get("anomalies_creees"), x.get("anomalies_corrigees"), x.get("moral")]
              for x in sprints]
    return [diapo("Sprints", tableau(["Sprint", "Fin", "Capacité (j/h)", "Prévu", "Réalisé", "Taux", "Ajouté",
                                      "Reste", "Anomalies créées", "Anomalies corrigées", "Moral"], lignes))]


def v_meteo(meteo_id=None):
    m = db.lire("meteo", meteo_id) if meteo_id else next(iter(db.lister("meteo")), None)
    if not m:
        return [diapo("Météo hebdomadaire", texte(["Aucune météo générée."]))]
    titre_general, sections, courante = "Météo hebdomadaire", [], None
    lignes = (m.get("contenu") or "").split("\n")
    i = 0
    while i < len(lignes):
        l = lignes[i].rstrip()
        if l.startswith("# "):
            titre_general = l[2:].strip()
            courante = {"titre": "Synthèse", "elements": [], "paragraphes": []}
            sections.append(courante)
        elif l.startswith("## "):
            courante = {"titre": l[3:].strip(), "elements": [], "paragraphes": []}
            sections.append(courante)
        elif l.startswith("|"):
            rangs = []
            while i < len(lignes) and lignes[i].startswith("|"):
                rangs.append([c.strip() for c in lignes[i].strip()[1:-1].split("|")])
                i += 1
            i -= 1
            rangs = [r for n, r in enumerate(rangs) if not (n == 1 and all(re.fullmatch(r"-+", c) for c in r))]
            if courante is None:
                courante = {"titre": "Météo", "elements": [], "paragraphes": []}
                sections.append(courante)
            if courante["paragraphes"]:
                courante["elements"].append(texte(courante["paragraphes"]))
                courante["paragraphes"] = []
            courante["elements"].append(tableau(rangs[0], rangs[1:]))
        elif l.strip():
            p = l.replace("**", "").strip("_")
            p = "• " + p[2:] if p.startswith("- ") else p
            if courante is None:
                courante = {"titre": "Météo", "elements": [], "paragraphes": []}
                sections.append(courante)
            courante["paragraphes"].append(p)
        i += 1
    diapos = []
    for s in sections:
        if s["paragraphes"]:
            s["elements"].append(texte(s["paragraphes"]))
        if s["elements"]:
            diapos.append(diapo(s["titre"], *s["elements"], sous=titre_general))
    return diapos


def _j(v):
    return "" if v is None else f"{round(v, 1):g} j".replace(".", ",")


def _alertes(alertes):
    return tableau(["Niveau", "Alerte", "Détail"],
                   [["Sponsor" if x["niveau"] >= 3 else "Projet", x["titre"], x["detail"]] for x in alertes],
                   {(i, 0): _style(ROUGE if x["niveau"] >= 3 else ORANGE) for i, x in enumerate(alertes)},
                   [0.8, 3, 3.5])


def v_chiffrage():
    c = donnees.chiffrage()
    euros = finances.euros
    diapos = []
    for mode, titre in (("macro", "Chiffrage macro — avant collecte"), ("detaille", "Chiffrage détaillé — après collecte")):
        m = c["modes"][mode]
        if not m["nb"]:
            continue
        t = m["total_jours"]
        tu = tuiles([("Charge de base", _j(m["base"]["retenu"]), f"{_j(m['base']['bas'])} à {_j(m['base']['haut'])}"),
                     (f"Majorations (+{round(c['taux_majoration'] * 100)} %)", _j(t["retenu"] - m["base"]["retenu"]), ""),
                     ("Charge totale", _j(t["retenu"]), f"{_j(t['bas'])} à {_j(t['haut'])}"),
                     ("Montant", euros(m["montant"]), f"{euros(m['montant_bas'])} à {euros(m['montant_haut'])}")])
        if mode == "macro":
            entetes = ["Lot", "Élément", "Taille", "Confiance", "Bas", "Retenu", "Haut", "Montant", "Hypothèses"]
            lignes = [[l.get("lot"), l.get("libelle"), l.get("taille"), l.get("confiance") or "moyenne", _j(l["bas"]),
                       _j(l["retenu"]), _j(l["haut"]), euros(l["montant"]), l.get("hypothese")] for l in m["lignes"]]
            larg = [0.6, 2.2, 0.6, 0.9, 0.7, 0.7, 0.7, 1, 2]
        else:
            entetes = ["Lot", "Élément", "Profil", "Bas", "Probable", "Haut", "PERT", "Montant", "Hypothèses"]
            lignes = [[l.get("lot"), l.get("libelle"), l.get("profil"), _j(l["bas"]), _j(l.get("jours_probable")),
                       _j(l["haut"]), _j(l["retenu"]), euros(l["montant"]), l.get("hypothese")] for l in m["lignes"]]
            larg = [0.6, 2.2, 1.2, 0.7, 0.7, 0.7, 0.7, 1, 1.8]
        retenu = " (retenu)" if c["parametres"]["mode_retenu"] == mode else ""
        diapos.append(diapo(titre + retenu, tu, tableau(entetes, lignes, None, larg, taille=9)))
    if c["modes"]["macro"]["nb"] and c["modes"]["detaille"]["nb"]:
        comp = c["comparaison"]
        diapos.append(diapo("Chiffrage — macro et détaillé par lot", tableau(
            ["Lot", "Macro", "Détaillé", "Écart"],
            [[l["lot"], _j(l["macro"]), _j(l["detaille"]) if l["detaille"] else "non détaillé",
              "" if l["ecart"] is None else f"{'+' if l['ecart'] > 0 else ''}{round(l['ecart'] * 100)} %"] for l in comp],
            {(i, 3): _style(ORANGE if abs(l["ecart"]) > 0.2 else VERT) for i, l in enumerate(comp) if l["ecart"] is not None},
            [1, 1.5, 1.5, 1.2]), sous="Charge de base, hors majorations"))
    return diapos or [diapo("Chiffrage", texte(["Aucun élément chiffré."]))]


def v_budget(aujourdhui=None):
    b = donnees.budget(aujourdhui)
    euros = finances.euros
    tu = tuiles([("Budget vendu" if b["reference_source"] == "vendu" else "Budget chiffré", euros(b["reference"]), ""),
                 ("Consommé", euros(b["consomme"]), f"{round((b['taux_consomme'] or 0) * 100)} % du budget"),
                 ("Reste à faire", euros(b["raf"]), ""),
                 ("Atterrissage", euros(b["atterrissage"]),
                  "" if b["ecart"] is None else ("Dépassement " if b["ecart"] < 0 else "Marge ") + euros(abs(b["ecart"]))),
                 ("Marge prévue", euros(b["marge"]), "" if b["taux_marge"] is None else f"{round(b['taux_marge'] * 100)} %"),
                 ("Facturé", euros(b["facture"]), f"payé {euros(b['paye'])}")])
    diapos = [diapo("Budget", tu, _alertes(b["alertes"]) if b["alertes"] else texte(["Aucun déclencheur atteint."]))]
    if b["par_mois"]:
        cat = [x["mois"] for x in b["par_mois"]]
        series = [("Cumul consommé", [x["cumul"] for x in b["par_mois"]], SERIE_1)]
        if b["reference"]:
            series.append(("Budget", [b["reference"]] * len(cat), DOUX))
        diapos.append(diapo("Budget — consommation", graphe("Consommé cumulé (€)", "ligne", cat, series, pointilles=["Budget"])))
    diapos.append(diapo("Budget — profils", tableau(
        ["Profil", "TJM", "Coût / j", "Consommé", "Reste à faire", "Atterrissage", "Montant"],
        [[p["nom"], euros(p.get("tjm")), euros(p.get("cout_journalier")), _j(p["consomme_jours"]), _j(p.get("raf_jours") or 0),
          _j(p["atterrissage_jours"]), euros(p["atterrissage"])] for p in b["par_profil"]], None, [1.6, 0.9, 0.9, 1, 1, 1, 1.1])))
    factures = db.lister("facture")
    auj = (aujourdhui or dt.date.today()).isoformat()
    diapos.append(diapo("Budget — échéancier de facturation", tableau(
        ["Échéance", "Jalon", "Date prévue", "Montant", "Statut"],
        [[f.get("libelle"), f.get("jalon"), fr(f.get("date_prevue")), euros(f.get("montant")), f.get("statut")] for f in factures],
        {(i, 4): _style(VERT if f.get("statut") == "payée" else ROUGE if (f.get("statut") or "à facturer") == "à facturer"
                        and (f.get("date_prevue") or "9") < auj else ORANGE) for i, f in enumerate(factures)},
        [2.4, 2, 1, 1, 1])))
    return diapos


def v_attentes(aujourdhui=None):
    a = donnees.suivi_attentes(aujourdhui)
    liste = sorted(a["attentes"], key=lambda x: (x.get("partie_prenante") or "", x.get("priorite") or 9))
    if not liste:
        return [diapo("Attentes du client", texte(["Aucune attente suivie."]))]
    evo = {"hausse": " ↗", "baisse": " ↘", "stable": " →"}
    lignes, styles = [], {}
    for i, x in enumerate(liste):
        s = x.get("satisfaction")
        lignes.append([x.get("partie_prenante"), x.get("libelle"), x.get("categorie"),
                       f"P{x['priorite']}" if x.get("priorite") else "",
                       (f"{s} / 5" + evo.get(x.get("evolution"), "")) if s is not None else "", x.get("position"),
                       " → ".join(v for v in (x.get("reponse"), x.get("prochaine_action")) if v), fr(x.get("echeance"))])
        if isinstance(s, int):
            styles[(i, 4)] = _style(ROUGE if s <= 2 else ORANGE if s == 3 else VERT)
        styles[(i, 5)] = _style({"alignée": VERT, "à recadrer": ORANGE}.get(x.get("position"), ("EEF0F3", DOUX)))
    diapos = [diapo("Attentes du client", tableau(
        ["Partie prenante", "Attente", "Catégorie", "Priorité", "Satisfaction", "Position", "Notre réponse", "Échéance"],
        lignes, styles, [1.2, 2.2, 0.9, 0.6, 0.9, 0.9, 2.4, 0.9], taille=9))]
    if a["alertes"]:
        diapos.append(diapo("Attentes du client — alertes", _alertes(a["alertes"])))
    return diapos


def construire(vue, meteo_id=None, aujourdhui=None):
    if vue not in LIBELLES:
        raise ErreurExport("Vue inconnue.")
    fonctions = {
        "route": v_route, "lotissement": v_lotissement, "storymap": v_storymap,
        "planning": lambda: v_planning(aujourdhui), "organisation": v_organisation,
        "gouvernance": lambda: v_gouvernance(aujourdhui), "sprintkpi": v_sprintkpi, "raci": v_raci,
        "mission": v_mission, "synthese": lambda: v_synthese(aujourdhui), "kpi": v_kpi,
        "risques": lambda: v_risques(aujourdhui), "decisions": lambda: v_decisions(aujourdhui),
        "meteo": lambda: v_meteo(meteo_id), "sprints": v_sprints,
        "chiffrage": v_chiffrage, "budget": lambda: v_budget(aujourdhui),
        "attentes": lambda: v_attentes(aujourdhui),
        "seance": lambda: v_seance(meteo_id, aujourdhui),
    }
    return fonctions[vue]()


# ---------------------------------------------------------------- modèles

def chemin_modele(cible, ext):
    return os.path.join(DOSSIER, f"{cible}.{ext}")


def source_modele(vue, ext):
    if os.path.isfile(chemin_modele(vue, ext)):
        return "vue"
    if os.path.isfile(chemin_modele("commun", ext)):
        return "commun"
    return "defaut"


def octets_modele(vue, ext):
    source = source_modele(vue, ext)
    if source != "defaut":
        with open(chemin_modele(vue if source == "vue" else "commun", ext), "rb") as f:
            return f.read()
    return _pptx_defaut() if ext == "pptx" else _xlsx_defaut()


def enregistrer_modele(cible, ext, octets):
    if cible != "commun" and cible not in LIBELLES:
        raise ErreurExport("Vue inconnue.")
    if not octets:
        raise ErreurExport("Fichier vide.")
    if len(octets) > TAILLE_MAX_MODELE:
        raise ErreurExport("Modèle trop volumineux (25 Mo au plus).")
    try:
        if ext == "pptx":
            Presentation(io.BytesIO(octets))
        else:
            if not load_workbook(io.BytesIO(octets)).worksheets:
                raise ValueError
    except Exception:
        raise ErreurExport(f"Ce fichier n'est pas un .{ext} lisible.")
    os.makedirs(DOSSIER, exist_ok=True)
    with open(chemin_modele(cible, ext), "wb") as f:
        f.write(octets)


def supprimer_modele(cible, ext):
    if os.path.isfile(chemin_modele(cible, ext)):
        os.remove(chemin_modele(cible, ext))


def etat_modeles():
    return {
        "commun": {ext: os.path.isfile(chemin_modele("commun", ext)) for ext in ("pptx", "xlsx")},
        "vues": {v: {ext: os.path.isfile(chemin_modele(v, ext)) for ext in ("pptx", "xlsx")} for v in LIBELLES},
    }


def _jetons(vue, titre=None):
    m = db.mission()
    return {"{{titre}}": titre or LIBELLES.get(vue, ""),
            "{{mission}}": " — ".join(x for x in (m.get("nom"), m.get("client")) if x),
            "{{date}}": fr(dt.date.today())}


def _remplacer(texte_, jetons):
    for k, v in jetons.items():
        texte_ = texte_.replace(k, v)
    return texte_


def exporter(vue, ext, meteo_id=None, aujourdhui=None):
    if ext not in ("pptx", "xlsx"):
        raise ErreurExport("Format inconnu.")
    if ext == "xlsx" and vue in SANS_EXCEL:
        raise ErreurExport("Cette vue ne s'exporte qu'en PowerPoint.")
    diapos = construire(vue, meteo_id, aujourdhui)
    octets = (_pptx(vue, diapos) if ext == "pptx" else _xlsx(vue, diapos))
    nom = re.sub(r"[^\w-]+", "-", (db.mission().get("nom") or "mission").lower()).strip("-") or "mission"
    return octets, f"{nom}-{vue}-{dt.date.today().isoformat()}.{ext}"


# ---------------------------------------------------------------- PowerPoint

def _pptx_defaut():
    prs = Presentation()
    k = 13.333 / 10  # le modèle intégré est en 4:3 ; on l'élargit en 16:9
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    # Seules les formes qui portent leur propre géométrie sont élargies : les autres
    # héritent du masque, déjà élargi (les élargir aussi doublerait le facteur).
    formes = list(prs.slide_master.placeholders)
    for disposition in prs.slide_layouts:
        formes += [p for p in disposition.placeholders if p._element.xfrm is not None]
    for f in formes:
        xfrm = f._element.xfrm
        if xfrm is not None and xfrm.off is not None and xfrm.ext is not None:
            xfrm.off.x, xfrm.ext.cx = int(xfrm.off.x * k), int(xfrm.ext.cx * k)
    titre_seul = _disposition_titre_seul(prs)
    for p in titre_seul.placeholders:  # titre plus compact : plus de place pour le contenu
        if p.placeholder_format.type == PP_PLACEHOLDER.TITLE:
            p.left, p.top, p.width, p.height = Inches(0.6), Inches(0.3), Inches(12.13), Inches(0.95)
    garde = prs.slides.add_slide(prs.slide_layouts[0])
    garde.shapes.title.text = "{{titre}}"
    garde.placeholders[1].text = "{{mission}}\n{{date}}"
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _disposition_titre_seul(prs):
    for d in prs.slide_layouts:
        if d.name.strip().lower() in ("title only", "titre seul"):
            return d
    for d in prs.slide_layouts:
        types = [p.placeholder_format.type for p in d.placeholders]
        if (PP_PLACEHOLDER.TITLE in types
                and not any(t in (PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT, PP_PLACEHOLDER.SUBTITLE) for t in types)):
            return d
    return prs.slide_layouts[min(5, len(prs.slide_layouts) - 1)]


def _zone(prs, disposition):
    largeur, hauteur = prs.slide_width, prs.slide_height
    titre = next((p for p in disposition.placeholders
                  if p.placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE)), None)
    geometrie = (titre.left, titre.top, titre.width, titre.height) if titre is not None else (None,)
    if None not in geometrie and titre.width > 0 and titre.height > 0:
        x, w, y = titre.left, titre.width, titre.top + titre.height + Inches(0.1)
    else:
        x, w, y = Inches(0.5), largeur - Inches(1), Inches(1.3)
    # Un modèle mal formé ne doit pas pousser le contenu hors de la diapositive.
    x = min(max(x, 0), largeur - Inches(2))
    w = min(w, largeur - x - Inches(0.3))
    y = min(max(y, Inches(0.6)), hauteur / 2)
    bas = hauteur - Inches(0.4)
    for p in disposition.placeholders:
        if (p.placeholder_format.type in (PP_PLACEHOLDER.FOOTER, PP_PLACEHOLDER.DATE, PP_PLACEHOLDER.SLIDE_NUMBER)
                and p.top is not None and p.top > hauteur / 2):
            bas = min(bas, p.top - Inches(0.05))
    return x, y, w, bas - y


def _rgb(hexa):
    return RGBColor.from_string(hexa)


def _remplir(tf, paragraphes, taille=11, gras=False, couleur=None, alignement=None):
    tf.word_wrap = True
    for i, p in enumerate(paragraphes):
        texte_, opts = p if isinstance(p, tuple) else (p, {})
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = para.add_run()
        run.text = _fmt(texte_)
        run.font.size = Pt(opts.get("taille", taille))
        run.font.bold = opts.get("gras", gras)
        c = opts.get("couleur", couleur)
        if c:
            run.font.color.rgb = _rgb(c)
        if alignement is not None:
            para.alignment = alignement


def _boite_texte(slide, x, y, w, h, paragraphes, **kw):
    b = slide.shapes.add_textbox(x, y, w, h)
    _remplir(b.text_frame, paragraphes, **kw)
    return b


def _nb_lignes(texte_, largeur, taille):
    par_ligne = max(int(largeur / 914400 * 125 / taille), 4)
    return sum(max(1, math.ceil(len(seg) / par_ligne)) for seg in _fmt(texte_).split("\n"))


def _hauteur_texte(lignes, taille):
    return Inches(0.0162 * taille * lignes + 0.08)


def _nouvelle(prs, disposition, titre):
    s = prs.slides.add_slide(disposition)
    if s.shapes.title is not None:
        s.shapes.title.text = titre
    else:
        _boite_texte(s, Inches(0.5), Inches(0.3), prs.slide_width - Inches(1), Inches(0.8),
                     [titre], taille=28, gras=True)
    return s


def _forme(slide, genre, x, y, w, h, fond=None, trait=None, pointille=False, theme=None):
    f = slide.shapes.add_shape(genre, x, y, w, h)
    if theme is not None:
        f.fill.solid()
        f.fill.fore_color.theme_color = theme
    elif fond:
        f.fill.solid()
        f.fill.fore_color.rgb = _rgb(fond)
    else:
        f.fill.background()
    if trait:
        f.line.color.rgb = _rgb(trait)
        f.line.width = Pt(1)
        if pointille:
            f.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    else:
        f.line.fill.background()
    f.shadow.inherit = False
    tf = f.text_frame
    tf.margin_left = tf.margin_right = Inches(0.07)
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    return f


def _trait(slide, x1, y1, x2, y2, couleur, epaisseur=0.75):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = _rgb(couleur)
    c.line.width = Pt(epaisseur)
    return c


def _pptx(vue, diapos):
    prs = Presentation(io.BytesIO(octets_modele(vue, "pptx")))
    jetons = _jetons(vue)
    for s in prs.slides:  # page de garde ou diapositives fixes du modèle
        for f in s.shapes:
            if f.has_text_frame:
                for p in f.text_frame.paragraphs:
                    if "{{" in "".join(r.text for r in p.runs) and p.runs:
                        p.runs[0].text = _remplacer("".join(r.text for r in p.runs), jetons)
                        for r in p.runs[1:]:
                            r.text = ""
    disposition = _disposition_titre_seul(prs)
    zone = _zone(prs, disposition)
    for d in diapos:
        _pptx_diapo(prs, disposition, zone, d)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _pptx_diapo(prs, disposition, zone, d):
    x, y, w, h = zone
    s = _nouvelle(prs, disposition, d["titre"])
    if d["sous"]:
        hs = _hauteur_texte(_nb_lignes(d["sous"], w, 11), 11)
        _boite_texte(s, x, y, w, hs, [d["sous"]], taille=11, couleur=DOUX)
        y, h = y + hs + Inches(0.05), h - hs - Inches(0.05)
    els, ecart = d["elements"], Inches(0.25)
    if d["disposition"] == "cote" and len(els) > 1:
        lw = int((w - ecart * (len(els) - 1)) / len(els))
        for i, el in enumerate(els):
            _pptx_element(s, el, x + i * (lw + ecart), y, lw, h)
        return
    for i, el in enumerate(els):
        if i < len(els) - 1:
            hh = min(_hauteur_fixe(el, w), int(h / 2))
            _pptx_element(s, el, x, y, w, hh)
            y, h = y + hh + ecart, h - hh - ecart
        elif el["type"] == "tableau":
            _pptx_tableau(prs, disposition, zone, d, s, el, x, y, w, h)
        elif el["type"] == "colonnes":
            _pptx_colonnes(prs, disposition, zone, d, s, el, x, y, w, h)
        else:
            _pptx_element(s, el, x, y, w, h)


def _hauteur_fixe(el, w):
    if el["type"] == "tuiles":
        return Inches(1.15)
    if el["type"] == "texte":
        return _hauteur_texte(sum(_nb_lignes(p, w, 12) for p in el["paragraphes"]), 12)
    return Inches(2.5)


def _pptx_element(s, el, x, y, w, h):
    genre = el["type"]
    if genre == "tableau":
        _pptx_table(s, el, list(range(len(el["lignes"]))), x, y, w)
    elif genre == "colonnes":
        _pptx_colonnes(None, None, None, None, s, el, x, y, w, h)
    elif genre == "graphe":
        _pptx_graphe(s, el, x, y, w, h)
    elif genre == "tuiles":
        _pptx_tuiles(s, el, x, y, w, h)
    elif genre == "texte":
        _boite_texte(s, x, y, w, h, el["paragraphes"], taille=12)
    elif genre == "gantt":
        _pptx_gantt(s, el, x, y, w, h)


def _largeurs(el, w):
    poids = el.get("largeurs") or [1] * len(el["entetes"])
    return [int(w * p / sum(poids)) for p in poids]


def _hauteur_ligne(ligne, largeurs, taille):
    return _hauteur_texte(max(_nb_lignes(v, lw, taille) for v, lw in zip(ligne, largeurs)), taille)


def _pptx_tableau(prs, disposition, zone, d, s, el, x, y, w, h):
    """Tableau découpé sur plusieurs diapositives, en-tête répété."""
    largeurs = _largeurs(el, w)
    taille = el["taille"]
    h_entete = _hauteur_ligne(el["entetes"], largeurs, taille)
    pages, courante, cumul = [], [], h_entete
    for i, ligne in enumerate(el["lignes"]):
        hl = _hauteur_ligne(ligne, largeurs, taille)
        if courante and cumul + hl > h:
            pages.append(courante)
            courante, cumul = [], h_entete
            h = zone[3]  # pages suivantes : toute la zone
        courante.append(i)
        cumul += hl
    pages.append(courante)
    for k, page in enumerate(pages):
        if k:
            s = _nouvelle(prs, disposition, d["titre"] + " (suite)")
            x, y = zone[0], zone[1]
        _pptx_table(s, el, page, x, y, w)


def _pptx_table(s, el, indices, x, y, w):
    largeurs = _largeurs(el, w)
    taille = el["taille"]
    lignes = [el["entetes"]] + [el["lignes"][i] for i in indices]
    hauteurs = [_hauteur_ligne(l, largeurs, taille) for l in lignes]
    cadre = s.shapes.add_table(len(lignes), len(largeurs), x, y, w, sum(hauteurs))
    t = cadre.table
    for j, lw in enumerate(largeurs):
        t.columns[j].width = lw
    for r, hl in enumerate(hauteurs):
        t.rows[r].height = hl
    for r, ligne in enumerate(lignes):
        for j, v in enumerate(ligne):
            cell = t.cell(r, j)
            cell.margin_left = cell.margin_right = Inches(0.05)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            sty = {} if r == 0 else {**el["styles"].get((indices[r - 1], None), {}),
                                    **el["styles"].get((indices[r - 1], j), {})}
            if sty.get("fond"):
                cell.fill.solid()
                cell.fill.fore_color.rgb = _rgb(sty["fond"])
            tf = cell.text_frame
            tf.text = ""
            _remplir(tf, [_fmt(v)], taille=taille, gras=(r == 0) or sty.get("gras", False),
                     couleur=sty.get("texte"), alignement=PP_ALIGN.CENTER if sty.get("centre") else None)
            if sty.get("centre"):
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE


def _hauteur_item(item, cw):
    texte_, precision, genre = item
    if genre == "groupe":
        return Inches(0.3)
    lignes = _nb_lignes(texte_, cw - Inches(0.14), 11)
    hauteur = 0.0175 * 11 * lignes + 0.12
    if precision:
        hauteur += 0.0175 * 9 * _nb_lignes(precision, cw - Inches(0.14), 9)
    return Inches(hauteur)


def _pptx_colonnes(prs, disposition, zone, d, s, el, x, y, w, h):
    cols = el["colonnes"]
    ecart = Inches(0.18)
    cw = int((w - ecart * (len(cols) - 1)) / len(cols))
    restes = [list(c["items"]) for c in cols]
    premiere = True
    while True:
        if not premiere:
            if prs is None:
                return  # élément non paginé : on s'arrête à la place disponible
            s = _nouvelle(prs, disposition, d["titre"] + " (suite)")
            x, y, w, h = zone
        h_tete = Inches(0.62 if any(c.get("sous") for c in cols) else 0.42)
        progression = False
        for i, c in enumerate(cols):
            cx = x + i * (cw + ecart)
            tete = _forme(s, MSO_SHAPE.RECTANGLE, cx, y, cw, h_tete, theme=MSO_THEME_COLOR.ACCENT_1)
            _remplir(tete.text_frame, [(c["titre"], {"taille": 15, "gras": True})]
                     + ([(c["sous"], {"taille": 9.5})] if c.get("sous") else []), couleur="FFFFFF")
            depart = y + h_tete + Inches(0.08)
            yy, limite = depart, y + h
            while restes[i]:
                item = restes[i][0]
                hi = _hauteur_item(item, cw)
                if yy + hi > limite and yy > depart:  # au moins un élément par colonne et par page
                    break
                _pptx_item(s, item, cx, yy, cw, hi)
                yy += hi + Inches(0.05)
                restes[i].pop(0)
                progression = True
        premiere = False
        if not any(restes) or not progression:
            return


def _pptx_item(s, item, x, y, w, h):
    texte_, precision, genre = item
    if genre == "groupe":
        _boite_texte(s, x, y, w, h, [texte_.upper()], taille=9, gras=True, couleur=DOUX)
        return
    fond, trait, pointille = {"prerequis": (None, "9AA3AF", True), "adherence": ("FDF0DC", "E0A458", False),
                              "vide": (None, None, False)}.get(genre, ("F1F3F6", None, False))
    f = _forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fond=fond, trait=trait, pointille=pointille)
    f.adjustments[0] = 0.12
    _remplir(f.text_frame, [(texte_, {"taille": 11, "gras": genre != "vide", "couleur": DOUX if genre == "vide" else ENCRE})]
             + ([(precision, {"taille": 9, "couleur": DOUX})] if precision else []), alignement=PP_ALIGN.LEFT)


def _pptx_tuiles(s, el, x, y, w, h):
    n = len(el["tuiles"])
    ecart = Inches(0.15)
    tw = int((w - ecart * (n - 1)) / n)
    for i, (nom, valeur, note) in enumerate(el["tuiles"]):
        f = _forme(s, MSO_SHAPE.ROUNDED_RECTANGLE, x + i * (tw + ecart), y, tw, h, fond="F1F3F6")
        f.adjustments[0] = 0.08
        _remplir(f.text_frame, [(nom, {"taille": 10, "couleur": DOUX}), (valeur, {"taille": 20, "gras": True}),
                                (note or "", {"taille": 9, "couleur": DOUX})], couleur=ENCRE, alignement=PP_ALIGN.LEFT)


def _pptx_graphe(s, el, x, y, w, h):
    donnees_ = CategoryChartData()
    donnees_.categories = el["categories"]
    for nom, valeurs, _ in el["series"]:
        donnees_.add_series(nom, valeurs)
    genre = XL_CHART_TYPE.LINE_MARKERS if el["genre"] == "ligne" else XL_CHART_TYPE.COLUMN_CLUSTERED
    graphique = s.shapes.add_chart(genre, x, y, w, h, donnees_).chart
    graphique.font.size = Pt(10)
    graphique.has_title = True
    graphique.chart_title.text_frame.text = el["titre"]
    graphique.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(13)
    graphique.has_legend = len(el["series"]) > 1
    if graphique.has_legend:
        graphique.legend.position = XL_LEGEND_POSITION.BOTTOM
        graphique.legend.include_in_layout = False
    axe = graphique.value_axis
    axe.has_major_gridlines = True
    axe.major_gridlines.format.line.color.rgb = _rgb("E6E9EE")
    axe.format.line.fill.background()
    if el.get("max"):
        axe.maximum_scale, axe.minimum_scale = el["max"], 0
    graphique.category_axis.tick_labels.font.size = Pt(9)
    graphique.category_axis.format.line.color.rgb = _rgb("B8C0CB")
    plot = graphique.plots[0]
    if el["genre"] == "barre":
        plot.gap_width = 60
        plot.overlap = 100 if el.get("superposer") else -5
    for serie, (nom, _, couleur) in zip(plot.series, el["series"]):
        if el["genre"] == "ligne":
            serie.smooth = False
            serie.format.line.color.rgb = _rgb(couleur)
            serie.format.line.width = Pt(2)
            if nom in el["pointilles"]:
                serie.format.line.dash_style = MSO_LINE_DASH_STYLE.DASH
                serie.marker.style = XL_MARKER_STYLE.NONE
            else:
                serie.marker.style = XL_MARKER_STYLE.CIRCLE
                serie.marker.size = 7
                serie.marker.format.fill.solid()
                serie.marker.format.fill.fore_color.rgb = _rgb(couleur)
                serie.marker.format.line.color.rgb = _rgb("FFFFFF")
        else:
            serie.format.fill.solid()
            serie.format.fill.fore_color.rgb = _rgb(couleur)


def _pptx_gantt(s, el, x, y, w, h):
    debut, fin, mois = el["debut"], el["fin"], el["mois"]
    total = max((fin - debut).days, 1)
    marge_libelle = Inches(1.7)
    gx, gw = x + marge_libelle, w - marge_libelle

    def pos(d):
        return gx + int(gw * (d - debut).days / total)
    h_tete = Inches(0.32)
    for i, m in enumerate(mois):
        suivant = mois[i + 1] if i + 1 < len(mois) else fin
        f = _forme(s, MSO_SHAPE.RECTANGLE, pos(m), y, pos(suivant) - pos(m), h_tete, fond="EEF0F3", trait="FFFFFF")
        _remplir(f.text_frame, [f"{MOIS_COURTS[m.month - 1]} {str(m.year)[2:]}"], taille=9, couleur=DOUX,
                 alignement=PP_ALIGN.CENTER)
        f.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    groupes = [("Jalons", max(len(el["jalons"]), 1))] + [(p, len(a)) for p, a in el["pistes"]]
    n = sum(c for _, c in groupes)
    lh = min(Inches(0.34), int((h - h_tete - Inches(0.05)) / max(n, 1)))
    bas = y + h_tete + lh * n
    for m in mois[1:]:
        _trait(s, pos(m), y + h_tete, pos(m), bas, "E6E9EE")
    yy = y + h_tete
    for g, (nom, nombre) in enumerate(groupes):
        _boite_texte(s, x, yy, marge_libelle - Inches(0.1), lh * nombre, [nom], taille=10, gras=True, couleur=ENCRE)
        if g == 0:
            for k, (libelle, date_, atteint) in enumerate(el["jalons"]):
                cy = yy + k * lh + int((lh - Inches(0.16)) / 2)
                cx = pos(date_)
                _forme(s, MSO_SHAPE.DIAMOND, cx - Inches(0.08), cy, Inches(0.16), Inches(0.16),
                       fond="1E7D4F" if atteint else ENCRE)
                etiquette = f"{libelle} · {fr(date_)}"
                lt = Inches(min(len(etiquette) * 0.075, 4))
                a_gauche = (cx - gx) > gw * 0.6
                _boite_texte(s, cx - Inches(0.12) - lt if a_gauche else cx + Inches(0.12), cy - Inches(0.06),
                             lt, Inches(0.25), [etiquette], taille=9, couleur=ENCRE,
                             alignement=PP_ALIGN.RIGHT if a_gauche else None)
        else:
            for k, (libelle, da, fa) in enumerate(el["pistes"][g - 1][1]):
                x1, x2 = pos(da), pos(fa + dt.timedelta(days=1))
                barre = _forme(s, MSO_SHAPE.RECTANGLE, x1, yy + k * lh + int(lh * 0.15), max(x2 - x1, Inches(0.05)),
                               int(lh * 0.7), fond=GRIS_PASSE if fa < el["aujourdhui"] else None,
                               theme=None if fa < el["aujourdhui"] else MSO_THEME_COLOR.ACCENT_1)
                barre.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
                largeur_texte = Inches(len(libelle) * 0.072 + 0.15)
                if x2 - x1 >= largeur_texte:
                    _remplir(barre.text_frame, [libelle], taille=9, couleur="FFFFFF")
                else:
                    a_gauche = (x2 - gx) > gw * 0.75
                    _boite_texte(s, x1 - largeur_texte - Inches(0.03) if a_gauche else x2 + Inches(0.03),
                                 yy + k * lh, largeur_texte, lh, [libelle], taille=9, couleur=ENCRE,
                                 alignement=PP_ALIGN.RIGHT if a_gauche else None)
        yy += lh * nombre
        _trait(s, x, yy, x + w, yy, "E6E9EE")
    if debut <= el["aujourdhui"] < fin:
        _trait(s, pos(el["aujourdhui"]), y + h_tete, pos(el["aujourdhui"]), bas, "B3261E", 1.5)


GRIS_PASSE = "8A94A3"


# ---------------------------------------------------------------- Excel

def _xlsx_defaut():
    wb = Workbook()
    ws = wb.active
    ws.title = "Gabarit"
    ws.sheet_view.showGridLines = False
    ws["A1"] = "{{titre}}"
    ws["A1"].font = Font(size=16, bold=True, color=ENCRE)
    ws["A2"] = "{{mission}} — {{date}}"
    ws["A2"].font = Font(color=DOUX)
    trait = Side(style="thin", color=TRAIT)
    ws["A4"] = "{{contenu}}"
    ws["A4"].font = Font(bold=True, color="FFFFFF")
    ws["A4"].fill = PatternFill("solid", fgColor="1F5F8B")
    ws["A4"].alignment = Alignment(vertical="top", wrap_text=True)
    ws["A4"].border = Border(left=trait, right=trait, top=trait, bottom=trait)
    ws["A5"].alignment = Alignment(vertical="top", wrap_text=True)
    ws["A5"].border = Border(left=trait, right=trait, top=trait, bottom=trait)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _capturer(cell):
    return {"font": copie.copy(cell.font), "fill": copie.copy(cell.fill), "border": copie.copy(cell.border),
            "alignment": copie.copy(cell.alignment)}


def _appliquer(cell, style):
    for k, v in style.items():
        setattr(cell, k, copie.copy(v))


def _nom_feuille(titre, pris):
    base = re.sub(r"[\[\]:*?/\\]", " ", titre).strip()[:31] or "Feuille"
    nom, n = base, 2
    while nom.lower() in pris:
        suffixe = f" ({n})"
        nom = base[:31 - len(suffixe)] + suffixe
        n += 1
    pris.add(nom.lower())
    return nom


def _xlsx(vue, diapos):
    wb = load_workbook(io.BytesIO(octets_modele(vue, "xlsx")))
    gabarit = wb.worksheets[0]
    marque = next((c for ligne in gabarit.iter_rows() for c in ligne
                   if isinstance(c.value, str) and "{{contenu}}" in c.value), None)
    trait = Side(style="thin", color=TRAIT)
    corps_defaut = {"alignment": Alignment(vertical="top", wrap_text=True),
                    "border": Border(left=trait, right=trait, top=trait, bottom=trait)}
    if marque is not None:
        r0, c0 = marque.row, marque.column
        entete = _capturer(marque)
        dessous = gabarit.cell(r0 + 1, c0)
        corps = _capturer(dessous) if dessous.has_style else corps_defaut
    else:
        r0 = gabarit.max_row + 2 if (gabarit.max_row > 1 or gabarit["A1"].value) else 1
        c0 = 1
        entete = {"font": Font(bold=True, color="FFFFFF"), "fill": PatternFill("solid", fgColor="1F5F8B"),
                  **corps_defaut}
        corps = corps_defaut
    couleur_barre = SERIE_1
    remplissage = entete.get("fill")
    if remplissage is not None and remplissage.fill_type == "solid" and remplissage.fgColor.type == "rgb":
        couleur_barre = remplissage.fgColor.rgb[-6:]
    styles = {"entete": entete, "corps": corps, "barre": couleur_barre}
    feuilles = [gabarit] + [wb.copy_worksheet(gabarit) for _ in diapos[1:]]
    pris = {f.title.lower() for f in wb.worksheets if f not in feuilles}
    for feuille, d in zip(feuilles, diapos):
        feuille.title = _nom_feuille(d["titre"], pris)
        jetons = _jetons(vue, d["titre"])
        for ligne in feuille.iter_rows():
            for c in ligne:
                if isinstance(c.value, str) and "{{" in c.value:
                    c.value = None if "{{contenu}}" in c.value else _remplacer(c.value, jetons)
        r = r0
        if d["sous"]:
            cell = feuille.cell(r, c0, d["sous"])
            cell.font = Font(italic=True, color=DOUX)
            r += 2
        for el in d["elements"]:
            r = _xlsx_element(feuille, el, r, c0, styles) + 1
    wb.active = wb.worksheets.index(gabarit)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _largeur(ws, col, valeurs, minimum=8, maximum=55):
    lettre = get_column_letter(col)
    longueur = max([len(seg) for v in valeurs for seg in _fmt(v).split("\n")] or [0])
    actuelle = ws.column_dimensions[lettre].width or 0
    ws.column_dimensions[lettre].width = max(actuelle, min(maximum, max(minimum, longueur + 2)))


def _xlsx_tableau(ws, entetes, lignes, r, c, styles, sty_cellules=None):
    sty_cellules = sty_cellules or {}
    for j, e in enumerate(entetes):
        _appliquer(ws.cell(r, c + j, _fmt(e)), styles["entete"])
    for i, ligne in enumerate(lignes):
        for j, v in enumerate(ligne):
            cell = ws.cell(r + 1 + i, c + j, v if isinstance(v, (int, float, dt.date)) else _fmt(v))
            _appliquer(cell, styles["corps"])
            sty = {**sty_cellules.get((i, None), {}), **sty_cellules.get((i, j), {})}
            if sty.get("fond"):
                cell.fill = PatternFill("solid", fgColor=sty["fond"])
            if sty.get("texte") or sty.get("gras"):
                cell.font = Font(bold=sty.get("gras", False), color=sty.get("texte") or ENCRE)
            if sty.get("centre"):
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for j in range(len(entetes)):
        _largeur(ws, c + j, [entetes[j]] + [l[j] for l in lignes])
    return r + 1 + len(lignes)


def _xlsx_element(ws, el, r, c, styles):
    genre = el["type"]
    if genre == "tableau":
        return _xlsx_tableau(ws, el["entetes"], el["lignes"], r, c, styles, el["styles"])
    if genre == "tuiles":
        return _xlsx_tableau(ws, ["Indicateur", "Valeur", "Précision"], [list(t) for t in el["tuiles"]], r, c, styles)
    if genre == "texte":
        for i, p in enumerate(el["paragraphes"]):
            ws.cell(r + i, c, p).alignment = Alignment(wrap_text=False)
        return r + len(el["paragraphes"])
    if genre == "colonnes":
        cols = el["colonnes"]
        n = max(len(col["items"]) for col in cols)
        lignes, sty = [], {}
        for i in range(n):
            ligne = []
            for j, col in enumerate(cols):
                if i >= len(col["items"]):
                    ligne.append("")
                    continue
                texte_, precision, g = col["items"][i]
                ligne.append(texte_.upper() if g == "groupe" else texte_ + (f"\n{precision}" if precision else ""))
                if g == "groupe":
                    sty[(i, j)] = {"gras": True, "texte": DOUX}
                elif g == "adherence":
                    sty[(i, j)] = {"fond": "FDF0DC", "texte": ENCRE}
                elif g == "prerequis":
                    sty[(i, j)] = {"texte": ENCRE, "fond": "F7F8FA"}
        entetes = [col["titre"] + (f"\n{col['sous']}" if col.get("sous") else "") for col in cols]
        return _xlsx_tableau(ws, entetes, lignes, r, c, styles, sty)
    if genre == "gantt":
        mois = el["mois"]
        entetes = ["Piste", "Activité", "Début", "Fin"] + [f"{MOIS_COURTS[m.month - 1]} {str(m.year)[2:]}" for m in mois]
        lignes = [["Jalons", l, d, None] + ["" for _ in mois] for l, d, _ in el["jalons"]]
        for piste, activites in el["pistes"]:
            lignes += [[piste, l, da, fa] + ["" for _ in mois] for l, da, fa in activites]
        fin_ligne = _xlsx_tableau(ws, entetes, lignes, r, c, styles)
        for i, ligne in enumerate(lignes):
            for k in (2, 3):
                ws.cell(r + 1 + i, c + k).number_format = "dd/mm/yyyy"
            da, fa = ligne[2], ligne[3] or ligne[2]
            for k, m in enumerate(mois):
                suivant = mois[k + 1] if k + 1 < len(mois) else el["fin"]
                if da < suivant and fa >= m:
                    cell = ws.cell(r + 1 + i, c + 4 + k)
                    if ligne[3] is None:
                        cell.value = "◆"
                        cell.alignment = Alignment(horizontal="center")
                    else:
                        couleur = GRIS_PASSE if fa < el["aujourdhui"] else styles["barre"]
                        cell.fill = PatternFill("solid", fgColor=couleur)
        for k in range(len(mois)):
            ws.column_dimensions[get_column_letter(c + 4 + k)].width = 8
        return fin_ligne
    if genre == "graphe":
        series = el["series"]
        lignes = [[cat] + [s[1][i] for s in series] for i, cat in enumerate(el["categories"])]
        ws.cell(r, c, el["titre"]).font = Font(bold=True)
        fin_ligne = _xlsx_tableau(ws, ["Sprint"] + [s[0] for s in series], lignes, r + 1, c, styles)
        graphique = LineChart() if el["genre"] == "ligne" else BarChart()
        graphique.title = el["titre"]
        graphique.height, graphique.width = 7.5, 16
        graphique.add_data(Reference(ws, min_col=c + 1, max_col=c + len(series), min_row=r + 1,
                                     max_row=r + 1 + len(lignes)), titles_from_data=True)
        graphique.set_categories(Reference(ws, min_col=c, min_row=r + 2, max_row=r + 1 + len(lignes)))
        graphique.x_axis.delete = False
        graphique.y_axis.delete = False
        if el.get("max"):
            graphique.y_axis.scaling.min, graphique.y_axis.scaling.max = 0, el["max"]
        if el["genre"] == "barre":
            graphique.gapWidth = 60
            if el.get("superposer"):
                graphique.overlap = 100
        for serie, (nom, _, couleur) in zip(graphique.series, series):
            if el["genre"] == "ligne":
                serie.smooth = False
                serie.graphicalProperties.line.solidFill = couleur
                serie.graphicalProperties.line.width = 28575
                if nom in el["pointilles"]:
                    serie.graphicalProperties.line.dashStyle = "dash"
                    serie.marker.symbol = "none"
                else:
                    serie.marker.symbol = "circle"
                    serie.marker.size = 6
                    serie.marker.graphicalProperties.solidFill = couleur
                    serie.marker.graphicalProperties.line.solidFill = couleur
            else:
                serie.graphicalProperties.solidFill = couleur
                serie.graphicalProperties.line.solidFill = couleur
        ws.add_chart(graphique, f"{get_column_letter(c + len(series) + 2)}{r}")
        return max(fin_ligne, r + 16)
    return r
