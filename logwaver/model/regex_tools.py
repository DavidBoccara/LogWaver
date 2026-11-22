"""Outils d'aide à la conception des plugins : test et génération de regex.

Génération automatique (assistant pas à pas) : sur une ligne d'exemple,
l'utilisateur sélectionne

* les **éléments à extraire** (chemin du fichier, code, description...) ;
* les **parties variables sans intérêt** (date, heure, identifiant...).

Tout le reste de la ligne est considéré comme **invariant** : c'est sur ce
texte fixe, et sur lui seul, que reposent les regex. Les éléments
sélectionnés peuvent donc prendre n'importe quelle valeur sur les autres
lignes (``.+?`` entre deux textes fixes). Le résultat est vérifié sur la
ligne d'exemple.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from logwaver.model.exceptions import RegexGenerationError
from logwaver.model.plugin import extract_with_pattern, value_group

MAX_TEST_MATCHES: int = 2000


@dataclass(frozen=True)
class RegexMatchResult:
    """Résultat d'un test de regex sur une ligne.

    :param line_number: numéro de ligne (1 = première).
    :param start: début de la valeur extraite dans la ligne.
    :param end: fin de la valeur extraite.
    :param extracted: valeur extraite selon la convention des plugins.
    """

    line_number: int
    start: int
    end: int
    extracted: str


@dataclass(frozen=True)
class RegexTestReport:
    """Rapport de test d'une regex sur un texte.

    :param error: message d'erreur de compilation (vide si valide).
    :param matches: correspondances trouvées.
    :param truncated: ``True`` si la limite d'affichage a été atteinte.
    """

    error: str
    matches: Tuple[RegexMatchResult, ...]
    truncated: bool = False

    @property
    def is_valid(self) -> bool:
        """Indique si la regex a pu être compilée."""
        return not self.error


class RegexTester:
    """Teste une regex ligne par ligne sur un texte d'exemple."""

    def test(self, pattern_text: str, sample_text: str) -> RegexTestReport:
        """Exécute la regex sur chaque ligne de l'exemple.

        :param pattern_text: regex à tester.
        :param sample_text: texte d'exemple (plusieurs lignes possibles).
        :return: rapport de test.
        """
        try:
            pattern = re.compile(pattern_text)
        except re.error as error:
            return RegexTestReport(error=str(error), matches=())
        results: List[RegexMatchResult] = []
        for line_number, line in enumerate(sample_text.splitlines(), start=1):
            match = pattern.search(line)
            if match is None:
                continue
            group = value_group(pattern)
            start, end = match.span(group)
            if start < 0:  # groupe optionnel non capturé
                start, end = match.span()
            results.append(
                RegexMatchResult(
                    line_number=line_number,
                    start=start,
                    end=end,
                    extracted=(match.group(group) or "").strip(),
                )
            )
            if len(results) >= MAX_TEST_MATCHES:
                return RegexTestReport("", tuple(results), truncated=True)
        return RegexTestReport("", tuple(results))


@dataclass(frozen=True)
class GeneratedRegexes:
    """Regex générées automatiquement pour un type d'élément.

    :param detect_regex: regex de détection de la ligne.
    :param field_regexes: regex par champ (ordre de la ligne).
    """

    detect_regex: str
    field_regexes: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class ExtractionResult:
    """Valeurs extraites d'une ligne par des regex générées.

    :param line_number: ligne de l'exemple (1 = première).
    :param values: champ → valeur extraite.
    """

    line_number: int
    values: Tuple[Tuple[str, str], ...]


VARIABLE_PATTERN: str = ".+?"
LAST_VARIABLE_PATTERN: str = ".+"
IGNORED_PART: str = "__ignored__"
# Séquences de chiffres éventuellement séparées (dates, heures, numéros...).
NUMERIC_RUN = re.compile(r"\d+(?:[-:/.,T ]\d+)*")


