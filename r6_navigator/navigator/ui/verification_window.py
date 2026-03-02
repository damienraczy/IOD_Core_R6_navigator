"""Fenêtre non-modale de vérification par 3 juges LLM.

Affiche les verdicts des 3 juges, un verdict agrégé, et gère un historique
de versions intra-session permettant de naviguer entre les états successifs
d'une fiche.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from r6_navigator.i18n import t
from r6_navigator.navigator.services.ai_judge import JudgeResults, SingleJudgeResult

# Mapping verdict → étoiles et icône
_STARS = {
    "pas_bon": "★☆☆",
    "satisfaisant": "★★☆",
    "tres_bon": "★★★",
}
_ICONS = {
    "pas_bon": "✗",
    "satisfaisant": "⚠",
    "tres_bon": "✓",
}


class VerificationWindow(QDialog):
    """Fenêtre non-modale affichant les résultats des 3 juges LLM.

    Signals:
        restore_version: Émis avec le dict ``content`` quand l'utilisateur
            navigue vers une version précédente/suivante/originale.
    """

    restore_version = Signal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setMinimumWidth(560)

        self._versions: list[tuple[dict, JudgeResults]] = []
        self._current_idx: int = 0

        self._build_ui()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def add_version(self, content: dict, results: JudgeResults) -> None:
        """Ajoute une nouvelle version et l'affiche immédiatement.

        Args:
            content: Snapshot des champs de la fiche au moment du jugement.
            results: Résultats des 3 juges.
        """
        self._versions.append((content, results))
        self._current_idx = len(self._versions) - 1
        self._refresh()

    def clear_history(self) -> None:
        """Efface tout l'historique et masque la fenêtre."""
        self._versions.clear()
        self._current_idx = 0
        self.hide()

    def show_running(self) -> None:
        """Affiche un indicateur « Évaluation en cours… » pendant les appels Ollama."""
        self._lbl_running.setText(t("judge.running"))
        self._lbl_running.setVisible(True)
        for frame in (self._frame_axioms, self._frame_halliday, self._frame_coherence):
            frame.setVisible(False)
        self._frame_aggregate.setVisible(False)
        self._nav_bar.setVisible(False)
        self._update_title()
        self.show()
        self.raise_()

    # ------------------------------------------------------------------ #
    # Private — build UI                                                   #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # Running indicator (visible only during evaluation)
        self._lbl_running = QLabel()
        self._lbl_running.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_running.setStyleSheet("font-style: italic; color: #666;")
        self._lbl_running.setVisible(False)
        root.addWidget(self._lbl_running)

        # Three judge frames
        self._frame_axioms = self._make_judge_frame()
        self._frame_halliday = self._make_judge_frame()
        self._frame_coherence = self._make_judge_frame()
        root.addWidget(self._frame_axioms)
        root.addWidget(self._frame_halliday)
        root.addWidget(self._frame_coherence)

        # Aggregate verdict frame
        self._frame_aggregate = QFrame()
        self._frame_aggregate.setFrameShape(QFrame.Shape.StyledPanel)
        agg_layout = QHBoxLayout(self._frame_aggregate)
        agg_layout.setContentsMargins(8, 6, 8, 6)
        self._lbl_aggregate_title = QLabel()
        self._lbl_aggregate_title.setStyleSheet("font-weight: bold;")
        self._lbl_aggregate_verdict = QLabel()
        self._lbl_aggregate_verdict.setStyleSheet("font-size: 14px;")
        agg_layout.addWidget(self._lbl_aggregate_title)
        agg_layout.addStretch()
        agg_layout.addWidget(self._lbl_aggregate_verdict)
        root.addWidget(self._frame_aggregate)

        # Navigation bar
        self._nav_bar = QWidget()
        nav_layout = QHBoxLayout(self._nav_bar)
        nav_layout.setContentsMargins(0, 4, 0, 0)
        self._btn_prev = QPushButton("← Précédent")
        self._btn_original = QPushButton(t("judge.original"))
        self._btn_next = QPushButton("Suivant →")
        self._lbl_version = QLabel()
        self._lbl_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(self._btn_prev)
        nav_layout.addWidget(self._btn_original)
        nav_layout.addStretch()
        nav_layout.addWidget(self._lbl_version)
        nav_layout.addStretch()
        nav_layout.addWidget(self._btn_next)
        root.addWidget(self._nav_bar)

        # Connect navigation
        self._btn_prev.clicked.connect(self._go_prev)
        self._btn_next.clicked.connect(self._go_next)
        self._btn_original.clicked.connect(self._go_original)

        # Initially hidden
        for frame in (self._frame_axioms, self._frame_halliday, self._frame_coherence):
            frame.setVisible(False)
        self._frame_aggregate.setVisible(False)
        self._nav_bar.setVisible(False)

    def _make_judge_frame(self) -> QFrame:
        """Crée un QFrame réutilisable pour afficher le résultat d'un juge."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        header = QHBoxLayout()
        lbl_name = QLabel()
        lbl_name.setStyleSheet("font-weight: bold;")
        lbl_stars = QLabel()
        lbl_stars.setStyleSheet("font-size: 16px; color: #f0a500;")
        lbl_verdict = QLabel()
        header.addWidget(lbl_name)
        header.addStretch()
        header.addWidget(lbl_stars)
        header.addWidget(lbl_verdict)
        layout.addLayout(header)

        lbl_just = QLabel()
        lbl_just.setWordWrap(True)
        lbl_just.setStyleSheet("color: #444; margin-top: 2px;")
        layout.addWidget(lbl_just)

        lbl_error = QLabel()
        lbl_error.setWordWrap(True)
        lbl_error.setStyleSheet("color: #c00;")
        lbl_error.setVisible(False)
        layout.addWidget(lbl_error)

        # Store refs as frame attributes for easy update
        frame._lbl_name = lbl_name          # type: ignore[attr-defined]
        frame._lbl_stars = lbl_stars        # type: ignore[attr-defined]
        frame._lbl_verdict = lbl_verdict    # type: ignore[attr-defined]
        frame._lbl_just = lbl_just          # type: ignore[attr-defined]
        frame._lbl_error = lbl_error        # type: ignore[attr-defined]
        return frame

    # ------------------------------------------------------------------ #
    # Private — refresh display                                            #
    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        """Rafraîchit tous les widgets depuis la version courante."""
        self._lbl_running.setVisible(False)

        if not self._versions:
            for frame in (self._frame_axioms, self._frame_halliday, self._frame_coherence):
                frame.setVisible(False)
            self._frame_aggregate.setVisible(False)
            self._nav_bar.setVisible(False)
            return

        _content, results = self._versions[self._current_idx]

        judge_map = [
            (self._frame_axioms, results.judge_axioms, t("judge.axioms_r6")),
            (self._frame_halliday, results.judge_halliday, t("judge.halliday")),
            (self._frame_coherence, results.judge_coherence, t("judge.coherence")),
        ]
        for frame, judge, title in judge_map:
            self._fill_judge_frame(frame, judge, title)
            frame.setVisible(True)

        # Aggregate
        agg_icon = _ICONS.get(results.aggregate_verdict, "?")
        agg_label = t(f"judge.verdict.{results.aggregate_verdict}")
        self._lbl_aggregate_title.setText(t("judge.aggregate") + " :")
        self._lbl_aggregate_verdict.setText(f"{agg_icon} {agg_label}")
        self._frame_aggregate.setVisible(True)

        # Version label
        n = self._current_idx + 1
        total = len(self._versions)
        self._lbl_version.setText(t("judge.version", n=n, total=total))

        # Navigation buttons
        self._btn_prev.setEnabled(self._current_idx > 0)
        self._btn_original.setEnabled(self._current_idx > 0)
        self._btn_next.setEnabled(self._current_idx < len(self._versions) - 1)
        self._nav_bar.setVisible(True)

        self._update_title()
        self.show()
        self.raise_()

    def _fill_judge_frame(
        self, frame: QFrame, judge: SingleJudgeResult, title: str
    ) -> None:
        stars = _STARS.get(judge.verdict, "?")
        verdict_label = t(f"judge.verdict.{judge.verdict}")
        frame._lbl_name.setText(title)          # type: ignore[attr-defined]
        frame._lbl_stars.setText(stars)         # type: ignore[attr-defined]
        frame._lbl_verdict.setText(verdict_label)  # type: ignore[attr-defined]
        frame._lbl_just.setText(judge.justification)  # type: ignore[attr-defined]
        if judge.error:
            frame._lbl_error.setText(judge.error)   # type: ignore[attr-defined]
            frame._lbl_error.setVisible(True)        # type: ignore[attr-defined]
        else:
            frame._lbl_error.setVisible(False)       # type: ignore[attr-defined]

    def _update_title(self) -> None:
        # Capacity ID is stored in the content dict under "capacity_id" if provided,
        # otherwise the window title stays generic.
        capacity_id = ""
        if self._versions:
            content, _ = self._versions[self._current_idx]
            capacity_id = content.get("capacity_id", "")
        if capacity_id:
            self.setWindowTitle(t("judge.window_title", capacity_id=capacity_id))
        else:
            self.setWindowTitle(t("judge.window_title", capacity_id=""))

    # ------------------------------------------------------------------ #
    # Navigation slots                                                     #
    # ------------------------------------------------------------------ #

    def _go_prev(self) -> None:
        if self._current_idx > 0:
            self._current_idx -= 1
            self._refresh()
            content, _ = self._versions[self._current_idx]
            self.restore_version.emit(content)

    def _go_next(self) -> None:
        if self._current_idx < len(self._versions) - 1:
            self._current_idx += 1
            self._refresh()
            content, _ = self._versions[self._current_idx]
            self.restore_version.emit(content)

    def _go_original(self) -> None:
        if self._versions:
            self._current_idx = 0
            self._refresh()
            content, _ = self._versions[0]
            self.restore_version.emit(content)
