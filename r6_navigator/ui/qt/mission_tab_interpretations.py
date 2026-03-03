"""Onglet Interprétations de la fenêtre Mission.

Affiche toutes les interprétations de la mission sélectionnée dans un QTableWidget.
Permet de valider, rejeter ou corriger chaque interprétation.
Filtres disponibles : tous / en attente / validés / rejetés.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from r6_navigator.i18n import t


class MissionTabInterpretations(QWidget):
    """Onglet d'affichage et de validation des interprétations."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = None
        self._mission_id: int | None = None
        self._rows: list[dict] = []  # raw data for filtering

        self._build_ui()
        self._retranslate()

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    # ── Construction UI ────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Filter row
        filter_row = QHBoxLayout()
        self._lbl_filter = QLabel()
        self._combo_filter = QComboBox()
        filter_row.addWidget(self._lbl_filter)
        filter_row.addWidget(self._combo_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        self._combo_filter.currentIndexChanged.connect(self._apply_filter)

    def _retranslate(self) -> None:
        self._lbl_filter.setText("Filtre :")
        self._combo_filter.clear()
        self._combo_filter.addItem(t("mission.filter.all"), "all")
        self._combo_filter.addItem(t("mission.filter.pending"), "pending")
        self._combo_filter.addItem(t("mission.filter.validated"), "validated")
        self._combo_filter.addItem(t("mission.filter.rejected"), "rejected")
        self._table.setHorizontalHeaderLabels([
            t("mission.col.extract"),
            t("mission.col.capacity"),
            t("mission.col.level"),
            t("mission.col.confidence"),
            t("mission.col.status"),
            t("mission.col.actions"),
        ])

    # ── Public API ──────────────────────────────────────────────────

    def load_mission(self, mission_id: int) -> None:
        self._mission_id = mission_id
        self._reload_data()

    def refresh(self) -> None:
        self._reload_data()

    # ── Data ────────────────────────────────────────────────────────

    def _reload_data(self) -> None:
        if self._session_factory is None or self._mission_id is None:
            return
        from r6_navigator.services.crud_mission import get_all_mission_interpretations
        with self._session_factory() as session:
            interps = get_all_mission_interpretations(session, self._mission_id)
            self._rows = [
                {
                    "id": i.id,
                    "text": i.text,
                    "capacity_id": i.capacity_id or "",
                    "maturity_level": i.maturity_level or "",
                    "confidence": i.confidence,
                    "status": i.status,
                }
                for i in interps
            ]
        self._apply_filter()

    def _apply_filter(self) -> None:
        filter_val = self._combo_filter.currentData() or "all"
        if filter_val == "all":
            rows = self._rows
        else:
            rows = [r for r in self._rows if r["status"] == filter_val]
        self._rebuild_table(rows)

    def _rebuild_table(self, rows: list[dict]) -> None:
        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)

            text_item = QTableWidgetItem(row["text"][:60] + "…" if len(row["text"]) > 60 else row["text"])
            text_item.setToolTip(row["text"])
            self._table.setItem(r, 0, text_item)
            self._table.setItem(r, 1, QTableWidgetItem(row["capacity_id"]))
            self._table.setItem(r, 2, QTableWidgetItem(row["maturity_level"]))
            conf = f"{row['confidence']:.0%}" if row["confidence"] is not None else ""
            self._table.setItem(r, 3, QTableWidgetItem(conf))
            status_key = f"mission.status.{row['status']}"
            self._table.setItem(r, 4, QTableWidgetItem(t(status_key) if t(status_key) != status_key else row["status"]))

            # Actions cell
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(4)

            btn_validate = QPushButton(t("mission.btn.validate"))
            btn_reject = QPushButton(t("mission.btn.reject"))
            btn_correct = QPushButton(t("mission.btn.correct"))

            interp_id = row["id"]
            btn_validate.clicked.connect(lambda _, iid=interp_id: self._on_validate(iid))
            btn_reject.clicked.connect(lambda _, iid=interp_id: self._on_reject(iid))
            btn_correct.clicked.connect(lambda _, iid=interp_id: self._on_correct(iid))

            actions_layout.addWidget(btn_validate)
            actions_layout.addWidget(btn_reject)
            actions_layout.addWidget(btn_correct)
            self._table.setCellWidget(r, 5, actions_widget)

        self._table.resizeColumnsToContents()

    # ── Actions ─────────────────────────────────────────────────────

    def _on_validate(self, interp_id: int) -> None:
        self._update_status(interp_id, "validated")

    def _on_reject(self, interp_id: int) -> None:
        self._update_status(interp_id, "rejected")

    def _on_correct(self, interp_id: int) -> None:
        row = next((r for r in self._rows if r["id"] == interp_id), None)
        current_text = row["text"] if row else ""
        new_text, ok = QInputDialog.getMultiLineText(
            self,
            t("mission.dialog.correct.title"),
            t("mission.dialog.correct.message"),
            current_text,
        )
        if ok and new_text.strip():
            from r6_navigator.services.crud_mission import update_interpretation_status
            with self._session_factory() as session:
                update_interpretation_status(session, interp_id, "corrected", new_text.strip())
            self._reload_data()

    def _update_status(self, interp_id: int, status: str) -> None:
        if self._session_factory is None:
            return
        from r6_navigator.services.crud_mission import update_interpretation_status
        with self._session_factory() as session:
            update_interpretation_status(session, interp_id, status)
        self._reload_data()
