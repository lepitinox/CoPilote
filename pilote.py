"""Ce dont le pilote a besoin au quotidien : quoi traiter, où en est-on, que dire en séance.

Calculs déterministes, sans LLM, à partir des données de la mission courante :
- glissements : écart entre la date d'un jalon ou d'un lot et sa date de référence (engagement),
  nombre de reports tiré de l'historique ;
- reponses : délai, budget, client — les trois questions d'un sponsor, chacune avec un état ;
- a_traiter : la liste d'actions du pilote, classée par urgence, avec l'action directe possible ;
- preparer_seance : ordre du jour minuté d'une instance, à partir des décisions, actions,
  risques, jalons et attentes qui la concernent.
"""
import datetime as dt

import agenda
import calculs
import db
import donnees
import meteo

SEUIL_GLISSEMENT = 14       # jours : au-delà, un report est signalé
SEUIL_GLISSEMENT_FORT = 30  # jours
ANCIENNETE_DECISION = 14    # jours sans échéance avant de signaler une décision qui traîne
ETAT_LIBELLE = {"vert": "vert", "orange": "orange", "rouge": "rouge", "inconnu": "non mesurable"}
MOTS_COMITE = ("comité", "comite", "copil", "sponsor", "steerco", "pilotage")


def _d(v):
    return calculs.date(v)


def _ecart(date, reference):
    a, b = _d(date), _d(reference)
    return (a - b).days if a and b else None


# ---------------------------------------------------------------- glissements

def glissements(aujourdhui=None):
    """Jalons et lots avec leur écart à la date de référence et leur nombre de reports."""
    auj = aujourdhui or dt.date.today()

    def reports(table):
        n = {}
        for e in db.journal(table, limite=1000):
            if e["action"] == "modification" and (e["avant"] or {}).get("date") != (e["apres"] or {}).get("date"):
                n[e["ligne"]] = n.get(e["ligne"], 0) + 1
        return n

    out = {}
    for table in ("jalon", "lot"):
        n = reports(table)
        lignes = []
        for x in db.lister(table):
            ecart = _ecart(x.get("date"), x.get("date_initiale"))
            atteint = x.get("statut") in ("atteint", "livré")
            depasse = not atteint and bool(_d(x.get("date"))) and _d(x["date"]) < auj
            lignes.append({**x, "glissement_jours": ecart, "reports": n.get(x["id"], 0), "depasse": depasse})
        out[table] = lignes
    return out


def alertes_glissements(g, mission, aujourdhui=None):
    cible = _d(mission.get("date_cible"))
    out = []
    for j in g["jalon"]:
        if j.get("statut") == "atteint":
            continue
        e = j["glissement_jours"]
        if j["depasse"]:
            out.append({"code": "jalon_depasse", "niveau": 2, "titre": f"Jalon dépassé non atteint : {j['libelle']}",
                        "detail": f"Prévu le {calculs.fr(j['date'])}, statut « {j.get('statut') or 'à venir'} » : "
                                  "le marquer atteint ou fixer une nouvelle date."})
        elif e is not None and e > SEUIL_GLISSEMENT:
            fort = e > SEUIL_GLISSEMENT_FORT and cible and _d(j["date"]) > cible
            out.append({"code": "glissement", "niveau": 3 if fort else 2,
                        "titre": f"Jalon reporté de {semaines(e)} : {j['libelle']}",
                        "detail": f"Engagé au {calculs.fr(j['date_initiale'])}, prévu désormais le {calculs.fr(j['date'])}"
                                  + (f" ({j['reports']} report(s))" if j["reports"] else "")
                                  + (" : au-delà de la date cible." if fort else ".")})
    return out


def semaines(jours):
    if jours is None:
        return "—"
    if abs(jours) < 14:
        return f"{jours} j"
    return f"{round(jours / 7)} semaines"


# ---------------------------------------------------------------- trois réponses

