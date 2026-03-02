"""Fenêtre principale du module Missions.

Lancée depuis R6NavigatorApp via le bouton [Missions].
Compose : MissionNavPanel (gauche) + MissionDetailPanel (droite)
avec une toolbar en haut pour la gestion des missions.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from r6_navigator.i18n import t
from r6_navigator.missions.services import crud
from r6_navigator.missions.ui.detail import MissionDetailPanel
from r6_navigator.missions.ui.nav import MissionNavPanel
from r6_navigator.missions.ui.tab_interpretations import TabInterpretations
from r6_navigator.missions.ui.tab_info import TabMissionInfo
from r6_navigator.missions.ui.tab_rapport import TabRapport
from r6_navigator.missions.ui.tab_verbatim import TabVerbatim


class MissionApp(QMainWindow):
    """Fenêtre dédiée à la gestion et l'analyse des missions clients."""

    def __init__(self, session_factory, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._current_verbatim_id: int | None = None
        self._current_mission_id: str | None = None

        self._build_ui()
        self._retranslate()
        self.nav_panel.populate()

    # ────────────────────────────────────────────────────────
    # UI construction
    # ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setMinimumSize(1000, 650)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Toolbar
        root.addWidget(self._build_toolbar())

        # Content area: nav (left) + detail (right)
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Navigation panel
        self.nav_panel = MissionNavPanel()
        self.nav_panel.setFixedWidth(280)
        self.nav_panel.set_session_factory(self._session_factory)
        content_layout.addWidget(self.nav_panel)

        # Separator
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(vsep)

        # Detail panel
        self.tab_info = TabMissionInfo()
        self.tab_verbatim = TabVerbatim()
        self.tab_interpretations = TabInterpretations()
        self.tab_rapport = TabRapport()

        for component in (self.tab_info, self.tab_verbatim, self.tab_interpretations, self.tab_rapport):
            component.set_session_factory(self._session_factory)

        self.detail_panel = MissionDetailPanel()
        self.detail_panel.set_tabs(
            self.tab_info,
            self.tab_verbatim,
            self.tab_interpretations,
            self.tab_rapport,
        )
        content_layout.addWidget(self.detail_panel, 1)
        root.addWidget(content, 1)

        # Connect nav signals
        self.nav_panel.verbatim_selected.connect(self._on_verbatim_selected)

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.btn_new_mission = QPushButton()
        self.btn_new_interview = QPushButton()
        self.btn_import_verbatim = QPushButton()

        layout.addWidget(self.btn_new_mission)
        layout.addWidget(self.btn_new_interview)
        layout.addWidget(self.btn_import_verbatim)
        layout.addStretch()

        self.btn_new_mission.clicked.connect(self._on_new_mission)
        self.btn_new_interview.clicked.connect(self._on_new_interview)
        self.btn_import_verbatim.clicked.connect(self._on_import_verbatim)

        return toolbar

    def _retranslate(self) -> None:
        self.setWindowTitle(t("mission.window_title"))
        self.btn_new_mission.setText(t("mission.btn_new_mission"))
        self.btn_new_interview.setText(t("mission.btn_new_interview"))
        self.btn_import_verbatim.setText(t("mission.btn_import_verbatim"))

    # ────────────────────────────────────────────────────────
    # Navigation
    # ────────────────────────────────────────────────────────

    def _on_verbatim_selected(self, verbatim_id: int) -> None:
        self._current_verbatim_id = verbatim_id
        self.detail_panel.load_verbatim(verbatim_id, self._session_factory)

    # ────────────────────────────────────────────────────────
    # Toolbar actions
    # ────────────────────────────────────────────────────────

    def _on_new_mission(self) -> None:
        name, ok = QInputDialog.getText(
            self, t("mission.new_mission_title"), t("mission.client_name")
        )
        if not ok or not name.strip():
            return
        with self._session_factory() as session:
            mission = crud.create_mission(session, client_name=name.strip())
        self._current_mission_id = mission.mission_id
        self.nav_panel.populate()
        self.detail_panel.load_mission(mission.mission_id)

    def _on_new_interview(self) -> None:
        if self._current_mission_id is None:
            # Try to derive from current verbatim context
            if self._current_verbatim_id is not None:
                with self._session_factory() as session:
                    v = crud.get_verbatim(session, self._current_verbatim_id)
                    if v:
                        self._current_mission_id = v.interview.mission.mission_id

        if self._current_mission_id is None:
            QMessageBox.information(self, t("mission.btn_new_interview"), t("mission.no_mission_selected"))
            return

        name, ok = QInputDialog.getText(
            self, t("mission.new_interview_title"), t("mission.interviewee_name")
        )
        if not ok or not name.strip():
            return
        with self._session_factory() as session:
            crud.create_interview(
                session,
                mission_id=self._current_mission_id,
                interviewee_name=name.strip(),
            )
        self.nav_panel.populate()

    def _on_import_verbatim(self) -> None:
        """Importe un fichier .txt comme nouveau verbatim."""
        if self._current_mission_id is None:
            QMessageBox.information(self, t("mission.import_verbatim"), t("mission.no_mission_selected"))
            return

        # Choose interview
        with self._session_factory() as session:
            interviews = crud.list_interviews(session, self._current_mission_id)
        if not interviews:
            QMessageBox.information(self, t("mission.import_verbatim"), t("mission.no_interview_for_mission"))
            return

        interview_labels = [
            f"{iv.interviewee_name} ({iv.interviewee_role or '—'})"
            for iv in interviews
        ]
        label, ok = QInputDialog.getItem(
            self, t("mission.import_verbatim"), t("mission.select_interview"),
            interview_labels, 0, False
        )
        if not ok:
            return
        interview_idx = interview_labels.index(label)
        interview_id = interviews[interview_idx].interview_id

        # Choose file
        path, _ = QFileDialog.getOpenFileName(
            self, t("mission.import_verbatim"), "",
            "Text files (*.txt);;All files (*)"
        )
        if not path:
            return

        try:
            raw = Path(path).read_text(encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self, t("mission.import_verbatim"), str(exc))
            return

        title = Path(path).stem
        with self._session_factory() as session:
            verbatim = crud.create_verbatim(
                session,
                interview_id=interview_id,
                raw_text=raw,
                title=title,
                source_file=path,
            )

        self.nav_panel.populate()
        self._on_verbatim_selected(verbatim.verbatim_id)
        self.nav_panel.select_verbatim(verbatim.verbatim_id)
