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

Puis ouvrir http://127.0.0.1:8765. Le bouton « Missions » crée, importe, exporte ou met à la
corbeille une mission ; « Charger la démo » y ouvre une mission fictive, dans sa propre mission
`demo`.
Le serveur n'écoute que sur la machine locale.

`python-pptx` et `openpyxl` servent aux exports ; `anthropic` aux fonctions LLM ; `mcp` au serveur MCP. Sans clé
d'API, tout fonctionne sauf la rédaction par le modèle : la météo est alors générée au format
factuel, et l'extraction des comptes rendus est indisponible.

## Où sont les données

- **Les missions** : un fichier SQLite par mission dans le dossier `missions/` à côté de
  `server.py` (autre emplacement avec `COPILOTE_MISSIONS`). Chaque onglet du navigateur garde sa
  mission ouverte. Une mission mise à la corbeille est déplacée dans `missions/corbeille/`.
  Une ancienne base `copilote.db` est reprise automatiquement comme première mission (l'original
  est gardé sous `copilote.db.avant-multi-missions`).
- **L'export d'une mission** : un fichier JSON lisible (`format: copilote-mission`, toutes les
  tables et l'historique). Il se réimporte comme nouvelle mission, sans jamais en écraser une.
- **Les modèles d'export** : le dossier `modeles/` (autre emplacement avec `COPILOTE_MODELES`).

Les deux sont exclus du dépôt Git : ils contiennent des données de mission.

## Serveur MCP : piloter avec Claude

`mcp_server.py` expose le co-pilote à un LLM par le protocole MCP : Claude (ou tout client
MCP) lit les missions et les met à jour avec les mêmes règles que l'interface. Il travaille
sur les mêmes fichiers que le serveur web ; les deux peuvent tourner en même temps.

**Claude Code** (à lancer une fois, chemin absolu vers ce dossier) :

```bash
claude mcp add copilote -- python <chemin>/copilote/mcp_server.py
```

**Claude Desktop** (`claude_desktop_config.json`) :

```json
{ "mcpServers": { "copilote": { "command": "python", "args": ["<chemin>/copilote/mcp_server.py"] } } }
```

**Autres clients** : `python mcp_server.py --http` sert en Streamable HTTP sur
`http://127.0.0.1:8766/mcp` (port : `--port` ou `COPILOTE_MCP_PORT`), sur la machine locale seulement.

Ce que l'assistant peut faire :

- **Lire** (outils marqués en lecture seule) : `lister_missions`, `decrire_modele`, `fiche_mission`,
  `synthese`, `lister_elements` (avec recherche), `lire_element`, `suivi_risques`, `chiffrage`,
  `budget`, `attentes_client`, `gouvernance`, `historique`, `exporter_mission`.
- **Écrire** : `creer_element`, `modifier_element`, `supprimer_element`, `modifier_fiche_mission`,
  `annuler_modification`, `proposer_creneaux`, `creer_mission`.
- **Prompts prêts à l'emploi** : `revue_hebdomadaire`, `integrer_compte_rendu`, `preparer_comite`.
- **Ressources** : `copilote://missions`, `copilote://modele`, `copilote://mission/{cle}/synthese`.

Chaque outil prend un paramètre `mission` (clé) ; à défaut, la dernière mission ouverte. Les
chiffres viennent des calculs du co-pilote, jamais du modèle. Chaque écriture est inscrite à
l'historique avec l'origine « assistant (MCP) » : elle se relit et s'annule dans la vue
Historique. Attention : les données de la mission sont alors transmises au modèle utilisé par
le client MCP (même réserve que pour les fonctions LLM ci-dessous).

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

**Pilotage** : synthèse et alertes, indicateurs, suivi des risques, attentes du client,
décisions et actions, météo hebdomadaire.

**Finances** : chiffrage, budget.

**Saisie** : sprints, comptes rendus, historique des modifications.

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

### Historique des modifications

Chaque création, modification et suppression est inscrite avec l'état avant et après et son
origine (saisie, proposition acceptée, créneaux proposés, annulation…). « Annuler » défait une
entrée si l'élément n'a pas changé depuis ; l'annulation est elle-même inscrite. Les
chargements en masse (démo, import) ne sont pas inscrits, sauf une ligne « import ».

### Chiffrage

Deux modes qui coexistent :

- **Macro**, quand on sait peu de choses : chaque élément reçoit une taille (XS à XL), convertie
  en jours par un abaque, et une confiance qui donne la fourchette (± 15, 30 ou 50 %), valorisée
  au TJM moyen.
- **Détaillé**, après la collecte d'informations : charge basse, probable et haute par profil,
  combinée en estimation PERT et valorisée au TJM du profil. « Initialiser depuis le macro »
  reprend les éléments du macro comme point de départ.

Les majorations (pilotage, qualité, contingence) s'appliquent aux deux. Une comparaison par lot
montre l'écart entre les deux modes. Le mode retenu sert de budget de référence tant que le
budget vendu n'est pas saisi ; « Reporter en budget vendu » le fixe.

### Budget

Profils avec TJM de vente, coût journalier et reste à faire en jours ; temps consommés par mois
et par profil ; dépenses hors temps passé ; échéancier de facturation. Calculés : consommé,
reste à faire, atterrissage et écart au budget, marge prévue, facturé et payé. Déclencheurs :
dépassement prévu (sponsor), consommation en avance de plus de 10 points sur l'avancement moyen
des livrables, échéance de facturation dépassée, temps passé sur un profil sans TJM.

### Attentes du client

Par partie prenante : l'attente, sa catégorie et sa priorité, la satisfaction perçue (1 à 5), la
position (alignée, à recadrer, hors périmètre), notre réponse et la prochaine action. L'évolution
de la satisfaction est tirée de l'historique. Déclencheurs : attente prioritaire insatisfaite
(sponsor), attente à recadrer sans action, échéance dépassée ; revue à refaire après 30 jours.

Les déclencheurs du budget et des attentes s'ajoutent à ceux de la livraison dans la synthèse
et la météo.

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
| `db.py` | Modèle de données, un fichier SQLite par mission, historique, export et import JSON |
| `calculs.py` | KPI, atterrissage, déclencheurs, contrôles — déterministe, sans LLM |
| `finances.py` | Chiffrage en deux modes, budget, attentes du client — déterministe, sans LLM |
| `donnees.py` | Données composées partagées par l'API et les exports |
| `meteo.py` | Assemblage de la météo hebdomadaire |
| `agenda.py` | Créneaux des réunions, calendrier type d'un sprint, invitations `.ics` |
| `exports.py` | Description neutre de chaque vue et rendu PowerPoint / Excel avec modèles |
| `mcp_server.py` | Serveur MCP : outils, ressources et prompts pour un LLM |
| `llm.py` | Les trois fonctions LLM (extraire, rédiger, challenger) ; seul point d'accès au modèle |
| `demo.py`, `demo_cadre.py` | Mission de démonstration fictive |
| `static/index.html` | Page et styles |
| `static/app.js` | Socle de l'interface : formulaires, navigation, exports |
| `static/cadre.js` | Vues du cadre : feuille de route, lotissement, story map, macro-planning, organisation, gouvernance, sprint et KPI, RACI |
| `static/pilotage.js` | Vues de pilotage : synthèse, suivi des risques, décisions, météo, saisies |
| `static/graphes.js` | Indicateurs en graphiques |
| `static/finances.js` | Chiffrage, budget, attentes du client |
| `tests/` | `test_calculs.py`, `test_agenda_exports.py`, `test_missions.py`, `test_finances.py`, `test_mcp.py` (chacun : `python tests/<fichier>`) |

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
- L'historique n'enregistre pas l'auteur (pas d'authentification) : seulement l'origine.
- Le chiffrage et le budget sont en euros hors taxes, sans gestion de devises ni de TVA.
- Les invitations sont en heure locale flottante (sans fuseau) ; un modèle Excel ne reporte
  pas ses images sur les onglets ajoutés (seul le premier onglet les garde).
- Pas d'authentification, pas de masquage des noms avant envoi au modèle.
- Pas de connecteur (temps passés, facturation et agenda se saisissent à la main).
