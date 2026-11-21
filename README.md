# LogWaver — suivi et justification des messages de logs

[![CI](https://github.com/DavidBoccara/LogWaver/actions/workflows/ci.yml/badge.svg)](https://github.com/DavidBoccara/LogWaver/actions/workflows/ci.yml)

LogWaver lit le fichier de log de **n'importe quel outil** grâce à des fichiers
*plugin*, extrait les notes / warnings / erreurs, et permet de les filtrer, de les
classer dans des catégories (À traiter, Justifié, Rejeté…) avec une justification
signée, puis de **réutiliser automatiquement ces justifications** sur de nouveaux
logs ou chez un autre concepteur.

---

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

Raccourcis : F1 documentation PDF à la page du code, Ctrl+G fichier source à la
ligne, Ctrl+I aide IA, Ctrl+F rechercher, Ctrl+R éditeur de plugin, Maj+F1
didacticiel.

## 4. Fichiers manipulés

| Fichier | Format | Rôle |
|---|---|---|
| `config/app_config.ini` | INI | catégories, règles de correspondance, éditeur externe, langue IA |
| `plugins/<outil>.ini` | INI | description d'un format de log (regex) |
| `plugins/<outil>_pdf_index.ini` | INI | code → page de la documentation PDF |
| `*.lwp` | JSON | **projet** : plugin, logs, utilisateur, justifications |
| `*.lwj` | JSON | **justifications seules**, à transmettre à un autre concepteur |
| `*.xlsx` / `*.docx` | Office | exports (synthèse, éléments, justifications) |

### 4.1 Format d'un plugin

```ini
[plugin]
tool_name = TINTIN
element_types = Note, Warning, Error
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
* `pdf_documentation` / `pdf_page_index` : optionnels, chemins relatifs au plugin.
* `detect` : regex identifiant une ligne du type ; `fields` : champs à extraire.

Règle d'extraction d'un champ : groupe nommé `(?P<value>…)` s'il existe, sinon
premier groupe capturant, sinon correspondance complète. Les champs `file` et
`line` activent « Aller à la ligne » ; `code` alimente la documentation PDF, l'aide
IA et le classement par code. Des champs supplémentaires peuvent être déclarés.

> Les commentaires INI ne sont reconnus qu'en **début de ligne** (`#` ou `;`) :
> un `#` ou `;` placé après une valeur fait partie de la regex.

### 4.2 Éditeur de plugin et testeur de regex (Outils > Éditeur…)

* coloration en direct des valeurs extraites sur un log d'exemple ;
* **génération automatique** : sélectionnez à la souris la valeur de chaque champ
  dans une ligne d'exemple, « Marquer la sélection », puis « Générer les regex ».
  Les regex produites sont vérifiées sur la ligne avant d'être proposées ;
* validation et enregistrement, avec rechargement proposé dans la session.

### 4.3 Correspondance des justifications (`[matching]` de la configuration)

Une justification est liée à une **empreinte** calculée à partir des attributs
listés dans `keys` (par défaut : outil, type, code, description, nom court du
fichier). Le numéro de ligne et le répertoire sont exclus par défaut : la
justification survit donc aux modifications du code et à son déplacement chez un
autre concepteur. Ajoutez `line` ou `file_path` pour un appariement plus strict.

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
├── tests/                         # unittest (43 tests, dont 3 tests d'IHM)
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
    │   ├── plugin_detector.py     # détection automatique du plugin
    │   ├── tutorial.py            # lecture et progression du didacticiel
    │   ├── events.py              # patron Observateur
    │   ├── app_config.py / exceptions.py
    │   └── exporters/             # xlsx_writer, excel_exporter, docx_exporter
    ├── presenter/                 # PRÉSENTATEURS : logique d'interaction
    │   ├── main_presenter.py
    │   ├── ai_assistant_presenter.py
    │   ├── plugin_editor_presenter.py
    │   ├── tutorial_presenter.py
    │   └── error_handling.py      # décorateur @guarded (try/except + logs)
    └── view/                      # VUES : widgets passifs, signaux uniquement
        ├── main_window.py
        ├── entry_tree_model.py    # modèle Qt : liste à plat ou groupes repliables
        ├── style_loader.py
        ├── widgets/               # entry_tree, filter_bar, category_panel,
        │                          # details_panel, welcome_page, tutorial_panel
        └── dialogs/               # justification, aide IA, éditeur de plugin,
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
* **Aucun élément reconnu** : ouvrez l'éditeur de plugin, collez quelques lignes
  du log et vérifiez la regex de détection.
* **Justifications non retrouvées après import** : un avertissement s'affiche si
  les clés `[matching]` diffèrent entre les deux concepteurs ; alignez-les.

## 8. Gestion de configuration

Versionnage sémantique, branches `main` / `develop` / `feature/*`, commits
conventionnels, CI GitHub Actions (PEP 8, analyse statique, contrôle de
l'architecture MVP, tests sur Linux et Windows) et publication automatique des
versions étiquetées `vX.Y.Z` : voir
[`docs/GESTION_DE_CONFIGURATION.md`](docs/GESTION_DE_CONFIGURATION.md),
[`CONTRIBUTING.md`](CONTRIBUTING.md) et [`CHANGELOG.md`](CHANGELOG.md).
L'historique de conception (demandes, décisions, vérifications) est dans
[`docs/conception/HISTORIQUE_CONCEPTION.md`](docs/conception/HISTORIQUE_CONCEPTION.md).
