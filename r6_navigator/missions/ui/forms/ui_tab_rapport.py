# -*- coding: utf-8 -*-
# Auto-generated UI file for TabRapport — do not edit manually.

from PySide6.QtCore import QMetaObject, QSize
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Ui_TabRapport(object):
    def setupUi(self, TabRapport):
        if not TabRapport.objectName():
            TabRapport.setObjectName("TabRapport")
        TabRapport.resize(800, 600)

        self.main_layout = QVBoxLayout(TabRapport)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(8)

        # Toolbar row
        self.toolbar_row = QHBoxLayout()
        self.btn_generate_report = QPushButton(TabRapport)
        self.btn_generate_report.setObjectName("btn_generate_report")
        self.btn_export_docx = QPushButton(TabRapport)
        self.btn_export_docx.setObjectName("btn_export_docx")
        self.lbl_status = QLabel(TabRapport)
        self.lbl_status.setObjectName("lbl_status")
        self.toolbar_row.addWidget(self.btn_generate_report)
        self.toolbar_row.addWidget(self.btn_export_docx)
        self.toolbar_row.addWidget(self.lbl_status)
        self.toolbar_row.addStretch()
        self.main_layout.addLayout(self.toolbar_row)

        # Report content
        self.text_report = QPlainTextEdit(TabRapport)
        self.text_report.setObjectName("text_report")
        self.text_report.setMinimumSize(QSize(0, 300))
        self.text_report.setReadOnly(True)
        self.main_layout.addWidget(self.text_report, 1)

        # Progress label
        self.lbl_progress = QLabel(TabRapport)
        self.lbl_progress.setObjectName("lbl_progress")
        self.lbl_progress.setVisible(False)
        self.main_layout.addWidget(self.lbl_progress)

        QMetaObject.connectSlotsByName(TabRapport)
