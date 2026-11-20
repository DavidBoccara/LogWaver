"""Assistance IA : génération des prompts, fournisseur d'IA et lecture des réponses.

L'IA elle-même n'est pas intégrée : :class:`TerminalPromptProvider` se
contente d'afficher le prompt dans le terminal. Pour brancher une vraie IA,
il suffit d'implémenter :class:`AiProvider` et de l'injecter dans le
présentateur (voir ``main.py``).
"""

from __future__ import annotations

import logging
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, TextIO

from logwaver.constants import DEFAULT_AI_LANGUAGE
from logwaver.model.entities import LogEntry, StatusDefinition

LOGGER = logging.getLogger(__name__)

SECTION_EXPLANATION: str = "EXPLICATION"
SECTION_ASSESSMENT: str = "ANALYSE"
SECTION_STATUS: str = "STATUT"
SECTION_JUSTIFICATION: str = "JUSTIFICATION"
RESPONSE_SECTIONS: tuple = (
    SECTION_EXPLANATION,
    SECTION_ASSESSMENT,
    SECTION_STATUS,
    SECTION_JUSTIFICATION,
)
MAX_OCCURRENCES_IN_PROMPT: int = 10
TERMINAL_SEPARATOR: str = "=" * 78

PROMPT_TEMPLATES: Dict[str, str] = {
    "fr": (
        "Tu es un expert de l'outil {tool}. Peux-tu m'expliquer le {type_lower} "
        "avec le code {code} qui provient de l'outil {tool} et qui me renvoie "
        "le message : « {description} » ?\n"
        "\n"
        "Contexte :\n"
        "- Fichier concerné : {file}\n"
        "- Ligne : {line}\n"
        "- Ligne complète du log : {raw}\n"
        "{occurrences}"
        "\n"
        "Peux-tu me dire pour quelle raison c'est un problème, si c'est un "
        "problème, ou pour quelle raison ça ne l'est pas, en fonction de la "
        "gravité du {type_lower} ? Peux-tu ensuite me faire une proposition de "
        "justification pour ce {type_lower} ?\n"
        "\n"
        "Choisis le statut le plus adapté parmi : {statuses}.\n"
        "\n"
        "Réponds STRICTEMENT avec les sections suivantes, chacune sur une "
        "ligne commençant par son titre en majuscules suivi de « : » :\n"
        "{sec_expl}: <explication du message>\n"
        "{sec_assess}: <est-ce un problème ? pourquoi ? gravité>\n"
        "{sec_status}: <identifiant du statut choisi>\n"
        "{sec_just}: <justification concise et factuelle, réutilisable telle "
        "quelle dans un rapport de revue>\n"
    ),
    "en": (
        "You are an expert of the {tool} tool. Can you explain the "
        "{type_lower} with code {code} coming from the {tool} tool, which "
        "reports: \"{description}\"?\n"
        "\n"
        "Context:\n"
        "- File: {file}\n"
        "- Line: {line}\n"
        "- Full log line: {raw}\n"
        "{occurrences}"
        "\n"
        "Please tell me why this is a problem, if it is one, or why it is "
        "not, depending on the severity of the {type_lower}. Then propose a "
        "justification for this {type_lower}.\n"
        "\n"
        "Pick the most suitable status among: {statuses}.\n"
        "\n"
        "Answer STRICTLY with the following sections, each on a line starting "
        "with its upper-case title followed by ':':\n"
        "{sec_expl}: <explanation>\n"
        "{sec_assess}: <is it a problem? why? severity>\n"
        "{sec_status}: <chosen status id>\n"
        "{sec_just}: <concise, factual justification, reusable as-is>\n"
    ),
}

OCCURRENCES_HEADERS: Dict[str, str] = {
    "fr": "- Ce code apparaît {count} fois, par exemple :\n",
    "en": "- This code appears {count} times, for example:\n",
}


