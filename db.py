"""Stockage SQLite du co-pilote : un fichier par mission, ses objets de pilotage et leur historique.

Chaque mission est un fichier `<clé>.db` du dossier des missions. La mission utilisée par une
requête est choisie par `dans(clé)` (une par fil d'exécution) ; à défaut, la dernière ouverte.
"""
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import threading
import unicodedata
from contextlib import contextmanager

ICI = os.path.dirname(os.path.abspath(__file__))
_DB_ENV = os.environ.get("COPILOTE_DB")  # une base précise (tests, usage ponctuel)
DOSSIER = os.environ.get("COPILOTE_MISSIONS") or (
    os.path.dirname(os.path.abspath(_DB_ENV)) if _DB_ENV else os.path.join(ICI, "missions"))
ANCIENNE_BASE = os.path.join(ICI, "copilote.db")  # emplacement d'avant le multi-missions
FORMAT = "copilote-mission"
VERSION_FORMAT = 1

# table -> {colonne: type SQL}
TABLES = {
    "mission": {
        "nom": "TEXT", "client": "TEXT",
        "objectif_business": "TEXT", "objectif_solution": "TEXT", "objectif_projet": "TEXT",
        "porteur_business": "TEXT", "porteur_solution": "TEXT", "porteur_projet": "TEXT",
        "hypotheses": "TEXT", "date_cible": "TEXT", "duree_sprint_jours": "INTEGER",
        "seuils": "TEXT", "raci_roles": "TEXT",
        # chiffrage : paramètres JSON (abaque, marges, majorations, mode retenu, TJM moyen)
        "chiffrage": "TEXT", "budget_vendu": "REAL",
    },
    # Chiffrage. mode : macro (peu d'informations : taille et abaque) | detaille (après
    # collecte : charge en trois points par profil).
    "estimation": {"mode": "TEXT", "lot": "TEXT", "libelle": "TEXT", "taille": "TEXT",
                   "confiance": "TEXT", "profil": "TEXT", "jours_bas": "REAL",
                   "jours_probable": "REAL", "jours_haut": "REAL", "hypothese": "TEXT",
                   "rang": "INTEGER", "bloc": "TEXT", "niveau": "TEXT"},  # bloc du catalogue d'origine
    # Budget. Profils vendus (TJM de vente, coût journalier, reste à faire en jours).
    "profil": {"nom": "TEXT", "metier": "TEXT", "tjm": "REAL", "cout_journalier": "REAL",
               "raf_jours": "REAL", "rang": "INTEGER"},
    "consommation": {"mois": "TEXT", "profil": "TEXT", "jours": "REAL", "commentaire": "TEXT"},
    # statut : prévue | engagée | payée
    "depense": {"date": "TEXT", "libelle": "TEXT", "categorie": "TEXT", "montant": "REAL",
                "statut": "TEXT"},
    # statut : à facturer | facturée | payée
    "facture": {"libelle": "TEXT", "date_prevue": "TEXT", "montant": "REAL", "statut": "TEXT",
                "jalon": "TEXT"},
    # Attentes du client. satisfaction : 1 à 5 ; position : alignée | à recadrer | hors périmètre.
    "attente": {"partie_prenante": "TEXT", "libelle": "TEXT", "categorie": "TEXT",
                "priorite": "INTEGER", "satisfaction": "INTEGER", "position": "TEXT",
                "reponse": "TEXT", "prochaine_action": "TEXT", "echeance": "TEXT",
                "revue_le": "TEXT"},
    # Cadre de la mission
    "lot": {"nom": "TEXT", "titre": "TEXT", "periode": "TEXT", "date": "TEXT",
            "statut": "TEXT", "rang": "INTEGER"},
    # axe : contenu | prerequis | pour_qui | comment | quoi | fonctionnalite
    "lot_element": {"lot": "TEXT", "axe": "TEXT", "libelle": "TEXT", "detail": "TEXT"},
    "story": {"etape": "TEXT", "rang_etape": "INTEGER", "libelle": "TEXT", "lot": "TEXT",
              "irritant": "INTEGER", "innovation": "INTEGER"},
    "activite": {"piste": "TEXT", "libelle": "TEXT", "debut": "TEXT", "fin": "TEXT"},
    # Catalogue des métiers : prérempli, modifiable. Sert à l'organisation et au RACI.
    "metier": {"nom": "TEXT", "rang": "INTEGER"},
    "acteur": {"nom": "TEXT", "role": "TEXT", "cercle": "TEXT", "entite": "TEXT",
               "adherence": "TEXT", "metier": "TEXT", "email": "TEXT"},
    # participants_ids : liste JSON d'identifiants d'acteurs.
    # recurrence, premiere (date), heure (HH:MM), duree_min : créneau de la réunion.
    "instance": {"nom": "TEXT", "chantier": "TEXT", "objectifs": "TEXT",
                 "participants": "TEXT", "frequence": "TEXT", "duree": "TEXT",
                 "rang": "INTEGER", "participants_ids": "TEXT", "recurrence": "TEXT",
                 "premiere": "TEXT", "heure": "TEXT", "duree_min": "INTEGER"},
    "raci": {"domaine": "TEXT", "activite": "TEXT", "valeurs": "TEXT", "rang": "INTEGER"},
    "jalon": {"libelle": "TEXT", "date": "TEXT", "version": "TEXT", "statut": "TEXT"},
    "livrable": {
        "chantier": "TEXT", "libelle": "TEXT", "avancement": "INTEGER",
        "statut": "TEXT", "tendance": "TEXT",
    },
    "sprint": {
        "numero": "INTEGER", "date_fin": "TEXT", "capacite": "REAL", "prevu": "REAL",
        "realise": "REAL", "ajoute": "REAL", "reste": "REAL",
        "anomalies_creees": "INTEGER", "anomalies_corrigees": "INTEGER", "moral": "INTEGER",
    },
    "risque": {
        "nature": "TEXT", "titre": "TEXT", "description": "TEXT",
        "probabilite": "INTEGER", "impact": "INTEGER", "etat": "TEXT", "evolution": "TEXT",
        "porteur": "TEXT", "echeance": "TEXT", "lot": "TEXT", "plan_action": "TEXT",
        "cree_le": "TEXT", "maj_le": "TEXT",
    },
    "decision": {
        "nature": "TEXT", "titre": "TEXT", "detail": "TEXT", "statut": "TEXT",
        "porteur": "TEXT", "echeance": "TEXT", "instance": "TEXT", "cree_le": "TEXT",
    },
    "compte_rendu": {"date": "TEXT", "titre": "TEXT", "texte": "TEXT"},
    "proposition": {
        "cr_id": "INTEGER", "cible": "TEXT", "operation": "TEXT", "ref_id": "INTEGER",
        "contenu": "TEXT", "extrait": "TEXT", "extrait_verifie": "INTEGER", "statut": "TEXT",
    },
    "meteo": {
        "semaine": "TEXT", "cree_le": "TEXT", "contenu": "TEXT",
        "tendance_calculee": "TEXT", "tendance": "TEXT", "motif_derogation": "TEXT",
        "alertes": "TEXT", "remarques": "TEXT", "statut": "TEXT", "source": "TEXT",
        "risques_instantane": "TEXT",
    },
}

