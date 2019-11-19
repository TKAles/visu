from PyQt5.uic import loadUiType, loadUi
from PyQt5.Qt import QMainWindow, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog, QMessageBox, QTabWidget

import glob
import os
import sys
from functools import partial
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import numpy as np
import pandas as pd
import tekmapper
import tekwfm
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
        self.connectAngleTab(0)
        
        # some flags to enable/disable buttons
        self.valid_velocity = False
        self.valid_angle = False

        # Create a list for the SRAS dataset objects
        self.datasets = [SRASDataset()]

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
            self.connectAngleTab(tab_count)
            self.datasets.append(SRASDataset)

    def connectAngleTab(self, tab_index):
        """
            connectAngleTab: Wires up all the signals and slots for the various 
                             UI elements in each tab. Only really designed to be
                             called from addAngleTab
        """   
        self.current_tabs[tab_index].plot_velocity_map_button.setEnabled(False)
        self.current_tabs[tab_index].select_scandir_button.clicked.connect(partial(self.selectDirectory, tab_index))
        self.current_tabs[tab_index].process_scope_data_button.clicked.connect(partial(self.noFunctionalityDialog, tab_index))
        self.current_tabs[tab_index].load_saved_data_button.clicked.connect(partial(self.noFunctionalityDialog, tab_index))
        self.current_tabs[tab_index].plot_dc_intensity_button.clicked.connect(partial(self.viewDCMap, tab_index))
        self.current_tabs[tab_index].plot_sample_mask_button.clicked.connect(partial(self.noFunctionalityDialog, tab_index))
        self.current_tabs[tab_index].plot_fft_map_button.clicked.connect(partial(self.noFunctionalityDialog, tab_index))
        self.current_tabs[tab_index].patch_spacing_textedit.editingFinished.connect(partial(self.updateSAWSize, tab_index))
        self.current_tabs[tab_index].plot_velocity_map_button.clicked.connect(partial(self.noFunctionalityDialog, tab_index))
        self.current_tabs[tab_index].saw_grating_angle_lineedit.editingFinished.connect(partial(self.noFunctionalityDialog, tab_index))

    def addmpl(self, tab_index, fig):
        """
        addmpl takes a tab index and figure and then plots that information.
        """
        self.canvas = FigureCanvas(fig)
        self.current_tabs[tab_index].mpl_vlayout.addWidget(self.canvas)
        self.canvas.draw()
        self.navbar = NavigationToolbar(self.canvas, self.current_tabs[tab_index].nav_widget, coordinates=True)
        self.current_tabs[tab_index].mpl_vlayout.addWidget(self.navbar)
    
    def rmmpl(self, tab_index,):
        """
        rmmpl does what addmpl does, but backwards.
        """
        self.current_tabs[tab_index].mpl_vlayout.removeWidget(self.canvas)
        self.canvas.close()
        self.current_tabs[tab_index].mpl_vlayout.removeWidget(self.navbar)
        self.navbar.close()

    def noFunctionalityDialog(self, tab_number):
        """
        noFunctionalityDialog(int): Displays an oopsie dialog along with the offending tab it came from.
                                    That way you can re-educate it...
        """
        oops_dialog = QMessageBox()
        print("This functionality has not been implemented yet.")
        oops_dialog.setText("This functionality has not been implemented yet.\n" +
        "Signal Received from tab #{0}".format(tab_number))
        oops_dialog.exec()
        return

    def selectDirectory(self, tab_number):
        """
        selectDirectory(int):   Pops a QFileDialog in directory mode to load up the .WFM files. 
                                Expects the tab number to properly assign the scan_directory
                                property of the SRASDataset object.
        """
        self.datasets[tab_number].data_directory = str(QFileDialog.getExistingDirectory(
            self, "Select scan data directory:"))
        self.datasets[tab_number].load_files()

    def updateSAWSize(self, tab_number):
        """
        updateSAWSize(int):     Triggers on a QLineEdit editingFinished() signal. Validates the input
                                and enables the 'Calculate Velocity Map' option if it gets a value that
                                isn't absolutely insane. (15-500 microns is ~~*valid*~~)
        """
        try:
            parsed_value = int(self.current_tabs[tab_number].patch_spacing_textedit.text())

        except ValueError:
            parsed_value = 0

        if(15 < parsed_value < 500):
            self.current_tabs[tab_number].plot_velocity_map_button.setEnabled(True)
        else:
            self.current_tabs[tab_number].plot_velocity_map_button.setEnabled(False)

    def viewDCMap(self, tab_number):
        if(self.datasets[tab_number].dc_ready == False):
            self.datasets[tab_number].process_dc()
            self.rmmpl(0)
            self.system_figures[tab_number] = plt.figure(figsize=[10,10])
            self.system_figure_axes[tab_number] = self.system_figures[tab_number].add_subplot("111")
            self.system_figure_axes[tab_number].imshow(
                self.datasets[tab_number].dc_map, 
                aspect=self.datasets[tab_number].number_of_records/self.datasets[tab_number].dc_files.__len__()
                )
            self.addmpl(tab_number, self.system_figures[tab_number])


