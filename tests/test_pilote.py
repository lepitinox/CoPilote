"""Besoins du pilote : glissements, trois réponses, page À traiter, préparation de séance."""
import asyncio
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest

DOSSIER = tempfile.mkdtemp(prefix="copilote-pilote-")
os.environ.pop("COPILOTE_DB", None)
os.environ["COPILOTE_MISSIONS"] = DOSSIER
os.environ["COPILOTE_MODELES"] = os.path.join(DOSSIER, "modeles")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import agenda  # noqa: E402
import db  # noqa: E402
import demo  # noqa: E402
import donnees  # noqa: E402
import exports  # noqa: E402
import pilote  # noqa: E402

AUJ = dt.date(2026, 11, 18)


def mission_demo(nom):
    cle = db.creer_mission(nom)
    with db.dans(cle):
        demo.charger(AUJ)
        agenda.proposer(True, AUJ)
    return cle


class Glissements(unittest.TestCase):
    def setUp(self):
        self.cle = db.creer_mission("Glissements")

    def test_reference_posee_puis_conservee(self):
        with db.dans(self.cle):
            j = donnees.creer_element("jalon", {"libelle": "Go-live", "date": "2027-01-15"}, AUJ)
            self.assertEqual(j["date_initiale"], "2027-01-15")
            donnees.modifier_element("jalon", j["id"], {"date": "2027-02-12"}, AUJ)
            donnees.modifier_element("jalon", j["id"], {"date": "2027-02-26"}, AUJ)
            g = next(x for x in pilote.glissements(AUJ)["jalon"] if x["id"] == j["id"])
            self.assertEqual((g["date_initiale"], g["glissement_jours"], g["reports"]), ("2027-01-15", 42, 2))
            alertes = pilote.alertes_glissements(pilote.glissements(AUJ), db.mission(), AUJ)
            self.assertEqual([a["code"] for a in alertes], ["glissement"])
            self.assertIn("6 semaines", alertes[0]["titre"])

    def test_jalon_sans_date_puis_date(self):
        with db.dans(self.cle):
            j = db.creer("jalon", {"libelle": "À dater"})
            self.assertIsNone(j["date_initiale"])
            self.assertEqual(db.modifier("jalon", j["id"], {"date": "2027-03-01"})["date_initiale"], "2027-03-01")

    def test_jalon_depasse(self):
        with db.dans(self.cle):
            db.creer("jalon", {"libelle": "Recette", "date": "2026-11-01", "statut": "à venir"})
            g = pilote.glissements(AUJ)
            self.assertTrue(g["jalon"][0]["depasse"])
            self.assertEqual(pilote.alertes_glissements(g, db.mission(), AUJ)[0]["code"], "jalon_depasse")


class Reponses(unittest.TestCase):
    def test_demo(self):
        with db.dans(mission_demo("Réponses")):
            r = pilote.reponses(AUJ)
        self.assertEqual(r["delai"]["etat"], "rouge")  # 8 sprints après la cible
        self.assertEqual(r["budget"]["etat"], "orange")  # dépassement de 2 %
        self.assertEqual(r["client"]["etat"], "orange")  # deux attentes à recadrer
        self.assertIn("3,0", r["client"]["phrase"])

    def test_mission_vide(self):
        with db.dans(db.creer_mission("Vide")):
            r = pilote.reponses(AUJ)
        self.assertEqual({v["etat"] for v in r.values()}, {"inconnu"})