# Historique : une ligne par création, modification ou suppression, avec l'état avant et après
# (lignes complètes en JSON). annule_par : entrée qui a défait celle-ci.
JOURNAL = {"horodatage": "TEXT", "cible": "TEXT", "ligne": "INTEGER", "action": "TEXT",
           "avant": "TEXT", "apres": "TEXT", "origine": "TEXT", "annule_par": "INTEGER"}

ORDRE = {
    "jalon": "date", "livrable": "chantier, id", "sprint": "numero",
    "risque": "probabilite * impact DESC, id", "decision": "echeance, id",
    "compte_rendu": "date DESC, id DESC", "proposition": "id", "meteo": "id DESC",
    "lot": "rang, id", "lot_element": "id", "story": "rang_etape, id",
    "activite": "debut, id", "acteur": "cercle, entite, id", "instance": "rang, id",
    "raci": "rang, id", "metier": "rang, nom",
    "estimation": "mode, lot, rang, id", "profil": "rang, id", "consommation": "mois, id",
    "depense": "date, id", "facture": "date_prevue, id",
    "attente": "partie_prenante, priorite, id",
}

METIERS_DEFAUT = [
    "Sponsor", "Pilotage de projet", "Product owner", "Business analyst", "UX / UI",
    "Architecte", "Tech lead", "Développeur", "QA", "Data", "DevOps", "Sécurité",
    "Conformité", "Juridique", "Métier", "IT", "Change", "Prestataire",
]


