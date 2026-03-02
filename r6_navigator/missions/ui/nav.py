"""Panneau de navigation gauche pour le module Missions.

Affiche un QTreeWidget hiérarchique :
  Mission (client_name)
    └─ Entretien (interviewee_name)
          └─ Verbatim (title ou date, avec indicateur de statut)

Émet ``verbatim_selected(int)`` quand l'utilisateur clique sur un verbatim.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from r6_navigator.i18n import t
from r6_navigator.missions.services import crud


# Status icons for verbatims
_STATUS_ICONS = {
    "pending": "○",
    "analyzed": "●",
    "validated": "✓",
}


class MissionNavPanel(QTreeWidget):
    """QTreeWidget listant missions → entretiens → verbatims."""

    verbatim_selected = Signal(int)  # verbatim_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = None
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.itemClicked.connect(self._on_item_clicked)

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    def populate(self) -> None:
        """Charge toutes les missions depuis la DB et peuple l'arbre."""
        if self._session_factory is None:
            return
        self.clear()
        with self._session_factory() as session:
            missions = crud.list_missions(session)
            for mission in missions:
                mission_item = QTreeWidgetItem([mission.client_name])
                mission_item.setData(0, 1000, ("mission", mission.mission_id))
                interviews = crud.list_interviews(session, mission.mission_id)
                for interview in interviews:
                    label = interview.interviewee_name
                    if interview.interviewee_role:
                        label += f" ({interview.interviewee_role})"
                    interview_item = QTreeWidgetItem([label])
                    interview_item.setData(0, 1000, ("interview", interview.interview_id))
                    verbatims = crud.list_verbatims(session, interview.interview_id)
                    for verbatim in verbatims:
                        icon = _STATUS_ICONS.get(verbatim.status, "○")
                        v_label = verbatim.title or f"Verbatim {verbatim.verbatim_id}"
                        verbatim_item = QTreeWidgetItem([f"{icon} {v_label}"])
                        verbatim_item.setData(0, 1000, ("verbatim", verbatim.verbatim_id))
                        interview_item.addChild(verbatim_item)
                    mission_item.addChild(interview_item)
                self.addTopLevelItem(mission_item)
                mission_item.setExpanded(True)

    def redraw(self) -> None:
        """Repopulate the tree (called on language change)."""
        self.populate()

    def select_verbatim(self, verbatim_id: int) -> None:
        """Sélectionne visuellement un verbatim dans l'arbre."""
        def _find(item: QTreeWidgetItem) -> bool:
            data = item.data(0, 1000)
            if data and data[0] == "verbatim" and data[1] == verbatim_id:
                self.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if _find(item.child(i)):
                    return True
            return False

        for i in range(self.topLevelItemCount()):
            if _find(self.topLevelItem(i)):
                break

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, 1000)
        if data and data[0] == "verbatim":
            self.verbatim_selected.emit(data[1])
