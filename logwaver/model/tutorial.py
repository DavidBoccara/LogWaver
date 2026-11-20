"""Didacticiel : lecture des étapes et progression (sans aucune dépendance à Qt).

Le contenu du didacticiel est décrit dans un fichier INI éditable à la main
(``resources/tutorial/didacticiel.ini``) ::

    [tutorial]
    title = Découvrir LogWaver
    steps = bienvenue, exemple

    [step:bienvenue]
    title = Bienvenue
    text = Texte de l'étape (HTML simple autorisé).
    target = EntryTree
    action = load_sample
    action_label = Charger l'exemple

``target`` est l'objectName du widget mis en évidence et ``action`` l'action
réalisée par le bouton « Montre-moi » (voir ``TutorialPresenter``).
"""

from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from logwaver.constants import FILE_ENCODING
from logwaver.model.exceptions import LogWaverError

LOGGER = logging.getLogger(__name__)

TUTORIAL_SECTION: str = "tutorial"
STEP_SECTION_PREFIX: str = "step:"


@dataclass(frozen=True)
class TutorialStep:
    """Étape du didacticiel.

    :param step_id: identifiant de l'étape.
    :param title: titre affiché.
    :param text: explication (HTML simple).
    :param target: objectName du widget mis en évidence (vide = aucun).
    :param action: action réalisable par l'outil à la demande (vide = aucune).
    :param action_label: libellé du bouton déclenchant l'action.
    """

    step_id: str
    title: str
    text: str
    target: str = ""
    action: str = ""
    action_label: str = ""


@dataclass(frozen=True)
class Tutorial:
    """Didacticiel complet.

    :param title: titre général.
    :param steps: étapes, dans l'ordre.
    """

    title: str
    steps: Tuple[TutorialStep, ...]


class TutorialLoader:
    """Lit un didacticiel au format INI."""

    def load(self, path: Path) -> Tutorial:
        """Charge et valide un didacticiel.

        :param path: fichier INI du didacticiel.
        :return: didacticiel chargé.
        :raises LogWaverError: si le fichier est absent ou invalide.
        """
        parser = configparser.ConfigParser(interpolation=None)
        parser.optionxform = str  # type: ignore[assignment]
        try:
            with path.open("r", encoding=FILE_ENCODING) as handle:
                parser.read_file(handle)
        except (OSError, configparser.Error) as error:
            raise LogWaverError(f"Didacticiel illisible « {path} » : {error}") from error
        step_ids = [item.strip() for item in
                    parser.get(TUTORIAL_SECTION, "steps", fallback="").split(",")
                    if item.strip()]
        if not step_ids:
            raise LogWaverError("Le didacticiel ne déclare aucune étape.")
        steps = []
        for step_id in step_ids:
            section = f"{STEP_SECTION_PREFIX}{step_id}"
            if not parser.has_section(section):
                raise LogWaverError(f"Étape « {step_id} » sans section [{section}].")
            steps.append(TutorialStep(
                step_id=step_id,
                title=parser.get(section, "title", fallback=step_id),
                text=parser.get(section, "text", fallback="").strip(),
                target=parser.get(section, "target", fallback="").strip(),
                action=parser.get(section, "action", fallback="").strip(),
                action_label=parser.get(section, "action_label", fallback="Montre-moi").strip(),
            ))
        LOGGER.info("Didacticiel chargé : %d étapes", len(steps))
        return Tutorial(parser.get(TUTORIAL_SECTION, "title", fallback="Didacticiel"),
                        tuple(steps))


class TutorialProgress:
    """Position courante dans un didacticiel."""

    def __init__(self, tutorial: Tutorial) -> None:
        """Démarre le didacticiel à la première étape.

        :param tutorial: didacticiel à parcourir.
        """
        self._tutorial: Tutorial = tutorial
        self._index: int = 0

    @property
    def tutorial(self) -> Tutorial:
        """Retourne le didacticiel parcouru."""
        return self._tutorial

    @property
    def index(self) -> int:
        """Retourne l'index (0-based) de l'étape courante."""
        return self._index

    @property
    def count(self) -> int:
        """Retourne le nombre d'étapes."""
        return len(self._tutorial.steps)

    @property
    def current(self) -> TutorialStep:
        """Retourne l'étape courante."""
        return self._tutorial.steps[self._index]

    @property
    def is_first(self) -> bool:
        """Indique si l'étape courante est la première."""
        return self._index == 0

    @property
    def is_last(self) -> bool:
        """Indique si l'étape courante est la dernière."""
        return self._index == self.count - 1

    def next(self) -> Optional[TutorialStep]:
        """Passe à l'étape suivante.

        :return: nouvelle étape, ou ``None`` si la fin est atteinte.
        """
        if self.is_last:
            return None
        self._index += 1
        return self.current

    def previous(self) -> Optional[TutorialStep]:
        """Revient à l'étape précédente.

        :return: nouvelle étape, ou ``None`` si déjà au début.
        """
        if self.is_first:
            return None
        self._index -= 1
        return self.current
