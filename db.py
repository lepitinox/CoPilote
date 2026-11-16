"""Stockage SQLite du co-pilote : une mission, ses objets de pilotage."""
import json
import os
import sqlite3

CHEMIN = os.environ.get(
    "COPILOTE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "copilote.db")
)

# table -> {colonne: type SQL}
TABLES = {
    "mission": {
        "nom": "TEXT", "client": "TEXT",
        "objectif_business": "TEXT", "objectif_solution": "TEXT", "objectif_projet": "TEXT",
        "porteur_business": "TEXT", "porteur_solution": "TEXT", "porteur_projet": "TEXT",
        "hypotheses": "TEXT", "date_cible": "TEXT", "duree_sprint_jours": "INTEGER",
        "seuils": "TEXT", "raci_roles": "TEXT",
    },
    # Cadre de la mission
    "lot": {"nom": "TEXT", "titre": "TEXT", "periode": "TEXT", "date": "TEXT",
            "statut": "TEXT", "rang": "INTEGER"},
    # axe : contenu | prerequis | pour_qui | comment | quoi | fonctionnalite
    "lot_element": {"lot": "TEXT", "axe": "TEXT", "libelle": "TEXT", "detail": "TEXT"},
    "story": {"etape": "TEXT", "rang_etape": "INTEGER", "libelle": "TEXT", "lot": "TEXT",
              "irritant": "INTEGER", "innovation": "INTEGER"},
    "activite": {"piste": "TEXT", "libelle": "TEXT", "debut": "TEXT", "fin": "TEXT"},
    "acteur": {"nom": "TEXT", "role": "TEXT", "cercle": "TEXT", "entite": "TEXT",
               "adherence": "TEXT"},
    "instance": {"nom": "TEXT", "chantier": "TEXT", "objectifs": "TEXT",
                 "participants": "TEXT", "frequence": "TEXT", "duree": "TEXT",
                 "rang": "INTEGER"},
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

ORDRE = {
    "jalon": "date", "livrable": "chantier, id", "sprint": "numero",
    "risque": "probabilite * impact DESC, id", "decision": "echeance, id",
    "compte_rendu": "date DESC, id DESC", "proposition": "id", "meteo": "id DESC",
    "lot": "rang, id", "lot_element": "id", "story": "rang_etape, id",
    "activite": "debut, id", "acteur": "cercle, entite, id", "instance": "rang, id",
    "raci": "rang, id",
}


def connexion():
    c = sqlite3.connect(CHEMIN)
    c.row_factory = sqlite3.Row
    return c


def initialiser():
    with connexion() as c:
        for table, cols in TABLES.items():
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


def vider():
    with connexion() as c:
        for table in TABLES:
            c.execute(f"DROP TABLE IF EXISTS {table}")
    initialiser()


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
        r = c.execute(f"SELECT * FROM {table} WHERE id = ?", (ident,)).fetchone()
        return dict(r) if r else None


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
    return lire(table, ident)


def modifier(table, ident, donnees):
    d = _filtrer(table, donnees)
    if d:
        affect = ", ".join(f"{k} = ?" for k in d)
        with connexion() as c:
            c.execute(f"UPDATE {table} SET {affect} WHERE id = ?", (*d.values(), ident))
    return lire(table, ident)


def supprimer(table, ident):
    with connexion() as c:
        c.execute(f"DELETE FROM {table} WHERE id = ?", (ident,))


def mission():
    m = lire("mission", 1)
    for cle, defaut in (("seuils", {}), ("raci_roles", [])):
        try:
            m[cle] = json.loads(m.get(cle) or "null") or defaut
        except ValueError:
            m[cle] = defaut
    return m
