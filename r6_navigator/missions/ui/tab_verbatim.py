"""Onglet Verbatim.

Affiche le texte brut d'un verbatim (lecture seule) et permet de déclencher
l'analyse IA via le bouton [Analyser], qui crée des Extract + Interpretation
en base via un QThread de fond.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from r6_navigator.i18n import current_lang, t
from r6_navigator.missions.services import crud
from r6_navigator.missions.ui.forms.ui_tab_verbatim import Ui_TabVerbatim


# ---------------------------------------------------------------------------
# Worker de fond pour l'analyse IA
# ---------------------------------------------------------------------------

class _AnalyzeWorker(QThread):
    """Thread de fond pour l'analyse du verbatim via Ollama."""

    finished = Signal(list)   # list[AnalyzedExtract]
    error = Signal(str)

    def __init__(self, verbatim_id: int, session_factory, lang: str) -> None:
        super().__init__()
        self._verbatim_id = verbatim_id
        self._session_factory = session_factory
        self._lang = lang

    def run(self) -> None:
        try:
            from r6_navigator.missions.services.ai_analyze import analyze_verbatim
            result = analyze_verbatim(self._verbatim_id, self._session_factory, self._lang)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Tab
# ---------------------------------------------------------------------------

class TabVerbatim(QWidget, Ui_TabVerbatim):
    """Onglet affichant le texte brut d'un verbatim + déclenchement d'analyse IA."""

    analysis_done = Signal()  # émis quand l'analyse est terminée → rafraîchir interprétations

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self._session_factory = None
        self._verbatim_id: int | None = None
        self._worker: _AnalyzeWorker | None = None

        self.text_raw.setReadOnly(True)
        self.btn_analyze.clicked.connect(self._on_analyze)

        self._retranslate()

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    def load_verbatim(self, verbatim_id: int) -> None:
        self._verbatim_id = verbatim_id
        self._load()

    def _load(self) -> None:
        if self._session_factory is None or self._verbatim_id is None:
            return
        with self._session_factory() as session:
            verbatim = crud.get_verbatim(session, self._verbatim_id)
            if verbatim is None:
                return
            self.entry_title.setText(verbatim.title or "")
            self.text_raw.setPlainText(verbatim.raw_text or "")
            self.lbl_status_val.setText(verbatim.status)

    def save_title(self) -> None:
        if self._session_factory is None or self._verbatim_id is None:
            return
        with self._session_factory() as session:
            crud.update_verbatim(
                session, self._verbatim_id, title=self.entry_title.text().strip() or None
            )

    def import_text_from_file(self) -> None:
        """Ouvre un fichier .txt et charge son contenu dans raw_text."""
        path, _ = QFileDialog.getOpenFileName(
            self, t("mission.import_verbatim"), "", "Text files (*.txt);;All files (*)"
        )
        if not path:
            return
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, t("mission.import_verbatim"), str(exc))
            return
        if self._session_factory is not None and self._verbatim_id is not None:
            with self._session_factory() as session:
                crud.update_verbatim(
                    session, self._verbatim_id,
                    raw_text=raw,
                    source_file=path,
                )
        self.text_raw.setPlainText(raw)

    def _on_analyze(self) -> None:
        if self._verbatim_id is None or self._session_factory is None:
            return
        if self._worker and self._worker.isRunning():
            return
        self.btn_analyze.setEnabled(False)
        self.lbl_progress.setText(t("mission.analyzing"))
        self.lbl_progress.setVisible(True)

        self._worker = _AnalyzeWorker(
            self._verbatim_id, self._session_factory, current_lang()
        )
        self._worker.finished.connect(self._on_analyze_done)
        self._worker.error.connect(self._on_analyze_error)
        self._worker.start()

    def _on_analyze_done(self, result: list) -> None:
        self.btn_analyze.setEnabled(True)
        self.lbl_progress.setVisible(False)
        self.lbl_status_val.setText("analyzed")
        QMessageBox.information(
            self,
            t("mission.analyze_done_title"),
            t("mission.analyze_done_msg", n=len(result)),
        )
        self.analysis_done.emit()

    def _on_analyze_error(self, message: str) -> None:
        self.btn_analyze.setEnabled(True)
        self.lbl_progress.setVisible(False)
        QMessageBox.critical(
            self, t("error.generate"), t("error.generate", message=message)
        )

    def redraw(self) -> None:
        self._retranslate()
        if self._verbatim_id:
            self._load()

    def _retranslate(self) -> None:
        self.lbl_title.setText(t("mission.verbatim_title"))
        self.lbl_status_key.setText(t("mission.verbatim_status"))
        self.btn_analyze.setText(t("mission.btn_analyze"))
        self.lbl_raw_text.setText(t("mission.raw_text"))
        self.lbl_progress.setText(t("mission.analyzing"))
