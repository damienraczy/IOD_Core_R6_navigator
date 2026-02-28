"""Onglet Fiche de R6 Navigator.

Affiche et édite les champs structurés d'une capacité (intitulé, définition,
fonction centrale, observable, risques) et orchestre la génération IA via
un QThread dédié (_GenerateWorker), ainsi que l'évaluation par 3 juges LLM
via _JudgeWorker.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QWidget

from r6_navigator.db.models import Capacity
from r6_navigator.i18n import current_lang, t
from r6_navigator.services import crud
from r6_navigator.ui.qt.forms.ui_tabfiche import Ui_TabFiche


# ────────────────────────────────────────────────────────────
# Worker de génération IA (thread de fond)
# ────────────────────────────────────────────────────────────


class _GenerateWorker(QThread):
    """Thread de fond pour l'appel Ollama — maintient l'UI réactive pendant la génération.

    Signals:
        finished: Émis avec le GeneratedContent en cas de succès.
        error: Émis avec le message d'erreur en cas d'échec.
    """

    finished = Signal(object)   # GeneratedContent
    error = Signal(str)

    def __init__(self, capacity_id: str, lang: str) -> None:
        """Initialise le worker avec les paramètres de la requête.

        Args:
            capacity_id: Identifiant de la capacité à générer (ex. ``"S1a"``).
            lang: Code langue de génération (``"fr"`` ou ``"en"``).
        """
        super().__init__()
        self._capacity_id = capacity_id
        self._lang = lang

    def run(self) -> None:
        """Exécute l'appel Ollama dans le thread de fond.

        Importe ``generate_fiche`` de façon différée pour éviter le chargement
        du module Ollama au démarrage de l'application.
        """
        try:
            from r6_navigator.services.ai_generate import generate_fiche
            content = generate_fiche(self._capacity_id, self._lang)
            self.finished.emit(content)
        except Exception as exc:
            self.error.emit(str(exc))



# ────────────────────────────────────────────────────────────
# Worker d'évaluation par 3 juges LLM (thread de fond)
# ────────────────────────────────────────────────────────────


class _JudgeWorker(QThread):
    """Thread de fond pour l'appel aux 3 juges LLM.

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
            from r6_navigator.services.ai_judge import judge_fiche
            results = judge_fiche(self._content, self._capacity_id, self._lang)
            self.results_ready.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


# ────────────────────────────────────────────────────────────
# Onglet Fiche
# ────────────────────────────────────────────────────────────

