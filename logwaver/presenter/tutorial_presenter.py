"""Présentateur du didacticiel : navigation entre les étapes et actions « Montre-moi »."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Dict, Optional

from logwaver.model.exceptions import LogWaverError
from logwaver.model.tutorial import Tutorial, TutorialProgress
from logwaver.presenter.error_handling import guarded

if TYPE_CHECKING:
    from logwaver.view.main_window import MainWindow

LOGGER = logging.getLogger(__name__)

TutorialAction = Callable[[], None]


class TutorialPresenter:
    """Fait défiler les étapes et exécute les actions de démonstration.

    Les actions (charger l'exemple, regrouper par code...) sont fournies par
    le présentateur principal sous forme de fonctions nommées, référencées
    par leur nom dans le fichier du didacticiel.
    """

    def __init__(self, view: "MainWindow", tutorial: Tutorial,
                 actions: Dict[str, TutorialAction]) -> None:
        """Relie le didacticiel à la fenêtre.

        :param view: fenêtre principale (porte le panneau du didacticiel).
        :param tutorial: contenu du didacticiel.
        :param actions: nom d'action → fonction à exécuter.
        """
        self._view = view
        self._tutorial = tutorial
        self._actions = actions
        self._progress: Optional[TutorialProgress] = None
        unknown = {step.action for step in tutorial.steps
                   if step.action and step.action not in actions}
        if unknown:
            LOGGER.warning("Actions de didacticiel inconnues : %s", ", ".join(sorted(unknown)))
        view.tutorial_next_requested.connect(self._on_next)
        view.tutorial_previous_requested.connect(self._on_previous)
        view.tutorial_action_requested.connect(self._on_action)
        view.tutorial_quit_requested.connect(self.stop)

    @property
    def is_running(self) -> bool:
        """Indique si le didacticiel est affiché."""
        return self._progress is not None

    def start(self) -> None:
        """Démarre (ou redémarre) le didacticiel à la première étape."""
        self._progress = TutorialProgress(self._tutorial)
        self._show_current()

    def stop(self) -> None:
        """Ferme le didacticiel."""
        self._progress = None
        self._view.hide_tutorial()

    def _report_error(self, message: str) -> None:
        """Affiche une erreur (utilisé par ``guarded``).

        :param message: texte de l'erreur.
        """
        self._view.show_error(message)

    @guarded
    def _on_next(self) -> None:
        """Passe à l'étape suivante, ou termine le didacticiel."""
        if self._progress is None:
            return
        if self._progress.next() is None:
            self.stop()
            self._view.show_status_message("Didacticiel terminé. Il reste disponible "
                                           "dans le menu Aide (Maj+F1).")
            return
        self._show_current()

    @guarded
    def _on_previous(self) -> None:
        """Revient à l'étape précédente."""
        if self._progress is not None and self._progress.previous() is not None:
            self._show_current()

    @guarded
    def _on_action(self) -> None:
        """Exécute l'action « Montre-moi » de l'étape courante."""
        if self._progress is None:
            return
        name = self._progress.current.action
        if not name:
            return  # étape purement explicative : rien à faire
        action = self._actions.get(name)
        if action is None:
            raise LogWaverError(f"Action de didacticiel inconnue : « {name} »")
        action()
        self._show_current()  # la mise en évidence peut viser un widget apparu entre-temps

    def _show_current(self) -> None:
        """Affiche l'étape courante."""
        if self._progress is None:
            return
        step = self._progress.current
        has_action = bool(step.action) and step.action in self._actions
        self._view.show_tutorial_step(
            index=self._progress.index,
            count=self._progress.count,
            title=step.title,
            text=step.text,
            action_label=step.action_label if has_action else "",
            is_first=self._progress.is_first,
            is_last=self._progress.is_last,
            target=step.target,
        )