class Conflit(Exception):
    """Opération refusée parce que l'état actuel ne le permet pas."""


class Introuvable(Exception):
    pass


# ---------- choix de la mission ----------

_local = threading.local()
_CLE = re.compile(r"[a-z0-9][a-z0-9-]{0,59}")


def cle_valide(cle):
    return bool(cle) and bool(_CLE.fullmatch(cle))


def chemin_de(cle):
    if not cle_valide(cle):
        raise Introuvable("Mission introuvable.")
    return os.path.join(DOSSIER, cle + ".db")


def existe(cle):
    return cle_valide(cle) and os.path.isfile(chemin_de(cle))


def _fichier_derniere():
    return os.path.join(DOSSIER, ".derniere")


def derniere():
    """Mission ouverte en dernier ; à défaut, la première trouvée."""
    if _DB_ENV:
        return os.path.splitext(os.path.basename(_DB_ENV))[0]
    try:
        with open(_fichier_derniere(), encoding="utf-8") as f:
            cle = f.read().strip()
        if existe(cle):
            return cle
    except OSError:
        pass
    cles = sorted(_cles())
    return cles[0] if cles else None


def marquer_derniere(cle):
    if _DB_ENV or not existe(cle):
        return
    with open(_fichier_derniere(), "w", encoding="utf-8") as f:
        f.write(cle)


def cle_courante():
    cle = getattr(_local, "cle", None) or derniere()
    if not cle:
        raise Introuvable("Aucune mission : créez-en une.")
    return cle


@contextmanager
def dans(cle):
    """Exécute le bloc sur la mission `cle`."""
    avant = getattr(_local, "cle", None)
    _local.cle = cle
    try:
        yield
    finally:
        _local.cle = avant


@contextmanager
def _ouvrir(chemin):
    """Connexion validée en fin de bloc puis fermée (un fichier ouvert reste verrouillé sous Windows)."""
    c = sqlite3.connect(chemin)
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()


def connexion():
    return _ouvrir(chemin_de(cle_courante()))


def _cles():
    if not os.path.isdir(DOSSIER):
        return []
    return [n[:-3] for n in os.listdir(DOSSIER) if n.endswith(".db") and cle_valide(n[:-3])]


def demarrer():
    """Au lancement du serveur : dossier des missions, reprise de l'ancienne base, une mission au moins."""
    os.makedirs(DOSSIER, exist_ok=True)
    par_defaut = not _DB_ENV and not os.environ.get("COPILOTE_MISSIONS")
    if par_defaut and not _cles() and os.path.isfile(ANCIENNE_BASE):
        # Base d'avant le multi-missions : copiée comme première mission ; l'original est gardé.
        nom = "mission"
        try:
            with _ouvrir(ANCIENNE_BASE) as c:
                nom = (c.execute("SELECT nom FROM mission WHERE id = 1").fetchone() or ["mission"])[0]
        except sqlite3.Error:
            pass
        cle = cle_libre(nom or "mission")
        shutil.copy2(ANCIENNE_BASE, chemin_de(cle))
        os.replace(ANCIENNE_BASE, ANCIENNE_BASE + ".avant-multi-missions")
        marquer_derniere(cle)
    if _DB_ENV:
        initialiser()
    elif not _cles():
        creer_mission("Nouvelle mission")
    for cle in _cles():  # mise à niveau du schéma de chaque mission
        with dans(cle):
            initialiser()


def slug(texte):
    t = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40].strip("-") or "mission"


def cle_libre(nom):
    base, n = slug(nom), 1
    cle = base
    while os.path.exists(os.path.join(DOSSIER, cle + ".db")):
        n += 1
        cle = f"{base}-{n}"
    return cle


def missions():
    liste = []
    for cle in _cles():
        fiche = {"cle": cle, "nom": cle, "client": ""}
        try:
            with _ouvrir(chemin_de(cle)) as c:
                r = c.execute("SELECT nom, client FROM mission WHERE id = 1").fetchone()
            if r:
                fiche.update(nom=r[0] or cle, client=r[1] or "")
        except sqlite3.Error:
            fiche["illisible"] = True
        fiche["modifiee_le"] = dt.datetime.fromtimestamp(
            os.path.getmtime(chemin_de(cle))).isoformat(timespec="minutes")
        liste.append(fiche)
    return sorted(liste, key=lambda m: m["nom"].lower())