class ATraiter(unittest.TestCase):
    def test_demo_et_actions_directes(self):
        with db.dans(mission_demo("À traiter")):
            t = pilote.a_traiter(AUJ)
            genres = {(i["groupe"], i["genre"]) for i in t["items"]}
            self.assertTrue({("maintenant", "decision"), ("maintenant", "action"), ("maintenant", "risque"),
                             ("maintenant", "facture"), ("maintenant", "attente"), ("semaine", "meteo")} <= genres)
            self.assertEqual([i["groupe"] for i in t["items"]], sorted([i["groupe"] for i in t["items"]],
                             key=["maintenant", "semaine", "surveiller"].index))
            facture = next(i for i in t["items"] if i["genre"] == "facture")
            a = facture["actions"][0]
            donnees.modifier_element(a["table"], a["id"], a["champs"], AUJ)
            self.assertFalse(any(i["genre"] == "facture" for i in pilote.a_traiter(AUJ)["items"]))

    def test_reunions_de_la_semaine(self):
        with db.dans(mission_demo("Réunions")):
            semaine_suivante = AUJ + dt.timedelta(days=12)  # le sprint de référence commence le 30 novembre
            reunions = [i for i in pilote.a_traiter(semaine_suivante)["items"] if i["genre"] == "reunion"]
        self.assertTrue(reunions)
        self.assertTrue(all(i["actions"][0].get("seance") for i in reunions))
        self.assertFalse(any("Mêlée" in i["titre"] for i in reunions))


class Seance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cle = mission_demo("Séances")

    def test_chaque_instance_tient_dans_sa_duree(self):
        with db.dans(self.cle):
            for inst in db.lister("instance"):
                s = pilote.preparer_seance(inst["id"], AUJ)
                self.assertEqual(s["depassement_minutes"], 0, inst["nom"])
                self.assertLessEqual(sum(p["minutes"] for p in s["ordre_du_jour"]), s["duree"], inst["nom"])

    def test_contenu_selon_le_type(self):
        with db.dans(self.cle):
            par_nom = {i["nom"]: pilote.preparer_seance(i["id"], AUJ) for i in db.lister("instance")}
        comite = par_nom["Comité sponsor"]
        self.assertEqual(comite["type"], "comite")
        self.assertTrue({"trajectoire", "decisions", "budget"} <= {p["cle"] for p in comite["ordre_du_jour"]})
        self.assertEqual(len(comite["messages_cles"]), 3)
        retro = par_nom["Rétrospective"]
        self.assertEqual([p["cle"] for p in retro["ordre_du_jour"]], ["ouverture", "sprint", "echanges", "cloture"])
        self.assertNotIn("risques", {p["cle"] for p in par_nom["Planification de sprint"]["ordre_du_jour"]})
        self.assertEqual(par_nom["Mêlée quotidienne"]["ordre_du_jour"], [])

    def test_export_powerpoint(self):
        from pptx import Presentation
        with db.dans(self.cle):
            comite = next(i for i in db.lister("instance") if i["nom"] == "Comité sponsor")
            octets, _ = exports.exporter("seance", "pptx", comite["id"], AUJ)
        titres = [s.shapes.title.text for s in Presentation(io.BytesIO(octets)).slides if s.shapes.title]
        self.assertIn("Comité sponsor — ordre du jour", titres)
        self.assertIn("Décisions à obtenir", titres)


