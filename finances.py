"""Chiffrage, budget et attentes du client : calculs déterministes, sans LLM.

Chiffrage en deux modes :
- macro, quand on sait peu de choses : chaque élément reçoit une taille (XS à XL) convertie
  en jours par un abaque, et une confiance qui donne la fourchette basse / haute ;
- détaillé, après la collecte d'informations : charge en trois points (basse, probable,
  haute) par profil, combinée en estimation PERT, valorisée au TJM du profil.
Les deux modes coexistent : la comparaison par lot montre ce que la collecte a changé.
"""
import datetime as dt

TAILLES = ["XS", "S", "M", "L", "XL"]
PARAMETRES_DEFAUT = {
    "abaque": {"XS": 2, "S": 5, "M": 10, "L": 20, "XL": 40},       # jours par taille
    "marges": {"forte": 0.15, "moyenne": 0.30, "faible": 0.50},     # fourchette selon la confiance
    "majorations": {"pilotage": 0.15, "qualite": 0.10, "contingence": 0.10},
    "mode_retenu": "macro",
    "tjm_moyen": None,                                               # sinon moyenne des profils
}
SEUILS_BUDGET = {"ecart_avancement": 0.10}  # consommé en avance de plus de 10 points sur l'avancement


def _n(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def parametres(mission):
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in PARAMETRES_DEFAUT.items()}
    saisis = mission.get("chiffrage") or {}
    for k, v in saisis.items():
        if isinstance(p.get(k), dict) and isinstance(v, dict):
            p[k].update({c: x for c, x in v.items() if _n(x) is not None})
        elif k in p:
            p[k] = v
    if p["mode_retenu"] not in ("macro", "detaille"):
        p["mode_retenu"] = "macro"
    return p


def tjm_moyen(p, profils):
    if _n(p.get("tjm_moyen")):
        return _n(p["tjm_moyen"])
    tjms = [_n(x.get("tjm")) for x in profils if _n(x.get("tjm"))]
    return round(sum(tjms) / len(tjms), 2) if tjms else None


def ligne_chiffree(e, p, tjms, tjm_def):
    """Une estimation avec ses jours bas / retenu / haut et sa valorisation."""
    bas, prob, haut = _n(e.get("jours_bas")), _n(e.get("jours_probable")), _n(e.get("jours_haut"))
    if e.get("mode") == "detaille":
        if prob is None:
            prob = bas if haut is None else haut if bas is None else (bas + haut) / 2
        bas = prob if bas is None else bas
        haut = prob if haut is None else haut
        retenu = (bas + 4 * prob + haut) / 6 if prob is not None else None  # PERT
        tjm = tjms.get(e.get("profil")) or tjm_def
    else:
        if prob is None:
            prob = _n(p["abaque"].get(e.get("taille")))
        marge = _n(p["marges"].get(e.get("confiance") or "moyenne")) or 0
        if prob is not None:
            bas = prob * (1 - marge) if bas is None else bas
            haut = prob * (1 + marge) if haut is None else haut
        retenu, tjm = prob, tjm_def
    out = {**e, "bas": bas, "retenu": retenu, "haut": haut, "tjm_applique": tjm}
    out["montant"] = round(retenu * tjm, 2) if retenu is not None and tjm else None
    return out


