# LogWaver — suivi et justification des messages de logs

[![CI](https://github.com/DavidBoccara/LogWaver/actions/workflows/ci.yml/badge.svg)](https://github.com/DavidBoccara/LogWaver/actions/workflows/ci.yml)

LogWaver lit le fichier de log de **n'importe quel outil** grâce à des fichiers
*plugin*, extrait les notes / warnings / erreurs, et permet de les filtrer, de les
classer dans des catégories (À traiter, Justifié, Rejeté…) avec une justification
signée, puis de **réutiliser automatiquement ces justifications** sur de nouveaux
logs ou chez un autre concepteur.

---

## Documentation

| Document | Contenu |
|---|---|
| [`docs/LogWaver_Documentation_Code.pdf`](docs/LogWaver_Documentation_Code.pdf) | explication complète du code : architecture, flux, formats, qualité et référence de chaque module, classe et méthode (84 pages) |
| [`docs/LogWaver_Presentation.pptx`](docs/LogWaver_Presentation.pptx) | présentation de l'application et de ses fonctionnalités (12 planches) |
| [`docs/GESTION_DE_CONFIGURATION.md`](docs/GESTION_DE_CONFIGURATION.md) | plan de gestion de configuration |
| [`docs/conception/HISTORIQUE_CONCEPTION.md`](docs/conception/HISTORIQUE_CONCEPTION.md) | historique complet de la conception |

Ces documents se régénèrent avec les outils de [`tools/doc/`](tools/doc/README.md).

## 1. Installation

Prérequis : Python 3.8 ou plus récent.

```bash
cd log_waver
python -m venv .venv
# Windows : .venv\Scripts\activate      Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
```

Seules les bibliothèques imposées sont utilisées : **PyQt5, PyQtWebEngine, numpy,
python-docx**. L'export Excel est écrit sans bibliothèque tierce (format Office
Open XML généré par la bibliothèque standard).

## 2. Lancement

```bash
python main.py                                     # page d'accueil
python main.py --plugin plugins/tintin.ini --log samples/tintin_designer_a.log
python main.py --project mon_projet.lwp --log nouveau_build.log
python main.py --debug                             # journal détaillé
```

| Option | Rôle |
|---|---|
| `--config` | fichier de configuration (défaut : `config/app_config.ini`) |
| `--plugin` | plugin à imposer (sinon détection automatique) |
| `--log` | log à ouvrir (option répétable) |
| `--project` | projet à ouvrir |

Le journal de l'application est écrit dans la console et dans
`~/.logwaver/logwaver.log`.

Tests unitaires (bibliothèque standard uniquement) :

```bash
python -m unittest discover -s tests -t .
```

## 3. Prise en main

### 3.1 Le plus simple : le didacticiel

Au premier lancement, LogWaver propose un **didacticiel de 5 minutes** (16 étapes).
Il charge un exemple, encadre en orange l'élément de l'écran dont il parle, et
un bouton **« Montre-moi »** réalise l'action à votre place si vous le souhaitez.
Il reste disponible à tout moment : bouton **Didacticiel** ou **Maj+F1**.

Son contenu est dans `resources/tutorial/didacticiel.ini`, modifiable à la main
(titres, textes, widget à encadrer, action proposée).

### 3.2 Utilisation courante en 3 gestes

1. **Ouvrir un log** : l'outil qui l'a produit est **reconnu automatiquement**
   parmi les plugins du dossier `plugins/` (plus besoin de choisir un plugin).
2. **Justifier** : sélectionnez un élément — ou un **groupe entier** — puis
   **✔ Justifier** (ou double-clic). Cochez la catégorie, écrivez pourquoi,
   validez. Votre nom n'est demandé qu'une fois. Les éléments quittent la liste
   « Non justifiés » et rejoignent leur catégorie.
3. **Enregistrer** (Ctrl+S) puis **Exporter vers Excel** (Ctrl+E).

Le bandeau jaune au-dessus de la liste indique toujours **quoi faire ensuite**.
**Ctrl+Z / Ctrl+Y** annulent / rétablissent ; **Suppr** retire une justification.

### 3.3 Regrouper pour justifier en masse

Le menu **Regrouper par** rassemble les éléments qui ont la même valeur :

| Critère | Exemple d'usage |
|---|---|
| Code | justifier toutes les occurrences du warning CL245 |
| Fichier (chemin complet ou nom seul) | justifier tous les warnings d'un fichier tiers |
| Description (texte identique) | traiter un message répété mot pour mot |
| Type d'élément, catégorie, auteur, log | revue, contrôle, répartition du travail |
| Tout autre champ extrait par le plugin | ajouté automatiquement à la liste |

Chaque groupe est replié et affiche son nombre d'éléments (dont non justifiés).
**Sélectionner la ligne d'un groupe sélectionne tous ses éléments** : un clic sur
« ✔ Justifier » les justifie tous ensemble. « Tout déplier / Tout replier » et
le menu du clic droit permettent d'explorer les groupes.

### 3.4 Partager avec un collègue

Concepteur A : **Fichier > Partager mes justifications…** (fichier `.lwj`).
Concepteur B : **Fichier > Récupérer les justifications d'un collègue…** : seuls
les éléments vraiment nouveaux restent à traiter. Essai avec l'exemple :
`samples/tintin_designer_a.log` puis `samples/tintin_designer_b.log`.
L'import accepte aussi un **fichier projet** (`.lwp`) complet.

**Priorités.** Si une justification importée et une justification existante
portent sur le même élément, la catégorie de **priorité la plus élevée
l'emporte** : un élément « Rejeté » chez un collègue remplace votre « Justifié ».
À priorité égale, votre justification est conservée. Les priorités se règlent
dans `config/app_config.ini` (`priority` de chaque catégorie, visible en
infobulle sur les catégories) ; le bilan de l'import détaille les justifications
ajoutées, remplacées et écartées, et Ctrl+Z annule l'import.

| Catégorie | Priorité (exemple fourni) |
|---|---|
| Rejeté | 50 |
| En cours d'analyse | 40 |
| À traiter | 30 |
| Justifié / Accepté | 20 |
| Clôturé | 10 |

### 3.5 Retrouver une justification malgré les différences

**Édition > Règles de correspondance** (Ctrl+M) indique ce qui doit être
identique pour qu'une justification existante s'applique à un élément d'un
nouveau log :

* **choix rapide** : Strict, Recommandé (par défaut), Tolérant, Par code seulement ;
* **critères** à cocher (outil, type, code, description, nom du fichier, chemin,
  numéro de ligne), chacun illustré par la valeur de l'élément sélectionné et
  par la conséquence de le décocher ;
* **tolérances sur la description** : ignorer le texte entre guillemets, les noms
  de fichiers et chemins, les nombres, la casse. Exemple : « le fichier
  ‹…› est introuvable » rapproche *dada.txt* et *theme.qss* ;
* **aperçu immédiat** : nombre d'éléments justifiés avant → après, liste des
  éléments qui retrouveraient une justification (et laquelle) ou en perdraient.

Les règles sont enregistrées dans le projet. Elles ne suppriment jamais de
justification : revenir au réglage précédent restaure exactement l'état
antérieur.

Raccourcis : F1 documentation PDF à la page du code, Ctrl+G fichier source à la
ligne, Ctrl+I aide IA, Ctrl+F rechercher, Ctrl+M règles de correspondance,
Ctrl+R modifier le plugin, Ctrl+Maj+N nouveau plugin, Maj+F1 didacticiel.

## 4. Fichiers manipulés

| Fichier | Format | Rôle |
|---|---|---|
| `config/app_config.ini` | INI | catégories, règles de correspondance, éditeur externe, langue IA |
| `plugins/<outil>.ini` | INI | description d'un format de log (regex) |
| `plugins/<outil>_pdf_index.ini` | INI | code → page de la documentation PDF |
| `*.lwp` | JSON | **projet** : plugin, logs, utilisateur, justifications, règles de correspondance (format v2 ; les projets v1 restent lisibles) |
| `*.lwj` | JSON | **justifications seules**, à transmettre à un autre concepteur |
| `*.xlsx` / `*.docx` | Office | exports (synthèse, éléments, justifications) |

### 4.1 Format d'un plugin

```ini
[plugin]
tool_name = TINTIN
element_types = Note, Warning, Error
file_extensions = .log, .tlog
pdf_documentation = tintin_manual.pdf
pdf_page_index = tintin_pdf_index.ini

[type:Warning]
detect = ^\[[^\]]+\]\s+WARNING\s
fields = file, line, code, description
regex.file = WARNING\s+\S+\s+([^:\s]+):\d+
regex.line = WARNING\s+\S+\s+[^:\s]+:(\d+)
regex.code = WARNING\s+(\S+)
regex.description = \s-\s(?P<value>.*)$
```

* `element_types` : types recherchés ; leur ordre fixe la priorité de détection.
* `file_extensions` : extensions des logs de l'outil. Un fichier portant l'une
  d'elles est associé automatiquement à ce plugin (sauf si un autre plugin
  reconnaît clairement son contenu alors que celui-ci n'y reconnaît rien).
  Sans extension déclarée, le plugin est choisi d'après le contenu du log ; si
  rien ne convient, l'outil demande quel plugin utiliser et propose de
  **mémoriser l'extension** dans le plugin (seule la ligne `file_extensions` est
  modifiée, les commentaires sont conservés).
