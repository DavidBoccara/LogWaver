"""Présentateur de l'assistant regex pas à pas."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, List, Optional, Sequence, Tuple

from logwaver.constants import FIELD_LABELS
from logwaver.model.exceptions import RegexGenerationError
from logwaver.model.regex_tools import GeneratedRegexes, RegexGenerator
from logwaver.presenter.error_handling import guarded
from logwaver.view_models import WizardCheckRow, WizardMarkView

if TYPE_CHECKING:
    from logwaver.view.dialogs.regex_wizard_dialog import RegexWizardDialog

LOGGER = logging.getLogger(__name__)

IGNORED_LABEL: str = "Partie variable ignorée"
IGNORED_TOKEN: str = "‹…›"
Mark = Tuple[str, int, int]  # (champ ou "" pour une partie ignorée, début, fin)


@dataclass(frozen=True)
class WizardResult:
    """Regex validées par l'utilisateur à la fin de l'assistant.

    :param type_name: type d'élément concerné.
    :param regexes: regex de détection et de champs.
    """

    type_name: str
    regexes: GeneratedRegexes


class RegexWizardPresenter:
    """Gère les sélections, la génération et la vérification des regex."""

    def __init__(
        self,
        dialog: "RegexWizardDialog",
        sample_lines: Sequence[str],
        field_names_of: Callable[[str], List[str]],
        load_sample: Callable[[], Optional[List[str]]],
    ) -> None:
        """Relie l'assistant à ses données.

        :param dialog: vue pilotée.
        :param sample_lines: lignes d'exemple disponibles.
        :param field_names_of: champs déjà déclarés pour un type.
        :param load_sample: demande un log d'exemple (``None`` si annulé).
        """
        self._dialog = dialog
        self._lines: List[str] = list(sample_lines)
        self._field_names_of = field_names_of
        self._load_sample = load_sample
        self._generator = RegexGenerator()
        self._line: str = ""
        self._marks: List[Mark] = []
        self._result: Optional[GeneratedRegexes] = None
        dialog.type_chosen.connect(self._on_type_chosen)
        dialog.line_chosen.connect(self._on_line_chosen)
        dialog.mark_requested.connect(self._on_mark)
        dialog.remove_mark_requested.connect(self._on_remove)
        dialog.suggest_requested.connect(self._on_suggest)
        dialog.check_requested.connect(self._on_check)
        dialog.load_sample_requested.connect(self._on_load_sample)
        dialog.set_sample_lines(self._lines)

    def run(self) -> Optional[WizardResult]:
        """Affiche l'assistant (modal).

        :return: regex validées, ou ``None`` si l'assistant est annulé.
        """
        accepted = self._dialog.exec_()
        if not accepted or self._result is None:
            return None
        return WizardResult(self._dialog.type_name(), self._result)

    def _report_error(self, message: str) -> None:
        """Affiche une erreur à l'étape de vérification (utilisé par ``guarded``).

        :param message: texte de l'erreur.
        """
        self._dialog.show_check("", (), (), "", message)

    # ============================================================ étapes
    @guarded
    def _on_type_chosen(self, type_name: str) -> None:
        """Propose les champs déjà connus du type choisi.

        :param type_name: type d'élément.
        """
        self._dialog.set_field_names(self._field_names_of(type_name))

    @guarded
    def _on_load_sample(self) -> None:
        """Remplace les lignes d'exemple par celles d'un log choisi."""
        lines = self._load_sample()
        if lines is not None:
            self._lines = lines
            self._dialog.set_sample_lines(lines)

    @guarded
    def _on_line_chosen(self, line: str) -> None:
        """Repart de zéro sur une nouvelle ligne d'exemple.

        :param line: ligne choisie.
        """
        self._line = line
        self._marks.clear()
        self._refresh_marks()

    @guarded
    def _on_mark(self, name: str, start: int, end: int) -> None:
        """Ajoute une sélection (un champ ne peut être marqué qu'une fois).

        Les espaces aux extrémités sont retirés ; une sélection qui en chevauche
        d'autres les remplace.

        :param name: champ visé (vide = partie variable ignorée).
        :param start: début de la sélection.
        :param end: fin de la sélection.
        """
        while start < end and self._line[start].isspace():
            start += 1
        while end > start and self._line[end - 1].isspace():
            end -= 1
        if start >= end:
            return
        self._marks = [mark for mark in self._marks
                       if not (mark[1] < end and start < mark[2])
                       and not (name and mark[0] == name)]
        self._marks.append((name, start, end))
        self._marks.sort(key=lambda mark: mark[1])
        self._refresh_marks()

    @guarded
    def _on_remove(self, index: int) -> None:
        """Supprime une sélection.

        :param index: position dans la liste affichée.
        """
        if 0 <= index < len(self._marks):
            del self._marks[index]
            self._refresh_marks()

    @guarded
    def _on_suggest(self) -> None:
        """Marque comme ignorés les nombres, dates et heures du texte fixe."""
        taken = [(start, end) for _, start, end in self._marks]
        for start, end in self._generator.suggest_variable_parts(self._line, taken):
            self._marks.append(("", start, end))
        self._marks.sort(key=lambda mark: mark[1])
        self._refresh_marks()

    @guarded
    def _on_check(self) -> None:
        """Génère les regex et les applique à toutes les lignes d'exemple."""
        self._result = None
        fields = {name: (start, end) for name, start, end in self._marks if name}
        ignored = [(start, end) for name, start, end in self._marks if not name]
        try:
            generated = self._generator.generate(self._line, fields, ignored)
        except RegexGenerationError as error:
            self._dialog.show_check("", (), (), "", f"Impossible de générer les regex : {error}")
            return
        results = self._generator.apply(generated, self._lines)
        rows = [WizardCheckRow(r.line_number, tuple(value for _, value in r.values))
                for r in results]
        total = sum(1 for line in self._lines if line.strip())
        summary = f"✔ {len(rows)} ligne(s) reconnue(s) sur {total} ligne(s) de l'exemple."
        if len(rows) <= 1 < total:
            summary += (" Seule la ligne choisie est reconnue : si d'autres lignes de ce "
                        "type existent, revenez à l'étape 3 et marquez leurs parties "
                        "variables (date, heure…).")
        self._result = generated
        self._dialog.show_check(generated.detect_regex, generated.field_regexes, rows,
                                summary, "")

    # ============================================================ interne
    def _refresh_marks(self) -> None:
        """Affiche les sélections et le modèle de ligne."""
        views = [WizardMarkView(
            label=FIELD_LABELS.get(name, name) if name else IGNORED_LABEL,
            text=self._line[start:end], start=start, end=end, ignored=not name)
            for name, start, end in self._marks]
        self._dialog.set_marks(views, self._template())

    def _template(self) -> str:
        """Construit la ligne où chaque sélection est remplacée par son nom.

        :return: modèle lisible (ex. « [‹…›] WARNING ‹Code› ‹Fichier›:‹Ligne› »).
        """
        parts: List[str] = []
        cursor = 0
        for name, start, end in self._marks:
            parts.append(self._line[cursor:start])
            parts.append(f"‹{FIELD_LABELS.get(name, name)}›" if name else IGNORED_TOKEN)
            cursor = end
        parts.append(self._line[cursor:])
        return "".join(parts)
