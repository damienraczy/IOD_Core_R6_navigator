"""Fenêtre principale du module Missions.

Compose le MissionNavPanel (gauche) et le MissionDetailPanel (droite).
Barre d'outils : [Nouvelle mission] [Nouvel entretien] [Supprimer] [Exporter rapport].
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from r6_navigator.i18n import t
from r6_navigator.ui.qt.mission_detail import MissionDetailPanel
from r6_navigator.ui.qt.mission_nav import MissionNavPanel


class MissionApp(QMainWindow):
    """Fenêtre autonome du module Missions."""

    def __init__(self, session_factory, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = session_factory
        self._current_mission_id: int | None = None
        self._current_interview_id: int | None = None

        self._build_ui()
        self._retranslate()
        self._nav.refresh()

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory
        self._nav.set_session_factory(factory)
        self._detail.set_session_factory(factory)

    # ── Construction UI ────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._nav = MissionNavPanel()
        self._nav.set_session_factory(self._session_factory)
        self._nav.setMinimumWidth(200)
        splitter.addWidget(self._nav)

        self._detail = MissionDetailPanel()
        self._detail.set_session_factory(self._session_factory)
        splitter.addWidget(self._detail)
        splitter.setSizes([250, 650])

        root.addWidget(splitter, 1)

        # Toolbar
        root.addWidget(self._build_toolbar())

        # Signals
        self._nav.mission_selected.connect(self._on_mission_selected)
        self._nav.interview_selected.connect(self._on_interview_selected)

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._btn_new_mission = QPushButton()
        self._btn_new_interview = QPushButton()
        self._btn_delete = QPushButton()

        layout.addWidget(self._btn_new_mission)
        layout.addWidget(self._btn_new_interview)
        layout.addWidget(self._btn_delete)
        layout.addStretch()

        self._btn_new_mission.clicked.connect(self._on_new_mission)
        self._btn_new_interview.clicked.connect(self._on_new_interview)
        self._btn_delete.clicked.connect(self._on_delete)

        return toolbar

    def _retranslate(self) -> None:
        self.setWindowTitle(t("mission.window_title"))
        self._btn_new_mission.setText(t("mission.new"))
        self._btn_new_interview.setText(t("mission.interview.new"))
        self._btn_delete.setText(t("btn.delete"))

    # ── Signals ─────────────────────────────────────────────────────

    def _on_mission_selected(self, mission_id: int) -> None:
        self._current_mission_id = mission_id
        self._current_interview_id = None
        self._detail.load_mission(mission_id)

    def _on_interview_selected(self, interview_id: int) -> None:
        self._current_interview_id = interview_id
        # Derive mission from interview
        from r6_navigator.db.models import Interview
        with self._session_factory() as session:
            iv = session.get(Interview, interview_id)
            if iv:
                self._current_mission_id = iv.mission_id
        self._detail.load_interview(interview_id)

    # ── Toolbar actions ──────────────────────────────────────────────

    def _on_new_mission(self) -> None:
        name, ok = QInputDialog.getText(self, t("mission.new"), t("mission.name"))
        if not ok or not name.strip():
            return
        from r6_navigator.services.crud_mission import create_mission
        with self._session_factory() as session:
            m = create_mission(session, name.strip())
        self._nav.refresh()
        # Select the newly created mission
        self._current_mission_id = m.id
        self._detail.load_mission(m.id)

    def _on_new_interview(self) -> None:
        if self._current_mission_id is None:
            QMessageBox.information(self, "", "Sélectionnez d'abord une mission.")
            return
        subject, ok = QInputDialog.getText(
            self, t("mission.interview.new"), t("mission.interview.subject")
        )
        if not ok or not subject.strip():
            return
        from r6_navigator.services.crud_mission import create_interview
        with self._session_factory() as session:
            iv = create_interview(session, self._current_mission_id, subject.strip())
        self._nav.refresh()
        self._current_interview_id = iv.id
        self._detail.load_interview(iv.id)

    def _on_delete(self) -> None:
        if self._current_mission_id is None:
            return
        from r6_navigator.services.crud_mission import delete_interview, delete_mission, get_mission
        with self._session_factory() as session:
            m = get_mission(session, self._current_mission_id)
            name = m.name if m else str(self._current_mission_id)

        if self._current_interview_id is not None:
            reply = QMessageBox.question(
                self,
                t("btn.delete"),
                f"Supprimer l'entretien sélectionné ?",
            )
            if reply == QMessageBox.StandardButton.Yes:
                with self._session_factory() as session:
                    delete_interview(session, self._current_interview_id)
                self._current_interview_id = None
                self._nav.refresh()
        else:
            msg = t("mission.dialog.delete_mission.message").format(name=name)
            reply = QMessageBox.question(self, t("mission.dialog.delete_mission.title"), msg)
            if reply == QMessageBox.StandardButton.Yes:
                with self._session_factory() as session:
                    delete_mission(session, self._current_mission_id)
                self._current_mission_id = None
                self._current_interview_id = None
                self._nav.refresh()