def creer_mission(nom, client=""):
    os.makedirs(DOSSIER, exist_ok=True)
    cle = cle_libre(nom)
    with dans(cle), sans_journal():
        initialiser()
        modifier("mission", 1, {"nom": (nom or "Nouvelle mission").strip(), "client": client or ""})
    return cle


def supprimer_mission(cle):
    """Met la mission à la corbeille (sous-dossier `corbeille`) : rien n'est effacé."""
    if not existe(cle):
        raise Introuvable("Mission introuvable.")
    corbeille = os.path.join(DOSSIER, "corbeille")
    os.makedirs(corbeille, exist_ok=True)
    horodatage = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.replace(chemin_de(cle), os.path.join(corbeille, f"{cle}-{horodatage}.db"))
    if not _cles():
        creer_mission("Nouvelle mission")


# ---------- schéma ----------

def initialiser():
    with connexion() as c:
        for table, cols in {**TABLES, "journal": JOURNAL}.items():
            defs = ", ".join(f"{n} {t}" for n, t in cols.items())
            c.execute(f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY, {defs})")
            # Bases créées par une version antérieure : ajouter les colonnes manquantes.
            presentes = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
            for n, t in cols.items():
                if n not in presentes:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {n} {t}")
        if not c.execute("SELECT 1 FROM mission WHERE id = 1").fetchone():
            c.execute(
                "INSERT INTO mission (id, nom, duree_sprint_jours, seuils) VALUES (1, ?, 14, ?)",
                ("Nouvelle mission", "{}"),
            )
        if not c.execute("SELECT 1 FROM metier").fetchone():
            c.executemany("INSERT INTO metier (nom, rang) VALUES (?, ?)",
                          [(n, i) for i, n in enumerate(METIERS_DEFAUT)])


def vider():
    with connexion() as c:
        for table in [*TABLES, "journal"]:
            c.execute(f"DROP TABLE IF EXISTS {table}")
    initialiser()


# ---------- historique ----------

@contextmanager
def sans_journal():
    """Chargements en masse (démo, import) : rien n'est inscrit à l'historique."""
    avant = getattr(_local, "silence", False)
    _local.silence = True
    try:
        yield
    finally:
        _local.silence = avant


@contextmanager
def origine(texte):
    """Libellé de l'origine des modifications faites dans le bloc (par défaut : saisie)."""
    avant = getattr(_local, "origine", None)
    _local.origine = texte
    try:
        yield
    finally:
        _local.origine = avant


def _ligne(c, table, ident):
    r = c.execute(f"SELECT * FROM {table} WHERE id = ?", (ident,)).fetchone()
    return dict(r) if r else None


def _journaliser(c, table, ident, action, avant, apres):
    if getattr(_local, "silence", False):
        return
    c.execute(
        "INSERT INTO journal (horodatage, cible, ligne, action, avant, apres, origine) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (dt.datetime.now().isoformat(timespec="seconds"), table, ident, action,
         json.dumps(avant, ensure_ascii=False) if avant is not None else None,
         json.dumps(apres, ensure_ascii=False) if apres is not None else None,
         getattr(_local, "origine", None) or "saisie"))
    return c.execute("SELECT last_insert_rowid()").fetchone()[0]


def _entree(r):
    e = dict(r)
    for k in ("avant", "apres"):
        e[k] = json.loads(e[k]) if e.get(k) else None
    return e


def journal(cible=None, limite=200, avant_id=None):
    """Entrées de l'historique, les plus récentes d'abord."""
    ou, params = [], []
    if cible:
        ou.append("cible = ?")
        params.append(cible)
    if avant_id:
        ou.append("id < ?")
        params.append(avant_id)
    sql = "SELECT * FROM journal" + (" WHERE " + " AND ".join(ou) if ou else "")
    sql += " ORDER BY id DESC LIMIT ?"
    with connexion() as c:
        return [_entree(r) for r in c.execute(sql, (*params, max(1, min(int(limite), 1000))))]