class Hypotheses(unittest.TestCase):
    def test_invalidation_cree_un_risque_relie_une_seule_fois(self):
        with db.dans(db.creer_mission("Hypothèses")):
            h = donnees.creer_element("hypothese", {"libelle": "API livrée avant la recette", "categorie": "planning",
                                                    "impact": "La recette glisse.", "lot": "V1", "porteur": "Tech lead"}, AUJ)
            self.assertEqual((h["statut"], h["cree_le"]), ("à vérifier", AUJ.isoformat()))
            h = donnees.modifier_element("hypothese", h["id"], {"statut": "invalidée"}, AUJ)
            r = db.lire("risque", h["risque_id"])
            self.assertEqual((r["titre"], r["probabilite"], r["lot"], r["porteur"]),
                             ("Hypothèse invalidée : API livrée avant la recette", 3, "V1", "Tech lead"))
            self.assertTrue(r["description"].startswith("La recette glisse."))
            self.assertEqual(h["verifiee_le"], AUJ.isoformat())
            donnees.modifier_element("hypothese", h["id"], {"statut": "à vérifier"}, AUJ)
            donnees.modifier_element("hypothese", h["id"], {"statut": "invalidée"}, AUJ)
            self.assertEqual(len(db.lister("risque")), 1)  # le risque existant est réutilisé

    def test_bloc_long_cree_une_hypothese_de_chiffrage(self):
        with db.dans(db.creer_mission("Bloc long")):
            donnees.appliquer_bloc("recuperation-data", "long", "macro", "L1")
            donnees.appliquer_bloc("recuperation-data", "rapide", "macro", "L1")
            (h,) = db.lister("hypothese")
            self.assertEqual((h["categorie"], h["statut"], h["lot"]), ("chiffrage", "à vérifier", "L1"))
            self.assertIn("20 j", h["impact"])

    def test_reprise_de_l_ancien_texte(self):
        with db.dans(db.creer_mission("Ancienne")):
            db.modifier("mission", 1, {"hypotheses": "Équipe complète ; API livrée\nDonnées disponibles.",
                                       "hypotheses_reprises": None})
            db.initialiser()
            db.initialiser()  # une seule reprise
            self.assertEqual([h["libelle"] for h in db.lister("hypothese")], ["Équipe complète", "API livrée", "Données disponibles"])

    def test_a_traiter_seance_et_incertitude(self):
        with db.dans(mission_demo("Hypothèses démo")):
            genres = {i["genre"] for i in pilote.a_traiter(AUJ)["items"]}
            self.assertIn("hypothese", genres)
            e = db.lister("lot_element", "axe = 'prerequis'")[0]
            donnees.modifier_element("lot_element", e["id"], {"statut": "bloquant"}, AUJ)
            bloquants = [i for i in pilote.a_traiter(AUJ)["items"] if i["genre"] == "prerequis"]
            self.assertEqual((bloquants[0]["groupe"], bloquants[0]["actions"][0]["champs"]), ("maintenant", {"statut": "obtenu"}))
            comite = next(i for i in db.lister("instance") if i["nom"] == "Comité sponsor")
            s = pilote.preparer_seance(comite["id"], AUJ)
            self.assertIn("hypotheses", {p["cle"] for p in s["ordre_du_jour"]})
            self.assertEqual(s["depassement_minutes"], 0)
            inc = donnees.chiffrage()["modes"]["macro"]["incertitude"]
            self.assertGreater(inc["part_sans_information"], 0.5)  # le macro de la démo est surtout « faible »
            self.assertIsNotNone(inc["couverture_contingence"])


class Api(unittest.TestCase):
    def test_routes_et_mcp(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from mcp import Client
        import mcp_server
        import server
        cle = mission_demo("API pilote")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Requete)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            def get(chemin):
                with urllib.request.urlopen(urllib.request.Request(base + chemin, headers={"X-Mission": cle})) as r:
                    return r.read()
            self.assertIn("items", json.loads(get("/api/a_traiter")))
            self.assertIn("reponses", json.loads(get("/api/synthese")))
            with db.dans(cle):
                ident = next(i["id"] for i in db.lister("instance") if i["nom"] == "Synchro hebdo")
            self.assertEqual(json.loads(get(f"/api/instance/{ident}/seance"))["type"], "operationnel")
            self.assertEqual(get(f"/api/export/seance.pptx?instance={ident}")[:2], b"PK")
        finally:
            srv.shutdown()
            srv.server_close()

        async def deroule():
            async with Client(mcp_server.serveur) as c:
                return await c.call_tool("a_traiter", {"mission": cle}), await c.call_tool("preparer_seance", {"instance": ident, "mission": cle})
        a, s = asyncio.run(deroule())
        self.assertFalse(a.is_error or s.is_error)
        self.assertTrue(a.structured_content["items"])


if __name__ == "__main__":
    unittest.main()
