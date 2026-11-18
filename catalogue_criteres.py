"""Critères de choix des trois niveaux de chaque bloc du catalogue.

Pour chaque bloc : (rapide, moyen, long). Chaque texte dit dans quelle situation choisir le
niveau (les signes observables) et ce que la charge couvre, pour que le pilote sache pourquoi
il retient ce preset et puisse le justifier au client.
"""

CRITERES = {
    # ---- Cadrage et conception
    "cadrage-besoin": (
        "Un interlocuteur métier unique et disponible, un besoin déjà écrit (note, cahier des charges) "
        "à confirmer. Deux ateliers suffisent : relecture, priorisation, validation.",
        "Plusieurs directions métier concernées, besoin connu dans les grandes lignes mais pas formalisé, "
        "quelques arbitrages à obtenir. Série d'ateliers, synthèse, priorisation et validation en comité.",
        "Besoin flou ou contradictoire selon les interlocuteurs, sponsors pas encore identifiés, "
        "processus actuel à comprendre d'abord. Entretiens individuels, observation du terrain, "
        "ateliers de convergence et plusieurs allers-retours de validation."),
    "specifications": (
        "Module simple (une dizaine de règles), règles déjà connues du métier, peu de cas particuliers. "
        "Rédaction directe et une relecture.",
        "Règles nombreuses mais maîtrisées par un référent métier, quelques cas limites à instruire, "
        "dépendances avec d'autres modules. Rédaction, ateliers de clarification, revue technique.",
        "Règles non documentées, dispersées dans les têtes ou dans un existant, exceptions nombreuses, "
        "pas de référent identifié. Recueil, reconstitution des règles, validations successives."),
    "architecture": (
        "Socle et standards du client imposés et connus, solution proche de l'existant. "
        "Dossier court qui applique les patterns en place.",
        "Quelques choix structurants à faire (hébergement, intégration, données), standards du client "
        "à respecter, passage en comité d'architecture. Étude d'options et dossier complet.",
        "Pas de standards, contraintes de sécurité ou de réglementation inconnues, système cible "
        "à inventer. Cartographie de l'existant, étude d'options, revues sécurité, comités successifs."),
    "maquettes-ux": (
        "Parcours court, charte et bibliothèque de composants existantes, utilisateurs bien connus. "
        "Maquettes directement à partir de la charte, une itération.",
        "Parcours de plusieurs écrans, charte à décliner, deux ou trois itérations avec le métier "
        "et quelques utilisateurs.",
        "Pas de charte, utilisateurs mal connus ou très hétérogènes, parcours à inventer. Entretiens "
        "utilisateurs, personas, prototypes, tests utilisateurs et itérations."),
    "poc-technique": (
        "Technologie connue de l'équipe, question précise (« est-ce que X sait faire Y ? »), "
        "environnement disponible. Prototype de quelques jours et conclusion.",
        "Technologie nouvelle pour l'équipe ou intégration à tester, environnement à monter, critères "
        "de réussite à définir avec le client.",
        "Question encore floue, plusieurs options à comparer, accès aux environnements ou aux données "
        "incertains. Cadrage du POC, plusieurs prototypes, comparaison et recommandation argumentée."),
    # ---- Données
    "recuperation-data": (
        "Source connue avec un propriétaire identifié, accès déjà ouverts, format documenté "
        "(API, export standard, table accessible). Extraction et contrôle de complétude.",
        "Source connue mais accès à demander, format à comprendre (fichiers plats, schéma non documenté), "
        "quelques champs manquants à faire compléter. Demandes d'accès, extraction, contrôles, "
        "allers-retours avec le propriétaire.",
        "On ne sait pas où est la donnée ni qui la possède, accès soumis à validation (sécurité, RGPD), "
        "extractions incomplètes probables. Enquête, demandes formelles, relances, extractions "
        "successives jusqu'à complétude."),
    "qualite-donnees": (
        "Données propres dans l'ensemble, règles de qualité évidentes (formats, doublons). "
        "Profilage et corrections automatiques.",
        "Anomalies connues mais nombreuses, règles à valider avec le métier, corrections partiellement "
        "manuelles. Profilage, règles, corrections, indicateurs partagés.",
        "Qualité inconnue, pas de référentiel, interprétations divergentes d'un même champ. "
        "Profilage poussé, ateliers de définition, corrections itératives, suivi de la qualité."),
    "modelisation-donnees": (
        "Domaine simple (quelques entités), modèle cible proche d'un existant ou d'un standard. "
        "Adaptation et dictionnaire.",
        "Domaine riche (dizaines d'entités), historisation ou règles de gestion à modéliser, "
        "validation avec l'architecture.",
        "Domaine mal compris, sources multiples à réconcilier, pas de référentiel commun. "
        "Analyse des sources, ateliers métier, modèle construit et révisé en plusieurs passes."),
    "pipeline-donnees": (
        "Une source, transformations simples, outillage d'ordonnancement en place. "
        "Développement, planification, supervision standard.",
        "Plusieurs sources ou transformations métier, reprise sur erreur et historisation à gérer, "
        "environnements à configurer, recette des flux.",
        "Volumes ou fréquences inconnus, outillage à choisir ou à installer, exigences d'exploitation "
        "non définies. Conception, socle, développement, tests de charge et mise en exploitation."),
    "reporting": (
        "Indicateurs déjà définis, données prêtes dans un entrepôt, outil de restitution en place. "
        "Construction du tableau et une revue.",
        "Indicateurs à préciser avec le métier, données à préparer, quelques itérations de mise en forme.",
        "Indicateurs à inventer, définitions divergentes entre équipes, données à aller chercher. "
        "Ateliers de définition, préparation des données, prototypes et itérations."),
    "migration-donnees": (
        "Volumétrie modeste, correspondance quasi directe entre ancien et nouveau modèle, "
        "une migration à blanc suffit.",
        "Correspondances à écrire, données à nettoyer, plusieurs migrations à blanc et contrôles "
        "de réconciliation signés par le métier.",
        "Ancien système mal connu, gros volumes, règles de reprise à inventer, fenêtre de bascule "
        "contrainte. Analyse, scripts, nombreuses répétitions, plan de bascule et de retour arrière."),
    # ---- Intelligence artificielle
    "poc-ia-generative": (
        "Cas d'usage précis et cadré (résumer, classer, extraire), données d'exemple disponibles, "
        "modèle accessible. Prompting, démonstration.",
        "Cas d'usage à préciser avec le métier, données à préparer, intégration à un outil existant, "
        "premières mesures de qualité.",
        "Cas d'usage encore vague, données sensibles ou non accessibles, choix du modèle et de "
        "l'hébergement à faire. Cadrage, préparation, plusieurs itérations, évaluation et recommandation."),
    "modele-ml": (
        "Variable cible claire, données historiques propres et étiquetées, problème classique "
        "(classification, régression). Entraînement et évaluation.",
        "Variables à construire, étiquettes partielles, déséquilibre des classes ou dérive à traiter, "
        "comparaison de plusieurs modèles.",
        "Cible à définir avec le métier, peu ou pas d'étiquettes, données dispersées. Construction du "
        "jeu d'apprentissage, exploration, modèles successifs, validation métier."),
    "evaluation-ia": (
        "Critères de qualité connus et jeu de test déjà disponible. Mesure et rapport.",
        "Jeu de test à constituer avec le métier, métriques et seuils d'acceptation à fixer, "
        "garde-fous standards (filtrage, refus).",
        "Pas de définition partagée d'une bonne réponse, enjeux réglementaires ou de réputation. "
        "Construction du référentiel, annotation, métriques, garde-fous spécifiques, surveillance."),
    "mlops": (
        "Plateforme MLOps du client en place et utilisée, modèle simple à packager. Déploiement "
        "et supervision standard.",
        "Plateforme existante mais à configurer pour ce modèle, réentraînement à automatiser, "
        "supervision des dérives à mettre en place.",
        "Aucune plateforme, exigences d'exploitation et de sécurité à définir, équipes d'exploitation "
        "à convaincre. Socle, chaîne de déploiement, supervision, passation."),
    "rag-documents": (
        "Corpus réduit (quelques centaines de documents), formats propres, accès ouverts, questions "
        "types connues. Indexation, recherche, réponses sourcées.",
        "Corpus volumineux ou formats hétérogènes (PDF scannés, tableaux), droits d'accès à respecter, "
        "jeu de questions à constituer et évaluation.",
        "Corpus à rassembler, confidentialité forte, attentes de qualité floues. Collecte, nettoyage, "
        "découpage, réglages successifs, évaluation et garde-fous."),
    # ---- Développement
    "ecran-standard": (
        "Écran à l'image d'écrans existants, sur un socle et des composants en place, règles simples.",
        "Écran avec plusieurs onglets ou contrôles croisés, quelques composants à créer, maquette à suivre.",
        "Écran nouveau dans son principe, socle à adapter, règles à préciser en cours de route."),
    "regle-gestion": (
        "Règle courte et écrite, sans cas particulier, testable avec quelques exemples.",
        "Règle avec plusieurs branches et cas limites connus, jeux de tests à construire avec le métier.",
        "Règle à reconstituer (existant, experts), exceptions nombreuses, résultats à réconcilier "
        "avec l'ancien calcul."),
    "api-exposee": (
        "Contrat d'interface fourni, données disponibles, socle d'API et sécurité en place.",
        "Contrat à co-construire avec les consommateurs, plusieurs opérations, sécurité à configurer, "
        "documentation et tests de contrat.",
        "Consommateurs et usages incertains, versionnement et sécurité à définir, performances exigeantes."),
    "authentification": (
        "Fournisseur d'identité du client en place (SSO), rôles simples. Branchement et rôles.",
        "Rôles et droits fins à modéliser, plusieurs populations d'utilisateurs, revue sécurité.",
        "Pas de fournisseur d'identité, utilisateurs externes, exigences d'audit ou réglementaires. "
        "Choix de la solution, intégration, droits fins, traçabilité, homologation."),
    "notifications": (
        "Quelques messages simples, service d'envoi existant.",
        "Plusieurs familles de messages, modèles personnalisés, suivi des envois et désabonnement.",
        "Canaux multiples (e-mail, SMS, notifications mobiles), contenus réglementés, service d'envoi "
        "à choisir."),
    "generation-documents": (
        "Gabarit fourni, données simples, un format de sortie.",
        "Gabarit à concevoir, données de plusieurs sources, plusieurs formats ou mises en forme "
        "conditionnelles.",
        "Documents réglementaires ou contractuels, validations juridiques, gros volumes à produire."),
    # ---- Intégration
    "interface-tiers": (
        "API du tiers documentée et stable, environnement de test disponible, interlocuteur réactif.",
        "Documentation partielle, environnement de test à obtenir, cas d'erreur à traiter, "
        "tests de bout en bout à planifier avec l'éditeur.",
        "Interface à créer côté tiers, éditeur peu disponible ou planning externe incertain. "
        "Prévoir l'attente, les relances et la coordination : le risque est hors de l'équipe."),
    "retro-ingenierie": (
        "Code lisible et récent, quelques zones à comprendre, auteurs joignables.",
        "Code ancien mais structuré, documentation absente, tests à écrire pour sécuriser les évolutions.",
        "Technologie ancienne, aucun auteur joignable, comportements à reconstituer par l'observation."),
    # ---- Qualité et mise en production
    "strategie-recette": (
        "Périmètre limité, cas de test connus du métier, outil de suivi en place.",
        "Plusieurs lots ou parcours, jeux de données à préparer, organisation de la recette métier "
        "à monter.",
        "Pas de pratique de recette chez le client, données de test à anonymiser, acteurs à mobiliser "
        "et former."),
    "recette": (
        "Testeurs métier disponibles, cas de test écrits, peu d'anomalies attendues.",
        "Cas de test à compléter, deux cycles de recette prévus, non-régression à assurer.",
        "Testeurs peu disponibles, qualité incertaine, plusieurs cycles et arbitrages des anomalies "
        "en comité."),
    "tests-performance": (
        "Exigences chiffrées, outillage et environnement représentatif disponibles.",
        "Scénarios à construire, environnement à préparer, une ou deux boucles d'optimisation.",
        "Exigences inconnues, pas d'environnement représentatif, goulots d'étranglement à chercher "
        "dans plusieurs couches."),
    "ci-cd": (
        "Chaîne d'intégration du client en place : il suffit d'y brancher l'application.",
        "Chaîne à adapter, plusieurs environnements à créer, droits et secrets à configurer.",
        "Aucune chaîne, infrastructure à provisionner, exigences de sécurité et d'exploitation à définir."),
    "mise-en-production": (
        "Mise en production standard, procédure rodée, faible impact utilisateur.",
        "Bascule à planifier avec les équipes d'exploitation, répétition, support renforcé quelques "
        "semaines.",
        "Bascule risquée (migration, arrêt de service, nombreux utilisateurs), plan de retour arrière, "
        "hypercare prolongé."),
    # ---- Sécurité et conformité
    "risques-securite-rgpd": (
        "Données peu sensibles, gabarits d'analyse du client disponibles.",
        "Données personnelles, registre de traitement à compléter, échanges avec le délégué à la "
        "protection des données.",
        "Données sensibles (santé, financières), transferts hors UE, sous-traitants multiples, "
        "méthode d'analyse à mettre en place."),
    "homologation": (
        "Processus d'homologation connu et léger, dossier type à compléter.",
        "Dossier complet, audit ou tests d'intrusion à piloter, quelques réserves à lever.",
        "Processus inconnu ou exigeant (secteur régulé), plusieurs instances de validation, "
        "réserves importantes probables."),
    # ---- Accompagnement et pilotage
    "conduite-changement": (
        "Petite population, changement limité, relais terrain identifiés.",
        "Population large ou plusieurs métiers, impacts sur les processus, plan de communication "
        "et de formation.",
        "Changement profond (organisation, métier), résistances attendues, populations dispersées. "
        "Analyse d'impacts, réseau de relais, formations multiples, suivi de l'adoption."),
    "documentation-transfert": (
        "Équipe de reprise identifiée et compétente, documentation au fil de l'eau.",
        "Équipe de reprise à former, documentation à consolider, sessions de passation.",
        "Repreneur inconnu ou éloigné du sujet, documentation inexistante, période de "
        "double fonctionnement."),
    "pilotage-mois": (
        "Petite équipe, client unique, gouvernance légère (un comité par mois).",
        "Équipe de taille moyenne, plusieurs parties prenantes, comités réguliers et reporting "
        "budgétaire.",
        "Nombreuses parties prenantes, dépendances externes, enjeux politiques, gouvernance à "
        "construire et à animer."),
}