class SRASDataset():
    

    def __init__(self):
        self._datadir = ""
        
        self._isdc_ready = False
        self._isfft_ready = False
        self._isvelocity_ready = False
        
        self.coordinates = {"x_start": 0.0, "y_start": 0.0,
                            "x_step": 0.0, "y_step":0.0}
        
        self.dc_files = []
        self.rf_files = []

        self.record_length = 0
        self.number_of_records = 0

        self.dc_map = pd.DataFrame()
        self.dc_mask = pd.DataFrame()
        self.fft_map = pd.DataFrame()
        self.fft_spd_map = pd.DataFrame()


    @property        
    def data_directory(self):
        return self._datadir

    @data_directory.setter
    def data_directory(self, value):
        self._datadir = value
        
    
    @property
    def dc_ready(self):
        return self._isdc_ready
    
    @dc_ready.setter
    def dc_ready(self, value):
        self._isdc_ready = value
        

    @property
    def fft_ready(self):
        return self._isfft_ready

    @fft_ready.setter
    def fft_ready(self, value):
        self._isfft_ready = value


    @property
    def velocity_ready(self):
        return self._isvelocity_ready

    @velocity_ready.setter
    def velocity_ready(self, value):
        self._isvelocity_ready = value
        

    def load_files(self):
        """
            load_files: Function to search the assigned scan_directory and load the 
                        files from within it. Does not perform any processing of the
                        files.
        """
        if(self.data_directory == ""):
        
            raise Exception("No data directory was initally selected for this object.")
        else:
            os.chdir(self.data_directory)

            for current_file in glob.glob("*.wfm"):
                if(current_file.startswith("RF")):
                    self.rf_files.append(self.data_directory + "/" + current_file)
                elif(current_file.startswith("DC")):
                    self.dc_files.append(self.data_directory + "/" + current_file)
            
            notification_box = QMessageBox()
            notification_box.setText("Found {0} RF files, and {1} DC files.".format(
                self.rf_files.__len__(), self.dc_files.__len__()))
            notification_box.setStandardButtons(QMessageBox.Ok)
            notification_box.exec()
            
        
    def process_dc(self, mask_threshold=0.08):
        """
            process_dc: Function to process the dc_files ande load them into the corresponding
                        image matrix. Also computes the mask according to the mask_threshold.
                        mask_threshold is set to 80mV by default, but can be overridden.
        """
        temp_dc_map = []
        for current_dc in self.dc_files:
            _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(current_dc)    
            if((self.record_length and self.number_of_records) == 0):
                self.record_length, self.number_of_records = _vt.shape
            dc_dataframe = pd.DataFrame(_vt)
            temp_dc_map.append(dc_dataframe.mean())
        
        self.dc_map = pd.DataFrame(temp_dc_map)
        self.dc_mask = self.dc_map > mask_threshold

app = QApplication(sys.argv)
window = Ui()
app.exec_()
