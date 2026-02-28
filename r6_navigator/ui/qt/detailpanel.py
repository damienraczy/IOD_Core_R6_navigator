"""Panneau de détail droit de R6 Navigator.

Contient la barre d'isomorphisme (capacités sœurs) et le QTabWidget
(Fiche / Questions / Coaching). Émet ``navigate_to`` quand l'utilisateur
clique sur un bouton de capacité sœur.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from r6_navigator.i18n import t


class DetailPanel(QWidget):
    """Panneau droit : barre d'isomorphisme + QTabWidget (Fiche / Questions / Coaching)."""

    navigate_to = Signal(str)   # capacity_id émis lors du clic sur un bouton sœur

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise le panneau et construit l'UI.

        Args:
            parent: Widget parent Qt (None pour un widget racine).
        """
        super().__init__(parent)
        self._current_capacity_id: str | None = None
        self._iso_dynamic: list[QWidget] = []   # widgets ajoutés dynamiquement dans la barre iso
        self._setup_ui()

    # ────────────────────────────────────────────────────────
    # API publique
    # ────────────────────────────────────────────────────────

    def set_tabs(
        self,
        tab_fiche: QWidget,
        tab_questions: QWidget,
        tab_coaching: QWidget,
    ) -> None:
        """Attache les trois onglets au QTabWidget (à appeler une seule fois avant l'affichage).

        Args:
            tab_fiche: Widget de l'onglet Fiche.
            tab_questions: Widget de l'onglet Questions.
            tab_coaching: Widget de l'onglet Coaching.
        """
        self.tabs.addTab(tab_fiche, t("tab.fiche"))
        self.tabs.addTab(tab_questions, t("tab.questions"))
        self.tabs.addTab(tab_coaching, t("tab.coaching"))

    def load_capacity(self, capacity_id: str, sibling_ids: list[str]) -> None:
        """Met à jour la barre d'isomorphisme pour la capacité sélectionnée.

        Args:
            capacity_id: Identifiant de la capacité courante (ex. ``"S1a"``).
            sibling_ids: Liste des identifiants des capacités sœurs (même axe + pôle).
        """
        self._current_capacity_id = capacity_id
        self._update_iso_bar(sibling_ids)

    def redraw(self) -> None:
        """Retraduit les libellés des onglets et de la barre iso après un changement de langue."""
        self._retranslate()

    # ────────────────────────────────────────────────────────
    # Construction de l'UI
    # ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Construit la barre d'isomorphisme, le séparateur et le QTabWidget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barre d'isomorphisme : libellé fixe + boutons dynamiques des capacités sœurs.
        self._iso_bar = QWidget()
        iso_layout = QHBoxLayout(self._iso_bar)
        iso_layout.setContentsMargins(8, 4, 8, 4)
        iso_layout.setSpacing(4)
        self._iso_label = QLabel()
        iso_layout.addWidget(self._iso_label)
        iso_layout.addStretch()
        layout.addWidget(self._iso_bar)

        # Séparateur horizontal entre la barre iso et les onglets.
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Onglets principaux.
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._retranslate()

    def _retranslate(self) -> None:
        """Met à jour le libellé de la barre iso et les titres des onglets."""
        self._iso_label.setText(t("isomorphism.label"))
        for i, key in enumerate(("tab.fiche", "tab.questions", "tab.coaching")):
            if i < self.tabs.count():
                self.tabs.setTabText(i, t(key))

    # ────────────────────────────────────────────────────────
    # Barre d'isomorphisme
    # ────────────────────────────────────────────────────────

    def _update_iso_bar(self, sibling_ids: list[str]) -> None:
        """Reconstruit les boutons de la barre d'isomorphisme pour les capacités sœurs.

        La capacité courante est affichée en gras et désactivée ; les autres
        sont des boutons cliquables qui émettent ``navigate_to``.

        Args:
            sibling_ids: Identifiants des capacités sœurs, dans l'ordre d'affichage.
        """
        iso_layout = self._iso_bar.layout()

        # Suppression des widgets dynamiques de la barre précédente.
        for w in self._iso_dynamic:
            iso_layout.removeWidget(w)
            w.deleteLater()
        self._iso_dynamic.clear()

        # Suppression du stretch final (tout ce qui suit le label fixe).
        while iso_layout.count() > 1:
            iso_layout.takeAt(iso_layout.count() - 1)

        arrow = t("isomorphism.arrow")
        for i, cid in enumerate(sibling_ids):
            if i > 0:
                lbl = QLabel(f" {arrow} ")
                iso_layout.addWidget(lbl)
                self._iso_dynamic.append(lbl)

            btn = QPushButton(cid)
            btn.setFlat(True)
            if cid == self._current_capacity_id:
                # La capacité active est mise en valeur visuellement et non cliquable.
                btn.setEnabled(False)
                btn.setStyleSheet("font-weight: bold; text-decoration: underline;")
            else:
                btn.clicked.connect(lambda _, c=cid: self.navigate_to.emit(c))
            iso_layout.addWidget(btn)
            self._iso_dynamic.append(btn)

        iso_layout.addStretch()