* `pdf_documentation` / `pdf_page_index` : optionnels, chemins relatifs au plugin.
* `detect` : regex identifiant une ligne du type ; `fields` : champs à extraire.

Règle d'extraction d'un champ : groupe nommé `(?P<value>…)` s'il existe, sinon
premier groupe capturant, sinon correspondance complète. Les champs `file` et
`line` activent « Aller à la ligne » ; `code` alimente la documentation PDF, l'aide
IA et le classement par code. Des champs supplémentaires peuvent être déclarés.

> Les commentaires INI ne sont reconnus qu'en **début de ligne** (`#` ou `;`) :
> un `#` ou `;` placé après une valeur fait partie de la regex.

### 4.2 Créer ou modifier un plugin (menu Outils)

* **Outils > Créer un nouveau plugin** part d'un plugin vierge, même si d'autres
  plugins existent ; **Modifier le plugin actuel** ouvre celui en cours. Un
  nouveau plugin est proposé à l'enregistrement dans `plugins/`, où il est
  détecté automatiquement. Le champ « Extensions des logs » se remplit tout seul
  avec l'extension du log d'exemple chargé.
* **Assistant regex pas à pas** (aucune regex à écrire) :
  1. choisir le **type** (ex. Warning), existant ou nouveau ;
  2. cliquer sur une **ligne d'exemple** où l'élément apparaît en entier ;
  3. surligner les **éléments à extraire** (chemin, ligne, code, description,
     ou tout autre champ) et les **parties variables sans intérêt** (date,
     heure…) — le bouton « Proposer automatiquement » repère dates et nombres.
     **Tout le reste est considéré comme invariant** et sert seul de repère :
     chaque élément sélectionné peut prendre n'importe quelle valeur. Le modèle
     de ligne obtenu s'affiche, ex. `[‹…›] WARNING ‹Code› ‹Fichier›:‹Ligne› - ‹Description›` ;
  4. **vérifier** : les regex sont appliquées à tout l'exemple, avec le nombre de
     lignes reconnues et les valeurs extraites de chacune.