def reponses(aujourdhui=None):
    """Délai, budget, client : un état (vert, orange, rouge, inconnu), une phrase et le détail."""
    auj = aujourdhui or dt.date.today()
    m = db.mission()
    g = glissements(auj)
    att = calculs.atterrissage(db.lister("sprint"), m)
    cible = _d(m.get("date_cible"))
    non_atteints = [j for j in g["jalon"] if j.get("statut") != "atteint" and _d(j.get("date"))]
    retard_max = max([j["glissement_jours"] or 0 for j in non_atteints] or [0])
    depasses = [j for j in non_atteints if j["depasse"]]
    fin_jalons = max([_d(j["date"]) for j in non_atteints] or [None], key=lambda d: d or dt.date.min)

    # Délai
    if att:
        if not att["atteignable"]:
            delai = ("rouge", "Aucune date de fin réaliste : le reste à faire ne diminue plus assez.")
        elif att["ecart_sprints"]:
            delai = ("rouge" if att["ecart_sprints"] > 2 else "orange",
                     f"Fin estimée le {calculs.fr(att['date_fin_estimee'])}, {att['ecart_sprints']} sprint(s) après la cible.")
        else:
            delai = ("vert", f"Fin estimée le {calculs.fr(att['date_fin_estimee'])}, dans la cible.")
    elif non_atteints:
        if cible and fin_jalons and fin_jalons > cible:
            delai = ("rouge", f"Dernier jalon prévu le {calculs.fr(fin_jalons)}, après la date cible du {calculs.fr(cible)}.")
        elif retard_max > SEUIL_GLISSEMENT or depasses:
            delai = ("orange", f"Jalons reportés jusqu'à {semaines(retard_max)}" if retard_max > SEUIL_GLISSEMENT
                     else f"{len(depasses)} jalon(s) dépassé(s) non atteint(s).")
        else:
            delai = ("vert", "Jalons tenus par rapport aux dates de référence.")
    else:
        delai = ("inconnu", "Ni sprint ni jalon daté : le délai n'est pas mesurable.")
    details_delai = [f"{j['libelle']} : {calculs.fr(j['date'])}"
                     + (f" (+{semaines(j['glissement_jours'])} vs engagement)" if (j["glissement_jours"] or 0) > 0 else "")
                     for j in sorted(non_atteints, key=lambda j: j["date"])[:4]]

    # Budget
    b = donnees.budget(auj)
    if not b["reference"]:
        budget_ = ("inconnu", "Aucun budget vendu ni chiffrage retenu.")
    elif b["ecart"] is not None and b["ecart"] < 0:
        part = -b["ecart"] / b["reference"]
        budget_ = ("rouge" if part > 0.05 else "orange",
                   f"Atterrissage {finances_euros(b['atterrissage'])} : dépassement de {finances_euros(-b['ecart'])} ({round(part * 100)} %).")
    elif any(a["code"] == "consommation" for a in b["alertes"]):
        budget_ = ("orange", "Dans l'enveloppe, mais la consommation est en avance sur l'avancement.")
    else:
        budget_ = ("vert", f"Atterrissage {finances_euros(b['atterrissage'])}, dans l'enveloppe de {finances_euros(b['reference'])}.")
    details_budget = [f"Consommé {finances_euros(b['consomme'])} ({round((b['taux_consomme'] or 0) * 100)} %)",
                      f"Reste à faire {finances_euros(b['raf'])}"] + (
        [f"{b['factures_en_retard']} facture(s) en retard"] if b["factures_en_retard"] else [])

    # Client
    a = donnees.suivi_attentes(auj)["attentes"]
    notes = [x["satisfaction"] for x in a if isinstance(x.get("satisfaction"), int)]
    prio = [x for x in a if x.get("priorite") == 1 and isinstance(x.get("satisfaction"), int) and x["satisfaction"] <= 2]
    recadrer = [x for x in a if x.get("position") == "à recadrer"]
    if not a:
        client = ("inconnu", "Aucune attente du client suivie.")
    elif prio:
        client = ("rouge", f"Attente prioritaire insatisfaite : {prio[0].get('libelle')} ({prio[0].get('partie_prenante')}).")
    elif recadrer or (notes and sum(notes) / len(notes) < 3.5):
        client = ("orange", f"{len(recadrer)} attente(s) à recadrer"
                  + (f", satisfaction moyenne {_note(notes)} / 5." if notes else "."))
    else:
        client = ("vert", f"Satisfaction moyenne {_note(notes)} / 5, rien à recadrer." if notes
                  else "Attentes alignées.")
    details_client = [f"{x.get('partie_prenante')} : {x.get('libelle')} ({x.get('position')})" for x in (prio + recadrer)[:4]]

    return {"delai": {"etat": delai[0], "phrase": delai[1], "details": details_delai},
            "budget": {"etat": budget_[0], "phrase": budget_[1], "details": details_budget},
            "client": {"etat": client[0], "phrase": client[1], "details": details_client}}


