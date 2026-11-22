"""Tests des priorités, des règles de correspondance et des extensions de plugin."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from logwaver.model.app_config import MatchingOptions
from logwaver.model.exceptions import LogWaverError
from logwaver.model.fingerprint import FingerprintBuilder
from logwaver.model.matching_presets import PRESETS, find_preset
from logwaver.model.plugin import PluginLoader, PluginWriter, normalize_extensions
from logwaver.model.plugin_detector import (
    REASON_CONTENT,
    REASON_EXTENSION,
    PluginDetector,
    PluginExtensionRegistrar,
)
from logwaver.model.session import WaverSession
from tests.helpers import LOG_A_PATH, LOG_B_PATH, PLUGIN_PATH, create_session, load_config

PRESET_BY_KEY = {preset.key: preset for preset in PRESETS}


def ids_with_code(session: WaverSession, code: str) -> list:
    """Retourne les éléments d'un code.

    :param session: session concernée.
    :param code: code recherché.
    :return: identifiants.
    """
    return [e.entry_id for e in session.entries if e.code == code]


def status_of(session: WaverSession, code: str) -> set:
    """Retourne les catégories des éléments d'un code.

    :param session: session concernée.
    :param code: code recherché.
    :return: ensemble des catégories (``None`` = non justifié).
    """
    return {getattr(session.justification_of(e), "status_id", None)
            for e in session.entries if e.code == code}


class PriorityTests(unittest.TestCase):
    """Résolution des conflits par priorité des catégories."""

    def export(self, status_id: str, directory: str) -> Path:
        """Exporte une justification de CL245 dans la catégorie donnée.

        :param status_id: catégorie.
        :param directory: dossier temporaire.
        :return: fichier de justifications.
        """
        other = create_session(user_name="Collègue")
        other.classify(ids_with_code(other, "CL245"), status_id, "avis du collègue")
        target = Path(directory) / f"{status_id}.lwj"
        other.export_rules(target)
        return target

    def test_rejected_overrides_justified(self) -> None:
        """« Rejeté » (50) l'emporte sur « Justifié » (20) ; Ctrl+Z restaure."""
        session = create_session()
        session.classify(ids_with_code(session, "CL245"), "justified", "ok pour moi")
        with tempfile.TemporaryDirectory() as directory:
            report = session.import_rules(self.export("rejected", directory))
        self.assertEqual((report.replaced, report.added, report.kept), (2, 0, 0))
        self.assertEqual(status_of(session, "CL245"), {"rejected"})
        session.undo()
        self.assertEqual(status_of(session, "CL245"), {"justified"})

    def test_lower_priority_does_not_override(self) -> None:
        """Une justification moins prioritaire est écartée."""
        session = create_session()
        session.classify(ids_with_code(session, "CL245"), "rejected", "à corriger")
        with tempfile.TemporaryDirectory() as directory:
            report = session.import_rules(self.export("justified", directory))
        self.assertEqual((report.kept, report.replaced), (2, 0))
        self.assertEqual(status_of(session, "CL245"), {"rejected"})

    def test_equal_priority_keeps_existing(self) -> None:
        """À priorité égale, la justification déjà présente est conservée."""
        session = create_session()
        session.classify(ids_with_code(session, "CL245"), "justified", "le mien")
        with tempfile.TemporaryDirectory() as directory:
            report = session.import_rules(self.export("justified", directory))
        self.assertEqual(report.kept, 2)
        texts = {session.justification_of(e).text for e in session.entries if e.code == "CL245"}
        self.assertEqual(texts, {"le mien"})

    def test_priorities_are_read_from_configuration(self) -> None:
        """Les priorités de la configuration d'exemple placent « Rejeté » en tête."""
        config = load_config()
        self.assertGreater(config.status_priority("rejected"),
                           config.status_priority("justified"))


