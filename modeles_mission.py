"""Modèles de mission : un cadre (organisation, gouvernance, profils, RACI, paramètres du chiffrage)
et un squelette de contenu (lots, prérequis, jalons et activités en dates relatives, hypothèses et
risques types, story map, blocs de chiffrage préchoisis).

Les modèles fournis sont dans modeles_fournis.py ; ceux enregistrés depuis une mission sont des
fichiers JSON du dossier `modeles-mission` (à côté des missions), communs à toutes les missions.
Créer une mission depuis un modèle recalcule les dates à partir de la date de début choisie.
"""
import datetime as dt
import json
import os
import re

import calculs
import db
import donnees
from modeles_fournis import MODELES_FOURNIS

FORMAT = "copilote-modele"
CADRE = ("metier", "acteur", "instance", "profil", "raci")


def _dossier():
    return os.path.join(db.DOSSIER, "modeles-mission")


def _fichier(cle):
    if not db.cle_valide(cle):
        raise ValueError("Modèle introuvable.")
    return os.path.join(_dossier(), cle + ".json")


def _personnels():
    out = {}
    if os.path.isdir(_dossier()):
        for n in sorted(os.listdir(_dossier())):
            if n.endswith(".json") and db.cle_valide(n[:-5]):
                try:
                    with open(os.path.join(_dossier(), n), encoding="utf-8") as f:
                        m = json.load(f)
                    if isinstance(m, dict) and m.get("format") == FORMAT:
                        out[n[:-5]] = m
                except (OSError, ValueError):
                    continue
    return out


def _resume(cle, m, origine):
    s, c = m.get("squelette") or {}, m.get("cadre") or {}
    return {"cle": cle, "nom": m.get("nom"), "description": m.get("description") or "", "origine": origine,
            "cree_le": m.get("cree_le"), "source": m.get("source"),
            "contenu": {"acteurs": len(c.get("acteur") or []), "instances": len(c.get("instance") or []),
                        "profils": len(c.get("profil") or []), "lots": len(s.get("lot") or []),
                        "jalons": len(s.get("jalon") or []), "hypotheses": len(s.get("hypothese") or []),
                        "risques": len(s.get("risque") or []), "blocs": len(s.get("blocs") or [])}}


def lister():
    fournis = [_resume(c, m, "fourni") for c, m in MODELES_FOURNIS.items()]
    return fournis + [_resume(c, m, "personnel") for c, m in _personnels().items()]


def lire(cle):
    if cle in MODELES_FOURNIS:
        return MODELES_FOURNIS[cle]
    m = _personnels().get(cle)
    if not m:
        raise ValueError("Modèle introuvable.")
    return m


def supprimer(cle):
    if cle in MODELES_FOURNIS:
        raise ValueError("Un modèle fourni ne se supprime pas.")
    chemin = _fichier(cle)
    if not os.path.isfile(chemin):
        raise ValueError("Modèle introuvable.")
    os.remove(chemin)


# ---------------------------------------------------------------- enregistrer depuis une mission

def _decalage(iso, j0):
    d = calculs.date(iso)
    return (d - j0).days if d and j0 else None


def depuis_mission(nom, description="", anonymiser=True):
    """Modèle construit à partir de la mission courante. anonymiser : les personnes deviennent leur
    rôle, sans e-mail ; le nom et le client de la mission ne sont jamais repris."""
    m = db.mission()
    lu = {t: db.lister(t) for t in (*CADRE, "lot", "lot_element", "jalon", "activite", "hypothese", "risque", "story", "estimation")}
    dates = [calculs.date(x) for x in [j.get("date_initiale") or j.get("date") for j in lu["jalon"]]
             + [a.get("debut") for a in lu["activite"]] + [l.get("date") for l in lu["lot"]]]
    j0 = min([d for d in dates if d] or [None], key=lambda d: d or dt.date.max)

    acteurs = []
    for i, a in enumerate(lu["acteur"], 1):
        a = {k: a.get(k) for k in ("id", "nom", "role", "cercle", "entite", "adherence", "metier", "email")}
        if anonymiser:
            a["nom"] = a.get("role") or a.get("metier") or f"Acteur {i}"
            a["email"] = ""
        acteurs.append(a)
    instances = [{k: i.get(k) for k in ("id", "nom", "chantier", "objectifs", "frequence", "duree", "rang",
                                        "participants_ids", "recurrence", "duree_min")}
                 | {"participants": "" if anonymiser else i.get("participants")} for i in lu["instance"]]
    blocs, vus = [], set()
    for e in lu["estimation"]:
        if not e.get("bloc") or e.get("mode") not in ("macro", "detaille"):
            continue
        q = re.search(r"× ([\d.,]+)$", e.get("libelle") or "")
        cle = (e["bloc"], e.get("niveau"), e.get("lot") or "", e.get("libelle"))
        if cle not in vus:
            vus.add(cle)
            blocs.append({"bloc": e["bloc"], "niveau": e.get("niveau") or "moyen", "lot": e.get("lot") or "",
                          "quantite": float(q.group(1).replace(",", ".")) if q else 1})
    return {
        "format": FORMAT, "version": 1, "nom": nom.strip(), "description": description.strip(),
        "cree_le": dt.date.today().isoformat(), "source": None if anonymiser else m.get("nom"),
        "cadre": {"metier": [{k: x.get(k) for k in ("nom", "rang")} for x in lu["metier"]], "acteur": acteurs,
                  "instance": instances,
                  "profil": [{k: p.get(k) for k in ("nom", "metier", "tjm", "cout_journalier", "rang")} for p in lu["profil"]],
                  "raci": [{k: r.get(k) for k in ("domaine", "activite", "valeurs", "rang")} for r in lu["raci"]],
                  "raci_roles": m.get("raci_roles") or [], "chiffrage": m.get("chiffrage") or {},
                  "duree_sprint_jours": m.get("duree_sprint_jours")},
        "squelette": {
            "lot": [{k: l.get(k) for k in ("nom", "titre", "periode", "rang")} | {"decalage": _decalage(l.get("date"), j0)} for l in lu["lot"]],
            "lot_element": [{k: e.get(k) for k in ("lot", "axe", "libelle", "detail")} for e in lu["lot_element"]],
            "jalon": [{"libelle": j["libelle"], "version": j.get("version"),
                       "decalage": _decalage(j.get("date_initiale") or j.get("date"), j0)} for j in lu["jalon"]],
            "activite": [{"piste": a.get("piste"), "libelle": a.get("libelle"), "debut": _decalage(a.get("debut"), j0),
                          "fin": _decalage(a.get("fin"), j0)} for a in lu["activite"]],
            "hypothese": [{k: h.get(k) for k in ("libelle", "categorie", "impact", "lot", "source")} for h in lu["hypothese"]
                          if not (h.get("source") == "catalogue de chiffrage")],
            "risque": [{k: r.get(k) for k in ("nature", "titre", "description", "probabilite", "impact", "lot", "plan_action")}
                       for r in lu["risque"] if not (r.get("titre") or "").startswith("Hypothèse invalidée")],
            "story": [{k: s.get(k) for k in ("etape", "rang_etape", "libelle", "lot", "irritant", "innovation")} for s in lu["story"]],
            "blocs": blocs,
        },
    }


