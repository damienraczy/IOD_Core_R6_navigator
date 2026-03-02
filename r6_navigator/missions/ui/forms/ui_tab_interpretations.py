# -*- coding: utf-8 -*-
# Auto-generated UI file for TabInterpretations — do not edit manually.

from PySide6.QtCore import QMetaObject
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


class Ui_TabInterpretations(object):
    def setupUi(self, TabInterpretations):
        if not TabInterpretations.objectName():
            TabInterpretations.setObjectName("TabInterpretations")
        TabInterpretations.resize(900, 600)

        self.main_layout = QVBoxLayout(TabInterpretations)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(6)

        # Stats bar
        self.stats_row = QHBoxLayout()
        self.lbl_stats = QLabel(TabInterpretations)
        self.lbl_stats.setObjectName("lbl_stats")
        self.stats_row.addWidget(self.lbl_stats)
        self.stats_row.addStretch()
        self.main_layout.addLayout(self.stats_row)

        # Table
        self.table_interpretations = QTableWidget(TabInterpretations)
        self.table_interpretations.setObjectName("table_interpretations")
        self.table_interpretations.setColumnCount(6)
        self.table_interpretations.setRowCount(0)
        self.main_layout.addWidget(self.table_interpretations, 1)

        QMetaObject.connectSlotsByName(TabInterpretations)