class RegexGenerator:
    """Construit des regex fondées uniquement sur le texte invariant d'une ligne."""

    def generate(
        self,
        sample_line: str,
        field_spans: Mapping[str, Tuple[int, int]],
        ignored_spans: Sequence[Tuple[int, int]] = (),
    ) -> GeneratedRegexes:
        """Génère les regex de détection et de champs.

        :param sample_line: ligne d'exemple.
        :param field_spans: champ → (début, fin) de sa valeur dans la ligne.
        :param ignored_spans: parties variables sans intérêt (début, fin).
        :return: regex générées et vérifiées.
        :raises RegexGenerationError: si les sélections sont incohérentes ou
            si la vérification échoue.
        """
        if not field_spans:
            raise RegexGenerationError("Sélectionnez au moins un élément à extraire.")
        marks = [(name, span) for name, span in field_spans.items()]
        marks += [(IGNORED_PART, span) for span in ignored_spans]
        segments = self._build_segments(sample_line, self._validate(sample_line, marks))
        detect_regex = self._assemble(segments, target=None)
        field_regexes = tuple((name, self._assemble(segments, target=name))
                              for name, _ in sorted(field_spans.items(),
                                                    key=lambda item: item[1][0]))
        result = GeneratedRegexes(detect_regex, field_regexes)
        self._verify(sample_line, dict(field_spans), result)
        return result

    @staticmethod
    def suggest_variable_parts(line: str,
                               taken: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Propose les parties fixes qui semblent en réalité variables.

        Les nombres, dates et heures restés dans le texte fixe changeront
        presque toujours d'une ligne à l'autre : ils sont proposés comme
        « parties variables sans intérêt ».

        :param line: ligne d'exemple.
        :param taken: zones déjà sélectionnées (exclues des propositions).
        :return: zones proposées (début, fin).
        """
        def overlaps(start: int, end: int) -> bool:
            return any(start < t_end and t_start < end for t_start, t_end in taken)

        return [(m.start(), m.end()) for m in NUMERIC_RUN.finditer(line)
                if not overlaps(m.start(), m.end())]

    @staticmethod
    def apply(regexes: GeneratedRegexes, lines: Sequence[str]) -> List[ExtractionResult]:
        """Applique des regex générées à des lignes d'exemple.

        :param regexes: regex à appliquer.
        :param lines: lignes d'exemple.
        :return: valeurs extraites pour chaque ligne reconnue.
        """
        detect = re.compile(regexes.detect_regex)
        fields = [(name, re.compile(regex)) for name, regex in regexes.field_regexes]
        results: List[ExtractionResult] = []
        for number, line in enumerate(lines, start=1):
            if detect.search(line) is None:
                continue
            values = tuple((name, extract_with_pattern(pattern, line) or "")
                           for name, pattern in fields)
            results.append(ExtractionResult(number, values))
        return results

    # ------------------------------------------------------------ interne
    @staticmethod
    def _validate(line: str, marks: List[Tuple[str, Tuple[int, int]]]
                  ) -> List[Tuple[str, Tuple[int, int]]]:
        """Trie et contrôle les sélections.

        :param line: ligne d'exemple.
        :param marks: sélections (nom ou ``IGNORED_PART``, zone).
        :return: sélections triées par position.
        :raises RegexGenerationError: si une sélection est vide, hors de la
            ligne, chevauche une autre ou en touche une autre.
        """
        ordered = sorted(marks, key=lambda item: item[1][0])
        previous: Optional[Tuple[str, int]] = None
        for name, (start, end) in ordered:
            label = "une partie ignorée" if name == IGNORED_PART else f"« {name} »"
            if not 0 <= start < end <= len(line):
                raise RegexGenerationError(f"Sélection invalide pour {label}.")
            if previous is not None and start < previous[1]:
                raise RegexGenerationError(f"La sélection de {label} chevauche une autre.")
            if previous is not None and start == previous[1]:
                raise RegexGenerationError(
                    f"La sélection de {label} touche la précédente : sans texte fixe "
                    "entre les deux, impossible de savoir où l'une finit. Fusionnez-les "
                    "ou laissez un séparateur entre elles.")
            previous = (name, end)
        return ordered

    def _build_segments(self, line: str, marks: List[Tuple[str, Tuple[int, int]]]
                        ) -> List[Tuple[Optional[str], str]]:
        """Découpe la ligne en textes fixes et zones variables.

        :param line: ligne d'exemple.
        :param marks: sélections triées.
        :return: liste de (nom ou None pour un texte fixe, motif regex).
        """
        segments: List[Tuple[Optional[str], str]] = []
        cursor = 0
        for index, (name, (start, end)) in enumerate(marks):
            if start > cursor:
                segments.append((None, self._literal(line[cursor:start])))
            is_last = index == len(marks) - 1 and not line[end:].strip()
            segments.append((name, LAST_VARIABLE_PATTERN if is_last else VARIABLE_PATTERN))
            cursor = end
        if line[cursor:].strip():
            segments.append((None, self._literal(line[cursor:].rstrip())))
        return segments

    @staticmethod
    def _assemble(segments: List[Tuple[Optional[str], str]], target: Optional[str]) -> str:
        """Assemble une regex complète ancrée sur la ligne.

        :param segments: textes fixes et zones variables.
        :param target: champ à capturer (``None`` = regex de détection).
        :return: regex.
        """
        parts = ["^"]
        for name, pattern in segments:
            if name is None:
                parts.append(pattern)
            elif name == target:
                parts.append(f"({pattern})")
            else:
                parts.append(f"(?:{pattern})")
        parts.append(r"\s*$")
        return "".join(parts)

    @staticmethod
    def _literal(text: str) -> str:
        """Transforme un texte fixe en motif exact (seuls les espaces sont tolérés).

        :param text: texte invariant.
        :return: motif regex.
        """
        pieces = re.split(r"(\s+)", text)
        return "".join(r"\s+" if piece.isspace() else re.escape(piece)
                       for piece in pieces if piece)

    @staticmethod
    def _verify(line: str, spans: Dict[str, Tuple[int, int]], result: GeneratedRegexes) -> None:
        """Vérifie que chaque regex générée extrait la valeur sélectionnée.

        :param line: ligne d'exemple.
        :param spans: sélections par champ.
        :param result: regex générées.
        :raises RegexGenerationError: si une extraction diffère.
        """
        if re.search(result.detect_regex, line) is None:
            raise RegexGenerationError(
                "La regex de détection générée ne reconnaît pas la ligne.")
        for name, regex in result.field_regexes:
            expected = line[spans[name][0]:spans[name][1]].strip()
            obtained = extract_with_pattern(re.compile(regex), line)
            if obtained != expected:
                raise RegexGenerationError(
                    f"Vérification échouée pour « {name} » : attendu « {expected} », "
                    f"obtenu « {obtained} ». Le texte fixe qui suit ce champ apparaît "
                    "peut-être aussi à l'intérieur de sa valeur : sélectionnez un "
                    "séparateur plus distinctif.")
