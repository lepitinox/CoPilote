import datetime as dt
import io
import os
import sys
import tempfile
import unittest

DOSSIER = tempfile.mkdtemp(prefix="copilote-tests-")
os.environ["COPILOTE_DB"] = os.path.join(DOSSIER, "test.db")
os.environ["COPILOTE_MODELES"] = os.path.join(DOSSIER, "modeles")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from openpyxl import Workbook, load_workbook  # noqa: E402
from pptx import Presentation  # noqa: E402

import agenda  # noqa: E402
import db  # noqa: E402
import demo  # noqa: E402
import donnees  # noqa: E402
import exports  # noqa: E402

AUJ = dt.date(2026, 11, 16)  # un lundi


class Durees(unittest.TestCase):
    def test_minutes(self):
        for texte, attendu in [("1 h 30", 90), ("15 min", 15), ("2 × 1 h", 60), ("30 min à 1 h", 60),
                               ("1h", 60), ("45 min", 45), ("", 60)]:
            self.assertEqual(agenda.minutes(texte), attendu, texte)

    def test_recurrence_devinee(self):
        self.assertEqual(agenda.deviner_recurrence("Tous les deux sprints"), "deux_sprints")
        self.assertEqual(agenda.deviner_recurrence("À chaque fin de sprint"), "fin_sprint")
        self.assertEqual(agenda.deviner_recurrence("Mensuelle"), "mensuelle")
        self.assertEqual(agenda.deviner_recurrence("À la demande"), "ponctuelle")


