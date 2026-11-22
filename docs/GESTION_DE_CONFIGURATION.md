# Plan de gestion de configuration — LogWaver

Ce document définit comment LogWaver est identifié, versionné, modifié, vérifié
et livré. Il s'applique à tout contributeur.

## 1. Outils

| Besoin | Outil |
|---|---|
| Gestion de versions | Git, dépôt de référence GitHub `DavidBoccara/LogWaver` |
| Suivi des demandes | GitHub Issues (modèles « anomalie » et « évolution ») |
| Revue des modifications | Pull requests GitHub (modèle de PR obligatoire) |
| Intégration continue | GitHub Actions (`.github/workflows/ci.yml`) |
| Dépendances | `requirements.txt` (exécution), `requirements-dev.txt` (développement) |

## 2. Éléments de configuration (EC)

| EC | Emplacement | Nature |
|---|---|---|
| Code source | `logwaver/`, `main.py` | code Python |
| Feuille de style | `resources/styles/main.qss` | QSS |
| Contenu du didacticiel | `resources/tutorial/didacticiel.ini` | données de paramétrage |
| Configuration applicative | `config/app_config.ini` | données de paramétrage |
| Plugins et index PDF | `plugins/*.ini` | données de paramétrage |
| Documentation d'outil | `plugins/*.pdf` | binaire (référence externe) |
| Données d'exemple | `samples/` | données de test |
| Tests | `tests/` | code Python |
| Documentation | `README.md`, `CHANGELOG.md`, `docs/` | texte |
| Documents générés | `docs/*.pdf`, `docs/*.pptx`, `docs/images/` | binaires, régénérés par `tools/doc/` à chaque version |
| Outils de documentation | `tools/doc/` | code (hors application) |
| Chaîne de vérification | `.github/`, `setup.cfg`, `requirements*.txt` | configuration |

Ne sont **pas** des EC et sont exclus par `.gitignore` : environnements
virtuels, caches, et les produits de travail des utilisateurs (`*.lwp`, `*.lwj`,
`*.xlsx`, `*.docx`). Un projet `.lwp` ou un fichier `.lwj` partagé entre
concepteurs relève de la gestion de configuration **de leur propre projet**, pas
de celle de LogWaver.

## 3. Identification et versionnage

* Versionnage sémantique `MAJEUR.MINEUR.CORRECTIF` :
  * **MAJEUR** : rupture de compatibilité (format `.lwp`/`.lwj`, format des
    plugins ou de la configuration, calcul de l'empreinte) ;
  * **MINEUR** : nouvelle fonctionnalité compatible ;
  * **CORRECTIF** : correction sans changement de comportement attendu.
* Source unique de la version : `__version__` dans `logwaver/__init__.py`.
  Le test `tests/test_version.py` refuse toute divergence avec `CHANGELOG.md`.
* Chaque livraison est une **étiquette annotée** `vX.Y.Z` posée sur `main`.
* Les fichiers de données portent leur propre version de format
  (`FILE_FORMAT_VERSION` dans `logwaver/constants.py`). Toute modification de ce
  format incrémente cette valeur et impose une version MAJEURE de l'application,
  sauf si la lecture des anciens fichiers est conservée (alors MINEURE).

> ⚠️ **Empreinte des justifications** : depuis la 1.2.0, les règles de
> correspondance sont réglables et enregistrées dans chaque projet ; les
> justifications gardent leur contexte complet. En revanche, modifier le contenu
> du contexte mémorisé ou l'identifiant strict (`FingerprintBuilder.strict`)
> reste une rupture de compatibilité (version MAJEURE + note de migration).

## 4. Branches (modèle Git Flow simplifié)

| Branche | Rôle | Règles |
|---|---|---|
| `main` | versions livrées uniquement | protégée ; fusion par PR depuis `develop` ou `hotfix/*` ; chaque fusion = une étiquette |
| `develop` | intégration de la prochaine version | protégée ; fusion par PR ; CI verte obligatoire |
| `feature/<n°>-<sujet>` | une évolution | part de `develop`, y revient par PR |
| `fix/<n°>-<sujet>` | une anomalie | part de `develop`, y revient par PR |
| `hotfix/<version>` | correctif urgent d'une version livrée | part de `main`, fusionnée dans `main` **et** `develop` |

`<n°>` est le numéro de l'issue GitHub : toute modification est tracée jusqu'à
une demande.

## 5. Messages de commit

Convention [Conventional Commits](https://www.conventionalcommits.org/fr/) :

```
<type>(<portée>): <résumé à l'impératif>

<corps facultatif : pourquoi, pas comment>

Refs #<n° d'issue>
```

Types : `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `build`, `ci`,
`chore`. Ajoutez `BREAKING CHANGE:` dans le corps pour une rupture de
compatibilité. Portées usuelles : `model`, `view`, `presenter`, `plugin`,
`export`, `ia`, `config`.

## 6. Maîtrise des modifications

1. Une issue décrit le besoin (modèle anomalie ou évolution).
2. Le développement se fait sur une branche dédiée.
3. La PR (modèle obligatoire) indique l'issue, l'impact sur les formats de
   fichiers et sur l'empreinte, et la mise à jour de `CHANGELOG.md`
   (rubrique « Non publié »).
4. La CI doit être verte : style PEP 8 (`pycodestyle`), analyse statique
   (`pyflakes`), tests unitaires et test d'interface hors écran, sur Linux et
   Windows, Python 3.8 à 3.12.
5. Une revue approuvée est requise avant fusion.

## 7. Livraison d'une version

Depuis `develop` à jour et CI verte :

```bash
# 1. Préparer la version
git switch -c release/1.1.0 develop
#    - mettre __version__ = "1.1.0" dans logwaver/__init__.py
#    - dans CHANGELOG.md, renommer « Non publié » en « [1.1.0] - AAAA-MM-JJ »,
#      recréer une rubrique « Non publié » vide et mettre à jour les liens
git commit -am "chore(release): 1.1.0"

# 2. PR release/1.1.0 -> main, puis après fusion :
git switch main && git pull
git tag -a v1.1.0 -m "LogWaver 1.1.0"
git push origin v1.1.0

# 3. Reporter main dans develop
git switch develop && git merge --no-ff main && git push
```

Le workflow CI crée automatiquement une **release GitHub** pour toute étiquette
`v*` et y attache l'archive source et les notes extraites du CHANGELOG.

## 8. Lignes de base

| Ligne de base | Contenu | Matérialisation |
|---|---|---|
| Développement | état intégré courant | tête de `develop` |
| Produit | version livrée | étiquette `vX.Y.Z` sur `main` + release GitHub |

Une ligne de base livrée n'est jamais modifiée : toute correction donne une
nouvelle version.

## 9. Réglages GitHub à activer (une fois)

Dans *Settings > Branches*, pour `main` et `develop` :
« Require a pull request before merging », « Require status checks to pass »
(job `Vérification`), « Do not allow bypassing the above settings ».
