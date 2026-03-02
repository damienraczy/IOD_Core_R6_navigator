"""Onglet Informations de mission.

Affiche et édite les métadonnées de la mission sélectionnée :
client_name, description, status. Montre aussi les statistiques
(nb entretiens, verbatims, interprétations).
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from r6_navigator.db.models import Mission
from r6_navigator.i18n import t
from r6_navigator.missions.services import crud
from r6_navigator.missions.ui.forms.ui_tab_mission_info import Ui_TabMissionInfo

_STATUSES = ["active", "complete", "archived"]


class TabMissionInfo(QWidget, Ui_TabMissionInfo):
    """Onglet affichant les métadonnées d'une mission."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self._session_factory = None
        self._mission_id: str | None = None

        self.combo_status.addItems(_STATUSES)

        self._set_readonly(True)
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
            mission = crud.get_mission(session, self._mission_id)
            if mission is None:
                return
            self.entry_client_name.setText(mission.client_name)
            self.text_description.setPlainText(mission.description or "")
            idx = self.combo_status.findText(mission.status)
            if idx >= 0:
                self.combo_status.setCurrentIndex(idx)
            # Stats
            interviews = crud.list_interviews(session, self._mission_id)
            nb_interviews = len(interviews)
            nb_verbatims = sum(
                len(crud.list_verbatims(session, iv.interview_id))
                for iv in interviews
            )
            interps = crud.list_interpretations_for_mission(session, self._mission_id)
            nb_interps = len(interps)

        self.lbl_nb_interviews_val.setText(str(nb_interviews))
        self.lbl_nb_verbatims_val.setText(str(nb_verbatims))
        self.lbl_nb_interps_val.setText(str(nb_interps))

    def save(self) -> None:
        if self._session_factory is None or self._mission_id is None:
            return
        with self._session_factory() as session:
            crud.update_mission(
                session,
                self._mission_id,
                client_name=self.entry_client_name.text().strip(),
                description=self.text_description.toPlainText().strip() or None,
                status=self.combo_status.currentText(),
            )

    def set_edit_mode(self, editing: bool) -> None:
        self._set_readonly(not editing)

    def _set_readonly(self, readonly: bool) -> None:
        self.entry_client_name.setReadOnly(readonly)
        self.text_description.setReadOnly(readonly)
        self.combo_status.setEnabled(not readonly)

    def redraw(self) -> None:
        self._retranslate()
        if self._mission_id:
            self._load()

    def _retranslate(self) -> None:
        self.lbl_client_name.setText(t("mission.client_name"))
        self.lbl_status.setText(t("mission.status"))
        self.lbl_description.setText(t("mission.description"))
        self.lbl_stats_title.setText(t("mission.stats_title"))
        self.lbl_nb_interviews_key.setText(t("mission.nb_interviews"))
        self.lbl_nb_verbatims_key.setText(t("mission.nb_verbatims"))
        self.lbl_nb_interps_key.setText(t("mission.nb_interpretations"))
