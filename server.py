"""Serveur local du co-pilote de mission. Lancement : python server.py"""
import datetime as dt
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agenda  # noqa: E402
import calculs  # noqa: E402
import db  # noqa: E402
import demo  # noqa: E402
import donnees  # noqa: E402
import exports  # noqa: E402
import finances  # noqa: E402
import llm  # noqa: E402
import meteo  # noqa: E402

PORT = int(os.environ.get("COPILOTE_PORT", "8765"))
STATIQUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PAGE = os.path.join(STATIQUE, "index.html")
TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}
EDITABLES = {"jalon", "livrable", "sprint", "risque", "decision", "compte_rendu",
             "lot", "lot_element", "story", "activite", "acteur", "instance", "raci", "metier",
             "estimation", "profil", "consommation", "depense", "facture", "attente"}
LISIBLES = EDITABLES | {"proposition", "meteo"}
TENDANCES = ("vert", "orange", "rouge")
TAILLE_MAX_IMPORT = 50 * 1024 * 1024


class Erreur(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


class Fichier:
    """Réponse à télécharger plutôt qu'un objet JSON."""
    def __init__(self, contenu, genre, nom):
        self.contenu = contenu if isinstance(contenu, bytes) else contenu.encode("utf-8")
        self.genre, self.nom = genre, nom


GENRES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ics": "text/calendar; charset=utf-8",
}


def aujourdhui():
    return dt.date.today()


def etat_mission():
    return donnees.etat_mission()


def synthese():
    return donnees.synthese(aujourdhui())


def suivi_risques():
    return donnees.suivi_risques(aujourdhui())


def extraire(cr_id):
    cr = db.lire("compte_rendu", cr_id)
    if not cr:
        raise Erreur("Compte rendu introuvable.", 404)
    if not (cr.get("texte") or "").strip():
        raise Erreur("Ce compte rendu est vide.")
    risques, decisions = db.lister("risque"), db.lister("decision")
    propositions = llm.extraire(cr, risques, decisions)
    ids = {"risque": {r["id"] for r in risques}, "decision": {d["id"] for d in decisions}}
    normalise = " ".join(cr["texte"].split())
    for p in propositions:
        table = "risque" if p["cible"] in ("risque", "adherence") else "decision"
        if p["operation"] == "mettre_a_jour" and p.get("ref_id") not in ids[table]:
            p["operation"], p["ref_id"] = "creer", 0  # référence inexistante : création
        extrait = p.pop("extrait", "")
        db.creer("proposition", {
            "cr_id": cr_id, "cible": p["cible"], "operation": p["operation"],
            "ref_id": p.get("ref_id") or 0, "contenu": json.dumps(p, ensure_ascii=False),
            "extrait": extrait,
            "extrait_verifie": int(bool(extrait) and " ".join(extrait.split()) in normalise),
            "statut": "en attente",
        })
    return db.lister("proposition", "cr_id = ?", (cr_id,))


def accepter(prop_id):
    p = db.lire("proposition", prop_id)
    if not p:
        raise Erreur("Proposition introuvable.", 404)
    if p["statut"] != "en attente":
        raise Erreur("Proposition déjà traitée.")
    c = json.loads(p["contenu"])
    auj = aujourdhui().isoformat()
    est_risque = p["cible"] in ("risque", "adherence")
    table = "risque" if est_risque else "decision"
    echeance = c.get("echeance") if calculs.date(c.get("echeance")) else ""
    if p["operation"] == "creer":
        if est_risque:
            db.creer("risque", {
                "nature": p["cible"], "titre": c.get("titre"), "description": c.get("description"),
                "probabilite": c.get("probabilite") or None, "impact": c.get("impact") or None,
                "etat": "ouvert", "evolution": c.get("evolution") or "stable",
                "porteur": c.get("porteur"), "echeance": echeance, "plan_action": "",
                "cree_le": auj, "maj_le": auj})
        else:
            db.creer("decision", {
                "nature": p["cible"], "titre": c.get("titre"), "detail": c.get("description"),
                "statut": "à prendre" if p["cible"] == "decision" else "à faire",
                "porteur": c.get("porteur"), "echeance": echeance, "cree_le": auj})
    else:
        existant = db.lire(table, p["ref_id"])
        if not existant:
            raise Erreur("L'élément à mettre à jour n'existe plus.", 409)
        champ = "description" if est_risque else "detail"
        maj = {}
        if c.get("description"):
            maj[champ] = ((existant.get(champ) or "") + f"\n[{auj}] {c['description']}").strip()
        for k in ("porteur",):
            if c.get(k):
                maj[k] = c[k]
        if echeance:
            maj["echeance"] = echeance
        if est_risque:
            maj["maj_le"] = auj
            for k in ("probabilite", "impact", "evolution"):
                if c.get(k):
                    maj[k] = c[k]
        db.modifier(table, p["ref_id"], maj)
    return db.modifier("proposition", prop_id, {"statut": "acceptée"})


