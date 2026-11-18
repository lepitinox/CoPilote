"""Demandes de changement : de l'origine (attente, hypothèse invalidée, risque) à l'avenant.

Cycle : à instruire → chiffrée → présentée (une décision « à prendre » est créée pour le
comité) → acceptée, refusée ou reportée.

Acceptée = avenant : le budget vendu augmente du montant chiffré, le reste à faire des profils
augmente des jours chiffrés, les jalons touchés sont décalés (date prévue et date de référence,
puisque l'engagement change), l'origine est mise à jour, la décision est marquée prise. Tout est
inscrit à l'historique sous l'origine « avenant : <demande> ».
"""
import datetime as dt
import json

import db
import donnees
import finances

STATUTS = ["à instruire", "chiffrée", "présentée", "acceptée", "refusée", "reportée"]
OUVERTS = ("à instruire", "chiffrée", "présentée")
ORIGINES = {"attente": "attente du client", "hypothese": "hypothèse invalidée", "risque": "risque", "directe": "demande directe"}
MOTS_COMITE = ("comité", "comite", "copil", "sponsor", "steerco")


class ErreurChangement(ValueError):
    pass


def _lire(ident):
    c = db.lire("changement", ident)
    if not c:
        raise ErreurChangement("Demande de changement introuvable.")
    return c


def chiffrage(ident):
    """Lignes de chiffrage de la demande, valorisées, avec majorations et fourchette."""
    m = db.mission()
    p = finances.parametres(m)
    profils = db.lister("profil")
    tjms = {x["nom"]: finances._n(x.get("tjm")) for x in profils if x.get("nom")}
    tjm_def = finances.tjm_moyen(p, profils)
    lignes = [finances.ligne_chiffree({**e, "mode": "detaille"}, p, tjms, tjm_def)
              for e in db.lister("estimation", "changement_id = ?", (ident,))]
    taux = sum(finances._n(v) or 0 for v in p["majorations"].values())
    base = {k: sum(l[k] or 0 for l in lignes) for k in ("bas", "retenu", "haut")}
    montant_base = sum(l["montant"] or 0 for l in lignes)
    tjm_pondere = montant_base / base["retenu"] if base["retenu"] and montant_base else tjm_def
    total = {k: round(v * (1 + taux), 2) for k, v in base.items()}
    return {"lignes": lignes, "base": {k: round(v, 2) for k, v in base.items()}, "total_jours": total,
            "taux_majoration": taux,
            "montant": round(total["retenu"] * tjm_pondere, 2) if tjm_pondere else None,
            "montant_bas": round(total["bas"] * tjm_pondere, 2) if tjm_pondere else None,
            "montant_haut": round(total["haut"] * tjm_pondere, 2) if tjm_pondere else None}


def _origine(c):
    t, i = c.get("origine_type") or "directe", c.get("origine_id")
    if t in ("attente", "hypothese", "risque") and i:
        o = db.lire(t, i)
        if o:
            return {"type": t, "id": i, "libelle": o.get("libelle") or o.get("titre"), "libelle_type": ORIGINES[t]}
    return {"type": "directe", "id": None, "libelle": None, "libelle_type": ORIGINES["directe"]}


def detail(ident):
    c = _lire(ident)
    jalons = {j["id"]: j for j in db.lister("jalon")}
    return {**c, "origine": _origine(c), "chiffrage": chiffrage(ident),
            "jalons": [jalons[i] for i in db.ids(c.get("jalons_ids")) if i in jalons]}