* testeur de regex en direct, validation et enregistrement, avec rechargement
  proposé dans la session.

### 4.3 Correspondance des justifications

Chaque justification mémorise le contexte complet de l'élément justifié (outil,
type, code, description, fichier, chemin, ligne). Pour un nouvel élément, une
**empreinte de comparaison** est calculée selon les règles de correspondance du
projet (§ 3.5) ; si plusieurs justifications correspondent, la plus
prioritaire l'emporte, puis la plus récente. Les règles par défaut d'un nouveau
projet sont celles de la section `[matching]` de `config/app_config.ini`
(`keys`, `mask_numbers`, `mask_quoted`, `mask_paths`, `ignore_case`).

## 5. Aide IA

Sur l'élément sélectionné, **Aide IA…** génère un prompt (affiché dans le
terminal et dans le dialogue) demandant à l'IA d'expliquer le message, d'évaluer
s'il pose problème selon sa gravité, de choisir un statut et de proposer une
justification, dans un format structuré :

```
EXPLICATION: …
ANALYSE: …
STATUT: justified
JUSTIFICATION: …
```

Sans IA branchée, copiez le prompt, collez la réponse, puis « Analyser la
réponse » et « Justifier avec la proposition de l'IA » (option : tous les
éléments du même code). L'origine « ia » est conservée dans la justification.

