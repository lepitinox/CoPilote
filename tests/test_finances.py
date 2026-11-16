"""Chiffrage (deux modes), budget et attentes du client : calculs purs."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import finances  # noqa: E402

AUJ = dt.date(2026, 11, 16)
PROFILS = [{"nom": "Dev", "tjm": 600, "cout_journalier": 400, "raf_jours": 10},
           {"nom": "Chef", "tjm": 1000, "cout_journalier": 700, "raf_jours": 2}]


class Chiffrage(unittest.TestCase):
    def test_macro_abaque_et_fourchette(self):
        m = {"chiffrage": {"majorations": {"pilotage": 0.1, "qualite": 0, "contingence": 0}}}
        c = finances.chiffrage(m, [{"mode": "macro", "lot": "V1", "libelle": "A", "taille": "M", "confiance": "faible"}], PROFILS)
        l = c["modes"]["macro"]["lignes"][0]
        self.assertEqual((l["bas"], l["retenu"], l["haut"]), (5, 10, 15))  # M = 10 j, ± 50 %
        self.assertEqual(c["tjm_moyen"], 800)  # moyenne des profils
        self.assertEqual(c["modes"]["macro"]["total_jours"]["retenu"], 11)  # + 10 % de pilotage
        self.assertEqual(c["modes"]["macro"]["montant"], 8800)

    def test_detaille_pert_valorise_au_profil(self):
        c = finances.chiffrage({"chiffrage": {"mode_retenu": "detaille", "majorations": {"pilotage": 0, "qualite": 0, "contingence": 0}}}, [
            {"mode": "detaille", "lot": "V1", "libelle": "A", "profil": "Dev", "jours_bas": 4, "jours_probable": 6, "jours_haut": 14},
            {"mode": "macro", "lot": "V1", "libelle": "A", "taille": "S"}], PROFILS)
        l = c["modes"]["detaille"]["lignes"][0]
        self.assertEqual(l["retenu"], 7)  # (4 + 4 × 6 + 14) / 6
        self.assertEqual(l["montant"], 4200)
        self.assertEqual(c["retenu"]["montant"], 4200)
        self.assertEqual(c["comparaison"], [{"lot": "V1", "macro": 5, "detaille": 7, "ecart": 0.4}])


class Budget(unittest.TestCase):
    def test_atterrissage_marge_et_alertes(self):
        b = finances.budget(
            {"budget_vendu": 12000}, PROFILS,
            [{"mois": "2026-10", "profil": "Dev", "jours": 5}, {"mois": "2026-11", "profil": "Chef", "jours": 1},
             {"mois": "2026-11", "profil": "Inconnu", "jours": 1}],
            [{"montant": 500, "statut": "payée"}, {"montant": 300, "statut": "prévue"}],
            [{"libelle": "Acompte", "montant": 3000, "statut": "payée", "date_prevue": "2026-10-01"},
             {"libelle": "Recette", "montant": 3000, "statut": "à facturer", "date_prevue": "2026-11-01"}],
            [{"avancement": 20}], aujourdhui=AUJ)
        self.assertEqual(b["consomme"], 5 * 600 + 1000 + 500)
        self.assertEqual(b["raf"], 10 * 600 + 2 * 1000 + 300)
        self.assertEqual(b["atterrissage"], 12800)
        self.assertEqual(b["ecart"], -800)
        self.assertEqual(b["marge"], 12000 - ((15 * 400) + (3 * 700) + 800))
        self.assertEqual([x["code"] for x in b["alertes"]], ["budget", "consommation", "facture", "profil"])
        self.assertEqual([x["cumul"] for x in b["par_mois"]], [3000, 4000])

    def test_reference_chiffree_sans_budget_vendu(self):
        b = finances.budget({}, PROFILS, [], [], [], [], {"retenu": {"montant": 5000}}, AUJ)
        self.assertEqual((b["reference"], b["reference_source"]), (5000, "chiffrage"))


class Attentes(unittest.TestCase):
    def test_evolution_tiree_de_l_historique_et_alertes(self):
        liste = [{"id": 1, "partie_prenante": "Sponsor", "libelle": "Délai", "priorite": 1, "satisfaction": 2,
                  "position": "alignée", "revue_le": "2026-11-10"},
                 {"id": 2, "partie_prenante": "Métier", "libelle": "Signature", "priorite": 2, "satisfaction": 4,
                  "position": "à recadrer", "prochaine_action": "", "revue_le": "2026-09-01"}]
        historique = [  # le plus récent d'abord
            {"action": "modification", "ligne": 1, "horodatage": "2026-11-10T10:00:00",
             "avant": {"satisfaction": 4}, "apres": {"satisfaction": 2}},
            {"action": "modification", "ligne": 1, "horodatage": "2026-10-01T10:00:00",
             "avant": {"satisfaction": 3}, "apres": {"satisfaction": 4}}]
        r = finances.attentes(liste, historique, AUJ)
        a, b = r["attentes"]
        self.assertEqual((a["satisfaction_precedente"], a["evolution"], a["revue_due"]), (4, "baisse", False))
        self.assertEqual((b["evolution"], b["revue_due"]), (None, True))
        self.assertEqual([x["code"] for x in r["alertes"]], ["attente", "recadrage"])


if __name__ == "__main__":
    unittest.main()