def enregistrer(modele):
    """Enregistre un modèle personnel ; la clé vient de son nom (jamais d'écrasement)."""
    if not isinstance(modele, dict) or modele.get("format") != FORMAT or not (modele.get("nom") or "").strip():
        raise ValueError("Un modèle a un nom.")
    os.makedirs(_dossier(), exist_ok=True)
    base = db.slug(modele["nom"])
    cle, n = base, 1
    while cle in MODELES_FOURNIS or os.path.exists(_fichier(cle)):
        n += 1
        cle = f"{base}-{n}"
    with open(_fichier(cle), "w", encoding="utf-8") as f:
        json.dump(modele, f, ensure_ascii=False, indent=1)
    return _resume(cle, modele, "personnel")


# ---------------------------------------------------------------- appliquer à une mission

def appliquer(cle, date_debut=None):
    """Remplit la mission courante (vide) avec le cadre et le squelette du modèle."""
    m = lire(cle)
    c, s = m.get("cadre") or {}, m.get("squelette") or {}
    j0 = calculs.date(date_debut) or dt.date.today()
    jour = lambda decalage: (j0 + dt.timedelta(days=decalage)).isoformat() if isinstance(decalage, (int, float)) else None
    with db.connexion() as cx:
        def copier(table, lignes, avec_id=False):
            if lignes is None:
                return
            cx.execute(f"DELETE FROM {table}")
            for l in lignes:
                d = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v)
                     for k, v in l.items() if (k == "id" and avec_id) or k in db.TABLES[table]}
                cx.execute(f"INSERT INTO {table} ({', '.join(d)}) VALUES ({', '.join('?' for _ in d)})", tuple(d.values()))
        if c.get("metier"):
            copier("metier", c["metier"])
        copier("acteur", c.get("acteur"), avec_id=True)
        copier("instance", c.get("instance"), avec_id=True)
        copier("profil", [{**p, "raf_jours": 0} for p in c.get("profil") or []])
        copier("raci", c.get("raci"))
        maj = {"raci_roles": json.dumps(c.get("raci_roles") or [], ensure_ascii=False),
               "chiffrage": json.dumps(c.get("chiffrage") or {}, ensure_ascii=False)}
        if c.get("duree_sprint_jours"):
            maj["duree_sprint_jours"] = c["duree_sprint_jours"]
        cx.execute(f"UPDATE mission SET {', '.join(k + ' = ?' for k in maj)} WHERE id = 1", tuple(maj.values()))
    for l in s.get("lot") or []:
        db.creer("lot", {**{k: v for k, v in l.items() if k != "decalage"}, "date": jour(l.get("decalage")), "statut": "à venir"})
    for e in s.get("lot_element") or []:
        db.creer("lot_element", {**e, "statut": "en attente" if e.get("axe") == "prerequis" else None})
    for j in s.get("jalon") or []:
        db.creer("jalon", {"libelle": j["libelle"], "version": j.get("version"), "date": jour(j.get("decalage")), "statut": "à venir"})
    for a in s.get("activite") or []:
        db.creer("activite", {"piste": a.get("piste"), "libelle": a.get("libelle"), "debut": jour(a.get("debut")), "fin": jour(a.get("fin"))})
    auj = dt.date.today()
    for h in s.get("hypothese") or []:
        donnees.creer_element("hypothese", {**h, "statut": "à vérifier"}, auj)
    for r in s.get("risque") or []:
        donnees.creer_element("risque", {**r, "etat": "ouvert", "evolution": "stable"}, auj)
    for st in s.get("story") or []:
        db.creer("story", st)
    erreurs = []
    for b in s.get("blocs") or []:
        try:
            donnees.appliquer_bloc(b["bloc"], b.get("niveau") or "moyen", "macro", b.get("lot") or "", b.get("quantite") or 1)
        except ValueError as e:  # bloc retiré du catalogue depuis
            erreurs.append(f"{b['bloc']} : {e}")
    if s.get("blocs"):
        db.modifier("mission", 1, {"chiffrage": json.dumps({**(db.mission()["chiffrage"] or {}), "mode_retenu": "macro"}, ensure_ascii=False)})
    return erreurs