def suivi(aujourdhui=None):
    """Toutes les demandes, avec leur chiffrage, et le cumul de ce qui a été accepté."""
    auj = aujourdhui or dt.date.today()
    liste = [detail(c["id"]) for c in db.lister("changement")]
    acceptees = [c for c in liste if c["statut"] == "acceptée"]
    cumul_montant = sum(c.get("montant_applique") or 0 for c in acceptees)
    cumul_jours = sum(c["chiffrage"]["total_jours"]["retenu"] for c in acceptees)
    cumul_delai = sum(c.get("impact_delai_jours") or 0 for c in acceptees)
    vendu = finances._n(db.mission().get("budget_vendu"))
    initial = vendu - cumul_montant if vendu is not None else None
    en_cours = [c for c in liste if c["statut"] in OUVERTS]
    for c in liste:
        cree = donnees.calculs.date(c.get("cree_le"))
        c["age_jours"] = (auj - cree).days if cree else None
    return {"demandes": liste,
            "compte": {s: sum(1 for c in liste if c["statut"] == s) for s in STATUTS},
            "cumul_accepte": {"montant": round(cumul_montant, 2), "jours": round(cumul_jours, 2), "delai_jours": cumul_delai,
                              "part_budget_initial": round(cumul_montant / initial, 4) if initial else None},
            "budget_initial": initial,
            "en_cours": {"nombre": len(en_cours),
                         "montant": round(sum(c["chiffrage"]["montant"] or 0 for c in en_cours), 2),
                         "delai_jours": sum(c.get("impact_delai_jours") or 0 for c in en_cours)}}


def creer(corps, aujourdhui=None):
    corps = dict(corps or {})
    t = corps.get("origine_type") or "directe"
    if t not in ORIGINES:
        raise ErreurChangement("Origine inconnue : attente, hypothese, risque ou directe.")
    if t != "directe":
        o = db.lire(t, corps.get("origine_id") or 0)
        if not o:
            raise ErreurChangement("L'élément d'origine n'existe pas.")
        corps.setdefault("titre", o.get("libelle") or o.get("titre"))
        corps.setdefault("demandeur", o.get("partie_prenante") or o.get("porteur") or "")
        corps.setdefault("lot", o.get("lot") or "")
        corps.setdefault("description", o.get("impact") or o.get("description") or o.get("reponse") or "")
    if not (corps.get("titre") or "").strip():
        raise ErreurChangement("Une demande de changement a un titre.")
    corps["origine_type"] = t
    corps.setdefault("statut", "à instruire")
    corps["cree_le"] = (aujourdhui or dt.date.today()).isoformat()
    return db.creer("changement", corps)


def chiffrer_avec_bloc(ident, bloc, niveau, quantite=1, libelle=None):
    c = _lire(ident)
    if c["statut"] not in OUVERTS:
        raise ErreurChangement("Cette demande est déjà décidée : son chiffrage ne change plus.")
    lignes = donnees.appliquer_bloc(bloc, niveau, "detaille", c.get("lot") or "", quantite, libelle, changement_id=ident)
    if c["statut"] == "à instruire":
        db.modifier("changement", ident, {"statut": "chiffrée"})
    return lignes


def presenter(ident, instance=None, echeance=None, aujourdhui=None):
    """Crée la décision à faire prendre en comité et passe la demande à « présentée »."""
    c = _lire(ident)
    if c["statut"] not in ("à instruire", "chiffrée"):
        raise ErreurChangement("Seule une demande à instruire ou chiffrée peut être présentée.")
    ch = chiffrage(ident)
    if not instance:
        comites = [i["nom"] for i in db.lister("instance") if any(k in (i["nom"] or "").lower() for k in MOTS_COMITE)]
        instance = comites[0] if comites else ""
    impact = [f"Montant {finances.euros(ch['montant'])} (fourchette {finances.euros(ch['montant_bas'])} à "
              f"{finances.euros(ch['montant_haut'])}), {ch['total_jours']['retenu']:g} jours" if ch["lignes"] else "Non chiffrée"]
    if c.get("impact_delai_jours"):
        impact.append(f"décalage de {c['impact_delai_jours']} jours sur les jalons touchés")
    d = donnees.creer_element("decision", {
        "nature": "decision", "statut": "à prendre", "titre": f"Demande de changement : {c['titre']}",
        "detail": (c.get("description") or "") + "\nImpact : " + " ; ".join(impact)
                  + ".\nOptions : accepter (avenant), refuser, reporter au lot suivant.",
        "porteur": c.get("decideur") or "", "echeance": echeance or "", "instance": instance}, aujourdhui)
    return db.modifier("changement", ident, {"statut": "présentée", "decision_id": d["id"]})


