"""Calculs déterministes du pilotage : KPI, atterrissage, déclencheurs, contrôles.

Aucun appel au LLM ici : tout chiffre affiché ou écrit dans une météo vient de ce module.
Les seuils reprennent la partie 9.1 de pilotage-mission.md ; ce sont des valeurs de départ.
"""
import datetime as dt
import math

SEUILS_DEFAUT = {
    "taux_realisation_min": 0.8,   # réalisé / prévu, en dessous deux sprints de suite
    "marge_ajout": 40,             # points ajoutés par sprint tolérés dans l'atterrissage
    "retard_sprints_max": 1,       # dépassement du jalon cible toléré, en sprints
    "adherence_alerte_jours": 30,
    "adherence_critique_jours": 15,
    "risque_stagnation_jours": 60,
}

OUVERTS = ("ouvert", "en traitement")
HORIZON_SPRINTS = 100  # au-delà, une date de fin n'a plus de sens
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def fr(valeur):
    """Date en clair : 7 décembre 2026."""
    d = valeur if isinstance(valeur, dt.date) else date(valeur)
    return f"{d.day} {MOIS[d.month - 1]} {d.year}" if d else "—"


def pc(taux):
    return f"{round(taux * 100)} %"


def seuils(mission):
    s = dict(SEUILS_DEFAUT)
    for k, v in (mission.get("seuils") or {}).items():
        if k in s and isinstance(v, (int, float)):
            s[k] = v
    return s


def date(valeur):
    try:
        return dt.date.fromisoformat((valeur or "")[:10])
    except ValueError:
        return None


def _n(valeur):
    return valeur if isinstance(valeur, (int, float)) else 0


def _moy(valeurs):
    return sum(valeurs) / len(valeurs) if valeurs else 0


def _tries(sprints):
    return sorted(sprints, key=lambda s: _n(s.get("numero")))


def kpi(sprints):
    sp = _tries(sprints)
    if not sp:
        return None
    dernier, recents = sp[-1], sp[-3:]
    taux = [_n(s["realise"]) / _n(s["prevu"]) for s in recents if _n(s.get("prevu")) > 0]
    return {
        "sprint": dernier.get("numero"),
        "prevu": _n(dernier.get("prevu")),
        "realise": _n(dernier.get("realise")),
        "ajoute": _n(dernier.get("ajoute")),
        "reste": _n(dernier.get("reste")),
        "taux_realisation": (_n(dernier["realise"]) / _n(dernier["prevu"]))
        if _n(dernier.get("prevu")) > 0 else None,
        "velocite_moyenne": round(_moy([_n(s.get("realise")) for s in recents]), 1),
        "ajout_moyen": round(_moy([_n(s.get("ajoute")) for s in recents]), 1),
        "predictibilite": round(_moy(taux), 2) if taux else None,
        "anomalies_creees": _n(dernier.get("anomalies_creees")),
        "anomalies_corrigees": _n(dernier.get("anomalies_corrigees")),
        "solde_anomalies": sum(
            _n(s.get("anomalies_creees")) - _n(s.get("anomalies_corrigees")) for s in sp
        ),
        "moral": dernier.get("moral"),
        "nb_sprints_moyenne": len(recents),
    }


def atterrissage(sprints, mission):
    """Projette le reste à faire sur la vélocité nette des trois derniers sprints."""
    sp = _tries(sprints)
    if not sp:
        return None
    k = kpi(sp)
    duree = _n(mission.get("duree_sprint_jours")) or 14
    net = k["velocite_moyenne"] - k["ajout_moyen"]
    fin_dernier = date(sp[-1].get("date_fin"))
    cible = date(mission.get("date_cible"))
    r = {
        "reste": k["reste"], "velocite_moyenne": k["velocite_moyenne"],
        "ajout_moyen": k["ajout_moyen"], "consommation_nette": round(net, 1),
        "date_cible": cible.isoformat() if cible else None,
        "sprints_restants": None, "date_fin_estimee": None,
        "ecart_jours": None, "ecart_sprints": None, "atteignable": True,
    }
    if k["reste"] <= 0:
        r["sprints_restants"] = 0
        r["date_fin_estimee"] = fin_dernier.isoformat() if fin_dernier else None
    elif net <= 0 or k["reste"] / net > HORIZON_SPRINTS:
        r["atteignable"] = False  # le backlog ne se vide pas, ou presque pas
        return r
    else:
        r["sprints_restants"] = math.ceil(k["reste"] / net)
        if fin_dernier:
            r["date_fin_estimee"] = (
                fin_dernier + dt.timedelta(days=duree * r["sprints_restants"])
            ).isoformat()
    fin = date(r["date_fin_estimee"])
    if fin and cible:
        r["ecart_jours"] = (fin - cible).days
        r["ecart_sprints"] = math.ceil(r["ecart_jours"] / duree) if r["ecart_jours"] > 0 else 0
    return r