def _note(notes):
    return f"{sum(notes) / len(notes):.1f}".replace(".", ",")


def finances_euros(v):
    import finances
    return finances.euros(v)


def decisions_en_attente(aujourdhui=None):
    auj = aujourdhui or dt.date.today()
    out = []
    for d in db.lister("decision"):
        if d.get("nature") != "decision" or d.get("statut") != "à prendre":
            continue
        age = (auj - _d(d["cree_le"])).days if _d(d.get("cree_le")) else None
        retard = bool(_d(d.get("echeance"))) and _d(d["echeance"]) < auj
        out.append({**d, "age_jours": age, "en_retard": retard})
    return sorted(out, key=lambda d: (not d["en_retard"], d.get("echeance") or "9999"))


def historique_tendance(limite=8):
    """Tendance des dernières météos, la plus ancienne d'abord."""
    m = [{"semaine": x.get("semaine"), "date": x.get("cree_le"), "tendance": x.get("tendance")}
         for x in db.lister("meteo") if x.get("tendance")]
    return list(reversed(m[:limite]))


# ---------------------------------------------------------------- à traiter

def _item(groupe, genre, titre, detail="", table=None, ident=None, vue=None, actions=()):
    return {"groupe": groupe, "genre": genre, "titre": titre, "detail": detail,
            "table": table, "id": ident, "vue": vue, "actions": list(actions)}


