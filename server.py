"""Serveur local du co-pilote de mission. Lancement : python server.py"""
import datetime as dt
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import calculs  # noqa: E402
import db  # noqa: E402
import demo  # noqa: E402
import llm  # noqa: E402
import meteo  # noqa: E402

PORT = int(os.environ.get("COPILOTE_PORT", "8765"))
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
EDITABLES = {"jalon", "livrable", "sprint", "risque", "decision", "compte_rendu"}
LISIBLES = EDITABLES | {"proposition", "meteo"}
TENDANCES = ("vert", "orange", "rouge")


class Erreur(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


def aujourdhui():
    return dt.date.today()


def etat_mission():
    return (db.mission(), db.lister("jalon"), db.lister("livrable"), db.lister("sprint"),
            db.lister("risque"), db.lister("decision"))


def synthese():
    d = meteo.donnees(*etat_mission(), aujourdhui())
    return {
        "semaine": d["semaine"], "tendance": d["tendance_calculee"], "alertes": d["alertes"],
        "kpi": d["kpi"], "atterrissage": d["atterrissage"],
        "seuils": calculs.seuils(db.mission()),
        "propositions_en_attente": len(db.lister("proposition", "statut = 'en attente'")),
        "risques_ouverts": len(d["risques_ouverts"]),
        "decisions_a_prendre": len(d["decisions_a_prendre"]),
    }


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


def generer_meteo():
    d = meteo.donnees(*etat_mission(), aujourdhui())
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
        remarques += llm.challenger(m["contenu"], meteo.donnees(*etat, aujourdhui()),
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
            chemin = urlparse(self.path).path.rstrip("/") or "/"
            resultat = self._router(methode, chemin)
            if resultat is not None:
                self._json(resultat)
        except Erreur as e:
            self._json({"erreur": str(e)}, e.code)
        except llm.LLMIndisponible as e:
            self._json({"erreur": str(e)}, 503)
        except Exception as e:  # dernière barrière : ne jamais laisser le serveur muet
            self._json({"erreur": f"Erreur interne : {e}"}, 500)

    def _router(self, methode, chemin):
        if methode == "GET" and chemin in ("/", "/index.html"):
            with open(PAGE, "rb") as f:
                corps = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corps)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corps)
            return None
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
            if nom in LISIBLES:
                return db.lister(nom)
        if methode == "POST":
            if nom == "demo" and not ident:
                demo.charger(aujourdhui())
                return {"ok": True}
            if nom == "compte_rendu" and ident and action == "extraire":
                return extraire(ident)
            if nom == "proposition" and ident and action == "accepter":
                return accepter(ident)
            if nom == "proposition" and ident and action == "rejeter":
                return db.modifier("proposition", ident, {"statut": "rejetée"})
            if nom == "meteo" and action is None and ident is None:
                return generer_meteo()
            if nom == "meteo" and ident and action == "challenger":
                return challenger_meteo(ident)
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
                if isinstance(corps.get("seuils"), dict):
                    corps["seuils"] = json.dumps(corps["seuils"])
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

    def do_GET(self):
        self._traiter("GET")

    def do_POST(self):
        self._traiter("POST")

    def do_PUT(self):
        self._traiter("PUT")

    def do_DELETE(self):
        self._traiter("DELETE")


if __name__ == "__main__":
    db.initialiser()
    print(f"Co-pilote de mission : http://127.0.0.1:{PORT}  (Ctrl+C pour arrêter)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Requete).serve_forever()
