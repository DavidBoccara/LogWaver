# Génération de la documentation

Ces outils produisent les documents de `docs/`. Ils ne sont **pas** nécessaires
pour exécuter LogWaver.

| Document | Commande | Prérequis |
|---|---|---|
| Captures d'écran `docs/images/*.png` | `QT_QPA_PLATFORM=offscreen python tools/doc/captures_ecran.py` | dépendances de l'application |
| PDF `docs/LogWaver_Documentation_Code.pdf` | `python tools/doc/generer_documentation_pdf.py` | `pip install -r tools/doc/requirements-doc.txt`, polices DejaVu |
| Présentation `docs/LogWaver_Presentation.pptx` | `node tools/doc/generer_presentation.js` | `npm install pptxgenjs react react-dom react-icons sharp` |

Ordre conseillé : captures, puis PDF et présentation (qui les réutilisent).

Le chapitre 9 du PDF (référence du code) est extrait automatiquement des
sources : régénérez le PDF à chaque version pour qu'il reste fidèle au code.
La version affichée est lue dans `logwaver/__init__.py`.