def detailler_depuis_macro():
    """Point de départ du chiffrage détaillé : une ligne par élément du macro, à affiner."""
    if any(e.get("mode") == "detaille" for e in db.lister("estimation")):
        raise Erreur("Le chiffrage détaillé a déjà des lignes : complétez-le plutôt que de le réinitialiser.", 409)
    c = donnees.chiffrage()
    lignes = c["modes"]["macro"]["lignes"]
    if not lignes:
        raise Erreur("Le chiffrage macro est vide.")
    for l in lignes:
        db.creer("estimation", {
            "mode": "detaille", "lot": l.get("lot"), "libelle": l.get("libelle"), "rang": l.get("rang"),
            "jours_bas": l["bas"], "jours_probable": l["retenu"], "jours_haut": l["haut"],
            "hypothese": "Repris du macro (" + (l.get("taille") or "charge saisie") + ") : à affiner par profil."})
    return donnees.chiffrage()


def generer_meteo():
    d = meteo.donnees(*etat_mission(), aujourdhui(), donnees.alertes_complementaires(aujourdhui()))
    avertissement = None
    try:
        redaction, source = llm.rediger(d), "modèle"
    except llm.LLMIndisponible as e:
        redaction, source = meteo.rediger_sans_llm(d), "gabarit"
        avertissement = f"Rédaction par le modèle indisponible ({e}) : météo factuelle générée."
    m = db.creer("meteo", {
        "semaine": d["semaine"], "cree_le": aujourdhui().isoformat(),
        "contenu": meteo.assembler(d, redaction),
        "tendance_calculee": d["tendance_calculee"], "tendance": d["tendance_calculee"],
        "motif_derogation": "", "alertes": json.dumps(d["alertes"], ensure_ascii=False),
        "remarques": "[]", "statut": "brouillon", "source": source,
        # Photo du registre : sert à calculer l'évolution des risques d'une session à l'autre.
        "risques_instantane": json.dumps(calculs.instantane(db.lister("risque"))),
    })
    return {"meteo": m, "avertissement": avertissement}


def modifier_meteo(ident, corps):
    m = db.lire("meteo", ident)
    if not m:
        raise Erreur("Météo introuvable.", 404)
    maj = {k: corps[k] for k in ("contenu", "tendance", "motif_derogation", "statut") if k in corps}
    tendance = maj.get("tendance", m["tendance"])
    motif = (maj.get("motif_derogation", m["motif_derogation"]) or "").strip()
    if tendance not in TENDANCES:
        raise Erreur("Tendance inconnue.")
    if tendance != m["tendance_calculee"] and not motif:
        raise Erreur("La tendance retenue diffère de la tendance calculée : un motif est requis.")
    if tendance == m["tendance_calculee"]:
        maj["motif_derogation"] = motif = ""
    contenu = maj.get("contenu", m["contenu"])
    ligne = f"**Tendance globale : {meteo.LIBELLE[tendance]}**"
    if motif:
        ligne += (f" — dérogation du pilote : {motif} "
                  f"(tendance calculée : {m['tendance_calculee']})")
    maj["contenu"] = re.sub(r"^\*\*Tendance globale :.*$", lambda _: ligne, contenu,
                            count=1, flags=re.M)
    return db.modifier("meteo", ident, maj)


