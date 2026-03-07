"""Onglet Rapport de la fenêtre Mission.

Affiche le rapport de mission généré par l'IA (ou sauvegardé précédemment).
Bouton [Générer] → _ReportWorker (QThread) → generate_mission_report().
Bouton [Exporter DOCX] → export_mission_report().
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from r6_navigator.i18n import current_lang, t


class _ReportWorker(QThread):
    """Exécute generate_mission_report() dans un thread séparé."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, mission_id: int, session_factory, lang: str) -> None:
        super().__init__()
        self._mission_id = mission_id
        self._session_factory = session_factory
        self._lang = lang

    def run(self) -> None:
        try:
            from r6_navigator.services.ai_analyze import generate_mission_report
            report = generate_mission_report(self._mission_id, self._session_factory, self._lang)
            self.finished.emit(report)
        except Exception as exc:
            self.error.emit(str(exc))


class MissionTabRapport(QWidget):
    """Onglet de génération et d'export du rapport de mission."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = None
        self._mission_id: int | None = None
        self._worker: _ReportWorker | None = None

        self._build_ui()
        self._retranslate()

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    # ── Construction UI ────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Toolbar
        btn_row = QHBoxLayout()
        self._btn_generate = QPushButton()
        self._btn_export = QPushButton()
        btn_row.addWidget(self._btn_generate)
        btn_row.addWidget(self._btn_export)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Report viewer — rendu Markdown natif Qt
        self._text_report = QTextEdit()
        self._text_report.setReadOnly(True)
        layout.addWidget(self._text_report)

        self._btn_generate.clicked.connect(self._on_generate)
        self._btn_export.clicked.connect(self._on_export)

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _clean_report_text(text: str) -> str:
        """Supprime l'éventuelle enveloppe ```json{...}``` et retourne le Markdown brut."""
        import json
        from r6_navigator.services.llm_json import strip_markdown_json
        cleaned = strip_markdown_json(text)
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                for key in ("report", "rapport", "text", "content", "markdown"):
                    if key in data and isinstance(data[key], str) and data[key].strip():
                        return str(data[key])
                # Fallback : plus longue valeur str
                str_values = [(k, v) for k, v in data.items() if isinstance(v, str) and v.strip()]
                if str_values:
                    _, value = max(str_values, key=lambda kv: len(kv[1]))
                    return str(value)
        except (json.JSONDecodeError, ValueError):
            pass
        return cleaned if cleaned.strip() else text

    def _retranslate(self) -> None:
        self._btn_generate.setText(t("mission.btn.generate_report"))
        self._btn_export.setText(t("mission.btn.export_report"))

    # ── Public API ──────────────────────────────────────────────────

    def load_mission(self, mission_id: int) -> None:
        self._mission_id = mission_id
        self._load_existing_report()

    # ── Data ────────────────────────────────────────────────────────

    def _load_existing_report(self) -> None:
        if self._session_factory is None or self._mission_id is None:
            return
        from r6_navigator.services.crud_mission import get_mission_report
        with self._session_factory() as session:
            report = get_mission_report(session, self._mission_id, current_lang())
        if report:
            self._text_report.setMarkdown(self._clean_report_text(report.text))
        else:
            self._text_report.clear()

    # ── Generate ────────────────────────────────────────────────────

    def _on_generate(self) -> None:
        if self._mission_id is None or self._session_factory is None:
            return
        self._btn_generate.setEnabled(False)
        self._btn_generate.setText(t("mission.generating_report"))

        lang = current_lang()
        self._worker = _ReportWorker(self._mission_id, self._session_factory, lang)
        self._worker.finished.connect(self._on_generate_done)
        self._worker.error.connect(self._on_generate_error)
        self._worker.start()

    def _on_generate_done(self, report_text: str) -> None:
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText(t("mission.btn.generate_report"))

        clean_text = self._clean_report_text(report_text)

        # Save to DB — on stocke le Markdown propre (sans enveloppe JSON)
        if self._session_factory is not None and self._mission_id is not None:
            from r6_navigator.services.crud_mission import upsert_mission_report
            with self._session_factory() as session:
                upsert_mission_report(session, self._mission_id, current_lang(), clean_text)

        self._text_report.setMarkdown(clean_text)

    def _on_generate_error(self, message: str) -> None:
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText(t("mission.btn.generate_report"))
        QMessageBox.warning(self, t("mission.error.generate_report").format(message=""), message)

    # ── Export ──────────────────────────────────────────────────────

    def _on_export(self) -> None:
        if self._mission_id is None or self._session_factory is None:
            return
        report_text = self._text_report.toMarkdown().strip()
        if not report_text:
            QMessageBox.information(self, "", t("mission.no_validated_interpretations"))
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            t("mission.btn.export_report"),
            "",
            "Word Document (*.docx)",
        )
        if not path:
            return
        if not path.endswith(".docx"):
            path += ".docx"

        try:
            from r6_navigator.services.export_docx import export_mission_report
            export_mission_report(
                self._mission_id,
                self._session_factory,
                Path(path),
                current_lang(),
            )
            QMessageBox.information(self, "", f"Rapport exporté : {path}")
        except Exception as exc:
            QMessageBox.warning(self, t("error.export").format(message=""), str(exc))
