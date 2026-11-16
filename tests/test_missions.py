"""Plusieurs missions, historique des modifications, export et import JSON."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

DOSSIER = tempfile.mkdtemp(prefix="copilote-missions-")
os.environ.pop("COPILOTE_DB", None)
os.environ["COPILOTE_MISSIONS"] = DOSSIER
os.environ["COPILOTE_MODELES"] = os.path.join(DOSSIER, "modeles")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import db  # noqa: E402
import demo  # noqa: E402

AUJ = dt.date(2026, 11, 16)


class Missions(unittest.TestCase):
    def test_isolation_et_corbeille(self):
        a = db.creer_mission("Mission Alpha", "Client A")
        b = db.creer_mission("Mission Alpha")  # même nom : clé distincte
        self.assertEqual((a, b), ("mission-alpha", "mission-alpha-2"))
        with db.dans(a):
            db.creer("risque", {"titre": "Propre à Alpha"})
        with db.dans(b):
            self.assertEqual(db.lister("risque"), [])
        noms = {m["cle"]: m for m in db.missions()}
        self.assertEqual(noms[a]["client"], "Client A")
        db.supprimer_mission(b)
        self.assertFalse(db.existe(b))
        self.assertTrue(os.listdir(os.path.join(DOSSIER, "corbeille")))

    def test_cle_refusee(self):
        with self.assertRaises(db.Introuvable):
            db.chemin_de("../evasion")


class Historique(unittest.TestCase):
    def setUp(self):
        self.cle = db.creer_mission("Historique")

    def test_creation_modification_suppression_annulees(self):
        with db.dans(self.cle):
            r = db.creer("risque", {"titre": "API en retard", "probabilite": 2})
            db.modifier("risque", r["id"], {"probabilite": 3})
            db.modifier("risque", r["id"], {"probabilite": 3})  # sans changement : pas d'entrée
            hist = db.journal("risque")
            self.assertEqual([e["action"] for e in hist], ["modification", "creation"])
            self.assertEqual((hist[0]["avant"]["probabilite"], hist[0]["apres"]["probabilite"]), (2, 3))

            db.annuler(hist[0]["id"])
            self.assertEqual(db.lire("risque", r["id"])["probabilite"], 2)
            with self.assertRaises(db.Conflit):
                db.annuler(hist[0]["id"])  # déjà annulée

            db.supprimer("risque", r["id"])
            suppression = db.journal("risque")[0]
            self.assertEqual(suppression["action"], "suppression")
            db.annuler(suppression["id"])
            self.assertEqual(db.lire("risque", r["id"])["titre"], "API en retard")

    def test_conflit_si_modifie_depuis(self):
        with db.dans(self.cle):
            r = db.creer("jalon", {"libelle": "Go-live"})
            creation = db.journal("jalon")[0]
            db.modifier("jalon", r["id"], {"libelle": "Go-live V1"})
            with self.assertRaises(db.Conflit):
                db.annuler(creation["id"])
            self.assertIsNotNone(db.lire("jalon", r["id"]))

    def test_origine_et_chargement_silencieux(self):
        with db.dans(self.cle):
            with db.origine("proposition acceptée"):
                db.creer("decision", {"titre": "Industrialiser"})
            self.assertEqual(db.journal("decision")[0]["origine"], "proposition acceptée")
            demo.charger(AUJ)
            self.assertEqual(db.journal(), [])


class ExportImport(unittest.TestCase):
    def test_aller_retour(self):
        source = db.creer_mission("Source")
        with db.dans(source):
            demo.charger(AUJ)
            db.modifier("risque", db.lister("risque")[0]["id"], {"porteur": "Camille"})
            export = json.loads(json.dumps(db.exporter_mission()))  # comme un fichier
        self.assertEqual(export["format"], db.FORMAT)
        cle, avertissements = db.importer_mission(export)
        self.assertNotEqual(cle, source)
        self.assertEqual(avertissements, [])
        with db.dans(source):
            avant = {t: db.lister(t) for t in db.TABLES}
        with db.dans(cle):
            apres = {t: db.lister(t) for t in db.TABLES}
            hist = db.journal()
        self.assertEqual(avant, apres)
        self.assertEqual(hist[0]["action"], "import")
        self.assertEqual(hist[1]["apres"]["porteur"], "Camille")  # historique repris

    def test_fichier_refuse(self):
        for objet in ({}, {"format": "autre"}, {"format": db.FORMAT, "version": 99, "tables": {}},
                      {"format": db.FORMAT, "version": 1, "tables": {}}):
            with self.assertRaises(ValueError):
                db.importer_mission(objet)

    def test_table_inconnue_signalee(self):
        cle, avertissements = db.importer_mission({
            "format": db.FORMAT, "version": 1,
            "tables": {"mission": [{"id": 1, "nom": "Minimale"}], "budget_futur": [{"id": 1}]}})
        self.assertEqual(avertissements, ["Table inconnue ignorée : budget_futur."])
        with db.dans(cle):
            self.assertEqual(db.mission()["nom"], "Minimale")
            self.assertTrue(db.lister("metier"))  # catalogue par défaut recréé


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer
        import server
        db.demarrer()
        cls.serveur = ThreadingHTTPServer(("127.0.0.1", 0), server.Requete)
        cls.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()

    def appel(self, methode, chemin, corps=None, mission=None, brut=False):
        import urllib.error
        import urllib.request
        entetes = {"Content-Type": "application/json"} if corps is not None else {}
        if mission:
            entetes["X-Mission"] = mission
        req = urllib.request.Request(self.base + chemin, method=methode, headers=entetes,
                                     data=json.dumps(corps).encode() if corps is not None else None)
        try:
            with urllib.request.urlopen(req) as r:
                contenu = r.read()
                return r.status, (contenu if brut else json.loads(contenu))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_parcours(self):
        code, r = self.appel("POST", "/api/missions", {"nom": "Par l'API", "client": "X"})
        self.assertEqual(code, 200)
        cle = r["cle"]
        code, _ = self.appel("POST", "/api/jalon", {"libelle": "J1"}, mission=cle)
        self.assertEqual(code, 200)
        code, hist = self.appel("GET", "/api/journal?cible=jalon", mission=cle)
        self.assertEqual((code, hist[0]["action"]), (200, "creation"))
        code, _ = self.appel("POST", f"/api/journal/{hist[0]['id']}/annuler", mission=cle)
        self.assertEqual(code, 200)
        code, r = self.appel("POST", f"/api/journal/{hist[0]['id']}/annuler", mission=cle)
        self.assertEqual(code, 409)
        code, contenu = self.appel("GET", f"/api/missions/{cle}/export", brut=True)
        self.assertEqual(code, 200)
        code, r = self.appel("POST", "/api/missions/importer", {"fichier": json.loads(contenu)})
        self.assertEqual(code, 200)
        self.assertTrue(r["cle"].startswith("par-l-api-"))
        code, _ = self.appel("GET", "/api/jalon", mission="inexistante")
        self.assertEqual(code, 404)
        code, r = self.appel("POST", "/api/missions/importer", {"fichier": {"format": "x"}})
        self.assertEqual(code, 400)
        code, r = self.appel("POST", "/api/demo")
        self.assertEqual((code, r["cle"]), (200, "demo"))
        code, jalons = self.appel("GET", "/api/jalon", mission="demo")
        self.assertTrue(jalons)


if __name__ == "__main__":
    unittest.main()
