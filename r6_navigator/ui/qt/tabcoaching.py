"""Onglet Coaching de R6 Navigator.

Affiche trois zones de texte libre (thèmes de réflexion, leviers
d'intervention, missions recommandées), toujours éditables et
sauvegardées automatiquement à chaque changement de capacité.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from r6_navigator.db.models import Capacity
from r6_navigator.i18n import current_lang, t
from r6_navigator.services import crud
from r6_navigator.ui.qt.forms.ui_tabcoaching import Ui_TabCoaching


# ────────────────────────────────────────────────────────────
# Worker de génération IA (thread de fond)
# ────────────────────────────────────────────────────────────

class _GenerateWorker(QThread):
    """Thread de fond pour l'appel Ollama — génère le contenu coaching.

    Signals:
        finished: Émis avec le GeneratedCoaching en cas de succès.
        error: Émis avec le message d'erreur en cas d'échec.
    """

    finished = Signal(object)   # GeneratedCoaching
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
            from r6_navigator.services.ai_generate import generate_coaching
            content = generate_coaching(self._capacity_id, self._lang)
            self.finished.emit(content)
        except Exception as exc:
            self.error.emit(str(exc))


# ────────────────────────────────────────────────────────────
# Onglet Coaching
# ────────────────────────────────────────────────────────────

class TabCoaching(QWidget, Ui_TabCoaching):
    """Onglet Coaching — trois zones de texte libre, toujours éditables et auto-sauvegardées."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise l'onglet et affiche les libellés traduits.

        Args:
            parent: Widget parent Qt (None pour un widget racine).
        """
        super().__init__(parent)
        self.setupUi(self)
        self._session_factory = None
        self._current_capacity: Capacity | None = None
        self._worker: _GenerateWorker | None = None
        self.btn_generer.clicked.connect(self._on_generate)
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
        """Sauvegarde le coaching courant puis charge la nouvelle capacité.

        La sauvegarde automatique garantit qu'aucune donnée n'est perdue
        lors de la navigation entre capacités sans clic explicite.

        Args:
            capacity: Objet ORM de la capacité à charger.
        """
        if self._current_capacity is not None:
            self._save_current()
        self._current_capacity = capacity
        self._load_coaching()

    def save(self) -> None:
        """Sauvegarde explicite du coaching courant (appelé à la fermeture ou au changement d'onglet).

        Délègue à _save_current ; exposé publiquement pour être appelé
        par R6NavigatorApp sans avoir accès aux membres privés.
        """
        self._save_current()

    def redraw(self) -> None:
        """Retraduit les libellés et recharge les données après un changement de langue.

        Le changement de langue peut modifier le contenu affiché car les
        traductions sont stockées par langue dans la base de données.
        """
        self._retranslate()
        if self._current_capacity is not None:
            self._load_coaching()

    # ────────────────────────────────────────────────────────
    # Méthodes privées
    # ────────────────────────────────────────────────────────

    def _retranslate(self) -> None:
        """Met à jour les libellés des trois zones de texte selon la langue active."""
        self.btn_generer.setText(t("btn.generate"))
        self.lbl_reflection_themes_key.setText(t("coaching.reflection_themes"))
        self.lbl_intervention_levers_key.setText(t("coaching.intervention_levers"))
        self.lbl_recommended_missions_key.setText(t("coaching.recommended_missions"))

    def _load_coaching(self) -> None:
        """Charge les données de coaching depuis la DB et peuple les trois zones de texte.

        Bloque les signaux pendant le remplissage programmatique pour éviter
        de déclencher des callbacks inutiles.
        """
        if self._session_factory is None or self._current_capacity is None:
            return
        lang = current_lang()
        with self._session_factory() as session:
            trans = crud.get_coaching_translation(
                session, self._current_capacity.capacity_id, lang
            )
        pairs = [
            (self.text_reflection_themes, "reflection_themes"),
            (self.text_intervention_levers, "intervention_levers"),
            (self.text_recommended_missions, "recommended_missions"),
        ]
        for widget, attr in pairs:
            widget.blockSignals(True)
            widget.setPlainText(getattr(trans, attr) or "" if trans else "")
            widget.blockSignals(False)

    def _save_current(self) -> None:
        """Persiste les trois zones de texte dans la table coaching_translations.

        Ne fait rien si aucune capacité n'est chargée ou si la factory
        de sessions n'a pas été injectée.
        """
        if self._session_factory is None or self._current_capacity is None:
            return
        lang = current_lang()
        with self._session_factory() as session:
            crud.upsert_coaching_translation(
                session,
                self._current_capacity.capacity_id,
                lang,
                reflection_themes=self.text_reflection_themes.toPlainText(),
                intervention_levers=self.text_intervention_levers.toPlainText(),
                recommended_missions=self.text_recommended_missions.toPlainText(),
            )

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
        """Remplace le contenu des trois zones de texte par le contenu généré.

        Bloque les signaux pendant le remplissage pour éviter des callbacks
        inutiles. La sauvegarde reste automatique à la prochaine navigation.

        Args:
            content: Objet GeneratedCoaching retourné par generate_coaching().
        """
        self.btn_generer.setEnabled(True)
        self._worker = None
        for widget, attr in (
            (self.text_reflection_themes, "reflection_themes"),
            (self.text_intervention_levers, "intervention_levers"),
            (self.text_recommended_missions, "recommended_missions"),
        ):
            widget.blockSignals(True)
            widget.setPlainText(getattr(content, attr))
            widget.blockSignals(False)

    def _on_generate_error(self, message: str) -> None:
        """Affiche une boîte de dialogue d'erreur et réactive le bouton Générer.

        Args:
            message: Description de l'erreur retournée par le worker.
        """
        self.btn_generer.setEnabled(True)
        self._worker = None
        QMessageBox.warning(self, t("error.generate"), message)