def a_traiter(aujourdhui=None):
    """Ce que le pilote doit faire : maintenant (retards, critiques), cette semaine, à surveiller."""
    auj = aujourdhui or dt.date.today()
    j7, iso = auj + dt.timedelta(days=7), auj.isoformat()
    m = db.mission()
    items = []

    for d in db.lister("decision"):
        ech = _d(d.get("echeance"))
        if d.get("nature") == "action" and d.get("statut") == "à faire":
            faite = {"libelle": "Marquer faite", "table": "decision", "id": d["id"], "champs": {"statut": "faite"}}
            if ech and ech < auj:
                items.append(_item("maintenant", "action", f"Action en retard : {d['titre']}",
                                   f"Échéance {calculs.fr(ech)} · {d.get('porteur') or 'sans porteur'}", "decision", d["id"],
                                   actions=[faite]))
            elif ech and ech <= j7:
                items.append(_item("semaine", "action", f"Action à échéance : {d['titre']}",
                                   f"{calculs.fr(ech)} · {d.get('porteur') or 'sans porteur'}", "decision", d["id"], actions=[faite]))
        elif d.get("nature") == "decision" and d.get("statut") == "à prendre":
            prise = {"libelle": "Marquer prise", "table": "decision", "id": d["id"], "champs": {"statut": "prise"}}
            age = (auj - _d(d["cree_le"])).days if _d(d.get("cree_le")) else None
            qui = d.get("porteur") or "décideur non désigné"
            if ech and ech < auj:
                items.append(_item("maintenant", "decision", f"Décision en retard : {d['titre']}",
                                   f"Attendue le {calculs.fr(ech)} · {qui}", "decision", d["id"], actions=[prise]))
            elif ech and ech <= j7:
                items.append(_item("semaine", "decision", f"Décision à obtenir : {d['titre']}",
                                   f"Avant le {calculs.fr(ech)} · {qui}", "decision", d["id"], actions=[prise]))
            elif not ech and age is not None and age > ANCIENNETE_DECISION:
                items.append(_item("surveiller", "decision", f"Décision en attente depuis {age} jours : {d['titre']}",
                                   f"Sans échéance · {qui}", "decision", d["id"], actions=[prise]))

    for r in db.lister("risque"):
        if r.get("etat") == "clos":
            continue
        crit = (r.get("probabilite") or 0) * (r.get("impact") or 0)
        manque = [x for x, ok in (("porteur", r.get("porteur")), ("plan d'action", (r.get("plan_action") or "").strip())) if not ok]
        ech = _d(r.get("echeance"))
        if crit >= 6 and manque:
            items.append(_item("maintenant", "risque", f"Risque critique sans {' ni '.join(manque)} : {r['titre']}",
                               f"Criticité {crit} / 9", "risque", r["id"]))
        elif ech and ech < auj:
            items.append(_item("maintenant", "risque", f"Échéance de traitement dépassée : {r['titre']}",
                               f"Prévue le {calculs.fr(ech)} · {r.get('porteur') or 'sans porteur'}", "risque", r["id"]))

    for j in glissements(auj)["jalon"]:
        if j.get("statut") == "atteint" or not _d(j.get("date")):
            continue
        if j["depasse"]:
            items.append(_item("maintenant", "jalon", f"Jalon dépassé : {j['libelle']}",
                               f"Prévu le {calculs.fr(j['date'])} : atteint, ou nouvelle date ?", "jalon", j["id"],
                               actions=[{"libelle": "Marquer atteint", "table": "jalon", "id": j["id"], "champs": {"statut": "atteint"}}]))
        elif _d(j["date"]) <= auj + dt.timedelta(days=14):
            items.append(_item("semaine", "jalon", f"Jalon dans les deux semaines : {j['libelle']}",
                               calculs.fr(j["date"]) + (f" · reporté de {semaines(j['glissement_jours'])}"
                                                        if (j["glissement_jours"] or 0) > 0 else ""), "jalon", j["id"]))

    for f in db.lister("facture"):
        if (f.get("statut") or "à facturer") != "à facturer" or not _d(f.get("date_prevue")):
            continue
        facturer = {"libelle": "Marquer facturée", "table": "facture", "id": f["id"], "champs": {"statut": "facturée"}}
        montant = finances_euros(f.get("montant"))
        if _d(f["date_prevue"]) <= auj:
            items.append(_item("maintenant", "facture", f"Facture à émettre : {f['libelle']}",
                               f"{montant} prévus le {calculs.fr(f['date_prevue'])}", "facture", f["id"], actions=[facturer]))
        elif _d(f["date_prevue"]) <= j7:
            items.append(_item("semaine", "facture", f"Facture à préparer : {f['libelle']}",
                               f"{montant} le {calculs.fr(f['date_prevue'])}", "facture", f["id"], actions=[facturer]))

    for a in donnees.suivi_attentes(auj)["attentes"]:
        titre = f"{a.get('partie_prenante') or 'Client'} : {a.get('libelle')}"
        revue = {"libelle": "Revue faite aujourd'hui", "table": "attente", "id": a["id"], "champs": {"revue_le": iso}}
        if a.get("position") == "à recadrer" and not (a.get("prochaine_action") or "").strip():
            items.append(_item("maintenant", "attente", "Attente à recadrer sans action : " + titre,
                               "Définir le message et la prochaine action", "attente", a["id"]))
        elif a.get("priorite") == 1 and isinstance(a.get("satisfaction"), int) and a["satisfaction"] <= 2:
            items.append(_item("maintenant", "attente", "Attente prioritaire insatisfaite : " + titre,
                               f"Satisfaction {a['satisfaction']} / 5", "attente", a["id"]))
        elif a.get("revue_due") and a.get("position") != "hors périmètre":
            items.append(_item("surveiller", "attente", "Attente à revoir avec le client : " + titre,
                               f"Dernière revue : {calculs.fr(a.get('revue_le'))}", "attente", a["id"], actions=[revue]))

    en_attente = db.lister("proposition", "statut = 'en attente'")
    if en_attente:
        items.append(_item("semaine", "compte_rendu", f"{len(en_attente)} proposition(s) extraite(s) des comptes rendus à valider",
                           "Rien n'entre au registre sans votre validation", vue="cr"))

    sprints = db.lister("sprint")
    duree = m.get("duree_sprint_jours") or 14
    if sprints and _d(sprints[-1].get("date_fin")):
        prochain = _d(sprints[-1]["date_fin"]) + dt.timedelta(days=duree)
        if prochain < auj:
            items.append(_item("maintenant", "sprint", f"Sprint {(sprints[-1].get('numero') or 0) + 1} terminé le {calculs.fr(prochain)} : à saisir",
                               "Les indicateurs et l'atterrissage en dépendent", vue="sprints"))

    if not any(x.get("semaine") == meteo.semaine(auj) for x in db.lister("meteo")):
        items.append(_item("semaine", "meteo", "Météo de la semaine pas encore générée", meteo.semaine(auj), vue="meteo"))

    duree_sprint = m.get("duree_sprint_jours") or 14
    for i in db.lister("instance"):
        for d in agenda.occurrences(i, auj, auj + dt.timedelta(days=6), duree_sprint):
            if (i.get("recurrence") or "") == "quotidienne":
                continue  # la mêlée quotidienne ne se prépare pas
            items.append(_item("semaine", "reunion", f"{i['nom']} le {calculs.fr(d)} à {i.get('heure')}",
                               "Préparer l'ordre du jour", "instance", i["id"],
                               actions=[{"libelle": "Préparer", "seance": i["id"]}]))
            break

    ordre = {"maintenant": 0, "semaine": 1, "surveiller": 2}
    items.sort(key=lambda x: ordre[x["groupe"]])
    return {"date": iso, "items": items,
            "compte": {g: sum(1 for x in items if x["groupe"] == g) for g in ordre}}


