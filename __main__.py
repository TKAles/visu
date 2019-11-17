from PyQt5.uic import loadUiType
from PyQt5.Qt import QMainWindow, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox

import glob
import os

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import numpy as np
import pandas as pd
import tekmapper

current_dir = os.getcwd() + "/" + "visu_gui.ui"
Ui_MainWindow, QMainWindow = loadUiType(current_dir)

class Main(QMainWindow, Ui_MainWindow):
    scandir_changed = pyqtSignal(object)

    def __init__(self, ):
        super(Main, self).__init__()
        self.setupUi(self)
        self.ui_selectdir.clicked.connect(self.selectdir)
        self.scandir_changed.connect(self.update_dirlabel)
        self.ui_loadfiles.clicked.connect(self.load_wfms)
        self.ui_view_dc.clicked.connect(self.show_dc_map)
        self.ui_view_fft.clicked.connect(self.show_fft_map)
        self._datadir = ""
        self._disp_mode = None
        self._is_dc_rdy = False
        self._is_fft_rdy = False

    @property
    def data_directory(self):
        return self._datadir
    
    @data_directory.setter
    def data_directory(self, value):
        self._datadir = value
        self.scandir_changed.emit(value)

    @property
    def is_dc_ready(self):
        return self._is_dc_rdy

    @is_dc_ready.setter
    def is_dc_ready(self, _dcmode):
        self._is_dc_rdy = _dcmode
        # TODO: Add appropriate Qt signal here
    
    @property
    def is_fft_ready(self):
        return self._is_fft_rdy
    
    @is_fft_ready.setter
    def is_fft_ready(self, _fftmode):
        self._is_fft_rdy = _fftmode
        # TODO: Add appropirate Qt signal here

    @property
    def display_mode(self):
        return self._disp_mode

    @display_mode.setter
    def display_mode(self, _dispmode):
        self._disp_mode = _dispmode
        
    def addmpl(self, fig):
        self.canvas = FigureCanvas(fig)
        self.mplvl.addWidget(self.canvas)
        self.canvas.draw()
        self.navbar = NavigationToolbar(self.canvas, self.navwidge, coordinates=True)
        self.mplvl.addWidget(self.navbar)
    
    def rmmpl(self,):
        self.mplvl.removeWidget(self.canvas)
        self.canvas.close()
        self.mplvl.removeWidget(self.navbar)
        self.navbar.close()

    def selectdir(self):
        self.data_directory = str(QFileDialog.getExistingDirectory(
            self, "Select scan data directory:"))    

    def update_dirlabel(self):
        self.ui_pathbox.setText(self.data_directory)
        return

    def load_wfms(self):
        self.dc_wfms = []
        self.rf_wfms = []

        os.chdir(self.data_directory)
        for current_file in glob.glob("*.wfm"):
            if(current_file.startswith("RF")):
                self.rf_wfms.append(self.data_directory + "/" + current_file)
            elif(current_file.startswith("DC")):
                self.dc_wfms.append(self.data_directory + "/" + current_file)
        
        notifyBox = QMessageBox()

        if(self.rf_wfms.__len__() == 0):
            # Handle the no files found case
            notifyBox.setText("No Files Found!")
            notifyBox.setInformativeText("visu couldn't find any files in {0}, are you sure that's where you put the .wfm files?".format(self.data_directory))
            notifyBox.setStandardButtons(QMessageBox.Ok)
            notifyBox.exec()
            return
        elif(self.rf_wfms.__len__() != self.dc_wfms.__len__()):
            # Handle the mismatch case
            notifyBox.setText("DC/RF Mismatch!")
            notifyBox.setInformativeText("There are {0} DC files and {1} RF files! No c xcfbueno!".format(
                self.dc_wfms.__len__(), self.rf_wfms.__len__()))
            return
        elif(self.rf_wfms.__len__() == self.dc_wfms.__len__()):
            # Standard behavior / case
            notifyBox = QMessageBox()
            notifyBox.setText("Found {0} files in {1}".format(self.rf_wfms.__len__(), self.data_directory))
            notifyBox.setInformativeText("Would you like to continue to process the {0} files?".format(self.rf_wfms.__len__()))
            notifyBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            notifyBox.setDefaultButton(QMessageBox.Yes)
            _response = notifyBox.exec()

        self.tekmap = tekmapper.TekMapper(self.dc_wfms, self.rf_wfms)
        self.tekmap.load_files()
        # Tell the software the DC waveform is ready
        self.is_dc_ready = True
        # Emit a signal to simulate clicking the DC Scan button
        self.show_dc_map()


    def show_dc_map(self):
        
        self.dc_figure = plt.figure()
        self.dc_figaxes = self.dc_figure.add_subplot("111")
        self.dc_figaxes.imshow(self.tekmap.voltages, 
                        aspect=self.tekmap.frames_in_map/self.dc_wfms.__len__())
        self.rmmpl()
        self.addmpl(self.dc_figure)

        return

    def show_fft_map(self):

        self.rmmpl()
        self.fft_figure = plt.figure()
        self.fft_figaxes = self.fft_figure.add_subplot("111")
        self.fft_figplot = self.fft_figaxes.imshow(self.tekmap.mask_fft,
                        aspect=self.tekmap.frames_in_map/self.rf_wfms.__len__())
        self.fft_figplot.set_clim(80E6, 250E6)
        self.addmpl(self.fft_figure)

        

if __name__ == '__main__':
    import sys
    import PyQt5
    figure_1 = Figure()
    fig1_axes1 = figure_1.add_subplot("111")
    fig1_axes1.plot(np.random.rand(5))
    app = PyQt5.Qt.QApplication(sys.argv)
    main = Main()
    main.addmpl(figure_1)
    main.show()

    sys.exit(app.exec_())