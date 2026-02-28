# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tabcoaching.ui'
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
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

class Ui_TabCoaching(object):
    def setupUi(self, TabCoaching):
        if not TabCoaching.objectName():
            TabCoaching.setObjectName(u"TabCoaching")
        TabCoaching.resize(620, 600)
        self.main_layout = QVBoxLayout(TabCoaching)
        self.main_layout.setSpacing(8)
        self.main_layout.setObjectName(u"main_layout")
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.coaching_header = QHBoxLayout()
        self.coaching_header.setObjectName(u"coaching_header")
        self.spacerItem = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.coaching_header.addItem(self.spacerItem)

        self.btn_generer = QPushButton(TabCoaching)
        self.btn_generer.setObjectName(u"btn_generer")

        self.coaching_header.addWidget(self.btn_generer)


        self.main_layout.addLayout(self.coaching_header)

        self.lbl_reflection_themes_key = QLabel(TabCoaching)
        self.lbl_reflection_themes_key.setObjectName(u"lbl_reflection_themes_key")
        font = QFont()
        font.setBold(True)
        self.lbl_reflection_themes_key.setFont(font)

        self.main_layout.addWidget(self.lbl_reflection_themes_key)

        self.text_reflection_themes = QPlainTextEdit(TabCoaching)
        self.text_reflection_themes.setObjectName(u"text_reflection_themes")
        self.text_reflection_themes.setMinimumSize(QSize(0, 100))

        self.main_layout.addWidget(self.text_reflection_themes)

        self.lbl_intervention_levers_key = QLabel(TabCoaching)
        self.lbl_intervention_levers_key.setObjectName(u"lbl_intervention_levers_key")
        self.lbl_intervention_levers_key.setFont(font)

        self.main_layout.addWidget(self.lbl_intervention_levers_key)

        self.text_intervention_levers = QPlainTextEdit(TabCoaching)
        self.text_intervention_levers.setObjectName(u"text_intervention_levers")
        self.text_intervention_levers.setMinimumSize(QSize(0, 100))

        self.main_layout.addWidget(self.text_intervention_levers)

        self.lbl_recommended_missions_key = QLabel(TabCoaching)
        self.lbl_recommended_missions_key.setObjectName(u"lbl_recommended_missions_key")
        self.lbl_recommended_missions_key.setFont(font)

        self.main_layout.addWidget(self.lbl_recommended_missions_key)

        self.text_recommended_missions = QPlainTextEdit(TabCoaching)
        self.text_recommended_missions.setObjectName(u"text_recommended_missions")
        self.text_recommended_missions.setMinimumSize(QSize(0, 100))

        self.main_layout.addWidget(self.text_recommended_missions)

        self.vertical_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.main_layout.addItem(self.vertical_spacer)


        self.retranslateUi(TabCoaching)

        QMetaObject.connectSlotsByName(TabCoaching)
    # setupUi

    def retranslateUi(self, TabCoaching):
        self.btn_generer.setText(QCoreApplication.translate("TabCoaching", u"G\u00e9n\u00e9rer", None))
#if QT_CONFIG(tooltip)
        self.btn_generer.setToolTip(QCoreApplication.translate("TabCoaching", u"G\u00e9n\u00e9rer le contenu coaching via IA", None))
#endif // QT_CONFIG(tooltip)
        self.lbl_reflection_themes_key.setText(QCoreApplication.translate("TabCoaching", u"Th\u00e8mes de r\u00e9flexion", None))
        self.text_reflection_themes.setPlaceholderText("")
        self.lbl_intervention_levers_key.setText(QCoreApplication.translate("TabCoaching", u"Leviers d'intervention", None))
        self.text_intervention_levers.setPlaceholderText("")
        self.lbl_recommended_missions_key.setText(QCoreApplication.translate("TabCoaching", u"Missions \u00e0 envisager", None))
        self.text_recommended_missions.setPlaceholderText("")
        pass
    # retranslateUi