def annuler(ident):
    """Défait une entrée de l'historique, si l'élément n'a pas changé depuis."""
    with connexion() as c:
        r = c.execute("SELECT * FROM journal WHERE id = ?", (ident,)).fetchone()
    if not r:
        raise Introuvable("Entrée d'historique introuvable.")
    e = _entree(r)
    if e["annule_par"]:
        raise Conflit("Cette modification a déjà été annulée.")
    table, ligne, avant, apres = e["cible"], e["ligne"], e["avant"], e["apres"]
    if table not in TABLES or e["action"] not in ("creation", "modification", "suppression"):
        raise Conflit("Cette entrée ne peut pas être annulée.")
    actuel = lire(table, ligne)
    change = actuel is not None and apres is not None and any(actuel.get(k) != v for k, v in apres.items())
    with origine(f"annulation de l'entrée n° {ident}"):
        if e["action"] in ("creation", "modification"):
            if actuel is None:
                raise Conflit("L'élément n'existe plus : rien à annuler.")
            if change:
                raise Conflit("L'élément a été modifié depuis : annulez d'abord les modifications plus récentes.")
            if e["action"] == "creation":
                supprimer(table, ligne)
            else:
                modifier(table, ligne, {k: v for k, v in avant.items() if k != "id"})
        else:
            if actuel is not None:
                raise Conflit("Un élément porte déjà cet identifiant : restauration impossible.")
            _inserer(table, avant)
    with connexion() as c:
        derniere_entree = c.execute("SELECT MAX(id) FROM journal").fetchone()[0]
        c.execute("UPDATE journal SET annule_par = ? WHERE id = ?", (derniere_entree, ident))
    return lire(table, ligne)


# ---------- lecture et écriture ----------

def _filtrer(table, donnees):
    return {k: v for k, v in (donnees or {}).items() if k in TABLES[table]}


def lister(table, ou=None, params=()):
    sql = f"SELECT * FROM {table}"
    if ou:
        sql += f" WHERE {ou}"
    if table in ORDRE:
        sql += f" ORDER BY {ORDRE[table]}"
    with connexion() as c:
        return [dict(r) for r in c.execute(sql, params)]


def lire(table, ident):
    with connexion() as c:
        return _ligne(c, table, ident)


def creer(table, donnees):
    d = _filtrer(table, donnees)
    with connexion() as c:
        if d:
            cols = ", ".join(d)
            trous = ", ".join("?" for _ in d)
            cur = c.execute(f"INSERT INTO {table} ({cols}) VALUES ({trous})", tuple(d.values()))
        else:
            cur = c.execute(f"INSERT INTO {table} DEFAULT VALUES")
        ident = cur.lastrowid
        apres = _ligne(c, table, ident)
        _journaliser(c, table, ident, "creation", None, apres)
    return apres


def _inserer(table, ligne):
    """Réinsère une ligne avec son identifiant (restauration après suppression)."""
    d = {"id": ligne["id"], **_filtrer(table, ligne)}
    with connexion() as c:
        c.execute(f"INSERT INTO {table} ({', '.join(d)}) VALUES ({', '.join('?' for _ in d)})",
                  tuple(d.values()))
        _journaliser(c, table, d["id"], "creation", None, _ligne(c, table, d["id"]))


def modifier(table, ident, donnees):
    d = _filtrer(table, donnees)
    with connexion() as c:
        avant = _ligne(c, table, ident)
        if d and avant:
            affect = ", ".join(f"{k} = ?" for k in d)
            c.execute(f"UPDATE {table} SET {affect} WHERE id = ?", (*d.values(), ident))
            apres = _ligne(c, table, ident)
            if apres != avant:
                _journaliser(c, table, ident, "modification", avant, apres)
            return apres
    return avant


def supprimer(table, ident):
    with connexion() as c:
        avant = _ligne(c, table, ident)
        c.execute(f"DELETE FROM {table} WHERE id = ?", (ident,))
        if avant:
            _journaliser(c, table, ident, "suppression", avant, None)


# ---------- export et import d'une mission ----------

