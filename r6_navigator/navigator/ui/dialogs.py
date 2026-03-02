"""Boîtes de dialogue de R6 Navigator.

Fournit des helpers de confirmation génériques et deux QDialog spécialisés :
NewCapacityDialog (création d'une capacité) et DocxExportDialog
(configuration de l'export DOCX).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)
from PySide6.QtCore import Qt

from r6_navigator.i18n import t
from r6_navigator.navigator.services.export_docx import ExportConfig


# ────────────────────────────────────────────────────────────
# Helpers de confirmation
# ────────────────────────────────────────────────────────────

def confirm(parent: QWidget, title: str, message: str) -> bool:
    """Affiche une boîte de dialogue Oui / Non et retourne le choix de l'utilisateur.

    Args:
        parent: Widget parent de la boîte de dialogue.
        title: Titre de la fenêtre modale.
        message: Texte de la question posée à l'utilisateur.

    Returns:
        True si l'utilisateur a cliqué sur Oui, False sinon.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    # Non sélectionné par défaut pour éviter la suppression accidentelle.
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes


def confirm_unsaved(parent: QWidget) -> str:
    """Affiche la boîte de dialogue « modifications non sauvegardées ».

    Propose trois actions : enregistrer, ignorer ou annuler.

    Args:
        parent: Widget parent de la boîte de dialogue.

    Returns:
        ``"save"`` si l'utilisateur choisit d'enregistrer,
        ``"discard"`` s'il choisit d'ignorer,
        ``"cancel"`` s'il annule ou ferme la fenêtre.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(t("dialog.unsaved.title"))
    box.setText(t("dialog.unsaved.message"))
    btn_save = box.addButton(t("dialog.unsaved.save"), QMessageBox.ButtonRole.AcceptRole)
    btn_discard = box.addButton(t("dialog.unsaved.discard"), QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(t("dialog.unsaved.cancel"), QMessageBox.ButtonRole.RejectRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked == btn_save:
        return "save"
    elif clicked == btn_discard:
        return "discard"
    return "cancel"


# ────────────────────────────────────────────────────────────
# Dialogue de création de capacité
# ────────────────────────────────────────────────────────────

class NewCapacityDialog(QDialog):
    """Dialogue de création d'une nouvelle capacité (Niveau / Axe / Pôle + libellé FR)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise le dialogue et construit le formulaire.

        Args:
            parent: Widget parent Qt (None pour un dialogue racine).
        """
        super().__init__(parent)
        self.setWindowTitle(t("dialog.new_capacity.title"))
        self.setMinimumWidth(360)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construit le formulaire : combos Niveau / Axe / Pôle, champ libellé, boutons OK / Annuler."""
        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self.combo_level = QComboBox()
        for code in ("S", "O", "I"):
            self.combo_level.addItem(f"{code} — {t(f'level.{code}')}", code)

        self.combo_axis = QComboBox()
        for num in (1, 2, 3):
            self.combo_axis.addItem(f"{num} — {t(f'axis.{num}')}", num)

        self.combo_pole = QComboBox()
        for code in ("a", "b"):
            self.combo_pole.addItem(f"{code} — {t(f'pole.{code}')}", code)

        self.entry_label = QLineEdit()
        self.entry_label.setPlaceholderText(t("fiche.label"))

        # Label d'erreur affiché uniquement si la validation échoue.
        self.lbl_error = QLabel()
        self.lbl_error.setStyleSheet("color: red;")
        self.lbl_error.hide()

        layout.addRow(t("dialog.new_capacity.level"), self.combo_level)
        layout.addRow(t("dialog.new_capacity.axis"), self.combo_axis)
        layout.addRow(t("dialog.new_capacity.pole"), self.combo_pole)
        layout.addRow(t("dialog.new_capacity.label_fr"), self.entry_label)
        layout.addRow(self.lbl_error)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate(self) -> None:
        """Valide le formulaire avant d'accepter le dialogue.

        Affiche un message d'erreur inline si le libellé français est vide.
        """
        if not self.entry_label.text().strip():
            self.lbl_error.setText(t("validation.label_fr_required"))
            self.lbl_error.show()
            return
        self.lbl_error.hide()
        self.accept()

    def get_values(self) -> tuple[str, int, str, str]:
        """Retourne les valeurs saisies dans le formulaire.

        Returns:
            Tuple ``(level_code, axis_number, pole_code, label_fr)`` avec les
            données sélectionnées / saisies par l'utilisateur.
        """
        return (
            self.combo_level.currentData(),
            self.combo_axis.currentData(),
            self.combo_pole.currentData(),
            self.entry_label.text().strip(),
        )


