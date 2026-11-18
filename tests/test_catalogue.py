"""Catalogue de blocs de chiffrage : contenu, application à une mission, personnalisation, MCP."""
import asyncio
import os
import sys
import tempfile
import unittest

DOSSIER = tempfile.mkdtemp(prefix="copilote-catalogue-")
os.environ.pop("COPILOTE_DB", None)
os.environ["COPILOTE_MISSIONS"] = DOSSIER
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import catalogue  # noqa: E402
import db  # noqa: E402
import donnees  # noqa: E402


class Contenu(unittest.TestCase):
    def test_blocs_complets_et_croissants(self):
        c = catalogue.catalogue()
        self.assertGreaterEqual(len(c["blocs"]), 30)
        self.assertEqual(len({b["id"] for b in c["blocs"]}), len(c["blocs"]))
        for b in c["blocs"]:
            t = b["totaux"]
            self.assertTrue(t["rapide"] < t["moyen"] < t["long"], b["id"])
            self.assertTrue(set(r for n in b["niveaux"].values() for r in n) <= set(catalogue.ROLES), b["id"])
            textes = [b["criteres"][n] for n in catalogue.NIVEAUX]
            self.assertTrue(all(len(t) > 40 for t in textes), b["id"])  # un vrai critère, pas un libellé
            self.assertEqual(len(set(textes)), 3, b["id"])
        self.assertIn("recuperation-data", {b["id"] for b in c["blocs"]})


class Application(unittest.TestCase):
    def setUp(self):
        self.cle = db.creer_mission("Chiffrage par blocs")

    def test_detaille_par_role_rapproche_des_profils(self):
        with db.dans(self.cle):
            db.creer("profil", {"nom": "Ingénieur data", "metier": "Data", "tjm": 800})
            db.creer("profil", {"nom": "Pilote", "metier": "Pilotage de projet", "tjm": 1000})
            lignes = donnees.appliquer_bloc("recuperation-data", "long", "detaille", "L1", 2)
            self.assertEqual({l["profil"]: l["jours_probable"] for l in lignes},
                             {"Ingénieur data": 24, "Business analyst": 10, "Pilote": 6})
            de = next(l for l in lignes if l["profil"] == "Ingénieur data")
            self.assertEqual((de["jours_bas"], de["jours_haut"], de["confiance"]), (12, 36, "faible"))
            self.assertEqual((de["bloc"], de["niveau"], de["libelle"]), ("recuperation-data", "long", "Récupération de la data × 2"))
            self.assertIn("ni qui la possède", de["hypothese"])  # le critère du niveau justifie la ligne
            c = donnees.chiffrage()["modes"]["detaille"]
            self.assertEqual(c["base"]["retenu"], 40)
            self.assertEqual(db.journal("estimation")[0]["action"], "creation")

    def test_macro_une_ligne(self):
        with db.dans(self.cle):
            (l,) = donnees.appliquer_bloc("api-exposee", "rapide", "macro", "V1")
            self.assertEqual((l["mode"], l["jours_probable"], l["confiance"]), ("macro", 3, "forte"))
            ligne = donnees.chiffrage()["modes"]["macro"]["lignes"][0]
            self.assertEqual((ligne["bas"], ligne["retenu"], ligne["haut"]), (2.55, 3, 3.45))

    def test_refus(self):
        with db.dans(self.cle):
            for args in (("inconnu", "rapide"), ("api-exposee", "eclair"), ("api-exposee", "rapide", "autre")):
                with self.assertRaises(ValueError):
                    donnees.appliquer_bloc(*args)


class Personnalisation(unittest.TestCase):
    def test_surcharge_ajout_et_retrait(self):
        b = catalogue.bloc("api-exposee")
        perso = {**b, "niveaux": {**b["niveaux"], "rapide": {"Développeur": 2}}}
        self.assertEqual(catalogue.enregistrer("api-exposee", perso)["totaux"]["rapide"], 2)
        self.assertEqual(catalogue.bloc("api-exposee")["criteres"], b["criteres"])  # critères conservés
        nouveau = catalogue.enregistrer(None, {"nom": "Atelier d'idéation", "famille": "Mes blocs", "niveaux": {
            "rapide": {"UX / UI": 1}, "moyen": {"UX / UI": 2}, "long": {"UX / UI": 4}},
            "criteres": {"rapide": "Sujet cadré, participants connus.", "moyen": "", "long": ""}})
        self.assertEqual(nouveau["id"], "atelier-d-ideation")
        self.assertEqual(nouveau["criteres"]["rapide"], "Sujet cadré, participants connus.")
        catalogue.retirer("api-exposee")
        self.assertEqual(catalogue.bloc("api-exposee")["totaux"]["rapide"], 3)
        catalogue.retirer("atelier-d-ideation")
        with self.assertRaises(ValueError):
            catalogue.bloc("atelier-d-ideation")
        with self.assertRaises(ValueError):
            catalogue.enregistrer("x", {"nom": "Incomplet", "niveaux": {"rapide": {"QA": 1}}})


class Mcp(unittest.TestCase):
    def test_outils(self):
        from mcp import Client
        import mcp_server
        cle = db.creer_mission("Par MCP")

        async def deroule():
            async with Client(mcp_server.serveur) as c:
                lecture = await c.call_tool("catalogue_chiffrage", {"recherche": "data"})
                ecriture = await c.call_tool("chiffrer_avec_bloc", {"bloc": "recette", "niveau": "moyen", "mission": cle})
                erreur = await c.call_tool("chiffrer_avec_bloc", {"bloc": "recette", "niveau": "x", "mission": cle})
                return lecture, ecriture, erreur
        lecture, ecriture, erreur = asyncio.run(deroule())
        self.assertTrue(all("data" in f"{b['nom']} {b['famille']} {b['description']}".lower()
                            for b in lecture.structured_content["blocs"]))
        self.assertEqual(len(ecriture.structured_content["lignes_creees"]), 2)
        self.assertTrue(erreur.is_error)
        self.assertIn("Niveau inconnu", erreur.content[0].text)
        with db.dans(cle):
            self.assertEqual(db.journal("estimation")[0]["origine"], "assistant (MCP)")


if __name__ == "__main__":
    unittest.main()
