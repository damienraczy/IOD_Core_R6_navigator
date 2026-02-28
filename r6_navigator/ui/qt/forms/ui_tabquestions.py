# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tabquestions.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QSpacerItem, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

class Ui_TabQuestions(object):
    def setupUi(self, TabQuestions):
        if not TabQuestions.objectName():
            TabQuestions.setObjectName(u"TabQuestions")
        TabQuestions.resize(620, 700)
        self.main_layout = QVBoxLayout(TabQuestions)
        self.main_layout.setSpacing(8)
        self.main_layout.setObjectName(u"main_layout")
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.questions_header = QHBoxLayout()
        self.questions_header.setObjectName(u"questions_header")
        self.lbl_questions_title = QLabel(TabQuestions)
        self.lbl_questions_title.setObjectName(u"lbl_questions_title")
        font = QFont()
        font.setBold(True)
        self.lbl_questions_title.setFont(font)

        self.questions_header.addWidget(self.lbl_questions_title)

        self.spacerItem = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.questions_header.addItem(self.spacerItem)

        self.btn_generer = QPushButton(TabQuestions)
        self.btn_generer.setObjectName(u"btn_generer")

        self.questions_header.addWidget(self.btn_generer)

        self.btn_new_question = QPushButton(TabQuestions)
        self.btn_new_question.setObjectName(u"btn_new_question")

        self.questions_header.addWidget(self.btn_new_question)


        self.main_layout.addLayout(self.questions_header)

        self.scroll_questions = QScrollArea(TabQuestions)
        self.scroll_questions.setObjectName(u"scroll_questions")
        self.scroll_questions.setWidgetResizable(True)
        self.scroll_questions.setFrameShape(QFrame.StyledPanel)
        self.scroll_questions.setMinimumSize(QSize(0, 120))
        self.questions_container = QWidget()
        self.questions_container.setObjectName(u"questions_container")
        self.questions_container.setGeometry(QRect(0, 0, 616, 118))
        self.questions_layout = QVBoxLayout(self.questions_container)
        self.questions_layout.setSpacing(2)
        self.questions_layout.setObjectName(u"questions_layout")
        self.questions_layout.setContentsMargins(4, 4, 4, 4)
        self.questions_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.questions_layout.addItem(self.questions_spacer)

        self.scroll_questions.setWidget(self.questions_container)

        self.main_layout.addWidget(self.scroll_questions)

        self.line_separator = QFrame(TabQuestions)
        self.line_separator.setObjectName(u"line_separator")
        self.line_separator.setFrameShape(QFrame.HLine)
        self.line_separator.setFrameShadow(QFrame.Sunken)

        self.main_layout.addWidget(self.line_separator)

        self.items_header = QHBoxLayout()
        self.items_header.setObjectName(u"items_header")
        self.lbl_items_title = QLabel(TabQuestions)
        self.lbl_items_title.setObjectName(u"lbl_items_title")
        self.lbl_items_title.setFont(font)

        self.items_header.addWidget(self.lbl_items_title)

        self.spacerItem1 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.items_header.addItem(self.spacerItem1)

        self.btn_new_item = QPushButton(TabQuestions)
        self.btn_new_item.setObjectName(u"btn_new_item")

        self.items_header.addWidget(self.btn_new_item)


        self.main_layout.addLayout(self.items_header)

        self.table_observable_items = QTableWidget(TabQuestions)
        if (self.table_observable_items.columnCount() < 3):
            self.table_observable_items.setColumnCount(3)
        __qtablewidgetitem = QTableWidgetItem()
        self.table_observable_items.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.table_observable_items.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.table_observable_items.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        self.table_observable_items.setObjectName(u"table_observable_items")
        self.table_observable_items.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_observable_items.setAlternatingRowColors(True)

        self.main_layout.addWidget(self.table_observable_items)


        self.retranslateUi(TabQuestions)

        QMetaObject.connectSlotsByName(TabQuestions)
    # setupUi

    def retranslateUi(self, TabQuestions):
        self.lbl_questions_title.setText(QCoreApplication.translate("TabQuestions", u"Questions", None))
        self.btn_generer.setText(QCoreApplication.translate("TabQuestions", u"G\u00e9n\u00e9rer", None))
#if QT_CONFIG(tooltip)
        self.btn_generer.setToolTip(QCoreApplication.translate("TabQuestions", u"G\u00e9n\u00e9rer questions et manifestations via IA", None))
#endif // QT_CONFIG(tooltip)
        self.btn_new_question.setText(QCoreApplication.translate("TabQuestions", u"+ Nouvelle question", None))
        self.lbl_items_title.setText(QCoreApplication.translate("TabQuestions", u"Manifestations observables", None))
        self.btn_new_item.setText(QCoreApplication.translate("TabQuestions", u"+ Nouvel item", None))
        ___qtablewidgetitem = self.table_observable_items.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("TabQuestions", u"Cat\u00e9gorie", None));
        ___qtablewidgetitem1 = self.table_observable_items.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("TabQuestions", u"Texte", None));
        ___qtablewidgetitem2 = self.table_observable_items.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("TabQuestions", u"Actions", None));
        pass
    # retranslateUi