# ---------------------------------------------------------------- préparer une séance

def _contient(a, b):
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    return bool(a and b) and (a in b or b in a)


CEREMONIES = {  # mot du nom -> type de rituel agile
    "planification": "planification", "planning": "planification", "affinage": "affinage",
    "refinement": "affinage", "démonstration": "demonstration", "demonstration": "demonstration",
    "démo": "demonstration", "review": "demonstration", "rétrospective": "retrospective",
    "retrospective": "retrospective", "rétro": "retrospective", "mêlée": "melee", "daily": "melee",
}
# Minutes par élément abordé, et durée fixe des points sans liste.
MINUTES_PAR_ELEMENT = {"decisions": 5, "risques": 3, "attentes": 3, "actions": 2, "jalons": 1}
MINUTES_FIXES = {"trajectoire": 10, "budget": 5, "sprint": 10, "capacite": 10}
# Le temps restant de la séance, selon son type.
TEMPS_LIBRE = {"planification": "Engagement du sprint : sélection et découpage des stories",
               "affinage": "Affinage et estimation des stories",
               "demonstration": "Démonstration des incréments et retours",
               "retrospective": "Ce qui a marché, ce qui est à améliorer, actions d'amélioration"}


def type_seance(inst):
    nom = (inst.get("nom") or "").lower()
    if any(k in nom for k in MOTS_COMITE):
        return "comite"
    for mot, genre in CEREMONIES.items():
        if mot in nom:
            return genre
    if (inst.get("recurrence") or "") == "quotidienne":
        return "melee"
    return "operationnel"


LIBELLES_TYPE = {"comite": "Comité de pilotage", "operationnel": "Point de suivi", "planification": "Planification de sprint",
                 "affinage": "Affinage du backlog", "demonstration": "Démonstration", "retrospective": "Rétrospective",
                 "melee": "Mêlée quotidienne"}