def alertes(mission, sprints, risques, decisions, aujourdhui=None):
    """Déclencheurs de la méthode. Niveau 2 = projet, niveau 3 = sponsor."""
    auj = aujourdhui or dt.date.today()
    s = seuils(mission)
    sp = _tries(sprints)
    out = []

    def ajouter(code, niveau, titre, detail):
        out.append({"code": code, "niveau": niveau, "titre": titre, "detail": detail})

    if len(sp) >= 2:
        a, b = sp[-2], sp[-1]
        taux = [
            _n(x.get("realise")) / _n(x.get("prevu")) if _n(x.get("prevu")) > 0 else None
            for x in (a, b)
        ]
        if all(t is not None and t < s["taux_realisation_min"] for t in taux):
            ajouter(
                "realisation", 2, "Réalisation inférieure au prévu deux sprints de suite",
                f"Sprint {a['numero']} : {pc(taux[0])}, sprint {b['numero']} : {pc(taux[1])} "
                f"(seuil {pc(s['taux_realisation_min'])}).",
            )
        if all(_n(x.get("ajoute")) > s["marge_ajout"] for x in (a, b)):
            ajouter(
                "perimetre", 2, "Ajouts au backlog supérieurs à la marge deux sprints de suite",
                f"Sprint {a['numero']} : {_n(a.get('ajoute')):g} pts, sprint {b['numero']} : "
                f"{_n(b.get('ajoute')):g} pts (marge {s['marge_ajout']:g} pts).",
            )
        m = [x.get("moral") for x in sp[-3:]]
        if len(m) == 3 and all(isinstance(v, int) for v in m) and m[0] > m[1] > m[2]:
            ajouter("moral", 2, "Moral de l'équipe en baisse deux sprints de suite",
                    f"Moral sur 5 : {m[0]} puis {m[1]} puis {m[2]}.")

    att = atterrissage(sp, mission)
    if att:
        if not att["atteignable"]:
            ajouter(
                "atterrissage", 3, "Le reste à faire ne diminue plus assez",
                f"Vélocité moyenne {att['velocite_moyenne']:g} pts, ajouts moyens "
                f"{att['ajout_moyen']:g} pts par sprint : aucune date de fin réaliste.",
            )
        elif att["ecart_sprints"] is not None and att["ecart_sprints"] > s["retard_sprints_max"]:
            ajouter(
                "atterrissage", 3, "L'atterrissage dépasse la date cible",
                f"Fin estimée le {fr(att['date_fin_estimee'])} pour une cible au "
                f"{fr(att['date_cible'])} : {att['ecart_sprints']} sprints de retard.",
            )

    for r in risques:
        if r.get("etat") not in OUVERTS:
            continue
        ech = date(r.get("echeance"))
        if r.get("nature") == "adherence" and ech:
            jours = (ech - auj).days
            if jours <= s["adherence_critique_jours"]:
                ajouter("adherence", 3, f"Adhérence à échéance proche : {r['titre']}",
                        f"Échéance le {fr(ech)} ({jours} jours), toujours ouverte.")
            elif jours <= s["adherence_alerte_jours"]:
                ajouter("adherence", 2, f"Adhérence à surveiller : {r['titre']}",
                        f"Échéance le {fr(ech)} ({jours} jours), toujours ouverte.")
        if _n(r.get("probabilite")) >= 3 and _n(r.get("impact")) >= 3:
            manques = [lib for champ, lib in (("porteur", "porteur"), ("plan_action", "plan d'action"))
                       if not (r.get(champ) or "").strip()]
            maj = date(r.get("maj_le"))
            if manques:
                ajouter("risque", 3, f"Risque critique non traité : {r['titre']}",
                        "Sans " + " ni ".join(manques) + ".")
            elif maj and (auj - maj).days > s["risque_stagnation_jours"]:
                ajouter("risque", 3, f"Risque critique sans évolution : {r['titre']}",
                        f"Dernière mise à jour le {fr(maj)}.")

    for d in decisions:
        ech = date(d.get("echeance"))
        if d.get("nature") == "decision" and d.get("statut") == "à prendre" and ech and ech < auj:
            ajouter("decision", 2, f"Décision en retard : {d['titre']}",
                    f"Attendue le {fr(ech)}, toujours à prendre.")

    return sorted(out, key=lambda a: -a["niveau"])