def challenger_meteo(ident):
    m = db.lire("meteo", ident)
    if not m:
        raise Erreur("Météo introuvable.", 404)
    etat = etat_mission()
    remarques = calculs.controles(etat[4], etat[5], m["contenu"], aujourdhui())
    if m["tendance"] != m["tendance_calculee"]:
        remarques.insert(0, {
            "origine": "règle", "gravite": "haute",
            "constat": f"Tendance retenue « {m['tendance']} » alors que les déclencheurs "
                       f"donnent « {m['tendance_calculee']} ».",
            "suggestion": "Vérifier que le motif de dérogation tient face aux sponsors."})
    avertissement = None
    try:
        remarques += llm.challenger(m["contenu"], meteo.donnees(*etat, aujourdhui(), donnees.alertes_complementaires(aujourdhui())),
                                    m["tendance"], m["motif_derogation"])
    except llm.LLMIndisponible as e:
        avertissement = f"Relecture par le modèle indisponible ({e}) : contrôles par règles seulement."
    remarques.sort(key=lambda r: ("haute", "moyenne", "basse").index(r.get("gravite", "basse"))
                   if r.get("gravite") in ("haute", "moyenne", "basse") else 3)
    m = db.modifier("meteo", ident, {"remarques": json.dumps(remarques, ensure_ascii=False)})
    return {"meteo": m, "avertissement": avertissement}


