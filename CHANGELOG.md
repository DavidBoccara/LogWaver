# Journal des modifications

Toutes les évolutions notables de LogWaver sont consignées ici.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
projet respecte le [versionnage sémantique](https://semver.org/lang/fr/)
(MAJEUR.MINEUR.CORRECTIF). La version de référence est `__version__` dans
`logwaver/__init__.py` ; un test vérifie qu'elle correspond à la dernière
version publiée ci-dessous.

## [Non publié]

## [1.2.1] - 2026-11-22

### Documentation
- **Documentation technique complète du code** en PDF
  (`docs/LogWaver_Documentation_Code.pdf`, 84 pages) : architecture MVP,
  mécanismes du modèle, flux principaux, interface, formats de fichiers, qualité,
  et référence exhaustive de chaque module, classe et méthode extraite des sources.
- **Présentation PowerPoint** de l'application (`docs/LogWaver_Presentation.pptx`,
  12 planches).
- Captures d'écran (`docs/images/`) et outils de régénération (`tools/doc/`).
- La CI vérifie aussi le style des outils de documentation.

Aucune modification du comportement de l'application.

## [1.2.0] - 2026-11-22

### Ajouté
- **Extensions de fichiers dans les plugins** (`file_extensions = .log, .mx`) :
  un log portant l'une d'elles est associé automatiquement au plugin. Si aucun
  plugin ne convient, l'outil demande lequel utiliser et propose de mémoriser
  l'extension (seule la ligne concernée du plugin est modifiée).
- **Créer un nouveau plugin de zéro** (Outils > Créer un nouveau plugin), même si
  des plugins existent déjà ; enregistrement proposé dans `plugins/`.
- **Assistant regex pas à pas** : type → ligne d'exemple → éléments à extraire
  et parties variables sans intérêt → vérification sur tout l'exemple. Les regex
  reposent uniquement sur le texte invariant ; chaque élément sélectionné peut
  prendre n'importe quelle valeur. Détection automatique des dates et nombres.
- **Priorités des catégories** (`priority` dans la configuration) : lors d'un
  import, la justification de la catégorie la plus prioritaire l'emporte
  (« Rejeté » remplace « Justifié ») ; à priorité égale, l'existante est gardée.
- **Règles de correspondance réglables dans l'outil** (Édition > Règles de
  correspondance, Ctrl+M) : préréglages, critères cochables illustrés par
  l'élément sélectionné, tolérances sur la description (texte entre guillemets,
  noms de fichiers, nombres, casse) et aperçu immédiat des éléments qui
  retrouveraient ou perdraient une justification.
- Étape « Règles de correspondance » dans le didacticiel (17 étapes).

### Modifié
- Fichiers projet et de justifications au **format v2** (règles de
  correspondance enregistrées) ; les fichiers v1 restent lisibles.
- Chaque justification mémorise le contexte complet de l'élément (chemin et
  ligne compris) ; changer les règles ne supprime jamais de justification.
- L'import de justifications ne pose plus la question « remplacer ? » : la
  priorité décide, et le bilan détaille ajoutées / remplacées / écartées.
- Éditeur de plugin : champ « Extensions des logs », bouton « Nouveau plugin » ;
  l'ancien marquage manuel est remplacé par l'assistant pas à pas.
- La regex générée ne généralise plus le texte fixe (les chiffres restent
  littéraux) : les parties variables sont désormais marquées explicitement.

## [1.1.0] - 2026-11-21

### Ajouté
- **Regroupement** des éléments par code, fichier (chemin ou nom seul),
  description identique, type, catégorie, auteur, log ou tout autre champ du
  plugin. Les groupes sont repliables ; sélectionner un groupe sélectionne tous
  ses éléments, qui sont alors justifiés en une seule action.
- **Didacticiel interactif** (16 étapes) : panneau dédié, mise en évidence de
  l'élément d'interface concerné, bouton « Montre-moi » ; proposé au premier
  lancement, contenu éditable dans `resources/tutorial/didacticiel.ini`.
- **Détection automatique du plugin** à l'ouverture d'un log.
- Page d'accueil en trois étapes, bouton « Essayer avec l'exemple fourni ».
- Bandeau « À faire » indiquant en permanence la prochaine action.
- Catégorie proposée par défaut configurable (`[statuses] default`).

### Modifié
- Fenêtre « Justifier » : catégories présentées en boutons à cocher avec leur
  description, et rappel de ce qui va être justifié (élément ou groupe).
- Barre d'outils réduite aux actions essentielles, avec icônes ; libellés de
  menus reformulés (« Partager mes justifications », « Récupérer les
  justifications d'un collègue »…).
- Filtres code/fichier/type regroupés sous « Plus de filtres ».
- Panneau de droite : actions en premier, cadres de détail masqués sans sélection.
- La liste des éléments est désormais une arborescence (`EntryTree`).

### Documentation
- Historique complet de la conception de l'outil
  (`docs/conception/HISTORIQUE_CONCEPTION.md`) : demandes, réponses, travaux
  réalisés, registre des décisions et couverture des exigences.

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

[Non publié]: https://github.com/DavidBoccara/LogWaver/compare/v1.2.1...HEAD
[1.2.1]: https://github.com/DavidBoccara/LogWaver/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/DavidBoccara/LogWaver/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/DavidBoccara/LogWaver/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/DavidBoccara/LogWaver/releases/tag/v1.0.0
