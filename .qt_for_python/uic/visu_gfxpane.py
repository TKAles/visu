# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'c:\Users\tka\source\repos\visu\visu_gfxpane.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(400, 300)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(Form)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.gfx_pane = QtWidgets.QVBoxLayout()
        self.gfx_pane.setObjectName("gfx_pane")
        self.verticalLayout_2.addLayout(self.gfx_pane)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Form"))

