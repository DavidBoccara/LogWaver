"""Façade du Modèle : état complet d'une session de travail LogWaver.

Le présentateur ne manipule que cette classe. Elle orchestre le plugin, les
logs, les justifications, l'historique d'annulation, les projets et les
exports, et publie des événements lorsque son état change.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from logwaver.constants import (
    CATEGORY_UNCLASSIFIED,
    CATEGORY_UNCLASSIFIED_LABEL,
    MATCH_KEY_CODE,
    MATCH_KEY_DESCRIPTION,
    MATCH_KEY_FILE_NAME,
    MATCH_KEY_FILE_PATH,
    MATCH_KEY_LINE,
    MATCH_KEY_TYPE,
    SOURCE_IMPORTED,
    SOURCE_MANUAL,
)
from logwaver.model.app_config import AppConfig, MatchingOptions
from logwaver.model.entities import Justification, LogEntry
from logwaver.model.entry_filter import EntryFilter, FilterCriteria
from logwaver.model.events import (
    EVENT_ENTRIES_CHANGED,
    EVENT_HISTORY_CHANGED,
    EVENT_JUSTIFICATIONS_CHANGED,
    EVENT_PROJECT_CHANGED,
    EventHub,
)
from logwaver.model.exceptions import LogWaverError
from logwaver.model.exporters.docx_exporter import DocxReportExporter
from logwaver.model.exporters.excel_exporter import ExcelReportExporter
from logwaver.model.exporters.report_data import (
    EntryReportRow,
    ReportData,
    RuleReportRow,
)
from logwaver.model.fingerprint import FingerprintBuilder
from logwaver.model.justification_index import JustificationIndex
from logwaver.model.justification_repository import JustificationRepository
from logwaver.model.log_parser import LogParser
from logwaver.model.pdf_index import DocumentationLocator, PdfLocation
from logwaver.model.plugin import PluginDefinition, PluginLoader
from logwaver.model.project_store import ProjectData, ProjectStore, RulesData
from logwaver.model.statistics import StatisticsCalculator, SummaryTable
from logwaver.model.undo import ChangeJustificationsCommand, UndoStack

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LogLoadReport:
    """Résultat de l'ouverture d'un log.

    :param path: log ouvert.
    :param entry_count: nombre d'éléments extraits.
    :param auto_justified_count: éléments justifiés automatiquement grâce
        aux justifications existantes.
    """

    path: str
    entry_count: int
    auto_justified_count: int


@dataclass(frozen=True)
class ImportReport:
    """Résultat d'un import de justifications (résolution par priorité).

    :param added: justifications nouvelles (élément encore non justifié).
    :param replaced: justifications existantes remplacées par une catégorie
        plus prioritaire (ex. « Rejeté » remplace « Justifié »).
    :param kept: justifications importées écartées car la justification
        existante est de priorité supérieure ou égale.
    :param matched_entries: éléments des logs ouverts concernés par l'import.
    :param warning: avertissement de compatibilité éventuel.
    """

    added: int
    replaced: int
    kept: int
    matched_entries: int
    warning: Optional[str]

    @property
    def imported(self) -> int:
        """Retourne le nombre de justifications effectivement appliquées."""
        return self.added + self.replaced


@dataclass(frozen=True)
class MatchingPreview:
    """Effet d'un changement de règles de correspondance sur les logs ouverts.

    :param justified_before: éléments justifiés avec les règles actuelles.
    :param justified_after: éléments justifiés avec les nouvelles règles.
    :param gained: éléments qui retrouveraient une justification, avec elle.
    :param lost: éléments qui perdraient leur justification.
    """

    justified_before: int
    justified_after: int
    gained: Tuple[Tuple[LogEntry, Justification], ...]
    lost: Tuple[LogEntry, ...]


@dataclass(frozen=True)
class ProjectOpenReport:
    """Résultat de l'ouverture d'un projet.

    :param missing_files: fichiers référencés mais introuvables.
    :param load_reports: rapports d'ouverture des logs.
    """

    missing_files: Tuple[str, ...]
    load_reports: Tuple[LogLoadReport, ...]


class WaverSession:
    """État et opérations métier d'une session de travail."""

    def __init__(self, config: AppConfig) -> None:
        """Crée une session vide.

        :param config: configuration de l'application.
        """
        self._config: AppConfig = config
        self._events: EventHub = EventHub()
        self._fingerprints = FingerprintBuilder(config.matching)
        self._strict_fingerprints = FingerprintBuilder.strict()
        self._repository = JustificationRepository()
        self._index = JustificationIndex(self._fingerprints, config.status_priority)
        self._undo_stack = UndoStack()
        self._undo_stack.add_listener(self._on_history_changed)
        self._id_counter = itertools.count(1)
        self._store = ProjectStore()
        self._plugin: Optional[PluginDefinition] = None
        self._documentation: Optional[DocumentationLocator] = None
        self._entries: List[LogEntry] = []
        self._entries_by_id: Dict[int, LogEntry] = {}
        self._log_paths: List[str] = []
        self._user_name: str = ""
        self._project_path: Optional[Path] = None
        self._metadata_dirty: bool = False

    # ================================================================ accès
    @property
    def events(self) -> EventHub:
        """Retourne le diffuseur d'événements de la session."""
        return self._events

    @property
    def config(self) -> AppConfig:
        """Retourne la configuration de l'application."""
        return self._config

    @property
    def plugin(self) -> Optional[PluginDefinition]:
        """Retourne le plugin chargé (ou ``None``)."""
        return self._plugin

    @property
    def entries(self) -> Tuple[LogEntry, ...]:
        """Retourne tous les éléments des logs ouverts."""
        return tuple(self._entries)

    @property
    def log_paths(self) -> Tuple[str, ...]:
        """Retourne les chemins des logs ouverts."""
        return tuple(self._log_paths)

    @property
    def user_name(self) -> str:
        """Retourne le nom de l'utilisateur courant."""
        return self._user_name

    @property
    def project_path(self) -> Optional[Path]:
        """Retourne le fichier projet courant (ou ``None``)."""
        return self._project_path

    @property
    def is_dirty(self) -> bool:
        """Indique si des modifications ne sont pas enregistrées."""
        return self._metadata_dirty or not self._undo_stack.is_clean

    @property
    def can_undo(self) -> bool:
        """Indique si une annulation est possible."""
        return self._undo_stack.can_undo

    @property
    def can_redo(self) -> bool:
        """Indique si un rétablissement est possible."""
        return self._undo_stack.can_redo

    @property
    def undo_text(self) -> str:
        """Retourne le libellé de la prochaine annulation."""
        return self._undo_stack.undo_text

    @property
    def redo_text(self) -> str:
        """Retourne le libellé du prochain rétablissement."""
        return self._undo_stack.redo_text

    @property
    def justifications(self) -> List[Justification]:
        """Retourne toutes les justifications stockées."""
        return self._repository.all()

    @property
    def matching_options(self) -> MatchingOptions:
        """Retourne les règles de correspondance du projet."""
        return self._fingerprints.options

    def comparable_values(self, entry: LogEntry,
                          options: Optional[MatchingOptions] = None) -> Dict[str, str]:
        """Montre les valeurs d'un élément telles qu'elles sont comparées.

        :param entry: élément concerné.
        :param options: règles à appliquer (``None`` = règles courantes).
        :return: attribut → valeur comparée (ex. description avec ‹…›).
        """
        builder = FingerprintBuilder(options) if options else self._fingerprints
        return builder.comparable_values(self._context_of(entry))

    def entry_by_id(self, entry_id: int) -> Optional[LogEntry]:
        """Retourne un élément par identifiant.

        :param entry_id: identifiant recherché.
        :return: élément, ou ``None`` s'il n'existe plus.
        """
        return self._entries_by_id.get(entry_id)

    def entries_by_ids(self, entry_ids: Iterable[int]) -> List[LogEntry]:
        """Retourne les éléments existants parmi une liste d'identifiants.

        :param entry_ids: identifiants demandés.
        :return: éléments trouvés.
        """
        return [self._entries_by_id[i] for i in entry_ids
                if i in self._entries_by_id]

    def justification_of(self, entry: LogEntry) -> Optional[Justification]:
        """Retourne la justification d'un élément.

        :param entry: élément concerné.
        :return: justification, ou ``None`` s'il n'est pas classé.
        """
        return self._index.best(entry.fingerprint)

    def entries_with_same_code(self, entry: LogEntry) -> List[LogEntry]:
        """Retourne les éléments du même outil, type et code.

        :param entry: élément de référence.
        :return: éléments correspondants (référence comprise).
        """
        return [
            other for other in self._entries
            if other.code == entry.code
            and other.entry_type == entry.entry_type
            and other.tool_name == entry.tool_name
        ]

    def filter_entries(self, criteria: FilterCriteria) -> List[LogEntry]:
        """Filtre les éléments affichés.

        :param criteria: critères de filtrage.
        :return: éléments retenus.
        """
        return EntryFilter(self.justification_of).apply(self._entries, criteria)

    def summary(self) -> SummaryTable:
        """Calcule le tableau croisé types × catégories.

        :return: tableau de synthèse.
        """
        type_names = self._plugin.type_names if self._plugin else ()
        status_ids = [status.status_id for status in self._config.statuses]
        return StatisticsCalculator(self.justification_of).summarize(
            self._entries, type_names, status_ids
        )

    # ======================================================= utilisateur
    def set_user_name(self, user_name: str) -> None:
        """Définit l'utilisateur auteur des justifications.

        :param user_name: nom saisi (espaces superflus retirés).
        :raises LogWaverError: si le nom est vide.
        """
        clean = user_name.strip()
        if not clean:
            raise LogWaverError("Le nom d'utilisateur ne peut pas être vide.")
        if clean != self._user_name:
            self._user_name = clean
            self._metadata_dirty = True
            self._events.publish(EVENT_PROJECT_CHANGED)

    # ============================================================ plugin/log
    def load_plugin(self, path: Path) -> PluginDefinition:
        """Charge un plugin et ré-analyse les logs déjà ouverts.

        :param path: fichier plugin.
        :return: plugin chargé.
        :raises PluginError: si le plugin est invalide.
        """
        plugin = PluginLoader().load(path)
        self._plugin = plugin
        self._documentation = DocumentationLocator(plugin)
        self._metadata_dirty = True
        if self._log_paths:
            self._reparse_logs()
        self._events.publish(EVENT_PROJECT_CHANGED)
        return plugin

    def open_log(self, path: Path) -> LogLoadReport:
        """Ouvre un log et applique les justifications existantes.

        Un log déjà ouvert est rechargé (ses anciens éléments sont remplacés).

        :param path: fichier de log.
        :return: rapport d'ouverture.
        :raises LogWaverError: si aucun plugin n'est chargé.
        :raises LogParsingError: si le log est illisible.
        """
        plugin = self._require_plugin()
        resolved = str(path.resolve())
        new_entries = self._create_parser(plugin).parse_file(path)
        self._remove_entries_of(resolved)
        self._entries.extend(new_entries)
        self._entries_by_id.update({e.entry_id: e for e in new_entries})
        if resolved not in self._log_paths:
            self._log_paths.append(resolved)
        self._metadata_dirty = True
        report = LogLoadReport(
            path=resolved,
            entry_count=len(new_entries),
            auto_justified_count=sum(
                1 for e in new_entries if self._index.best(e.fingerprint) is not None
            ),
        )
        LOGGER.info("Log %s : %d éléments, %d justifiés automatiquement.",
                    resolved, report.entry_count, report.auto_justified_count)
        self._events.publish(EVENT_ENTRIES_CHANGED)
        self._events.publish(EVENT_PROJECT_CHANGED)
        return report

    def close_logs(self) -> None:
        """Ferme tous les logs (les justifications sont conservées)."""
        self._entries.clear()
        self._entries_by_id.clear()
        self._log_paths.clear()
        self._metadata_dirty = True
        self._events.publish(EVENT_ENTRIES_CHANGED)
        self._events.publish(EVENT_PROJECT_CHANGED)

    # ========================================================= justification
    def classify(
        self,
        entry_ids: Sequence[int],
        status_id: str,
        text: str,
        source: str = SOURCE_MANUAL,
    ) -> int:
        """Classe des éléments dans une catégorie avec une justification.

        :param entry_ids: éléments à classer.
        :param status_id: catégorie choisie.
        :param text: texte de justification.
        :param source: origine de la justification.
        :return: nombre d'empreintes justifiées.
        :raises LogWaverError: si l'utilisateur, la catégorie ou le texte
            est manquant.
        """
        if not self._user_name:
            raise LogWaverError("Renseignez votre nom avant de justifier.")
        if self._config.find_status(status_id) is None:
            raise LogWaverError(f"Catégorie inconnue : {status_id}")
        if not text.strip():
            raise LogWaverError("La justification ne peut pas être vide.")
        entries = self.entries_by_ids(entry_ids)
        if not entries:
            return 0
        timestamp = Justification.now_iso()
        # 1. Les justifications qui s'appliquaient à ces éléments sont remplacées...
        changes: Dict[str, Optional[Justification]] = {
            rule_id: None
            for entry in entries for rule_id in self._index.rule_ids(entry.fingerprint)
        }
        # 2. ...par une justification par élément distinct (identifiant strict).
        created: Dict[str, Justification] = {}
        for entry in entries:
            context = self._context_of(entry)
            rule_id = self._strict_fingerprints.build_from_context(context)
            created[rule_id] = Justification(
                fingerprint=rule_id,
                status_id=status_id,
                text=text.strip(),
                author=self._user_name,
                timestamp=timestamp,
                source=source,
                context=context,
            )
        changes.update(created)
        label = self._config.status_label(status_id)
        self._undo_stack.push(ChangeJustificationsCommand(
            self._repository, changes,
            f"Classer {len(entries)} élément(s) en « {label} »",
        ))
        return len(created)

    def unclassify(self, entry_ids: Sequence[int]) -> int:
        """Retire la justification d'éléments (retour en « non justifiés »).

        :param entry_ids: éléments concernés.
        :return: nombre d'empreintes libérées.
        """
        changes: Dict[str, Optional[Justification]] = {
            rule_id: None
            for entry in self.entries_by_ids(entry_ids)
            for rule_id in self._index.rule_ids(entry.fingerprint)
        }
        if not changes:
            return 0
        self._undo_stack.push(ChangeJustificationsCommand(
            self._repository, changes,
            f"Retirer {len(changes)} justification(s)",
        ))
        return len(changes)

    def undo(self) -> Optional[str]:
        """Annule la dernière action.

        :return: libellé de l'action annulée, ou ``None``.
        """
        return self._undo_stack.undo()

    def redo(self) -> Optional[str]:
        """Rétablit la dernière action annulée.

        :return: libellé de l'action rétablie, ou ``None``.
        """
        return self._undo_stack.redo()

    # ===================================================== import / export
    def import_rules(self, path: Path) -> ImportReport:
        """Importe les justifications d'un collègue (fichier ``.lwj`` ou projet ``.lwp``).

        Conflits résolus par priorité : pour un même élément, la justification
        dont la catégorie a la priorité la plus élevée l'emporte (ex. « Rejeté »
        remplace « Justifié ») ; à priorité égale, la justification déjà
        présente est conservée. L'import est annulable (Ctrl+Z).

        :param path: fichier ``.lwj`` ou ``.lwp``.
        :return: rapport d'import.
        :raises ProjectFileError: si le fichier est invalide.
        """
        rules = self._store.load_rules(path)
        changes: Dict[str, Optional[Justification]] = {}
        retained: Dict[str, Justification] = {}  # clé -> gagnant après import
        added = replaced = kept = 0
        for rule in rules.justifications:
            source = rule.source if rule.source != SOURCE_MANUAL else SOURCE_IMPORTED
            incoming = rule.with_source(source)
            key = self._index.key_of(incoming)
            current = retained.get(key) or self._index.best(key)
            if current is None:
                added += 1
            elif self._config.status_priority(incoming.status_id) > \
                    self._config.status_priority(current.status_id):
                replaced += 1
                for rule_id in self._index.rule_ids(key):
                    changes.setdefault(rule_id, None)
                if current.fingerprint in changes:
                    changes[current.fingerprint] = None
            else:
                kept += 1
                continue
            changes[incoming.fingerprint] = incoming
            retained[key] = incoming
        if changes:
            self._undo_stack.push(ChangeJustificationsCommand(
                self._repository, changes,
                f"Importer {added + replaced} justification(s)",
            ))
        matched = sum(1 for e in self._entries if e.fingerprint in retained)
        return ImportReport(added, replaced, kept, matched,
                            self._context_warning(rules.justifications))

    def export_rules(self, path: Path) -> int:
        """Exporte toutes les justifications (fichier de transmission).

        :param path: fichier ``.lwj`` de destination.
        :return: nombre de justifications exportées.
        :raises ProjectFileError: si l'écriture échoue.
        """
        justifications = tuple(self._repository.all())
        self._store.save_rules(
            RulesData(
                tool_name=self._plugin.tool_name if self._plugin else "",
                matching_keys=self._fingerprints.keys,
                justifications=justifications,
                matching=self._fingerprints.options.to_dict(),
            ),
            path,
        )
        return len(justifications)

    def export_excel(self, path: Path) -> None:
        """Exporte le travail au format Excel.

        :param path: fichier ``.xlsx``.
        :raises ExportError: si l'écriture échoue.
        """
        ExcelReportExporter().export(self.build_report(), path)

    def export_docx(self, path: Path) -> None:
        """Exporte un rapport Word.

        :param path: fichier ``.docx``.
        :raises ExportError: si l'écriture échoue.
        """
        DocxReportExporter().export(self.build_report(), path)

    def build_report(self) -> ReportData:
        """Assemble les données communes aux exports.

        :return: données de rapport.
        """
        labels = {CATEGORY_UNCLASSIFIED: CATEGORY_UNCLASSIFIED_LABEL}
        labels.update({s.status_id: s.label for s in self._config.statuses})
        occurrences: Dict[str, int] = {}
        entry_rows: List[EntryReportRow] = []
        for entry in self._entries:
            justification = self.justification_of(entry)
            if justification is not None:
                occurrences[justification.fingerprint] = (
                    occurrences.get(justification.fingerprint, 0) + 1)
            entry_rows.append(EntryReportRow(
                entry_id=entry.entry_id,
                entry_type=entry.entry_type,
                code=entry.code,
                file_path=entry.file_path,
                line=entry.source_line,
                description=entry.description,
                status_label=(labels.get(justification.status_id,
                                         justification.status_id)
                              if justification else labels[CATEGORY_UNCLASSIFIED]),
                justification=justification.text if justification else "",
                author=justification.author if justification else "",
                timestamp=justification.timestamp if justification else "",
                source=justification.source if justification else "",
                log_path=entry.log_path,
                log_line_number=entry.log_line_number,
            ))
        rule_rows = tuple(
            RuleReportRow(
                fingerprint=rule.fingerprint,
                entry_type=rule.context.get(MATCH_KEY_TYPE, ""),
                code=rule.context.get(MATCH_KEY_CODE, ""),
                description=rule.context.get(MATCH_KEY_DESCRIPTION, ""),
                file_name=rule.context.get(MATCH_KEY_FILE_NAME, ""),
                status_label=labels.get(rule.status_id, rule.status_id),
                justification=rule.text,
                author=rule.author,
                timestamp=rule.timestamp,
                source=rule.source,
                occurrences=occurrences.get(rule.fingerprint, 0),
            )
            for rule in self._repository.all()
        )
        return ReportData(
            tool_name=self._plugin.tool_name if self._plugin else "",
            generated_at=datetime.now().isoformat(timespec="seconds"),
            user_name=self._user_name,
            log_paths=tuple(self._log_paths),
            summary=self.summary(),
            category_labels=labels,
            entries=tuple(entry_rows),
            rules=rule_rows,
        )

    # ============================================================== projet
    def new_project(self) -> None:
        """Réinitialise la session (le plugin et l'utilisateur sont conservés)."""
        self._entries.clear()
        self._entries_by_id.clear()
        self._log_paths.clear()
        self._repository.replace_all([])
        self._set_builder(self._config.matching)
        self._project_path = None
        self._undo_stack.clear()
        self._metadata_dirty = False
        self._publish_all()

    def save_project(self, path: Optional[Path] = None) -> Path:
        """Enregistre le projet.

        :param path: destination (``None`` = fichier projet courant).
        :return: fichier écrit.
        :raises LogWaverError: si aucun chemin n'est connu.
        :raises ProjectFileError: si l'écriture échoue.
        """
        target = path or self._project_path
        if target is None:
            raise LogWaverError("Aucun fichier projet n'est défini.")
        self._store.save_project(
            ProjectData(
                plugin_path=str(self._plugin.source_path)
                if self._plugin and self._plugin.source_path else "",
                log_paths=list(self._log_paths),
                user_name=self._user_name,
                matching_keys=self._fingerprints.keys,
                justifications=self._repository.all(),
                matching=self._fingerprints.options.to_dict(),
            ),
            target,
        )
        self._project_path = target.resolve()
        self._metadata_dirty = False
        self._undo_stack.mark_clean()
        self._events.publish(EVENT_PROJECT_CHANGED)
        return self._project_path

    def open_project(self, path: Path) -> ProjectOpenReport:
        """Ouvre un projet : plugin, logs et justifications.

        Les fichiers introuvables sont signalés sans interrompre l'ouverture.

        :param path: fichier projet.
        :return: rapport d'ouverture.
        :raises ProjectFileError: si le projet est invalide.
        :raises PluginError: si le plugin référencé est invalide.
        """
        data = self._store.load_project(path)
        missing: List[str] = []
        self._entries.clear()
        self._entries_by_id.clear()
        self._log_paths.clear()
        self._repository.replace_all(data.justifications)
        self._set_builder(MatchingOptions.from_dict(data.matching, self._config.matching)
                          if data.matching else self._config.matching)
        self._user_name = data.user_name
        if data.plugin_path:
            if Path(data.plugin_path).is_file():
                self.load_plugin(Path(data.plugin_path))
            else:
                missing.append(data.plugin_path)
        reports: List[LogLoadReport] = []
        for log_path in data.log_paths:
            if self._plugin is not None and Path(log_path).is_file():
                reports.append(self.open_log(Path(log_path)))
            else:
                missing.append(log_path)
        self._project_path = path.resolve()
        self._undo_stack.clear()
        self._metadata_dirty = False
        self._publish_all()
        warning = self._context_warning(data.justifications)
        if warning:
            LOGGER.warning(warning)
        return ProjectOpenReport(tuple(missing), tuple(reports))

    # ============================================== règles de correspondance
    def set_matching_options(self, options: MatchingOptions) -> None:
        """Change les règles de correspondance et réapplique les justifications.

        Aucune justification n'est supprimée : seules les associations
        élément ↔ justification sont recalculées, si bien que revenir aux
        règles précédentes restaure exactement l'état antérieur.

        :param options: nouvelles règles.
        :raises LogWaverError: si aucun attribut n'est comparé.
        """
        if not options.keys:
            raise LogWaverError("Cochez au moins un critère de comparaison.")
        if options == self._fingerprints.options:
            return
        self._set_builder(options)
        self._metadata_dirty = True
        LOGGER.info("Règles de correspondance : %s", options)
        self._publish_all()

    def preview_matching(self, options: MatchingOptions) -> MatchingPreview:
        """Calcule l'effet de nouvelles règles sans rien modifier.

        :param options: règles envisagées.
        :return: éléments gagnés et perdus.
        """
        builder = FingerprintBuilder(options)
        index = JustificationIndex(builder, self._config.status_priority)
        index.rebuild(self._repository.all())
        gained: List[Tuple[LogEntry, Justification]] = []
        lost: List[LogEntry] = []
        before = after = 0
        for entry in self._entries:
            current = self.justification_of(entry)
            future = index.best(builder.build_from_context(self._context_of(entry)))
            before += current is not None
            after += future is not None
            if future is not None and current is None:
                gained.append((entry, future))
            elif future is None and current is not None:
                lost.append(entry)
        return MatchingPreview(before, after, tuple(gained), tuple(lost))

    # ======================================================== documentation
    @property
    def has_documentation(self) -> bool:
        """Indique si le plugin déclare une documentation PDF."""
        return bool(self._documentation and self._documentation.is_available)

    def documentation_location(self, entry: LogEntry) -> PdfLocation:
        """Retourne le PDF et la page documentant un élément.

        :param entry: élément concerné.
        :return: emplacement dans la documentation.
        :raises DocumentationError: si la documentation est indisponible.
        """
        if self._documentation is None:
            raise LogWaverError("Aucun plugin n'est chargé.")
        return self._documentation.locate(entry.code)

    def resolve_source_file(self, entry: LogEntry) -> Optional[Path]:
        """Retrouve sur disque le fichier source cité par un élément.

        Le chemin est essayé tel quel puis relativement au répertoire du log.

        :param entry: élément concerné.
        :return: fichier existant, ou ``None`` s'il est introuvable.
        """
        if not entry.file_path:
            return None
        candidate = Path(entry.file_path).expanduser()
        candidates = [candidate]
        if not candidate.is_absolute():
            candidates.append(Path(entry.log_path).parent / candidate)
        for path in candidates:
            if path.is_file():
                return path.resolve()
        return None

    # ============================================================== interne
    def _require_plugin(self) -> PluginDefinition:
        """Retourne le plugin chargé.

        :return: plugin courant.
        :raises LogWaverError: si aucun plugin n'est chargé.
        """
        if self._plugin is None:
            raise LogWaverError("Chargez d'abord un fichier plugin.")
        return self._plugin

    def _create_parser(self, plugin: PluginDefinition) -> LogParser:
        """Crée un analyseur pour le plugin donné.

        :param plugin: plugin à utiliser.
        :return: analyseur prêt à l'emploi.
        """
        return LogParser(plugin, self._fingerprints, self._id_counter)

    def _set_builder(self, options: MatchingOptions) -> None:
        """Installe de nouvelles règles : empreintes des éléments et index recalculés.

        :param options: règles de correspondance.
        """
        self._fingerprints = FingerprintBuilder(options)
        self._index = JustificationIndex(self._fingerprints, self._config.status_priority)
        rebuilt = [replace(e, fingerprint=self._fingerprints.build(
            e.tool_name, e.entry_type, e.fields)) for e in self._entries]
        self._entries = rebuilt
        self._entries_by_id = {e.entry_id: e for e in rebuilt}
        self._index.rebuild(self._repository.all())

    def _context_warning(self, justifications: Iterable[Justification]) -> Optional[str]:
        """Signale les justifications anciennes ne permettant pas les règles actuelles.

        :param justifications: justifications à contrôler.
        :return: avertissement, ou ``None``.
        """
        needed = [key for key in (MATCH_KEY_FILE_PATH, MATCH_KEY_LINE)
                  if key in self._fingerprints.keys]
        if not needed:
            return None
        incomplete = sum(1 for j in justifications
                         if j.context and any(key not in j.context for key in needed))
        if not incomplete:
            return None
        return (f"{incomplete} justification(s) proviennent d'une ancienne version et ne "
                "connaissent pas le chemin complet ou le numéro de ligne : elles ne "
                "seront retrouvées que si ces critères sont décochés "
                "(Édition > Règles de correspondance).")

    def _remove_entries_of(self, log_path: str) -> None:
        """Retire de la session les éléments issus d'un log.

        :param log_path: chemin absolu du log.
        """
        removed = [e for e in self._entries if e.log_path == log_path]
        if not removed:
            return
        self._entries = [e for e in self._entries if e.log_path != log_path]
        for entry in removed:
            self._entries_by_id.pop(entry.entry_id, None)

    def _reparse_logs(self) -> None:
        """Ré-analyse tous les logs ouverts avec le plugin courant."""
        paths = list(self._log_paths)
        self._entries.clear()
        self._entries_by_id.clear()
        self._log_paths.clear()
        for path in paths:
            try:
                self.open_log(Path(path))
            except LogWaverError as error:
                LOGGER.error("Ré-analyse impossible de %s : %s", path, error)

    def _context_of(self, entry: LogEntry) -> Dict[str, str]:
        """Construit le contexte mémorisé avec une justification.

        :param entry: élément justifié.
        :return: valeurs brutes de tous les attributs comparables.
        """
        return FingerprintBuilder.raw_context(entry.tool_name, entry.entry_type, entry.fields)

    def _on_history_changed(self) -> None:
        """Recalcule l'index puis relaie les changements aux observateurs."""
        self._index.rebuild(self._repository.all())
        self._events.publish(EVENT_JUSTIFICATIONS_CHANGED)
        self._events.publish(EVENT_HISTORY_CHANGED)
        self._events.publish(EVENT_PROJECT_CHANGED)

    def _publish_all(self) -> None:
        """Publie tous les événements (rafraîchissement complet)."""
        for event_name in (EVENT_ENTRIES_CHANGED, EVENT_JUSTIFICATIONS_CHANGED,
                           EVENT_HISTORY_CHANGED, EVENT_PROJECT_CHANGED):
            self._events.publish(event_name)