class Reunions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.initialiser()
        demo.charger(AUJ)

    def test_creneaux_sans_chevauchement(self):
        agenda.proposer(tout=True, aujourdhui=AUJ)
        instances = db.lister("instance")
        self.assertTrue(all(i["premiere"] and i["heure"] for i in instances))
        debut = AUJ
        fin = AUJ + dt.timedelta(days=56)
        occupation = {}
        for i in instances:
            a = agenda.hm(i["heure"])
            b = a + i["duree_min"]
            self.assertFalse(a < agenda.PAUSE[1] and b > agenda.PAUSE[0], f"{i['nom']} sur la pause")
            for d in agenda.occurrences(i, debut, fin, 14):
                self.assertLess(d.weekday(), 5, f"{i['nom']} un week-end")
                for x, y, nom in occupation.get(d, []):
                    self.assertFalse(a < y and x < b, f"{i['nom']} chevauche {nom} le {d}")
                occupation.setdefault(d, []).append((a, b, i["nom"]))

    def test_invitations(self):
        agenda.proposer(tout=True, aujourdhui=AUJ)
        texte = agenda.ics(db.lister("instance"), AUJ)
        self.assertTrue(texte.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertEqual(texte.count("BEGIN:VEVENT"), 7)
        self.assertIn("RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", texte)
        self.assertIn("RRULE:FREQ=WEEKLY;INTERVAL=4;BYDAY=FR", texte)  # rétrospective : tous les deux sprints
        self.assertTrue(all(len(l.encode()) <= 75 for l in texte.split("\r\n")))
        deplie = texte.replace("\r\n ", "")  # les lignes longues sont repliées (RFC 5545)
        self.assertIn("mailto:camille.r@mutuelle-horizon.example", deplie)
        self.assertNotIn("Équipe SI Contrats", deplie.split("SUMMARY:Portail partenaires — Synchro hebdo")[1]
                         .split("END:VEVENT")[0].split("RRULE")[1])  # sans e-mail : pas d'ATTENDEE

    def test_calendrier(self):
        agenda.proposer(tout=True, aujourdhui=AUJ)
        cal = agenda.calendrier(AUJ)
        self.assertEqual((cal["debut"], cal["fin"]), ("2026-11-16", "2026-11-27"))
        self.assertEqual(len(cal["jours"]), 10)
        self.assertEqual(sum(1 for j in cal["jours"] for s in j["seances"] if s["nom"] == "Mêlée quotidienne"), 10)


class Raci(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.initialiser()
        demo.charger(AUJ)

    def test_colonnes_metiers_et_personnes(self):
        camille = next(a for a in db.lister("acteur") if a["nom"] == "Camille R.")
        db.modifier("mission", 1, {"raci_roles": f'["metier:Sponsor", "acteur:{camille["id"]}", "PO"]'})
        cols = donnees.colonnes_raci()
        self.assertEqual(cols[0][:2], ("metier:Sponsor", "Sponsor"))
        self.assertIn("Marc L.", cols[0][2])
        self.assertEqual(cols[1][1:], ("Camille R.", "Pilotage de projet"))
        self.assertEqual(cols[2][0], "metier:PO")  # ancien format : libellé seul lu comme un métier

    def test_valeurs_ancien_format(self):
        self.assertEqual(db.valeurs_raci({"valeurs": '{"PO": "A", "acteur:3": "R"}'}),
                         {"metier:PO": "A", "acteur:3": "R"})


class Exports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.initialiser()
        demo.charger(AUJ)
        agenda.proposer(tout=True, aujourdhui=AUJ)

    def test_toutes_les_vues(self):
        for vue in exports.LIBELLES:
            octets, _ = exports.exporter(vue, "pptx", aujourdhui=AUJ)
            self.assertGreater(len(Presentation(io.BytesIO(octets)).slides), 1, vue)
            if vue not in exports.SANS_EXCEL:
                octets, _ = exports.exporter(vue, "xlsx", aujourdhui=AUJ)
                self.assertGreaterEqual(len(load_workbook(io.BytesIO(octets)).worksheets), 1, vue)

    def test_modele_excel_personnalise(self):
        wb = Workbook()
        ws = wb.active
        ws["B2"] = "Rapport {{titre}} — {{mission}}"
        ws["C5"] = "{{contenu}}"
        buf = io.BytesIO()
        wb.save(buf)
        exports.enregistrer_modele("raci", "xlsx", buf.getvalue())
        try:
            self.assertEqual(exports.source_modele("raci", "xlsx"), "vue")
            feuille = load_workbook(io.BytesIO(exports.exporter("raci", "xlsx", aujourdhui=AUJ)[0])).worksheets[0]
            self.assertEqual(feuille["B2"].value, "Rapport RACI — Portail partenaires — Mutuelle Horizon (fictif)")
            self.assertEqual(feuille["C5"].value, "R : réalise · A : approuve · C : est consulté · I : est informé")
            self.assertEqual(feuille["C7"].value, "Domaine")  # sous-titre à la cellule marquée, tableau deux lignes plus bas
        finally:
            exports.supprimer_modele("raci", "xlsx")
        self.assertEqual(exports.source_modele("raci", "xlsx"), "defaut")

    def test_modele_invalide_refuse(self):
        with self.assertRaises(exports.ErreurExport):
            exports.enregistrer_modele("commun", "pptx", b"pas un fichier PowerPoint")
        with self.assertRaises(exports.ErreurExport):
            exports.enregistrer_modele("inconnue", "pptx", b"x")


class Api(unittest.TestCase):
    """Passe par le vrai serveur HTTP : routes, codes de retour, téléchargements."""

    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer
        import server
        db.initialiser()
        demo.charger(AUJ)
        cls.serveur = ThreadingHTTPServer(("127.0.0.1", 0), server.Requete)
        cls.base = f"http://127.0.0.1:{cls.serveur.server_address[1]}"
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()

    def appel(self, methode, chemin, corps=None, brut=False):
        import json
        import urllib.error
        import urllib.request
        donnees_ = json.dumps(corps).encode() if corps is not None else None
        req = urllib.request.Request(self.base + chemin, data=donnees_, method=methode,
                                     headers={"Content-Type": "application/json"} if corps is not None else {})
        try:
            with urllib.request.urlopen(req) as r:
                contenu = r.read()
                return r.status, (contenu if brut else json.loads(contenu)), r.headers
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read()), e.headers

    def test_listes(self):
        for table in ("lot", "acteur", "metier", "instance", "raci", "risque", "sprint", "meteo"):
            code, corps, _ = self.appel("GET", f"/api/{table}")
            self.assertEqual(code, 200, table)
            self.assertIsInstance(corps, list, table)

    def test_creneaux_et_invitations(self):
        code, corps, _ = self.appel("POST", "/api/instance/proposer", {"tout": True})
        self.assertEqual((code, len(corps)), (200, 7))
        code, contenu, entetes = self.appel("GET", "/api/instance/ics", brut=True)
        self.assertEqual(code, 200)
        self.assertTrue(entetes["Content-Type"].startswith("text/calendar"))
        self.assertIn(b"BEGIN:VCALENDAR", contenu)

    def test_exports_et_modeles(self):
        code, contenu, entetes = self.appel("GET", "/api/export/raci.pptx", brut=True)
        self.assertEqual(code, 200)
        self.assertIn("attachment", entetes["Content-Disposition"])
        self.assertEqual(contenu[:2], b"PK")
        code, corps, _ = self.appel("GET", "/api/export/meteo.xlsx")
        self.assertEqual(code, 400)
        code, corps, _ = self.appel("GET", "/api/modele/inconnue.pptx")
        self.assertEqual(code, 404)
        code, corps, _ = self.appel("GET", "/api/modeles")
        self.assertEqual(code, 200)
        self.assertIn("raci", corps["libelles"])


if __name__ == "__main__":
    unittest.main()
