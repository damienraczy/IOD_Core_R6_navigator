# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tabfiche.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

class Ui_TabFiche(object):
    def setupUi(self, TabFiche):
        if not TabFiche.objectName():
            TabFiche.setObjectName(u"TabFiche")
        TabFiche.resize(1000, 800)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(TabFiche.sizePolicy().hasHeightForWidth())
        TabFiche.setSizePolicy(sizePolicy)
        self.main_layout = QVBoxLayout(TabFiche)
        self.main_layout.setObjectName(u"main_layout")
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea(TabFiche)
        self.scroll_area.setObjectName(u"scroll_area")
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_contents = QWidget()
        self.scroll_contents.setObjectName(u"scroll_contents")
        self.scroll_contents.setGeometry(QRect(0, 0, 1000, 800))
        self.contents_layout = QVBoxLayout(self.scroll_contents)
        self.contents_layout.setSpacing(8)
        self.contents_layout.setObjectName(u"contents_layout")
        self.contents_layout.setContentsMargins(12, 12, 12, 12)
        self.header_frame = QFrame(self.scroll_contents)
        self.header_frame.setObjectName(u"header_frame")
        self.header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.header_frame.setFrameShadow(QFrame.Shadow.Sunken)
        self.header_form = QFormLayout(self.header_frame)
        self.header_form.setObjectName(u"header_form")
        self.lbl_level_key = QLabel(self.header_frame)
        self.lbl_level_key.setObjectName(u"lbl_level_key")

        self.header_form.setWidget(0, QFormLayout.ItemRole.LabelRole, self.lbl_level_key)

        self.lbl_level_val = QLabel(self.header_frame)
        self.lbl_level_val.setObjectName(u"lbl_level_val")

        self.header_form.setWidget(0, QFormLayout.ItemRole.FieldRole, self.lbl_level_val)

        self.lbl_axis_key = QLabel(self.header_frame)
        self.lbl_axis_key.setObjectName(u"lbl_axis_key")

        self.header_form.setWidget(1, QFormLayout.ItemRole.LabelRole, self.lbl_axis_key)

        self.lbl_axis_val = QLabel(self.header_frame)
        self.lbl_axis_val.setObjectName(u"lbl_axis_val")

        self.header_form.setWidget(1, QFormLayout.ItemRole.FieldRole, self.lbl_axis_val)

        self.lbl_pole_key = QLabel(self.header_frame)
        self.lbl_pole_key.setObjectName(u"lbl_pole_key")

        self.header_form.setWidget(2, QFormLayout.ItemRole.LabelRole, self.lbl_pole_key)

        self.lbl_pole_val = QLabel(self.header_frame)
        self.lbl_pole_val.setObjectName(u"lbl_pole_val")

        self.header_form.setWidget(2, QFormLayout.ItemRole.FieldRole, self.lbl_pole_val)

        self.lbl_code_key = QLabel(self.header_frame)
        self.lbl_code_key.setObjectName(u"lbl_code_key")

        self.header_form.setWidget(3, QFormLayout.ItemRole.LabelRole, self.lbl_code_key)

        self.lbl_code_val = QLabel(self.header_frame)
        self.lbl_code_val.setObjectName(u"lbl_code_val")

        self.header_form.setWidget(3, QFormLayout.ItemRole.FieldRole, self.lbl_code_val)


        self.contents_layout.addWidget(self.header_frame)

        self.line_separator = QFrame(self.scroll_contents)
        self.line_separator.setObjectName(u"line_separator")
        self.line_separator.setFrameShape(QFrame.Shape.HLine)
        self.line_separator.setFrameShadow(QFrame.Shadow.Sunken)

        self.contents_layout.addWidget(self.line_separator)

        self.label_row = QHBoxLayout()
        self.label_row.setSpacing(6)
        self.label_row.setObjectName(u"label_row")
        self.lbl_label_key = QLabel(self.scroll_contents)
        self.lbl_label_key.setObjectName(u"lbl_label_key")

        self.label_row.addWidget(self.lbl_label_key)

        self.entry_label = QLineEdit(self.scroll_contents)
        self.entry_label.setObjectName(u"entry_label")

        self.label_row.addWidget(self.entry_label)

        self.btn_generer = QPushButton(self.scroll_contents)
        self.btn_generer.setObjectName(u"btn_generer")

        self.label_row.addWidget(self.btn_generer)


        self.contents_layout.addLayout(self.label_row)

        self.fields_layout = QVBoxLayout()
        self.fields_layout.setSpacing(4)
        self.fields_layout.setObjectName(u"fields_layout")
        self.lbl_definition_key = QLabel(self.scroll_contents)
        self.lbl_definition_key.setObjectName(u"lbl_definition_key")

        self.fields_layout.addWidget(self.lbl_definition_key)

        self.text_definition = QPlainTextEdit(self.scroll_contents)
        self.text_definition.setObjectName(u"text_definition")
        self.text_definition.setMinimumSize(QSize(0, 80))

        self.fields_layout.addWidget(self.text_definition)

        self.lbl_central_function_key = QLabel(self.scroll_contents)
        self.lbl_central_function_key.setObjectName(u"lbl_central_function_key")

        self.fields_layout.addWidget(self.lbl_central_function_key)

        self.text_central_function = QPlainTextEdit(self.scroll_contents)
        self.text_central_function.setObjectName(u"text_central_function")
        self.text_central_function.setMinimumSize(QSize(0, 80))

        self.fields_layout.addWidget(self.text_central_function)

        self.lbl_observable_key = QLabel(self.scroll_contents)
        self.lbl_observable_key.setObjectName(u"lbl_observable_key")

        self.fields_layout.addWidget(self.lbl_observable_key)

        self.text_observable = QPlainTextEdit(self.scroll_contents)
        self.text_observable.setObjectName(u"text_observable")
        self.text_observable.setMinimumSize(QSize(0, 80))

        self.fields_layout.addWidget(self.text_observable)

        self.lbl_risk_insufficient_key = QLabel(self.scroll_contents)
        self.lbl_risk_insufficient_key.setObjectName(u"lbl_risk_insufficient_key")

        self.fields_layout.addWidget(self.lbl_risk_insufficient_key)

        self.text_risk_insufficient = QPlainTextEdit(self.scroll_contents)
        self.text_risk_insufficient.setObjectName(u"text_risk_insufficient")
        self.text_risk_insufficient.setMinimumSize(QSize(0, 80))

        self.fields_layout.addWidget(self.text_risk_insufficient)

        self.lbl_risk_excessive_key = QLabel(self.scroll_contents)
        self.lbl_risk_excessive_key.setObjectName(u"lbl_risk_excessive_key")

        self.fields_layout.addWidget(self.lbl_risk_excessive_key)

        self.text_risk_excessive = QPlainTextEdit(self.scroll_contents)
        self.text_risk_excessive.setObjectName(u"text_risk_excessive")
        self.text_risk_excessive.setMinimumSize(QSize(0, 80))

        self.fields_layout.addWidget(self.text_risk_excessive)


        self.contents_layout.addLayout(self.fields_layout)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.contents_layout.addItem(self.vertical_spacer)

        self.scroll_area.setWidget(self.scroll_contents)

        self.main_layout.addWidget(self.scroll_area)


        self.retranslateUi(TabFiche)

        QMetaObject.connectSlotsByName(TabFiche)
    # setupUi

    def retranslateUi(self, TabFiche):
        self.lbl_level_key.setText(QCoreApplication.translate("TabFiche", u"Niveau", None))
        self.lbl_level_val.setText("")
        self.lbl_axis_key.setText(QCoreApplication.translate("TabFiche", u"Axe", None))
        self.lbl_axis_val.setText("")
        self.lbl_pole_key.setText(QCoreApplication.translate("TabFiche", u"P\u00f4le", None))
        self.lbl_pole_val.setText("")
        self.lbl_code_key.setText(QCoreApplication.translate("TabFiche", u"Code", None))
        self.lbl_code_val.setText("")
        self.lbl_label_key.setText(QCoreApplication.translate("TabFiche", u"Intitul\u00e9", None))
        self.entry_label.setPlaceholderText("")
#if QT_CONFIG(tooltip)
        self.btn_generer.setToolTip(QCoreApplication.translate("TabFiche", u"G\u00e9n\u00e9rer le contenu via IA", None))
#endif // QT_CONFIG(tooltip)
        self.btn_generer.setText(QCoreApplication.translate("TabFiche", u"G\u00e9n\u00e9rer", None))
        self.lbl_definition_key.setText(QCoreApplication.translate("TabFiche", u"D\u00e9finition", None))
        self.lbl_central_function_key.setText(QCoreApplication.translate("TabFiche", u"Fonction centrale", None))
        self.lbl_observable_key.setText(QCoreApplication.translate("TabFiche", u"Observable", None))
        self.lbl_risk_insufficient_key.setText(QCoreApplication.translate("TabFiche", u"Risque si insuffisant", None))
        self.lbl_risk_excessive_key.setText(QCoreApplication.translate("TabFiche", u"Risque si excessif", None))
        pass
    # retranslateUi

