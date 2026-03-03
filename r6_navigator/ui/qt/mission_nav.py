"""Panneau de navigation des missions (QTreeWidget).

Affiche deux niveaux : Mission → Interview(s).
Émet les signaux ``mission_selected(int)`` et ``interview_selected(int)``
lors d'un clic sur un nœud.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


class MissionNavPanel(QTreeWidget):
    """QTreeWidget affichant la liste des missions et leurs entretiens."""

    mission_selected = Signal(int)    # mission_id
    interview_selected = Signal(int)  # interview_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = None
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.itemClicked.connect(self._on_item_clicked)

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    def refresh(self) -> None:
        """Recharge la liste des missions depuis la base."""
        if self._session_factory is None:
            return
        self.clear()
        from r6_navigator.services.crud_mission import get_all_missions, get_interviews

        with self._session_factory() as session:
            missions = get_all_missions(session)
            data = []
            for m in missions:
                interviews = get_interviews(session, m.id)
                data.append((m.id, m.name, [(iv.id, iv.subject_name) for iv in interviews]))

        for mission_id, mission_name, interviews in data:
            mission_item = QTreeWidgetItem([mission_name])
            mission_item.setData(0, 0x0100, ("mission", mission_id))
            for interview_id, subject_name in interviews:
                iv_item = QTreeWidgetItem([subject_name])
                iv_item.setData(0, 0x0100, ("interview", interview_id))
                mission_item.addChild(iv_item)
            self.addTopLevelItem(mission_item)
            mission_item.setExpanded(True)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        payload = item.data(0, 0x0100)
        if payload is None:
            return
        kind, entity_id = payload
        if kind == "mission":
            self.mission_selected.emit(entity_id)
        elif kind == "interview":
            self.interview_selected.emit(entity_id)
