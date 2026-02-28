"""Onglet Questions de R6 Navigator.

Gère la liste des questions STAR (widgets _QuestionRow dynamiques) et
le tableau des items observables (QTableWidget avec combos de catégorie).
Supporte l'ajout, la suppression et le réordonnancement en mode édition.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidgetItem,
    QWidget,
)

from r6_navigator.db.models import Capacity
from r6_navigator.i18n import current_lang, t
from r6_navigator.services import crud
from r6_navigator.ui.qt.forms.ui_tabquestions import Ui_TabQuestions

# Codes de catégorie des items observables, dans l'ordre d'affichage.
_CATEGORY_CODES = ("OK", "EXC", "DEP", "INS")


# ────────────────────────────────────────────────────────────
# Worker de génération IA (thread de fond)
# ────────────────────────────────────────────────────────────

class _GenerateWorker(QThread):
    """Thread de fond pour l'appel Ollama — génère questions et manifestations observables.

    Signals:
        finished: Émis avec le GeneratedQuestions en cas de succès.
        error: Émis avec le message d'erreur en cas d'échec.
    """

    finished = Signal(object)   # GeneratedQuestions
    error = Signal(str)

    def __init__(self, capacity_id: str, lang: str) -> None:
        """Initialise le worker avec les paramètres de la requête.

        Args:
            capacity_id: Identifiant de la capacité à générer (ex. ``"I1a"``).
            lang: Code langue de génération (``"fr"`` ou ``"en"``).
        """
        super().__init__()
        self._capacity_id = capacity_id
        self._lang = lang

    def run(self) -> None:
        """Exécute l'appel Ollama dans le thread de fond."""
        try:
            from r6_navigator.services.ai_generate import generate_questions
            content = generate_questions(self._capacity_id, self._lang)
            self.finished.emit(content)
        except Exception as exc:
            self.error.emit(str(exc))


# ────────────────────────────────────────────────────────────
# Worker d'évaluation par 3 juges LLM (thread de fond)
# ────────────────────────────────────────────────────────────

class _JudgeWorker(QThread):
    """Thread de fond pour l'appel aux 3 juges LLM — questions et items observables.

    Signals:
        results_ready: Émis avec un objet JudgeResults en cas de succès.
        error: Émis avec le message d'erreur en cas d'échec.
    """

    results_ready = Signal(object)  # JudgeResults
    error = Signal(str)

    def __init__(self, content: dict, capacity_id: str, lang: str) -> None:
        super().__init__()
        self._content = content
        self._capacity_id = capacity_id
        self._lang = lang

    def run(self) -> None:
        try:
            from r6_navigator.services.ai_judge import judge_questions
            results = judge_questions(self._content, self._capacity_id, self._lang)
            self.results_ready.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


# ────────────────────────────────────────────────────────────
# Widget ligne de question
# ────────────────────────────────────────────────────────────

