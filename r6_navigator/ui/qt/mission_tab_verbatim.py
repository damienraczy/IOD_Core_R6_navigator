"""Onglet Verbatim de la fenêtre Mission.

Affiche le texte brut du verbatim d'entretien, permet de l'éditer, et lance
l'analyse IA via un ``QThread`` (_AnalyzeWorker).
Les extraits proposés par l'IA sont affichés dans une liste scrollable,
avec un bouton pour les sauvegarder en base (Extract + Interpretation pending).
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from r6_navigator.i18n import t


class _AnalyzeWorker(QThread):
    """Exécute analyze_verbatim() dans un thread séparé."""

    finished = Signal(list)   # list[AnalyzedExtract]
    error = Signal(str)

    def __init__(self, verbatim_text: str, interview_info: dict, lang: str) -> None:
        super().__init__()
        self._verbatim_text = verbatim_text
        self._interview_info = interview_info
        self._lang = lang

    def run(self) -> None:
        try:
            from r6_navigator.services.ai_analyze import analyze_verbatim
            extracts = analyze_verbatim(self._verbatim_text, self._interview_info, self._lang)
            self.finished.emit(extracts)
        except Exception as exc:
            self.error.emit(str(exc))


class MissionTabVerbatim(QWidget):
    """Onglet d'édition du verbatim et d'analyse IA."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = None
        self._interview_id: int | None = None
        self._verbatim_id: int | None = None
        self._analyzed_extracts: list = []
        self._worker: _AnalyzeWorker | None = None
        self._editing = False

        self._build_ui()
        self._retranslate()

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    # ── Construction UI ────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # Top: verbatim editor
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self._lbl_verbatim = QLabel()
        top_layout.addWidget(self._lbl_verbatim)

        self._text_verbatim = QPlainTextEdit()
        self._text_verbatim.setReadOnly(True)
        top_layout.addWidget(self._text_verbatim)

        btn_row = QHBoxLayout()
        self._btn_edit = QPushButton()
        self._btn_save = QPushButton()
        self._btn_cancel = QPushButton()
        self._btn_analyze = QPushButton()
        self._btn_save.setVisible(False)
        self._btn_cancel.setVisible(False)

        btn_row.addWidget(self._btn_edit)
        btn_row.addWidget(self._btn_save)
        btn_row.addWidget(self._btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_analyze)
        top_layout.addLayout(btn_row)

        splitter.addWidget(top)

        # Bottom: analyzed extracts
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        self._lbl_extracts = QLabel()
        bottom_layout.addWidget(self._lbl_extracts)

        self._list_extracts = QListWidget()
        bottom_layout.addWidget(self._list_extracts)

        save_row = QHBoxLayout()
        self._btn_save_extracts = QPushButton()
        self._btn_save_extracts.setEnabled(False)
        save_row.addStretch()
        save_row.addWidget(self._btn_save_extracts)
        bottom_layout.addLayout(save_row)

        splitter.addWidget(bottom)
        splitter.setSizes([300, 200])

        # Wire
        self._btn_edit.clicked.connect(self._on_edit)
        self._btn_save.clicked.connect(self._on_save)
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_analyze.clicked.connect(self._on_analyze)
        self._btn_save_extracts.clicked.connect(self._on_save_extracts)

    def _retranslate(self) -> None:
        self._lbl_verbatim.setText(t("mission.verbatim"))
        self._lbl_extracts.setText(t("mission.tab.interpretations"))
        self._btn_edit.setText(t("btn.edit"))
        self._btn_save.setText(t("btn.save"))
        self._btn_cancel.setText(t("btn.cancel"))
        self._btn_analyze.setText(t("mission.btn.analyze"))
        self._btn_save_extracts.setText(t("mission.btn.save_extracts"))

    # ── Public API ──────────────────────────────────────────────────

    def load_interview(self, interview_id: int) -> None:
        self._interview_id = interview_id
        self._load_verbatim()

    def clear(self) -> None:
        self._interview_id = None
        self._verbatim_id = None
        self._text_verbatim.setPlainText(t("mission.no_interview_selected"))
        self._list_extracts.clear()
        self._analyzed_extracts = []
        self._btn_save_extracts.setEnabled(False)

    # ── Data ────────────────────────────────────────────────────────

    def _load_verbatim(self) -> None:
        if self._session_factory is None or self._interview_id is None:
            return
        from r6_navigator.services.crud_mission import create_verbatim, get_verbatims
        with self._session_factory() as session:
            verbatims = get_verbatims(session, self._interview_id)
            if verbatims:
                v = verbatims[0]
                self._verbatim_id = v.id
                text = v.text
            else:
                # Create empty verbatim
                v = create_verbatim(session, self._interview_id, "")
                self._verbatim_id = v.id
                text = ""
        self._text_verbatim.setPlainText(text)
        self._set_readonly(True)

    def _set_readonly(self, readonly: bool) -> None:
        self._text_verbatim.setReadOnly(readonly)
        self._btn_edit.setVisible(readonly)
        self._btn_save.setVisible(not readonly)
        self._btn_cancel.setVisible(not readonly)
        self._editing = not readonly

    # ── Edit ─────────────────────────────────────────────────────────

    def _on_edit(self) -> None:
        self._set_readonly(False)

    def _on_save(self) -> None:
        if self._session_factory is None or self._verbatim_id is None:
            return
        from r6_navigator.services.crud_mission import update_verbatim
        with self._session_factory() as session:
            update_verbatim(session, self._verbatim_id, self._text_verbatim.toPlainText())
        self._set_readonly(True)

    def _on_cancel(self) -> None:
        self._load_verbatim()

    # ── Analyze ──────────────────────────────────────────────────────

    def _on_analyze(self) -> None:
        verbatim_text = self._text_verbatim.toPlainText().strip()
        if not verbatim_text:
            return

        if self._interview_id is None or self._session_factory is None:
            return

        from r6_navigator.db.models import Interview
        with self._session_factory() as session:
            iv = session.get(Interview, self._interview_id)
            if iv is None:
                return
            interview_info = {
                "subject_name": iv.subject_name,
                "subject_role": iv.subject_role or "",
                "level_code": iv.level_code or "I",
                "interview_date": iv.interview_date or "",
            }

        from r6_navigator.i18n import current_lang
        self._btn_analyze.setEnabled(False)
        self._btn_analyze.setText(t("mission.analyzing"))
        self._list_extracts.clear()
        self._analyzed_extracts = []
        self._btn_save_extracts.setEnabled(False)

        self._worker = _AnalyzeWorker(verbatim_text, interview_info, current_lang())
        self._worker.finished.connect(self._on_analyze_done)
        self._worker.error.connect(self._on_analyze_error)
        self._worker.start()

    def _on_analyze_done(self, extracts: list) -> None:
        self._btn_analyze.setEnabled(True)
        self._btn_analyze.setText(t("mission.btn.analyze"))
        self._analyzed_extracts = extracts
        self._list_extracts.clear()
        for ex in extracts:
            tag = ex.tag or "?"
            conf = f"{ex.confidence:.0%}"
            label = f"[{tag}] ({conf}) {ex.text[:80]}…" if len(ex.text) > 80 else f"[{tag}] ({conf}) {ex.text}"
            item = QListWidgetItem(label)
            item.setToolTip(ex.interpretation)
            self._list_extracts.addItem(item)
        self._btn_save_extracts.setEnabled(bool(extracts))

    def _on_analyze_error(self, message: str) -> None:
        self._btn_analyze.setEnabled(True)
        self._btn_analyze.setText(t("mission.btn.analyze"))
        QMessageBox.warning(self, t("mission.error.generate").format(message=""), message)

    def _on_save_extracts(self) -> None:
        if self._session_factory is None or self._verbatim_id is None:
            return
        from r6_navigator.services.crud_mission import create_extract, create_interpretation
        with self._session_factory() as session:
            for i, ex in enumerate(self._analyzed_extracts):
                extract = create_extract(
                    session,
                    self._verbatim_id,
                    text=ex.text,
                    tag=ex.tag,
                    display_order=i,
                )
                create_interpretation(
                    session,
                    extract_id=extract.id,
                    capacity_id=ex.capacity_id,
                    maturity_level=ex.maturity_level,
                    confidence=ex.confidence,
                    text=ex.interpretation,
                )
        self._btn_save_extracts.setEnabled(False)
        QMessageBox.information(self, "", f"{len(self._analyzed_extracts)} extraits sauvegardés.")