def tendance(liste_alertes):
    niveau = max((a["niveau"] for a in liste_alertes), default=0)
    return "rouge" if niveau >= 3 else "orange" if niveau == 2 else "vert"


def controles(risques, decisions, contenu_meteo="", aujourdhui=None):
    """Contrôles de cohérence déterministes, complétés ensuite par le LLM."""
    auj = aujourdhui or dt.date.today()
    out = []

    def ajouter(gravite, constat, suggestion):
        out.append({"origine": "règle", "gravite": gravite,
                    "constat": constat, "suggestion": suggestion})

    for r in risques:
        if r.get("etat") not in OUVERTS:
            continue
        nom = ("Adhérence" if r.get("nature") == "adherence" else "Risque") + f" « {r['titre']} »"
        if not (r.get("porteur") or "").strip():
            ajouter("moyenne", f"{nom} sans porteur.", "Désigner un porteur.")
        if r.get("nature") == "adherence" and not date(r.get("echeance")):
            ajouter("moyenne", f"{nom} sans échéance.", "Obtenir une date engagée.")
        if _n(r.get("probabilite")) * _n(r.get("impact")) >= 6 and not (r.get("plan_action") or "").strip():
            ajouter("haute", f"{nom} de criticité élevée sans plan d'action.",
                    "Formaliser un plan de remédiation ou de contournement.")
    for d in decisions:
        ech = date(d.get("echeance"))
        if d.get("nature") == "action" and d.get("statut") == "à faire" and ech and ech < auj:
            ajouter("basse", f"Action en retard : « {d['titre']} » (échéance {fr(ech)}).",
                    "Relancer le porteur ou replanifier.")
    if "À qualifier" in contenu_meteo:
        ajouter("haute", "Au moins un point de vigilance n'a pas d'impact qualifié.",
                "Écrire l'impact sur le périmètre, le planning, le budget ou la qualité.")
    if "À définir" in contenu_meteo:
        ajouter("moyenne", "Au moins un point de vigilance n'a pas d'action associée.",
                "Associer une action ou une demande d'arbitrage.")
    return out


def instantane(risques):
    """Photo du registre à un instant : criticité et état de chaque risque."""
    return {str(r["id"]): {"criticite": _n(r.get("probabilite")) * _n(r.get("impact")),
                           "etat": r.get("etat")} for r in risques}


def evolution(risques, photo):
    """Compare chaque risque à la photo de la dernière session.

    Sans photo, on retombe sur l'évolution saisie à la main.
    """
    out = []
    for r in risques:
        crit = _n(r.get("probabilite")) * _n(r.get("impact"))
        avant = (photo or {}).get(str(r["id"]))
        if photo is None:
            evo, source = r.get("evolution") or "stable", "saisie"
        elif avant is None:
            evo, source = "nouveau", "calcul"
        elif r.get("etat") == "clos" and avant.get("etat") != "clos":
            evo, source = "clos", "calcul"
        elif crit > _n(avant.get("criticite")):
            evo, source = "hausse", "calcul"
        elif crit < _n(avant.get("criticite")):
            evo, source = "baisse", "calcul"
        else:
            evo, source = "stable", "calcul"
        out.append(dict(r, criticite=crit, evolution_session=evo, evolution_source=source,
                        criticite_precedente=(avant or {}).get("criticite"),
                        etat_precedent=(avant or {}).get("etat")))
    return out
