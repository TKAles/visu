'''
    Visu 2.0-a
    Thomas K Ales

    VISU with support for 'new data' format.
'''
from xml.etree.ElementTree import parse
import PyQt5
from matplotlib import gridspec
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from PyQt5 import QtWidgets, QtGui, uic
from PyQt5.QtCore import pyqtSlot

from functools import partial
import os
import sys

import VisuScan as vs

ui_file = './visu.ui'

class Ui(QtWidgets.QMainWindow):

    scanobj = vs.VisuScanCollection()

    def __init__(self) -> None:
        super(Ui, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()
        self.default_element_state()
        self.tab_objects = []
        self.canvas_objects = []
        self.plot_navigation_objects = []
        self.create_figure()
        self.load_wfm_dataset_button.clicked.connect(self.wfm_load)
        self.process_dc_button.clicked.connect(self.ui_process_dc)
        self.gfx_ui = 'C:\\Users\\tka\\source\\repos\\visu\\visu_gfxpane.ui'
    def default_element_state(self):
        '''
        default_element_state: Disables all UI elements excep the Load WFM Dataset
                               and Load Saved Dataset buttons.
        '''
        # DC UI Elements
        self.process_dc_button.setEnabled(False)
        self.min_dc_slider.setEnabled(False)
        self.max_dc_slider.setEnabled(False)
        # FFT
        self.process_fft_button.setEnabled(False)
        self.min_fft_slider.setEnabled(False)
        self.max_fft_slider.setEnabled(False)
        # Velocity
        self.fft_to_velocity_button.setEnabled(False)
        self.spacing_text.setEnabled(False)
        # Save/Export/Align
        self.save_all_images_button.setEnabled(False)
        self.export_dc_fft_vel_button.setEnabled(False)
        self.begin_alignment_button.setEnabled(False)
        self.export_orientation_button.setEnabled(False)
        # Metadata
        self.sample_name_text.setEnabled(False)
        self.x_delta_text.setEnabled(False)
        self.y_delta_text.setEnabled(False)
        self.scan_speed_text.setEnabled(False)
        self.laser_frequency_text.setEnabled(False)
        self.angle_spacing_text.setEnabled(False)
        

    def create_figure(self):
        self.tab_objects.append(uic.loadUi('./visu_gfxpane.ui'))
        self.canvas_objects.append(FigureCanvas())
        self.plot_navigation_objects.append(NavigationToolbar(self.canvas_objects[-1], self))
        self.tab_objects[-1].gfx_pane.addWidget(self.canvas_objects[-1])
        self.tab_objects[-1].gfx_pane.addWidget(self.plot_navigation_objects[-1])
        self.scan_collection_tabs.addTab(self.tab_objects[-1], 'Test Tab')

    
    def wfm_load(self):
        self.scanobj.path_to_files = QtWidgets.QFileDialog.getExistingDirectory(
            None, 'Select Directory', 'C:\\'
        )
        self.scanobj.parse_directory()
        print('Parse Completed.')
        parseBox = QtWidgets.QMessageBox()
        parseBox.setIcon(QtWidgets.QMessageBox.Information)
        parseBox.setWindowTitle('Directory Load Results')
        parseBox.setText(
            'Found {0} scans in directory: {1}\nContinue Processing?'.format(
                self.scanobj.rf_files.__len__(),
                self.scanobj.path_to_files
            )
        )
        parseBox.setStandardButtons(QtWidgets.QMessageBox.Yes | 
                                    QtWidgets.QMessageBox.No)
        response = parseBox.exec()
        if response == QtWidgets.QMessageBox.Yes:
            self.scan_collection_tabs.removeTab(2)
            self.scan_collection_tabs.removeTab(1)
            self.tab_objects = []
            for x in range(0, self.scanobj.number_of_scans):
                if x == 0:
                    self.tab_objects.append(uic.loadUi(self.gfx_ui))
                    self.canvas_objects.append(FigureCanvas())
                    self.plot_navigation_objects.append(NavigationToolbar(
                        self.canvas_objects[-1], None
                    ))
                    self.tab_objects[-1].gfx_pane.addWidget(self.canvas_objects[-1])
                    self.tab_objects[-1].gfx_pane.addWidget(self.plot_navigation_objects[-1])
                    self.scan_collection_tabs.removeTab(0)
                    self.scan_collection_tabs.insertTab(0, self.tab_objects[0], 'Reference Scan')
                    
                else:
                    self.tab_objects.append(uic.loadUi(self.gfx_ui))
                    self.scan_collection_tabs.addTab(self.tab_objects[-1],
                                                     'Scan {0}'.format(x))
                    self.canvas_objects.append(FigureCanvas())
                    self.plot_navigation_objects.append(NavigationToolbar(
                        self.canvas_objects[-1], None
                    ))
                    self.tab_objects[-1].gfx_pane.addWidget(self.canvas_objects[-1])
                    self.tab_objects[-1].gfx_pane.addWidget(self.plot_navigation_objects[-1])

                self.process_dc_button.setEnabled(True)                        
        return

    def ui_process_dc(self):
        for x in range(0, self.scanobj.rf_files.__len__()):
            self.scanobj.scan_collection[x].mp_assemble_dcmap()
            self.tab_objects[x] = uic.loadUi(self.gfx_ui)
            fig = Figure()
            axes = fig.subplots()
            axes.imshow(self.scanobj.scan_collection[x].dc_map)
            self.canvas_objects[x] = FigureCanvas(fig)
            self.plot_navigation_objects[x] = NavigationToolbar(self.canvas_objects[x], None)
            self.tab_objects[x].gfx_pane.addWidget(self.canvas_objects[x])
            self.tab_objects[x].gfx_pane.addWidget(self.plot_navigation_objects[x])
            self.scan_collection_tabs.removeTab(x)
            if x == 0:
                tabstr = 'Reference Angle'
            else:
                tabstr = 'Scan {0}'.format(x)
            self.scan_collection_tabs.insertTab(x, self.tab_objects[x], tabstr)
        self.process_dc_button.setText('DC Processed')
        return
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Ui()
    app.exec_()