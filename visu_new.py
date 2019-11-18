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
        self.tab_qwidget_filepath = 'visu_tab_widget.ui'
        super(Ui, self).__init__()
        loadUi('visu_gui_new.ui', self)
        self.show()

        # Create a list of the currently loaded tabs and load up the 'first' angle tab.
        self.current_tabs = [loadUi(self.tab_qwidget_filepath)]
        
        self.tabWidget.insertTab(0, self.current_tabs[0], "Angle 1")
        self.tabWidget.removeTab(1)
        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.currentChanged.connect(self.addAngleTab)
        self.system_figures = [Figure()]
        self.system_figure_axes = [self.system_figures[0].add_subplot("111")]
        self.system_figure_axes[0].plot(np.random.rand(5))
        self.addmpl(0, self.system_figures[0])
        
        # figure_1 = Figure()
        # fig1_axes1 = figure_1.add_subplot("111")
        # fig1_axes1.plot(np.random.rand(5))
        # self.addmpl(0, figure_1)

    def addAngleTab(self, tab_index):
        """
            addAngleTab: Signal for the main UI TabWidget currentChanged event.
                         Adds a new angle tab at the end of the file when the 'Add Tab'
                         tab is clicked, then switches to the new tab.
        """
        tab_count = self.current_tabs.__len__()
        if(tab_index == tab_count):
            tab_string = "Angle {0}".format(tab_count + 1)
            self.current_tabs.append(loadUi(self.tab_qwidget_filepath))
            self.tabWidget.insertTab(tab_count,
                                    self.current_tabs[tab_count], tab_string)
            self.tabWidget.setCurrentIndex(tab_count)
            self.system_figures.append(Figure())
            self.system_figure_axes.append(self.system_figures[-1].add_subplot("111"))
            self.system_figure_axes[-1].plot(np.random.rand(5))
            self.addmpl((self.system_figures.__len__()-1), self.system_figures[-1])
        
    def addmpl(self, tab_index, fig):
        self.canvas = FigureCanvas(fig)
        self.current_tabs[tab_index].mpl_vlayout.addWidget(self.canvas)
        self.canvas.draw()
        self.navbar = NavigationToolbar(self.canvas, self.current_tabs[tab_index].nav_widget, coordinates=True)
        self.current_tabs[tab_index].mpl_vlayout.addWidget(self.navbar)
    
    def rmmpl(self, tab_index,):
        self.current_tabs[tab_index].mpl_vlayout.removeWidget(self.canvas)
        self.canvas.close()
        self.current_tabs[tab_index].mpl_vlayout.removeWidget(self.navbar)
        self.navbar.close()

app = QApplication(sys.argv)
window = Ui()
app.exec_()
