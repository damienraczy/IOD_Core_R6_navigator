"""Onglet Rapport de mission.

Affiche le rapport narratif S-O-I et permet de :
- Générer un nouveau rapport via IA ([Générer])
- Exporter le rapport en DOCX ([Exporter DOCX])
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from r6_navigator.i18n import current_lang, t
from r6_navigator.missions.services import crud
from r6_navigator.missions.ui.forms.ui_tab_rapport import Ui_TabRapport


# ---------------------------------------------------------------------------
# Worker de génération de rapport (thread de fond)
# ---------------------------------------------------------------------------

class _ReportWorker(QThread):
    """Thread de fond pour la génération du rapport via Ollama."""

    finished = Signal(str)   # content
    error = Signal(str)

    def __init__(self, mission_id: str, session_factory, lang: str) -> None:
        super().__init__()
        self._mission_id = mission_id
        self._session_factory = session_factory
        self._lang = lang

    def run(self) -> None:
        try:
            from r6_navigator.missions.services.ai_analyze import generate_mission_report
            content = generate_mission_report(
                self._mission_id, self._session_factory, self._lang
            )
            self.finished.emit(content)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Tab
# ---------------------------------------------------------------------------

class TabRapport(QWidget, Ui_TabRapport):
    """Onglet affichant et permettant de générer le rapport narratif de mission."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self._session_factory = None
        self._mission_id: str | None = None
        self._worker: _ReportWorker | None = None

        self.btn_generate_report.clicked.connect(self._on_generate)
        self.btn_export_docx.clicked.connect(self._on_export_docx)

        self._retranslate()

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    def load_mission(self, mission_id: str) -> None:
        self._mission_id = mission_id
        self._load()

    def _load(self) -> None:
        if self._session_factory is None or self._mission_id is None:
            return
        with self._session_factory() as session:
            report = crud.get_latest_report(session, self._mission_id)
        if report:
            self.text_report.setPlainText(report.content or "")
            self.lbl_status.setText(t("mission.report_status", status=report.status))
        else:
            self.text_report.setPlainText("")
            self.lbl_status.setText(t("mission.no_report"))

    def _on_generate(self) -> None:
        if self._mission_id is None or self._session_factory is None:
            return
        if self._worker and self._worker.isRunning():
            return
        self.btn_generate_report.setEnabled(False)
        self.lbl_progress.setText(t("mission.generating_report"))
        self.lbl_progress.setVisible(True)

        self._worker = _ReportWorker(
            self._mission_id, self._session_factory, current_lang()
        )
        self._worker.finished.connect(self._on_generate_done)
        self._worker.error.connect(self._on_generate_error)
        self._worker.start()

    def _on_generate_done(self, content: str) -> None:
        self.btn_generate_report.setEnabled(True)
        self.lbl_progress.setVisible(False)
        self.text_report.setPlainText(content)
        self._load()  # refresh status label

    def _on_generate_error(self, message: str) -> None:
        self.btn_generate_report.setEnabled(True)
        self.lbl_progress.setVisible(False)
        QMessageBox.critical(
            self, t("error.generate"), t("error.generate", message=message)
        )

    def _on_export_docx(self) -> None:
        if self._mission_id is None or self._session_factory is None:
            return
        output_path, _ = QFileDialog.getSaveFileName(
            self, t("btn.export_docx"), f"rapport_{self._mission_id[:8]}.docx",
            "Word Document (*.docx)"
        )
        if not output_path:
            return
        try:
            from r6_navigator.missions.services.export_docx import export_mission_report_docx
            export_mission_report_docx(
                self._mission_id,
                self._session_factory,
                Path(output_path),
                current_lang(),
            )
            QMessageBox.information(
                self, t("btn.export_docx"),
                t("dialog.save_db.success", path=output_path)
            )
        except Exception as exc:
            QMessageBox.critical(
                self, t("btn.export_docx"),
                t("error.export", message=str(exc))
            )

    def redraw(self) -> None:
        self._retranslate()
        if self._mission_id:
            self._load()

    def _retranslate(self) -> None:
        self.btn_generate_report.setText(t("mission.btn_generate_report"))
        self.btn_export_docx.setText(t("btn.export_docx"))
        self.lbl_progress.setText(t("mission.generating_report"))