class _QuestionRow(QWidget):
    """Widget représentant une question STAR dans la liste.

    Affiche un numéro, un champ de texte et, en mode édition,
    des boutons de déplacement et de suppression.

    Signals:
        changed: Émis quand le texte de la question est modifié.
        remove_requested: Émis avec ce widget quand l'utilisateur clique sur Supprimer.
        move_up_requested: Émis avec ce widget quand l'utilisateur clique sur Monter.
        move_down_requested: Émis avec ce widget quand l'utilisateur clique sur Descendre.
    """

    changed = Signal()
    remove_requested = Signal(object)
    move_up_requested = Signal(object)
    move_down_requested = Signal(object)

    def __init__(
        self,
        index: int,
        question_id: int | None,
        text: str,
        editing: bool,
        parent: QWidget | None = None,
    ) -> None:
        """Crée une ligne de question.

        Args:
            index: Numéro d'ordre affiché devant la question (commence à 1).
            question_id: Identifiant DB de la question, ou None pour une nouvelle.
            text: Texte initial de la question.
            editing: True pour afficher les boutons d'action dès la création.
            parent: Widget parent Qt.
        """
        super().__init__(parent)
        self.question_id = question_id

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(4)

        self._lbl_num = QLabel(f"{index}.")
        self._lbl_num.setFixedWidth(24)
        row.addWidget(self._lbl_num)

        self._edit = QLineEdit(text)
        self._edit.setReadOnly(not editing)
        self._edit.textChanged.connect(self.changed)
        row.addWidget(self._edit)

        self._btn_up = QPushButton(t("btn.move_up"))
        self._btn_up.setFixedWidth(28)
        self._btn_up.clicked.connect(lambda: self.move_up_requested.emit(self))
        row.addWidget(self._btn_up)

        self._btn_down = QPushButton(t("btn.move_down"))
        self._btn_down.setFixedWidth(28)
        self._btn_down.clicked.connect(lambda: self.move_down_requested.emit(self))
        row.addWidget(self._btn_down)

        self._btn_del = QPushButton(t("btn.remove"))
        self._btn_del.setFixedWidth(28)
        self._btn_del.clicked.connect(lambda: self.remove_requested.emit(self))
        row.addWidget(self._btn_del)

        self._set_edit_controls_visible(editing)

    def set_editing(self, editing: bool) -> None:
        """Bascule le champ et les boutons d'action selon le mode édition.

        Args:
            editing: True pour activer l'édition et afficher les boutons.
        """
        self._edit.setReadOnly(not editing)
        self._set_edit_controls_visible(editing)

    def set_index(self, index: int) -> None:
        """Met à jour le numéro d'ordre affiché.

        Args:
            index: Nouveau numéro (commence à 1).
        """
        self._lbl_num.setText(f"{index}.")

    def get_text(self) -> str:
        """Retourne le texte saisi dans le champ de la question.

        Returns:
            Texte courant du QLineEdit.
        """
        return self._edit.text()

    def _set_edit_controls_visible(self, visible: bool) -> None:
        """Affiche ou masque les boutons Monter / Descendre / Supprimer.

        Args:
            visible: True pour afficher, False pour masquer.
        """
        self._btn_up.setVisible(visible)
        self._btn_down.setVisible(visible)
        self._btn_del.setVisible(visible)


# ────────────────────────────────────────────────────────────
# Onglet Questions
# ────────────────────────────────────────────────────────────

