# Journal des modifications

Toutes les évolutions notables de LogWaver sont consignées ici.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
projet respecte le [versionnage sémantique](https://semver.org/lang/fr/)
(MAJEUR.MINEUR.CORRECTIF). La version de référence est `__version__` dans
`logwaver/__init__.py` ; un test vérifie qu'elle correspond à la dernière
version publiée ci-dessous.

## [Non publié]

## [1.0.0] - 2026-11-20

### Ajouté
- Lecture de logs de n'importe quel outil via des plugins INI (regex de
  détection et regex par champ).
- Classement des éléments dans des catégories configurables avec justification
  signée par l'utilisateur, retrait de justification, annulation/rétablissement
  (Ctrl+Z / Ctrl+Y).
- Fichier projet `.lwp` et fichier de justifications `.lwj` (format v1) ;
  réapplication automatique des justifications sur un nouveau log et entre
  concepteurs.
- Filtres (catégorie, type, code, fichier, texte libre).
- Génération de prompts d'aide IA (affichés dans le terminal) et justification
  à partir de la réponse, y compris pour tout un code.
- Ouverture de la documentation PDF à la page du code ; visionneuse de fichier
  source positionnée sur la ligne ; éditeur externe optionnel.
- Éditeur de plugin avec testeur de regex et génération automatique.
- Exports Excel (sans bibliothèque tierce) et Word.
- Exemple complet TINTIN (plugin, index, PDF, logs des concepteurs A et B).

[Non publié]: https://github.com/DavidBoccara/LogWaver/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/DavidBoccara/LogWaver/releases/tag/v1.0.0
