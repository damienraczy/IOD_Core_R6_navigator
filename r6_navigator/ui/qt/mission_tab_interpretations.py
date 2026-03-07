"""Onglet Interprétations de la fenêtre Mission.

Affiche toutes les interprétations de la mission sélectionnée dans un QTableWidget.
Permet de valider, rejeter ou corriger chaque interprétation.
Filtres disponibles : tous / en attente / validés / rejetés.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeyEvent

from r6_navigator.i18n import t


class _ConfirmDeleteDialog(QDialog):
    """Dialogue de confirmation de suppression avec raccourcis clavier.

    Y / O → confirmer (Oui/Yes), N → annuler.
    """

    def __init__(self, message: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("dialog.delete.title"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Y, Qt.Key.Key_O):
            self.accept()
        elif key == Qt.Key.Key_N:
            self.reject()
        else:
            super().keyPressEvent(event)


class _CorrectionDialog(QDialog):
    """Dialogue de correction d'une interprétation.

    Affiche l'extrait source en lecture seule (référence) et
    l'interprétation dans une zone éditable.
    """

    def __init__(self, current_text: str, extract_text: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("mission.dialog.correct.title"))
        self.resize(900, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Extrait source — lecture seule
        layout.addWidget(QLabel(t("mission.dialog.correct.extract_label")))
        self._extract_view = QPlainTextEdit()
        self._extract_view.setPlainText(extract_text)
        self._extract_view.setReadOnly(True)
        self._extract_view.setMinimumHeight(120)
        self._extract_view.setMaximumHeight(160)
        layout.addWidget(self._extract_view)

        # Interprétation — éditable
        layout.addWidget(QLabel(t("mission.dialog.correct.message")))
        self._editor = QPlainTextEdit()
        self._editor.setPlainText(current_text)
        self._editor.setMinimumHeight(220)
        layout.addWidget(self._editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def text(self) -> str:
        return self._editor.toPlainText()


class MissionTabInterpretations(QWidget):
    """Onglet d'affichage et de validation des interprétations."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._session_factory = None
        self._mission_id: int | None = None
        self._rows: list[dict] = []  # raw data for filtering
        self._filter_interview_id: int | None = None  # None = pas de filtre entretien

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
        self._btn_delete_interview = QPushButton()
        self._btn_delete_all = QPushButton()
        filter_row.addWidget(self._btn_delete_interview)
        filter_row.addWidget(self._btn_delete_all)
        layout.addLayout(filter_row)

        # Table — 9 colonnes :
        # 0:Entretien  1:Extrait  2:Interprétation  3:Capacité  4:Niveau
        # 5:Confiance  6:Halliday  7:Statut  8:Actions
        self._table = QTableWidget()
        self._table.setColumnCount(9)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # Entretien
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)          # Extrait
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)          # Interprétation
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Capacité
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Niveau
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Confiance
        hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)            # Halliday
        hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents) # Statut
        hdr.setSectionResizeMode(8, QHeaderView.ResizeMode.Fixed)            # Actions
        self._table.setColumnWidth(6, 60)
        self._table.setColumnWidth(8, 170)
        layout.addWidget(self._table)

        self._btn_delete_interview.setEnabled(False)
        self._combo_filter.currentIndexChanged.connect(self._apply_filter)
        self._btn_delete_interview.clicked.connect(self._on_delete_interview)
        self._btn_delete_all.clicked.connect(self._on_delete_all)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def _retranslate(self) -> None:
        self._lbl_filter.setText("Filtre :")
        self._combo_filter.clear()
        self._combo_filter.addItem(t("mission.filter.all"), "all")
        self._combo_filter.addItem(t("mission.filter.pending"), "pending")
        self._combo_filter.addItem(t("mission.filter.validated"), "validated")
        self._combo_filter.addItem(t("mission.filter.rejected"), "rejected")
        self._btn_delete_interview.setText(t("mission.btn.delete_interview_interps"))
        self._btn_delete_all.setText(t("mission.btn.delete_all_interps"))
        self._table.setHorizontalHeaderLabels([
            t("mission.col.interview"),
            t("mission.col.extract"),
            t("mission.col.interpretation"),
            t("mission.col.capacity"),
            t("mission.col.level"),
            t("mission.col.confidence"),
            t("mission.col.halliday"),
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
                    "extract_text": i.extract.text if i.extract else "",
                    "interview_id": (
                        i.extract.verbatim.interview.id
                        if i.extract and i.extract.verbatim and i.extract.verbatim.interview
                        else None
                    ),
                    "subject_name": (
                        i.extract.verbatim.interview.subject_name
                        if i.extract and i.extract.verbatim and i.extract.verbatim.interview
                        else ""
                    ),
                    "interview_date": (
                        i.extract.verbatim.interview.interview_date or ""
                        if i.extract and i.extract.verbatim and i.extract.verbatim.interview
                        else ""
                    ),
                    "capacity_id": i.capacity_id or "",
                    "maturity_level": i.maturity_level or "",
                    "confidence": i.confidence,
                    "status": i.status,
                    "halliday_ok": i.extract.halliday_ok if i.extract else None,
                    "halliday_note": i.extract.halliday_note if i.extract else None,
                }
                for i in interps
            ]
        self._filter_interview_id = None
        self._apply_filter()

    def _apply_filter(self) -> None:
        filter_val = self._combo_filter.currentData() or "all"
        rows = self._rows if filter_val == "all" else [r for r in self._rows if r["status"] == filter_val]
        if self._filter_interview_id is not None:
            rows = [r for r in rows if r.get("interview_id") == self._filter_interview_id]
        self._btn_delete_interview.setEnabled(self._filter_interview_id is not None)
        self._rebuild_table(rows)

    def _rebuild_table(self, rows: list[dict]) -> None:
        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            interp_id = row["id"]

            # Col 0 — Entretien (sujet + date)
            interview_label = row["subject_name"]
            if row["interview_date"]:
                interview_label += f"\n{row['interview_date']}"
            interview_item = QTableWidgetItem(interview_label)
            interview_item.setData(Qt.ItemDataRole.UserRole, interp_id)
            interview_item.setData(Qt.ItemDataRole.UserRole + 1, row.get("interview_id"))
            interview_item.setToolTip(t("mission.filter.interview_tooltip"))
            self._table.setItem(r, 0, interview_item)

            # Col 1 — Extrait (texte verbatim source)
            extract_text = row["extract_text"]
            extract_item = QTableWidgetItem(
                extract_text[:80] + "…" if len(extract_text) > 80 else extract_text
            )
            extract_item.setToolTip(extract_text)
            self._table.setItem(r, 1, extract_item)

            # Col 2 — Interprétation
            interp_text = row["text"]
            interp_item = QTableWidgetItem(
                interp_text[:80] + "…" if len(interp_text) > 80 else interp_text
            )
            interp_item.setToolTip(interp_text)
            self._table.setItem(r, 2, interp_item)

            self._table.setItem(r, 3, QTableWidgetItem(row["capacity_id"]))
            self._table.setItem(r, 4, QTableWidgetItem(row["maturity_level"]))
            conf = f"{row['confidence']:.0%}" if row["confidence"] is not None else ""
            self._table.setItem(r, 5, QTableWidgetItem(conf))

            # Col 6 — Halliday
            halliday_item = QTableWidgetItem()
            halliday_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            halliday_ok = row.get("halliday_ok")
            if halliday_ok is False:
                halliday_item.setText("!")
                halliday_item.setForeground(QColor("red"))
                halliday_item.setToolTip(
                    row.get("halliday_note") or t("mission.halliday.inconsistent")
                )
            elif halliday_ok is True:
                halliday_item.setText("OK")
                halliday_item.setForeground(QColor("green"))
                halliday_item.setToolTip(t("mission.halliday.consistent"))
            self._table.setItem(r, 6, halliday_item)

            status_key = f"mission.status.{row['status']}"
            self._table.setItem(r, 7, QTableWidgetItem(t(status_key) if t(status_key) != status_key else row["status"]))

            # Col 8 — Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(4)

            btn_validate = QPushButton("✅")
            btn_reject = QPushButton("❌")
            btn_correct = QPushButton("✏️")
            btn_delete = QPushButton("🗑️")
            for btn, tip in (
                (btn_validate, t("mission.btn.validate")),
                (btn_reject,   t("mission.btn.reject")),
                (btn_correct,  t("mission.btn.correct")),
                (btn_delete,   t("btn.delete")),
            ):
                btn.setToolTip(tip)
                btn.setFixedWidth(36)

            btn_validate.clicked.connect(lambda _, iid=interp_id: self._on_validate(iid))
            btn_reject.clicked.connect(lambda _, iid=interp_id: self._on_reject(iid))
            btn_correct.clicked.connect(lambda _, iid=interp_id: self._on_correct(iid))
            btn_delete.clicked.connect(lambda _, iid=interp_id: self._on_delete(iid))

            actions_layout.addWidget(btn_validate)
            actions_layout.addWidget(btn_reject)
            actions_layout.addWidget(btn_correct)
            actions_layout.addWidget(btn_delete)
            self._table.setCellWidget(r, 8, actions_widget)

    # ── Actions ─────────────────────────────────────────────────────

    def _on_validate(self, interp_id: int) -> None:
        self._update_status(interp_id, "validated")

    def _on_reject(self, interp_id: int) -> None:
        self._update_status(interp_id, "rejected")

    def _on_correct(self, interp_id: int) -> None:
        row = next((r for r in self._rows if r["id"] == interp_id), None)
        if row is None:
            return
        current_text = row["text"]
        extract_text = row["extract_text"]
        dlg = _CorrectionDialog(current_text, extract_text, parent=self)
        if dlg.exec() == _CorrectionDialog.DialogCode.Accepted:
            new_text = dlg.text().strip()
            if new_text and new_text != current_text:
                from r6_navigator.services.crud_mission import update_interpretation_status
                with self._session_factory() as session:
                    update_interpretation_status(session, interp_id, "corrected", new_text)
                self._reload_data()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Clic simple sur col 0 (Entretien) → filtre sur cet entretien (toggle)."""
        if col != 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        interview_id = item.data(Qt.ItemDataRole.UserRole + 1)
        if interview_id is None:
            return
        if self._filter_interview_id == interview_id:
            self._filter_interview_id = None   # deuxième clic → tout afficher
        else:
            self._filter_interview_id = interview_id
        self._apply_filter()

    def _on_cell_double_clicked(self, row: int, _col: int) -> None:
        """Double-clic sur n'importe quelle cellule → ouvre la correction."""
        item = self._table.item(row, 0)
        if item is None:
            return
        interp_id = item.data(Qt.ItemDataRole.UserRole)
        if interp_id is None:
            return
        self._on_correct(interp_id)

    def _on_delete(self, interp_id: int) -> None:
        dlg = _ConfirmDeleteDialog(t("mission.dialog.delete_interpretation.message"), parent=self)
        if dlg.exec() == _ConfirmDeleteDialog.DialogCode.Accepted:
            from r6_navigator.services.crud_mission import delete_interpretation
            with self._session_factory() as session:
                delete_interpretation(session, interp_id)
            self._reload_data()

    def _on_delete_all(self) -> None:
        if self._session_factory is None or self._mission_id is None:
            return
        dlg = _ConfirmDeleteDialog(t("mission.dialog.delete_all_interps.message"), parent=self)
        if dlg.exec() == _ConfirmDeleteDialog.DialogCode.Accepted:
            from r6_navigator.services.crud_mission import delete_all_mission_interpretations
            with self._session_factory() as session:
                delete_all_mission_interpretations(session, self._mission_id)
            self._reload_data()

    def _on_delete_interview(self) -> None:
        if self._session_factory is None or self._filter_interview_id is None:
            return
        dlg = _ConfirmDeleteDialog(t("mission.dialog.delete_interview_interps.message"), parent=self)
        if dlg.exec() == _ConfirmDeleteDialog.DialogCode.Accepted:
            from r6_navigator.services.crud_mission import delete_interview_interpretations
            with self._session_factory() as session:
                delete_interview_interpretations(session, self._filter_interview_id)
            self._reload_data()

    def _update_status(self, interp_id: int, status: str) -> None:
        if self._session_factory is None:
            return
        from r6_navigator.services.crud_mission import update_interpretation_status
        with self._session_factory() as session:
            update_interpretation_status(session, interp_id, status)
        self._reload_data()
