"""Génère la documentation technique complète du code au format PDF.

Le document combine des chapitres rédigés (architecture, flux, formats,
qualité) et une **référence exhaustive extraite automatiquement du code**
(chaque module, classe, fonction et méthode, avec sa signature et sa
docstring) : il reste ainsi fidèle au code à chaque régénération.

Outil de documentation uniquement (non nécessaire pour exécuter LogWaver) ::

    pip install -r tools/doc/requirements-doc.txt
    python tools/doc/generer_documentation_pdf.py
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT: Path = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from logwaver import __version__  # noqa: E402

OUTPUT: Path = ROOT / "docs" / "LogWaver_Documentation_Code.pdf"
IMAGES: Path = ROOT / "docs" / "images"
FONT_DIR: Path = Path("/usr/share/fonts/truetype/dejavu")
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN: float = 2.0 * cm
CONTENT_WIDTH: float = PAGE_WIDTH - 2 * MARGIN

NAVY = colors.HexColor("#2f4f6f")
BLUE = colors.HexColor("#2f6fb0")
GREEN = colors.HexColor("#2e9d4f")
ORANGE = colors.HexColor("#e0a000")
LIGHT = colors.HexColor("#eef3f8")
GREY = colors.HexColor("#5f6b76")
CODE_BG = colors.HexColor("#f6f8fa")

# Ordre de présentation des modules dans la référence (par couche).
LAYERS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("Point d'entrée et socle", "Démarrage, constantes, journalisation, objets de transfert.",
     ("main.py", "logwaver/__init__.py", "logwaver/constants.py", "logwaver/logging_setup.py",
      "logwaver/view_models.py")),
    ("Couche Modèle", "Logique métier en Python pur : aucun import de PyQt5.",
     ("logwaver/model/",)),
    ("Couche Présentateur", "Relie les vues passives au modèle ; toute la logique d'interaction.",
     ("logwaver/presenter/",)),
    ("Couche Vue", "Widgets PyQt5 passifs : affichage et signaux uniquement.",
     ("logwaver/view/",)),
)


# =========================================================================== styles
def register_fonts() -> None:
    """Enregistre les polices DejaVu (accents et symboles ‹…› ✔ → ●)."""
    for name, file_name in (("DejaVu", "DejaVuSans.ttf"), ("DejaVu-Bold", "DejaVuSans-Bold.ttf"),
                            ("DejaVu-Italic", "DejaVuSans-Oblique.ttf"),
                            ("DejaVu-BoldItalic", "DejaVuSans-BoldOblique.ttf"),
                            ("DejaVuMono", "DejaVuSansMono.ttf"),
                            ("DejaVuMono-Bold", "DejaVuSansMono-Bold.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file_name)))
    pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                                  italic="DejaVu-Italic", boldItalic="DejaVu-BoldItalic")
    pdfmetrics.registerFontFamily("DejaVuMono", normal="DejaVuMono", bold="DejaVuMono-Bold",
                                  italic="DejaVuMono", boldItalic="DejaVuMono-Bold")


@dataclass
class Styles:
    """Feuille de styles du document."""

    body: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Body", fontName="DejaVu", fontSize=9.6, leading=13.6, spaceAfter=5,
        textColor=colors.HexColor("#1f2933")))
    h1: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "H1", fontName="DejaVu-Bold", fontSize=19, leading=24, spaceBefore=4, spaceAfter=12,
        textColor=NAVY))
    h2: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "H2", fontName="DejaVu-Bold", fontSize=13.5, leading=17, spaceBefore=12, spaceAfter=6,
        textColor=BLUE))
    h3: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "H3", fontName="DejaVu-Bold", fontSize=11, leading=14, spaceBefore=9, spaceAfter=4,
        textColor=NAVY))
    module: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Module", fontName="DejaVuMono-Bold", fontSize=11, leading=14, spaceBefore=12,
        spaceAfter=5, textColor=colors.white, backColor=NAVY, borderPadding=(4, 6, 4, 6)))
    klass: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Class", fontName="DejaVuMono-Bold", fontSize=9.6, leading=12.5, spaceBefore=8,
        spaceAfter=3, textColor=BLUE))
    signature: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Signature", fontName="DejaVuMono", fontSize=7.9, leading=10.2, leftIndent=10,
        spaceBefore=4, spaceAfter=1, textColor=colors.HexColor("#0b3d6b"),
        backColor=CODE_BG, borderPadding=(2, 3, 2, 3)))
    docstring: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Doc", fontName="DejaVu", fontSize=8.4, leading=11, leftIndent=18, spaceAfter=2,
        textColor=colors.HexColor("#33404d")))
    bullet: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Bullet", fontName="DejaVu", fontSize=9.6, leading=13.4, leftIndent=14,
        bulletIndent=4, spaceAfter=2))
    code: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Code", fontName="DejaVuMono", fontSize=7.8, leading=10, backColor=CODE_BG,
        borderPadding=6, leftIndent=4, rightIndent=4, spaceBefore=4, spaceAfter=8))
    caption: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Caption", fontName="DejaVu-Italic", fontSize=8.4, leading=11, alignment=TA_CENTER,
        textColor=GREY, spaceAfter=10))
    cell: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Cell", fontName="DejaVu", fontSize=8.2, leading=10.6))
    cell_head: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "CellHead", fontName="DejaVu-Bold", fontSize=8.2, leading=10.6,
        textColor=colors.white))
    note: ParagraphStyle = field(default_factory=lambda: ParagraphStyle(
        "Note", fontName="DejaVu", fontSize=9, leading=12.6, backColor=colors.HexColor("#fff8e1"),
        borderColor=colors.HexColor("#f0d58c"), borderWidth=0.6, borderPadding=7,
        spaceBefore=6, spaceAfter=10))


ST = Styles()


def code_markup(text: str) -> str:
    """Met en forme les fragments `code` d'un texte balisé (style Markdown simplifié).

    Le texte peut contenir **gras** et `code` ; le reste est échappé.

    :param text: texte source.
    :return: balisage ReportLab.
    """
    parts = re.split(r"(`[^`]+`)", text)
    out: List[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f'<font name="DejaVuMono" color="#0b3d6b">{escape(part[1:-1])}</font>')
        else:
            chunk = escape(part)
            chunk = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", chunk)
            out.append(chunk)
    return "".join(out)


def p(text: str, style: Optional[ParagraphStyle] = None) -> Paragraph:
    """Crée un paragraphe à partir d'un texte au balisage simplifié.

    :param text: texte (**gras**, `code`).
    :param style: style (corps de texte par défaut).
    :return: paragraphe.
    """
    return Paragraph(code_markup(text), style or ST.body)


def bullets(items: Sequence[str]) -> List[Paragraph]:
    """Crée une liste à puces.

    :param items: éléments (balisage simplifié).
    :return: paragraphes.
    """
    return [Paragraph(code_markup(item), ST.bullet, bulletText="•") for item in items]


def table(rows: Sequence[Sequence[str]], widths: Sequence[float],
          header: bool = True) -> Table:
    """Crée un tableau stylé.

    :param rows: lignes (la première est l'en-tête si ``header``).
    :param widths: largeurs relatives des colonnes (somme quelconque).
    :param header: ``True`` si la première ligne est un en-tête.
    :return: tableau.
    """
    total = sum(widths)
    col_widths = [CONTENT_WIDTH * w / total for w in widths]
    data = []
    for index, row in enumerate(rows):
        style = ST.cell_head if header and index == 0 else ST.cell
        data.append([Paragraph(code_markup(str(cell)), style) for cell in row])
    result = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d1d9")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, LIGHT]),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    result.setStyle(TableStyle(commands))
    return result


def code_block(text: str) -> Preformatted:
    """Crée un bloc de code.

    :param text: code.
    :return: bloc préformaté.
    """
    return Preformatted(text.strip("\n"), ST.code)


def screenshot(name: str, caption: str, width: float = CONTENT_WIDTH) -> KeepTogether:
    """Insère une capture d'écran avec sa légende.

    :param name: nom du fichier dans docs/images.
    :param caption: légende.
    :param width: largeur affichée.
    :return: bloc image + légende.
    """
    path = IMAGES / f"{name}.png"
    image = Image(str(path))
    ratio = image.imageHeight / image.imageWidth
    image.drawWidth, image.drawHeight = width, width * ratio
    return KeepTogether([image, Spacer(1, 3), p(caption, ST.caption)])


# ========================================================================= schémas
def _arrow(drawing: Drawing, x1: float, y1: float, x2: float, y2: float,
           color: colors.Color = GREY, label: str = "", dashed: bool = False) -> None:
    """Dessine une flèche avec une étiquette facultative.

    :param drawing: dessin cible.
    :param x1: abscisse de départ.
    :param y1: ordonnée de départ.
    :param x2: abscisse d'arrivée.
    :param y2: ordonnée d'arrivée.
    :param color: couleur.
    :param label: texte au milieu de la flèche.
    :param dashed: trait pointillé.
    """
    line = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1.3)
    if dashed:
        line.strokeDashArray = [3, 2]
    drawing.add(line)
    length = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1)
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    size = 6
    half = size * 0.5
    drawing.add(Polygon([x2, y2,
                         x2 - size * ux + half * uy, y2 - size * uy - half * ux,
                         x2 - size * ux - half * uy, y2 - size * uy + half * ux],
                        fillColor=color, strokeColor=color))
    if label:
        drawing.add(String((x1 + x2) / 2 + 4, (y1 + y2) / 2 + 2, label, fontName="DejaVu-Italic",
                           fontSize=7, fillColor=color))


def _box(drawing: Drawing, x: float, y: float, w: float, h: float, title: str,
         lines: Sequence[str], fill: colors.Color,
         title_color: colors.Color = colors.white) -> None:
    """Dessine un cadre titré contenant quelques lignes.

    :param drawing: dessin cible.
    :param x: abscisse du coin inférieur gauche.
    :param y: ordonnée du coin inférieur gauche.
    :param w: largeur.
    :param h: hauteur.
    :param title: titre.
    :param lines: lignes de contenu.
    :param fill: couleur du bandeau de titre.
    :param title_color: couleur du titre.
    """
    drawing.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=colors.white, strokeColor=fill,
                     strokeWidth=1.4))
    drawing.add(Rect(x, y + h - 17, w, 17, rx=5, ry=5, fillColor=fill, strokeColor=fill))
    drawing.add(String(x + w / 2, y + h - 12.5, title, fontName="DejaVu-Bold", fontSize=8.6,
                       fillColor=title_color, textAnchor="middle"))
    for index, text in enumerate(lines):
        drawing.add(String(x + 7, y + h - 30 - index * 10.5, text, fontName="DejaVu",
                           fontSize=7.2, fillColor=colors.HexColor("#1f2933")))


def architecture_diagram() -> Drawing:
    """Schéma des trois couches MVP et de leurs échanges.

    :return: dessin.
    """
    width, height = CONTENT_WIDTH, 330
    d = Drawing(width, height)
    _box(d, 10, 235, 300, 88, "VUE  (PyQt5, passive)", [
        "MainWindow · EntryTree · FilterBar · CategoryPanel",
        "DetailsPanel · WelcomePage · TutorialPanel",
        "Dialogues : Justifier, Aide IA, Éditeur de plugin,",
        "Assistant regex, Règles de correspondance, Sources, PDF",
        "Style : resources/styles/main.qss"], BLUE)
    _box(d, 10, 122, 300, 80, "PRÉSENTATEURS", [
        "MainPresenter (orchestration de la fenêtre)",
        "TutorialPresenter · AiAssistantPresenter",
        "PluginEditorPresenter · RegexWizardPresenter",
        "MatchingRulesPresenter · @guarded (erreurs)"], ORANGE)
    _box(d, 10, 6, 300, 86, "MODÈLE  (Python pur, sans Qt)", [
        "WaverSession : façade de tout le métier",
        "Plugin, LogParser, PluginDetector, RegexGenerator",
        "FingerprintBuilder, JustificationIndex, Repository",
        "UndoStack + commandes, EventHub, ProjectStore",
        "Grouping, Statistics (numpy), Exporters, AI"], GREEN)
    _box(d, 345, 235, 130, 88, "DTO", [
        "view_models.py :", "EntryRow, EntryGroupView,", "EntryDetails, ActionsState,",
        "MatchingSettings…", "(dataclasses immuables)"], GREY)
    _box(d, 345, 6, 130, 86, "FICHIERS", [
        "plugins/*.ini", "config/app_config.ini", "*.lwp / *.lwj (JSON v2)",
        "logs, sources, PDF", "exports .xlsx / .docx"], NAVY)
    _arrow(d, 110, 235, 110, 202, BLUE, "signaux (intentions)")
    _arrow(d, 210, 202, 210, 235, ORANGE, "méthodes d'affichage")
    _arrow(d, 110, 122, 110, 92, ORANGE, "appels métier")
    _arrow(d, 210, 92, 210, 122, GREEN, "événements (EventHub)", dashed=True)
    _arrow(d, 310, 270, 345, 270, GREY)
    _arrow(d, 310, 160, 345, 255, GREY, dashed=True)
    _arrow(d, 310, 50, 345, 50, NAVY)
    d.add(String(312, 30, "lecture /", fontName="DejaVu-Italic", fontSize=7, fillColor=NAVY))
    d.add(String(312, 21, "écriture", fontName="DejaVu-Italic", fontSize=7, fillColor=NAVY))
    return d


def chain_diagram(steps: Sequence[Tuple[str, str]], colors_cycle: Sequence[colors.Color]
                  ) -> Drawing:
    """Schéma vertical d'une suite d'étapes (acteur, action).

    :param steps: couples (acteur, action).
    :param colors_cycle: couleurs des acteurs.
    :return: dessin.
    """
    box_h, gap = 26, 11
    height = len(steps) * (box_h + gap)
    d = Drawing(CONTENT_WIDTH, height)
    for index, (actor, action) in enumerate(steps):
        y = height - (index + 1) * (box_h + gap) + gap
        color = colors_cycle[index % len(colors_cycle)]
        d.add(Rect(10, y, 150, box_h, rx=4, ry=4, fillColor=color, strokeColor=color))
        d.add(String(85, y + 9.5, actor, fontName="DejaVuMono-Bold", fontSize=7.4,
                     fillColor=colors.white, textAnchor="middle"))
        d.add(Rect(168, y, CONTENT_WIDTH - 178, box_h, rx=4, ry=4, fillColor=LIGHT,
                   strokeColor=colors.HexColor("#c9d1d9")))
        d.add(String(176, y + 9.5, action, fontName="DejaVu", fontSize=7.8,
                     fillColor=colors.HexColor("#1f2933")))
        if index < len(steps) - 1:
            _arrow(d, 85, y, 85, y - gap + 1, GREY)
    return d


def index_diagram() -> Drawing:
    """Schéma de la correspondance élément ↔ justification (index et priorités).

    :return: dessin.
    """
    d = Drawing(CONTENT_WIDTH, 175)
    _box(d, 5, 70, 150, 98, "Justifications stockées", [
        "id strict (tous attributs)", "catégorie, texte, auteur,", "date, origine",
        "contexte complet de", "l'élément justifié"], GREEN)
    _box(d, 182, 70, 115, 98, "Règles", ["attributs comparés", "(code, description…)",
                                         "tolérances (‹…›)", "→ FingerprintBuilder"], ORANGE)
    _box(d, 325, 70, 150, 98, "JustificationIndex", ["clé → justifications", "retenue = priorité",
                                                     "la plus haute,", "puis la plus récente"],
         BLUE)
    _box(d, 325, 2, 150, 52, "Élément du log", ["empreinte selon les", "mêmes règles"], NAVY)
    _arrow(d, 155, 119, 182, 119, GREY, "contexte")
    _arrow(d, 297, 119, 325, 119, GREY, "clé")
    _arrow(d, 400, 54, 400, 70, NAVY, "justification_of()")
    return d


# ======================================================================= extraction
@dataclass
class FunctionDoc:
    """Fonction ou méthode extraite du code."""

    name: str
    signature: str
    doc: str
    decorators: List[str]
    is_property: bool = False


@dataclass
class ClassDoc:
    """Classe extraite du code."""

    name: str
    bases: str
    doc: str
    methods: List[FunctionDoc]
    is_dataclass: bool = False
    attributes: List[str] = field(default_factory=list)


@dataclass
class ModuleDoc:
    """Module extrait du code."""

    path: str
    doc: str
    lines: int
    classes: List[ClassDoc]
    functions: List[FunctionDoc]
    constants: List[str]


def _signature(node: ast.AST) -> str:
    """Reconstitue la signature d'une fonction (annotations comprises).

    :param node: nœud ``FunctionDef``.
    :return: signature textuelle.
    """
    args = node.args  # type: ignore[attr-defined]
    parts: List[str] = []
    positional = args.posonlyargs + args.args
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg + (f": {ast.unparse(arg.annotation)}" if arg.annotation else "")
        if default is not None:
            text += f" = {ast.unparse(default)}"
        parts.append(text)
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        text = arg.arg + (f": {ast.unparse(arg.annotation)}" if arg.annotation else "")
        if default is not None:
            text += f" = {ast.unparse(default)}"
        parts.append(text)
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""  # type: ignore
    return f"{node.name}({', '.join(parts)}){returns}"  # type: ignore[attr-defined]


def _function(node: ast.AST) -> FunctionDoc:
    """Extrait la documentation d'une fonction.

    :param node: nœud ``FunctionDef``.
    :return: documentation de la fonction.
    """
    decorators = [ast.unparse(d) for d in node.decorator_list]  # type: ignore[attr-defined]
    return FunctionDoc(node.name, _signature(node),  # type: ignore[attr-defined]
                       ast.get_docstring(node) or "", decorators,
                       "property" in decorators)


def extract_module(path: Path) -> ModuleDoc:
    """Analyse un fichier Python.

    :param path: fichier source.
    :return: documentation du module.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes: List[ClassDoc] = []
    functions: List[FunctionDoc] = []
    constants: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            decorators = [ast.unparse(d) for d in node.decorator_list]
            methods = [_function(item) for item in node.body
                       if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
            attributes = [ast.unparse(item.target) + ": " + ast.unparse(item.annotation)
                          for item in node.body if isinstance(item, ast.AnnAssign)]
            classes.append(ClassDoc(node.name, ", ".join(ast.unparse(b) for b in node.bases),
                                    ast.get_docstring(node) or "", methods,
                                    any("dataclass" in d for d in decorators), attributes))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(_function(node))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    constants.append(target.id)
    return ModuleDoc(str(path.relative_to(ROOT)).replace("\\", "/"),
                     ast.get_docstring(tree) or "", len(source.splitlines()),
                     classes, functions, constants)


def collect_modules() -> List[Tuple[str, str, List[ModuleDoc]]]:
    """Analyse tous les modules de l'application, couche par couche.

    :return: (titre de couche, description, modules).
    """
    result = []
    for title, description, patterns in LAYERS:
        modules: List[ModuleDoc] = []
        for pattern in patterns:
            if pattern.endswith("/"):
                files = sorted((ROOT / pattern).rglob("*.py"))
            else:
                files = [ROOT / pattern]
            for file_path in files:
                if file_path.name == "__init__.py" and file_path.stat().st_size < 120 \
                        and pattern.endswith("/"):
                    continue
                modules.append(extract_module(file_path))
        result.append((title, description, modules))
    return result


def collect_tests() -> List[Tuple[str, str, List[Tuple[str, str]]]]:
    """Inventorie les tests : (fichier, classe, [(test, docstring)]).

    :return: inventaire des tests.
    """
    inventory = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                tests = [(item.name, ast.get_docstring(item) or "") for item in node.body
                         if isinstance(item, ast.FunctionDef) and item.name.startswith("test_")]
                if tests:
                    inventory.append((path.name, node.name, tests))
    return inventory


def first_paragraph(doc: str) -> str:
    """Retourne le premier paragraphe d'une docstring.

    :param doc: docstring.
    :return: premier paragraphe sur une ligne.
    """
    return " ".join(doc.strip().split("\n\n")[0].split())


def _inline(text: str) -> str:
    """Échappe un texte de docstring et met en forme les ``littéraux``.

    :param text: texte brut.
    :return: balisage ReportLab.
    """
    result = escape(text)
    result = re.sub(r"``(.+?)``", r'<font name="DejaVuMono">\1</font>', result)
    return re.sub(r":(?:class|meth|func|attr):`~?(.+?)`", r'<font name="DejaVuMono">\1</font>',
                  result)


FIELD_LABELS: dict = {"param": "↳", "return": "⇒ retourne", "raise": "⚠ lève",
                      "raises": "⚠ lève"}


def doc_markup(doc: str) -> str:
    """Convertit une docstring (reST simplifié) en balisage lisible.

    Les champs ``:param x:``, ``:return:`` et ``:raises E:`` sont mis en forme ;
    leurs lignes de continuation sont rattachées au champ.

    :param doc: docstring.
    :return: balisage ReportLab.
    """
    blocks: List[str] = []
    current: List[str] = []
    in_field = False
    for raw in doc.strip().splitlines():
        line = raw.strip()
        match = re.match(r":(param|raises?|return)\s*([^:]*):\s*(.*)", line)
        if not line:
            if current:
                blocks.append(" ".join(current))
                current = []
            in_field = False
        elif match:
            if current:
                blocks.append(" ".join(current))
                current = []
            kind, name, text = match.groups()
            name_markup = (f' <font name="DejaVuMono">{escape(name.strip())}</font>'
                           if name.strip() else "")
            blocks.append(f"{FIELD_LABELS[kind]}{name_markup} : {_inline(text)}")
            in_field = True
        elif in_field and blocks:
            blocks[-1] += " " + _inline(line)
        elif line.startswith(("* ", "- ")):
            if current:
                blocks.append(" ".join(current))
            current = ["• " + _inline(line[2:])]
        else:
            current.append(_inline(line))
    if current:
        blocks.append(" ".join(current))
    return "<br/>".join(blocks)


# =================================================================== document
class DocTemplate(BaseDocTemplate):
    """Gabarit avec page de titre, en-têtes, sommaire et signets PDF."""

    def __init__(self, filename: str) -> None:
        """Prépare les gabarits de page.

        :param filename: fichier PDF produit.
        """
        super().__init__(filename, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=MARGIN + 0.3 * cm, bottomMargin=MARGIN,
                         title="LogWaver — Documentation technique du code",
                         author="LogWaver", subject=f"Version {__version__}")
        frame = Frame(MARGIN, MARGIN, CONTENT_WIDTH, PAGE_HEIGHT - 2 * MARGIN - 0.3 * cm,
                      id="normal")
        self.addPageTemplates([
            PageTemplate("cover", frames=[frame], onPage=self._cover),
            PageTemplate("content", frames=[frame], onPage=self._header_footer),
        ])
        self._chapter = ""

    def handle_documentBegin(self) -> None:  # noqa: N802
        """Réinitialise le titre courant à chaque passe de construction (API ReportLab)."""
        self._chapter = ""
        super().handle_documentBegin()

    def afterFlowable(self, flowable: object) -> None:  # noqa: N802
        """Alimente le sommaire et les signets à partir des titres (API ReportLab).

        :param flowable: élément venant d'être placé.
        """
        if not isinstance(flowable, Paragraph):
            return
        name = flowable.style.name
        if name not in ("H1", "H2", "Module"):
            return
        text = flowable.getPlainText()
        level = {"H1": 0, "H2": 1, "Module": 1}[name]
        key = f"h{abs(hash((text, self.page)))}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
        if name == "H1":
            self._chapter = text
        if name in ("H1", "H2"):
            self.notify("TOCEntry", (level, text, self.page, key))

    def _cover(self, canvas: object, _doc: object) -> None:
        """Dessine la page de titre.

        :param canvas: toile ReportLab.
        :param _doc: document (inutilisé).
        """
        c = canvas
        c.saveState()  # type: ignore[attr-defined]
        c.setFillColor(NAVY)  # type: ignore[attr-defined]
        c.rect(0, PAGE_HEIGHT - 9.5 * cm, PAGE_WIDTH, 9.5 * cm, fill=1, stroke=0)  # type: ignore
        c.setFillColor(GREEN)  # type: ignore[attr-defined]
        c.rect(0, PAGE_HEIGHT - 9.8 * cm, PAGE_WIDTH, 0.3 * cm, fill=1, stroke=0)  # type: ignore
        c.setFillColor(colors.white)  # type: ignore[attr-defined]
        c.setFont("DejaVu-Bold", 38)  # type: ignore[attr-defined]
        c.drawString(MARGIN, PAGE_HEIGHT - 4.6 * cm, "LogWaver")  # type: ignore
        c.setFont("DejaVu", 17)  # type: ignore[attr-defined]
        c.drawString(MARGIN, PAGE_HEIGHT - 6.0 * cm,  # type: ignore[attr-defined]
                     "Documentation technique complète du code")
        c.setFont("DejaVu", 11)  # type: ignore[attr-defined]
        c.drawString(MARGIN, PAGE_HEIGHT - 7.2 * cm,  # type: ignore[attr-defined]
                     f"Version {__version__}  ·  {date.today().strftime('%d/%m/%Y')}")
        c.setFillColor(GREY)  # type: ignore[attr-defined]
        c.setFont("DejaVu", 9)  # type: ignore[attr-defined]
        c.drawString(MARGIN, 1.6 * cm,  # type: ignore[attr-defined]
                     "Généré par tools/doc/generer_documentation_pdf.py "
                     "(référence extraite automatiquement des sources).")
        c.restoreState()  # type: ignore[attr-defined]

    def _header_footer(self, canvas: object, doc: object) -> None:
        """Dessine en-tête et pied de page.

        :param canvas: toile ReportLab.
        :param doc: document.
        """
        c = canvas
        c.saveState()  # type: ignore[attr-defined]
        c.setStrokeColor(colors.HexColor("#c9d1d9"))  # type: ignore[attr-defined]
        c.setLineWidth(0.5)  # type: ignore[attr-defined]
        top = PAGE_HEIGHT - MARGIN + 0.25 * cm
        c.line(MARGIN, top, PAGE_WIDTH - MARGIN, top)  # type: ignore[attr-defined]
        c.setFont("DejaVu", 7.5)  # type: ignore[attr-defined]
        c.setFillColor(GREY)  # type: ignore[attr-defined]
        c.drawString(MARGIN, top + 4,  # type: ignore[attr-defined]
                     f"LogWaver {__version__} — Documentation du code")
        c.drawRightString(PAGE_WIDTH - MARGIN, top + 4, self._chapter[:80])  # type: ignore
        c.line(MARGIN, MARGIN - 0.45 * cm, PAGE_WIDTH - MARGIN, MARGIN - 0.45 * cm)  # type: ignore
        c.drawRightString(PAGE_WIDTH - MARGIN, MARGIN - 0.8 * cm,  # type: ignore[attr-defined]
                          f"Page {doc.page}")  # type: ignore[attr-defined]
        c.restoreState()  # type: ignore[attr-defined]


def h1(text: str) -> List[object]:
    """Titre de chapitre sur une nouvelle page.

    :param text: titre.
    :return: éléments à insérer.
    """
    return [PageBreak(), Paragraph(code_markup(text), ST.h1)]


def h2(text: str) -> List[object]:
    """Titre de section (évite un titre orphelin en bas de page).

    :param text: titre.
    :return: éléments à insérer.
    """
    return [CondPageBreak(3 * cm), Paragraph(code_markup(text), ST.h2)]


def h3(text: str) -> Paragraph:
    """Titre de sous-section.

    :param text: titre.
    :return: paragraphe.
    """
    return Paragraph(code_markup(text), ST.h3)


# ===================================================================== contenu
def chapter_introduction(stats: dict) -> List[object]:
    """Chapitre 1 : présentation de l'application.

    :param stats: statistiques du code (modules, lignes, classes, tests).
    :return: éléments du chapitre.
    """
    story: List[object] = [Paragraph("1. Présentation", ST.h1)]
    story.append(p(
        "**LogWaver** lit le fichier de log de n'importe quel outil, en extrait les notes, "
        "warnings et erreurs, et permet de les **justifier** : chaque élément est classé dans "
        "une catégorie (À traiter, Justifié, Rejeté…) avec un texte explicatif signé par son "
        "auteur. Le cœur de l'outil est le **suivi** : les justifications sont réappliquées "
        "automatiquement aux logs suivants et peuvent être transmises à un autre concepteur, "
        "qui ne garde alors que les éléments réellement nouveaux."))
    story.append(p("Ce document explique l'intégralité du code de la version "
                   f"**{__version__}** : son architecture, ses mécanismes, ses formats de "
                   "fichiers, sa démarche qualité, puis, au chapitre 9, chaque module, classe et "
                   "méthode, extraits automatiquement des sources."))
    story += h2("1.1 Fonctionnalités")
    story += bullets([
        "**Plugins** décrivant le format de log d'un outil (regex de détection et d'extraction), "
        "choisis automatiquement par extension de fichier ou par contenu.",
        "**Justification** d'un élément, d'une sélection ou d'un **groupe** entier (même code, "
        "même fichier, même message…), avec nom de l'auteur demandé une seule fois.",
        "**Annuler / Rétablir** (Ctrl+Z / Ctrl+Y) de toute modification des justifications.",
        "**Projet** (`.lwp`) et **fichier de justifications** (`.lwj`) réutilisables ; "
        "**priorités** entre catégories lors des imports ; **règles de correspondance** "
        "réglables pour retrouver une justification malgré des différences.",
        "**Aide IA** : génération de prompts, lecture de la réponse, justification en un clic.",
        "**Documentation PDF** de l'outil ouverte à la page du code ; fichier **source** ouvert "
        "à la ligne concernée.",
        "**Éditeur de plugin** avec testeur de regex et **assistant pas à pas** qui écrit les "
        "regex à partir de sélections à la souris.",
        "**Exports** Excel et Word ; page d'accueil, bandeau « À faire » et **didacticiel**.",
    ])
    story += h2("1.2 Le code en chiffres")
    story.append(table([
        ["Mesure", "Valeur"],
        ["Fichiers Python de l'application", str(stats["modules"])],
        ["Lignes de code (application)", str(stats["lines"])],
        ["Classes / fonctions et méthodes documentées",
         f"{stats['classes']} / {stats['functions']}"],
        ["Tests automatisés", str(stats["tests"])],
        ["Bibliothèques tierces", "PyQt5, PyQtWebEngine, numpy, python-docx (exclusivement)"],
    ], [3, 2]))
    story.append(Spacer(1, 8))
    story.append(screenshot("03_liste_details", "Figure 1 — Fenêtre principale : catégories, "
                            "liste des éléments, détails et actions."))
    return story


def chapter_installation() -> List[object]:
    """Chapitre 2 : installation et exécution.

    :return: éléments du chapitre.
    """
    story: List[object] = h1("2. Installation et exécution")
    story.append(p("Prérequis : Python 3.8 ou plus récent."))
    story.append(code_block("""
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\\Scripts\\activate
pip install -r requirements.txt    # PyQt5, PyQtWebEngine, numpy, python-docx

python main.py                     # page d'accueil
python main.py --log build.log     # plugin détecté automatiquement
python main.py --project mon_projet.lwp --log nouveau_build.log
python -m unittest discover -s tests -t .
"""))
    story.append(table([
        ["Option", "Rôle"],
        ["`--config`", "fichier de configuration (défaut : `config/app_config.ini`)"],
        ["`--plugin`", "impose un plugin (sinon détection automatique)"],
        ["`--log`", "log à ouvrir (option répétable)"],
        ["`--project`", "projet à ouvrir"],
        ["`--debug`", "journalisation détaillée"],
    ], [1, 3]))
    story.append(Spacer(1, 6))
    story.append(p("`main.py` assemble les trois couches : il charge la configuration "
                   "(`AppConfigLoader`), crée la session métier (`WaverSession`), la fenêtre "
                   "(`MainWindow`) et le présentateur (`MainPresenter`) en lui injectant le "
                   "fournisseur d'IA (`TerminalPromptProvider` par défaut), les préférences "
                   "(`UserPreferences`) et les chemins des ressources (`ApplicationPaths`). "
                   "Le module `pdf_viewer_dialog` est importé **avant** la création de "
                   "`QApplication`, contrainte imposée par QtWebEngine. Le journal est écrit "
                   "dans la console et dans `~/.logwaver/logwaver.log` (fichier tournant)."))
    return story


def chapter_architecture() -> List[object]:
    """Chapitre 3 : architecture générale.

    :return: éléments du chapitre.
    """
    story: List[object] = h1("3. Architecture générale")
    story.append(p(
        "L'application applique le patron **MVP « Passive View »** (Modèle – Vue – "
        "Présentateur). Le modèle contient toute la logique métier en Python pur ; les vues "
        "ne font qu'afficher et émettre des signaux ; les présentateurs relient les deux."))
    story.append(architecture_diagram())
    story.append(p("Figure 2 — Les trois couches et leurs échanges.", ST.caption))
    story += h2("3.1 Règles de dépendance")
    story.append(table([
        ["Couche", "Peut utiliser", "Ne doit jamais utiliser"],
        ["Modèle (`logwaver/model`)", "bibliothèque standard, numpy, python-docx",
         "PyQt5, vues, présentateurs (vérifié par la CI)"],
        ["Présentateurs (`logwaver/presenter`)", "modèle, DTO (`view_models.py`), vues "
         "(uniquement pour le typage)", "widgets Qt directement"],
        ["Vues (`logwaver/view`)", "PyQt5, DTO", "modèle"],
        ["DTO (`view_models.py`)", "bibliothèque standard", "tout le reste"],
    ], [1.3, 1.6, 1.6]))
    story.append(Spacer(1, 6))
    story += bullets([
        "**Modèle → présentateur** : par événements (`EventHub` : `entries_changed`, "
        "`justifications_changed`, `project_changed`, `history_changed`). Le modèle ne connaît "
        "pas ses observateurs.",
        "**Vue → présentateur** : par signaux Qt (`classify_requested`, `grouping_changed`…). "
        "Une vue n'appelle jamais le modèle.",
        "**Présentateur → vue** : par des méthodes d'affichage recevant des **DTO immuables** "
        "(`EntryRow`, `EntryDetails`, `ActionsState`…).",
        "**Erreurs** : le modèle lève des exceptions typées (`LogWaverError` et dérivées) ; "
        "chaque gestionnaire d'action est décoré par `@guarded`, qui journalise et affiche un "
        "message clair sans interrompre l'application.",
        "**Style** : exclusivement dans `resources/styles/main.qss` (objectName et propriétés "
        "dynamiques `role`, `state`, `tutorialTarget`).",
    ])
    story += h2("3.2 Arborescence")
    story.append(code_block("""
main.py                      point d'entrée (composition MVP)
config/app_config.ini        catégories, priorités, correspondance, éditeur, IA
plugins/                     plugins INI, index PDF, documentation d'exemple
resources/styles/main.qss    style visuel
resources/tutorial/          contenu du didacticiel (INI)
samples/                     logs des concepteurs A et B, sources d'exemple
tests/                       tests unitaires et d'interface (unittest)
tools/doc/                   génération de cette documentation
logwaver/
  constants.py  logging_setup.py  view_models.py
  model/        session, entités, plugin, analyse, empreintes, index,
                annulation, projets, regroupement, statistiques, IA,
                regex, didacticiel, exporters/ (xlsx, Excel, Word)
  presenter/    main, tutoriel, aide IA, éditeur de plugin,
                assistant regex, règles de correspondance, gestion d'erreurs
  view/         main_window, entry_tree_model, style_loader,
                widgets/ (arbre, filtres, catégories, détails, accueil, didacticiel)
                dialogs/ (justifier, IA, éditeur, assistant, règles, sources, PDF)
"""))
    return story


def chapter_model() -> List[object]:
    """Chapitre 4 : les mécanismes du modèle.

    :return: éléments du chapitre.
    """
    story: List[object] = h1("4. Le modèle métier")
    story.append(p("`WaverSession` (`model/session.py`) est la **façade** du modèle : le "
                   "présentateur ne manipule qu'elle. Elle orchestre plugin, logs, "
                   "justifications, historique, projets et exports, et publie des événements."))
    story += h2("4.1 Entités")
    story.append(table([
        ["Entité", "Rôle", "Points clés"],
        ["`LogEntry`", "élément extrait d'un log", "immuable ; champs extraits, ligne brute, log "
         "et ligne d'origine, **empreinte** de comparaison"],
        ["`Justification`", "décision sur un élément", "catégorie, texte, auteur, date, origine "
         "(manuelle, ia, importée), **contexte complet** de l'élément, identifiant strict"],
        ["`StatusDefinition`", "catégorie configurée", "libellé, description, couleur, "
         "**priorité**"],
        ["`PluginDefinition`", "format de log d'un outil", "types d'éléments, regex, extensions, "
         "documentation PDF"],
    ], [1.2, 1.4, 3]))
    story += h2("4.2 Des lignes de log aux éléments")
    story += bullets([
        "`PluginLoader` lit le fichier INI (sans interpolation, clés sensibles à la casse) et "
        "**compile toutes les regex dès le chargement** : une erreur est signalée avec le type et "
        "le champ concernés.",
        "`LogParser` lit le log (UTF-8, repli Latin-1) ; pour chaque ligne, le **premier type** "
        "dont la regex `detect` correspond l'emporte, puis chaque champ est extrait : groupe "
        "nommé `value`, sinon premier groupe capturant, sinon correspondance complète "
        "(`extract_with_pattern`).",
        "`PluginDetector` choisit le plugin : extension déclarée (`file_extensions`), sauf si ses "
        "plugins ne reconnaissent rien alors qu'un autre reconnaît le contenu ; sinon le plugin "
        "reconnaissant le plus de lignes. `PluginExtensionRegistrar` mémorise une extension en "
        "ne modifiant que la ligne `file_extensions`.",
    ])
    story += h2("4.3 Empreintes, index et priorités")
    story.append(p(
        "Retrouver une justification revient à comparer deux éléments. `FingerprintBuilder` "
        "calcule une **empreinte** (SHA-1 tronqué) à partir des attributs choisis dans les "
        "**règles de correspondance** (`MatchingOptions`), après application des tolérances : "
        "espaces, casse, et, dans la description, texte entre guillemets, chemins et nombres "
        "remplacés par `‹…›`."))
    story.append(index_diagram())
    story.append(p("Figure 3 — Une justification s'applique à un élément si leurs empreintes, "
                   "calculées avec les mêmes règles, sont égales.", ST.caption))
    story += bullets([
        "Chaque justification est stockée sous un **identifiant strict** (tous les attributs, "
        "sans tolérance) avec le **contexte brut** de l'élément justifié "
        "(`FingerprintBuilder.raw_context`).",
        "`JustificationIndex` recalcule à la volée la clé de chaque justification selon les "
        "règles courantes ; si plusieurs partagent une clé, la **plus prioritaire** l'emporte, "
        "puis la **plus récente** (`rank`).",
        "Changer de règles (`set_matching_options`) ne supprime **rien** : seules les "
        "associations sont recalculées ; revenir aux règles précédentes restaure l'état exact. "
        "`preview_matching` calcule l'effet d'un réglage sans rien modifier.",
        "**Import** (`import_rules`) : pour chaque justification reçue, si l'élément n'est pas "
        "justifié elle est ajoutée ; si la catégorie reçue est **plus prioritaire**, elle "
        "remplace l'existante ; sinon elle est écartée. Le tout est une seule commande "
        "annulable.",
    ])
    story += h2("4.4 Annulation et événements")
    story.append(p(
        "Toute modification des justifications passe par une **unique commande** : "
        "`ChangeJustificationsCommand` reçoit un lot « identifiant → nouvelle justification ou "
        "`None` », mémorise l'état précédent et sait l'appliquer ou le restaurer. Classer, "
        "retirer, classer en masse, importer : tout est donc annulable de la même façon. "
        "`UndoStack` gère l'historique, sa limite et un repère « enregistré » qui alimente "
        "l'indicateur de modifications non enregistrées (`*` dans le titre). À chaque "
        "changement, la session reconstruit l'index puis publie ses événements."))
    story += h2("4.5 Regroupement, filtres et statistiques")
    story += bullets([
        "`EntryFilter` applique catégorie, type, code, fichier et texte libre "
        "(insensible à la casse, recherche aussi dans la justification et l'auteur).",
        "`EntryGrouper` regroupe par code, fichier (chemin ou nom seul), description "
        "identique, type, catégorie, auteur, log ou **tout champ propre au plugin** ; les "
        "groupes les plus grands viennent en premier.",
        "`StatisticsCalculator` construit avec **numpy** le tableau croisé types × catégories "
        "utilisé par les compteurs, la barre d'état et les exports.",
    ])
    story += h2("4.6 Assistant regex : génération fondée sur l'invariant")
    story.append(p(
        "`RegexGenerator.generate` reçoit une ligne d'exemple, les zones des **éléments à "
        "extraire** et celles des **parties variables sans intérêt**. Tout le reste est "
        "considéré comme **invariant** : il est échappé tel quel (seuls les espaces deviennent "
        "`\\s+`). Chaque zone sélectionnée devient `.+?` (ou `.+` en fin de ligne) : sa valeur "
        "peut donc changer complètement. La regex de détection et une regex par champ (le champ "
        "visé en groupe capturant) sont produites, ancrées de `^` à `\\s*$`, puis **vérifiées** "
        "sur la ligne. `suggest_variable_parts` propose les dates et nombres restés dans le "
        "texte fixe ; `apply` évalue le résultat sur tout l'exemple."))
    story.append(code_block("""
Ligne  : [2026-11-20 10:01:02] WARNING CL245 src/io/loader.c:42 - le fichier dada.txt
         est introuvable
Modèle : [‹…›] WARNING ‹Code› ‹Fichier›:‹Ligne› - ‹Description›
detect      = ^\\[(?:.+?)\\]\\s+WARNING\\s+(?:.+?)\\s+(?:.+?):(?:.+?)\\s+\\-\\s+(?:.+)\\s*$
regex.code  = ^\\[(?:.+?)\\]\\s+WARNING\\s+(.+?)\\s+(?:.+?):(?:.+?)\\s+\\-\\s+(?:.+)\\s*$
"""))
    story += h2("4.7 Projets, exports et IA")
    story += bullets([
        "`ProjectStore` lit et écrit les fichiers `.lwp` / `.lwj` en JSON, de façon **atomique** "
        "(fichier temporaire puis remplacement), avec chemins relatifs au projet et contrôle "
        "du format et de sa version (v2, lecture des v1).",
        "`XlsxWriter` produit un classeur Office Open XML **avec la seule bibliothèque standard** "
        "(feuilles, en-tête figé, filtres, largeurs) ; `ExcelReportExporter` y écrit synthèse, "
        "éléments et justifications ; `DocxReportExporter` produit un rapport Word.",
        "`PromptBuilder` génère un prompt imposant une réponse structurée (EXPLICATION, ANALYSE, "
        "STATUT, JUSTIFICATION) ; `AiResponseParser` la découpe ; `AiProvider` est l'interface à "
        "implémenter pour brancher une IA (`TerminalPromptProvider` affiche le prompt).",
        "`DocumentationLocator` / `PdfPageIndex` associent un code à une page du PDF de l'outil ; "
        "`SourceFileReader` et `ExternalEditorLauncher` ouvrent le fichier source cité.",
    ])
    return story


def chapter_flows() -> List[object]:
    """Chapitre 5 : déroulé des principaux scénarios.

    :return: éléments du chapitre.
    """
    story: List[object] = h1("5. Les flux principaux")
    palette = (BLUE, ORANGE, GREEN, NAVY)
    flows = (
        ("5.1 Ouvrir un log", (
            ("MainWindow", "signal open_log_requested (bouton, menu ou page d'accueil)"),
            ("MainPresenter", "_on_open_log → ask_open_file → _open_log_file(chemin)"),
            ("PluginDetector", "detect : extension déclarée puis contenu ; sinon choix manuel"),
            ("WaverSession", "load_plugin (si besoin) puis open_log"),
            ("LogParser", "parse_file : détection du type, extraction des champs, empreinte"),
            ("JustificationIndex", "best(empreinte) : justifications réappliquées"),
            ("EventHub", "entries_changed, project_changed"),
            ("MainPresenter", "_refresh_entries : catégories, arbre, bandeau « À faire »"),
        )),
        ("5.2 Justifier une sélection ou un groupe", (
            ("EntryTree", "sélection : un groupe sélectionné = tous ses éléments"),
            ("MainPresenter", "_on_classify : nom demandé une fois, dialogue « Justifier »"),
            ("WaverSession", "classify : remplace les justifications de chaque clé"),
            ("UndoStack", "push(ChangeJustificationsCommand) → execute"),
            ("JustificationIndex", "rebuild (via _on_history_changed)"),
            ("EventHub", "justifications_changed, history_changed, project_changed"),
            ("MainWindow", "éléments retirés de « Non justifiés », compteurs à jour"),
        )),
        ("5.3 Importer les justifications d'un collègue", (
            ("MainPresenter", "_on_import_rules → fichier .lwj ou .lwp"),
            ("ProjectStore", "load_rules : lecture et validation du JSON"),
            ("WaverSession", "import_rules : ajout, remplacement si plus prioritaire, ou rejet"),
            ("UndoStack", "une seule commande annulable"),
            ("MainWindow", "bilan : ajoutées / remplacées / écartées"),
        )),
        ("5.4 Créer des regex avec l'assistant", (
            ("PluginEditorDialog", "wizard_requested"),
            ("RegexWizardPresenter", "étapes : type → ligne → éléments et parties ignorées"),
            ("RegexGenerator", "generate (invariant), suggest_variable_parts, apply"),
            ("RegexWizardDialog", "vérification sur tout l'exemple, puis « Utiliser ces regex »"),
            ("PluginEditorPresenter", "select_or_create_type + apply_generated, enregistrement"),
        )),
        ("5.5 Régler les règles de correspondance", (
            ("MainWindow", "Édition > Règles de correspondance (Ctrl+M)"),
            ("MatchingRulesPresenter", "préréglage ou cases → MatchingOptions"),
            ("WaverSession", "preview_matching : éléments gagnés / perdus (sans modification)"),
            ("MatchingRulesDialog", "aperçu immédiat ; « Appliquer ces règles »"),
            ("WaverSession", "set_matching_options : empreintes et index recalculés"),
        )),
    )
    for title, steps in flows:
        story += h2(title)
        story.append(chain_diagram(steps, palette))
        story.append(Spacer(1, 6))
    story += h2("5.6 Autres scénarios")
    story += bullets([
        "**Aide IA** : `MainPresenter._on_ai_help` construit le prompt (`PromptBuilder`), "
        "l'envoie au fournisseur, ouvre `AiHelpDialog` piloté par `AiAssistantPresenter` ; "
        "la justification proposée est appliquée par `classify(…, SOURCE_AI)`.",
        "**Projet** : `save_project` / `open_project` (plugin, logs, utilisateur, "
        "justifications, règles) ; les fichiers manquants sont signalés sans bloquer.",
        "**Didacticiel** : `TutorialLoader` lit `didacticiel.ini`, `TutorialPresenter` fait "
        "défiler les étapes, met en évidence le widget ciblé (propriété QSS "
        "`tutorialTarget`) et exécute les actions « Montre-moi » fournies par "
        "`MainPresenter._tutorial_actions`.",
        "**Fermeture** : `MainWindow.closeEvent` consulte le présentateur (`_can_close`), qui "
        "propose d'enregistrer les modifications.",
    ])
    return story


def chapter_interface() -> List[object]:
    """Chapitre 6 : l'interface utilisateur.

    :return: éléments du chapitre.
    """
    story: List[object] = h1("6. L'interface utilisateur")
    story.append(p("Toutes les vues reposent sur des layouts (aucun positionnement absolu) et "
                   "leur apparence est entièrement définie dans `main.qss`."))
    shots = (
        ("01_accueil", "Page d'accueil (`WelcomePage`) : trois étapes et actions de démarrage."),
        ("02_liste_groupee", "Arbre regroupé par code (`EntryTree`, `EntryTreeModel`) : un groupe "
         "sélectionné est justifié en entier."),
        ("06_didacticiel", "Didacticiel (`TutorialPanel`) : l'élément expliqué est encadré."),
        ("04_justifier", "Fenêtre « Justifier » (`JustificationDialog`)."),
        ("05_aide_ia", "Aide IA (`AiHelpDialog`) : prompt, réponse, proposition."),
        ("07_editeur_plugin", "Éditeur de plugin (`PluginEditorDialog`)."),
        ("08_assistant_elements", "Assistant regex, étape 3 : éléments et parties ignorées."),
        ("09_assistant_verification", "Assistant regex, étape 4 : vérification sur l'exemple."),
        ("10_regles_correspondance", "Règles de correspondance (`MatchingRulesDialog`) avec "
         "aperçu."),
    )
    for index, (name, caption) in enumerate(shots, start=4):
        width = CONTENT_WIDTH if not name.startswith(("04", "05")) else CONTENT_WIDTH * 0.72
        story.append(screenshot(name, f"Figure {index} — {caption}", width))
    story += h2("6.1 Correspondance vues / présentateurs")
    story.append(table([
        ["Vue", "Présentateur", "Rôle"],
        ["`MainWindow` + widgets", "`MainPresenter`", "fenêtre principale, menus, actions"],
        ["`TutorialPanel`", "`TutorialPresenter`", "didacticiel"],
        ["`AiHelpDialog`", "`AiAssistantPresenter`", "aide IA"],
        ["`PluginEditorDialog`", "`PluginEditorPresenter`", "création / modification de plugin"],
        ["`RegexWizardDialog`", "`RegexWizardPresenter`", "assistant regex"],
        ["`MatchingRulesDialog`", "`MatchingRulesPresenter`", "règles de correspondance"],
        ["`JustificationDialog`, `SourceViewerDialog`, `PdfViewerDialog`", "`MainPresenter`",
         "dialogues simples"],
    ], [2.2, 1.6, 1.6]))
    return story


def chapter_formats() -> List[object]:
    """Chapitre 7 : formats de fichiers.

    :return: éléments du chapitre.
    """
    story: List[object] = h1("7. Formats de fichiers")
    story += h2("7.1 Plugin (`plugins/<outil>.ini`)")
    story.append(code_block((ROOT / "plugins" / "tintin.ini").read_text(encoding="utf-8")))
    story += h2("7.2 Configuration (`config/app_config.ini`)")
    story.append(p("Catégories (ordre, libellé, description, couleur, **priorité**), catégorie "
                   "par défaut, règles de correspondance par défaut (`[matching]`), commande "
                   "d'éditeur externe (`{file}`, `{line}`) et langue des prompts."))
    story.append(code_block((ROOT / "config" / "app_config.ini").read_text(encoding="utf-8")))
    story += h2("7.3 Projet (`.lwp`) et justifications (`.lwj`) — JSON, format v2")
    story.append(code_block("""
{
  "format": "logwaver-project",          // ou "logwaver-justifications"
  "version": 2,
  "application_version": "1.2.0",
  "plugin_path": "../plugins/tintin.ini", // chemins relatifs au projet
  "log_paths": ["build.log"],
  "user_name": "Alice",
  "matching": {"keys": ["tool", "type", "code", "description", "file_name"],
               "mask_numbers": false, "mask_quoted": false, "mask_paths": false, ...},
  "justifications": [{
    "fingerprint": "identifiant strict", "status_id": "justified",
    "text": "Fichier optionnel", "author": "Alice",
    "timestamp": "2026-11-22T12:00:00", "source": "manuelle",
    "context": {"tool": "TINTIN", "type": "Warning", "code": "CL245",
                "description": "...", "file_name": "loader.c",
                "file_path": "src/io/loader.c", "line": "42"}}]
}
"""))
    story += h2("7.4 Autres fichiers")
    story.append(table([
        ["Fichier", "Contenu"],
        ["`plugins/<outil>_pdf_index.ini`", "section `[pages]` : code = page, `default_page`"],
        ["`resources/tutorial/didacticiel.ini`",
         "étapes : titre, texte HTML simple, widget ciblé, "
         "action « Montre-moi »"],
        ["`~/.logwaver/preferences.json`", "dernier utilisateur, didacticiel déjà proposé"],
        ["Export `.xlsx`", "feuilles Synthèse, Éléments, Justifications"],
        ["Export `.docx`", "synthèse, éléments non justifiés, éléments classés"],
    ], [1.6, 3]))
    return story


def chapter_quality(tests: List[Tuple[str, str, List[Tuple[str, str]]]]) -> List[object]:
    """Chapitre 8 : qualité, tests et gestion de configuration.

    :param tests: inventaire des tests.
    :return: éléments du chapitre.
    """
    story: List[object] = h1("8. Qualité, tests et gestion de configuration")
    story += h2("8.1 Normes de codage")
    story += bullets([
        "PEP 8 (lignes de 99 caractères), `snake_case`, `PascalCase`, `UPPER_CASE` — vérifié "
        "par `pycodestyle` ; analyse statique par `pyflakes`.",
        "Annotations de type sur toutes les signatures et docstring (rôle, paramètres, retour) "
        "sur chaque classe et méthode : la référence du chapitre 9 en est directement issue.",
        "Encapsulation : attributs internes préfixés `_`, entités immuables (`frozen` "
        "dataclasses), DTO immuables entre présentateurs et vues.",
    ])
    story += h2("8.2 Tests automatisés")
    rows = [["Fichier", "Classe", "Test", "Vérifie"]]
    for file_name, class_name, items in tests:
        for name, doc in items:
            rows.append([f"`{file_name}`", class_name, f"`{name}`", first_paragraph(doc)])
    story.append(table(rows, [1.3, 1.3, 1.9, 2.6]))
    story += h2("8.3 Intégration continue et gestion de configuration")
    story += bullets([
        "GitHub Actions (`.github/workflows/ci.yml`) : style, analyse statique, contrôle "
        "« le modèle n'importe pas PyQt5 », tests sur Linux et Windows, Python 3.8 / 3.10 / "
        "3.12 ; publication d'une version GitHub pour chaque étiquette `vX.Y.Z`.",
        "Versionnage sémantique ; source unique `logwaver/__init__.py` ; un test vérifie la "
        "concordance avec `CHANGELOG.md`.",
        "Branches `main` (livrées), `develop` (intégration), `feature/*`, `fix/*`, `hotfix/*` ; "
        "commits conventionnels ; modèles d'issue et de pull request.",
        "Plan complet : `docs/GESTION_DE_CONFIGURATION.md` ; historique de conception : "
        "`docs/conception/HISTORIQUE_CONCEPTION.md`.",
    ])
    return story


def chapter_reference(layers: List[Tuple[str, str, List[ModuleDoc]]]) -> List[object]:
    """Chapitre 9 : référence complète extraite du code.

    :param layers: modules par couche.
    :return: éléments du chapitre.
    """
    story: List[object] = h1("9. Référence complète du code")
    story.append(p(
        "Ce chapitre est **généré automatiquement** à partir des sources : chaque module, "
        "classe, fonction et méthode y figure avec sa signature exacte et sa docstring. Les "
        "symboles : ↳ paramètre, ⇒ valeur retournée, ⚠ exception levée."))
    for number, (title, description, modules) in enumerate(layers, start=1):
        story += h2(f"9.{number} {title}")
        story.append(p(description))
        for module in modules:
            story.append(CondPageBreak(4 * cm))
            story.append(Paragraph(f"{escape(module.path)}   ({module.lines} lignes)", ST.module))
            if module.doc:
                story.append(Paragraph(doc_markup(module.doc), ST.body))
            if module.constants:
                story.append(Paragraph(
                    "<b>Constantes :</b> " + ", ".join(
                        f'<font name="DejaVuMono" size="7.6">{escape(c)}</font>'
                        for c in module.constants), ST.docstring))
            for function in module.functions:
                story += function_flowables(function, "")
            for klass in module.classes:
                bases = f"({klass.bases})" if klass.bases else ""
                kind = "dataclass " if klass.is_dataclass else ""
                story.append(Paragraph(f"{kind}class {escape(klass.name)}{escape(bases)}",
                                       ST.klass))
                if klass.doc:
                    story.append(Paragraph(doc_markup(klass.doc), ST.docstring))
                if klass.is_dataclass and klass.attributes:
                    story.append(Paragraph(
                        "<b>Attributs :</b> " + "; ".join(
                            f'<font name="DejaVuMono" size="7.4">{escape(a)}</font>'
                            for a in klass.attributes), ST.docstring))
                for method in klass.methods:
                    story += function_flowables(method, klass.name)
    return story


def function_flowables(function: FunctionDoc, owner: str) -> List[object]:
    """Met en page une fonction ou une méthode.

    :param function: fonction extraite.
    :param owner: classe propriétaire (vide pour une fonction de module).
    :return: éléments à insérer.
    """
    prefix = ""
    if function.is_property:
        prefix = "@property  "
    elif "staticmethod" in function.decorators:
        prefix = "@staticmethod  "
    elif "classmethod" in function.decorators:
        prefix = "@classmethod  "
    elif any(d.endswith(".setter") for d in function.decorators):
        prefix = "@setter  "
    elif "guarded" in function.decorators:
        prefix = "@guarded  "
    signature = escape(prefix + ("def " if not owner else "") + function.signature)
    items: List[object] = [Paragraph(signature, ST.signature)]
    if function.doc:
        items.append(Paragraph(doc_markup(function.doc), ST.docstring))
    return [KeepTogether(items)]


def chapter_glossary() -> List[object]:
    """Annexe : glossaire.

    :return: éléments de l'annexe.
    """
    story: List[object] = h1("Annexe — Glossaire")
    story.append(table([
        ["Terme", "Définition"],
        ["Élément", "note, warning ou erreur extrait d'une ligne de log"],
        ["Plugin", "fichier INI décrivant le format de log d'un outil"],
        ["Justification", "catégorie + texte + auteur associés à un élément"],
        ["Catégorie", "classement configurable (À traiter, Justifié, Rejeté…) avec une priorité"],
        ["Empreinte", "valeur calculée pour comparer deux éléments selon les règles de "
         "correspondance"],
        ["Règles de correspondance", "attributs qui doivent être identiques et tolérances "
         "appliquées pour retrouver une justification"],
        ["Identifiant strict", "empreinte « tout identique » servant d'identifiant stable à une "
         "justification"],
        ["Invariant", "texte d'une ligne d'exemple non sélectionné dans l'assistant regex : "
         "repère fixe des regex"],
        ["DTO", "objet de transfert immuable entre présentateur et vue"],
        ["MVP", "Modèle – Vue – Présentateur (variante « Passive View »)"],
    ], [1.3, 3.5]))
    return story


def compute_stats(layers: List[Tuple[str, str, List[ModuleDoc]]],
                  tests: List[Tuple[str, str, List[Tuple[str, str]]]]) -> dict:
    """Calcule les chiffres clés du code.

    :param layers: modules par couche.
    :param tests: inventaire des tests.
    :return: statistiques.
    """
    modules = [m for _, _, mods in layers for m in mods]
    return {
        "modules": len(modules),
        "lines": sum(m.lines for m in modules),
        "classes": sum(len(m.classes) for m in modules),
        "functions": sum(len(m.functions) + sum(len(c.methods) for c in m.classes)
                         for m in modules),
        "tests": sum(len(items) for _, _, items in tests),
    }


def build() -> Path:
    """Assemble et écrit le PDF.

    :return: fichier produit.
    """
    register_fonts()
    layers = collect_modules()
    tests = collect_tests()
    stats = compute_stats(layers, tests)
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOC1", fontName="DejaVu-Bold", fontSize=10.5, leading=15, leftIndent=0),
        ParagraphStyle("TOC2", fontName="DejaVu", fontSize=9, leading=12, leftIndent=16),
    ]
    story: List[object] = [NextPageTemplate("content"), PageBreak(),
                           Paragraph("Sommaire", ST.h1), toc, PageBreak()]
    story += chapter_introduction(stats)
    story += chapter_installation()
    story += chapter_architecture()
    story += chapter_model()
    story += chapter_flows()
    story += chapter_interface()
    story += chapter_formats()
    story += chapter_quality(tests)
    story += chapter_reference(layers)
    story += chapter_glossary()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DocTemplate(str(OUTPUT)).multiBuild(story)
    print(f"PDF généré : {OUTPUT} — {stats}")
    return OUTPUT


if __name__ == "__main__":
    build()
