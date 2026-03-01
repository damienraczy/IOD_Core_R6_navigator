"""Onglet Questions de R6 Navigator.

Gère la liste des questions STAR et le tableau des items observables.
Les deux sections utilisent un QTableWidget avec la même structure de colonnes
(N° / texte / actions), ce qui harmonise le look & feel et assure un
redimensionnement correct avec la fenêtre.

Chaque section dispose de son propre bouton [Générer] :
- btn_generer      → generate_questions()       → 10 questions uniquement
- btn_generer_items → generate_questions_items() → 4×5 items uniquement
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
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
# Worker de génération des questions (thread de fond)
# ────────────────────────────────────────────────────────────

class _GenerateWorker(QThread):
    """Thread de fond pour l'appel Ollama — génère les questions d'entretien.

    Signals:
        finished: Émis avec la list[str] des questions en cas de succès.
        error: Émis avec le message d'erreur en cas d'échec.
    """

    finished = Signal(object)   # list[str]
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
# Worker de génération des items observables (thread de fond)
# ────────────────────────────────────────────────────────────

class _GenerateItemsWorker(QThread):
    """Thread de fond pour générer les 4×5 items observables via Ollama.

    Signals:
        finished: Émis avec le dict[str, list[str]] des items en cas de succès.
        error: Émis avec le message d'erreur en cas d'échec.
    """

    finished = Signal(object)   # dict[str, list[str]]
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
            from r6_navigator.services.ai_generate import generate_questions_items
            items = generate_questions_items(self._capacity_id, self._lang)
            self.finished.emit(items)
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
# Onglet Questions
# ────────────────────────────────────────────────────────────

class TabQuestions(QWidget, Ui_TabQuestions):
    """Onglet Questions — tableau des questions STAR + tableau des items observables.

    Les deux sections utilisent un QTableWidget (colonnes N° | texte | actions)
    pour un look & feel uniforme et un redimensionnement naturel avec la fenêtre.

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

        # Données en mémoire : liste de dicts {"question_id": int|None, "text": str}
        self._question_data: list[dict] = []
        # Données en mémoire : liste de dicts {"item_id": int|None, "category_code": str, "text": str}
        self._item_data: list[dict] = []

        self._deleted_question_ids: list[int] = []
        self._deleted_item_ids: list[int] = []
        self._worker: _GenerateWorker | None = None
        self._items_worker: _GenerateItemsWorker | None = None

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
        """Active ou désactive le mode édition sur les deux tableaux.

        Args:
            editing: True pour passer en mode édition, False pour lecture seule.
        """
        self._editing = editing
        self.btn_new_question.setVisible(editing)
        self.btn_new_item.setVisible(editing)
        self._rebuild_questions_table()
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
            for item in self._question_data:
                text = item["text"].strip()
                if item["question_id"] is None:
                    if text:
                        q = crud.create_question(
                            session, self._current_capacity.capacity_id, text, lang
                        )
                        item["question_id"] = q.question_id
                        ordered_q_ids.append(q.question_id)
                else:
                    crud.upsert_question_translation(
                        session, item["question_id"], lang, text=text
                    )
                    ordered_q_ids.append(item["question_id"])
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
    # Méthodes privées — initialisation
    # ────────────────────────────────────────────────────────

    def _setup_connections(self) -> None:
        """Connecte les boutons et les signaux de modification des deux tableaux."""
        self.btn_generer.clicked.connect(self._on_generate)
        self.btn_generer_items.clicked.connect(self._on_generate_items)
        self.btn_juger.clicked.connect(self._on_juger_clicked)
        self.btn_new_question.clicked.connect(self._add_new_question)
        self.btn_new_item.clicked.connect(self._add_new_item)
        self.table_questions.itemChanged.connect(self._on_questions_item_changed)
        self.table_observable_items.itemChanged.connect(self._on_table_item_changed)

    def _retranslate(self) -> None:
        """Met à jour tous les libellés de l'onglet selon la langue active."""
        self.btn_generer.setText(t("btn.generate"))
        self.btn_generer_items.setText(t("btn.generate_items"))
        self.btn_juger.setText(t("btn.judge"))
        self.lbl_questions_title.setText(t("questions.section_title"))
        self.btn_new_question.setText(t("questions.new"))
        self.lbl_items_title.setText(t("questions.items_title"))
        self.btn_new_item.setText(t("questions.new_item"))

        hq = self.table_questions
        hq.horizontalHeaderItem(0).setText(t("table.col.number"))
        hq.horizontalHeaderItem(1).setText(t("table.col.question"))
        hq.horizontalHeaderItem(2).setText(t("table.col.actions"))

        hi = self.table_observable_items
        hi.horizontalHeaderItem(0).setText(t("questions.category_label"))
        hi.horizontalHeaderItem(1).setText(t("table.col.text"))
        hi.horizontalHeaderItem(2).setText(t("table.col.actions"))

    # ────────────────────────────────────────────────────────
    # Chargement depuis la DB
    # ────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        """Recharge questions et items depuis la base de données."""
        self._load_questions()
        self._load_observable_items()

    def _load_questions(self) -> None:
        """Charge les questions STAR depuis la DB et reconstruit le tableau."""
        if self._session_factory is None or self._current_capacity is None:
            return
        lang = current_lang()
        with self._session_factory() as session:
            questions = crud.get_questions(session, self._current_capacity.capacity_id)
            self._question_data = []
            for q in questions:
                trans = crud.get_question_translation(session, q.question_id, lang)
                self._question_data.append({
                    "question_id": q.question_id,
                    "text": trans.text if trans else "",
                })
        self._rebuild_questions_table()

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

    # ────────────────────────────────────────────────────────
    # Reconstruction des tableaux
    # ────────────────────────────────────────────────────────

    def _rebuild_questions_table(self) -> None:
        """Reconstruit le QTableWidget des questions depuis _question_data.

        En mode édition : colonne Texte éditable, colonne Actions = boutons.
        En lecture seule : cellules non éditables, colonne Actions vide.
        Structure des colonnes : # | Question | Actions
        """
        table = self.table_questions
        table.blockSignals(True)
        table.setRowCount(0)

        for idx, item in enumerate(self._question_data):
            table.insertRow(idx)

            # Colonne 0 — Numéro (toujours non éditable).
            num_item = QTableWidgetItem(str(idx + 1))
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(idx, 0, num_item)

            # Colonne 1 — Texte de la question.
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
                btn_up.clicked.connect(lambda _, i=idx: self._move_question_up(i))
                btn_dn = QPushButton(t("btn.move_down"))
                btn_dn.setFixedWidth(28)
                btn_dn.clicked.connect(lambda _, i=idx: self._move_question_down(i))
                btn_del = QPushButton(t("btn.remove"))
                btn_del.setFixedWidth(28)
                btn_del.clicked.connect(lambda _, i=idx: self._remove_question(i))
                al.addWidget(btn_up)
                al.addWidget(btn_dn)
                al.addWidget(btn_del)
                table.setCellWidget(idx, 2, actions_w)
            else:
                empty = QTableWidgetItem()
                empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(idx, 2, empty)

        table.blockSignals(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)

        self.btn_new_question.setVisible(self._editing)

    def _rebuild_items_table(self) -> None:
        """Reconstruit le QTableWidget des items observables depuis _item_data.

        En mode édition : colonne Catégorie = QComboBox, colonne Actions = boutons.
        En lecture seule : cellules non éditables, colonne Actions vide.
        Structure des colonnes : Catégorie | Texte | Actions
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

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, header.ResizeMode.Stretch)
        header.setSectionResizeMode(2, header.ResizeMode.ResizeToContents)

        self.btn_new_item.setVisible(self._editing)

    # ────────────────────────────────────────────────────────
    # Actions sur les questions
    # ────────────────────────────────────────────────────────

    def _add_new_question(self) -> None:
        """Ajoute une nouvelle question vide en fin de liste."""
        self._question_data.append({"question_id": None, "text": ""})
        self._rebuild_questions_table()
        self._mark_dirty()

    def _remove_question(self, idx: int) -> None:
        """Supprime une question de la liste et marque son ID pour suppression DB.

        Args:
            idx: Index de la question à supprimer dans _question_data.
        """
        if idx >= len(self._question_data):
            return
        qid = self._question_data[idx]["question_id"]
        if qid is not None:
            self._deleted_question_ids.append(qid)
        self._question_data.pop(idx)
        self._rebuild_questions_table()
        self._mark_dirty()

    def _move_question_up(self, idx: int) -> None:
        """Déplace une question d'une position vers le haut.

        Args:
            idx: Index de la question à déplacer dans _question_data.
        """
        if idx == 0 or idx >= len(self._question_data):
            return
        self._question_data[idx], self._question_data[idx - 1] = (
            self._question_data[idx - 1],
            self._question_data[idx],
        )
        self._rebuild_questions_table()
        self._mark_dirty()

    def _move_question_down(self, idx: int) -> None:
        """Déplace une question d'une position vers le bas.

        Args:
            idx: Index de la question à déplacer dans _question_data.
        """
        if idx >= len(self._question_data) - 1:
            return
        self._question_data[idx], self._question_data[idx + 1] = (
            self._question_data[idx + 1],
            self._question_data[idx],
        )
        self._rebuild_questions_table()
        self._mark_dirty()

    def _on_questions_item_changed(self, item: QTableWidgetItem) -> None:
        """Synchronise _question_data quand l'utilisateur édite une cellule de texte.

        Args:
            item: Cellule modifiée dans le QTableWidget des questions.
        """
        row, col = item.row(), item.column()
        if col == 1 and row < len(self._question_data):
            self._question_data[row]["text"] = item.text()
            self._mark_dirty()

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
            item: Cellule modifiée dans le QTableWidget des items observables.
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
        """Déplace un item observable d'une position vers le haut.

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
        """Déplace un item observable d'une position vers le bas.

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
    # Génération IA — Questions
    # ────────────────────────────────────────────────────────

    def _on_generate(self) -> None:
        """Lance la génération des questions dans un thread de fond."""
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
        """Remplace les questions par le contenu généré.

        Marque les questions existantes pour suppression, reconstruit le
        tableau avec le nouveau contenu, puis marque comme modifié.
        Les items observables ne sont pas touchés par ce bouton.

        Args:
            content: list[str] retourné par generate_questions().
        """
        self.btn_generer.setEnabled(True)
        self._worker = None

        # Marque les questions existantes pour suppression lors du prochain save().
        for item in self._question_data:
            if item["question_id"] is not None:
                self._deleted_question_ids.append(item["question_id"])

        self._question_data = [{"question_id": None, "text": text} for text in content]
        self._rebuild_questions_table()
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
    # Génération IA — Items observables
    # ────────────────────────────────────────────────────────

    def _on_generate_items(self) -> None:
        """Lance la génération des items observables dans un thread de fond."""
        if self._current_capacity is None:
            return
        if self._items_worker is not None and self._items_worker.isRunning():
            return
        self.btn_generer_items.setEnabled(False)
        self._items_worker = _GenerateItemsWorker(
            self._current_capacity.capacity_id, current_lang()
        )
        self._items_worker.finished.connect(self._on_generate_items_done)
        self._items_worker.error.connect(self._on_generate_items_error)
        self._items_worker.start()

    def _on_generate_items_done(self, items: dict) -> None:
        """Remplace les items observables par le contenu généré.

        Marque les items existants pour suppression, reconstruit le tableau
        avec le nouveau contenu, puis marque comme modifié.
        Les questions ne sont pas touchées par ce bouton.

        Args:
            items: dict[str, list[str]] retourné par generate_questions_items().
        """
        self.btn_generer_items.setEnabled(True)
        self._items_worker = None

        for item in self._item_data:
            if item["item_id"] is not None:
                self._deleted_item_ids.append(item["item_id"])

        self._item_data = []
        for code in _CATEGORY_CODES:
            for text in items.get(code, []):
                self._item_data.append(
                    {"item_id": None, "category_code": code, "text": text}
                )
        self._rebuild_items_table()
        self._mark_dirty()

    def _on_generate_items_error(self, message: str) -> None:
        """Affiche une erreur et réactive le bouton Générer items.

        Args:
            message: Description de l'erreur retournée par le worker.
        """
        self.btn_generer_items.setEnabled(True)
        self._items_worker = None
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
                {"question_id": item["question_id"], "text": item["text"]}
                for item in self._question_data
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
        self._question_data = [
            {
                "question_id": q.get("question_id"),
                "text": q.get("text", ""),
            }
            for q in content.get("questions", [])
        ]
        self._rebuild_questions_table()

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
