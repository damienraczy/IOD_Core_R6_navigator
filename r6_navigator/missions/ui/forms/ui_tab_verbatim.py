# -*- coding: utf-8 -*-
# Auto-generated UI file for TabVerbatim — do not edit manually.

from PySide6.QtCore import QMetaObject, QSize
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class Ui_TabVerbatim(object):
    def setupUi(self, TabVerbatim):
        if not TabVerbatim.objectName():
            TabVerbatim.setObjectName("TabVerbatim")
        TabVerbatim.resize(800, 600)

        self.main_layout = QVBoxLayout(TabVerbatim)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(8)

        # Title row
        self.title_row = QHBoxLayout()
        self.lbl_title = QLabel(TabVerbatim)
        self.lbl_title.setObjectName("lbl_title")
        self.entry_title = QLineEdit(TabVerbatim)
        self.entry_title.setObjectName("entry_title")
        self.title_row.addWidget(self.lbl_title)
        self.title_row.addWidget(self.entry_title)
        self.main_layout.addLayout(self.title_row)

        # Status row
        self.status_row = QHBoxLayout()
        self.lbl_status_key = QLabel(TabVerbatim)
        self.lbl_status_key.setObjectName("lbl_status_key")
        self.lbl_status_val = QLabel(TabVerbatim)
        self.lbl_status_val.setObjectName("lbl_status_val")
        self.lbl_status_val.setText("—")
        self.status_row.addWidget(self.lbl_status_key)
        self.status_row.addWidget(self.lbl_status_val)
        self.status_row.addStretch()
        self.btn_analyze = QPushButton(TabVerbatim)
        self.btn_analyze.setObjectName("btn_analyze")
        self.status_row.addWidget(self.btn_analyze)
        self.main_layout.addLayout(self.status_row)

        # Separator
        self.separator = QFrame(TabVerbatim)
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.addWidget(self.separator)

        # Raw text
        self.lbl_raw_text = QLabel(TabVerbatim)
        self.lbl_raw_text.setObjectName("lbl_raw_text")
        self.main_layout.addWidget(self.lbl_raw_text)

        self.text_raw = QPlainTextEdit(TabVerbatim)
        self.text_raw.setObjectName("text_raw")
        self.text_raw.setMinimumSize(QSize(0, 200))
        self.main_layout.addWidget(self.text_raw, 1)

        # Progress label (hidden by default)
        self.lbl_progress = QLabel(TabVerbatim)
        self.lbl_progress.setObjectName("lbl_progress")
        self.lbl_progress.setVisible(False)
        self.main_layout.addWidget(self.lbl_progress)

        QMetaObject.connectSlotsByName(TabVerbatim)
