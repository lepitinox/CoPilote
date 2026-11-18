"""Demandes de changement : création depuis une origine, chiffrage, présentation, décision et avenant."""
import asyncio
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest

DOSSIER = tempfile.mkdtemp(prefix="copilote-cr-")
os.environ.pop("COPILOTE_DB", None)
os.environ["COPILOTE_MISSIONS"] = DOSSIER
os.environ["COPILOTE_MODELES"] = os.path.join(DOSSIER, "modeles")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import agenda  # noqa: E402
import changements as C  # noqa: E402
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


class Cycle(unittest.TestCase):
    def setUp(self):
        self.cle = mission_demo("Changements")

    def nouvelle(self, **kw):
        att = next(a for a in db.lister("attente") if a["libelle"].startswith("Rester dans"))
        jal = next(j for j in db.lister("jalon") if j["libelle"] == "Ouverture du parcours mobile")
        return C.creer({"origine_type": "attente", "origine_id": att["id"], "impact_delai_jours": 14,
                        "jalons_ids": json.dumps([jal["id"]]), **kw}, AUJ), att, jal

    def test_origine_reprise(self):
        with db.dans(self.cle):
            c, att, _ = self.nouvelle()
            self.assertEqual((c["titre"], c["demandeur"], c["statut"], c["cree_le"]),
                             (att["libelle"], att["partie_prenante"], "à instruire", AUJ.isoformat()))
            with self.assertRaises(C.ErreurChangement):
                C.creer({"origine_type": "attente", "origine_id": 9999}, AUJ)
            with self.assertRaises(C.ErreurChangement):
                C.creer({"origine_type": "directe"}, AUJ)  # sans titre

    def test_chiffrage_hors_mission_et_valorise(self):
        with db.dans(self.cle):
            c, _, _ = self.nouvelle()
            avant = donnees.chiffrage()
            C.chiffrer_avec_bloc(c["id"], "api-exposee", "rapide")
            self.assertEqual(db.lire("changement", c["id"])["statut"], "chiffrée")
            self.assertEqual(donnees.chiffrage()["modes"]["detaille"]["base"], avant["modes"]["detaille"]["base"])
            ch = C.chiffrage(c["id"])
            self.assertEqual(ch["base"]["retenu"], 3)  # API exposée, simple et clair : 3 j de développeur
            self.assertEqual(ch["total_jours"]["retenu"], round(3 * (1 + ch["taux_majoration"]), 2))
            self.assertEqual(ch["montant"], round(ch["total_jours"]["retenu"] * 700, 2))  # TJM du développeur

    def test_presenter_puis_accepter_applique_l_avenant(self):
        with db.dans(self.cle):
            c, att, jal = self.nouvelle(decideur="Marc L.")
            C.chiffrer_avec_bloc(c["id"], "api-exposee", "rapide")
            p = C.presenter(c["id"], aujourdhui=AUJ)
            d = db.lire("decision", p["decision_id"])
            self.assertEqual((p["statut"], d["statut"], d["instance"], d["porteur"]), ("présentée", "à prendre", "Comité sponsor", "Marc L."))
            comite = next(i for i in db.lister("instance") if i["nom"] == "Comité sponsor")
            ordre = pilote.preparer_seance(comite["id"], AUJ)["ordre_du_jour"]
            self.assertTrue(any(c["titre"] in x for p_ in ordre if p_["cle"] == "decisions" for x in p_["contenu"]))

            vendu, montant = db.mission()["budget_vendu"], C.chiffrage(c["id"])["montant"]
            dev = next(x for x in db.lister("profil") if x["nom"] == "Développeur")
            r = C.decider(c["id"], "accepter", "Validé en comité", AUJ)
            self.assertEqual(db.mission()["budget_vendu"], round(vendu + montant, 2))
            self.assertAlmostEqual(db.lire("profil", dev["id"])["raf_jours"] - dev["raf_jours"], C.chiffrage(c["id"])["total_jours"]["retenu"], 1)
            j2 = db.lire("jalon", jal["id"])
            decale = lambda iso: (dt.date.fromisoformat(iso) + dt.timedelta(days=14)).isoformat()
            self.assertEqual((j2["date"], j2["date_initiale"]), (decale(jal["date"]), decale(jal["date_initiale"])))
            self.assertEqual(db.lire("attente", att["id"])["position"], "alignée")
            self.assertEqual(db.lire("decision", p["decision_id"])["statut"], "prise")
            self.assertEqual(r["demande"]["statut"], "acceptée")
            self.assertTrue(all(e["origine"].startswith("avenant") for e in db.journal(limite=5)))
            with self.assertRaises(C.ErreurChangement):
                C.decider(c["id"], "refuser")  # déjà décidée
            s = C.suivi(AUJ)
            self.assertAlmostEqual(s["budget_initial"], db.mission()["budget_vendu"] - s["cumul_accepte"]["montant"], 2)
            self.assertAlmostEqual(s["cumul_accepte"]["part_budget_initial"], s["cumul_accepte"]["montant"] / s["budget_initial"], 3)

    def test_refus_sans_effet_budgetaire(self):
        with db.dans(self.cle):
            c, att, jal = self.nouvelle()
            C.chiffrer_avec_bloc(c["id"], "api-exposee", "moyen")
            vendu = db.mission()["budget_vendu"]
            C.decider(c["id"], "refuser", "Hors enveloppe", AUJ)
            self.assertEqual(db.mission()["budget_vendu"], vendu)
            self.assertEqual(db.lire("jalon", jal["id"])["date"], jal["date"])
            a = db.lire("attente", att["id"])
            self.assertEqual(a["position"], "hors périmètre")
            self.assertIn("refusée : Hors enveloppe", a["reponse"])

    def test_a_traiter_et_export(self):
        from pptx import Presentation
        with db.dans(self.cle):
            items = [i for i in pilote.a_traiter(AUJ)["items"] if i["genre"] == "changement"]
            self.assertTrue(any("à présenter" in i["titre"] for i in items))  # la demande chiffrée de la démo
            octets, _ = exports.exporter("changements", "pptx", aujourdhui=AUJ)
        self.assertGreaterEqual(len(Presentation(io.BytesIO(octets)).slides), 1)


