"""Fenêtre principale de R6 Navigator.

Orchestre la composition de l'interface : navpanel, detailpanel, tabs,
barre d'outils et gestion des changements non sauvegardés (EditGuard).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from r6_navigator.db.models import Capacity
from r6_navigator.i18n import current_lang, set_lang, t
from r6_navigator.services import crud
from r6_navigator.services.backup import restore_backup, save_backup
from r6_navigator.services.export_docx import export_bulk, export_capacity, make_filename
from r6_navigator.ui.qt.detailpanel import DetailPanel
from r6_navigator.ui.qt.dialogs import (
    DocxExportDialog,
    NewCapacityDialog,
    confirm,
    confirm_unsaved,
)
from r6_navigator.ui.qt.navpanel import NavPanel
from r6_navigator.ui.qt.tabcoaching import TabCoaching
from r6_navigator.ui.qt.tabfiche import TabFiche
from r6_navigator.ui.qt.tabquestions import TabQuestions


# ────────────────────────────────────────────────────────────
# EditGuard
# ────────────────────────────────────────────────────────────

def _open_path(path: str | Path) -> None:
    """Ouvre un fichier ou un répertoire avec l'application par défaut du système.

    Args:
        path: Chemin vers le fichier ou le répertoire à ouvrir.
    """
    path = str(path)
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform.startswith("win"):
        subprocess.Popen(["start", path], shell=True)


class EditGuard:
    """Surveille les modifications non sauvegardées sur Fiche et Questions.

    Interpose une boîte de dialogue avant toute action destructrice
    (navigation, changement de langue, suppression de capacité).
    """

    def __init__(self) -> None:
        """Initialise le garde avec un état propre."""
        self.is_dirty = False

    def mark_dirty(self) -> None:
        """Signale la présence de modifications non sauvegardées."""
        self.is_dirty = True

    def mark_clean(self) -> None:
        """Réinitialise l'état à « propre » (aucune modification en cours)."""
        self.is_dirty = False

    def confirm_if_dirty(self, parent: QWidget, save_fn=None) -> bool:
        """Demande confirmation si des modifications sont en attente.

        Args:
            parent: Widget parent de la boîte de dialogue.
            save_fn: Callback optionnel exécuté si l'utilisateur choisit
                d'enregistrer avant de continuer.

        Returns:
            True si l'action peut se poursuivre (aucun changement, ou
            l'utilisateur a confirmé) ; False si l'utilisateur a annulé.
        """
        if not self.is_dirty:
            return True
        result = confirm_unsaved(parent)
        if result == "cancel":
            return False
        if result == "save" and save_fn is not None:
            save_fn()
        self.mark_clean()
        return True


# ────────────────────────────────────────────────────────────
# Fenêtre principale
# ────────────────────────────────────────────────────────────