class PromptBuilder:
    """Construit les prompts d'aide à destination d'une IA."""

    def __init__(self, language: str = DEFAULT_AI_LANGUAGE) -> None:
        """Initialise le générateur.

        :param language: langue du prompt (``fr`` ou ``en``).
        """
        if language not in PROMPT_TEMPLATES:
            LOGGER.warning("Langue IA « %s » inconnue, repli sur %s.",
                           language, DEFAULT_AI_LANGUAGE)
            language = DEFAULT_AI_LANGUAGE
        self._language: str = language

    def build(
        self,
        entry: LogEntry,
        statuses: Sequence[StatusDefinition],
        same_code_entries: Sequence[LogEntry] = (),
    ) -> str:
        """Génère le prompt d'explication/justification d'un élément.

        :param entry: élément concerné.
        :param statuses: catégories proposées à l'IA.
        :param same_code_entries: autres occurrences du même code (contexte).
        :return: texte du prompt.
        """
        template = PROMPT_TEMPLATES[self._language]
        status_text = ", ".join(
            f"{status.status_id} ({status.label})" for status in statuses
        )
        return template.format(
            tool=entry.tool_name,
            type_lower=entry.entry_type.lower(),
            code=entry.code or "?",
            description=entry.description or entry.raw_text,
            file=entry.file_path or "?",
            line=entry.fields.get("line", "") or "?",
            raw=entry.raw_text,
            occurrences=self._occurrences_block(entry, same_code_entries),
            statuses=status_text,
            sec_expl=SECTION_EXPLANATION,
            sec_assess=SECTION_ASSESSMENT,
            sec_status=SECTION_STATUS,
            sec_just=SECTION_JUSTIFICATION,
        )

    def _occurrences_block(
        self, entry: LogEntry, same_code_entries: Sequence[LogEntry]
    ) -> str:
        """Construit la liste des autres occurrences du même code.

        :param entry: élément principal.
        :param same_code_entries: occurrences du même code.
        :return: texte (vide s'il n'y a pas d'autre occurrence).
        """
        others = [e for e in same_code_entries if e.entry_id != entry.entry_id]
        if not others:
            return ""
        header = OCCURRENCES_HEADERS[self._language].format(
            count=len(others) + 1
        )
        samples = "".join(
            f"    * {other.raw_text}\n"
            for other in others[:MAX_OCCURRENCES_IN_PROMPT]
        )
        return header + samples


class AiProvider(ABC):
    """Interface d'un fournisseur d'IA (à implémenter pour une vraie IA)."""

    @abstractmethod
    def ask(self, prompt: str) -> Optional[str]:
        """Soumet un prompt.

        :param prompt: texte du prompt.
        :return: réponse de l'IA, ou ``None`` si aucune IA n'est branchée.
        """


class TerminalPromptProvider(AiProvider):
    """Fournisseur « sans IA » : affiche le prompt dans le terminal."""

    def __init__(self, stream: TextIO = sys.stdout) -> None:
        """Initialise le fournisseur.

        :param stream: flux de sortie (terminal par défaut).
        """
        self._stream: TextIO = stream

    def ask(self, prompt: str) -> Optional[str]:
        """Affiche le prompt et ne retourne aucune réponse.

        :param prompt: texte du prompt.
        :return: toujours ``None``.
        """
        try:
            self._stream.write(
                f"\n{TERMINAL_SEPARATOR}\nPROMPT IA LOGWAVER\n"
                f"{TERMINAL_SEPARATOR}\n{prompt}{TERMINAL_SEPARATOR}\n"
            )
            self._stream.flush()
        except (OSError, ValueError) as error:  # flux fermé ou absent
            LOGGER.error("Impossible d'afficher le prompt : %s", error)
        return None


@dataclass(frozen=True)
class AiSuggestion:
    """Réponse de l'IA découpée en sections.

    :param explanation: explication du message.
    :param assessment: analyse de gravité.
    :param status_id: statut suggéré (peut être vide ou inconnu).
    :param justification: justification proposée.
    """

    explanation: str
    assessment: str
    status_id: str
    justification: str

    @property
    def is_usable(self) -> bool:
        """Indique si une justification exploitable a été trouvée."""
        return bool(self.justification.strip())


class AiResponseParser:
    """Découpe une réponse textuelle d'IA selon les sections attendues."""

    _SECTION_PATTERN = re.compile(
        r"^\s*(?:[#*\-]+\s*)?(" + "|".join(RESPONSE_SECTIONS) + r")\s*\**\s*:",
        re.IGNORECASE | re.MULTILINE,
    )

    def parse(self, response: str) -> AiSuggestion:
        """Analyse une réponse d'IA.

        Si aucune section n'est reconnue, la réponse complète est utilisée
        comme justification (l'utilisateur peut la retoucher).

        :param response: texte renvoyé par l'IA.
        :return: suggestion structurée.
        """
        sections = self._split_sections(response)
        if not sections:
            return AiSuggestion("", "", "", response.strip())
        status_raw = sections.get(SECTION_STATUS, "")
        status_id = status_raw.split()[0].strip("`*().,;") if status_raw else ""
        return AiSuggestion(
            explanation=sections.get(SECTION_EXPLANATION, ""),
            assessment=sections.get(SECTION_ASSESSMENT, ""),
            status_id=status_id,
            justification=sections.get(SECTION_JUSTIFICATION, ""),
        )

    def _split_sections(self, response: str) -> Dict[str, str]:
        """Associe chaque titre de section au texte qui le suit.

        :param response: texte complet.
        :return: titre (majuscules) → contenu.
        """
        matches = list(self._SECTION_PATTERN.finditer(response))
        sections: Dict[str, str] = {}
        for position, match in enumerate(matches):
            end = (matches[position + 1].start()
                   if position + 1 < len(matches) else len(response))
            title = match.group(1).upper()
            sections[title] = response[match.end():end].strip()
        return sections
