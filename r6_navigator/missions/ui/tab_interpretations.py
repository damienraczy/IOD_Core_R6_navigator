"""Onglet Interprétations.

Affiche les extraits et interprétations d'un verbatim dans un QTableWidget.
Permet de valider [✓], rejeter [✗] ou corriger [✎] chaque interprétation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from r6_navigator.i18n import t
from r6_navigator.missions.services import crud
from r6_navigator.missions.ui.forms.ui_tab_interpretations import Ui_TabInterpretations


# ---------------------------------------------------------------------------
# Correction dialog
# ---------------------------------------------------------------------------

class _CorrectionDialog(QDialog):
    """Dialogue de correction d'une interprétation."""

    def __init__(self, interp, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("mission.correct_title"))
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.entry_capacity = QLineEdit()
        self.entry_capacity.setText(interp.capacity_id or "")
        form.addRow(t("mission.col_capacity"), self.entry_capacity)

        self.spin_score = QSpinBox()
        self.spin_score.setRange(0, 10)
        self.spin_score.setValue(interp.maturity_score or 0)
        form.addRow(t("mission.col_score"), self.spin_score)

        self.entry_direction = QLineEdit()
        self.entry_direction.setText(interp.direction or "")
        self.entry_direction.setPlaceholderText("INS / OK / EXC")
        form.addRow(t("mission.col_direction"), self.entry_direction)

        self.entry_justification = QLineEdit()
        self.entry_justification.setText(interp.justification or "")
        form.addRow(t("mission.col_justification"), self.entry_justification)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> dict:
        return {
            "corrected_capacity_id": self.entry_capacity.text().strip() or None,
            "corrected_maturity_score": self.spin_score.value(),
            "corrected_direction": self.entry_direction.text().strip().upper() or None,
            "corrected_justification": self.entry_justification.text().strip() or None,
        }


# ---------------------------------------------------------------------------
# Tab
# ---------------------------------------------------------------------------

class TabInterpretations(QWidget, Ui_TabInterpretations):
    """Onglet affichant les interprétations d'un verbatim."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setupUi(self)
        self._session_factory = None
        self._verbatim_id: int | None = None
        self._interp_data: list[dict] = []

        self._setup_table()
        self._retranslate()

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    def load_verbatim(self, verbatim_id: int) -> None:
        self._verbatim_id = verbatim_id
        self._load()

    def _setup_table(self) -> None:
        table = self.table_interpretations
        table.setColumnCount(6)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)

    def _load(self) -> None:
        if self._session_factory is None or self._verbatim_id is None:
            return
        self._interp_data = []
        with self._session_factory() as session:
            extracts = crud.list_extracts(session, self._verbatim_id)
            for extract in extracts:
                interps = crud.list_interpretations(session, extract.extract_id)
                for interp in interps:
                    self._interp_data.append({
                        "interp_id": interp.interpretation_id,
                        "extract_text": extract.raw_text,
                        "capacity_id": interp.capacity_id,
                        "score": interp.maturity_score,
                        "direction": interp.direction,
                        "justification": interp.justification,
                        "status": interp.status,
                    })
        self._rebuild_table()
        self._update_stats()

    def _rebuild_table(self) -> None:
        table = self.table_interpretations
        table.setRowCount(0)
        for row_idx, row in enumerate(self._interp_data):
            table.insertRow(row_idx)
            table.setItem(row_idx, 0, QTableWidgetItem(row["extract_text"][:120]))
            table.setItem(row_idx, 1, QTableWidgetItem(row["capacity_id"] or "—"))
            table.setItem(row_idx, 2, QTableWidgetItem(str(row["score"]) if row["score"] is not None else "—"))
            table.setItem(row_idx, 3, QTableWidgetItem(row["direction"] or "—"))
            table.setItem(row_idx, 4, QTableWidgetItem(row["justification"] or ""))

            # Status + action buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(2)

            status_label = QLabel(row["status"])
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            actions_layout.addWidget(status_label)

            btn_validate = QPushButton("✓")
            btn_validate.setFixedWidth(28)
            btn_validate.setToolTip(t("mission.btn_validate"))
            btn_validate.clicked.connect(lambda _, iid=row["interp_id"]: self._on_validate(iid))
            actions_layout.addWidget(btn_validate)

            btn_reject = QPushButton("✗")
            btn_reject.setFixedWidth(28)
            btn_reject.setToolTip(t("mission.btn_reject"))
            btn_reject.clicked.connect(lambda _, iid=row["interp_id"]: self._on_reject(iid))
            actions_layout.addWidget(btn_reject)

            btn_correct = QPushButton("✎")
            btn_correct.setFixedWidth(28)
            btn_correct.setToolTip(t("mission.btn_correct"))
            btn_correct.clicked.connect(lambda _, iid=row["interp_id"]: self._on_correct(iid))
            actions_layout.addWidget(btn_correct)

            table.setCellWidget(row_idx, 5, actions_widget)

    def _update_stats(self) -> None:
        nb_total = len(self._interp_data)
        nb_validated = sum(1 for r in self._interp_data if r["status"] == "validated")
        nb_rejected = sum(1 for r in self._interp_data if r["status"] == "rejected")
        self.lbl_stats.setText(
            t("mission.interp_stats", total=nb_total, validated=nb_validated, rejected=nb_rejected)
        )

    def _on_validate(self, interp_id: int) -> None:
        if self._session_factory is None:
            return
        with self._session_factory() as session:
            crud.validate_interpretation(session, interp_id)
        self._load()

    def _on_reject(self, interp_id: int) -> None:
        if self._session_factory is None:
            return
        with self._session_factory() as session:
            crud.reject_interpretation(session, interp_id)
        self._load()

    def _on_correct(self, interp_id: int) -> None:
        if self._session_factory is None:
            return
        with self._session_factory() as session:
            interp = crud.get_interpretation(session, interp_id)
            if interp is None:
                return

        dlg = _CorrectionDialog(interp, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.get_values()
        with self._session_factory() as session:
            crud.correct_interpretation(session, interp_id, **values)
        self._load()

    def redraw(self) -> None:
        self._retranslate()
        if self._verbatim_id:
            self._load()

    def _retranslate(self) -> None:
        headers = [
            t("mission.col_extract"),
            t("mission.col_capacity"),
            t("mission.col_score"),
            t("mission.col_direction"),
            t("mission.col_justification"),
            t("table.col.actions"),
        ]
        self.table_interpretations.setHorizontalHeaderLabels(headers)
        self._update_stats()
