# Co-pilote de mission — prototype

Prototype en mode intégré d'un co-pilote de mission appuyé sur un LLM : une mission, un
utilisateur, aucun connecteur. La note de cadrage (`cadrage-outil-copilotage.md`) et la méthode
de pilotage (`pilotage-mission.md`) sont conservées hors de ce dépôt.

## Lancer

```bash
python server.py
```

Puis ouvrir http://127.0.0.1:8765 et cliquer sur « Charger la démo » (mission fictive).
Le serveur n'écoute que sur la machine locale. Les données sont dans `copilote.db` (SQLite).

Sans autre installation, tout fonctionne sauf la rédaction par le modèle : la météo est
alors générée au format factuel, et l'extraction des comptes rendus est indisponible.

## Activer les fonctions LLM

```bash
pip install -r requirements.txt
```

Puis définir la variable d'environnement `ANTHROPIC_API_KEY` avant de lancer le serveur.
Le modèle se change avec `COPILOTE_MODELE` (par défaut `claude-opus-5-5`).

Attention : avec le LLM activé, le texte des comptes rendus et les données de la mission
sont envoyés à l'API. À n'utiliser sur des données client qu'une fois le mode d'hébergement
du modèle validé (décision D3 de la note de cadrage).

## Organisation du code

| Fichier | Rôle |
|---|---|
| `server.py` | Serveur HTTP local et routes de l'API |
| `db.py` | Modèle de données et stockage SQLite |
| `calculs.py` | KPI, atterrissage, déclencheurs, contrôles — déterministe, sans LLM |
| `meteo.py` | Assemblage de la météo hebdomadaire |
| `llm.py` | Les trois fonctions LLM (extraire, rédiger, challenger) ; seul point d'accès au modèle |
| `demo.py`, `demo_cadre.py` | Mission de démonstration fictive |
| `static/index.html` | Page et styles |
| `static/app.js` | Socle de l'interface : formulaires, navigation |
| `static/cadre.js` | Vues du cadre : feuille de route, lotissement, story map, macro-planning, organisation, gouvernance, sprint et KPI, RACI |
| `static/pilotage.js` | Vues de pilotage : synthèse, suivi des risques, décisions, météo, saisies |
| `static/graphes.js` | Indicateurs en graphiques |
| `tests/test_calculs.py` | Tests des calculs : `python tests/test_calculs.py` |

## Vues

**Cadre de la mission** : feuille de route (lots, grande temporalité, prérequis), lotissement
détaillé (pour qui, comment, quoi, grâce à quoi), story map, macro-planning au mois,
organisation et adhérences, gouvernance, rappel du sprint et des KPI à collecter, RACI.

**Pilotage** : synthèse et alertes, indicateurs, suivi des risques, décisions et actions,
météo hebdomadaire.

L'évolution d'un risque est calculée par rapport à la dernière session, c'est-à-dire la
dernière météo générée avant aujourd'hui : chaque météo garde une photo du registre.

## Principes tenus par le code

- Les chiffres viennent de `calculs.py`, jamais du modèle.
- Rien n'entre au registre sans validation : l'extraction produit des propositions.
- Chaque proposition porte l'extrait qui la justifie ; le serveur vérifie qu'il figure bien
  dans le compte rendu.
- La tendance de la météo est calculée ; s'en écarter exige un motif, qui est conservé.
- Les seuils des déclencheurs sont dans `calculs.SEUILS_DEFAUT` et se surchargent par mission
  (champ `seuils` de la mission, sans écran dédié pour l'instant).

## Limites connues

- Les fonctions LLM n'ont pas encore été exécutées contre l'API.
- Pas d'authentification, pas de masquage des noms avant envoi au modèle.
- Pas de budget, pas de multi-missions, pas de connecteur.
