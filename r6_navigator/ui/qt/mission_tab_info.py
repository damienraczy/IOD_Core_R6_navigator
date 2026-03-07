"""Onglet Infos de la fenêtre Mission.

Affiche et permet d'éditer les champs de la mission (nom, client, consultant,
date de début, objectif) et les champs de l'entretien sélectionné (interviewé,
rôle, date, niveau R6, notes).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from r6_navigator.i18n import t


class MissionTabInfo(QWidget):
    """Onglet affichant les informations de mission et d'entretien."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = None
        self._mission_id: int | None = None
        self._interview_id: int | None = None
        self._editing_mission = False
        self._editing_interview = False

        self._build_ui()
        self._retranslate()

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    # ── Construction UI ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setSpacing(12)

        # ── Mission section ─────────────────────────────────────────
        self._grp_mission = QGroupBox()
        form_mission = QFormLayout(self._grp_mission)

        self._edit_name = QLineEdit()
        self._edit_client = QLineEdit()
        self._edit_consultant = QLineEdit()
        self._edit_start_date = QLineEdit()
        self._edit_objective = QPlainTextEdit()
        self._edit_objective.setMaximumHeight(80)

        self._lbl_name = QLabel()
        self._lbl_client = QLabel()
        self._lbl_consultant = QLabel()
        self._lbl_start_date = QLabel()
        self._lbl_objective = QLabel()

        form_mission.addRow(self._lbl_name, self._edit_name)
        form_mission.addRow(self._lbl_client, self._edit_client)
        form_mission.addRow(self._lbl_consultant, self._edit_consultant)
        form_mission.addRow(self._lbl_start_date, self._edit_start_date)
        form_mission.addRow(self._lbl_objective, self._edit_objective)

        # Mission buttons
        mission_btns = QHBoxLayout()
        self._btn_edit_mission = QPushButton()
        self._btn_save_mission = QPushButton()
        self._btn_cancel_mission = QPushButton()
        self._btn_save_mission.setVisible(False)
        self._btn_cancel_mission.setVisible(False)
        mission_btns.addWidget(self._btn_edit_mission)
        mission_btns.addWidget(self._btn_save_mission)
        mission_btns.addWidget(self._btn_cancel_mission)
        mission_btns.addStretch()
        form_mission.addRow("", mission_btns)

        layout.addWidget(self._grp_mission)
        self._set_mission_fields_readonly(True)

        # ── Interview section ───────────────────────────────────────
        self._grp_interview = QGroupBox()
        form_iv = QFormLayout(self._grp_interview)

        self._edit_subject = QLineEdit()
        self._edit_role = QLineEdit()
        self._edit_iv_date = QLineEdit()
        self._edit_notes = QPlainTextEdit()
        self._edit_notes.setMaximumHeight(80)

        self._lbl_subject = QLabel()
        self._lbl_role = QLabel()
        self._lbl_iv_date = QLabel()
        self._lbl_notes = QLabel()

        form_iv.addRow(self._lbl_subject, self._edit_subject)
        form_iv.addRow(self._lbl_role, self._edit_role)
        form_iv.addRow(self._lbl_iv_date, self._edit_iv_date)
        form_iv.addRow(self._lbl_notes, self._edit_notes)

        # Interview buttons
        iv_btns = QHBoxLayout()
        self._btn_edit_iv = QPushButton()
        self._btn_save_iv = QPushButton()
        self._btn_cancel_iv = QPushButton()
        self._btn_save_iv.setVisible(False)
        self._btn_cancel_iv.setVisible(False)
        iv_btns.addWidget(self._btn_edit_iv)
        iv_btns.addWidget(self._btn_save_iv)
        iv_btns.addWidget(self._btn_cancel_iv)
        iv_btns.addStretch()
        form_iv.addRow("", iv_btns)

        layout.addWidget(self._grp_interview)
        layout.addStretch()
        self._set_interview_fields_readonly(True)

        # Wire buttons
        self._btn_edit_mission.clicked.connect(self._on_edit_mission)
        self._btn_save_mission.clicked.connect(self._on_save_mission)
        self._btn_cancel_mission.clicked.connect(self._on_cancel_mission)
        self._btn_edit_iv.clicked.connect(self._on_edit_iv)
        self._btn_save_iv.clicked.connect(self._on_save_iv)
        self._btn_cancel_iv.clicked.connect(self._on_cancel_iv)

    def _retranslate(self) -> None:
        self._grp_mission.setTitle(t("mission.name"))
        self._lbl_name.setText(t("mission.name"))
        self._lbl_client.setText(t("mission.client"))
        self._lbl_consultant.setText(t("mission.consultant"))
        self._lbl_start_date.setText(t("mission.start_date"))
        self._lbl_objective.setText(t("mission.objective"))
        self._btn_edit_mission.setText(t("btn.edit"))
        self._btn_save_mission.setText(t("btn.save"))
        self._btn_cancel_mission.setText(t("btn.cancel"))

        self._grp_interview.setTitle(t("mission.interview.subject"))
        self._lbl_subject.setText(t("mission.interview.subject"))
        self._lbl_role.setText(t("mission.interview.role"))
        self._lbl_iv_date.setText(t("mission.interview.date"))
        self._lbl_notes.setText(t("mission.interview.notes"))
        self._btn_edit_iv.setText(t("btn.edit"))
        self._btn_save_iv.setText(t("btn.save"))
        self._btn_cancel_iv.setText(t("btn.cancel"))

    def _set_mission_fields_readonly(self, readonly: bool) -> None:
        for w in (self._edit_name, self._edit_client, self._edit_consultant, self._edit_start_date):
            w.setReadOnly(readonly)
        self._edit_objective.setReadOnly(readonly)

    def _set_interview_fields_readonly(self, readonly: bool) -> None:
        for w in (self._edit_subject, self._edit_role, self._edit_iv_date):
            w.setReadOnly(readonly)
        self._edit_notes.setReadOnly(readonly)

    # ── Public API ──────────────────────────────────────────────────

    def load_mission(self, mission_id: int) -> None:
        self._mission_id = mission_id
        self._interview_id = None
        self._load_mission_data()
        self._grp_interview.setVisible(False)

    def load_interview(self, interview_id: int) -> None:
        from r6_navigator.services.crud_mission import get_interviews

        self._interview_id = interview_id
        with self._session_factory() as session:
            from r6_navigator.services.crud_mission import get_mission
            from r6_navigator.db.models import Interview
            iv = session.get(Interview, interview_id)
            if iv:
                self._mission_id = iv.mission_id
                self._load_mission_data()
                self._load_interview_data(iv)
                self._grp_interview.setVisible(True)

    # ── Private data loaders ────────────────────────────────────────

    def _load_mission_data(self) -> None:
        if self._session_factory is None or self._mission_id is None:
            return
        from r6_navigator.services.crud_mission import get_mission
        with self._session_factory() as session:
            m = get_mission(session, self._mission_id)
        if m is None:
            return
        self._edit_name.setText(m.name or "")
        self._edit_client.setText(m.client or "")
        self._edit_consultant.setText(m.consultant or "")
        self._edit_start_date.setText(m.start_date or "")
        self._edit_objective.setPlainText(m.objective or "")
        self._set_mission_fields_readonly(True)
        self._btn_save_mission.setVisible(False)
        self._btn_cancel_mission.setVisible(False)
        self._btn_edit_mission.setVisible(True)
        self._editing_mission = False

    def _load_interview_data(self, iv) -> None:
        self._edit_subject.setText(iv.subject_name or "")
        self._edit_role.setText(iv.subject_role or "")
        self._edit_iv_date.setText(iv.interview_date or "")
        self._edit_notes.setPlainText(iv.notes or "")
        self._set_interview_fields_readonly(True)
        self._btn_save_iv.setVisible(False)
        self._btn_cancel_iv.setVisible(False)
        self._btn_edit_iv.setVisible(True)
        self._editing_interview = False

    # ── Mission edit ────────────────────────────────────────────────

    def _on_edit_mission(self) -> None:
        self._editing_mission = True
        self._set_mission_fields_readonly(False)
        self._btn_edit_mission.setVisible(False)
        self._btn_save_mission.setVisible(True)
        self._btn_cancel_mission.setVisible(True)

    def _on_save_mission(self) -> None:
        if self._session_factory is None or self._mission_id is None:
            return
        from r6_navigator.services.crud_mission import update_mission
        with self._session_factory() as session:
            update_mission(
                session,
                self._mission_id,
                name=self._edit_name.text().strip(),
                client=self._edit_client.text().strip() or None,
                consultant=self._edit_consultant.text().strip() or None,
                start_date=self._edit_start_date.text().strip() or None,
                objective=self._edit_objective.toPlainText().strip() or None,
            )
        self._set_mission_fields_readonly(True)
        self._btn_edit_mission.setVisible(True)
        self._btn_save_mission.setVisible(False)
        self._btn_cancel_mission.setVisible(False)
        self._editing_mission = False

    def _on_cancel_mission(self) -> None:
        self._load_mission_data()

    # ── Interview edit ──────────────────────────────────────────────

    def _on_edit_iv(self) -> None:
        self._editing_interview = True
        self._set_interview_fields_readonly(False)
        self._btn_edit_iv.setVisible(False)
        self._btn_save_iv.setVisible(True)
        self._btn_cancel_iv.setVisible(True)

    def _on_save_iv(self) -> None:
        if self._session_factory is None or self._interview_id is None:
            return
        from r6_navigator.services.crud_mission import update_interview
        with self._session_factory() as session:
            update_interview(
                session,
                self._interview_id,
                subject_name=self._edit_subject.text().strip(),
                subject_role=self._edit_role.text().strip() or None,
                interview_date=self._edit_iv_date.text().strip() or None,
                notes=self._edit_notes.toPlainText().strip() or None,
            )
        self._set_interview_fields_readonly(True)
        self._btn_edit_iv.setVisible(True)
        self._btn_save_iv.setVisible(False)
        self._btn_cancel_iv.setVisible(False)
        self._editing_interview = False

    def _on_cancel_iv(self) -> None:
        if self._interview_id is None:
            return
        from r6_navigator.db.models import Interview
        with self._session_factory() as session:
            iv = session.get(Interview, self._interview_id)
        if iv:
            self._load_interview_data(iv)
