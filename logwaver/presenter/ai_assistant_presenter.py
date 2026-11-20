"""Présentateur du dialogue d'aide IA."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

from logwaver.model.ai_assistant import AiProvider, AiResponseParser
from logwaver.presenter.error_handling import guarded
from logwaver.view_models import AiSuggestionData

if TYPE_CHECKING:  # import réservé au typage : aucune dépendance d'exécution
    from logwaver.view.dialogs.ai_help_dialog import AiHelpDialog

LOGGER = logging.getLogger(__name__)

ApplyCallback = Callable[[str, str, bool], bool]
NO_RESPONSE_HINT: str = (
    "Aucune réponse : aucune IA n'est branchée. Le prompt a été réaffiché dans le terminal."
)
UNSTRUCTURED_HINT: str = (
    "La réponse ne suit pas le format attendu : elle a été reprise entièrement "
    "comme justification. Relisez-la avant de valider."
)


class AiAssistantPresenter:
    """Pilote :class:`AiHelpDialog` : envoi du prompt, analyse, justification."""

    def __init__(
        self,
        dialog: "AiHelpDialog",
        provider: AiProvider,
        parser: AiResponseParser,
        apply_callback: ApplyCallback,
    ) -> None:
        """Relie le dialogue à ses collaborateurs.

        :param dialog: vue pilotée.
        :param provider: fournisseur d'IA.
        :param parser: analyseur des réponses.
        :param apply_callback: fonction ``(statut, texte, même_code) -> succès``
            appliquant la justification (fournie par le présentateur principal).
        """
        self._dialog = dialog
        self._provider = provider
        self._parser = parser
        self._apply_callback = apply_callback
        dialog.ask_requested.connect(self._on_ask)
        dialog.analyse_requested.connect(self._on_analyse)
        dialog.apply_requested.connect(self._on_apply)

    def run(self, initial_response: str) -> None:
        """Affiche le dialogue (modal) après analyse d'une éventuelle réponse.

        :param initial_response: réponse déjà obtenue (peut être vide).
        """
        if initial_response.strip():
            self._on_analyse(initial_response)
        self._dialog.exec_()

    def _report_error(self, message: str) -> None:
        """Affiche une erreur dans le dialogue (utilisé par ``guarded``).

        :param message: texte de l'erreur.
        """
        self._dialog.show_hint(message)

    @guarded
    def _on_ask(self, prompt: str) -> None:
        """Soumet le prompt au fournisseur d'IA.

        :param prompt: prompt (éventuellement retouché par l'utilisateur).
        """
        response = self._provider.ask(prompt)
        if not response:
            self._dialog.show_hint(NO_RESPONSE_HINT)
            return
        self._dialog.set_response(response)
        self._on_analyse(response)

    @guarded
    def _on_analyse(self, response: str) -> None:
        """Extrait la proposition structurée d'une réponse.

        :param response: texte de la réponse.
        """
        if not response.strip():
            self._dialog.show_hint("Collez d'abord la réponse de l'IA.")
            return
        suggestion = self._parser.parse(response)
        self._dialog.show_suggestion(AiSuggestionData(
            explanation=suggestion.explanation,
            assessment=suggestion.assessment,
            status_id=suggestion.status_id or None,
            justification=suggestion.justification,
        ))
        if not suggestion.explanation and not suggestion.status_id:
            self._dialog.show_hint(UNSTRUCTURED_HINT)

    @guarded
    def _on_apply(self, status_id: str, text: str, apply_to_same_code: bool) -> None:
        """Applique la justification proposée puis ferme le dialogue.

        :param status_id: catégorie choisie.
        :param text: justification.
        :param apply_to_same_code: étendre à tous les éléments du même code.
        """
        if self._apply_callback(status_id, text, apply_to_same_code):
            self._dialog.accept()
