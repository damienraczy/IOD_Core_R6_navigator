"""Panneau de détail droit pour le module Missions.

Orchestre les 4 onglets (Mission Info, Verbatim, Interprétations, Rapport)
via un QTabWidget. Charge le bon contenu quand un verbatim est sélectionné
dans le panneau de navigation.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QWidget

from r6_navigator.i18n import t
from r6_navigator.missions.services import crud


class MissionDetailPanel(QWidget):
    """Panneau droit : QTabWidget avec 4 onglets mission."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QVBoxLayout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._tab_info = None
        self._tab_verbatim = None
        self._tab_interpretations = None
        self._tab_rapport = None
        self._mission_id: str | None = None
        self._verbatim_id: int | None = None

    def set_tabs(
        self,
        tab_info,
        tab_verbatim,
        tab_interpretations,
        tab_rapport,
    ) -> None:
        self._tab_info = tab_info
        self._tab_verbatim = tab_verbatim
        self._tab_interpretations = tab_interpretations
        self._tab_rapport = tab_rapport

        self.tabs.addTab(tab_info, t("mission.tab_info"))
        self.tabs.addTab(tab_verbatim, t("mission.tab_verbatim"))
        self.tabs.addTab(tab_interpretations, t("mission.tab_interpretations"))
        self.tabs.addTab(tab_rapport, t("mission.tab_rapport"))

        # When analysis is done, refresh interpretations tab
        tab_verbatim.analysis_done.connect(
            lambda: self._tab_interpretations.load_verbatim(self._verbatim_id)
            if self._verbatim_id else None
        )

    def load_verbatim(self, verbatim_id: int, session_factory) -> None:
        """Charge un verbatim + sa mission dans tous les onglets."""
        self._verbatim_id = verbatim_id

        with session_factory() as session:
            verbatim = crud.get_verbatim(session, verbatim_id)
            if verbatim is None:
                return
            self._mission_id = verbatim.interview.mission.mission_id

        if self._tab_info:
            self._tab_info.load_mission(self._mission_id)
        if self._tab_verbatim:
            self._tab_verbatim.load_verbatim(verbatim_id)
        if self._tab_interpretations:
            self._tab_interpretations.load_verbatim(verbatim_id)
        if self._tab_rapport:
            self._tab_rapport.load_mission(self._mission_id)

    def load_mission(self, mission_id: str) -> None:
        """Charge une mission dans les onglets info et rapport (sans verbatim)."""
        self._mission_id = mission_id
        self._verbatim_id = None
        if self._tab_info:
            self._tab_info.load_mission(mission_id)
        if self._tab_rapport:
            self._tab_rapport.load_mission(mission_id)

    def redraw(self) -> None:
        self._retranslate()
        for tab in (self._tab_info, self._tab_verbatim, self._tab_interpretations, self._tab_rapport):
            if tab:
                tab.redraw()

    def _retranslate(self) -> None:
        self.tabs.setTabText(0, t("mission.tab_info"))
        self.tabs.setTabText(1, t("mission.tab_verbatim"))
        self.tabs.setTabText(2, t("mission.tab_interpretations"))
        self.tabs.setTabText(3, t("mission.tab_rapport"))