class TabFiche(QWidget, Ui_TabFiche):
    """Onglet Fiche — champs structurés + génération IA, avec mode édition.

    Signals:
        dirty_changed: Émis avec True quand des modifications non sauvegardées
            apparaissent, False quand l'état redevient propre.
    """

    dirty_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise l'onglet, câble les signaux et passe en lecture seule.

        Args:
            parent: Widget parent Qt (None pour un widget racine).
        """
        super().__init__(parent)
        self.setupUi(self)
        self._session_factory = None
        self._current_capacity: Capacity | None = None
        self._editing = False
        self._dirty = False
        self._worker: _GenerateWorker | None = None

        # Juge LLM
        self._original_snapshot: dict | None = None
        self._judge_worker: _JudgeWorker | None = None
        self._verification_window = None  # VerificationWindow, created on first use

        # Bouton [Juger] ajouté programmatiquement sous le scroll_area
        judge_bar = QWidget()
        judge_layout = QHBoxLayout(judge_bar)
        judge_layout.setContentsMargins(12, 4, 12, 4)
        self.btn_juger = QPushButton()
        judge_layout.addStretch()
        judge_layout.addWidget(self.btn_juger)
        self.main_layout.addWidget(judge_bar)

        self._setup_connections()
        self._set_fields_readonly(True)
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
        """Charge les données d'une capacité et repasse en lecture seule.

        Args:
            capacity: Objet ORM de la capacité à afficher.
        """
        # Ferme la fenêtre de vérification de la capacité précédente.
        if self._verification_window is not None:
            self._verification_window.clear_history()

        self._current_capacity = capacity
        self._editing = False
        self._dirty = False
        self._set_fields_readonly(True)
        self._load_capacity_data()

        # Capture le snapshot initial après chargement.
        self._original_snapshot = self._take_snapshot()

    def set_edit_mode(self, editing: bool) -> None:
        """Active ou désactive le mode édition sur tous les champs.

        Args:
            editing: True pour passer en mode édition, False pour lecture seule.
        """
        self._editing = editing
        self._set_fields_readonly(not editing)
        if not editing:
            self._dirty = False

    def save(self) -> None:
        """Persiste les valeurs des champs dans la table de traductions de la capacité courante."""
        if self._current_capacity is None or self._session_factory is None:
            return
        lang = current_lang()
        with self._session_factory() as session:
            crud.upsert_capacity_translation(
                session,
                self._current_capacity.capacity_id,
                lang,
                label=self.entry_label.text().strip(),
                definition=self.text_definition.toPlainText(),
                central_function=self.text_central_function.toPlainText(),
                observable=self.text_observable.toPlainText(),
                risk_insufficient=self.text_risk_insufficient.toPlainText(),
                risk_excessive=self.text_risk_excessive.toPlainText(),
            )
        self._dirty = False
        self.dirty_changed.emit(False)
        if self._verification_window is not None:
            self._verification_window.clear_history()

    def discard(self) -> None:
        """Annule les modifications en cours en rechargeant les données depuis la base."""
        self._dirty = False
        self._load_capacity_data()

    def redraw(self) -> None:
        """Retraduit les libellés et recharge les données après un changement de langue."""
        self._retranslate()
        if self._current_capacity is not None:
            self._load_capacity_data()

    def current_label(self) -> str:
        """Retourne le texte actuel du champ Intitulé (utilisé pour le titre de fenêtre).

        Returns:
            Libellé courant, sans espaces en début/fin.
        """
        return self.entry_label.text().strip()

    # ────────────────────────────────────────────────────────
    # Méthodes privées
    # ────────────────────────────────────────────────────────

    def _setup_connections(self) -> None:
        """Connecte les boutons Générer/Juger et les signaux de modification des champs."""
        self.btn_generer.clicked.connect(self._on_generate)
        self.btn_juger.clicked.connect(self._on_juger_clicked)
        self.entry_label.textChanged.connect(self._on_field_changed)
        for widget in (
            self.text_definition,
            self.text_central_function,
            self.text_observable,
            self.text_risk_insufficient,
            self.text_risk_excessive,
        ):
            widget.textChanged.connect(self._on_field_changed)

    def _retranslate(self) -> None:
        """Met à jour tous les libellés de l'onglet selon la langue active."""
        self.lbl_level_key.setText(t("fiche.level"))
        self.lbl_axis_key.setText(t("fiche.axis"))
        self.lbl_pole_key.setText(t("fiche.pole"))
        self.lbl_code_key.setText(t("fiche.code"))
        self.lbl_label_key.setText(t("fiche.label"))
        self.lbl_definition_key.setText(t("fiche.definition"))
        self.lbl_central_function_key.setText(t("fiche.central_function"))
        self.lbl_observable_key.setText(t("fiche.observable"))
        self.lbl_risk_insufficient_key.setText(t("fiche.risk_insufficient"))
        self.lbl_risk_excessive_key.setText(t("fiche.risk_excessive"))
        self.btn_generer.setText(t("btn.generate"))
        self.btn_juger.setText(t("btn.judge"))

    def _load_capacity_data(self) -> None:
        """Charge depuis la DB et affiche les données de la capacité courante.

        Bloque les signaux des champs pendant le chargement pour ne pas
        déclencher le flag dirty lors du remplissage programmatique.
        """
        if self._session_factory is None or self._current_capacity is None:
            return
        cap = self._current_capacity
        lang = current_lang()
        with self._session_factory() as session:
            trans = crud.get_capacity_translation(session, cap.capacity_id, lang)

        # Blocage des signaux pour éviter de marquer dirty pendant le chargement.
        for w in self._all_editable():
            w.blockSignals(True)

        # En-tête structurel (lecture seule — données du modèle, pas de la traduction).
        self.lbl_level_val.setText(f"{t(f'level.{cap.level_code}')} ({cap.level_code})")
        axis_prefix = t("nav.filter.axis")
        self.lbl_axis_val.setText(
            f"{axis_prefix} {cap.axis_number} — {t(f'axis.{cap.axis_number}')}"
        )
        self.lbl_pole_val.setText(f"{t(f'pole.{cap.pole_code}')} ({cap.pole_code})")
        self.lbl_code_val.setText(cap.capacity_id)

        # Champs de traduction éditables.
        self.entry_label.setText(trans.label if trans else "")
        self.text_definition.setPlainText(trans.definition or "" if trans else "")
        self.text_central_function.setPlainText(trans.central_function or "" if trans else "")
        self.text_observable.setPlainText(trans.observable or "" if trans else "")
        self.text_risk_insufficient.setPlainText(trans.risk_insufficient or "" if trans else "")
        self.text_risk_excessive.setPlainText(trans.risk_excessive or "" if trans else "")

        for w in self._all_editable():
            w.blockSignals(False)

    def _set_fields_readonly(self, readonly: bool) -> None:
        """Passe tous les champs éditables en lecture seule ou en édition.

        Args:
            readonly: True pour lecture seule, False pour édition.
        """
        self.entry_label.setReadOnly(readonly)
        for w in (
            self.text_definition,
            self.text_central_function,
            self.text_observable,
            self.text_risk_insufficient,
            self.text_risk_excessive,
        ):
            w.setReadOnly(readonly)

    def _all_editable(self):
        """Retourne un tuple de tous les widgets de saisie éditables.

        Returns:
            Tuple contenant entry_label et les cinq QPlainTextEdit.
        """
        return (
            self.entry_label,
            self.text_definition,
            self.text_central_function,
            self.text_observable,
            self.text_risk_insufficient,
            self.text_risk_excessive,
        )

    def _on_field_changed(self) -> None:
        """Marque l'onglet comme modifié lors de la première saisie en mode édition."""
        if self._editing and not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

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
        """Peuple les champs avec le contenu généré et marque l'onglet comme modifié.

        Active le mode édition si nécessaire avant d'écrire dans les champs,
        puis bloque les signaux le temps du remplissage pour n'émettre
        dirty_changed qu'une seule fois à la fin.

        Args:
            content: Objet GeneratedContent retourné par generate_fiche().
        """
        self.btn_generer.setEnabled(True)
        # Active le mode édition avant d'écrire pour que les champs soient modifiables.
        if not self._editing:
            self.set_edit_mode(True)
        for w in self._all_editable():
            w.blockSignals(True)
        self.entry_label.setText(content.name)
        self.text_definition.setPlainText(content.definition)
        self.text_central_function.setPlainText(content.central_function)
        self.text_observable.setPlainText(content.observable)
        self.text_risk_insufficient.setPlainText(content.risk_insufficient)
        self.text_risk_excessive.setPlainText(content.risk_excessive)
        for w in self._all_editable():
            w.blockSignals(False)
        self._worker = None
        # Signale les modifications pour que la barre d'outils affiche [Enregistrer]/[Annuler].
        self._dirty = True
        self.dirty_changed.emit(True)

    def _on_generate_error(self, message: str) -> None:
        """Affiche une boîte de dialogue d'erreur et réactive le bouton Générer.

        Args:
            message: Description de l'erreur retournée par le worker.
        """
        self.btn_generer.setEnabled(True)
        QMessageBox.warning(self, t("error.generate"), message)
        self._worker = None

    # ────────────────────────────────────────────────────────
    # Évaluation par 3 juges LLM
    # ────────────────────────────────────────────────────────

    def _take_snapshot(self) -> dict:
        """Lit les champs courants et retourne un dict snapshot.

        Returns:
            Dictionnaire avec les clés ``capacity_id``, ``label``, ``definition``,
            ``central_function``, ``observable``, ``risk_insufficient``, ``risk_excessive``.
        """
        capacity_id = (
            self._current_capacity.capacity_id if self._current_capacity else ""
        )
        return {
            "capacity_id": capacity_id,
            "label": self.entry_label.text().strip(),
            "definition": self.text_definition.toPlainText(),
            "central_function": self.text_central_function.toPlainText(),
            "observable": self.text_observable.toPlainText(),
            "risk_insufficient": self.text_risk_insufficient.toPlainText(),
            "risk_excessive": self.text_risk_excessive.toPlainText(),
        }

    def _on_juger_clicked(self) -> None:
        """Lance l'évaluation par 3 juges LLM si aucune n'est déjà en cours."""
        if self._current_capacity is None:
            return
        if self._judge_worker is not None and self._judge_worker.isRunning():
            return

        snapshot = self._take_snapshot()
        self.btn_juger.setEnabled(False)
        self.btn_juger.setText(t("judge.running"))

        # Crée la fenêtre de vérification si nécessaire.
        if self._verification_window is None:
            from r6_navigator.ui.qt.verification_window import VerificationWindow
            self._verification_window = VerificationWindow(self)
            self._verification_window.restore_version.connect(self._restore_version)

        self._verification_window.show_running()

        self._judge_worker = _JudgeWorker(
            snapshot, self._current_capacity.capacity_id, current_lang()
        )
        self._judge_worker.results_ready.connect(self._on_judge_results)
        self._judge_worker.error.connect(self._on_judge_error)
        self._judge_worker.start()

    def _on_judge_results(self, results) -> None:
        """Reçoit les résultats des juges et les affiche dans la VerificationWindow.

        Args:
            results: Objet JudgeResults retourné par judge_fiche().
        """
        self.btn_juger.setEnabled(True)
        self.btn_juger.setText(t("btn.judge"))
        snapshot = self._take_snapshot()
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
        """Réinjecte un snapshot dans les champs de la fiche.

        Appelé par le signal ``restore_version`` de VerificationWindow.

        Args:
            content: Snapshot dict retourné par _take_snapshot().
        """
        for w in self._all_editable():
            w.blockSignals(True)
        self.entry_label.setText(content.get("label", ""))
        self.text_definition.setPlainText(content.get("definition", ""))
        self.text_central_function.setPlainText(content.get("central_function", ""))
        self.text_observable.setPlainText(content.get("observable", ""))
        self.text_risk_insufficient.setPlainText(content.get("risk_insufficient", ""))
        self.text_risk_excessive.setPlainText(content.get("risk_excessive", ""))
        for w in self._all_editable():
            w.blockSignals(False)
