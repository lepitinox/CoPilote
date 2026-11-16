# Co-pilote de mission — prototype

Prototype en mode intégré d'un co-pilote de mission appuyé sur un LLM : une mission, un
utilisateur, aucun connecteur. La note de cadrage (`cadrage-outil-copilotage.md`) et la méthode
de pilotage (`pilotage-mission.md`) sont conservées hors de ce dépôt.

## Lancer

```bash
pip install -r requirements.txt
```

```bash
python server.py
```

Puis ouvrir http://127.0.0.1:8765 et cliquer sur « Charger la démo » (mission fictive).
Le serveur n'écoute que sur la machine locale.

`python-pptx` et `openpyxl` servent aux exports ; `anthropic` aux fonctions LLM. Sans clé
d'API, tout fonctionne sauf la rédaction par le modèle : la météo est alors générée au format
factuel, et l'extraction des comptes rendus est indisponible.

## Où sont les données

- **La mission** : un fichier SQLite, `copilote.db`, à côté de `server.py` (autre emplacement
  avec la variable `COPILOTE_DB`). Une base = une mission. Pour sauvegarder ou transmettre une
  mission, copier ce fichier ; « Charger la démo » l'écrase.
- **Les modèles d'export** : le dossier `modeles/` (autre emplacement avec `COPILOTE_MODELES`).

Les deux sont exclus du dépôt Git : ils contiennent des données de mission.

## Activer les fonctions LLM

Définir la variable d'environnement `ANTHROPIC_API_KEY` avant de lancer le serveur.
Le modèle se change avec `COPILOTE_MODELE` (par défaut `claude-opus-5-5`).

Attention : avec le LLM activé, le texte des comptes rendus et les données de la mission
sont envoyés à l'API. À n'utiliser sur des données client qu'une fois le mode d'hébergement
du modèle validé (décision D3 de la note de cadrage).

## Vues

**Cadre de la mission** : feuille de route (lots, grande temporalité, prérequis), lotissement
détaillé (pour qui, comment, quoi, grâce à quoi), story map, macro-planning au mois,
organisation et adhérences, gouvernance, rappel du sprint et des KPI à collecter, RACI.

**Pilotage** : synthèse et alertes, indicateurs, suivi des risques, décisions et actions,
météo hebdomadaire.

L'évolution d'un risque est calculée par rapport à la dernière session, c'est-à-dire la
dernière météo générée avant aujourd'hui : chaque météo garde une photo du registre.

### Métiers, organisation et RACI

Un catalogue de métiers (UX / UI, Développeur, Product owner…) est prérempli et se complète
depuis la vue Organisation. Chaque acteur porte un métier. Les colonnes du RACI se choisissent
parmi les métiers (la colonne regroupe toutes les personnes qui l'exercent) et les personnes
de l'organisation (colonne nominative), ou un mélange des deux.

### Réunions

Chaque instance de gouvernance a des participants choisis dans l'organisation, une
récurrence, un créneau et une durée. « Proposer des créneaux » les pose à partir du rythme des
sprints, sans chevauchement sur huit semaines, hors week-end et hors pause de midi.
« Télécharger les invitations » produit un fichier `.ics` (séries récurrentes, participants
ayant un e-mail) à importer dans Outlook ou Google Agenda, d'où l'on envoie les invitations.

### Exports PowerPoint et Excel

Chaque vue s'exporte en PowerPoint, et en Excel sauf la météo. Le bouton « Modèles » de
chaque vue permet de télécharger le modèle utilisé, de le modifier, puis de le renvoyer
pour cette vue ou pour toutes les vues :

- **PowerPoint** : le masque des diapositives donne couleurs, polices, logo et pied de page ;
  la disposition « Titre seul » sert aux pages de contenu ; les diapositives présentes dans le
  modèle (page de garde) sont conservées.
- **Excel** : la première feuille sert de gabarit pour chaque onglet ; la cellule `{{contenu}}`
  indique où écrire et donne le style des en-têtes, la cellule au-dessous celui des lignes.
- Jetons remplacés dans les deux : `{{titre}}`, `{{mission}}`, `{{date}}`.

Ordre de recherche : `modeles/<vue>.pptx|xlsx`, puis `modeles/commun.pptx|xlsx`, puis le
modèle par défaut.

## Organisation du code

| Fichier | Rôle |
|---|---|
| `server.py` | Serveur HTTP local et routes de l'API |
| `db.py` | Modèle de données et stockage SQLite |
| `calculs.py` | KPI, atterrissage, déclencheurs, contrôles — déterministe, sans LLM |
| `donnees.py` | Données composées partagées par l'API et les exports |
| `meteo.py` | Assemblage de la météo hebdomadaire |
| `agenda.py` | Créneaux des réunions, calendrier type d'un sprint, invitations `.ics` |
| `exports.py` | Description neutre de chaque vue et rendu PowerPoint / Excel avec modèles |
| `llm.py` | Les trois fonctions LLM (extraire, rédiger, challenger) ; seul point d'accès au modèle |
| `demo.py`, `demo_cadre.py` | Mission de démonstration fictive |
| `static/index.html` | Page et styles |
| `static/app.js` | Socle de l'interface : formulaires, navigation, exports |
| `static/cadre.js` | Vues du cadre : feuille de route, lotissement, story map, macro-planning, organisation, gouvernance, sprint et KPI, RACI |
| `static/pilotage.js` | Vues de pilotage : synthèse, suivi des risques, décisions, météo, saisies |
| `static/graphes.js` | Indicateurs en graphiques |
| `tests/` | `python tests/test_calculs.py` et `python tests/test_agenda_exports.py` |

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
- Une seule mission par base ; pas d'export ni d'import de mission en un fichier lisible.
- Les invitations sont en heure locale flottante (sans fuseau) ; un modèle Excel ne reporte
  pas ses images sur les onglets ajoutés (seul le premier onglet les garde).
- Pas d'authentification, pas de masquage des noms avant envoi au modèle.
- Pas de budget, pas de multi-missions, pas de connecteur.
