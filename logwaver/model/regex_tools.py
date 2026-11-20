"""Outils d'aide à la conception des plugins : test et génération de regex.

Génération automatique : l'utilisateur colle une ligne d'exemple et
sélectionne, pour chaque champ, le texte correspondant. Le générateur
construit alors un « squelette » de la ligne où :

* les parties fixes sont généralisées (chiffres → ``\\d+``, espaces →
  ``\\s+``, ponctuation échappée, mots conservés) ;
* chaque champ est remplacé par un motif déduit de sa valeur.

Chaque regex de champ est ce squelette où seul le champ concerné est
capturant. Le résultat est vérifié sur la ligne d'exemple.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Pattern, Tuple

from logwaver.model.exceptions import RegexGenerationError
from logwaver.model.plugin import extract_with_pattern, value_group

MAX_TEST_MATCHES: int = 2000
_LITERAL_TOKEN = re.compile(r"\d+|\s+|[A-Za-z_]+|.", re.DOTALL)


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


class RegexGenerator:
    """Déduit des regex de champs à partir d'une ligne annotée."""

    def generate(
        self, sample_line: str, field_spans: Mapping[str, Tuple[int, int]]
    ) -> GeneratedRegexes:
        """Génère les regex de détection et de champs.

        :param sample_line: ligne d'exemple.
        :param field_spans: champ → (début, fin) de sa valeur dans la ligne.
        :return: regex générées et vérifiées.
        :raises RegexGenerationError: si les sélections sont incohérentes ou
            si la vérification échoue.
        """
        spans = self._validate_spans(sample_line, field_spans)
        segments = self._build_segments(sample_line, spans)
        detect_regex = "^" + "".join(
            literal if name is None else f"(?:{pattern})"
            for name, literal, pattern in segments
        )
        field_regexes: List[Tuple[str, str]] = []
        for target_name, _ in spans:
            regex = "^" + "".join(
                literal if name is None
                else (f"({pattern})" if name == target_name else f"(?:{pattern})")
                for name, literal, pattern in segments
            )
            field_regexes.append((target_name, regex))
        result = GeneratedRegexes(detect_regex, tuple(field_regexes))
        self._verify(sample_line, dict(spans), result)
        return result

    # ------------------------------------------------------------ interne
    @staticmethod
    def _validate_spans(
        line: str, field_spans: Mapping[str, Tuple[int, int]]
    ) -> List[Tuple[str, Tuple[int, int]]]:
        """Trie et contrôle les sélections de champs.

        :param line: ligne d'exemple.
        :param field_spans: sélections brutes.
        :return: sélections triées par position.
        :raises RegexGenerationError: si une sélection est vide, hors de la
            ligne ou chevauche une autre.
        """
        if not field_spans:
            raise RegexGenerationError("Aucun champ n'a été sélectionné.")
        ordered = sorted(field_spans.items(), key=lambda item: item[1][0])
        previous_end = 0
        for name, (start, end) in ordered:
            if not 0 <= start < end <= len(line):
                raise RegexGenerationError(
                    f"Sélection invalide pour le champ « {name} »."
                )
            if start < previous_end:
                raise RegexGenerationError(
                    f"La sélection du champ « {name} » chevauche un autre champ."
                )
            previous_end = end
        return ordered

    def _build_segments(
        self, line: str, spans: List[Tuple[str, Tuple[int, int]]]
    ) -> List[Tuple[Optional[str], str, str]]:
        """Découpe la ligne en segments fixes et segments de champs.

        :param line: ligne d'exemple.
        :param spans: sélections triées.
        :return: liste de (nom du champ ou None, littéral, motif du champ).
        """
        segments: List[Tuple[Optional[str], str, str]] = []
        cursor = 0
        for index, (name, (start, end)) in enumerate(spans):
            if start > cursor:
                segments.append((None, self._generalize(line[cursor:start]), ""))
            next_start = spans[index + 1][1][0] if index + 1 < len(spans) else len(line)
            following = line[end:next_start]
            is_last = end == len(line) or (
                index + 1 == len(spans) and not line[end:].strip()
            )
            segments.append(
                (name, "", self._field_pattern(line[start:end], following, is_last))
            )
            cursor = end
        return segments

    @staticmethod
    def _generalize(literal: str) -> str:
        """Transforme un texte fixe en motif tolérant.

        :param literal: texte situé entre deux champs.
        :return: motif regex équivalent mais généralisé.
        """
        parts: List[str] = []
        for token in _LITERAL_TOKEN.findall(literal):
            if token.isdigit():
                parts.append(r"\d+")
            elif token.isspace():
                parts.append(r"\s+")
            else:
                parts.append(re.escape(token))
        return "".join(parts)

    @staticmethod
    def _field_pattern(value: str, following: str, is_last: bool) -> str:
        """Déduit le motif d'un champ à partir de sa valeur.

        :param value: valeur sélectionnée.
        :param following: texte fixe qui suit le champ.
        :param is_last: ``True`` si le champ termine la ligne.
        :return: motif regex du champ.
        """
        if value.isdigit():
            return r"\d+"
        if is_last:
            return r".+"
        if not any(char.isspace() for char in value):
            stop_char = following[:1]
            if stop_char and not stop_char.isspace() and not stop_char.isalnum():
                return rf"[^\s{re.escape(stop_char)}]+"
            return r"\S+"
        return r".+?"

    @staticmethod
    def _verify(
        line: str, spans: Dict[str, Tuple[int, int]], result: GeneratedRegexes
    ) -> None:
        """Vérifie que chaque regex générée extrait la valeur sélectionnée.

        :param line: ligne d'exemple.
        :param spans: sélections par champ.
        :param result: regex générées.
        :raises RegexGenerationError: si une extraction diffère.
        """
        if re.search(result.detect_regex, line) is None:
            raise RegexGenerationError(
                "La regex de détection générée ne reconnaît pas la ligne."
            )
        for name, regex in result.field_regexes:
            pattern: Pattern[str] = re.compile(regex)
            expected = line[spans[name][0]:spans[name][1]].strip()
            obtained = extract_with_pattern(pattern, line)
            if obtained != expected:
                raise RegexGenerationError(
                    f"Vérification échouée pour « {name} » : attendu "
                    f"« {expected} », obtenu « {obtained} »."
                )
