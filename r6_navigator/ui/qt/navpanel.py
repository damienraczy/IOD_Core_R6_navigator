"""Panneau de navigation gauche de R6 Navigator.

Affiche un QTreeWidget hiérarchique (Niveau → Axe → Capacité) avec trois
filtres combinés (niveau, axe, pôle). Émet ``capacity_selected`` quand
l'utilisateur clique sur une feuille.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from r6_navigator.i18n import current_lang, t
from r6_navigator.services import crud

# Couleurs associées à chaque pôle pour différencier visuellement les feuilles.
_POLE_COLORS: dict[str, QColor] = {
    "a": QColor("#1565C0"),   # bleu — pôle agentif
    "b": QColor("#E65100"),   # orange — pôle instrumental
}

# Rôle Qt utilisé pour stocker le capacity_id sur les nœuds feuilles.
_ROLE_CAPACITY_ID = Qt.ItemDataRole.UserRole


class NavPanel(QWidget):
    """Panneau de navigation gauche : 3 filtres combo + arbre des capacités."""

    capacity_selected = Signal(str)   # capacity_id émis au clic sur une feuille

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialise le panneau et construit l'UI.

        Args:
            parent: Widget parent Qt (None pour un widget racine).
        """
        super().__init__(parent)
        self._session_factory = None
        self._selected_id: str | None = None
        self._setup_ui()
        self._setup_filter_combos()
        self._connect_signals()

    # ────────────────────────────────────────────────────────
    # API publique
    # ────────────────────────────────────────────────────────

    def set_session_factory(self, factory) -> None:
        """Injecte la factory de sessions SQLAlchemy.

        Args:
            factory: Callable retournant une session SQLAlchemy (context-manager).
        """
        self._session_factory = factory

    def populate(self) -> None:
        """Charge l'arbre depuis la base de données (appeler après set_session_factory)."""
        self._populate_tree()

    def redraw(self) -> None:
        """Reconstruit les combos de filtre et l'arbre après un changement de langue."""
        self._rebuild_filter_combos()
        self._populate_tree()

    def select_capacity(self, capacity_id: str) -> None:
        """Met en surbrillance la feuille correspondante sans émettre le signal.

        Args:
            capacity_id: Identifiant de la capacité à sélectionner (ex. ``"S1a"``).
        """
        self._selected_id = capacity_id
        self._highlight(capacity_id)

    # ────────────────────────────────────────────────────────
    # Construction de l'UI
    # ────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        """Construit la ligne de filtres et le QTreeWidget."""
        main = QVBoxLayout(self)
        main.setContentsMargins(4, 4, 4, 4)
        main.setSpacing(4)

        # Ligne de filtres combinés (niveau / axe / pôle).
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)
        self.combo_level = QComboBox()
        self.combo_axis = QComboBox()
        self.combo_pole = QComboBox()
        filter_row.addWidget(self.combo_level)
        filter_row.addWidget(self.combo_axis)
        filter_row.addWidget(self.combo_pole)
        main.addLayout(filter_row)

        # Arbre principal des capacités.
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.setMinimumWidth(240)
        main.addWidget(self.tree)

    def _setup_filter_combos(self) -> None:
        """Remplit les combos de filtre avec les valeurs initiales."""
        self._fill_filter_combos()

    def _fill_filter_combos(self) -> None:
        """Peuple les trois combos (niveau, axe, pôle) avec les libellés traduits."""
        all_label = t("nav.filter.all")

        self.combo_level.clear()
        self.combo_level.addItem(all_label, None)
        for code in ("S", "O", "I"):
            self.combo_level.addItem(f"{code} — {t(f'level.{code}')}", code)

        self.combo_axis.clear()
        self.combo_axis.addItem(all_label, None)
        for n in (1, 2, 3):
            self.combo_axis.addItem(f"{n} — {t(f'axis.{n}')}", n)

        self.combo_pole.clear()
        self.combo_pole.addItem(all_label, None)
        for code in ("a", "b"):
            self.combo_pole.addItem(f"{code} — {t(f'pole.{code}')}", code)

    def _rebuild_filter_combos(self) -> None:
        """Reconstruit les combos de filtre en préservant la sélection courante."""
        cur_level = self.combo_level.currentData()
        cur_axis = self.combo_axis.currentData()
        cur_pole = self.combo_pole.currentData()

        self.combo_level.blockSignals(True)
        self.combo_axis.blockSignals(True)
        self.combo_pole.blockSignals(True)

        self._fill_filter_combos()

        # Restaure les valeurs sélectionnées avant la reconstruction.
        for combo, val in (
            (self.combo_level, cur_level),
            (self.combo_axis, cur_axis),
            (self.combo_pole, cur_pole),
        ):
            for i in range(combo.count()):
                if combo.itemData(i) == val:
                    combo.setCurrentIndex(i)
                    break

        self.combo_level.blockSignals(False)
        self.combo_axis.blockSignals(False)
        self.combo_pole.blockSignals(False)

    def _connect_signals(self) -> None:
        """Connecte les signaux des combos et du clic sur l'arbre."""
        self.combo_level.currentIndexChanged.connect(self._populate_tree)
        self.combo_axis.currentIndexChanged.connect(self._populate_tree)
        self.combo_pole.currentIndexChanged.connect(self._populate_tree)
        self.tree.itemClicked.connect(self._on_item_clicked)

    # ────────────────────────────────────────────────────────
    # Population de l'arbre
    # ────────────────────────────────────────────────────────

    def _populate_tree(self) -> None:
        """Reconstruit l'arbre en appliquant les filtres actifs et la langue courante."""
        if self._session_factory is None:
            return

        filter_level: str | None = self.combo_level.currentData()
        filter_axis: int | None = self.combo_axis.currentData()
        filter_pole: str | None = self.combo_pole.currentData()
        lang = current_lang()

        with self._session_factory() as session:
            capacities = crud.get_all_capacities(session)
            # Pré-chargement des traductions pour éviter N requêtes dans la boucle.
            trans_map: dict[str, str] = {}
            for cap in capacities:
                tr = crud.get_capacity_translation(session, cap.capacity_id, lang)
                trans_map[cap.capacity_id] = tr.label if tr else cap.capacity_id

        self.tree.blockSignals(True)
        self.tree.clear()

        axis_prefix = t("nav.filter.axis")

        for level_code in ("S", "O", "I"):
            if filter_level is not None and filter_level != level_code:
                continue

            level_caps = [c for c in capacities if c.level_code == level_code]

            level_node = QTreeWidgetItem(self.tree)
            level_node.setText(0, f"{level_code} — {t(f'level.{level_code}')}")
            level_node.setFlags(Qt.ItemFlag.ItemIsEnabled)
            level_node.setExpanded(True)

            has_any = False
            for axis_num in (1, 2, 3):
                if filter_axis is not None and filter_axis != axis_num:
                    continue

                axis_caps = [
                    c for c in level_caps
                    if c.axis_number == axis_num and (
                        filter_pole is None or c.pole_code == filter_pole
                    )
                ]
                if not axis_caps:
                    continue

                has_any = True
                axis_node = QTreeWidgetItem(level_node)
                axis_node.setText(0, f"{axis_prefix} {axis_num} — {t(f'axis.{axis_num}')}")
                axis_node.setFlags(Qt.ItemFlag.ItemIsEnabled)
                axis_node.setExpanded(True)

                for cap in axis_caps:
                    label = trans_map.get(cap.capacity_id, cap.capacity_id)
                    # Troncature pour éviter les libellés trop longs dans l'arbre.
                    truncated = label[:40] + "…" if len(label) > 40 else label
                    leaf = QTreeWidgetItem(axis_node)
                    leaf.setText(0, f"{cap.capacity_id}  {truncated}  [{cap.pole_code}]")
                    leaf.setData(0, _ROLE_CAPACITY_ID, cap.capacity_id)
                    leaf.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    color = _POLE_COLORS.get(cap.pole_code)
                    if color:
                        leaf.setForeground(0, QBrush(color))

            # Supprime le nœud de niveau si aucune capacité ne correspond aux filtres.
            if not has_any:
                root = self.tree.invisibleRootItem()
                root.removeChild(level_node)

        self.tree.blockSignals(False)

        if self._selected_id:
            self._highlight(self._selected_id)

    def _highlight(self, capacity_id: str) -> None:
        """Sélectionne visuellement la feuille sans émettre de signal.

        Args:
            capacity_id: Identifiant de la capacité à mettre en surbrillance.
        """
        self.tree.blockSignals(True)
        self.tree.clearSelection()
        leaf = self._find_leaf(capacity_id)
        if leaf:
            leaf.setSelected(True)
            self.tree.scrollToItem(leaf)
        self.tree.blockSignals(False)

    def _find_leaf(self, capacity_id: str) -> QTreeWidgetItem | None:
        """Recherche récursivement la feuille correspondant à un capacity_id.

        Args:
            capacity_id: Identifiant à rechercher.

        Returns:
            Le QTreeWidgetItem feuille correspondant, ou None si introuvable.
        """
        root = self.tree.invisibleRootItem()
        return self._search(root, capacity_id)

    def _search(
        self, node: QTreeWidgetItem, capacity_id: str
    ) -> QTreeWidgetItem | None:
        """Parcourt récursivement l'arbre à la recherche d'un nœud feuille.

        Args:
            node: Nœud à partir duquel la recherche commence.
            capacity_id: Identifiant à trouver dans les données UserRole.

        Returns:
            Le nœud correspondant, ou None si absent dans ce sous-arbre.
        """
        for i in range(node.childCount()):
            child = node.child(i)
            if child.data(0, _ROLE_CAPACITY_ID) == capacity_id:
                return child
            found = self._search(child, capacity_id)
            if found:
                return found
        return None

    # ────────────────────────────────────────────────────────
    # Gestionnaire d'événements
    # ────────────────────────────────────────────────────────

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Émet ``capacity_selected`` quand l'utilisateur clique sur une feuille.

        Args:
            item: Élément cliqué dans l'arbre.
            _column: Colonne cliquée (toujours 0, non utilisé).
        """
        capacity_id = item.data(0, _ROLE_CAPACITY_ID)
        if capacity_id:
            self._selected_id = capacity_id
            self.capacity_selected.emit(capacity_id)