**Brancher une IA** : implémentez `AiProvider` et injectez-le dans `main.py`.

```python
from logwaver.model.ai_assistant import AiProvider

class MyAiProvider(AiProvider):
    def ask(self, prompt: str) -> str | None:
        return mon_client.complete(prompt)   # appel à votre IA

# main.py : MainPresenter(window, session, MyAiProvider(), UserPreferences())
```

## 6. Architecture (MVP – « Passive View »)

```
log_waver/
├── main.py                        # composition des couches + lancement Qt
├── requirements.txt / requirements-dev.txt / setup.cfg
├── README.md / CHANGELOG.md / CONTRIBUTING.md
├── docs/GESTION_DE_CONFIGURATION.md
├── docs/conception/HISTORIQUE_CONCEPTION.md
├── .github/                       # CI, modèles d'issue et de PR
├── config/app_config.ini          # catégories, correspondance, éditeur, IA
├── plugins/                       # plugin TINTIN + index + PDF d'exemple
├── resources/styles/main.qss      # tout le style visuel (séparé du code)
├── resources/tutorial/            # contenu du didacticiel (INI éditable)
├── samples/                       # logs des concepteurs A et B + sources
├── tests/                         # unittest (64 tests, dont 5 tests d'IHM)
└── logwaver/
    ├── constants.py               # constantes UPPER_CASE centralisées
    ├── logging_setup.py           # journal console + fichier tournant
    ├── view_models.py             # DTO immuables Présentateur <-> Vue
    ├── model/                     # MODÈLE : Python pur, aucun import Qt
    │   ├── session.py             # façade métier (WaverSession)
    │   ├── entities.py            # LogEntry, Justification, StatusDefinition
    │   ├── plugin.py              # lecture/écriture/compilation des plugins
    │   ├── log_parser.py          # extraction des éléments d'un log
    │   ├── fingerprint.py         # empreinte = clé de réutilisation
    │   ├── justification_repository.py
    │   ├── undo.py                # patron Commande + pile Ctrl+Z
    │   ├── entry_filter.py        # filtrage (catégorie, type, code, texte)
    │   ├── project_store.py       # .lwp / .lwj (JSON, écriture atomique)
    │   ├── statistics.py          # synthèse types × catégories (numpy)
    │   ├── ai_assistant.py        # PromptBuilder, AiProvider, parseur
    │   ├── regex_tools.py         # testeur + générateur de regex
    │   ├── pdf_index.py           # code -> page de documentation
    │   ├── source_files.py        # lecture source, éditeur externe
    │   ├── preferences.py         # dernier utilisateur, didacticiel proposé
    │   ├── grouping.py            # regroupement par code, fichier, champ…
    │   ├── plugin_detector.py     # choix du plugin (extension, contenu) + mémorisation
    │   ├── justification_index.py # correspondance et priorités des justifications
    │   ├── matching_presets.py    # préréglages Strict / Recommandé / Tolérant…
    │   ├── tutorial.py            # lecture et progression du didacticiel
    │   ├── events.py              # patron Observateur
    │   ├── app_config.py / exceptions.py
    │   └── exporters/             # xlsx_writer, excel_exporter, docx_exporter
    ├── presenter/                 # PRÉSENTATEURS : logique d'interaction
    │   ├── main_presenter.py
    │   ├── ai_assistant_presenter.py
    │   ├── plugin_editor_presenter.py
    │   ├── tutorial_presenter.py
    │   ├── regex_wizard_presenter.py
    │   ├── matching_rules_presenter.py
    │   └── error_handling.py      # décorateur @guarded (try/except + logs)
    └── view/                      # VUES : widgets passifs, signaux uniquement
        ├── main_window.py
        ├── entry_tree_model.py    # modèle Qt : liste à plat ou groupes repliables
        ├── style_loader.py
        ├── widgets/               # entry_tree, filter_bar, category_panel,
        │                          # details_panel, welcome_page, tutorial_panel
        └── dialogs/               # justification, aide IA, éditeur de plugin,
                                   # assistant regex, règles de correspondance,
                                   # visionneuse source, visionneuse PDF
```

