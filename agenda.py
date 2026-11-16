"""Réunions de la gouvernance : créneaux proposés, calendrier type d'un sprint, invitations.

Le co-pilote propose un créneau pour chaque instance à partir du rythme des sprints, en
évitant les chevauchements et la pause de midi. Le pilote ajuste, puis télécharge un
fichier .ics à importer dans son agenda pour envoyer les invitations.
"""
import datetime as dt
import re

import calculs
import db

RECURRENCES = {
    "quotidienne": "Chaque jour ouvré",
    "hebdomadaire": "Chaque semaine",
    "debut_sprint": "À chaque début de sprint",
    "fin_sprint": "À chaque fin de sprint",
    "deux_sprints": "Tous les deux sprints, en fin de sprint",
    "mensuelle": "Chaque mois",
    "ponctuelle": "Ponctuelle ou à la demande",
}
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
ICAL = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
PLAGE = (9 * 60, 18 * 60)
PAUSE = (12 * 60, 13 * 60 + 30)
HORIZON_JOURS = 56  # contrôle des chevauchements sur huit semaines


def deviner_recurrence(frequence):
    f = (frequence or "").lower()
    for motif, code in ((r"quotid|chaque jour", "quotidienne"),
                        (r"deux sprints|2 sprints", "deux_sprints"),
                        (r"d[ée]but de sprint", "debut_sprint"), (r"fin de sprint", "fin_sprint"),
                        (r"mensu|mois", "mensuelle"), (r"hebdo|semaine", "hebdomadaire")):
        if re.search(motif, f):
            return code
    return "ponctuelle"


def minutes(duree, defaut=60):
    """'1 h 30' -> 90 ; '15 min' -> 15 ; '2 × 1 h' -> 60 ; '30 min à 1 h' -> 60."""
    t = (duree or "").lower().replace(",", ".")
    t = re.split(r"\bà\b", t)[-1]                 # fourchette : borne haute
    t = re.sub(r"^\s*\d+\s*[×x]\s*", "", t)       # « 2 × 1 h » : durée d'une séance
    h = re.search(r"(\d+(?:\.\d+)?)\s*h\s*(\d+)?", t)
    if h:
        return int(float(h.group(1)) * 60 + int(h.group(2) or 0))
    m = re.search(r"(\d+)\s*min", t)
    return int(m.group(1)) if m else defaut


def hm(texte):
    try:
        h, m = (texte or "").split(":")[:2]
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def en_heure(minutes_):
    return f"{minutes_ // 60:02d}:{minutes_ % 60:02d}"


def _jour_ouvre(d, sens=1):
    while d.weekday() >= 5:
        d += dt.timedelta(days=sens)
    return d


def sprint_de_reference(mission, sprints, aujourdhui):
    """Premier jour du sprint en cours ou à venir, et dernier jour ouvré de ce sprint."""
    duree = int(mission.get("duree_sprint_jours") or 14)
    fins = [f for f in (calculs.date(s.get("date_fin")) for s in sprints) if f]
    debut = _jour_ouvre(max(fins) + dt.timedelta(days=1)) if fins else _jour_ouvre(aujourdhui)
    while debut < aujourdhui:
        debut = _jour_ouvre(debut + dt.timedelta(days=duree))
    fin = _jour_ouvre(debut + dt.timedelta(days=duree - 1), -1)
    return debut, fin, duree


def occurrences(inst, debut, fin, duree_sprint):
    """Dates des séances d'une instance entre deux dates incluses."""
    p = calculs.date(inst.get("premiere"))
    if not p or hm(inst.get("heure")) is None:
        return []
    code, out = inst.get("recurrence"), []
    if code == "ponctuelle":
        return [p] if debut <= p <= fin else []
    if code == "mensuelle":
        rang, jour = (p.day - 1) // 7, p.weekday()
        a, m = p.year, p.month
        while dt.date(a, m, 1) <= fin:
            premier = dt.date(a, m, 1)
            d = premier + dt.timedelta(days=(jour - premier.weekday()) % 7 + 7 * rang)
            if d.month == m and p <= d and debut <= d <= fin:
                out.append(d)
            a, m = (a + 1, 1) if m == 12 else (a, m + 1)
        return out
    pas = {"quotidienne": 1, "hebdomadaire": 7, "debut_sprint": duree_sprint,
           "fin_sprint": duree_sprint, "deux_sprints": 2 * duree_sprint}.get(code, 7)
    d = p
    while d <= fin:
        if d >= debut and (code != "quotidienne" or d.weekday() < 5):
            out.append(d)
        d += dt.timedelta(days=pas)
    return out