def decider(ident, choix, motif="", aujourdhui=None):
    """accepter (avenant), refuser ou reporter. Renvoie la demande et ce qui a été modifié."""
    if choix not in ("accepter", "refuser", "reporter"):
        raise ErreurChangement("Décision inconnue : accepter, refuser ou reporter.")
    c = _lire(ident)
    if c["statut"] not in OUVERTS:
        raise ErreurChangement("Cette demande est déjà décidée.")
    auj = (aujourdhui or dt.date.today()).isoformat()
    effets = []
    libelle = {"accepter": "avenant", "refuser": "demande de changement refusée", "reporter": "demande de changement reportée"}[choix]
    with db.origine(f"{libelle} : {c['titre']}"):
        maj = {"statut": {"accepter": "acceptée", "refuser": "refusée", "reporter": "reportée"}[choix],
               "decide_le": auj, "motif": motif}
        if choix == "accepter":
            ch = chiffrage(ident)
            m = db.mission()
            if ch["montant"] and finances._n(m.get("budget_vendu")) is not None:
                donnees.modifier_fiche({"budget_vendu": round(m["budget_vendu"] + ch["montant"], 2)})
                maj["montant_applique"] = ch["montant"]
                effets.append(f"budget vendu augmenté de {finances.euros(ch['montant'])}")
            elif ch["montant"]:
                maj["montant_applique"] = ch["montant"]
                effets.append("pas de budget vendu saisi : le montant n'a pas pu être ajouté")
            profils = {p["nom"]: p for p in db.lister("profil")}
            ajout = {}
            for l in ch["lignes"]:
                if l.get("profil") in profils:
                    ajout[l["profil"]] = ajout.get(l["profil"], 0) + (l["retenu"] or 0) * (1 + ch["taux_majoration"])
            for nom, j in ajout.items():
                p = profils[nom]
                donnees.modifier_element("profil", p["id"], {"raf_jours": round((p.get("raf_jours") or 0) + j, 2)}, aujourdhui)
            if ajout:
                effets.append("reste à faire augmenté : " + ", ".join(f"{n} +{j:.1f} j".replace(".", ",") for n, j in ajout.items()))
            decale = c.get("impact_delai_jours") or 0
            if decale:
                for i in db.ids(c.get("jalons_ids")):
                    j = db.lire("jalon", i)
                    if not j:
                        continue
                    nouveau = {}
                    for cle in ("date", "date_initiale"):
                        d = donnees.calculs.date(j.get(cle))
                        if d:
                            nouveau[cle] = (d + dt.timedelta(days=decale)).isoformat()
                    donnees.modifier_element("jalon", i, nouveau, aujourdhui)
                    effets.append(f"jalon « {j['libelle']} » décalé de {decale} jours (engagement compris)")
            maj["avenant_le"] = auj
        o = _origine(c)
        if o["type"] == "attente":
            a = db.lire("attente", o["id"])
            note = {"accepter": "acceptée par avenant", "refuser": "refusée", "reporter": "reportée"}[choix]
            donnees.modifier_element("attente", o["id"], {
                "position": "alignée" if choix == "accepter" else "hors périmètre" if choix == "refuser" else a.get("position"),
                "reponse": ((a.get("reponse") or "") + f"\n[{auj}] Demande de changement {note}" + (f" : {motif}" if motif else "") + ".").strip(),
                "revue_le": auj}, aujourdhui)
            effets.append("attente d'origine mise à jour")
        elif o["type"] == "risque" and choix == "accepter":
            r = db.lire("risque", o["id"])
            donnees.modifier_element("risque", o["id"], {"plan_action": ((r.get("plan_action") or "")
                                     + f"\n[{auj}] Traité par la demande de changement acceptée : {c['titre']}.").strip()}, aujourdhui)
            effets.append("plan d'action du risque d'origine complété")
        if c.get("decision_id") and db.lire("decision", c["decision_id"]):
            d = db.lire("decision", c["decision_id"])
            donnees.modifier_element("decision", d["id"], {"statut": "prise", "detail": ((d.get("detail") or "")
                                     + f"\n[{auj}] Décision : {maj['statut']}" + (f" — {motif}" if motif else "") + ".").strip()}, aujourdhui)
            effets.append("décision marquée prise")
        db.modifier("changement", ident, maj)
    return {"demande": detail(ident), "effets": effets}
