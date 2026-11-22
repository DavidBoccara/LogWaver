# Historique de conception de LogWaver

Ce document retrace la conception de LogWaver, de la demande initiale jusqu'à la
mise sous gestion de configuration. Il est issu de la discussion de conception
menée le 20 novembre 2026 avec l'assistant Claude.

## Portée et fidélité de ce document

* **Demandes de l'utilisateur** : reproduites **intégralement et mot pour mot**.
* **Réponses de l'assistant** : reproduites **intégralement** (texte final de
  chaque réponse).
* **Travail réalisé entre les réponses** (création de fichiers, commandes, tests) :
  **résumé** chronologiquement, avec les résultats obtenus et les problèmes
  rencontrés. Les sorties brutes des commandes et le raisonnement interne de
  l'assistant ne sont pas reproduits ; le code produit, lui, est intégralement
  dans le dépôt et son évolution est tracée par l'historique Git.
* Les heures sont en heure de Paris (UTC+01:00).

## Sommaire

1. [Échange 1 — Cahier des charges et réalisation de l'outil](#échange-1)
2. [Échange 2 — Mise sous gestion de configuration](#échange-2)
3. [Échange 3 — Publication sur le dépôt GitHub](#échange-3)
4. [Échange 4 — Traçabilité de la conception](#échange-4)
5. [Échange 5 — Simplification, didacticiel et regroupement](#échange-5)
6. [Échange 6 — Publication de la version 1.1.0](#échange-6)
7. [Échange 7 — Où trouver la nouvelle version ?](#échange-7)
8. [Échange 8 — Plugins par extension, assistant regex, priorités et correspondance](#échange-8)
5. [Registre des décisions de conception](#registre-des-décisions-de-conception)
6. [Problèmes rencontrés et traitements](#problèmes-rencontrés-et-traitements)
7. [Couverture des exigences](#couverture-des-exigences)

---

<a id="échange-1"></a>
## Échange 1 — Cahier des charges et réalisation de l'outil (19:01)

### Demande de l'utilisateur (fichier joint, texte intégral)

> : Tu agis en tant qu'Expert Architecte logiciel et Développeur Python Senior, spécialiste des interfaces graphiques avec PyQt5. Ton objectif est de concevoir un outil avec une dette technique proche de zéro.
>
> Projet : Je veux concevoir un outil graphique qui est un waver, cet outil permettrait de lire un fichier de log provenant de n'importe quel outil. Il doit être capable d'extraire des informations provenant de ce fichier de log comme des warnings, note, erreurs et les afficher dans une fenêtre graphique, le type d'éléments à extraire doit pouvoir varier en fonction du fichier plugin que nous décrirons par la suite.  L'utilisateur doit pouvoir filtrer la vue de la fenêtre. il doit pouvoir sélectionner un ou plusieurs éléments et les classer en fonction d'une liste d'éléments décrits dans un fichier de configuration (qui n'est pas le fichier plugin), par exemple:
>
> ·  À traiter (To Do / Pending) : nouvelle exception détectée, non encore analysée.
>
> ·  En cours d'analyse (In Investigation) : Un analyste examine le log pour comprendre l'origine.
>
> ·  Justifié / Accepté (Justified / Approved) : L'exception est validée et ne doit plus générer d'alerte.
>
> ·  Rejeté (Rejected) : L'exception n'est pas acceptable, le problème doit être corrigé.
>
> ·  Clôturé (Closed) : Le problème a été résolu techniquement (le log n'apparaît plus).
>
> L'utilisateur qui sélectionne un élément de cette liste doit pouvoir entrer une justification pour la catégorie choisie. Une fois la justification réalisée l'outil doit retirer l'élément justifié et le placer dans une autre catégorie avec la justification. Une fois fait, tu dois pouvoir sauvegarder à tout moment ton travail, revenir en arrière via un ctrl z, l'utilisateur doit pouvoir obtenir un fichier projet de tout ce qu'il a fait. Si l'utilisateur ouvre l'outil avec le fichier projet et ouvre un nouveau fichier de log, l'outil doit être capable de retrouver tous les éléments déjà justifiés et leur appliquer la justification déjà existante.
>
> Pour fonctionner sur n'importe quel outil et avec n'importe quel fichier de log. L'outil doit utiliser des fichiers de type plugin dans lequel on doit retrouvés :
>
> Nom de l'outil : TINTIN
>
> Type d'éléments recherché : Note, Warning, Error
>
> Type d'éléments a extraire pour : Note ( Nom du fichier, ligne, code, description), Warning ( Nom du fichier, ligne, code, description), Error ( Nom du fichier, ligne, code, description),
>
> Regex pour chaque éléments : Note ( Nom du fichier : "REGEX", ligne: "REGEX",  code: "REGEX",  description: "REGEX"), Warning ( Nom du fichier: "REGEX", ligne: "REGEX", code: "REGEX", description: "REGEX"), Error ( Nom du fichier: "REGEX",  ligne: "REGEX",  code: "REGEX", description),
>
> Le fichier plugin doit être facile à lire et à modifier à la main, tu peux concevoir un outil dans le logiciel permettant d'aider à concevoir ce fichier notamment avec un regex viewer permettant de vérifier sa regex ou de la concevoir de manière automatique.
>
> Dans la suite du prompt, nous prendrons l'exemple du warning à traiter.
>
> Je veux que tu crées une fonction qui génère des promptes à destination d'une ia, cette IA je l'ajouterais moi après donc conçois juste les promptes et fait les afficher sur le terminal, L'objectif et que pour chaque élément sélectionné par l'utilisateur, si l'utilisateur le souhaite il peut afficher une aide, le prompt doit donc demander à l'IA quelque chose comme par exemple: "peut-tu m'expliquer le warning avec le code CL245 qui provient de l'outil TINTIN et qui me renvoie le warning : "le fichier dada.txt est introuvable", peut-tu me dire pour quelle raison c'est un problème si c'est un problème ou pour quelle raison ça ne l'est pas, peut-tu me faire une proposition de justification pour ce warning " à ce moment-là l'utilisateur peut si il le souhaite utiliser la justification générée par IA .pour résumer :  Sur la demande de l'utilisateur, l'outil affiche un texte qui explique ton warning, et te propose une justification de : pourquoi c'est un problème ou pourquoi ce n'est pas un problème en fonction de la gravité du warning. Tu pourras alors sur l'appui d'un simple bouton justifier le warning avec la justification de l'ia. Cette justification tu peux la faire très simplement à tous les warnings du même code warning par exemple.
>
> Je veux que l'outil puisse ouvrir sur la demande de l'utilisateur un pdf qui contient l'explication de chaque warning a la page du code du warning. Ce pdf sera renseigné avec le fichier plugin et un fichier en plus décrivant pour chaque warning la page dans le pdf qui y fait référence.
>
> Je veux que la justification soit associée à un nom utilisateur donc au moment de justifier le warning l'utilisateur doit renseigner son nom.
>
> La première justification on renseigne le nom puis ensuite on a plus besoin de le faire.
>
> Une fois le warning justifié l'utilisateur peut à tout moment enlever la justification à ce moment-là le warning repasse dans la liste des warnings non justifier sans classe.
>
> Le cœur de l'outil c'est le suivi de warning. Par exemple, le concepteur A d'un code qui produit des warnings, a réussi à les justifier. Il fournit son code a un concepteur B et donc qui va hériter des nouveaux warnings. Le concepteur B doit pouvoir utiliser le fichier automatique de justification qu'a obtenu le concepteur A pour justifier automatiquement les warnings du code qu'il a réutilisé et il doit donc se retrouver qu'avec les warnings non justifiés.
>
> Si dans le plugin l'outil peut extraire le chemin du fichier par exemple. L'outil doit pouvoir t'aider à aller directement à la ligne du warning
>
> L'utilisateur doit pouvoir a tout moment extraire un fichier Excel de son travail
>
> Contraintes Techniques Strictes :
>
> Stack Technologique : Utilise EXCLUSIVEMENT les bibliothèques suivantes : PyQt5, numpy, python-docx et PyQtWebEngine. Aucun autre package tiers ne doit être installé.
> Architecture : Applique rigoureusement le pattern MVC (Modèle-Vue-Contrôleur) ou MVP (Modèle-Vue-Présentateur) pour séparer totalement la logique métier (calculs, manipulation de documents) de l'interface utilisateur.
> Structure du Code :
> Découpe le code en plusieurs modules/fichiers (ou simule-le via des classes distinctes et clairement séparées si tu fournis un seul bloc).
> Utilise la Programmation Orientée Objet (POO) avec une encapsulation forte.
> Implémente une gestion d'erreurs robuste via des blocs try...except avec des logs clairs.
> Normes de Codage :
> Respect strict de la PEP 8.
> Nomenclature : snake_case pour les fonctions et variables, PascalCase pour les classes, UPPER_CASE pour les constantes.
> Typage : Utilise le type hinting (ex: def calculate(data: np.array) -> float:) pour toutes les signatures de fonctions.
> Documentation : Chaque classe et méthode doit posséder une docstring concise expliquant son rôle, ses paramètres et sa valeur de retour.
> Qualité UI/UX :
> L'interface doit être responsive (utilisation des QLayouts : QVBoxLayout, QHBoxLayout, QGridLayout). Ne jamais utiliser de positionnement absolu.
> Séparez le style visuel (QSS/CSS) de la structure logique.
> Livrables attendus :
>
> Une structure de fichiers suggérée.
> Le code source complet, modulaire, commenté et prêt à l'emploi.
> Un guide rapide d'installation et d'exécution.
> Interdiction : Ne fais aucun compromis sur la lisibilité pour gagner en concision. Je préfère un code plus long mais parfaitement maintenable qu'un code compact et opaque.

### Travail réalisé (résumé chronologique)

1. **Annonce et vérification de l'environnement** — vérification de Python 3.13,
   numpy et python-docx disponibles ; PyQt5 et PyQtWebEngine installés pour
   pouvoir tester l'interface.
2. **Plan de travail** en quatre étapes : couche Modèle, couche Vue et QSS,
   Présentateurs et point d'entrée, exemples / tests / documentation /
   livraison.
3. **Couche Modèle (Python pur, sans Qt)** — fichiers écrits dans cet ordre :
   `constants.py`, `logging_setup.py`, `model/exceptions.py`,
   `model/entities.py`, `model/app_config.py`, `model/plugin.py`,
   `model/pdf_index.py`, `model/fingerprint.py`, `model/log_parser.py`,
   `model/justification_repository.py`, `model/undo.py`,
   `model/entry_filter.py`, `model/project_store.py`, `model/ai_assistant.py`,
   `model/regex_tools.py`, `model/statistics.py`,
   `model/exporters/xlsx_writer.py`, `report_data.py`, `excel_exporter.py`,
   `docx_exporter.py`, `model/events.py`, `model/session.py`.
   * Le générateur XML d'une feuille Excel (`_sheet_xml`) a été réécrit
     aussitôt après sa première version, jugée confuse et incorrecte (voir
     [problèmes](#problèmes-rencontrés-et-traitements)).
   * Une fonction inutile et un test d'appartenance quadratique ont été retirés
     de l'export Word.
4. **Données d'exemple** — `config/app_config.ini` (5 catégories),
   `plugins/tintin.ini`, `plugins/tintin_pdf_index.ini`, logs des concepteurs A
   et B (`samples/`), fichiers sources factices pour « Aller à la ligne ».
5. **Premier test de bout en bout du Modèle** — extraction de 8 éléments,
   classement, annulation/rétablissement, projet, export des justifications,
   exports Excel et Word, import chez le concepteur B, génération de prompt,
   génération de regex : tout fonctionnait ; seule la documentation PDF manquait
   (normal à ce stade). Le classeur Excel a été validé comme XML bien formé.
6. **Couche Vue (PyQt5)** — `view_models.py` (DTO), `model/source_files.py`,
   `view/style_loader.py`, `view/entry_table_model.py`, widgets
   (`filter_bar`, `category_panel`, `details_panel`), dialogues
   (`justification_dialog`, `ai_help_dialog`, `source_viewer_dialog`,
   `pdf_viewer_dialog`, `regex_highlighter`, `plugin_editor_dialog`),
   `view/main_window.py`, `resources/styles/main.qss`.
7. **Présentateurs** — `model/preferences.py`, `presenter/error_handling.py`
   (décorateur `@guarded`), `presenter/ai_assistant_presenter.py`,
   `presenter/plugin_editor_presenter.py`, `presenter/main_presenter.py`,
   puis `main.py`. Les constantes de réponse « enregistrer / ignorer / annuler »
   ont été centralisées dans `view_models.py`.
8. **Test de l'interface hors écran** — scénario complet piloté par les signaux :
   ouverture, sélection, classement, Ctrl+Z / Ctrl+Y, filtres, retrait de
   justification, visionneuse source, aide IA (analyse de réponse puis
   justification), enregistrement, exports, éditeur de plugin avec génération
   automatique, import des justifications chez B : tout conforme.
9. **PDF d'exemple** `plugins/tintin_manual.pdf` (5 pages) généré avec un outil
   externe au projet. La visionneuse intégrée n'a pas pu être testée dans
   l'environnement (absence d'OpenGL).
10. **Tests unitaires** — `tests/helpers.py`, `test_parsing.py`,
    `test_session.py`, `test_tools.py` : **27 tests, tous réussis**.
11. **Qualité** — `pyflakes` et `pycodestyle` (99 caractères, `setup.cfg`) :
    8 écarts corrigés (lignes trop longues, ligne vide finale). Export Excel
    ouvert avec succès dans LibreOffice.
12. **Revue visuelle** par captures d'écran de la fenêtre principale et de
    l'éditeur de plugin, suivie de trois améliorations : surlignage de la
    seule valeur extraite (et non de toute la correspondance), libellés
    Annuler/Rétablir courts dans la barre d'outils (détail en infobulle),
    colonnes Type/Code/Ligne ajustées à leur contenu.
13. **README**, `requirements.txt`, vérification de l'archive dans un dossier
    vierge (tests verts, lancement et arrêt propres, code de sortie 0), puis
    livraison de `log_waver.zip`.

### Réponse de l'assistant (texte intégral)

> J'ai construit l'outil LogWaver. Il est livré dans **log_waver.zip** : code complet, exemple TINTIN prêt à l'emploi et guide d'installation dans le README.
>
> **Installation et lancement**
> ```bash
> pip install -r requirements.txt
> python main.py --plugin plugins/tintin.ini --log samples/tintin_designer_a.log
> ```
>
> **Tests effectués**
> - Les 27 tests unitaires passent.
> - Tout le parcours a été joué sur l'interface réelle : filtrer, classer, Ctrl+Z / Ctrl+Y, retirer une justification, aide IA, aller à la ligne, enregistrer le projet, exports Excel, Word et fichier de justifications.
> - Le cas des deux concepteurs a été vérifié : B importe le fichier de justifications de A, et seuls ses warnings nouveaux restent « non justifiés ».
> - L'export Excel s'ouvre correctement dans LibreOffice.
> - Le code respecte la PEP 8, avec des lignes limitées à 99 caractères.
>
> **Non testé ici :** l'affichage du PDF dans la visionneuse intégrée. Mon environnement de test n'a pas d'OpenGL, ce dont PyQtWebEngine a besoin. Le calcul de la page est bien vérifié (ER900 ouvre la page 5). Si PyQtWebEngine n'est pas installé, le PDF s'ouvre avec l'application du système et la page à consulter est indiquée.
>
> **Choix techniques**
> - **Bibliothèques :** seules les quatre autorisées sont utilisées. Comme `openpyxl` n'en fait pas partie, l'export Excel est écrit uniquement avec la bibliothèque standard de Python.
> - **Architecture MVP :** la partie métier n'importe jamais Qt et se teste sans interface. Les vues ne font qu'émettre des signaux et afficher des données simples.
> - **Plugins au format INI :** les regex s'écrivent telles quelles, sans échapper les `\`, et le fichier se modifie facilement à la main. L'éditeur de plugin colore en direct ce que chaque regex extrait. Il peut aussi générer les regex : vous sélectionnez à la souris la valeur de chaque champ dans une ligne d'exemple, et chaque regex produite est vérifiée sur cette ligne.
> - **Retrouver les justifications :** chaque élément reçoit une empreinte calculée à partir de l'outil, du type, du code, de la description et du nom court du fichier. Le numéro de ligne et le dossier n'en font pas partie. Une justification survit donc aux modifications du code et à son transfert vers un autre concepteur. Ces critères se règlent dans `config/app_config.ini`.
> - **IA :** le prompt est affiché dans le terminal et dans une fenêtre. Il demande à l'IA une réponse structurée (explication, analyse, statut, justification), que l'outil sait relire. En attendant une IA branchée, vous pouvez coller la réponse à la main, puis justifier d'un clic, éventuellement pour tout le même code. Pour brancher votre IA, il suffit d'implémenter la classe `AiProvider` (exemple dans le README).
>
> **Trois points de comportement à connaître**
> - **Un message par ligne :** un élément doit tenir sur une seule ligne du log. Les messages répartis sur plusieurs lignes ne sont pas reconnus.
> - **Messages identiques :** deux messages identiques partagent la même justification. Justifier l'un justifie l'autre, et retirer la justification de l'un la retire aussi de l'autre.
> - **Pas d'icônes :** la barre d'outils affiche du texte uniquement. On pourra ajouter des icônes plus tard dans `resources/`.

---

<a id="échange-2"></a>
## Échange 2 — Mise sous gestion de configuration (22:00)

### Demande de l'utilisateur

> je veux que tu passe par claud code et que tu mettes le projet avec tout ce qui faut pour une gestion de conf

### Travail réalisé (résumé chronologique)

1. **État des lieux** — le projet était intact ; l'outil `gh` n'était pas
   authentifié ; la liste des dépôts GitHub du compte `DavidBoccara` ne
   contenait pas de dépôt LogWaver, et la session ne permet pas d'en créer.
   Décision : préparer tout le dépôt Git localement.
2. **Fichiers de gestion de configuration créés** : `.gitignore`,
   `.gitattributes`, `.editorconfig`, `requirements-dev.txt`, `CHANGELOG.md`,
   `docs/GESTION_DE_CONFIGURATION.md`, `CONTRIBUTING.md`,
   `.github/workflows/ci.yml`, `.github/PULL_REQUEST_TEMPLATE.md`,
   `.github/ISSUE_TEMPLATE/anomalie.md`, `.github/ISSUE_TEMPLATE/evolution.md`,
   `tests/test_version.py`, `tests/test_gui_smoke.py`.
3. **Vérification locale identique à la CI** — style, analyse statique,
   contrôle « le modèle n'importe pas PyQt5 », **30 tests réussis**.
4. **README** complété (badge CI, arborescence, section « Gestion de
   configuration »).
5. **Historique Git** — dépôt initialisé sur `main`, deux commits
   (`feat: LogWaver 1.0.0…` puis `build: mise en place de la gestion de
   configuration`), étiquette annotée `v1.0.0`, branche `develop`.
6. **Livraison** de `LogWaver-depot-git.zip` (dépôt avec son historique).

### Réponse de l'assistant (texte intégral)

> J'ai préparé le dépôt Git complet, mais il n'est pas encore sur GitHub. Aucun dépôt LogWaver n'existe sur votre compte, et je ne peux pas en créer un d'ici : je peux seulement me rattacher à un dépôt existant pour y pousser.
>
> **Pour que je le pousse :** créez sur GitHub un dépôt vide nommé `LogWaver`, de préférence privé, sans README ni .gitignore ni licence. Prévenez-moi ensuite et je pousse `main`, `develop` et l'étiquette `v1.0.0`. Vous pouvez aussi le pousser vous-même depuis **LogWaver-depot-git.zip**, qui contient tout l'historique :
> ```bash
> git remote add origin https://github.com/DavidBoccara/LogWaver.git
> git push -u origin main develop --tags
> ```
>
> **Contenu ajouté pour la gestion de configuration**
> - **Plan de gestion de configuration** (`docs/GESTION_DE_CONFIGURATION.md`) : il couvre les points suivants.
>   - La liste des éléments à suivre en version (code, style, configuration, plugins, exemples, tests, documentation).
>   - Les règles de version au format MAJEUR.MINEUR.CORRECTIF.
>   - Les branches `main`, `develop`, `feature/*`, `fix/*` et `hotfix/*`.
>   - La règle d'écriture des messages de commit.
>   - La façon de faire évoluer le code.
>   - La procédure de publication d'une version, étape par étape.
>
>   Il précise aussi qu'un changement du calcul de l'empreinte des justifications casse la compatibilité et impose une nouvelle version majeure.
> - **CHANGELOG.md** : le journal des versions, avec la version 1.0.0. Un nouveau test échoue si la version du code et celle du journal ne concordent pas.
> - **CONTRIBUTING.md** : l'installation du poste, le déroulé d'une modification et les règles de code.
> - **Vérification automatique sur GitHub (`ci.yml`)** : à chaque push ou pull request, elle contrôle le style PEP 8 et lance une analyse statique. Elle vérifie aussi que la partie métier n'importe jamais PyQt5, puis exécute les tests sous Linux et Windows, avec Python 3.8, 3.10 et 3.12. Quand une étiquette `vX.Y.Z` est posée, elle publie la version sur GitHub avec son archive et ses notes tirées du CHANGELOG.
> - **Modèles GitHub** : un pour signaler une anomalie, un pour proposer une évolution, et un modèle de pull request qui oblige à dire si la modification touche les formats `.lwp` et `.lwj`, l'empreinte ou les dépendances.
> - **Fichiers de réglage Git** : `.gitignore` (les `.lwp`, `.lwj` et exports sont des fichiers de travail, pas du code), `.gitattributes` (fins de ligne, PDF traité comme binaire), `.editorconfig` et `requirements-dev.txt`.
> - **Un test de l'interface** qui tourne sans écran, pour que la vérification automatique contrôle aussi la fenêtre.
>
> L'historique contient deux commits : l'application, puis la gestion de configuration. Les 30 tests et tous les contrôles de la vérification automatique passent en local. Le fichier GitHub qui la décrit n'a pas encore tourné sur GitHub : on le verra au premier push.
>
> Une fois le dépôt en ligne, activez la protection des branches `main` et `develop` (section 9 du plan). Elle exige une pull request et une vérification réussie avant toute fusion.

---

<a id="échange-3"></a>
## Échange 3 — Publication sur le dépôt GitHub (22:05)

### Demande de l'utilisateur

> tu peux trouver le depo LogWaver

### Travail réalisé (résumé chronologique)

1. Dépôt `DavidBoccara/LogWaver` trouvé (créé par l'utilisateur, **public**),
   rattaché à la session avec droit d'écriture, puis cloné : il était vide.
2. Push de `main` et `develop` : **réussi** (commit `a5df6b0`).
3. Push de l'étiquette `v1.0.0` : **échec** à deux reprises (connexion coupée
   par la session) ; pas de nouvelle tentative.
4. Copie de travail de la session synchronisée sur `main`.

### Réponse de l'assistant (texte intégral)

> J'ai trouvé le dépôt **DavidBoccara/LogWaver** et j'y ai poussé le projet : les branches `main` et `develop` sont en ligne, avec les deux commits (l'application, puis la gestion de configuration).
>
> **Le dépôt est public.** Tout le monde peut voir le code. Si vous le préférez privé, changez-le dans *Settings > General > Danger Zone > Change visibility*.
>
> **L'étiquette `v1.0.0` n'a pas pu être poussée.** L'envoi a été coupé deux fois par la connexion de cette session, alors que les branches sont passées sans problème. Je n'ai pas insisté. Pour la publier, deux possibilités :
> - en ligne de commande, depuis votre copie du dépôt : `git fetch && git tag -a v1.0.0 origin/main -m "LogWaver 1.0.0" && git push origin v1.0.0` ;
> - ou sur GitHub, dans *Releases > Draft a new release*, en saisissant `v1.0.0` comme nouvelle étiquette sur `main`.
>
> La ligne de commande déclenche la publication automatique prévue dans la CI. Une release créée depuis l'interface GitHub ne la déclenche pas.
>
> **Je n'ai pas pu vérifier la CI.** Le push sur `main` et `develop` a dû lancer le premier passage, mais je n'ai pas accès à l'API GitHub depuis ici. Le résultat est dans l'onglet *Actions* du dépôt. Si un passage échoue, envoyez-moi le message d'erreur et je corrige.
>
> Il reste un réglage à faire vous-même : protéger `main` et `develop` (section 9 du plan de gestion de configuration). Ces deux branches ne pourront alors être modifiées que par une pull request dont la CI est verte.
>
> Le dépôt est maintenant rattaché à cette session : je peux y travailler directement, par exemple ouvrir une branche `feature/*` pour une prochaine évolution.

---

<a id="échange-4"></a>
## Échange 4 — Traçabilité de la conception (22:08)

### Demande de l'utilisateur

> aussi je veux que tu mette dans un fichier sous le git l'intégralité de cette discussion je veux un suivi complet de la conception de l'outil

### Travail réalisé

Rédaction du présent document `docs/conception/HISTORIQUE_CONCEPTION.md`,
ajout d'une entrée dans la rubrique « Non publié » du `CHANGELOG.md` et d'un
lien dans le `README.md`, sur la branche `docs/historique-conception` issue de
`develop`, conformément au plan de gestion de configuration (fusion vers
`develop` par pull request).

---

<a id="échange-5"></a>
## Échange 5 — Simplification, didacticiel et regroupement (21/11, 00:05)

### Demande de l'utilisateur

> C'est parfait mais j'aimerais que l'outil soient plus simple, j'aimerais qu'il soit le plus facile possible à prendre en main, tu peux aussi ajouter un didacticiel. Enfin j'aimerais qu'on puisse ranger les warning par code par exemple enfaîte qu'on puisse collapser un ensemble d'élément par texte redondant ça veux dire que si l'utilisateur veux collapser tous les élément par nom de fichier alors il peux ce qui permet quand on sélectionne le fichier de justifier automatiquement tous les warning relié au fichier en question, cette exemple peut être fait pas fichier ou par code ou par n'importe quelle élément choisi

### Travail réalisé (résumé chronologique)

1. **État du dépôt** : la pull request de l'historique n'étant pas encore
   fusionnée, la branche `feature/prise-en-main-regroupement` a été créée à
   partir de `docs/historique-conception` (afin de pouvoir compléter ce
   document).
2. **Regroupement (modèle)** — `model/grouping.py` : critères Code, Fichier
   (chemin / nom seul), Description identique, Type, Catégorie, Auteur, Log,
   plus tout champ propre au plugin ; groupes triés du plus grand au plus petit.
3. **Détection automatique du plugin** — `model/plugin_detector.py` : chaque
   plugin du dossier `plugins/` est essayé sur les premières lignes du log, le
   plus efficace est retenu ; les `.ini` qui ne sont pas des plugins (index PDF)
   sont ignorés.
4. **Didacticiel (modèle)** — `model/tutorial.py` (lecture INI, progression) et
   contenu `resources/tutorial/didacticiel.ini` (16 étapes).
5. **Vues** : la table plate est remplacée par une arborescence
   (`view/entry_tree_model.py`, `view/widgets/entry_tree.py`) où sélectionner un
   groupe sélectionne tous ses éléments ; nouvelle barre de filtres
   (recherche + « Regrouper par » + « Plus de filtres ») ; page d'accueil
   (`welcome_page.py`) ; panneau du didacticiel (`tutorial_panel.py`) ; fenêtre
   « Justifier » à boutons radio décrits ; panneau de droite réordonné ;
   fenêtre principale réécrite (accueil / espace de travail, bandeau « À faire »,
   barre d'outils réduite avec icônes, menus reformulés).
6. **Présentateurs** : `presenter/tutorial_presenter.py` ; dans
   `main_presenter.py` : regroupement, détection du plugin, exemple fourni,
   bandeau « À faire », libellé de sélection (« Code « CL245 » : 3 éléments »),
   proposition du didacticiel au premier lancement, actions « Montre-moi ».
7. **Configuration** : catégorie proposée par défaut (`[statuses] default`).
8. **Vérifications** :
   * pilotage complet de l'interface hors écran : accueil, détection de TINTIN
     sans plugin choisi, regroupement par code puis par fichier, justification
     d'un groupe entier, annulation, didacticiel parcouru de bout en bout avec
     toutes ses actions (cibles mises en évidence vérifiées à chaque étape) ;
   * revue visuelle par captures (accueil, vue groupée, didacticiel, fenêtre
     « Justifier ») suivie de deux retouches : cadres de détail masqués sans
     sélection, largeur minimale du panneau des catégories ;
   * 13 nouveaux tests (`tests/test_ease_of_use.py`, 2 tests d'IHM) :
     **43 tests réussis**, style PEP 8, analyse statique et contrôle MVP verts.
9. **Documentation** : README (prise en main, regroupement, partage,
   arborescence), CHANGELOG (rubrique « Non publié »), plan de gestion de
   configuration (nouvel élément de configuration : le didacticiel), présent
   historique.

### Réponse de l'assistant (texte intégral)

> J'ai fait les trois évolutions : un outil plus simple à prendre en main, un didacticiel et le regroupement des éléments. Elles sont poussées sur une nouvelle branche `feature/prise-en-main-regroupement`, pas encore dans `develop`.
>
> **Ranger et replier par texte redondant**
> - Le menu **« Regrouper par »**, au-dessus de la liste, propose : code, fichier (chemin complet ou nom seul), description identique, type, catégorie, auteur ou fichier de log.
> - Tout autre champ défini dans le plugin est ajouté automatiquement à ce menu : on peut donc regrouper par n'importe quel élément.
> - Chaque groupe est replié et affiche son nombre d'éléments, dont ceux encore à justifier.
> - **Sélectionner la ligne d'un groupe sélectionne tous ses éléments.** Un clic sur « ✔ Justifier » les justifie tous d'un coup. Par exemple, avec un regroupement par fichier, sélectionner `src/core/engine.c` justifie ses 3 warnings ensemble.
>
> **Plus simple à prendre en main**
> - Une **page d'accueil en 3 étapes** remplace la fenêtre vide, avec un bouton « Essayer avec l'exemple fourni ».
> - **Plus besoin de choisir un plugin** : à l'ouverture d'un log, l'outil qui l'a produit est reconnu automatiquement.
> - Un **bandeau jaune « À faire »** indique toujours la prochaine action et combien d'éléments restent à justifier.
> - La **fenêtre « Justifier »** présente les catégories en boutons à cocher, chacune avec son explication. Elle rappelle ce qui va être justifié et propose « Justifié / Accepté » par défaut.
> - La **barre d'outils** est réduite à 7 boutons avec icônes. Les filtres avancés sont rangés sous « Plus de filtres ». Les menus parlent plus simplement, par exemple « Partager mes justifications ».
>
> **Didacticiel**
> - Il compte 16 étapes et est proposé au premier lancement. On peut le relancer à tout moment avec le bouton « Didacticiel » ou Maj+F1.
> - Il s'affiche dans un panneau à droite et encadre en orange l'élément de l'écran dont il parle.
> - Un bouton **« Montre-moi »** fait l'action à la place de l'utilisateur : ouvrir l'exemple, regrouper par code, sélectionner un groupe, le justifier, annuler…
> - Son texte se modifie à la main dans `resources/tutorial/didacticiel.ini`, sans toucher au code.
>
> **Vérifications**
> - 43 tests passent, dont 13 nouveaux. Les contrôles de style, l'analyse statique et la vérification de l'architecture passent aussi.
> - J'ai joué tout le parcours dans l'interface : reconnaissance du plugin sans choix manuel, regroupement par code puis par fichier, justification d'un groupe entier, annulation, puis le didacticiel du début à la fin.
> - J'ai vérifié l'écran d'accueil, la vue groupée, le didacticiel et la fenêtre « Justifier » sur des captures, ce qui m'a fait corriger deux détails d'affichage.
> - Un test a révélé un vrai défaut, que j'ai corrigé : cliquer sur « Montre-moi » à une étape sans action provoquait une erreur.
>
> **Limite à connaître :** une session ne travaille qu'avec un seul plugin. Si l'on ouvre dans la même session un log d'un autre outil, le plugin change et les logs déjà ouverts sont relus avec ce nouveau plugin.
>
> L'historique de conception est complété avec cet échange : votre demande mot pour mot, le travail fait et 8 nouvelles décisions de conception. Le texte intégral de cette réponse y sera ajouté à la prochaine mise à jour, puisqu'il ne pouvait pas être enregistré avant d'être écrit.
>
> **À faire de votre côté :** la branche part de celle de l'historique, qui n'est pas encore fusionnée. Une seule pull request vers `develop` suffit donc pour verser les deux : https://github.com/DavidBoccara/LogWaver/compare/develop...feature/prise-en-main-regroupement

---

<a id="échange-6"></a>
## Échange 6 — Publication de la version 1.1.0 (21/11, 10:27)

### Demande de l'utilisateur

> je ne trouve pas la bonne version sous git

### Diagnostic

La page d'accueil du dépôt GitHub affiche la branche `main`, restée en 1.0.0 :
les évolutions de l'échange 5 n'existaient que sur la branche
`feature/prise-en-main-regroupement`, aucune pull request n'ayant été fusionnée.

### Choix de l'utilisateur

À la question « Que voulez-vous que je fasse ? » (publier en 1.1.0, fusionner
dans `develop` seulement, ou simplement expliquer), l'utilisateur a choisi :
**« Publier en 1.1.0 »**.

### Travail réalisé

Application de la procédure de livraison du plan de gestion de configuration :

1. `develop` avancée jusqu'à la branche d'évolution (avance rapide, sans
   conflit) : elle contient l'historique de conception et l'évolution 1.1.0.
2. Commit de version sur `develop` : `__version__ = "1.1.0"`, rubrique
   « Non publié » du CHANGELOG renommée en `[1.1.0] - 2026-11-21`, liens de
   comparaison mis à jour, réponse intégrale de l'échange 5 et présent échange
   ajoutés à l'historique ; tests et contrôles de la CI rejoués.
3. Fusion de `develop` dans `main` (commit de fusion `--no-ff`, ligne de base
   livrée) puis report de `main` dans `develop`.
4. Étiquette annotée `v1.1.0` posée sur `main`.

### Réponse de l'assistant (texte intégral)

> La version 1.1.0 est maintenant sur `main`. Vous la voyez directement sur la page d'accueil du dépôt : https://github.com/DavidBoccara/LogWaver
>
> **Pourquoi vous ne la trouviez pas :** GitHub affiche la branche `main` par défaut, et elle était restée en 1.0.0. Les nouveautés (regroupement, didacticiel, prise en main simplifiée) n'étaient que sur la branche `feature/prise-en-main-regroupement`, en attente d'une pull request que personne n'avait fusionnée.
>
> **Ce que j'ai fait, selon la procédure de livraison du plan :**
> - `develop` contient maintenant l'historique de conception et les nouveautés.
> - J'ai ajouté un commit de version : la version passe à 1.1.0 et le CHANGELOG a une entrée `[1.1.0] - 2026-11-21`.
> - J'ai fusionné `develop` dans `main` avec un commit de fusion, qui marque la version livrée. `main` et `develop` sont identiques.
> - Les 43 tests et tous les contrôles de la CI passent sur cette version.
> - L'historique de conception contient maintenant ma réponse précédente en entier, ainsi que cet échange (votre question, le diagnostic et votre choix).
>
> **Ce qui n'a pas marché : l'étiquette `v1.1.0` n'est pas sur GitHub.** La connexion de cette session refuse les envois d'étiquettes, comme pour la 1.0.0. Pour poser les deux étiquettes, depuis votre copie du dépôt :
> ```bash
> git fetch origin
> git tag -a v1.0.0 a5df6b0 -m "LogWaver 1.0.0"
> git tag -a v1.1.0 origin/main -m "LogWaver 1.1.0"
> git push origin v1.0.0 v1.1.0
> ```
> Cet envoi déclenche la CI. Une fois ses vérifications passées, elle crée automatiquement les deux versions dans l'onglet *Releases*, avec leurs archives.
>
> Les branches `docs/historique-conception` et `feature/prise-en-main-regroupement` ne servent plus, puisque leur contenu est dans `main`. Vous pouvez les supprimer depuis l'onglet *Branches* de GitHub.

---

<a id="échange-7"></a>
## Échange 7 — Où trouver la nouvelle version ? (21/11, 10:31)

### Demande de l'utilisateur

> une fois fait je ne trouve pas les nouveaux ajouts

### Travail réalisé

1. Vérification de GitHub : `main` en 1.1.0 avec tous les nouveaux fichiers ;
   étiquettes `v1.0.0` et `v1.1.0` bien poussées par l'utilisateur.
2. Consultation des pages publiques *Releases* et *Actions* : aucune version
   publiée, aucune exécution de la CI.
3. Diagnostic : copie locale ancienne probable, et GitHub Actions
   vraisemblablement désactivé (d'où l'absence de version publiée).

### Réponse de l'assistant (texte intégral)

> J'ai vérifié : tout est bien sur GitHub. `main` est en version 1.1.0 et contient tous les nouveaux fichiers (regroupement, didacticiel, page d'accueil). Vos étiquettes `v1.0.0` et `v1.1.0` sont aussi arrivées. Le problème vient donc d'ailleurs, et je vois deux causes possibles.
>
> **1. Vous lancez une ancienne copie de l'outil.** C'est le plus probable si vous ne voyez pas les nouveautés dans l'application. Votre dossier local date sans doute d'avant la mise à jour, par exemple celui du zip `log_waver.zip` de la première version. Pour récupérer la 1.1.0 :
> - si vous avez cloné le dépôt, placez-vous dans son dossier et tapez `git checkout main` puis `git pull` ;
> - sinon, téléchargez à nouveau le projet sur https://github.com/DavidBoccara/LogWaver avec le bouton vert *Code > Download ZIP*, puis lancez `python main.py` depuis ce **nouveau** dossier.
>
> Vous saurez que c'est la bonne version si :
> - au lancement sans argument, une page d'accueil « Bienvenue dans LogWaver » s'affiche ;
> - la barre d'outils contient un bouton **Didacticiel** ;
> - au-dessus de la liste, il y a un menu **« Regrouper par : »** ;
> - le menu *Aide > À propos* indique **1.1.0**.
>
> **2. Vous cherchez dans l'onglet *Releases*.** Il est vide, et l'onglet *Actions* n'affiche aucune exécution. La vérification automatique (CI) n'a donc jamais tourné, ni lors de mes envois ni lors de votre envoi d'étiquettes. Or c'est elle qui crée les versions dans *Releases*. La cause la plus courante : GitHub Actions est désactivé sur le dépôt.
>
> Pour corriger :
> 1. Allez dans *Settings > Actions > General* et cochez **« Allow all actions and reusable workflows »**.
> 2. Relancez la publication en renvoyant l'étiquette :
> ```bash
> git push origin :refs/tags/v1.1.0
> git push origin v1.1.0
> ```
> Sinon, créez la version à la main dans *Releases > Draft a new release* en choisissant l'étiquette `v1.1.0`.
>
> Si ce n'est ni l'un ni l'autre, dites-moi où vous regardez (l'application lancée sur votre poste ou une page GitHub) et ce qui s'affiche : je chercherai la cause précise.

---

<a id="échange-8"></a>
## Échange 8 — Plugins par extension, assistant regex, priorités et correspondance (22/11, 12:08)

### Demande de l'utilisateur

> J'aimerais que tu puisse renseigner dans l'outil l'extension du fichier par exemple si c'est un .log ou .mx comme ça l'outil connais automatiquement quelle plugin utiliser. aussi j'aimerais que l'outil de création de plugin soit plus puissant, deja qu'il puisse cree un plugin de zero même si des plugin sont deja renseigné, ensuit pour la regex l'idée est de proposer a l'utilisateur de dans un premier temps, choisir le type voulu comme "warning" par exemple, ensuit il sélectionne la ligne ou l'intégralité du warning apparait. puis l'outil propose de sélectionner les élément comme le chemin du fichier, le code etc etc . chaque élément renseigné doivent pouvoir bouger complètement donc la regex doit se baser uniquement sur ce qui n'est pas renseigné qu'on considérera comme invariant, l'outil doit pouvoir proposer de sélectionner les éléments qui peuvent varier mais qui n'intéresse pas. enfin j'aimerais qu'il y ai des niveau de priorité par exemple si on renseigne un nouveau fichier projet ou une meme ligne est indiqué en "rejeté" alors ça puisse prendre le dessus sur le "justifié" déjà présent. aussi j'aimerais que l'outil puisse nous permettre de sélectionner ce qui sera comparé pour retrouver une justification déjà présente, ça veux dire que on peux permettre a l'outil de associer une justification deja presente a un warning du nouveau log qui n'est pas exactement pareille mais pour ça il faut pouvoir montrer ce qui peux changer n'hesitpas a rendre cette option le plus facilement compreensible.

### Travail réalisé (résumé chronologique)

1. Branche `feature/plugins-correspondance-priorites` créée depuis `develop`
   (identique à `main`, 1.1.0).
2. **Priorités** : attribut `priority` des catégories (configuration d'exemple :
   Rejeté 50, En cours d'analyse 40, À traiter 30, Justifié 20, Clôturé 10).
3. **Refonte de la correspondance** :
   * `MatchingOptions` enrichi des tolérances sur la description (nombres, texte
     entre guillemets, noms de fichiers/chemins) ;
   * `FingerprintBuilder` réécrit : contexte brut complet mémorisé avec chaque
     justification, empreinte recalculable selon n'importe quelles règles,
     identifiant strict indépendant des règles ;
   * nouvel `JustificationIndex` : pour chaque clé, la justification retenue est
     la plus prioritaire puis la plus récente ;
   * session : justifier/retirer agissent sur toutes les justifications de la
     clé ; import résolu par priorité (ajoutées / remplacées / écartées) ;
     `set_matching_options` et `preview_matching` (éléments gagnés / perdus) ;
   * fichiers projet et justifications en **format v2** (règles enregistrées),
     lecture des fichiers v1 conservée et testée.
4. **Extensions** : `file_extensions` dans les plugins ; détection par
   extension puis par contenu ; choix manuel proposé en dernier recours avec
   **mémorisation de l'extension** dans le plugin (modification de la seule
   ligne concernée, commentaires préservés).
   * Un test a révélé qu'une extension courante (`.log`) déclarée par un plugin
     qui ne reconnaît rien pouvait masquer le bon plugin : règle affinée
     (le contenu l'emporte alors, l'extension restant décisive si rien ne
     reconnaît le contenu).
5. **Générateur de regex réécrit** : texte non sélectionné = invariant exact
   (seuls les espaces sont tolérés) ; éléments sélectionnés = `.+?` (valeur
   libre) ; parties variables sans intérêt marquées explicitement ; détection
   automatique des dates/nombres ; refus explicite de deux sélections collées ;
   application à tout l'exemple.
6. **Assistant regex pas à pas** (`RegexWizardDialog` + `RegexWizardPresenter`) :
   type → ligne → éléments (avec modèle de ligne lisible) → vérification.
7. **Éditeur de plugin** : bouton « Nouveau plugin », champ « Extensions des
   logs » (prérempli depuis le log d'exemple), assistant à la place de l'ancien
   marquage, enregistrement proposé dans `plugins/`. Menus « Outils > Créer un
   nouveau plugin » et « Modifier le plugin actuel ».
8. **Règles de correspondance** (`MatchingRulesDialog` + présentateur, menu
   Édition, Ctrl+M) : préréglages, critères illustrés par l'élément
   sélectionné, tolérances, « ce qui sera comparé », aperçu avant → après et
   listes des éléments gagnés / perdus.
9. Didacticiel : étape « Règles de correspondance » (17 étapes).
10. **Vérifications** : 21 nouveaux tests (priorités, correspondance, format v1,
    extensions, générateur, assistant et dialogue pilotés), **64 tests
    réussis** ; parcours complet dans la fenêtre principale (détection par
    contenu d'un `.xyz`, choix manuel et mémorisation de `.mx`) ; revue visuelle
    de l'assistant, du dialogue des règles et de l'éditeur, suivie de trois
    retouches (explications tronquées, liste sans retour à la ligne, colonnes
    « Ligne » ambiguës).
11. Documentation (README, CHANGELOG 1.2.0), version 1.2.0, livraison sur
    `develop` puis `main`.

### Réponse de l'assistant

Le texte intégral de la réponse sera ajouté lors de la prochaine mise à jour
de l'historique.

---

## Registre des décisions de conception

| N° | Décision | Raison | Alternatives écartées |
|---|---|---|---|
| D1 | Architecture **MVP « Passive View »** ; le paquet `model` n'importe jamais Qt | Logique métier testable sans interface ; séparation totale exigée | MVC avec contrôleurs Qt (couplage plus fort) |
| D2 | Vues pilotées par **signaux** et alimentées par des **DTO immuables** (`view_models.py`) | Les vues n'ont aucune connaissance du modèle | Accès direct des vues aux entités |
| D3 | Modèle **observable** (`EventHub`) | Rafraîchissement de l'IHM sans dépendance du modèle vers la vue | Signaux Qt dans le modèle (dépendance à Qt) |
| D4 | Plugins au format **INI** sans interpolation, clés sensibles à la casse | Lisible et modifiable à la main ; regex écrites sans échappement | JSON (doublement des `\`), YAML (bibliothèque tierce interdite) |
| D5 | Une regex de **détection** par type + une regex **par champ** ; valeur = groupe `value`, sinon groupe 1, sinon correspondance complète | Respecte la structure demandée (une regex par champ) tout en restant souple | Une regex unique à groupes nommés |
| D6 | Justification rattachée à une **empreinte** (outil, type, code, description, nom court du fichier) et non à une ligne de log | Survie aux modifications du code ; héritage concepteur A → B | Correspondance par numéro de ligne (fragile) |
| D7 | Clés d'empreinte **configurables** (`[matching]`) avec avertissement d'incompatibilité à l'import | Adapter la rigueur d'appariement à chaque projet | Clés figées |
| D8 | Catégorie implicite **« Non justifiés (sans classe) »**, distincte de « À traiter » | Le retrait d'une justification renvoie l'élément « sans classe », comme demandé | Assimiler « non classé » à « À traiter » |
| D9 | Une seule commande d'annulation **`ChangeJustificationsCommand`** (état avant/après) et pile d'annulation propre au modèle | Ctrl+Z fiable pour classer, retirer, classer en masse, importer ; sans `QUndoStack` (Qt) dans le modèle | Une commande par action |
| D10 | Deux fichiers : **projet `.lwp`** (tout le travail) et **justifications `.lwj`** (à transmettre) ; JSON, écriture atomique, chemins relatifs, version de format | Répond à « fichier projet » et « fichier automatique de justification » | Un seul fichier |
| D11 | Export Excel écrit **avec la seule bibliothèque standard** (Office Open XML) | `openpyxl` interdit par les contraintes | Export CSV (pas un vrai fichier Excel) |
| D12 | Export **Word** supplémentaire via python-docx | Bibliothèque autorisée ; rapport lisible pour une revue | — |
| D13 | **numpy** pour le tableau croisé types × catégories | Bibliothèque imposée ; calcul matriciel naturel | Comptage par dictionnaires |
| D14 | IA derrière une interface **`AiProvider`** ; implémentation par défaut qui **affiche le prompt dans le terminal** | L'utilisateur branchera son IA plus tard | Appel direct à une API |
| D15 | Prompt imposant une **réponse structurée** (EXPLICATION / ANALYSE / STATUT / JUSTIFICATION) et analyseur tolérant (Markdown, repli sur le texte entier) | Permet le bouton « Justifier avec la proposition de l'IA » | Réponse libre non exploitable |
| D16 | Documentation PDF via **PyQtWebEngine** à `#page=N`, index code → page dans un INI séparé ; repli sur l'application système | Exigence de la page exacte ; robustesse si WebEngine absent | Lecteur PDF tiers |
| D17 | « Aller à la ligne » : **visionneuse intégrée** avec numéros de ligne et surlignage, éditeur externe optionnel configurable (`{file}`, `{line}`) | Fonctionne partout sans configuration | Éditeur externe obligatoire |
| D18 | **Générateur de regex** à partir de sélections à la souris, avec vérification sur la ligne d'exemple | Exigence « concevoir la regex de manière automatique » | Saisie manuelle uniquement |
| D19 | Nom d'utilisateur demandé **à la première justification**, mémorisé dans le projet et dans `~/.logwaver/preferences.json` | Exigence « on renseigne le nom une seule fois » | Saisie à chaque justification |
| D20 | Gestion d'erreurs par **exceptions métier typées** et décorateur **`@guarded`** sur chaque action | Messages clairs, journalisation complète, application jamais interrompue | `try/except` dispersés |
| D21 | Style **entièrement en QSS** (objectName, propriétés dynamiques) ; seules les couleurs de catégorie, données de configuration, sont appliquées par le code | Séparation style / structure exigée | Styles en dur dans les widgets |
| D22 | Limite de ligne PEP 8 portée à **99 caractères** (`setup.cfg`) | Autorisée par la PEP 8 ; lisibilité des signatures typées | 79 caractères |
| D23 | Gestion de configuration : **SemVer**, Git Flow simplifié, Conventional Commits, CI GitHub Actions Linux/Windows, publication sur étiquette | Traçabilité et lignes de base livrées | — |
| D24 | Produits de travail utilisateurs (`.lwp`, `.lwj`, exports) **exclus** du dépôt | Ce sont des données des projets utilisateurs, pas des éléments de configuration de l'outil | Les versionner avec l'outil |
| D25 | **Arborescence** (`QTreeView` + `QStandardItemModel`) à la place de la table, à plat ou groupée selon le critère choisi | Permet de replier les éléments redondants tout en gardant une seule vue | Deux vues distinctes (table et arbre) |
| D26 | **Sélectionner un groupe = sélectionner tous ses éléments** ; la justification reste l'action habituelle (« ✔ Justifier ») | Un seul geste à apprendre, valable pour un élément comme pour un groupe | Bouton spécifique « Justifier le groupe » |
| D27 | Regroupement calculé dans le **modèle** (`EntryGrouper`), critères proposés selon les champs du plugin | Testable sans IHM ; « n'importe quel élément choisi » couvert automatiquement | Regroupement fait par la vue |
| D28 | **Détection automatique du plugin** par le nombre de lignes reconnues | Supprime l'étape la plus technique (choisir un plugin) | Association manuelle extension → plugin |
| D29 | Didacticiel **décrit dans un fichier INI** (texte, widget ciblé, action) et affiché dans un **panneau ancré** ; mise en évidence par propriété dynamique stylée en QSS | Contenu modifiable sans code ; respecte les interdictions de positionnement absolu et de style dans le code | Bulles superposées positionnées en absolu |
| D30 | Actions **« Montre-moi »** exécutées par le présentateur principal et référencées par nom | Le didacticiel montre le vrai fonctionnement, sur de vraies données | Captures ou animations figées |
| D31 | **Bandeau « À faire »** contextuel, page d'accueil en 3 étapes, barre d'outils réduite, filtres avancés repliés | Réduire la charge cognitive : l'utilisateur voit toujours l'action suivante | Documentation seule |
| D32 | Catégorie **proposée par défaut** configurable (`justified` dans l'exemple) | Cas le plus fréquent en un clic, sans figer d'identifiant dans le code | Première catégorie de la liste |
| D33 | Extensions déclarées **dans le plugin** (`file_extensions`) ; mémorisation par modification de la seule ligne concernée | Le plugin reste l'unique description d'un outil, lisible à la main ; commentaires préservés | Table extension → plugin dans les préférences (invisible et non partageable) |
| D34 | Extension prioritaire, **sauf** si ses plugins ne reconnaissent rien alors qu'un autre reconnaît le contenu | Une extension générique (`.log`) ne doit pas masquer le bon plugin | Extension toujours prioritaire |
| D35 | Regex fondées **uniquement sur le texte invariant** ; éléments en `.+?` ; parties variables marquées explicitement avec proposition automatique | Exigence : les éléments peuvent « bouger complètement » | Généralisation automatique du texte fixe (version 1.0), imprévisible pour l'utilisateur |
| D36 | Assistant en **QWizard** à 4 étapes, avec modèle de ligne `‹…›` et vérification sur tout l'exemple | Guidage pas à pas, résultat compréhensible avant validation | Formulaire unique |
| D37 | **Priorité** portée par la catégorie ; à l'import, la plus prioritaire l'emporte ; à égalité, l'existante est gardée | « Rejeté » doit primer sur « Justifié » ; ne jamais écraser son propre travail sans raison | Date la plus récente ; question systématique |
| D38 | Justification stockée avec son **contexte complet** et un identifiant strict ; correspondance calculée à la volée par un **index** | Règles modifiables à tout moment sans perte ni migration ; retour arrière exact | Recalcul et fusion des justifications (perte d'information) |
| D39 | Règles de correspondance **enregistrées dans le projet**, défaut issu de la configuration | Chaque projet garde son niveau de tolérance | Réglage global uniquement |
| D40 | Dialogue des règles avec **préréglages, exemple concret et aperçu gagnés/perdus** | Rendre l'option « le plus facilement compréhensible » : on voit l'effet avant de valider | Cases à cocher seules |
| D41 | Format de fichier **v2** avec lecture des v1 → version **MINEURE** 1.2.0 | Conforme au plan de gestion de configuration (compatibilité ascendante préservée) | Version majeure |

## Problèmes rencontrés et traitements

| Problème | Traitement |
|---|---|
| Première version du générateur XML d'une feuille Excel confuse et incorrecte (élément `<cols>` mal placé) | Réécriture complète en méthodes courtes et documentées ; validation XML puis ouverture dans LibreOffice |
| Code mort et test quadratique dans l'export Word | Supprimés |
| Rôles Qt écrits en nombres magiques (`3`) | Remplacés par `Qt.ToolTipRole` |
| Surlignage du testeur de regex couvrant toute la correspondance | Surlignage limité à la valeur extraite (fonction `value_group`) |
| Libellés Annuler/Rétablir trop longs dans la barre d'outils | Libellé court, détail en infobulle |
| Visionneuse PDF non testable dans l'environnement (pas d'OpenGL, exécution en root) | Calcul des pages testé unitairement ; repli système conservé ; conseil de dépannage dans le README |
| `gh` non authentifié, création de dépôt impossible depuis la session | Dépôt créé par l'utilisateur, puis rattaché et poussé |
| Push de l'étiquette `v1.0.0` coupé par la connexion de la session | Procédure manuelle fournie à l'utilisateur |
| Test d'IHM du didacticiel réussissant à tort (fenêtre non affichée pendant le test) | Test rendu strict (fenêtre affichée, progression vérifiée sur l'état du présentateur) |
| « Montre-moi » déclenché sur une étape sans action provoquait une erreur (révélé par le test strict) | Le présentateur ignore désormais ce cas |
| Cadres de détail vides affichés sans sélection ; catégories tronquées didacticiel ouvert | Cadres masqués sans sélection ; largeur minimale du panneau des catégories (QSS) |
| Plugin déclarant `.log` choisi d'office même sans rien reconnaître (révélé par un test) | Règle de détection affinée (D34) |
| Dialogue des règles : explications tronquées, texte des listes coupé ; assistant : deux colonnes « Ligne » | Zone défilante, exemple déplacé sous chaque critère, retour à la ligne, colonne « N° dans l'exemple » |

## Couverture des exigences

| Exigence du cahier des charges | Réalisation |
|---|---|
| Lire le log de n'importe quel outil, types d'éléments selon un plugin | `model/plugin.py`, `model/log_parser.py`, `plugins/tintin.ini` |
| Filtrer la vue | `view/widgets/filter_bar.py`, `model/entry_filter.py` |
| Sélection multiple et classement selon une liste issue d'un fichier de configuration | `config/app_config.ini`, `JustificationDialog` |
| Justification obligatoire, élément retiré de la liste et placé dans sa catégorie | `WaverSession.classify`, panneau des catégories |
| Sauvegarde à tout moment, Ctrl+Z, fichier projet | `model/undo.py`, `model/project_store.py` |
| Réappliquer les justifications à un nouveau log | `WaverSession.open_log` (empreintes) |
| Plugin lisible, éditeur avec testeur et génération automatique de regex | `PluginEditorDialog`, `model/regex_tools.py` |
| Prompts IA affichés dans le terminal, justification IA en un clic, pour tout un code | `model/ai_assistant.py`, `AiHelpDialog` |
| PDF ouvert à la page du code (plugin + fichier d'index) | `model/pdf_index.py`, `PdfViewerDialog` |
| Justification associée au nom de l'utilisateur, saisi une seule fois | `MainPresenter._ensure_user_name`, `UserPreferences` |
| Retrait d'une justification → retour en « non justifiés sans classe » | `WaverSession.unclassify` |
| Héritage des justifications du concepteur A par le concepteur B | Export / import `.lwj` |
| Aller directement à la ligne du fichier source | `SourceViewerDialog`, éditeur externe |
| Export Excel à tout moment | `model/exporters/` |
| Bibliothèques limitées à PyQt5, numpy, python-docx, PyQtWebEngine | Vérifié ; contrôle demandé dans les PR |
| MVP, POO, gestion d'erreurs, PEP 8, nommage, typage, docstrings | Vérifié par la CI (style, analyse statique, contrôle MVP) |
| Interface responsive par layouts, style séparé en QSS | Aucun positionnement absolu ; `resources/styles/main.qss` |
| Structure de fichiers, code complet, guide d'installation | `README.md` |
| Gestion de configuration | `docs/GESTION_DE_CONFIGURATION.md`, `CHANGELOG.md`, `.github/` |
| Outil le plus simple possible à prendre en main | Page d'accueil, détection du plugin, bandeau « À faire », barre d'outils réduite, fenêtre « Justifier » simplifiée |
| Didacticiel | `resources/tutorial/didacticiel.ini`, `TutorialPanel`, `TutorialPresenter` |
| Replier les éléments par texte redondant (code, fichier, tout champ) et justifier tout un groupe | `model/grouping.py`, `EntryTree`, « Regrouper par » |
| Renseigner l'extension (.log, .mx) pour choisir automatiquement le plugin | `file_extensions`, `PluginDetector`, `PluginExtensionRegistrar`, champ de l'éditeur |
| Créer un plugin de zéro même si des plugins existent | Outils > Créer un nouveau plugin, bouton « Nouveau plugin » |
| Regex : type → ligne → éléments → parties variables ignorées, fondée sur l'invariant | `RegexWizardDialog`, `RegexWizardPresenter`, `RegexGenerator` |
| Niveaux de priorité (« Rejeté » prime sur « Justifié ») | `priority`, `JustificationIndex`, `WaverSession.import_rules` |
| Choisir ce qui est comparé pour retrouver une justification, en montrant ce qui peut changer | `MatchingRulesDialog`, `MatchingRulesPresenter`, `matching_presets.py` |