def _conflit(candidat, placees, horizon, duree_sprint):
    a = hm(candidat["heure"])
    b = a + (candidat.get("duree_min") or 60)
    jours = set(occurrences(candidat, *horizon, duree_sprint))
    for autre in placees:
        x = hm(autre.get("heure"))
        y = x + (autre.get("duree_min") or 60) if x is not None else None
        if x is not None and a < y and x < b and jours & set(occurrences(autre, *horizon, duree_sprint)):
            return True
    return False


def _creneau_prefere(inst, code, rang_hebdo, debut, fin):
    nom = (inst.get("nom") or "").lower()
    if code == "quotidienne":
        return debut, "09:30"
    if code == "debut_sprint":
        return debut, "10:00"
    if code == "fin_sprint":
        return fin, "14:00"
    if code == "deux_sprints":
        return fin, "15:30"
    if code == "hebdomadaire":
        if re.search(r"affinage|refinement", nom):
            jour, heure = 3, "14:00"
        elif re.search(r"synchro|weekly|hebdo", nom):
            jour, heure = 1, "11:00"
        else:
            jour, heure = [2, 4, 0, 1, 3][rang_hebdo % 5], "11:00"
        return debut + dt.timedelta(days=(jour - debut.weekday()) % 7), heure
    if code == "mensuelle":  # premier jeudi du mois suivant
        m = dt.date(debut.year + debut.month // 12, debut.month % 12 + 1, 1)
        return m + dt.timedelta(days=(3 - m.weekday()) % 7), "10:00"
    return None, None


def _placer(inst, jour, heure, placees, horizon, duree_sprint):
    """Premier créneau libre à partir du créneau préféré : même jour d'abord, puis jours suivants."""
    duree = inst.get("duree_min") or 60
    for decalage in range(1 if inst["recurrence"] == "quotidienne" else 5):
        d = _jour_ouvre(jour + dt.timedelta(days=decalage))
        depart = hm(heure) if decalage == 0 else PLAGE[0]
        for t in range(depart, PLAGE[1] - duree + 1, 30):
            if t < PAUSE[1] and t + duree > PAUSE[0]:
                continue
            candidat = dict(inst, premiere=d.isoformat(), heure=en_heure(t))
            if not _conflit(candidat, placees, horizon, duree_sprint):
                return d, en_heure(t)
    return jour, heure  # journée pleine : on garde le créneau préféré, le pilote tranchera


def proposer(tout=False, aujourdhui=None):
    """Propose un créneau aux instances qui n'en ont pas (à toutes si `tout`)."""
    auj = aujourdhui or dt.date.today()
    mission = db.mission()
    debut, fin, duree_sprint = sprint_de_reference(mission, db.lister("sprint"), auj)
    horizon = (debut, debut + dt.timedelta(days=HORIZON_JOURS))
    instances = db.lister("instance")
    placees = [] if tout else [i for i in instances if i.get("premiere") and hm(i.get("heure")) is not None]
    deja = {i["id"] for i in placees}
    rang_hebdo, modifiees = 0, []
    for inst in instances:
        if inst["id"] in deja:
            continue
        code = inst.get("recurrence") or deviner_recurrence(inst.get("frequence"))
        maj = {"recurrence": code, "duree_min": inst.get("duree_min") or minutes(inst.get("duree"))}
        jour, heure = _creneau_prefere(inst, code, rang_hebdo, debut, fin)
        rang_hebdo += code == "hebdomadaire"
        if jour is None:  # à la demande : pas de série à poser
            maj.update(premiere="", heure="")
        else:
            jour, heure = _placer(dict(inst, **maj), jour, heure, placees, horizon, duree_sprint)
            maj.update(premiere=jour.isoformat(), heure=heure)
        inst = db.modifier("instance", inst["id"], maj)
        if inst.get("heure"):
            placees.append(inst)
        modifiees.append(inst)
    return modifiees


def calendrier(aujourdhui=None):
    """Les séances du sprint de référence, jour par jour, et les instances hors de ce sprint."""
    auj = aujourdhui or dt.date.today()
    debut, fin, duree_sprint = sprint_de_reference(db.mission(), db.lister("sprint"), auj)
    instances = db.lister("instance")
    jours, d = [], debut
    while d <= fin:
        if d.weekday() < 5:
            seances = []
            for i in instances:
                if d in occurrences(i, d, d, duree_sprint):
                    a = hm(i["heure"])
                    seances.append({"id": i["id"], "nom": i["nom"], "debut": i["heure"],
                                    "fin": en_heure(a + (i.get("duree_min") or 60))})
            jours.append({"date": d.isoformat(), "jour": JOURS[d.weekday()],
                          "seances": sorted(seances, key=lambda s: s["debut"])})
        d += dt.timedelta(days=1)
    vues = {s["id"] for j in jours for s in j["seances"]}
    hors, non_planifiees = [], []
    for i in instances:
        if i["id"] in vues:
            continue
        prochaines = occurrences(i, debut, debut + dt.timedelta(days=400), duree_sprint)
        if prochaines:
            hors.append({"id": i["id"], "nom": i["nom"], "date": prochaines[0].isoformat(),
                         "heure": i["heure"]})
        else:
            non_planifiees.append({"id": i["id"], "nom": i["nom"],
                                   "recurrence": i.get("recurrence") or ""})
    return {"debut": debut.isoformat(), "fin": fin.isoformat(), "jours": jours,
            "hors_sprint": hors, "non_planifiees": non_planifiees}


def _regle(inst, duree_sprint, jusqua):
    p = calculs.date(inst.get("premiere"))
    code, jour = inst.get("recurrence"), ICAL[p.weekday()]

    def tous_les(jours):
        return (f"FREQ=WEEKLY;INTERVAL={jours // 7};BYDAY={jour}" if jours % 7 == 0
                else f"FREQ=DAILY;INTERVAL={jours}")
    regle = {
        "quotidienne": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
        "hebdomadaire": f"FREQ=WEEKLY;BYDAY={jour}",
        "debut_sprint": tous_les(duree_sprint), "fin_sprint": tous_les(duree_sprint),
        "deux_sprints": tous_les(2 * duree_sprint),
        "mensuelle": f"FREQ=MONTHLY;BYDAY={(p.day - 1) // 7 + 1}{jour}",
    }.get(code)
    if regle and jusqua:
        regle += f";UNTIL={jusqua:%Y%m%d}T235959"
    return regle


def _echapper(texte):
    return (str(texte or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r", "").replace("\n", "\\n"))


def _plier(ligne):
    """Lignes de 75 octets au plus (RFC 5545), sans couper un caractère UTF-8."""
    morceaux, courant = [], ""
    for c in ligne:
        if len((courant + c).encode("utf-8")) > (75 if not morceaux else 74):
            morceaux.append(courant)
            courant = ""
        courant += c
    morceaux.append(courant)
    return "\r\n ".join(morceaux)


def ics(instances, aujourdhui=None):
    """Fichier iCalendar des séries de réunions, avec les participants qui ont un e-mail."""
    mission = db.mission()
    acteurs = {a["id"]: a for a in db.lister("acteur")}
    duree_sprint = int(mission.get("duree_sprint_jours") or 14)
    bornes = [calculs.date(j.get("date")) for j in db.lister("jalon")] + [calculs.date(mission.get("date_cible"))]
    jusqua = max([b for b in bornes if b], default=None)
    horodatage = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Copilote de mission//FR",
              "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for inst in instances:
        p, a = calculs.date(inst.get("premiere")), hm(inst.get("heure"))
        if not p or a is None:
            continue
        debut = dt.datetime.combine(p, dt.time(a // 60, a % 60))
        fin = debut + dt.timedelta(minutes=inst.get("duree_min") or 60)
        personnes = [acteurs[i] for i in db.ids(inst.get("participants_ids")) if i in acteurs]
        description = (inst.get("objectifs") or "").strip()
        noms = [f"{x['nom']} ({x.get('role') or x.get('metier') or ''})".replace(" ()", "") for x in personnes]
        if inst.get("participants"):
            noms.append(inst["participants"])
        if noms:
            description += "\n\nParticipants : " + " ; ".join(noms)
        lignes += ["BEGIN:VEVENT", f"UID:copilote-instance-{inst['id']}@copilote.local",
                   f"DTSTAMP:{horodatage}", f"DTSTART:{debut:%Y%m%dT%H%M%S}",
                   f"DTEND:{fin:%Y%m%dT%H%M%S}",
                   "SUMMARY:" + _echapper(f"{mission.get('nom') or 'Mission'} — {inst.get('nom')}"),
                   "DESCRIPTION:" + _echapper(description)]
        regle = _regle(inst, duree_sprint, jusqua)
        if regle:
            lignes.append("RRULE:" + regle)
        for x in personnes:
            if (x.get("email") or "").strip():
                cn = re.sub(r'[";:,]', " ", x["nom"]).strip()
                lignes.append(f'ATTENDEE;CN="{cn}";ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{x["email"].strip()}')
        lignes.append("END:VEVENT")
    lignes.append("END:VCALENDAR")
    return "\r\n".join(_plier(l) for l in lignes) + "\r\n"