class Interfaces(unittest.TestCase):
    def test_api_et_mcp(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from mcp import Client
        import mcp_server
        import server
        cle = mission_demo("Changements API")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Requete)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def appel(methode, chemin, corps=None):
            req = urllib.request.Request(base + chemin, method=methode, data=json.dumps(corps).encode() if corps is not None else None,
                                         headers={"X-Mission": cle, "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())
        try:
            code, c = appel("POST", "/api/changement", {"titre": "Mode sombre", "origine_type": "directe"})
            self.assertEqual((code, c["statut"]), (200, "à instruire"))
            code, lignes = appel("POST", f"/api/changement/{c['id']}/chiffrer", {"bloc": "ecran-standard", "niveau": "rapide"})
            self.assertEqual((code, len(lignes)), (200, 2))
            code, _ = appel("POST", f"/api/changement/{c['id']}/presenter", {})
            self.assertEqual(code, 200)
            code, r = appel("POST", f"/api/changement/{c['id']}/decider", {"choix": "n'importe"})
            self.assertEqual(code, 400)
            code, s = appel("GET", "/api/suivi_changements")
            self.assertEqual((code, s["compte"]["présentée"]), (200, 1))
        finally:
            srv.shutdown()
            srv.server_close()

        async def deroule():
            async with Client(mcp_server.serveur) as cl:
                cree = await cl.call_tool("creer_changement", {"titre": "Notifications SMS", "mission": cle})
                ident = cree.structured_content["id"]
                ch = await cl.call_tool("chiffrer_changement", {"changement": ident, "bloc": "notifications", "niveau": "moyen", "mission": cle})
                dec = await cl.call_tool("decider_changement", {"changement": ident, "choix": "reporter", "motif": "V2", "mission": cle})
                return cree, ch, dec
        cree, ch, dec = asyncio.run(deroule())
        self.assertFalse(cree.is_error or ch.is_error or dec.is_error)
        self.assertEqual(dec.structured_content["demande"]["statut"], "reportée")


if __name__ == "__main__":
    unittest.main()