# ────────────────────────────────────────────────────────────
# Dialogue de configuration de l'export DOCX
# ────────────────────────────────────────────────────────────

class DocxExportDialog(QDialog):
    """Dialogue de configuration de l'export DOCX (périmètre, sections, langue)."""

    def __init__(
        self,
        current_capacity_id: str | None,
        all_capacity_ids: list[str],
        parent: QWidget | None = None,
    ) -> None:
        """Initialise le dialogue avec les capacités disponibles.

        Args:
            current_capacity_id: Identifiant de la capacité actuellement sélectionnée
                (propose l'option « capacité courante seulement » si non None).
            all_capacity_ids: Liste de tous les identifiants pour l'option « toutes ».
            parent: Widget parent Qt.
        """
        super().__init__(parent)
        self.setWindowTitle(t("dialog.docx.title"))
        self.setMinimumWidth(360)
        self._current_id = current_capacity_id
        self._all_ids = all_capacity_ids
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construit les groupes Périmètre, Sections, Langue et les boutons OK / Annuler."""
        layout = QVBoxLayout(self)

        # Groupe Périmètre : capacité courante ou toutes les capacités.
        scope_group = QGroupBox(t("dialog.docx.scope_current"))
        scope_layout = QVBoxLayout(scope_group)
        self.combo_scope = QComboBox()
        if self._current_id:
            self.combo_scope.addItem(
                t("dialog.docx.scope_current"), [self._current_id]
            )
        self.combo_scope.addItem(t("dialog.docx.scope_all"), self._all_ids)
        scope_layout.addWidget(self.combo_scope)
        layout.addWidget(scope_group)

        # Groupe Sections : cases à cocher pour inclure Fiche, Questions, Coaching.
        sections_group = QGroupBox(t("dialog.docx.include"))
        sections_layout = QVBoxLayout(sections_group)
        self.chk_fiche = QCheckBox(t("tab.fiche"))
        self.chk_fiche.setChecked(True)
        self.chk_questions = QCheckBox(t("tab.questions"))
        self.chk_questions.setChecked(True)
        self.chk_coaching = QCheckBox(t("tab.coaching"))
        self.chk_coaching.setChecked(True)
        sections_layout.addWidget(self.chk_fiche)
        sections_layout.addWidget(self.chk_questions)
        sections_layout.addWidget(self.chk_coaching)
        layout.addWidget(sections_group)

        # Sélecteur de langue du document exporté.
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel(t("dialog.docx.language")))
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("Français", "fr")
        self.combo_lang.addItem("English", "en")
        self.combo_lang.addItem("Français + English", "both")
        lang_row.addWidget(self.combo_lang)
        layout.addLayout(lang_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_capacity_ids(self) -> list[str]:
        """Retourne la liste des capacity_id à exporter selon la sélection de périmètre.

        Returns:
            Liste d'identifiants (un seul élément pour « courante », tous pour « toutes »).
        """
        return self.combo_scope.currentData() or []

    def get_language(self) -> str:
        """Retourne le code langue sélectionné pour l'export.

        Returns:
            ``"fr"`` ou ``"en"``.
        """
        return self.combo_lang.currentData()

    def get_config(self, output_path: Path) -> ExportConfig:
        """Construit un ExportConfig à partir des choix de l'utilisateur.

        Args:
            output_path: Chemin de destination du fichier DOCX.

        Returns:
            Instance ExportConfig prête à être passée à export_bulk().
        """
        return ExportConfig(
            output_path=output_path,
            language=self.get_language(),
            include_fiche=self.chk_fiche.isChecked(),
            include_questions=self.chk_questions.isChecked(),
            include_coaching=self.chk_coaching.isChecked(),
        )
