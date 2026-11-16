"""Assemblage de la météo hebdomadaire.

Les chiffres et les tableaux sont produits ici à partir des données ; seules la
synthèse, la formulation des points de vigilance et les prochaines étapes peuvent
venir du LLM.
"""
import datetime as dt

import calculs

LIBELLE = {"vert": "VERT — dans les temps", "orange": "ORANGE — à risque",
           "rouge": "ROUGE — trajectoire menacée"}


fr = calculs.fr


def semaine(aujourdhui=None):
    auj = aujourdhui or dt.date.today()
    lundi = auj - dt.timedelta(days=auj.weekday())
    vendredi = lundi + dt.timedelta(days=4)
    return f"Semaine {auj.isocalendar()[1]} (du {fr(lundi)} au {fr(vendredi)})"


def donnees(mission, jalons, livrables, sprints, risques, decisions, aujourdhui=None):
    """Tout ce que la météo peut citer. C'est aussi l'entrée donnée au LLM."""
    auj = aujourdhui or dt.date.today()
    al = calculs.alertes(mission, sprints, risques, decisions, auj)
    ouverts = [r for r in risques if r.get("etat") in calculs.OUVERTS]
    return {
        "date": auj.isoformat(),
        "semaine": semaine(auj),
        "mission": {k: mission.get(k) for k in (
            "nom", "client", "objectif_business", "objectif_solution", "objectif_projet",
            "hypotheses", "date_cible")},
        "tendance_calculee": calculs.tendance(al),
        "alertes": al,
        "kpi": calculs.kpi(sprints),
        "atterrissage": calculs.atterrissage(sprints, mission),
        "livrables": livrables,
        "risques_ouverts": ouverts,
        "decisions_a_prendre": [d for d in decisions
                                if d.get("nature") == "decision" and d.get("statut") == "à prendre"],
        "actions_a_faire": [d for d in decisions
                            if d.get("nature") == "action" and d.get("statut") == "à faire"],
        "jalons_a_venir": [j for j in jalons if j.get("statut") != "atteint"][:5],
    }


def rediger_sans_llm(d):
    """Version factuelle, sans rédaction : les impacts restent à qualifier par le pilote."""
    att, al = d["atterrissage"], d["alertes"]
    if not att:
        synthese = "Aucun sprint saisi : la trajectoire ne peut pas être évaluée."
    elif not att["atteignable"]:
        synthese = "Le reste à faire ne diminue plus assez : aucune date de fin réaliste n'est calculable."
    elif att["ecart_sprints"]:
        synthese = (f"Au rythme actuel, la fin est estimée au {fr(att['date_fin_estimee'])}, "
                    f"soit {att['ecart_sprints']} sprints après la cible.")
    else:
        synthese = (f"Au rythme actuel, la fin est estimée au {fr(att['date_fin_estimee'])}, "
                    "dans la cible.")
    synthese += f" {len(al)} alerte(s) active(s)." if al else " Aucune alerte active."

    points = [{"sujet": a["titre"], "point": a["detail"],
               "impact": "À qualifier", "action": "À définir"} for a in al]
    deja = " ".join(a["titre"] for a in al)
    for r in d["risques_ouverts"]:
        if len(points) >= 5:
            break
        if r["titre"] not in deja:
            points.append({"sujet": r["titre"], "point": r.get("description") or "—",
                           "impact": "À qualifier",
                           "action": r.get("plan_action") or "À définir"})
    etapes = [f"{j['libelle']} — {fr(j.get('date'))}" for j in d["jalons_a_venir"][:3]]
    etapes += [f"{a['titre']} ({a.get('porteur') or 'sans porteur'}, {fr(a.get('echeance'))})"
               for a in d["actions_a_faire"][:3]]
    return {"synthese": synthese, "points_vigilance": points[:5], "prochaines_etapes": etapes}


def _c(valeur):
    return str(valeur if valeur not in (None, "") else "—").replace("|", "/").replace("\n", " ")


def _tableau(entetes, lignes):
    if not lignes:
        return "_Aucun élément._"
    out = ["| " + " | ".join(entetes) + " |", "|" + "---|" * len(entetes)]
    out += ["| " + " | ".join(_c(v) for v in ligne) + " |" for ligne in lignes]
    return "\n".join(out)


def assembler(d, redaction):
    k, att = d["kpi"], d["atterrissage"]
    out = [f"# Météo — {d['mission'].get('nom') or 'Mission'} — {d['semaine']}", "",
           f"**Tendance globale : {LIBELLE[d['tendance_calculee']]}**", "",
           "## Synthèse", "", redaction["synthese"], "", "## Trajectoire", ""]
    if k and att:
        taux = calculs.pc(k["taux_realisation"]) if k["taux_realisation"] is not None else "—"
        if not att["atteignable"]:
            fin, ecart = "Non calculable", "—"
        else:
            fin = fr(att["date_fin_estimee"])
            ecart = ("—" if att["ecart_sprints"] is None else
                     "Dans la cible" if att["ecart_sprints"] == 0 else
                     f"+{att['ecart_sprints']} sprints")
        out.append(_tableau(["Indicateur", "Valeur"], [
            (f"Sprint {k['sprint']} : réalisé / prévu", f"{k['realise']:g} / {k['prevu']:g} pts ({taux})"),
            ("Points ajoutés au backlog", f"{k['ajoute']:g} pts"),
            ("Reste à faire", f"{k['reste']:g} pts"),
            (f"Vélocité moyenne ({k['nb_sprints_moyenne']} derniers sprints)", f"{k['velocite_moyenne']:g} pts"),
            ("Consommation nette du backlog", f"{att['consommation_nette']:g} pts par sprint"),
            ("Fin estimée", fin),
            ("Date cible", fr(att["date_cible"])),
            ("Écart à la cible", ecart),
            ("Anomalies créées / corrigées", f"{k['anomalies_creees']} / {k['anomalies_corrigees']}"),
            ("Moral de l'équipe", f"{k['moral']} / 5" if k["moral"] else "—"),
        ]))
    else:
        out.append("_Aucun sprint saisi._")
    out += ["", "## Avancement par livrable", "",
            _tableau(["Chantier", "Livrable", "Avancement", "Statut", "Tendance"],
                     [(l.get("chantier"), l.get("libelle"),
                       f"{l['avancement']} %" if l.get("avancement") is not None else "—",
                       l.get("statut"), l.get("tendance")) for l in d["livrables"]]),
            "", "## Points de vigilance", "",
            _tableau(["Sujet", "Point", "Impact", "Action"],
                     [(p["sujet"], p["point"], p["impact"], p["action"])
                      for p in redaction["points_vigilance"]]),
            "", "## Décisions attendues", "",
            _tableau(["Décision", "Décideur", "Instance", "Échéance"],
                     [(x.get("titre"), x.get("porteur"), x.get("instance"), fr(x.get("echeance")))
                      for x in d["decisions_a_prendre"]]),
            "", "## Prochaines étapes", ""]
    out += [f"- {e}" for e in redaction["prochaines_etapes"]] or ["_Aucune._"]
    return "\n".join(out) + "\n"
