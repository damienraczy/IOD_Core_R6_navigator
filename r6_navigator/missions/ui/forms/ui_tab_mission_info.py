# -*- coding: utf-8 -*-
# Auto-generated UI file for TabMissionInfo — do not edit manually.

from PySide6.QtCore import QMetaObject, QSize
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)


class Ui_TabMissionInfo(object):
    def setupUi(self, TabMissionInfo):
        if not TabMissionInfo.objectName():
            TabMissionInfo.setObjectName("TabMissionInfo")
        TabMissionInfo.resize(800, 600)

        self.main_layout = QVBoxLayout(TabMissionInfo)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea(TabMissionInfo)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)

        self.scroll_contents = QWidget()
        self.contents_layout = QVBoxLayout(self.scroll_contents)
        self.contents_layout.setSpacing(8)
        self.contents_layout.setContentsMargins(12, 12, 12, 12)

        # Fields section
        self.fields_form = QFormLayout()
        self.fields_form.setSpacing(6)

        self.lbl_client_name = QLabel(self.scroll_contents)
        self.lbl_client_name.setObjectName("lbl_client_name")
        self.entry_client_name = QLineEdit(self.scroll_contents)
        self.entry_client_name.setObjectName("entry_client_name")
        self.fields_form.addRow(self.lbl_client_name, self.entry_client_name)

        self.lbl_status = QLabel(self.scroll_contents)
        self.lbl_status.setObjectName("lbl_status")
        self.combo_status = QComboBox(self.scroll_contents)
        self.combo_status.setObjectName("combo_status")
        self.fields_form.addRow(self.lbl_status, self.combo_status)

        self.contents_layout.addLayout(self.fields_form)

        self.lbl_description = QLabel(self.scroll_contents)
        self.lbl_description.setObjectName("lbl_description")
        self.contents_layout.addWidget(self.lbl_description)

        self.text_description = QPlainTextEdit(self.scroll_contents)
        self.text_description.setObjectName("text_description")
        self.text_description.setMinimumSize(QSize(0, 80))
        self.contents_layout.addWidget(self.text_description)

        # Separator
        self.separator = QFrame(self.scroll_contents)
        self.separator.setFrameShape(QFrame.Shape.HLine)
        self.separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.contents_layout.addWidget(self.separator)

        # Stats section
        self.lbl_stats_title = QLabel(self.scroll_contents)
        self.lbl_stats_title.setObjectName("lbl_stats_title")
        self.contents_layout.addWidget(self.lbl_stats_title)

        self.stats_form = QFormLayout()
        self.stats_form.setSpacing(4)

        self.lbl_nb_interviews_key = QLabel(self.scroll_contents)
        self.lbl_nb_interviews_key.setObjectName("lbl_nb_interviews_key")
        self.lbl_nb_interviews_val = QLabel(self.scroll_contents)
        self.lbl_nb_interviews_val.setObjectName("lbl_nb_interviews_val")
        self.lbl_nb_interviews_val.setText("0")
        self.stats_form.addRow(self.lbl_nb_interviews_key, self.lbl_nb_interviews_val)

        self.lbl_nb_verbatims_key = QLabel(self.scroll_contents)
        self.lbl_nb_verbatims_key.setObjectName("lbl_nb_verbatims_key")
        self.lbl_nb_verbatims_val = QLabel(self.scroll_contents)
        self.lbl_nb_verbatims_val.setObjectName("lbl_nb_verbatims_val")
        self.lbl_nb_verbatims_val.setText("0")
        self.stats_form.addRow(self.lbl_nb_verbatims_key, self.lbl_nb_verbatims_val)

        self.lbl_nb_interps_key = QLabel(self.scroll_contents)
        self.lbl_nb_interps_key.setObjectName("lbl_nb_interps_key")
        self.lbl_nb_interps_val = QLabel(self.scroll_contents)
        self.lbl_nb_interps_val.setObjectName("lbl_nb_interps_val")
        self.lbl_nb_interps_val.setText("0")
        self.stats_form.addRow(self.lbl_nb_interps_key, self.lbl_nb_interps_val)

        self.contents_layout.addLayout(self.stats_form)

        self.vertical_spacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        self.contents_layout.addItem(self.vertical_spacer)

        self.scroll_area.setWidget(self.scroll_contents)
        self.main_layout.addWidget(self.scroll_area)

        QMetaObject.connectSlotsByName(TabMissionInfo)