def chiffrage(mission, estimations, profils):
    p = parametres(mission)
    tjms = {x["nom"]: _n(x.get("tjm")) for x in profils if x.get("nom")}
    tjm_def = tjm_moyen(p, profils)
    taux_maj = sum(_n(v) or 0 for v in p["majorations"].values())
    modes = {}
    for mode in ("macro", "detaille"):
        lignes = [ligne_chiffree(e, p, tjms, tjm_def) for e in estimations if (e.get("mode") or "macro") == mode]
        base = {k: sum(l[k] or 0 for l in lignes) for k in ("bas", "retenu", "haut")}
        montant_base = sum(l["montant"] or 0 for l in lignes)
        # Les majorations (pilotage, qualité, contingence) s'appliquent à la charge de base,
        # valorisées au TJM moyen pondéré de la base.
        tjm_pondere = montant_base / base["retenu"] if base["retenu"] and montant_base else tjm_def
        majorations = {k: round(base["retenu"] * (_n(v) or 0), 2) for k, v in p["majorations"].items()}
        total = {k: round(base[k] * (1 + taux_maj), 2) for k in base}
        part_faible = sum(l["retenu"] or 0 for l in lignes if (l.get("confiance") == "faible" or l.get("niveau") == "long")) / base["retenu"] \
            if base["retenu"] else None
        etendue = (base["haut"] - base["bas"]) / base["retenu"] / 2 if base["retenu"] else None
        risque_haut = base["haut"] - base["retenu"]
        contingence = base["retenu"] * (_n(p["majorations"].get("contingence")) or 0)
        modes[mode] = {
            "incertitude": {"part_sans_information": round(part_faible, 3) if part_faible is not None else None,
                            "etendue": round(etendue, 3) if etendue is not None else None,
                            "couverture_contingence": round(contingence / risque_haut, 3) if risque_haut > 0 else None,
                            "sans_profil": sum(1 for l in lignes if mode == "detaille" and not l.get("profil"))},
            "lignes": lignes, "base": {k: round(v, 2) for k, v in base.items()},
            "majorations": majorations, "total_jours": total,
            "montant": round(total["retenu"] * tjm_pondere, 2) if tjm_pondere else None,
            "montant_bas": round(total["bas"] * tjm_pondere, 2) if tjm_pondere else None,
            "montant_haut": round(total["haut"] * tjm_pondere, 2) if tjm_pondere else None,
            "sans_valorisation": sum(1 for l in lignes if l["montant"] is None and l["retenu"]),
            "nb": len(lignes),
        }
    lots = sorted({(l.get("lot") or "") for m in modes.values() for l in m["lignes"]})
    comparaison = []
    for lot in lots:
        a = sum(l["retenu"] or 0 for l in modes["macro"]["lignes"] if (l.get("lot") or "") == lot)
        b = sum(l["retenu"] or 0 for l in modes["detaille"]["lignes"] if (l.get("lot") or "") == lot)
        comparaison.append({"lot": lot, "macro": round(a, 2), "detaille": round(b, 2),
                            "ecart": round((b - a) / a, 3) if a and b else None})
    return {"parametres": p, "tjm_moyen": tjm_def, "taux_majoration": taux_maj, "modes": modes,
            "comparaison": comparaison, "retenu": modes[p["mode_retenu"]]}


def budget(mission, profils, consommations, depenses, factures, livrables, chiffre=None, aujourdhui=None):
    auj = (aujourdhui or dt.date.today()).isoformat()
    par_profil = []
    tjms = {x["nom"]: x for x in profils}
    for x in profils:
        cons = sum(_n(c.get("jours")) or 0 for c in consommations if c.get("profil") == x["nom"])
        tjm, cout, raf = _n(x.get("tjm")), _n(x.get("cout_journalier")), _n(x.get("raf_jours")) or 0
        par_profil.append({
            **x, "consomme_jours": cons, "consomme": round(cons * tjm, 2) if tjm else None,
            "raf": round(raf * tjm, 2) if tjm else None, "atterrissage_jours": cons + raf,
            "atterrissage": round((cons + raf) * tjm, 2) if tjm else None,
            "cout": round((cons + raf) * cout, 2) if cout else None})
    inconnus = sorted({c.get("profil") or "—" for c in consommations if c.get("profil") not in tjms})
    dep_faites = sum(_n(d.get("montant")) or 0 for d in depenses if d.get("statut") in ("engagée", "payée"))
    dep_prevues = sum(_n(d.get("montant")) or 0 for d in depenses if d.get("statut") not in ("engagée", "payée"))
    consomme = sum(p["consomme"] or 0 for p in par_profil) + dep_faites
    raf = sum(p["raf"] or 0 for p in par_profil) + dep_prevues
    atterrissage = consomme + raf
    vendu = _n(mission.get("budget_vendu"))
    reference = vendu if vendu is not None else (chiffre or {}).get("retenu", {}).get("montant")
    couts_connus = all(p["cout"] is not None for p in par_profil) and par_profil
    cout_total = (sum(p["cout"] for p in par_profil) + dep_faites + dep_prevues) if couts_connus else None
    avancements = [_n(l.get("avancement")) for l in livrables if _n(l.get("avancement")) is not None]
    avancement = sum(avancements) / len(avancements) / 100 if avancements else None

    mois = sorted({c.get("mois") for c in consommations if c.get("mois")})
    par_mois, cumul = [], 0.0
    for m in mois:
        montant = sum((_n(c.get("jours")) or 0) * (_n((tjms.get(c.get("profil")) or {}).get("tjm")) or 0)
                      for c in consommations if c.get("mois") == m)
        cumul += montant
        par_mois.append({"mois": m, "montant": round(montant, 2), "cumul": round(cumul, 2)})

    facture_ = sum(_n(f.get("montant")) or 0 for f in factures if f.get("statut") in ("facturée", "payée"))
    paye = sum(_n(f.get("montant")) or 0 for f in factures if f.get("statut") == "payée")
    en_retard = [f for f in factures if f.get("statut") in (None, "", "à facturer")
                 and f.get("date_prevue") and f["date_prevue"] < auj]

    alertes = []
    if reference and atterrissage > reference:
        alertes.append({"code": "budget", "niveau": 3, "titre": "Dépassement de budget prévu",
                        "detail": f"Atterrissage {euros(atterrissage)} pour {euros(reference)} "
                                  f"{'vendus' if vendu is not None else 'chiffrés'} : "
                                  f"+{euros(atterrissage - reference)}."})
    if reference and avancement is not None and consomme / reference > avancement + SEUILS_BUDGET["ecart_avancement"]:
        alertes.append({"code": "consommation", "niveau": 2, "titre": "Consommation en avance sur l'avancement",
                        "detail": f"{round(consomme / reference * 100)} % du budget consommé pour "
                                  f"{round(avancement * 100)} % d'avancement moyen des livrables."})
    for f in en_retard:
        alertes.append({"code": "facture", "niveau": 2, "titre": f"Facturation en retard : {f.get('libelle')}",
                        "detail": f"{euros(_n(f.get('montant')) or 0)} prévus le {f['date_prevue']}, toujours à facturer."})
    if inconnus:
        alertes.append({"code": "profil", "niveau": 2, "titre": "Consommation sur un profil sans TJM",
                        "detail": "Profils non valorisés : " + ", ".join(inconnus) + "."})
    return {
        "vendu": vendu, "reference": reference, "reference_source": "vendu" if vendu is not None else "chiffrage",
        "consomme": round(consomme, 2), "raf": round(raf, 2), "atterrissage": round(atterrissage, 2),
        "ecart": round(reference - atterrissage, 2) if reference else None,
        "taux_consomme": round(consomme / reference, 4) if reference else None,
        "avancement": avancement, "cout_total": cout_total,
        "marge": round(reference - cout_total, 2) if reference and cout_total is not None else None,
        "taux_marge": round((reference - cout_total) / reference, 4) if reference and cout_total is not None else None,
        "depenses_faites": dep_faites, "depenses_prevues": dep_prevues,
        "par_profil": par_profil, "par_mois": par_mois,
        "facture": facture_, "paye": paye, "a_facturer": round((reference or 0) - facture_, 2) if reference else None,
        "factures_en_retard": len(en_retard), "alertes": alertes,
    }