class MatchingRulesTests(unittest.TestCase):
    """Règles de correspondance réglables."""

    def test_by_code_preset_extends_justification(self) -> None:
        """« Par code seulement » : une justification couvre tout le code."""
        session = create_session()
        first = next(e for e in session.entries if e.code == "CL300")
        session.classify([first.entry_id], "justified", "variables inutilisées tolérées")
        self.assertEqual(status_of(session, "CL300"), {"justified", None})
        options = PRESET_BY_KEY["by_code"].options
        preview = session.preview_matching(options)
        self.assertEqual(len(preview.gained), 1)
        session.set_matching_options(options)
        self.assertEqual(status_of(session, "CL300"), {"justified"})

    def test_changing_rules_back_restores_state(self) -> None:
        """Assouplir puis revenir aux règles d'origine ne perd rien."""
        session = create_session()
        session.classify(ids_with_code(session, "CL245")[:1], "justified", "a")
        original = session.matching_options
        session.set_matching_options(PRESET_BY_KEY["by_code"].options)
        session.set_matching_options(original)
        self.assertEqual(status_of(session, "CL245"), {"justified", None})
        self.assertEqual(len(session.justifications), 1)

    def test_tolerant_preset_matches_other_file_names(self) -> None:
        """Mode tolérant : « le fichier ‹…› est introuvable » vaut pour tout fichier cité."""
        session_a = create_session()
        session_a.classify(ids_with_code(session_a, "CL245"), "justified", "fichiers optionnels")
        session_b = create_session(LOG_B_PATH, user_name="Bob")
        with tempfile.TemporaryDirectory() as directory:
            rules = Path(directory) / "a.lwj"
            session_a.export_rules(rules)
            session_b.import_rules(rules)
        self.assertEqual(status_of(session_b, "CL245"), {"justified", None})
        session_b.set_matching_options(PRESET_BY_KEY["tolerant"].options)
        self.assertEqual(status_of(session_b, "CL245"), {"justified"})

    def test_comparable_values_show_what_is_ignored(self) -> None:
        """La description comparée montre les parties ignorées."""
        session = create_session()
        entry = next(e for e in session.entries if e.code == "CL245")
        values = session.comparable_values(entry, PRESET_BY_KEY["tolerant"].options)
        self.assertEqual(values["description"], "le fichier ‹…› est introuvable")

    def test_masks_do_not_touch_french_apostrophes(self) -> None:
        """« l'erreur d'accès » n'est pas pris pour du texte entre apostrophes."""
        builder = FingerprintBuilder(MatchingOptions(mask_quoted=True))
        values = builder.comparable_values({"description": "l'erreur d'accès 'x' ici"})
        self.assertEqual(values["description"], "l'erreur d'accès ‹…› ici")

    def test_rules_saved_with_project(self) -> None:
        """Les règles de correspondance sont enregistrées dans le projet."""
        session = create_session()
        session.set_matching_options(PRESET_BY_KEY["tolerant"].options)
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "p.lwp"
            session.save_project(project)
            reopened = WaverSession(load_config())
            reopened.open_project(project)
        self.assertEqual(find_preset(reopened.matching_options).key, "tolerant")

    def test_reads_version_1_project(self) -> None:
        """Un projet en version 1 (sans règles enregistrées) reste lisible."""
        legacy = {
            "format": "logwaver-project", "version": 1, "plugin_path": str(PLUGIN_PATH),
            "log_paths": [str(LOG_A_PATH)], "user_name": "Ancien",
            "matching_keys": ["tool", "type", "code", "description", "file_name"],
            "justifications": [{
                "fingerprint": "ancien-id", "status_id": "justified", "text": "v1",
                "author": "Ancien", "timestamp": "2026-11-20T10:00:00", "source": "manuelle",
                "context": {"tool": "TINTIN", "type": "Warning", "code": "CL512",
                            "description": "conversion implicite de double vers int",
                            "file_name": "engine.c"}}],
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "v1.lwp"
            project.write_text(json.dumps(legacy), encoding="utf-8")
            session = WaverSession(load_config())
            session.open_project(project)
        self.assertEqual(status_of(session, "CL512"), {"justified"})

    def test_at_least_one_key_required(self) -> None:
        """Des règles sans aucun critère sont refusées."""
        session = create_session()
        with self.assertRaises(LogWaverError):
            session.set_matching_options(MatchingOptions(keys=()))


class PluginExtensionTests(unittest.TestCase):
    """Extensions de fichiers déclarées dans les plugins."""

    def test_normalize_extensions(self) -> None:
        """Les saisies libres sont normalisées."""
        self.assertEqual(normalize_extensions("log, .MX ;*.Out"), (".log", ".mx", ".out"))

    def test_round_trip(self) -> None:
        """Les extensions survivent à l'écriture du plugin."""
        plugin = PluginLoader().load(PLUGIN_PATH)
        reloaded = PluginLoader().load_from_text(PluginWriter().to_text(plugin))
        self.assertEqual(reloaded.file_extensions, (".log", ".tlog"))

    def test_extension_designates_plugin_and_is_remembered(self) -> None:
        """Une extension mémorisée désigne le plugin ; les commentaires sont conservés."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            plugin_copy = folder / "tintin.ini"
            shutil.copy(PLUGIN_PATH, plugin_copy)
            log = folder / "build.mx"
            log.write_text(LOG_A_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            detector = PluginDetector([folder])
            self.assertEqual(detector.detect(log).reason, REASON_CONTENT)
            PluginExtensionRegistrar().add_extension(plugin_copy, "mx")
            self.assertEqual(detector.detect(log).reason, REASON_EXTENSION)
            text = plugin_copy.read_text(encoding="utf-8")
        self.assertIn("file_extensions = .log, .tlog, .mx", text)
        self.assertIn("# Plugin LogWaver pour l'outil TINTIN", text)

    def test_generic_extension_does_not_hide_content_match(self) -> None:
        """Un plugin qui déclare l'extension mais ne reconnaît rien cède au contenu."""
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            shutil.copy(PLUGIN_PATH, folder / "tintin.ini")
            (folder / "autre.ini").write_text(
                "[plugin]\ntool_name = AUTRE\nelement_types = W\nfile_extensions = .mx\n"
                "[type:W]\ndetect = ^ZZZ\nfields = code\nregex.code = ZZZ(\\d+)\n",
                encoding="utf-8")
            log = folder / "build.mx"
            log.write_text(LOG_A_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            candidate = PluginDetector([folder]).detect(log)
        self.assertEqual(candidate.definition.tool_name, "TINTIN")


if __name__ == "__main__":
    unittest.main()