def preparer_seance(ident, aujourdhui=None):
    """Ordre du jour minuté d'une instance : le contenu dépend du type de séance."""
    auj = aujourdhui or dt.date.today()
    inst = db.lire("instance", ident)
    if not inst:
        raise ValueError("Instance introuvable.")
    m = db.mission()
    genre = type_seance(inst)
    duree_sprint = m.get("duree_sprint_jours") or 14
    prochaines = agenda.occurrences(inst, auj, auj + dt.timedelta(days=400), duree_sprint)
    acteurs = {a["id"]: a for a in db.lister("acteur")}
    personnes = [acteurs[i]["nom"] for i in db.ids(inst.get("participants_ids")) if i in acteurs]

    def concerne(nom):
        return any(_contient(nom, p) for p in personnes) or _contient(nom, inst.get("participants"))

    rattache = lambda d: _contient(d.get("instance"), inst["nom"])
    g = glissements(auj)
    jalons_proches = [j for j in g["jalon"] if j.get("statut") != "atteint" and _d(j.get("date"))
                      and (_d(j["date"]) <= auj + dt.timedelta(days=45) or (j["glissement_jours"] or 0) > SEUIL_GLISSEMENT)]
    fmt_jalon = lambda j: (f"{j['libelle']} : {calculs.fr(j['date'])}"
                           + (f" — reporté de {semaines(j['glissement_jours'])}" if (j['glissement_jours'] or 0) > 0 else "")
                           + (" — dépassé" if j["depasse"] else ""))
    risques = [r for r in donnees.suivi_risques(auj)["risques"] if r.get("etat") != "clos"]
    fmt_risque = lambda r: (f"{r['titre']} — criticité {r.get('criticite') or '?'} / 9, {r.get('evolution_session') or 'stable'}"
                            + (f", porteur {r['porteur']}" if r.get("porteur") else ", sans porteur"))
    attentes = donnees.suivi_attentes(auj)["attentes"]
    a_traiter_ = lambda a: a.get("position") == "à recadrer" or (isinstance(a.get("satisfaction"), int) and a["satisfaction"] <= 2)
    fmt_attente = lambda a: (f"{a.get('partie_prenante')} : {a.get('libelle')} — {a.get('position')}, satisfaction "
                             f"{a.get('satisfaction') or '?'} / 5" + (f". Notre message : {a['reponse']}" if a.get("reponse") else ""))
    decisions_ = decisions_en_attente(auj)
    fmt_decision = lambda d: (f"{d['titre']} — décideur {d.get('porteur') or 'à désigner'}"
                              + (f", attendue le {calculs.fr(d['echeance'])}" if d.get("echeance") else "")
                              + (" (en retard)" if d["en_retard"] else "")
                              + ("" if d.get("instance") else " (non rattachée à une instance)"))
    actions = [d for d in db.lister("decision") if d.get("nature") == "action" and d.get("statut") == "à faire"]
    fmt_action = lambda d: (f"{d['titre']} — {d.get('porteur') or 'sans porteur'}, échéance {calculs.fr(d.get('echeance'))}"
                            + (" (en retard)" if _d(d.get("echeance")) and _d(d["echeance"]) < auj else ""))
    sprints = db.lister("sprint")
    dernier = sprints[-1] if sprints else None
    k = calculs.kpi(sprints)

    points = []  # (clé, titre, contenu)
    if genre == "comite":
        rep = reponses(auj)
        points.append(("trajectoire", "Trajectoire : délai, budget, client",
                       [f"{t} — {ETAT_LIBELLE[rep[c]['etat']]} : {rep[c]['phrase']}" for c, t in (("delai", "Délai"), ("budget", "Budget"), ("client", "Client"))]))
        points.append(("jalons", "Jalons à venir et reports", [fmt_jalon(j) for j in jalons_proches]))
        points.append(("risques", "Risques critiques ou en hausse", [fmt_risque(r) for r in risques
                       if (r.get("criticite") or 0) >= 6 or r.get("evolution_session") in ("hausse", "nouveau")]))
        points.append(("attentes", "Attentes du client à traiter", [fmt_attente(a) for a in attentes if a_traiter_(a)]))
        points.append(("decisions", "Décisions à obtenir", [fmt_decision(d) for d in decisions_ if rattache(d) or not d.get("instance")]))
        b = donnees.budget(auj)
        if b["reference"]:
            points.append(("budget", "Budget", [rep["budget"]["phrase"]] + rep["budget"]["details"]))
    elif genre == "operationnel":
        points.append(("actions", "Suivi des actions", [fmt_action(d) for d in actions if rattache(d) or concerne(d.get("porteur"))]
                       or [fmt_action(d) for d in actions if _d(d.get("echeance")) and _d(d["echeance"]) < auj]))
        points.append(("risques", "Risques et adhérences", [fmt_risque(r) for r in risques
                       if concerne(r.get("porteur")) or r.get("nature") == "adherence" or r.get("evolution_session") in ("hausse", "nouveau")]))
        points.append(("jalons", "Jalons des six prochaines semaines", [fmt_jalon(j) for j in jalons_proches]))
        points.append(("attentes", "Attentes des participants", [fmt_attente(a) for a in attentes if concerne(a.get("partie_prenante")) and a_traiter_(a)]))
        points.append(("decisions", "Décisions à préparer", [fmt_decision(d) for d in decisions_ if rattache(d)]))
    elif genre == "planification":
        if dernier:
            points.append(("capacite", "Capacité et reste à faire", [
                f"Sprint {dernier.get('numero')} : {dernier.get('realise') or 0:g} points réalisés sur {dernier.get('prevu') or 0:g} prévus",
                f"Vélocité moyenne : {k['velocite_moyenne']:g} points" if k and k.get("velocite_moyenne") is not None else "",
                f"Reste à faire : {dernier.get('reste') or 0:g} points"]))
        points.append(("jalons", "Jalons à préparer dans ce sprint", [fmt_jalon(j) for j in jalons_proches]))
    elif genre == "affinage":
        points.append(("attentes", "Demandes de périmètre à instruire", [fmt_attente(a) for a in attentes if a.get("categorie") == "périmètre"]))
        points.append(("jalons", "Jalons qui conditionnent la priorisation", [fmt_jalon(j) for j in jalons_proches]))
    elif genre == "demonstration":
        points.append(("jalons", "Où en est-on des jalons", [fmt_jalon(j) for j in jalons_proches]))
        points.append(("attentes", "Attentes des participants à vérifier pendant la démonstration",
                       [fmt_attente(a) for a in attentes if concerne(a.get("partie_prenante")) or a.get("categorie") in ("périmètre", "qualité")]))
    elif genre == "retrospective" and dernier:
        points.append(("sprint", "Chiffres du sprint", [
            f"Réalisé / prévu : {dernier.get('realise') or 0:g} / {dernier.get('prevu') or 0:g} points",
            f"Moral : {dernier['moral']} / 5" if dernier.get("moral") else "",
            f"Anomalies : {dernier.get('anomalies_creees') or 0} créées, {dernier.get('anomalies_corrigees') or 0} corrigées"]))
    points = [(c, t, [x for x in contenu if x]) for c, t, contenu in points]
    points = [p for p in points if p[2]]

    # Minutage : ouverture et clôture fixes, chaque point selon ce qu'il contient, plafonné à la
    # durée de la séance ; le temps restant va aux échanges plutôt que d'allonger artificiellement.
    total = inst.get("duree_min") or agenda.minutes(inst.get("duree"))
    pas = 5 if total >= 30 else 1
    bornes = (5 if total >= 30 else 2) if genre != "melee" else 0
    dispo = max(0, total - 2 * bornes)
    voulu = {c: MINUTES_FIXES.get(c) or max(pas, MINUTES_PAR_ELEMENT.get(c, 2) * len(contenu)) for c, _, contenu in points}
    if sum(voulu.values()) > dispo and voulu:
        f = dispo / sum(voulu.values())
        voulu = {c: max(pas, int(v * f / pas) * pas) for c, v in voulu.items()}
        while sum(voulu.values()) > dispo and any(v > pas for v in voulu.values()):
            voulu[max(voulu, key=voulu.get)] -= pas
    else:
        voulu = {c: -(-v // pas) * pas for c, v in voulu.items()}  # arrondi au pas supérieur
    libre = total - 2 * bornes - sum(voulu.values())
    objectifs = [o for o in (inst.get("objectifs") or "").split("\n") if o.strip()]
    ordre_du_jour = [{"cle": "ouverture", "titre": "Objectifs de la séance", "minutes": bornes, "contenu": objectifs}] if bornes else []
    ordre_du_jour += [{"cle": c, "titre": t, "minutes": voulu[c], "contenu": contenu} for c, t, contenu in points]
    if libre >= pas and genre != "melee":
        ordre_du_jour.append({"cle": "echanges", "titre": TEMPS_LIBRE.get(genre, "Échanges et points divers"),
                              "minutes": libre, "contenu": []})
    if bornes:
        ordre_du_jour.append({"cle": "cloture", "titre": "Relevé de décisions et prochaines étapes", "minutes": bornes, "contenu": []})

    rep = reponses(auj) if genre == "comite" else None
    return {"instance": {k_: inst.get(k_) for k_ in ("id", "nom", "chantier", "heure", "duree_min", "frequence")},
            "type": genre, "type_libelle": LIBELLES_TYPE[genre],
            "date": prochaines[0].isoformat() if prochaines else None, "participants": personnes,
            "autres_participants": inst.get("participants") or "", "duree": total,
            "depassement_minutes": max(0, sum(p["minutes"] for p in ordre_du_jour) - total),
            "ordre_du_jour": ordre_du_jour,
            "messages_cles": [rep[c]["phrase"] for c in ("delai", "budget", "client") if rep[c]["etat"] != "inconnu"] if rep else []}