CATEGORIES_ATTENTE = ["délai", "périmètre", "qualité", "coût", "relation", "communication"]
DELAI_REVUE_JOURS = 30


def attentes(liste, historique, aujourdhui=None):
    """Attentes avec l'évolution de la satisfaction (tirée de l'historique) et les alertes."""
    auj = aujourdhui or dt.date.today()
    precedente = {}
    for e in historique:  # le plus récent d'abord
        if e.get("action") != "modification" or e["ligne"] in precedente:
            continue
        a, b = (e.get("avant") or {}).get("satisfaction"), (e.get("apres") or {}).get("satisfaction")
        if a != b:
            precedente[e["ligne"]] = {"valeur": a, "le": (e.get("horodatage") or "")[:10]}
    out, alertes = [], []
    limite = (auj - dt.timedelta(days=DELAI_REVUE_JOURS)).isoformat()
    for x in liste:
        p = precedente.get(x["id"])
        s, avant = x.get("satisfaction"), (p or {}).get("valeur")
        evolution = None
        if isinstance(s, int) and isinstance(avant, int):
            evolution = "hausse" if s > avant else "baisse" if s < avant else "stable"
        revue_due = not x.get("revue_le") or x["revue_le"] < limite
        out.append({**x, "satisfaction_precedente": avant, "satisfaction_changee_le": (p or {}).get("le"),
                    "evolution": evolution, "revue_due": revue_due})
        titre = f"{x.get('partie_prenante') or 'Client'} : {x.get('libelle')}"
        if x.get("priorite") == 1 and isinstance(s, int) and s <= 2:
            alertes.append({"code": "attente", "niveau": 3, "titre": "Attente prioritaire insatisfaite",
                            "detail": f"{titre} (satisfaction {s} / 5)."})
        elif x.get("position") == "à recadrer" and not (x.get("prochaine_action") or "").strip():
            alertes.append({"code": "recadrage", "niveau": 2, "titre": "Attente à recadrer sans action prévue",
                            "detail": titre + "."})
        if x.get("position") != "hors périmètre" and x.get("echeance") and x["echeance"] < auj.isoformat() \
                and (s or 0) < 4:
            alertes.append({"code": "attente_echeance", "niveau": 2, "titre": "Échéance d'une attente dépassée",
                            "detail": f"{titre} — échéance {x['echeance']}."})
    return {"attentes": out, "alertes": alertes}


def euros(v):
    if v is None:
        return "—"
    return f"{round(v):,} €".replace(",", " ")
