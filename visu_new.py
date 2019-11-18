from PyQt5.uic import loadUiType, loadUi
from PyQt5.Qt import QMainWindow, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox, QTabWidget

import glob
import os
import sys

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import numpy as np
import pandas as pd
import tekmapper

class Ui(QMainWindow):

    def __init__(self):
        self.tab_qwidget_filepath = 'C://Users//tka//source//repos//tempvisu//visu//visu_tab_widget.ui'
        super(Ui, self).__init__()
        loadUi('C://Users//tka//source//repos//tempvisu//visu//visu_gui_new.ui', self)
        self.show()

        # Create a list of the currently loaded tabs and load up the 'first' angle tab.
        self.current_tabs = [loadUi(self.tab_qwidget_filepath)]
        self.tabWidget.insertTab(0, self.current_tabs[0], "Angle 1")
        self.tabWidget.removeTab(1)
        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.currentChanged.connect(self.addAngleTab)

    def addAngleTab(self, tab_index):
        tab_count = self.current_tabs.__len__()
        if(tab_index == tab_count):
            tab_string = "Angle {0}".format(tab_count + 1)
            self.current_tabs.append(loadUi(self.tab_qwidget_filepath))
            self.tabWidget.insertTab(tab_count,
                                    self.current_tabs[tab_count], tab_string)
            self.tabWidget.setCurrentIndex(tab_count)
        


app = QApplication(sys.argv)
window = Ui()
app.exec_()