class R6NavigatorApp(QMainWindow):
    """Fenêtre principale de l'application R6 Navigator.

    Compose et relie : NavPanel (gauche), DetailPanel + tabs (droite),
    barre de langue (haut), barre d'outils CRUD/export (bas).
    """

    def __init__(self, session_factory, db_path: Path | None = None) -> None:
        """Initialise la fenêtre, construit l'UI et restaure les réglages.

        Args:
            session_factory: Callable retournant une session SQLAlchemy
                (pattern context-manager).
            db_path: Chemin vers le fichier SQLite, utilisé pour la
                sauvegarde/restauration. None si non disponible.
        """
        super().__init__()
        self._session_factory = session_factory
        self._db_path_value = db_path
        self._current_capacity: Capacity | None = None
        self._in_edit_mode = False
        self._edit_guard = EditGuard()
        self._mission_window = None  # lazy MissionApp

        self._build_ui()
        self._retranslate()
        self._restore_settings()
        self._populate_nav()
        self._update_toolbar_state()

    # ────────────────────────────────────────────────────────
    # Construction de l'UI
    # ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Construit et assemble tous les widgets de la fenêtre principale."""
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Barre supérieure : sélecteur de langue aligné à droite.
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(8, 4, 8, 4)
        top_bar.addStretch()
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Français", "fr")
        self._lang_combo.addItem("English", "en")
        top_bar.addWidget(QLabel("🌐"))
        top_bar.addWidget(self._lang_combo)
        root.addLayout(top_bar)

        # Zone centrale : navpanel (largeur fixe) + séparateur + detailpanel.
        # Un QHBoxLayout est préféré à un QSplitter car le navpanel
        # a une largeur fixe — le redimensionnement manuel n'est pas nécessaire.
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Panneau de navigation (gauche).
        self.nav_panel = NavPanel()
        self.nav_panel.setFixedWidth(280)
        self.nav_panel.set_session_factory(self._session_factory)
        content_layout.addWidget(self.nav_panel)

        # Séparateur vertical entre le navpanel et le detailpanel.
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setFrameShadow(QFrame.Shadow.Sunken)
        content_layout.addWidget(vsep)

        # Panneau de détail (droite) avec ses trois onglets.
        self.detail_panel = DetailPanel()
        self.tab_fiche = TabFiche()
        self.tab_questions = TabQuestions()
        self.tab_coaching = TabCoaching()

        for component in (self.tab_fiche, self.tab_questions, self.tab_coaching):
            component.set_session_factory(self._session_factory)

        self.detail_panel.set_tabs(
            self.tab_fiche, self.tab_questions, self.tab_coaching
        )
        content_layout.addWidget(self.detail_panel, 1)
        root.addWidget(content, 1)

        # Barre d'outils (bas).
        root.addWidget(self._build_toolbar())

        # Connexion des signaux inter-composants.
        self.nav_panel.capacity_selected.connect(self._on_capacity_selected)
        self.detail_panel.navigate_to.connect(self._on_capacity_selected)
        self.detail_panel.tabs.currentChanged.connect(self._on_tab_changed)
        self.tab_fiche.dirty_changed.connect(self._on_dirty_changed)
        self.tab_questions.dirty_changed.connect(self._on_dirty_changed)
        self._lang_combo.currentIndexChanged.connect(self._on_language_changed)

    def _build_toolbar(self) -> QWidget:
        """Construit la barre d'outils inférieure (CRUD + export + sauvegarde DB).

        Returns:
            Widget contenant tous les boutons d'action, prêt à être inséré
            dans le layout principal.
        """
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.btn_new = QPushButton()
        self.btn_edit = QPushButton()
        self.btn_save_edit = QPushButton()
        self.btn_cancel_edit = QPushButton()
        self.btn_delete = QPushButton()

        # Les boutons Save/Cancel n'apparaissent qu'en mode édition.
        self.btn_save_edit.setVisible(False)
        self.btn_cancel_edit.setVisible(False)

        layout.addWidget(self.btn_new)
        layout.addWidget(self.btn_edit)
        layout.addWidget(self.btn_save_edit)
        layout.addWidget(self.btn_cancel_edit)
        layout.addWidget(self.btn_delete)
        layout.addStretch()

        self.btn_save_db = QPushButton()
        self.btn_restore_db = QPushButton()
        self.btn_export_docx = QPushButton()
        self.btn_missions = QPushButton()

        layout.addWidget(self.btn_save_db)
        layout.addWidget(self.btn_restore_db)
        layout.addWidget(self.btn_export_docx)
        layout.addWidget(self.btn_missions)

        self.btn_new.clicked.connect(self._on_new_capacity)
        self.btn_edit.clicked.connect(self._on_enter_edit)
        self.btn_save_edit.clicked.connect(self._on_save_edit)
        self.btn_cancel_edit.clicked.connect(self._on_cancel_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_save_db.clicked.connect(self._on_save_db)
        self.btn_restore_db.clicked.connect(self._on_restore_db)
        self.btn_export_docx.clicked.connect(self._on_export_docx)
        self.btn_missions.clicked.connect(self._on_open_missions)

        return toolbar

    def _retranslate(self) -> None:
        """Met à jour tous les libellés de la fenêtre selon la langue active."""
        self.setWindowTitle(t("app.title"))
        self.btn_new.setText(t("btn.new"))
        self.btn_edit.setText(t("btn.edit"))
        self.btn_save_edit.setText(t("btn.save"))
        self.btn_cancel_edit.setText(t("btn.cancel"))
        self.btn_delete.setText(t("btn.delete"))
        self.btn_save_db.setText(t("btn.save_db"))
        self.btn_restore_db.setText(t("btn.restore_db"))
        self.btn_export_docx.setText(t("btn.export_docx"))
        self.btn_missions.setText(t("mission.title"))

    # ────────────────────────────────────────────────────────
    # Persistance des réglages utilisateur
    # ────────────────────────────────────────────────────────

    def _restore_settings(self) -> None:
        """Restaure la langue active et la géométrie de fenêtre depuis la DB."""
        with self._session_factory() as session:
            lang = crud.get_setting(session, "active_language")
            geom_b64 = crud.get_setting(session, "window_geometry")

        if lang:
            try:
                set_lang(lang)
            except ValueError:
                pass
            # Synchronise le combo sans déclencher le handler de changement.
            self._lang_combo.blockSignals(True)
            for i in range(self._lang_combo.count()):
                if self._lang_combo.itemData(i) == current_lang():
                    self._lang_combo.setCurrentIndex(i)
                    break
            self._lang_combo.blockSignals(False)

        if geom_b64:
            self.restoreGeometry(QByteArray.fromBase64(geom_b64.encode()))

    def _save_settings(self) -> None:
        """Sauvegarde la langue active et la géométrie de fenêtre dans la DB."""
        geom_b64 = self.saveGeometry().toBase64().data().decode()
        with self._session_factory() as session:
            crud.set_setting(session, "active_language", current_lang())
            crud.set_setting(session, "window_geometry", geom_b64)

    # ────────────────────────────────────────────────────────
    # Navigation entre capacités
    # ────────────────────────────────────────────────────────

    def _populate_nav(self) -> None:
        """Peuple le navpanel avec les capacités de la base de données."""
        self.nav_panel.populate()

    def _on_capacity_selected(self, capacity_id: str) -> None:
        """Réagit à la sélection d'une capacité (navpanel ou barre isoomorphisme).

        Sauvegarde le coaching courant, quitte le mode édition si actif,
        puis charge la capacité dans tous les onglets.

        Args:
            capacity_id: Identifiant de la capacité à afficher (ex. ``"S1a"``).
        """
        if not self._edit_guard.confirm_if_dirty(self, self._save_current_edit):
            return

        # Sauvegarde automatique du coaching avant de changer de capacité.
        self.tab_coaching.save()

        if self._in_edit_mode:
            self._exit_edit_mode()

        with self._session_factory() as session:
            capacity = crud.get_capacity(session, capacity_id)
        if capacity is None:
            return

        self._current_capacity = capacity
        sibling_ids = self._get_sibling_ids(capacity)

        self.nav_panel.select_capacity(capacity_id)
        self.detail_panel.load_capacity(capacity_id, sibling_ids)
        self.tab_fiche.load_capacity(capacity)
        self.tab_questions.load_capacity(capacity)
        self.tab_coaching.load_capacity(capacity)

        self._update_window_title()
        self._update_toolbar_state()

    def _get_sibling_ids(self, capacity: Capacity) -> list[str]:
        """Retourne les capacity_id partageant le même axe et le même pôle.

        Args:
            capacity: Capacité de référence.

        Returns:
            Liste triée des identifiants des capacités sœurs (même axe + pôle).
        """
        with self._session_factory() as session:
            all_caps = crud.get_all_capacities(session)
        return [
            c.capacity_id
            for c in all_caps
            if c.axis_number == capacity.axis_number
            and c.pole_code == capacity.pole_code
        ]

    def _on_tab_changed(self, index: int) -> None:
        """Sauvegarde automatiquement le coaching quand on quitte son onglet.

        Args:
            index: Index du nouvel onglet actif (0 = Fiche, 1 = Questions, 2 = Coaching).
        """
        if index != 2:
            self.tab_coaching.save()

    # ────────────────────────────────────────────────────────
    # Mode édition
    # ────────────────────────────────────────────────────────

    def _on_enter_edit(self) -> None:
        """Active le mode édition sur les onglets Fiche et Questions."""
        if self._current_capacity is None:
            return
        self._in_edit_mode = True
        self.tab_fiche.set_edit_mode(True)
        self.tab_questions.set_edit_mode(True)
        self.btn_edit.setVisible(False)
        self.btn_save_edit.setVisible(True)
        self.btn_cancel_edit.setVisible(True)

    def _on_save_edit(self) -> None:
        """Enregistre les modifications des onglets Fiche et Questions, puis quitte le mode édition."""
        self.tab_fiche.save()
        self.tab_questions.save()
        self._exit_edit_mode()
        # Rafraîchit le navpanel au cas où le libellé aurait changé.
        self.nav_panel.redraw()
        if self._current_capacity:
            self.nav_panel.select_capacity(self._current_capacity.capacity_id)
        self._update_window_title()

    def _on_cancel_edit(self) -> None:
        """Annule les modifications en cours et quitte le mode édition."""
        self.tab_fiche.discard()
        self.tab_questions.discard()
        self._exit_edit_mode()

    def _exit_edit_mode(self) -> None:
        """Repasse en mode lecture seule et restaure les boutons de la barre d'outils."""
        self._in_edit_mode = False
        self._edit_guard.mark_clean()
        self.tab_fiche.set_edit_mode(False)
        self.tab_questions.set_edit_mode(False)
        self.btn_edit.setVisible(True)
        self.btn_save_edit.setVisible(False)
        self.btn_cancel_edit.setVisible(False)

    def _save_current_edit(self) -> None:
        """Sauvegarde et quitte le mode édition — utilisé comme callback par EditGuard."""
        self.tab_fiche.save()
        self.tab_questions.save()
        self._exit_edit_mode()

    def _on_dirty_changed(self, dirty: bool) -> None:
        """Synchronise l'EditGuard et la barre d'outils avec l'état dirty des onglets.

        Déclenché par ``TabFiche.dirty_changed`` ou ``TabQuestions.dirty_changed``.
        Active automatiquement le mode édition si une génération IA introduit
        des modifications sans que l'utilisateur ait cliqué sur [Modifier].

        Args:
            dirty: True si des modifications non sauvegardées existent.
        """
        if dirty:
            self._edit_guard.mark_dirty()
            # Passage automatique en mode édition si déclenché par la génération IA.
            if not self._in_edit_mode:
                self._in_edit_mode = True
                self.btn_edit.setVisible(False)
                self.btn_save_edit.setVisible(True)
                self.btn_cancel_edit.setVisible(True)
        else:
            self._edit_guard.mark_clean()

    # ────────────────────────────────────────────────────────
    # Actions de la barre d'outils
    # ────────────────────────────────────────────────────────

    def _on_new_capacity(self) -> None:
        """Ouvre le dialogue de création d'une nouvelle capacité."""
        if not self._edit_guard.confirm_if_dirty(self, self._save_current_edit):
            return
        dlg = NewCapacityDialog(self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        level_code, axis_number, pole_code, label_fr = dlg.get_values()
        capacity_id = f"{level_code}{axis_number}{pole_code}"
        with self._session_factory() as session:
            existing = crud.get_capacity(session, capacity_id)
            if existing is not None:
                QMessageBox.warning(
                    self,
                    t("dialog.new_capacity.title"),
                    t("dialog.new_capacity.duplicate", capacity_id=capacity_id),
                )
                return
            crud.create_capacity(
                session,
                level_code=level_code,
                axis_number=axis_number,
                pole_code=pole_code,
                label=label_fr,
                lang="fr",
                is_canonical=False,
            )
        self.nav_panel.redraw()
        self._on_capacity_selected(capacity_id)

    def _on_delete(self) -> None:
        """Supprime la capacité courante après confirmation (double confirmation pour les canoniques)."""
        if self._current_capacity is None:
            return
        cap = self._current_capacity
        if cap.is_canonical:
            # Double confirmation pour protéger les capacités standard du référentiel.
            QMessageBox.warning(
                self,
                t("dialog.delete.title"),
                t("dialog.delete.canonical_warning"),
            )
            if not confirm(
                self,
                t("dialog.delete.title"),
                t("dialog.delete.canonical_confirm"),
            ):
                return
        else:
            if not confirm(
                self,
                t("dialog.delete.title"),
                t("dialog.delete.message", capacity_id=cap.capacity_id),
            ):
                return

        # Détermine quelle capacité sélectionner après la suppression.
        with self._session_factory() as session:
            all_caps = crud.get_all_capacities(session)
        ids = [c.capacity_id for c in all_caps]
        cur_idx = ids.index(cap.capacity_id) if cap.capacity_id in ids else -1
        next_id = None
        if len(ids) > 1:
            next_idx = cur_idx + 1 if cur_idx < len(ids) - 1 else cur_idx - 1
            next_id = ids[next_idx]

        with self._session_factory() as session:
            crud.delete_capacity(session, cap.capacity_id)

        self._current_capacity = None
        if self._in_edit_mode:
            self._exit_edit_mode()
        self.nav_panel.redraw()
        self._update_toolbar_state()

        if next_id:
            self._on_capacity_selected(next_id)

    def _on_save_db(self) -> None:
        """Sauvegarde la base de données dans le répertoire ``backups/``."""
        db_path = self._db_path()
        if db_path is None:
            return
        backup_dir = db_path.parent / "backups"
        try:
            dest = save_backup(db_path, backup_dir)
            QMessageBox.information(
                self,
                t("btn.save_db"),
                t("dialog.save_db.success", path=str(dest)),
            )
        except Exception as exc:
            QMessageBox.critical(self, t("btn.save_db"), str(exc))

    def _on_restore_db(self) -> None:
        """Restaure la base de données depuis un fichier de sauvegarde choisi par l'utilisateur."""
        if not confirm(
            self, t("dialog.restore.title"), t("dialog.restore.confirm")
        ):
            return
        backup_path, _ = QFileDialog.getOpenFileName(
            self,
            t("dialog.restore.title"),
            "",
            "SQLite DB (*.db)",
        )
        if not backup_path:
            return
        db_path = self._db_path()
        if db_path is None:
            return
        try:
            restore_backup(Path(backup_path), db_path)
            QMessageBox.information(
                self,
                t("dialog.restore.title"),
                t("dialog.restore.message"),
            )
            # Recharge le navpanel pour refléter le nouvel état de la DB.
            self.nav_panel.redraw()
        except IOError as exc:
            QMessageBox.critical(self, t("dialog.restore.title"), str(exc))

    def _on_export_docx(self) -> None:
        """Ouvre le dialogue d'export DOCX et génère un fichier par capacité.

        Pour une seule capacité en une seule langue, ouvre un dialogue de
        sauvegarde de fichier avec le nom suggéré. Pour toute autre combinaison
        (plusieurs capacités ou mode bilingue), ouvre un sélecteur de répertoire
        et génère les fichiers nommés automatiquement.
        """
        if self._current_capacity is None:
            return
        with self._session_factory() as session:
            all_caps = crud.get_all_capacities(session)
        all_ids = [c.capacity_id for c in all_caps]

        dlg = DocxExportDialog(
            current_capacity_id=self._current_capacity.capacity_id,
            all_capacity_ids=all_ids,
            parent=self,
        )
        if dlg.exec() != dlg.DialogCode.Accepted:
            return

        capacity_ids = dlg.get_capacity_ids()
        lang = dlg.get_language()
        single_file = len(capacity_ids) == 1 and lang != "both"

        try:
            if single_file:
                # Un seul fichier → dialogue de sauvegarde avec nom suggéré.
                cid = capacity_ids[0]
                with self._session_factory() as session:
                    trans = crud.get_capacity_translation(session, cid, lang)
                label = trans.label if trans and trans.label else cid
                suggested = make_filename(cid, label, lang)
                output_path, _ = QFileDialog.getSaveFileName(
                    self,
                    t("btn.export_docx"),
                    suggested,
                    "Word Document (*.docx)",
                )
                if not output_path:
                    return
                config = dlg.get_config(Path(output_path))
                with self._session_factory() as session:
                    export_capacity(cid, session, config)
                _open_path(output_path)
            else:
                # Plusieurs fichiers → sélecteur de répertoire.
                output_dir = QFileDialog.getExistingDirectory(
                    self, t("btn.export_docx")
                )
                if not output_dir:
                    return
                config = dlg.get_config(Path(output_dir))
                with self._session_factory() as session:
                    export_bulk(capacity_ids, session, config)
                _open_path(output_dir)
        except Exception as exc:
            QMessageBox.critical(
                self,
                t("btn.export_docx"),
                t("error.export", message=str(exc)),
            )

    # ────────────────────────────────────────────────────────
    # Changement de langue
    # ────────────────────────────────────────────────────────

    def _on_language_changed(self, _index: int) -> None:
        """Applique la nouvelle langue sélectionnée et redessine toute l'UI.

        Annule le changement (restaure le combo) si l'utilisateur refuse
        de perdre des modifications non sauvegardées.

        Args:
            _index: Index du nouvel élément sélectionné dans le combo (non utilisé).
        """
        lang = self._lang_combo.currentData()
        if not self._edit_guard.confirm_if_dirty(self, self._save_current_edit):
            # Revenir à la langue courante sans déclencher ce handler.
            self._lang_combo.blockSignals(True)
            for i in range(self._lang_combo.count()):
                if self._lang_combo.itemData(i) == current_lang():
                    self._lang_combo.setCurrentIndex(i)
                    break
            self._lang_combo.blockSignals(False)
            return

        set_lang(lang)
        self._redraw_all()

        with self._session_factory() as session:
            crud.set_setting(session, "active_language", lang)

    def _redraw_all(self) -> None:
        """Propage le changement de langue à tous les composants de l'UI."""
        self._retranslate()
        self.nav_panel.redraw()
        self.detail_panel.redraw()
        self.tab_fiche.redraw()
        self.tab_questions.redraw()
        self.tab_coaching.redraw()
        if self._current_capacity:
            self._update_window_title()

    # ────────────────────────────────────────────────────────
    # Utilitaires
    # ────────────────────────────────────────────────────────

    def _update_window_title(self) -> None:
        """Met à jour le titre de la fenêtre avec l'identifiant et le libellé de la capacité courante."""
        if self._current_capacity is None:
            self.setWindowTitle(t("app.title"))
        else:
            label = self.tab_fiche.current_label()
            self.setWindowTitle(
                t(
                    "app.title_with_capacity",
                    capacity_id=self._current_capacity.capacity_id,
                    label=label,
                )
            )

    def _update_toolbar_state(self) -> None:
        """Active ou désactive les boutons de la barre d'outils selon la sélection courante."""
        has_cap = self._current_capacity is not None
        self.btn_edit.setEnabled(has_cap)
        self.btn_delete.setEnabled(has_cap)
        self.btn_export_docx.setEnabled(has_cap)

    def _db_path(self) -> Path | None:
        """Retourne le chemin vers la base de données SQLite.

        Returns:
            Chemin absolu vers le fichier ``.db``, ou None si non configuré.
        """
        return self._db_path_value

    def _on_open_missions(self) -> None:
        """Ouvre (ou remet au premier plan) la fenêtre du module Missions."""
        from r6_navigator.ui.qt.mission_app import MissionApp
        if self._mission_window is None:
            self._mission_window = MissionApp(self._session_factory, parent=None)
        self._mission_window.show()
        self._mission_window.raise_()
        self._mission_window.activateWindow()

    # ────────────────────────────────────────────────────────
    # Événements de fenêtre
    # ────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Intercepte la fermeture pour sauvegarder le coaching et les réglages.

        Annule la fermeture si l'utilisateur refuse de gérer ses modifications
        non sauvegardées.

        Args:
            event: Événement de fermeture Qt.
        """
        self.tab_coaching.save()
        if not self._edit_guard.confirm_if_dirty(self, self._save_current_edit):
            event.ignore()
            return
        self._save_settings()
        event.accept()
