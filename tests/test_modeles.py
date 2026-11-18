"""Modèles de mission : modèles fournis, création depuis un modèle, enregistrement d'une mission."""
import asyncio
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

DOSSIER = tempfile.mkdtemp(prefix="copilote-modeles-")
os.environ.pop("COPILOTE_DB", None)
os.environ["COPILOTE_MISSIONS"] = DOSSIER
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import catalogue  # noqa: E402
import db  # noqa: E402
import demo  # noqa: E402
import donnees  # noqa: E402
import modeles_mission as MM  # noqa: E402
from modeles_fournis import MODELES_FOURNIS  # noqa: E402

AUJ = dt.date(2026, 11, 18)


class Fournis(unittest.TestCase):
    def test_coherence(self):
        blocs = {b["id"] for b in catalogue.catalogue()["blocs"]}
        for cle, m in MODELES_FOURNIS.items():
            c, s = m["cadre"], m["squelette"]
            ids = {a["id"] for a in c["acteur"]}
            for i in c["instance"]:
                self.assertTrue(set(json.loads(i["participants_ids"])) <= ids, (cle, i["nom"]))
            for r in c["raci"]:
                v = list(json.loads(r["valeurs"]).values())
                self.assertEqual(v.count("A"), 1, (cle, r["activite"]))
                self.assertIn("R", v, (cle, r["activite"]))
                self.assertTrue(set(json.loads(r["valeurs"])) <= set(c["raci_roles"]), (cle, r["activite"]))
            lots = {l["nom"] for l in s["lot"]}
            self.assertTrue({j["version"] for j in s["jalon"]} <= lots, cle)
            self.assertTrue({b["bloc"] for b in s["blocs"]} <= blocs, cle)
            self.assertTrue(all(len(h["libelle"]) > 15 and h["impact"] for h in s["hypothese"]), cle)

    def test_creation_depuis_chaque_modele(self):
        for cle in MODELES_FOURNIS:
            m = db.creer_mission_complete({"nom": f"Depuis {cle}", "date_debut": "2027-01-04", "date_cible": "2027-12-31"}, modele=cle)
            with db.dans(m):
                modele = MODELES_FOURNIS[cle]
                self.assertEqual(len(db.lister("acteur")), len(modele["cadre"]["acteur"]))
                premier = min(modele["squelette"]["jalon"], key=lambda j: j["decalage"])
                jalon = next(j for j in db.lister("jalon") if j["libelle"] == premier["libelle"])
                attendu = (dt.date(2027, 1, 4) + dt.timedelta(days=premier["decalage"])).isoformat()
                self.assertEqual((jalon["date"], jalon["date_initiale"]), (attendu, attendu))
                self.assertTrue(all(h["statut"] == "à vérifier" for h in db.lister("hypothese")))
                self.assertTrue(all(p["raf_jours"] == 0 for p in db.lister("profil")))
                c = donnees.chiffrage()
                self.assertEqual(c["parametres"]["mode_retenu"], "macro")
                self.assertGreater(c["retenu"]["montant"], 0)
                self.assertEqual(db.journal(), [])  # la création n'encombre pas l'historique
                self.assertEqual(db.mission()["date_debut"], "2027-01-04")


class Personnels(unittest.TestCase):
    def test_enregistrer_anonymise_puis_reutiliser(self):
        source = db.creer_mission("Source")
        with db.dans(source):
            demo.charger(AUJ)
            donnees.appliquer_bloc("api-exposee", "moyen", "macro", "V1", 2)
            modele = MM.depuis_mission("Portail type", "Issu de la démo")
        self.assertIsNone(modele["source"])
        noms = {a["nom"] for a in modele["cadre"]["acteur"]}
        self.assertNotIn("Camille R.", noms)
        self.assertTrue(all(not a["email"] for a in modele["cadre"]["acteur"]))
        texte = json.dumps(modele, ensure_ascii=False)
        self.assertNotIn("Mutuelle Horizon", texte)  # le client n'est jamais repris
        self.assertIn({"bloc": "api-exposee", "niveau": "moyen", "lot": "V1", "quantite": 2.0}, modele["squelette"]["blocs"])
        self.assertFalse(any(r["titre"].startswith("Hypothèse invalidée") for r in modele["squelette"]["risque"]))
        r = MM.enregistrer(modele)
        self.assertEqual(MM.enregistrer(modele)["cle"], r["cle"] + "-2")  # jamais d'écrasement
        cible = db.creer_mission_complete({"nom": "Nouvelle", "date_debut": "2027-03-01"}, modele=r["cle"])
        with db.dans(cible):
            self.assertEqual(len(db.lister("jalon")), len(modele["squelette"]["jalon"]))
            self.assertEqual(len(db.lister("estimation")), 1)
        MM.supprimer(r["cle"])
        with self.assertRaises(ValueError):
            MM.lire(r["cle"])
        with self.assertRaises(ValueError):
            MM.supprimer("projet-agile")

    def test_non_anonymise_garde_les_personnes(self):
        with db.dans(db.creer_mission("Source 2")):
            demo.charger(AUJ)
            modele = MM.depuis_mission("Nominatif", anonymiser=False)
        self.assertIn("Camille R.", {a["nom"] for a in modele["cadre"]["acteur"]})


class Interfaces(unittest.TestCase):
    def test_api_et_mcp(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from mcp import Client
        import mcp_server
        import server
        srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Requete)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def appel(methode, chemin, corps=None):
            req = urllib.request.Request(base + chemin, method=methode, data=json.dumps(corps).encode() if corps is not None else None,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())
        try:
            code, liste = appel("GET", "/api/modeles_mission")
            self.assertEqual((code, [m["cle"] for m in liste][:3]), (200, ["projet-agile", "projet-data-ia", "mission-conseil"]))
            code, r = appel("POST", "/api/missions", {"fiche": {"nom": "Par API", "date_debut": "2027-02-01"}, "modele": "mission-conseil"})
            self.assertEqual(code, 200)
            code, m = appel("POST", f"/api/missions/{r['cle']}/modele", {"nom": "Conseil maison"})
            self.assertEqual((code, m["origine"]), (200, "personnel"))
            code, _ = appel("DELETE", "/api/modeles_mission/projet-agile")
            self.assertEqual(code, 400)
            code, _ = appel("POST", "/api/missions", {"fiche": {"nom": "X"}, "modele": "inexistant"})
            self.assertEqual(code, 400)
        finally:
            srv.shutdown()
            srv.server_close()

        async def deroule():
            async with Client(mcp_server.serveur) as c:
                return (await c.call_tool("lister_modeles_mission", {}),
                        await c.call_tool("creer_mission", {"nom": "Via MCP", "modele": "projet-data-ia", "fiche": {"date_debut": "2027-01-04"}}))
        liste, cree = asyncio.run(deroule())
        self.assertFalse(liste.is_error or cree.is_error)
        self.assertGreaterEqual(cree.structured_content["demarrage"]["faites"], 5)


if __name__ == "__main__":
    unittest.main()