Principes appliqués :

* **Modèle sans Qt** : testable sans interface ; il publie des événements
  (`EventHub`) auxquels le présentateur s'abonne.
* **Vues passives** : elles n'émettent que des signaux et n'affichent que des DTO
  (`view_models.py`) ; aucune n'importe le modèle.
* **Erreurs** : exceptions métier typées (`LogWaverError` et dérivées) ; chaque
  action utilisateur est protégée par `@guarded`, qui journalise et affiche un
  message clair sans faire tomber l'application.
* **Undo** : toute modification des justifications passe par une unique
  `ChangeJustificationsCommand` (état avant/après), d'où un Ctrl+Z fiable pour le
  classement, le retrait, le classement en masse et l'import.
* **Style** : uniquement dans `main.qss` (objectName + propriétés dynamiques) ;
  seules les couleurs des catégories, qui sont des données de configuration,
  sont appliquées par le code.

## 7. Dépannage

* **Le PDF ne s'affiche pas dans la visionneuse intégrée** : PyQtWebEngine
  nécessite un pilote OpenGL fonctionnel. Sous Linux, en tant que root, exportez
  `QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox`. Si PyQtWebEngine est absent, le PDF
  est ouvert par l'application système et la page à consulter est indiquée.
* **Aucun élément reconnu** : Outils > Modifier le plugin actuel, collez quelques lignes
  du log et vérifiez la regex de détection.
* **Justifications non retrouvées après import ou sur un nouveau log** : ouvrez
  Édition > Règles de correspondance (Ctrl+M) et décochez ce qui change d'un log
  à l'autre ; l'aperçu indique combien d'éléments retrouveraient leur
  justification.

## 8. Gestion de configuration

Versionnage sémantique, branches `main` / `develop` / `feature/*`, commits
conventionnels, CI GitHub Actions (PEP 8, analyse statique, contrôle de
l'architecture MVP, tests sur Linux et Windows) et publication automatique des
versions étiquetées `vX.Y.Z` : voir
[`docs/GESTION_DE_CONFIGURATION.md`](docs/GESTION_DE_CONFIGURATION.md),
[`CONTRIBUTING.md`](CONTRIBUTING.md) et [`CHANGELOG.md`](CHANGELOG.md).
L'historique de conception (demandes, décisions, vérifications) est dans
[`docs/conception/HISTORIQUE_CONCEPTION.md`](docs/conception/HISTORIQUE_CONCEPTION.md).