def exporter_mission():
    """La mission courante en un objet JSON lisible : toutes les tables et l'historique."""
    with connexion() as c:
        tables = {t: [dict(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY id")] for t in TABLES}
        hist = [_entree(r) for r in c.execute("SELECT * FROM journal ORDER BY id")]
    m = (tables["mission"] or [{}])[0]
    return {"format": FORMAT, "version": VERSION_FORMAT,
            "exporte_le": dt.datetime.now().isoformat(timespec="seconds"),
            "mission": {"nom": m.get("nom"), "client": m.get("client")},
            "tables": tables, "journal": hist}


def _scalaire(v):
    if v is None or isinstance(v, (str, int, float)):
        return v
    if isinstance(v, bool):
        return int(v)
    return json.dumps(v, ensure_ascii=False)


def importer_mission(objet, nom=None):
    """Crée une nouvelle mission à partir d'un export ; n'écrase jamais une mission existante.

    Renvoie (clé, avertissements)."""
    if not isinstance(objet, dict) or objet.get("format") != FORMAT:
        raise ValueError("Ce fichier n'est pas un export de mission du co-pilote.")
    if not isinstance(objet.get("version"), int) or objet["version"] > VERSION_FORMAT:
        raise ValueError("Version de fichier non prise en charge : mettez le co-pilote à jour.")
    tables = objet.get("tables")
    if not isinstance(tables, dict) or not isinstance(tables.get("mission"), list) or not tables["mission"]:
        raise ValueError("Fichier incomplet : la fiche mission est absente.")
    avertissements = [f"Table inconnue ignorée : {t}." for t in tables if t not in TABLES]
    fiche = tables["mission"][0] if isinstance(tables["mission"][0], dict) else {}
    titre = (nom or fiche.get("nom") or "Mission importée").strip()
    os.makedirs(DOSSIER, exist_ok=True)
    cle = cle_libre(titre)
    try:
        with dans(cle), sans_journal():
            initialiser()
            with connexion() as c:
                for t, lignes in tables.items():
                    if t not in TABLES or not isinstance(lignes, list):
                        continue
                    c.execute(f"DELETE FROM {t}")  # métiers par défaut, fiche vide
                    for ligne in lignes:
                        if not isinstance(ligne, dict):
                            continue
                        d = {k: _scalaire(v) for k, v in ligne.items() if k in TABLES[t]}
                        if isinstance(ligne.get("id"), int):
                            d["id"] = ligne["id"]
                        if d:
                            c.execute(f"INSERT INTO {t} ({', '.join(d)}) VALUES ({', '.join('?' for _ in d)})",
                                      tuple(d.values()))
                for e in objet.get("journal") or []:
                    if not isinstance(e, dict):
                        continue
                    d = {k: _scalaire(e.get(k)) for k in JOURNAL}
                    for k in ("avant", "apres"):
                        d[k] = json.dumps(e[k], ensure_ascii=False) if e.get(k) is not None else None
                    c.execute(f"INSERT INTO journal ({', '.join(d)}) VALUES ({', '.join('?' for _ in d)})",
                              tuple(d.values()))
                if nom:
                    c.execute("UPDATE mission SET nom = ? WHERE id = 1", (titre,))
            initialiser()  # fiche mission et métiers si le fichier n'en avait pas
        with dans(cle), connexion() as c:  # trace de l'import, qui ne s'annule pas
            c.execute("INSERT INTO journal (horodatage, cible, ligne, action, origine) VALUES (?, ?, ?, ?, ?)",
                      (dt.datetime.now().isoformat(timespec="seconds"), "mission", 1, "import",
                       f"import du fichier exporté le {objet.get('exporte_le') or '?'}"))
    except Exception:
        try:
            os.remove(chemin_de(cle))
        except OSError:
            pass
        raise
    return cle, avertissements


# ---------- aides ----------

def mission():
    m = lire("mission", 1)
    for cle, defaut in (("seuils", {}), ("raci_roles", []), ("chiffrage", {})):
        try:
            m[cle] = json.loads(m.get(cle) or "null") or defaut
        except ValueError:
            m[cle] = defaut
    # Colonnes du RACI : "metier:<nom>" ou "acteur:<id>". Les anciennes bases stockaient
    # un simple libellé de rôle : on le lit comme un métier.
    m["raci_roles"] = [c if ":" in str(c) else f"metier:{c}" for c in m["raci_roles"]]
    return m


def ids(valeur):
    """Liste d'identifiants stockée en JSON ; tolère une valeur vide ou illisible."""
    try:
        liste = json.loads(valeur or "[]")
    except ValueError:
        return []
    return [int(x) for x in liste if str(x).isdigit()] if isinstance(liste, list) else []


def valeurs_raci(ligne):
    """Valeurs d'une ligne du RACI, clés normalisées comme les colonnes."""
    try:
        v = json.loads(ligne.get("valeurs") or "{}") or {}
    except ValueError:
        v = {}
    return {(k if ":" in k else f"metier:{k}"): x for k, x in v.items()}
