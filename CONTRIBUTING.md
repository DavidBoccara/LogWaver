# Contribuer à LogWaver

Les règles complètes (branches, versions, livraison) sont dans
[`docs/GESTION_DE_CONFIGURATION.md`](docs/GESTION_DE_CONFIGURATION.md).
Résumé pour démarrer :

## Préparer son poste

```bash
git clone https://github.com/DavidBoccara/LogWaver.git
cd LogWaver
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
```

## Cycle d'une modification

```bash
git switch develop && git pull
git switch -c feature/12-filtre-par-auteur
# ... développement ...
python -m pycodestyle main.py logwaver tests
python -m pyflakes main.py logwaver tests
python -m unittest discover -s tests -t .
git commit -m "feat(view): filtre par auteur de justification" -m "Refs #12"
git push -u origin feature/12-filtre-par-auteur
# puis ouvrir une pull request vers develop
```

## Règles de code (vérifiées par la CI)

* PEP 8, lignes de 99 caractères maximum ;
* `snake_case` (fonctions, variables), `PascalCase` (classes), `UPPER_CASE`
  (constantes, regroupées dans `logwaver/constants.py`) ;
* annotations de type sur toutes les signatures ;
* docstring (rôle, paramètres, retour) sur chaque classe et méthode ;
* architecture MVP : le paquet `logwaver/model` n'importe jamais PyQt5 ;
  les vues n'importent jamais le modèle ;
* aucune dépendance hors PyQt5, PyQtWebEngine, numpy, python-docx ;
* tout style visuel va dans `resources/styles/main.qss` ;
* toute modification visible est ajoutée à la rubrique « Non publié » de
  `CHANGELOG.md`.
