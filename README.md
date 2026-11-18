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

Puis ouvrir http://127.0.0.1:8765.

- **« + Nouvelle mission »** (en-tête, ou dernière ligne du sélecteur de mission) : nom, client,
  date cible, budget vendu, objectifs, pilote et durée de sprint ; au besoin, un modèle de
  mission (voir ci-dessous) ou la reprise du cadre d'une mission existante — organisation, gouvernance (créneaux à reposer), profils et TJM,
  RACI, paramètres du chiffrage — sans aucune donnée de suivi. La mission s'ouvre sur la liste
  « Démarrage de la mission » (page À traiter) : fiche, lots, jalons, organisation, gouvernance,
  hypothèses, chiffrage ou budget, attentes, risques, chacune avec son raccourci.
- **« Missions »** : ouvrir, importer, exporter ou mettre à la corbeille une mission, l'enregistrer
  comme modèle ; « Charger la démo » ouvre une mission fictive, dans sa propre mission `demo`.

### Modèles de mission

Un modèle apporte le **cadre** (organisation par rôles, gouvernance, profils et TJM, RACI,
paramètres du chiffrage) et un **squelette** : lots et prérequis, jalons et activités en dates
relatives (recalculées depuis la date de début de la nouvelle mission), hypothèses et risques
types, story map, blocs de chiffrage préchoisis (premier chiffrage macro). Trois modèles sont
fournis : projet agile de développement, projet data / IA, mission de conseil ou de cadrage
(`modeles_fournis.py`). « Modèle » sur une mission l'enregistre comme modèle personnel
(dossier `missions/modeles-mission/`, fichier JSON) : le nom, le client, le budget et tout le
suivi sont exclus ; anonymisé par défaut (personnes remplacées par leur rôle, sans e-mail). Les
textes des risques, hypothèses et prérequis sont repris tels quels : à relire si la mission est
confidentielle.
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
  `annuler_modification`, `proposer_creneaux`, `creer_mission` (depuis un modèle ou avec reprise du
  cadre d'une mission), `lister_modeles_mission`, `enregistrer_modele_mission`, `demarrage_mission`, `chiffrer_avec_bloc`
  (avec `catalogue_chiffrage`, `a_traiter`, `preparer_seance` et `glissements` en lecture).
- **Demandes de changement** : `suivi_changements` (lecture), `creer_changement`,
  `chiffrer_changement`, `presenter_changement`, `decider_changement`.
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

Le menu est rangé par moment du pilotage :

- **Aujourd'hui** : À traiter (page d'accueil), Synthèse.
- **Piloter** : suivi des risques, attentes du client, décisions et actions (avec leur
  ancienneté), demandes de changement, macro-planning (reports et hypothèses du planning), indicateurs (avec, en bas de
  page, le rappel du fonctionnement d'un sprint et des KPI à collecter), budget (analyse).
- **Préparer et rendre compte** : gouvernance (préparation des séances), météo hebdomadaire.
- **Cadrer** : fiche mission et hypothèses, feuille de route (vue d'ensemble ou détail pour
  qui, comment, quoi ; état de chaque prérequis), story map, organisation, RACI, chiffrage.
- **Saisir** : sprints, saisie du budget (temps consommés, dépenses), comptes rendus, historique.

**À traiter** rassemble ce que la mission attend du pilote, classé en *maintenant* (actions et
décisions en retard, risques critiques sans porteur ou plan, jalons dépassés, prérequis
bloquants, hypothèses non vérifiées à temps, factures à émettre, attentes à recadrer, sprint à
saisir), *cette semaine* (échéances, réunions à préparer, météo à générer, propositions à valider)
et *à surveiller* (décisions qui traînent, hypothèses sans échéance, attentes à revoir). Les
boutons agissent directement (« Marquer faite », « Obtenu », « Confirmée », « Préparer »…).

L'évolution d'un risque est calculée par rapport à la dernière session, c'est-à-dire la
dernière météo générée avant aujourd'hui : chaque météo garde une photo du registre.

### Demandes de changement

Toute évolution du périmètre suit le même chemin :

1. **Origine** : une demande se crée directement, ou depuis une attente « à recadrer » ou une
   hypothèse invalidée (bouton « Demande de changement ») ; titre, demandeur, lot et description
   sont repris de l'origine.
2. **Chiffrage** avec le catalogue de blocs (trois niveaux), valorisé aux TJM et majoré comme le
   chiffrage de la mission, mais tenu à part ; décalage des jalons touchés en jours.
3. **Présentation** : une décision « à prendre » est créée et rattachée au comité ; elle apparaît
   dans les décisions à obtenir, la synthèse et l'ordre du jour de la séance.
4. **Décision** : accepter, refuser ou reporter, avec un motif. Accepter applique l'avenant :
   budget vendu augmenté du montant, reste à faire des profils augmenté des jours, jalons touchés
   décalés (date de référence comprise, puisque l'engagement change), attente d'origine
   « alignée », décision marquée prise — le tout tracé à l'historique sous « avenant ». Refuser
   passe l'attente d'origine « hors périmètre » avec le motif.

La vue de suivi donne le cumul accepté : montant, part du budget initial, jours et décalage.
Une demande à chiffrer depuis plus d'une semaine, ou chiffrée et pas encore présentée, remonte
dans À traiter.

### Hypothèses suivies

Chaque hypothèse (planning, chiffrage, périmètre, organisation, technique, données, budget) a un
statut — à vérifier, confirmée, invalidée —, la personne qui doit la confirmer, une échéance de
vérification et sa conséquence si elle tombe. Les passer à « invalidée » crée le risque
correspondant, relié à l'hypothèse. Elles apparaissent dans la fiche mission, le macro-planning
(hypothèses du planning), le chiffrage (hypothèses du chiffrage, alerte si l'une est invalidée),
la préparation des comités et des points de suivi, et la page À traiter. Un bloc du catalogue
retenu au niveau « aucune information » crée une hypothèse de chiffrage à vérifier. L'ancien
champ texte des hypothèses est repris automatiquement, une ligne par hypothèse.

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

### Synthèse, glissements et préparation de séance

- **Synthèse** : les trois questions du sponsor, chacune avec un état (vert, orange, rouge, non
  mesurable), une phrase et son détail — délai (atterrissage des sprints, sinon jalons et date
  cible), budget (atterrissage et vendu), client (attentes) — puis les décisions à obtenir avec
  leur décideur et leur ancienneté, et la tendance des dernières météos.
- **Glissements** : jalons et lots ont une date de référence (l'engagement), posée à la première
  date saisie et modifiable seulement après un avenant. Le macro-planning montre la date initiale
  et le report ; un report de plus de deux semaines déclenche une alerte (sponsor s'il dépasse la
  date cible), un jalon dépassé non atteint aussi. Le nombre de reports vient de l'historique.
- **Préparer une séance** (bouton de chaque instance, ou depuis À traiter) : ordre du jour minuté
  selon le type de séance — comité (trajectoire, jalons, risques critiques, attentes, décisions,
  budget), point de suivi (actions, risques, jalons, attentes des participants), rituels agiles
  (capacité, chiffres du sprint, demandes de périmètre) — avec les horaires, les messages clés,
  l'export PowerPoint et le texte à copier dans l'invitation. Le temps non utilisé va aux
  échanges plutôt que d'allonger les points.

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

**Catalogue de blocs** : 34 blocs types prêts à l'emploi (récupération de la data, qualité des
données, pipeline, API, écran standard, interface avec un système tiers, POC d'IA générative,
RAG, recette, mise en production, RGPD, conduite du changement, pilotage…), en neuf familles.
Chaque bloc a trois niveaux : **simple et clair** (rapide), **compliqué mais chemin clair**
(moyen), **aucune information** (long), avec des jours par rôle type et, pour chaque niveau,
un critère de choix : les signes concrets qui orientent vers ce niveau (accès ouverts ou non,
propriétaire identifié, documentation…) et ce que couvre la charge. Ce critère est repris dans
l'hypothèse de la ligne créée, pour justifier le chiffrage au client
(textes dans `catalogue_criteres.py`). Appliqué avec un lot et une
quantité, il crée une ligne par rôle en mode détaillé (rôle rapproché des profils de la mission
par nom, puis par métier) ou une ligne en mode macro ; la fourchette suit le niveau. Les blocs se
personnalisent ou se créent depuis l'interface ; ils sont communs à toutes les missions
(`missions/catalogue-chiffrage.json`). Les valeurs par défaut sont un point de départ à calibrer.

Les majorations (pilotage, qualité, contingence) s'appliquent aux deux. Un indice
d'incertitude dit si le chiffrage est défendable : étendue de la fourchette, part de la charge
chiffrée sans information, part du risque haut couverte par la contingence, lignes sans profil. Une comparaison par lot
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
| `catalogue_criteres.py` | Critères de choix des trois niveaux de chaque bloc |
| `catalogue.py` | Catalogue des blocs de chiffrage à trois niveaux, personnalisation, application |
| `modeles_mission.py`, `modeles_fournis.py` | Modèles de mission : enregistrement, application, modèles fournis |
| `changements.py` | Demandes de changement : création, chiffrage, présentation, décision, avenant |
| `pilote.py` | Besoins du pilote : à traiter, glissements, trois réponses, préparation de séance |
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
| `static/changements.js` | Demandes de changement |
| `static/pilote.js` | Page À traiter et préparation de séance |
| `static/finances.js` | Chiffrage, budget, attentes du client |
| `tests/` | `test_calculs.py`, `test_agenda_exports.py`, `test_missions.py`, `test_finances.py`, `test_mcp.py`, `test_catalogue.py`, `test_pilote.py`, `test_changements.py`, `test_modeles.py` (chacun : `python tests/<fichier>`) |

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
