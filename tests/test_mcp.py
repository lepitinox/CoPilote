"""Serveur MCP : outils, ressources et prompts, par un vrai client MCP."""
import asyncio
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

DOSSIER = tempfile.mkdtemp(prefix="copilote-mcp-")
os.environ.pop("COPILOTE_DB", None)
os.environ["COPILOTE_MISSIONS"] = DOSSIER
ICI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ICI)

from mcp import Client, StdioServerParameters  # noqa: E402

import db  # noqa: E402
import demo  # noqa: E402
import mcp_server  # noqa: E402


def contenu(resultat):
    """Objet renvoyé par un outil (sortie structurée, sinon texte JSON)."""
    if resultat.structured_content is not None:
        s = resultat.structured_content
        return s.get("result", s) if isinstance(s, dict) and set(s) == {"result"} else s
    return json.loads(resultat.content[0].text)


class Outils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.demarrer()
        cls.cle = db.creer_mission("Démo MCP")
        with db.dans(cls.cle):
            demo.charger(dt.date.today())

    def appeler(self, *etapes):
        async def deroule():
            async with Client(mcp_server.serveur) as c:
                return [await c.call_tool(nom, args) for nom, args in etapes]
        return asyncio.run(deroule())

    def test_catalogue(self):
        async def deroule():
            async with Client(mcp_server.serveur) as c:
                return (await c.list_tools(), await c.list_prompts(), await c.list_resources())
        outils, prompts, ressources = asyncio.run(deroule())
        noms = {t.name for t in outils.tools}
        self.assertTrue({"synthese", "creer_element", "annuler_modification", "budget", "chiffrage"} <= noms)
        lecture = next(t for t in outils.tools if t.name == "synthese")
        self.assertTrue(lecture.annotations.read_only_hint)
        self.assertEqual({p.name for p in prompts.prompts}, {"revue_hebdomadaire", "integrer_compte_rendu", "preparer_comite"})
        self.assertIn("copilote://missions", {str(r.uri) for r in ressources.resources})

    def test_lecture(self):
        r_missions, r_synthese, r_risques = self.appeler(
            ("lister_missions", {}), ("synthese", {"mission": self.cle}),
            ("lister_elements", {"table": "risque", "mission": self.cle, "recherche": "vélocité"}))
        self.assertIn(self.cle, [m["cle"] for m in contenu(r_missions)["missions"]])
        s = contenu(r_synthese)
        self.assertIn(s["tendance"], ("vert", "orange", "rouge"))
        self.assertTrue(s["alertes"])
        self.assertEqual(contenu(r_risques)["nombre"], 1)

    def test_ecriture_tracee_et_annulable(self):
        (cree,) = self.appeler(("creer_element", {"table": "attente", "mission": self.cle, "champs": {
            "partie_prenante": "Marc L.", "libelle": "Tableau de bord mensuel", "priorite": 2, "inconnu": 1}}))
        c = contenu(cree)
        self.assertEqual(c["champs_ignores"], ["inconnu"])
        ident = c["element"]["id"]
        with db.dans(self.cle):
            entree = db.journal("attente", 1)[0]
        self.assertEqual((entree["origine"], entree["ligne"]), ("assistant (MCP)", ident))
        (annule,) = self.appeler(("annuler_modification", {"entree": entree["id"], "mission": self.cle}))
        self.assertFalse(annule.is_error)
        with db.dans(self.cle):
            self.assertIsNone(db.lire("attente", ident))

    def test_raci_en_objet_et_risque_date(self):
        (cree,) = self.appeler(("creer_element", {"table": "raci", "mission": self.cle, "champs": {
            "activite": "Recette", "valeurs": {"metier:QA": "R", "metier:Sponsor": "A"}}}))
        self.assertEqual(json.loads(contenu(cree)["element"]["valeurs"]), {"metier:QA": "R", "metier:Sponsor": "A"})
        (risque,) = self.appeler(("creer_element", {"table": "risque", "mission": self.cle, "champs": {"titre": "Test"}}))
        self.assertEqual(contenu(risque)["element"]["cree_le"], dt.date.today().isoformat())

    def test_erreurs_explicites(self):
        table_inconnue, mission_inconnue, absent = self.appeler(
            ("creer_element", {"table": "journal", "champs": {"x": 1}}),
            ("synthese", {"mission": "nexiste-pas"}),
            ("modifier_element", {"table": "risque", "id": 99999, "mission": self.cle, "champs": {"titre": "x"}}))
        for r in (table_inconnue, mission_inconnue, absent):
            self.assertTrue(r.is_error)
        self.assertIn("non prise en charge", table_inconnue.content[0].text)
        self.assertIn("lister_missions", mission_inconnue.content[0].text)

    def test_prompt(self):
        async def deroule():
            async with Client(mcp_server.serveur) as c:
                return await c.get_prompt("integrer_compte_rendu", {"texte": "L'API glisse de deux semaines."})
        p = asyncio.run(deroule())
        self.assertIn("L'API glisse de deux semaines.", p.messages[0].content.text)


class Stdio(unittest.TestCase):
    """Le serveur lancé comme un client MCP le lance : sous-processus, échanges sur stdin / stdout."""

    def test_sous_processus(self):
        async def deroule():
            params = StdioServerParameters(command=sys.executable, args=[os.path.join(ICI, "mcp_server.py")],
                                           env={**os.environ, "COPILOTE_MISSIONS": DOSSIER})
            async with Client(params) as c:
                return await c.call_tool("lister_missions", {})
        r = asyncio.run(deroule())
        self.assertFalse(r.is_error)
        self.assertTrue(contenu(r)["missions"])


if __name__ == "__main__":
    unittest.main()
