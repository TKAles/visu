# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'c:\Users\tka\source\repos\visu\visu_progress.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(400, 63)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(Dialog)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.progresslabel = QtWidgets.QLabel(Dialog)
        font = QtGui.QFont()
        font.setPointSize(13)
        self.progresslabel.setFont(font)
        self.progresslabel.setAlignment(QtCore.Qt.AlignCenter)
        self.progresslabel.setObjectName("progresslabel")
        self.verticalLayout.addWidget(self.progresslabel)
        self.progressbar = QtWidgets.QProgressBar(Dialog)
        self.progressbar.setProperty("value", 24)
        self.progressbar.setObjectName("progressbar")
        self.verticalLayout.addWidget(self.progressbar)
        self.verticalLayout_2.addLayout(self.verticalLayout)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Dialog"))
        self.progresslabel.setText(_translate("Dialog", "Processing..."))

