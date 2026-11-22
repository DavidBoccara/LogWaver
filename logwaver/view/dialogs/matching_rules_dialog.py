"""Dialogue « Règles de correspondance » : ce qui doit être identique pour
qu'une justification existante s'applique à un élément d'un nouveau log."""

from __future__ import annotations

import html
from typing import Dict, Optional, Sequence

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from logwaver.view_models import (
    MatchingKeyView,
    MatchingPresetView,
    MatchingPreviewView,
    MatchingSettings,
)

PREVIEW_DEBOUNCE_MS: int = 150
MAX_EXAMPLE_LENGTH: int = 32
CUSTOM_PRESET_LABEL: str = "Personnalisé"
INTRO_TEXT: str = (
    "Quand vous ouvrez un nouveau log, LogWaver cherche pour chaque élément une "
    "justification déjà faite. Deux éléments sont considérés comme <b>le même</b> si "
    "les critères cochés sont identiques.<br><b>Décochez ce qui peut changer</b> d'un "
    "log à l'autre sans changer le problème (numéro de ligne, dossier, nom de fichier "
    "cité dans le message…). L'aperçu en bas montre l'effet immédiatement."
)


class MatchingRulesDialog(QDialog):
    """Vue passive : émet ``settings_changed`` et ``preset_selected``.

    Signaux :
    * ``settings_changed(MatchingSettings)`` : réglage modifié (aperçu à recalculer) ;
    * ``preset_selected(str)`` : préréglage choisi.
    """

    settings_changed = pyqtSignal(object)
    preset_selected = pyqtSignal(str)

    def __init__(self, keys: Sequence[MatchingKeyView], presets: Sequence[MatchingPresetView],
                 example_title: str, parent: Optional[QWidget] = None) -> None:
        """Construit le dialogue.

        :param keys: critères proposés, avec la valeur de l'élément d'exemple.
        :param presets: préréglages.
        :param example_title: description de l'élément d'exemple.
        :param parent: widget parent.
        """
        super().__init__(parent)
        self.setObjectName("MatchingRulesDialog")
        self.setWindowTitle("Règles de correspondance des justifications")
        self.resize(940, 900)
        self._key_checks: Dict[str, QCheckBox] = {}
        self._preset_group = QButtonGroup(self)
        self._preset_radios: Dict[str, QRadioButton] = {}
        self._custom_radio = QRadioButton(CUSTOM_PRESET_LABEL)
        self._custom_radio.setEnabled(False)
        self._mask_numbers = QCheckBox("les nombres (ex. 42, 3.14)")
        self._mask_quoted = QCheckBox("le texte entre guillemets ou apostrophes "
                                      "(ex. 'dada.txt', \"x\")")
        self._mask_paths = QCheckBox("les noms de fichiers et chemins (ex. dada.txt, "
                                     "src/a.c)")
        self._ignore_case = QCheckBox("les différences de majuscules / minuscules")
        self._compared_form = QFormLayout()
        self._effect_label = QLabel()
        self._effect_label.setObjectName("PanelTitle")
        self._gained_list = QListWidget()
        self._lost_list = QListWidget()
        for widget in (self._gained_list, self._lost_list):
            widget.setWordWrap(True)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.button(QDialogButtonBox.Ok).setText("Appliquer ces règles")
        self._buttons.button(QDialogButtonBox.Ok).setProperty("role", "primary")
        self._buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(PREVIEW_DEBOUNCE_MS)
        self._build_layout(keys, presets, example_title)
        self._connect_signals()

    # ================================================================== API
    def set_settings(self, settings: MatchingSettings) -> None:
        """Coche les cases selon un réglage (sans émettre de signal immédiat).

        :param settings: réglage à afficher.
        """
        for key, check in self._key_checks.items():
            check.blockSignals(True)
            check.setChecked(key in settings.keys)
            check.blockSignals(False)
        for check, value in ((self._mask_numbers, settings.mask_numbers),
                             (self._mask_quoted, settings.mask_quoted),
                             (self._mask_paths, settings.mask_paths),
                             (self._ignore_case, settings.ignore_case)):
            check.blockSignals(True)
            check.setChecked(value)
            check.blockSignals(False)
        self._debounce.start()

    def settings(self) -> MatchingSettings:
        """Retourne le réglage affiché.

        :return: critères cochés et tolérances.
        """
        return MatchingSettings(
            keys=tuple(key for key, check in self._key_checks.items() if check.isChecked()),
            ignore_case=self._ignore_case.isChecked(),
            mask_numbers=self._mask_numbers.isChecked(),
            mask_quoted=self._mask_quoted.isChecked(),
            mask_paths=self._mask_paths.isChecked(),
        )

    def show_preview(self, preview: MatchingPreviewView) -> None:
        """Affiche l'effet des règles envisagées.

        :param preview: aperçu calculé par le présentateur.
        """
        radio = self._preset_radios.get(preview.preset_key, self._custom_radio)
        radio.setChecked(True)
        while self._compared_form.rowCount():
            self._compared_form.removeRow(0)
        if not preview.compared:
            self._compared_form.addRow(QLabel("⚠ Aucun critère coché : cochez au moins "
                                              "le code."))
        for label, value in preview.compared:
            value_label = QLabel(value or "(vide)")
            value_label.setWordWrap(True)
            self._compared_form.addRow(f"{label} :", value_label)
        delta = preview.justified_after - preview.justified_before
        sign = f"+{delta}" if delta > 0 else str(delta)
        self._effect_label.setText(
            f"Éléments justifiés dans les logs ouverts : {preview.justified_before} → "
            f"{preview.justified_after} ({sign})")
        self._gained_list.clear()
        for entry_text, justification_text in preview.gained:
            self._gained_list.addItem(f"✔ {entry_text}\n      ← {justification_text}")
        if not preview.gained:
            self._gained_list.addItem("Aucun")
        self._lost_list.clear()
        for entry_text in preview.lost:
            self._lost_list.addItem(f"✘ {entry_text}")
        if not preview.lost:
            self._lost_list.addItem("Aucun")
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(bool(preview.compared))

    # ============================================================== interne
    def _build_layout(self, keys: Sequence[MatchingKeyView],
                      presets: Sequence[MatchingPresetView], example_title: str) -> None:
        """Dispose les trois zones : réglages, exemple, effet.

        :param keys: critères proposés.
        :param presets: préréglages.
        :param example_title: description de l'élément d'exemple.
        """
        intro = QLabel(INTRO_TEXT)
        intro.setWordWrap(True)
        presets_box = QGroupBox("Choix rapide")
        presets_layout = QVBoxLayout(presets_box)
        for preset in presets:
            radio = QRadioButton(f"{preset.label} — {preset.description}")
            radio.clicked.connect(lambda _c=False, k=preset.key: self.preset_selected.emit(k))
            self._preset_group.addButton(radio)
            self._preset_radios[preset.key] = radio
            presets_layout.addWidget(radio)
        self._preset_group.addButton(self._custom_radio)
        presets_layout.addWidget(self._custom_radio)

        keys_box = QGroupBox("Doivent être identiques")
        keys_content = QWidget()
        keys_content.setObjectName("MatchingKeysContent")
        keys_layout = QVBoxLayout(keys_content)
        for key_view in keys:
            example = key_view.example or "vide"
            if len(example) > MAX_EXAMPLE_LENGTH:
                example = example[:MAX_EXAMPLE_LENGTH - 1] + "…"
            check = QCheckBox(key_view.label)
            check.setToolTip(key_view.hint)
            hint = QLabel(f"Ici : <b>{html.escape(example)}</b> — {html.escape(key_view.hint)}")
            hint.setObjectName("HintLabel")
            hint.setWordWrap(True)
            self._key_checks[key_view.key] = check
            keys_layout.addWidget(check)
            keys_layout.addWidget(hint)
        keys_scroll = QScrollArea()
        keys_scroll.setWidgetResizable(True)
        keys_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        keys_scroll.setWidget(keys_content)
        keys_scroll.setMinimumHeight(260)
        QVBoxLayout(keys_box).addWidget(keys_scroll)
        tolerance_box = QGroupBox("Dans la description, ignorer")
        tolerance_layout = QVBoxLayout(tolerance_box)
        for check in (self._mask_quoted, self._mask_paths, self._mask_numbers,
                      self._ignore_case):
            tolerance_layout.addWidget(check)
        tolerance_layout.addStretch(1)
        settings_row = QHBoxLayout()
        settings_row.addWidget(keys_box, stretch=3)
        settings_row.addWidget(tolerance_box, stretch=2)

        example_box = QGroupBox(f"Ce qui sera comparé pour : {example_title}")
        example_box.setLayout(self._compared_form)

        effect_box = QGroupBox("Effet sur les logs ouverts")
        effect_layout = QVBoxLayout(effect_box)
        effect_layout.addWidget(self._effect_label)
        lists = QHBoxLayout()
        gained_column = QVBoxLayout()
        gained_column.addWidget(QLabel("Retrouveraient une justification :"))
        gained_column.addWidget(self._gained_list)
        lost_column = QVBoxLayout()
        lost_column.addWidget(QLabel("Perdraient leur justification :"))
        lost_column.addWidget(self._lost_list)
        lists.addLayout(gained_column, stretch=3)
        lists.addLayout(lost_column, stretch=2)
        effect_layout.addLayout(lists)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(presets_box)
        layout.addLayout(settings_row)
        layout.addWidget(example_box)
        layout.addWidget(effect_box, stretch=1)
        layout.addWidget(self._buttons)

    def _connect_signals(self) -> None:
        """Relie les cases au recalcul (différé) de l'aperçu."""
        for check in list(self._key_checks.values()) + [
                self._mask_numbers, self._mask_quoted, self._mask_paths, self._ignore_case]:
            check.toggled.connect(self._debounce.start)
        self._debounce.timeout.connect(lambda: self.settings_changed.emit(self.settings()))
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