class Requete(BaseHTTPRequestHandler):
    server_version = "Copilote/0.1"

    def log_message(self, *args):
        pass

    def _json(self, objet, code=200):
        corps = json.dumps(objet, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corps)

    def _fichier(self, f):
        self.send_response(200)
        self.send_header("Content-Type", f.genre)
        self.send_header("Content-Length", str(len(f.contenu)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(f.nom)}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(f.contenu)

    def _octets(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > exports.TAILLE_MAX_MODELE:
            raise Erreur("Fichier trop volumineux (25 Mo au plus).", 413)
        return self.rfile.read(n) if n else b""

    def _corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            objet = json.loads(self.rfile.read(n).decode("utf-8"))
        except ValueError:
            raise Erreur("Corps de requête illisible.")
        if not isinstance(objet, dict):
            raise Erreur("Un objet JSON est attendu.")
        return objet

    def _traiter(self, methode):
        try:
            # N'accepter que les appels adressés à la machine locale.
            hote = (self.headers.get("Host") or "").split(":")[0]
            if hote not in ("127.0.0.1", "localhost"):
                raise Erreur("Hôte refusé.", 403)
            adresse = urlparse(self.path)
            chemin = adresse.path.rstrip("/") or "/"
            self.requete = parse_qs(adresse.query)
            # Mission visée : en-tête X-Mission (ou paramètre ?mission=), sinon la dernière ouverte.
            cle = self.headers.get("X-Mission") or (self.requete.get("mission") or [""])[0]
            if cle and chemin.startswith("/api/") and not chemin.startswith("/api/missions") \
                    and not db.existe(cle):
                raise Erreur("Mission introuvable : elle a peut-être été supprimée.", 404)
            with db.dans(cle or None):
                resultat = self._router(methode, chemin)
            if isinstance(resultat, Fichier):
                self._fichier(resultat)
            elif resultat is not None:
                self._json(resultat)
        except exports.ErreurExport as e:
            self._json({"erreur": str(e)}, 400)
        except Erreur as e:
            self._json({"erreur": str(e)}, e.code)
        except db.Introuvable as e:
            self._json({"erreur": str(e)}, 404)
        except db.Conflit as e:
            self._json({"erreur": str(e)}, 409)
        except llm.LLMIndisponible as e:
            self._json({"erreur": str(e)}, 503)
        except Exception as e:  # dernière barrière : ne jamais laisser le serveur muet
            self._json({"erreur": f"Erreur interne : {e}"}, 500)

    def _router(self, methode, chemin):
        statique = re.fullmatch(r"/static/([\w-]+)(\.js|\.css)", chemin)
        if methode == "GET" and (chemin in ("/", "/index.html") or statique):
            fichier, genre = PAGE, "text/html; charset=utf-8"
            if statique:  # nom sans séparateur de chemin : on ne sort pas du dossier static
                fichier = os.path.join(STATIQUE, statique.group(1) + statique.group(2))
                genre = TYPES[statique.group(2)]
                if not os.path.isfile(fichier):
                    raise Erreur("Fichier introuvable.", 404)
            with open(fichier, "rb") as f:
                corps = f.read()
            self.send_response(200)
            self.send_header("Content-Type", genre)
            self.send_header("Content-Length", str(len(corps)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corps)
            return None
        export = re.fullmatch(r"/api/export/(\w+)\.(pptx|xlsx)", chemin)
        if export and methode == "GET":
            meteo_id = (self.requete.get("meteo") or [""])[0]
            octets, nom = exports.exporter(export.group(1), export.group(2),
                                           int(meteo_id) if meteo_id.isdigit() else None, aujourdhui())
            return Fichier(octets, GENRES[export.group(2)], nom)
        modele = re.fullmatch(r"/api/modele/(\w+)\.(pptx|xlsx)", chemin)
        if modele:
            cible, ext = modele.groups()
            if cible != "commun" and cible not in exports.LIBELLES:
                raise Erreur("Vue inconnue.", 404)
            if methode == "GET":
                return Fichier(exports.octets_modele(cible, ext), GENRES[ext], f"modele-{cible}.{ext}")
            if methode == "PUT":
                exports.enregistrer_modele(cible, ext, self._octets())
                return exports.etat_modeles()
            if methode == "DELETE":
                exports.supprimer_modele(cible, ext)
                return exports.etat_modeles()
        if chemin == "/api/missions" or chemin.startswith("/api/missions/"):
            return self._missions(methode, chemin)
        m = re.fullmatch(r"/api/(\w+)(?:/(\d+))?(?:/(\w+))?", chemin)
        if not m:
            raise Erreur("Ressource inconnue.", 404)
        nom, ident, action = m.group(1), m.group(2), m.group(3)
        ident = int(ident) if ident else None

        if methode == "GET" and not ident:
            if nom == "etat":
                return llm.etat()
            if nom == "mission":
                return db.mission()
            if nom == "synthese":
                return synthese()
            if nom == "suivi_risques":
                return suivi_risques()
            if nom == "chiffrage":
                return donnees.chiffrage()
            if nom == "budget":
                return donnees.budget(aujourdhui())
            if nom == "suivi_attentes":
                return {**donnees.suivi_attentes(aujourdhui()), "categories": finances.CATEGORIES_ATTENTE}
            if nom == "agenda":
                return {**agenda.calendrier(aujourdhui()), "recurrences": agenda.RECURRENCES}
            if nom == "modeles":
                return {**exports.etat_modeles(), "libelles": exports.LIBELLES,
                        "sans_excel": sorted(exports.SANS_EXCEL)}
            if nom == "journal":
                q = {k: (self.requete.get(k) or [""])[0] for k in ("cible", "limite", "avant")}
                if q["cible"] and q["cible"] not in db.TABLES:
                    raise Erreur("Type d'élément inconnu.")
                return db.journal(q["cible"] or None, int(q["limite"]) if q["limite"].isdigit() else 200,
                                  int(q["avant"]) if q["avant"].isdigit() else None)
            if nom in LISIBLES and not action:
                return db.lister(nom)
        if methode == "GET" and nom == "instance" and action == "ics":
            liste = [db.lire("instance", ident)] if ident else db.lister("instance")
            if not liste or liste[0] is None:
                raise Erreur("Instance introuvable.", 404)
            if not any(i.get("premiere") and i.get("heure") for i in liste):
                raise Erreur("Aucun créneau posé : proposez d'abord des créneaux.")
            nom_fichier = "reunions" if not ident else re.sub(r"[^\w-]+", "-", liste[0]["nom"].lower()).strip("-")
            return Fichier(agenda.ics(liste, aujourdhui()), GENRES["ics"], f"{nom_fichier}.ics")
        if methode == "POST":
            if nom == "demo" and not ident:
                # La démonstration a sa propre mission : elle n'écrase jamais une mission réelle.
                if not db.existe("demo"):
                    db.creer_mission("demo")
                with db.dans("demo"):
                    demo.charger(aujourdhui())
                db.marquer_derniere("demo")
                return {"cle": "demo"}
            if nom == "estimation" and not ident and action == "depuis_macro":
                with db.origine("détaillé initialisé depuis le macro"):
                    return detailler_depuis_macro()
            if nom == "journal" and ident and action == "annuler":
                return {"element": db.annuler(ident)}  # None si l'annulation a supprimé l'élément
            if nom == "compte_rendu" and ident and action == "extraire":
                with db.origine("extraction du compte rendu"):
                    return extraire(ident)
            if nom == "proposition" and ident and action == "accepter":
                with db.origine("proposition acceptée"):
                    return accepter(ident)
            if nom == "proposition" and ident and action == "rejeter":
                with db.origine("proposition rejetée"):
                    return db.modifier("proposition", ident, {"statut": "rejetée"})
            if nom == "meteo" and action is None and ident is None:
                with db.origine("météo générée"):
                    return generer_meteo()
            if nom == "meteo" and ident and action == "challenger":
                with db.origine("relecture de la météo"):
                    return challenger_meteo(ident)
            if nom == "instance" and not ident and action == "proposer":
                with db.origine("créneaux proposés"):
                    return agenda.proposer(bool(self._corps().get("tout")), aujourdhui())
            if nom in EDITABLES and not ident:
                corps = self._corps()
                if nom in ("risque", "decision"):
                    corps["cree_le"] = aujourdhui().isoformat()
                if nom == "risque" and not corps.get("maj_le"):
                    corps["maj_le"] = aujourdhui().isoformat()
                return db.creer(nom, corps)
        if methode == "PUT":
            if nom == "mission" and not ident:
                corps = self._corps()
                for cle in ("seuils", "raci_roles", "chiffrage"):
                    if isinstance(corps.get(cle), (dict, list)):
                        corps[cle] = json.dumps(corps[cle], ensure_ascii=False)
                db.modifier("mission", 1, corps)
                return db.mission()
            if nom == "meteo" and ident and not action:
                return modifier_meteo(ident, self._corps())
            if nom in EDITABLES and ident and not action:
                existant = db.lire(nom, ident)
                if not existant:
                    raise Erreur("Élément introuvable.", 404)
                corps = self._corps()
                # Toute modification d'un risque le date du jour, sauf date saisie à la main.
                if nom == "risque" and corps.get("maj_le") in (None, "", existant.get("maj_le")):
                    corps["maj_le"] = aujourdhui().isoformat()
                return db.modifier(nom, ident, corps)
        if methode == "DELETE" and ident and not action and nom in EDITABLES | {"meteo"}:
            db.supprimer(nom, ident)
            return {"ok": True}
        raise Erreur("Opération non prise en charge.", 404)

    def _missions(self, methode, chemin):
        """Liste, création, import, export, ouverture et mise à la corbeille des missions."""
        reste = chemin[len("/api/missions"):].strip("/")
        if not reste:
            if methode == "GET":
                return {"missions": db.missions(), "derniere": db.derniere()}
            if methode == "POST":
                corps = self._corps()
                nom = (corps.get("nom") or "").strip()
                if not nom:
                    raise Erreur("Donnez un nom à la mission.")
                cle = db.creer_mission(nom, (corps.get("client") or "").strip())
                db.marquer_derniere(cle)
                return {"cle": cle}
        if reste == "importer" and methode == "POST":
            if int(self.headers.get("Content-Length") or 0) > TAILLE_MAX_IMPORT:
                raise Erreur("Fichier trop volumineux (50 Mo au plus).", 413)
            corps = self._corps()
            try:
                cle, avertissements = db.importer_mission(corps.get("fichier"), corps.get("nom"))
            except ValueError as e:
                raise Erreur(str(e))
            db.marquer_derniere(cle)
            return {"cle": cle, "avertissements": avertissements}
        m = re.fullmatch(r"([a-z0-9][a-z0-9-]*)(?:/(\w+))?", reste)
        if not m or not db.existe(m.group(1)):
            raise Erreur("Mission introuvable.", 404)
        cle, action = m.groups()
        if methode == "GET" and action == "export":
            with db.dans(cle):
                contenu = json.dumps(db.exporter_mission(), ensure_ascii=False, indent=1)
            return Fichier(contenu, "application/json; charset=utf-8",
                           f"mission-{cle}-{aujourdhui().isoformat()}.json")
        if methode == "PUT" and action == "ouvrir":
            db.marquer_derniere(cle)
            return {"ok": True}
        if methode == "DELETE" and not action:
            db.supprimer_mission(cle)
            return {"missions": db.missions(), "derniere": db.derniere()}
        raise Erreur("Opération non prise en charge.", 404)

    def do_GET(self):
        self._traiter("GET")

    def do_POST(self):
        self._traiter("POST")

    def do_PUT(self):
        self._traiter("PUT")

    def do_DELETE(self):
        self._traiter("DELETE")


if __name__ == "__main__":
    db.demarrer()
    print(f"Co-pilote de mission : http://127.0.0.1:{PORT}  (Ctrl+C pour arrêter)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Requete).serve_forever()
