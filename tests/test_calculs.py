import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import calculs  # noqa: E402
import meteo  # noqa: E402

AUJ = dt.date(2026, 11, 16)
MISSION = {"nom": "Test", "date_cible": "2027-01-31", "duree_sprint_jours": 14, "seuils": {}}


def sprint(n, prevu, realise, ajoute, reste, moral=4, fin=None):
    return {"numero": n, "date_fin": fin or (dt.date(2026, 9, 1) + dt.timedelta(days=14 * n)).isoformat(),
            "prevu": prevu, "realise": realise, "ajoute": ajoute, "reste": reste,
            "anomalies_creees": 2, "anomalies_corrigees": 1, "moral": moral}


def codes(alertes):
    return [(a["code"], a["niveau"]) for a in alertes]


class Atterrissage(unittest.TestCase):
    def test_projection(self):
        sp = [sprint(1, 100, 100, 0, 300), sprint(2, 100, 100, 0, 200)]
        a = calculs.atterrissage(sp, MISSION)
        self.assertEqual(a["sprints_restants"], 2)
        self.assertEqual(a["date_fin_estimee"], "2026-10-27")  # 29/09 + 2 x 14 jours
        self.assertEqual(a["ecart_sprints"], 0)

    def test_ajouts_deduits_de_la_velocite(self):
        a = calculs.atterrissage([sprint(1, 100, 100, 50, 500)], MISSION)
        self.assertEqual(a["consommation_nette"], 50)
        self.assertEqual(a["sprints_restants"], 10)

    def test_backlog_qui_grossit(self):
        a = calculs.atterrissage([sprint(1, 100, 40, 60, 500)], MISSION)
        self.assertFalse(a["atteignable"])
        self.assertIsNone(a["date_fin_estimee"])

    def test_sans_sprint(self):
        self.assertIsNone(calculs.atterrissage([], MISSION))
        self.assertIsNone(calculs.kpi([]))

    def test_retard_en_sprints(self):
        a = calculs.atterrissage([sprint(1, 100, 50, 0, 1000)], MISSION)
        self.assertEqual(a["sprints_restants"], 20)
        self.assertGreater(a["ecart_sprints"], 1)

    def test_horizon_irrealiste(self):
        a = calculs.atterrissage([sprint(1, 100, 65, 60, 1000)], MISSION)
        self.assertFalse(a["atteignable"])


class Alertes(unittest.TestCase):
    def test_aucune_alerte(self):
        sp = [sprint(1, 100, 95, 10, 200), sprint(2, 100, 98, 10, 110)]
        al = calculs.alertes(MISSION, sp, [], [], AUJ)
        self.assertEqual(al, [])
        self.assertEqual(calculs.tendance(al), "vert")

    def test_realisation_deux_sprints(self):
        sp = [sprint(1, 100, 70, 0, 200), sprint(2, 100, 75, 0, 125)]
        self.assertIn(("realisation", 2), codes(calculs.alertes(MISSION, sp, [], [], AUJ)))

    def test_realisation_un_seul_sprint_ne_declenche_pas(self):
        sp = [sprint(1, 100, 95, 0, 200), sprint(2, 100, 60, 0, 140)]
        self.assertNotIn(("realisation", 2), codes(calculs.alertes(MISSION, sp, [], [], AUJ)))

    def test_perimetre_et_seuil_personnalise(self):
        sp = [sprint(1, 100, 100, 45, 200), sprint(2, 100, 100, 45, 145)]
        self.assertIn(("perimetre", 2), codes(calculs.alertes(MISSION, sp, [], [], AUJ)))
        large = dict(MISSION, seuils={"marge_ajout": 50})
        self.assertNotIn(("perimetre", 2), codes(calculs.alertes(large, sp, [], [], AUJ)))

    def test_moral(self):
        sp = [sprint(1, 100, 100, 0, 300, 4), sprint(2, 100, 100, 0, 200, 3), sprint(3, 100, 100, 0, 100, 2)]
        self.assertIn(("moral", 2), codes(calculs.alertes(MISSION, sp, [], [], AUJ)))

    def test_atterrissage_niveau_3(self):
        al = calculs.alertes(MISSION, [sprint(1, 100, 50, 0, 1000)], [], [], AUJ)
        self.assertIn(("atterrissage", 3), codes(al))
        self.assertEqual(calculs.tendance(al), "rouge")

    def test_adherence_selon_echeance(self):
        def adh(jours, etat="ouvert"):
            return {"nature": "adherence", "titre": "API", "etat": etat,
                    "echeance": (AUJ + dt.timedelta(days=jours)).isoformat()}
        self.assertEqual(codes(calculs.alertes(MISSION, [], [adh(40)], [], AUJ)), [])
        self.assertEqual(codes(calculs.alertes(MISSION, [], [adh(25)], [], AUJ)), [("adherence", 2)])
        self.assertEqual(codes(calculs.alertes(MISSION, [], [adh(10)], [], AUJ)), [("adherence", 3)])
        self.assertEqual(codes(calculs.alertes(MISSION, [], [adh(10, "clos")], [], AUJ)), [])

    def test_risque_critique(self):
        r = {"nature": "risque", "titre": "R", "etat": "ouvert", "probabilite": 3, "impact": 3,
             "porteur": "", "plan_action": "", "maj_le": AUJ.isoformat()}
        self.assertEqual(codes(calculs.alertes(MISSION, [], [r], [], AUJ)), [("risque", 3)])
        traite = dict(r, porteur="PO", plan_action="Plan")
        self.assertEqual(codes(calculs.alertes(MISSION, [], [traite], [], AUJ)), [])
        ancien = dict(traite, maj_le="2026-08-01")
        self.assertEqual(codes(calculs.alertes(MISSION, [], [ancien], [], AUJ)), [("risque", 3)])

    def test_decision_en_retard(self):
        d = {"nature": "decision", "titre": "D", "statut": "à prendre", "echeance": "2026-11-10"}
        self.assertEqual(codes(calculs.alertes(MISSION, [], [], [d], AUJ)), [("decision", 2)])
        self.assertEqual(codes(calculs.alertes(MISSION, [], [], [dict(d, statut="prise")], AUJ)), [])

    def test_donnees_incompletes(self):
        sp = [{"numero": 1}, {"numero": 2, "prevu": None, "realise": None}]
        calculs.alertes(MISSION, sp, [{"etat": "ouvert", "titre": "x"}], [{}], AUJ)  # ne doit pas lever


class Meteo(unittest.TestCase):
    def test_meteo_sans_llm(self):
        sp = [sprint(1, 100, 70, 50, 900), sprint(2, 100, 60, 55, 895)]
        d = meteo.donnees(MISSION, [], [{"chantier": "A|B", "libelle": "L", "avancement": 10,
                                         "statut": "s", "tendance": "vert"}], sp, [], [], AUJ)
        texte = meteo.assembler(d, meteo.rediger_sans_llm(d))
        self.assertIn("Semaine 47 (du 16 novembre 2026 au 20 novembre 2026)", texte)
        self.assertIn("ROUGE", texte)
        self.assertIn("À qualifier", texte)
        self.assertIn("A/B", texte)  # barre verticale neutralisée dans les tableaux
        remarques = calculs.controles([], [], texte, AUJ)
        self.assertTrue(any("impact qualifié" in r["constat"] for r in remarques))


if __name__ == "__main__":
    unittest.main()