class TabQuestions(QWidget, Ui_TabQuestions):
    """Onglet Questions — liste STAR + tableau des items observables.

    Signals:
        dirty_changed: Émis avec True quand des modifications non sauvegardées
            apparaissent, False quand l'état redevient propre.
    """

    dirty_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise l'onglet et câble les signaux.

        Args:
            parent: Widget parent Qt (None pour un widget racine).
        """
        super().__init__(parent)
        self.setupUi(self)
        self._session_factory = None
        self._current_capacity: Capacity | None = None
        self._editing = False
        self._dirty = False
        self._question_rows: list[_QuestionRow] = []
        # Structure en mémoire des items observables : liste de dicts
        # {"item_id": int|None, "category_code": str, "text": str}.
        self._item_data: list[dict] = []
        self._deleted_question_ids: list[int] = []
        self._deleted_item_ids: list[int] = []
        self._worker: _GenerateWorker | None = None

        # Juge LLM
        self._original_snapshot: dict | None = None
        self._judge_worker: _JudgeWorker | None = None
        self._verification_window = None  # VerificationWindow, created on first use

        # Bouton [Juger] ajouté programmatiquement sous le tableau des items
        judge_bar = QWidget()
        judge_layout = QHBoxLayout(judge_bar)
        judge_layout.setContentsMargins(12, 4, 12, 4)
        self.btn_juger = QPushButton()
        judge_layout.addStretch()
        judge_layout.addWidget(self.btn_juger)
        self.main_layout.addWidget(judge_bar)

        self._setup_connections()
        self._retranslate()

    # ────────────────────────────────────────────────────────
    # API publique
    # ────────────────────────────────────────────────────────

    def set_session_factory(self, factory) -> None:
        """Injecte la factory de sessions SQLAlchemy.

        Args:
            factory: Callable retournant une session SQLAlchemy (context-manager).
        """
        self._session_factory = factory

    def load_capacity(self, capacity: Capacity) -> None:
        """Charge les questions et items d'une capacité et repasse en lecture seule.

        Args:
            capacity: Objet ORM de la capacité à afficher.
        """
        if self._verification_window is not None:
            self._verification_window.clear_history()

        self._current_capacity = capacity
        self._editing = False
        self._dirty = False
        self._deleted_question_ids.clear()
        self._deleted_item_ids.clear()
        self._load_all()

        self._original_snapshot = self._take_snapshot()

    def set_edit_mode(self, editing: bool) -> None:
        """Active ou désactive le mode édition sur les questions et le tableau des items.

        Args:
            editing: True pour passer en mode édition, False pour lecture seule.
        """
        self._editing = editing
        self.btn_new_question.setVisible(editing)
        self.btn_new_item.setVisible(editing)
        for row in self._question_rows:
            row.set_editing(editing)
        self._rebuild_items_table()

    def save(self) -> None:
        """Persiste les questions et items observables dans la base de données.

        Supprime d'abord les enregistrements marqués comme supprimés,
        puis upsert les données modifiées et réordonne les IDs.
        """
        if self._current_capacity is None or self._session_factory is None:
            return
        lang = current_lang()
        with self._session_factory() as session:
            # Suppression des questions retirées.
            for qid in self._deleted_question_ids:
                crud.delete_question(session, qid)
            self._deleted_question_ids.clear()

            # Upsert des questions avec collecte des IDs pour le réordonnancement.
            ordered_q_ids: list[int] = []
            for row in self._question_rows:
                text = row.get_text().strip()
                if row.question_id is None:
                    if text:
                        q = crud.create_question(
                            session, self._current_capacity.capacity_id, text, lang
                        )
                        row.question_id = q.question_id
                        ordered_q_ids.append(q.question_id)
                else:
                    crud.upsert_question_translation(
                        session, row.question_id, lang, text=text
                    )
                    ordered_q_ids.append(row.question_id)
            if ordered_q_ids:
                crud.reorder_questions(
                    session, self._current_capacity.capacity_id, ordered_q_ids
                )

            # Suppression des items observables retirés.
            for iid in self._deleted_item_ids:
                crud.delete_observable_item(session, iid)
            self._deleted_item_ids.clear()

            # Upsert des items avec réordonnancement par catégorie.
            ordered_by_cat: dict[str, list[int]] = {c: [] for c in _CATEGORY_CODES}
            for item in self._item_data:
                text = item["text"].strip()
                cat = item["category_code"]
                if item["item_id"] is None:
                    if text:
                        obs = crud.create_observable_item(
                            session,
                            self._current_capacity.capacity_id,
                            cat,
                            text,
                            lang,
                        )
                        item["item_id"] = obs.item_id
                        ordered_by_cat[cat].append(obs.item_id)
                else:
                    crud.upsert_observable_item_translation(
                        session, item["item_id"], lang, text=text
                    )
                    ordered_by_cat[cat].append(item["item_id"])
            for cat, ids in ordered_by_cat.items():
                if ids:
                    crud.reorder_observable_items(session, cat, ids)

        self._dirty = False
        self.dirty_changed.emit(False)
        if self._verification_window is not None:
            self._verification_window.clear_history()

    def discard(self) -> None:
        """Annule les modifications en cours en rechargeant les données depuis la base."""
        self._deleted_question_ids.clear()
        self._deleted_item_ids.clear()
        self._dirty = False
        self._load_all()

    def redraw(self) -> None:
        """Retraduit les libellés et recharge les données après un changement de langue."""
        self._retranslate()
        if self._current_capacity is not None:
            self._load_all()

    # ────────────────────────────────────────────────────────
    # Méthodes privées
    # ────────────────────────────────────────────────────────

    def _setup_connections(self) -> None:
        """Connecte les boutons d'ajout, de génération, de jugement et le signal de modification du tableau."""
        self.btn_generer.clicked.connect(self._on_generate)
        self.btn_juger.clicked.connect(self._on_juger_clicked)
        self.btn_new_question.clicked.connect(self._add_new_question)
        self.btn_new_item.clicked.connect(self._add_new_item)
        self.table_observable_items.itemChanged.connect(self._on_table_item_changed)

    def _retranslate(self) -> None:
        """Met à jour tous les libellés de l'onglet selon la langue active."""
        self.btn_generer.setText(t("btn.generate"))
        self.btn_juger.setText(t("btn.judge"))
        self.lbl_questions_title.setText(t("questions.section_title"))
        self.btn_new_question.setText(t("questions.new"))
        self.lbl_items_title.setText(t("questions.items_title"))
        self.btn_new_item.setText(t("questions.new_item"))
        h = self.table_observable_items
        h.horizontalHeaderItem(0).setText(t("questions.category_label"))
        h.horizontalHeaderItem(1).setText(t("table.col.text"))
        h.horizontalHeaderItem(2).setText(t("table.col.actions"))

    def _load_all(self) -> None:
        """Recharge questions et items depuis la base de données."""
        self._load_questions()
        self._load_observable_items()

    def _load_questions(self) -> None:
        """Charge les questions STAR depuis la DB et reconstruit les widgets lignes."""
        if self._session_factory is None or self._current_capacity is None:
            return
        lang = current_lang()
        with self._session_factory() as session:
            questions = crud.get_questions(session, self._current_capacity.capacity_id)
            q_data: list[tuple[int, str]] = []
            for q in questions:
                trans = crud.get_question_translation(session, q.question_id, lang)
                q_data.append((q.question_id, trans.text if trans else ""))
        self._rebuild_question_rows(q_data)

    def _rebuild_question_rows(self, q_data: list[tuple[int, str]]) -> None:
        """Reconstruit les widgets _QuestionRow dans le layout questions.

        Supprime le spacer final avant de reconstruire, puis le remet en place.

        Args:
            q_data: Liste de tuples (question_id, texte) dans l'ordre d'affichage.
        """
        # Suppression du spacer expansible (toujours en dernière position).
        count = self.questions_layout.count()
        if count > 0 and self.questions_layout.itemAt(count - 1).spacerItem():
            self.questions_layout.takeAt(count - 1)

        for row in self._question_rows:
            self.questions_layout.removeWidget(row)
            row.deleteLater()
        self._question_rows.clear()

        for i, (qid, text) in enumerate(q_data):
            row = _QuestionRow(i + 1, qid, text, self._editing, self.questions_container)
            row.changed.connect(self._mark_dirty)
            row.remove_requested.connect(self._remove_question_row)
            row.move_up_requested.connect(self._move_question_up)
            row.move_down_requested.connect(self._move_question_down)
            self.questions_layout.addWidget(row)
            self._question_rows.append(row)

        # Réajout du spacer expansible pour pousser les lignes vers le haut.
        self.questions_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        self.btn_new_question.setVisible(self._editing)

    def _load_observable_items(self) -> None:
        """Charge les items observables depuis la DB et reconstruit le tableau."""
        if self._session_factory is None or self._current_capacity is None:
            return
        lang = current_lang()
        with self._session_factory() as session:
            items = crud.get_observable_items(session, self._current_capacity.capacity_id)
            self._item_data = []
            for item in items:
                trans = crud.get_observable_item_translation(session, item.item_id, lang)
                self._item_data.append(
                    {
                        "item_id": item.item_id,
                        "category_code": item.category_code,
                        "text": trans.text if trans else "",
                    }
                )
        self._rebuild_items_table()

    def _rebuild_items_table(self) -> None:
        """Reconstruit le QTableWidget des items observables depuis _item_data.

        En mode édition : colonne Catégorie = QComboBox, colonne Actions = boutons.
        En lecture seule : cellules non éditables, colonne Actions vide.
        """
        table = self.table_observable_items
        table.blockSignals(True)
        table.setRowCount(0)

        for idx, item in enumerate(self._item_data):
            table.insertRow(idx)

            # Colonne 0 — Catégorie.
            if self._editing:
                combo = QComboBox()
                for code in _CATEGORY_CODES:
                    combo.addItem(t(f"category.{code}"), code)
                cur_idx = _CATEGORY_CODES.index(item["category_code"])
                combo.setCurrentIndex(cur_idx)
                # Capture de idx par argument par défaut pour éviter la capture tardive.
                combo.currentIndexChanged.connect(
                    lambda _, i=idx, c=combo: self._on_item_category_changed(i, c)
                )
                table.setCellWidget(idx, 0, combo)
            else:
                cat_item = QTableWidgetItem(t(f"category.{item['category_code']}"))
                cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(idx, 0, cat_item)

            # Colonne 1 — Texte.
            text_item = QTableWidgetItem(item["text"])
            if not self._editing:
                text_item.setFlags(text_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(idx, 1, text_item)

            # Colonne 2 — Actions (visibles uniquement en mode édition).
            if self._editing:
                actions_w = QWidget()
                al = QHBoxLayout(actions_w)
                al.setContentsMargins(2, 0, 2, 0)
                al.setSpacing(2)
                btn_up = QPushButton(t("btn.move_up"))
                btn_up.setFixedWidth(28)
                btn_up.clicked.connect(lambda _, i=idx: self._move_item_up(i))
                btn_dn = QPushButton(t("btn.move_down"))
                btn_dn.setFixedWidth(28)
                btn_dn.clicked.connect(lambda _, i=idx: self._move_item_down(i))
                btn_del = QPushButton(t("btn.remove"))
                btn_del.setFixedWidth(28)
                btn_del.clicked.connect(lambda _, i=idx: self._remove_item(i))
                al.addWidget(btn_up)
                al.addWidget(btn_dn)
                al.addWidget(btn_del)
                table.setCellWidget(idx, 2, actions_w)
            else:
                empty = QTableWidgetItem()
                empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(idx, 2, empty)

        table.blockSignals(False)

        # Adaptation des largeurs de colonnes.
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)

        self.btn_new_item.setVisible(self._editing)

    # ────────────────────────────────────────────────────────
    # Actions sur les lignes de questions
    # ────────────────────────────────────────────────────────

    def _add_new_question(self) -> None:
        """Ajoute une nouvelle ligne de question vide en fin de liste."""
        # Suppression temporaire du spacer avant d'insérer la nouvelle ligne.
        count = self.questions_layout.count()
        if count > 0 and self.questions_layout.itemAt(count - 1).spacerItem():
            self.questions_layout.takeAt(count - 1)

        idx = len(self._question_rows) + 1
        row = _QuestionRow(idx, None, "", True, self.questions_container)
        row.changed.connect(self._mark_dirty)
        row.remove_requested.connect(self._remove_question_row)
        row.move_up_requested.connect(self._move_question_up)
        row.move_down_requested.connect(self._move_question_down)
        self.questions_layout.addWidget(row)
        self._question_rows.append(row)

        self.questions_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        self._mark_dirty()

    def _remove_question_row(self, row: _QuestionRow) -> None:
        """Retire une ligne de question du layout et marque son ID pour suppression DB.

        Args:
            row: Widget _QuestionRow à supprimer.
        """
        if row.question_id is not None:
            self._deleted_question_ids.append(row.question_id)
        self.questions_layout.removeWidget(row)
        row.deleteLater()
        self._question_rows.remove(row)
        # Renumérotation des lignes restantes.
        for i, r in enumerate(self._question_rows):
            r.set_index(i + 1)
        self._mark_dirty()

    def _move_question_up(self, row: _QuestionRow) -> None:
        """Déplace une question d'une position vers le haut.

        Args:
            row: Widget _QuestionRow à déplacer.
        """
        idx = self._question_rows.index(row)
        if idx == 0:
            return
        self._question_rows[idx], self._question_rows[idx - 1] = (
            self._question_rows[idx - 1],
            self._question_rows[idx],
        )
        self._rebuild_question_layout()
        self._mark_dirty()

    def _move_question_down(self, row: _QuestionRow) -> None:
        """Déplace une question d'une position vers le bas.

        Args:
            row: Widget _QuestionRow à déplacer.
        """
        idx = self._question_rows.index(row)
        if idx >= len(self._question_rows) - 1:
            return
        self._question_rows[idx], self._question_rows[idx + 1] = (
            self._question_rows[idx + 1],
            self._question_rows[idx],
        )
        self._rebuild_question_layout()
        self._mark_dirty()

    def _rebuild_question_layout(self) -> None:
        """Réinsère les widgets _QuestionRow dans le layout selon leur ordre actuel.

        Vide entièrement le layout sans détruire les widgets, puis les réinsère
        dans l'ordre de _question_rows avec leurs numéros mis à jour.
        """
        while self.questions_layout.count():
            self.questions_layout.takeAt(0)
        for i, row in enumerate(self._question_rows):
            row.set_index(i + 1)
            self.questions_layout.addWidget(row)
        self.questions_layout.addItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

    # ────────────────────────────────────────────────────────
    # Actions sur les items observables
    # ────────────────────────────────────────────────────────

    def _add_new_item(self) -> None:
        """Ajoute un item observable vide avec la première catégorie par défaut."""
        self._item_data.append(
            {"item_id": None, "category_code": _CATEGORY_CODES[0], "text": ""}
        )
        self._rebuild_items_table()
        self._mark_dirty()

    def _on_item_category_changed(self, idx: int, combo: QComboBox) -> None:
        """Met à jour la catégorie d'un item quand l'utilisateur change le combo.

        Args:
            idx: Index de l'item dans _item_data.
            combo: QComboBox dont la sélection a changé.
        """
        if idx < len(self._item_data):
            self._item_data[idx]["category_code"] = combo.currentData()
            self._mark_dirty()

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        """Synchronise _item_data quand l'utilisateur édite une cellule de texte.

        Args:
            item: Cellule modifiée dans le QTableWidget.
        """
        row, col = item.row(), item.column()
        if col == 1 and row < len(self._item_data):
            self._item_data[row]["text"] = item.text()
            self._mark_dirty()

    def _remove_item(self, idx: int) -> None:
        """Supprime un item observable de la liste et marque son ID pour suppression DB.

        Args:
            idx: Index de l'item à supprimer dans _item_data.
        """
        if idx >= len(self._item_data):
            return
        item_id = self._item_data[idx]["item_id"]
        if item_id is not None:
            self._deleted_item_ids.append(item_id)
        self._item_data.pop(idx)
        self._rebuild_items_table()
        self._mark_dirty()

    def _move_item_up(self, idx: int) -> None:
        """Déplace un item observable d'une position vers le haut dans la liste.

        Args:
            idx: Index de l'item à déplacer dans _item_data.
        """
        if idx == 0 or idx >= len(self._item_data):
            return
        self._item_data[idx], self._item_data[idx - 1] = (
            self._item_data[idx - 1],
            self._item_data[idx],
        )
        self._rebuild_items_table()
        self._mark_dirty()

    def _move_item_down(self, idx: int) -> None:
        """Déplace un item observable d'une position vers le bas dans la liste.

        Args:
            idx: Index de l'item à déplacer dans _item_data.
        """
        if idx >= len(self._item_data) - 1:
            return
        self._item_data[idx], self._item_data[idx + 1] = (
            self._item_data[idx + 1],
            self._item_data[idx],
        )
        self._rebuild_items_table()
        self._mark_dirty()

    # ────────────────────────────────────────────────────────
    # Génération IA
    # ────────────────────────────────────────────────────────

    def _on_generate(self) -> None:
        """Lance la génération IA dans un thread de fond si aucune n'est déjà en cours."""
        if self._current_capacity is None:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self.btn_generer.setEnabled(False)
        self._worker = _GenerateWorker(
            self._current_capacity.capacity_id, current_lang()
        )
        self._worker.finished.connect(self._on_generate_done)
        self._worker.error.connect(self._on_generate_error)
        self._worker.start()

    def _on_generate_done(self, content) -> None:
        """Remplace les questions et items observables par le contenu généré.

        Vide les listes existantes (marque les IDs existants pour suppression),
        reconstruit les widgets avec le nouveau contenu, puis marque comme modifié.

        Args:
            content: Objet GeneratedQuestions retourné par generate_questions().
        """
        self.btn_generer.setEnabled(True)
        self._worker = None

        # Marque tous les IDs existants pour suppression lors du prochain save().
        for row in self._question_rows:
            if row.question_id is not None:
                self._deleted_question_ids.append(row.question_id)
        for item in self._item_data:
            if item["item_id"] is not None:
                self._deleted_item_ids.append(item["item_id"])

        # Reconstruit les lignes de questions depuis le contenu généré.
        q_data = [(None, text) for text in content.questions]
        self._rebuild_question_rows(q_data)

        # Reconstruit les items observables en préservant l'ordre des catégories.
        self._item_data = []
        for code in _CATEGORY_CODES:
            for text in content.observable_items.get(code, []):
                self._item_data.append(
                    {"item_id": None, "category_code": code, "text": text}
                )
        self._rebuild_items_table()

        self._mark_dirty()

    def _on_generate_error(self, message: str) -> None:
        """Affiche une boîte de dialogue d'erreur et réactive le bouton Générer.

        Args:
            message: Description de l'erreur retournée par le worker.
        """
        self.btn_generer.setEnabled(True)
        self._worker = None
        QMessageBox.warning(self, t("error.generate"), message)

    # ────────────────────────────────────────────────────────
    # Évaluation par 3 juges LLM
    # ────────────────────────────────────────────────────────

    def _take_snapshot(self) -> dict:
        """Capture l'état courant des questions et items sous forme de snapshot.

        Returns:
            Dictionnaire avec ``capacity_id``, ``questions`` et ``observable_items``.
        """
        capacity_id = (
            self._current_capacity.capacity_id if self._current_capacity else ""
        )
        return {
            "capacity_id": capacity_id,
            "questions": [
                {"question_id": row.question_id, "text": row.get_text()}
                for row in self._question_rows
            ],
            "observable_items": [
                {
                    "item_id": item["item_id"],
                    "category_code": item["category_code"],
                    "text": item["text"],
                }
                for item in self._item_data
            ],
        }

    def _to_llm_content(self, snapshot: dict) -> dict:
        """Extrait le contenu texte uniquement depuis un snapshot pour l'envoi au LLM.

        Args:
            snapshot: Snapshot retourné par _take_snapshot().

        Returns:
            Dictionnaire avec ``questions`` (liste de textes) et
            ``observable_items`` (dict catégorie → liste de textes).
        """
        questions = [q["text"] for q in snapshot.get("questions", [])]
        items_by_cat: dict[str, list[str]] = {}
        for item in snapshot.get("observable_items", []):
            cat = item["category_code"]
            items_by_cat.setdefault(cat, []).append(item["text"])
        return {"questions": questions, "observable_items": items_by_cat}

    def _on_juger_clicked(self) -> None:
        """Lance l'évaluation par 3 juges LLM si aucune n'est déjà en cours."""
        if self._current_capacity is None:
            return
        if self._judge_worker is not None and self._judge_worker.isRunning():
            return

        snapshot = self._take_snapshot()
        self.btn_juger.setEnabled(False)
        self.btn_juger.setText(t("judge.running"))

        if self._verification_window is None:
            from r6_navigator.ui.qt.verification_window import VerificationWindow
            self._verification_window = VerificationWindow(self)
            self._verification_window.restore_version.connect(self._restore_version)

        self._verification_window.show_running()

        llm_content = self._to_llm_content(snapshot)
        self._judge_worker = _JudgeWorker(
            llm_content, self._current_capacity.capacity_id, current_lang()
        )
        self._judge_worker.results_ready.connect(
            lambda results: self._on_judge_results(snapshot, results)
        )
        self._judge_worker.error.connect(self._on_judge_error)
        self._judge_worker.start()

    def _on_judge_results(self, snapshot: dict, results) -> None:
        """Reçoit les résultats des juges et les affiche dans la VerificationWindow.

        Args:
            snapshot: Snapshot capturé au moment du clic sur [Juger].
            results: Objet JudgeResults retourné par judge_questions().
        """
        self.btn_juger.setEnabled(True)
        self.btn_juger.setText(t("btn.judge"))
        if self._verification_window is not None:
            self._verification_window.add_version(snapshot, results)
        self._judge_worker = None

    def _on_judge_error(self, message: str) -> None:
        """Affiche une erreur de jugement et réactive le bouton Juger.

        Args:
            message: Description de l'erreur retournée par le worker.
        """
        self.btn_juger.setEnabled(True)
        self.btn_juger.setText(t("btn.judge"))
        if self._verification_window is not None:
            self._verification_window.hide()
        QMessageBox.warning(self, t("judge.error", message=message), message)
        self._judge_worker = None

    def _restore_version(self, content: dict) -> None:
        """Réinjecte un snapshot dans les listes de questions et d'items observables.

        Appelé par le signal ``restore_version`` de VerificationWindow.

        Args:
            content: Snapshot dict retourné par _take_snapshot().
        """
        q_data = [
            (q.get("question_id"), q.get("text", ""))
            for q in content.get("questions", [])
        ]
        self._rebuild_question_rows(q_data)

        self._item_data = [
            {
                "item_id": item.get("item_id"),
                "category_code": item.get("category_code", _CATEGORY_CODES[0]),
                "text": item.get("text", ""),
            }
            for item in content.get("observable_items", [])
        ]
        self._rebuild_items_table()

    # ────────────────────────────────────────────────────────

    def _mark_dirty(self) -> None:
        """Marque l'onglet comme modifié et émet dirty_changed une seule fois."""
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)
