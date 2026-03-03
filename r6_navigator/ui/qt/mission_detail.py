"""Panneau de détail des missions (QTabWidget 4 onglets).

Orchestre les 4 onglets : Infos, Verbatim, Interprétations, Rapport.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget

from r6_navigator.i18n import t
from r6_navigator.ui.qt.mission_tab_info import MissionTabInfo
from r6_navigator.ui.qt.mission_tab_verbatim import MissionTabVerbatim
from r6_navigator.ui.qt.mission_tab_interpretations import MissionTabInterpretations
from r6_navigator.ui.qt.mission_tab_rapport import MissionTabRapport


class MissionDetailPanel(QTabWidget):
    """QTabWidget contenant les 4 onglets du module Mission."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tab_info = MissionTabInfo()
        self._tab_verbatim = MissionTabVerbatim()
        self._tab_interpretations = MissionTabInterpretations()
        self._tab_rapport = MissionTabRapport()

        self.addTab(self._tab_info, "")
        self.addTab(self._tab_verbatim, "")
        self.addTab(self._tab_interpretations, "")
        self.addTab(self._tab_rapport, "")

        self._retranslate()

    def set_session_factory(self, factory) -> None:
        for tab in (self._tab_info, self._tab_verbatim, self._tab_interpretations, self._tab_rapport):
            tab.set_session_factory(factory)

    def _retranslate(self) -> None:
        self.setTabText(0, t("mission.tab.info"))
        self.setTabText(1, t("mission.tab.verbatim"))
        self.setTabText(2, t("mission.tab.interpretations"))
        self.setTabText(3, t("mission.tab.rapport"))

    def load_mission(self, mission_id: int) -> None:
        """Charge les données d'une mission dans tous les onglets applicables."""
        self._tab_info.load_mission(mission_id)
        self._tab_verbatim.clear()
        self._tab_interpretations.load_mission(mission_id)
        self._tab_rapport.load_mission(mission_id)

    def load_interview(self, interview_id: int) -> None:
        """Charge les données d'un entretien dans les onglets Infos et Verbatim."""
        self._tab_info.load_interview(interview_id)
        self._tab_verbatim.load_interview(interview_id)
