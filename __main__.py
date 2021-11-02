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
import multiprocessing
import threading
import os
import sys
import time

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
        self.dc_figures = []
        self.dc_axes = []
        self.rf_figures = []
        self.rf_axes = []
        self.process_progress = 0
        self.load_wfm_dataset_button.clicked.connect(self.wfm_load)
        self.process_dc_button.clicked.connect(self.ui_process_dc)
        self.gfx_ui = os.getcwd() + '\\visu_gfxpane.ui'
        self.gfx_progress = os.getcwd() + '\\visu_progress.ui'

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
        '''
        wfm_load:   Process to setup the VisuScan object with the scans grouped by
                    angle as individual map objects.
        '''
        self.scanobj.path_to_files = QtWidgets.QFileDialog.getExistingDirectory(
            None, 'Select Directory', 'C:\\'
        )
        self.scanobj.parse_directory()
        # Put up message box showing # of scans and ask if would like to continue
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
        # If Yes, continue loading object.
        if response == QtWidgets.QMessageBox.Yes:
            self.scan_collection_tabs.removeTab(2)
            self.scan_collection_tabs.removeTab(1)
            self.tab_objects = []
            for x in range(0, self.scanobj.number_of_scans):
                # For the zero case, label the tab as the Reference Scan
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
                    
                # For all other cases, replace per usual but name tab 'Scan n'
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
                
                # Enable the process DC button once scans are configured
                self.process_dc_button.setEnabled(True)
            else:
                # TODO: Implement No Path
                pass
        return

    def ui_process_dc(self):
        self.current_map = 0
        self.statusbar.showMessage('Processing DC 1/{0}'.format(self.scanobj.dc_files.__len__()))
        self.process_dc_button.setText('Processing WFM...')
        self.process_dc_button.setEnabled(False)
        dc_thread = threading.Thread(target=self.scanobj.assemble_dc_maps)
        dc_thread.start()
        
        while self.scanobj.dc_map_progress != -1:
            time.sleep(0.25)
            self.process_dc_button.setText('Assembling DC Map {0}...'.format(
                self.scanobj.dc_map_progress
            ))
            self.statusbar.showMessage('Processing DC {0}/{1}'.format(
                self.scanobj.dc_map_progress, self.scanobj.dc_files.__len__() - 1
            ))

        self.ui_draw_dc()
        self.angle_spacing_text.setEnabled(True)
        self.angle_spacing_text.setText('{0}'.format(self.scanobj.angle_increment))
        self.statusbar.showMessage('DC View Mode: Map {0}'.format(
            self.scan_collection_tabs.currentIndex()
        ), 2000)
        dc_min = self.scanobj.scan_collection[0].dc_map.min()
        final_min = dc_min.min()
        self.min_dc_label.setText('{0:.03f}v'.format(final_min))
        dc_max = self.scanobj.scan_collection[0].dc_map.max()
        final_max = dc_max.max()
        self.max_dc_label.setText('{0:.03f}v'.format(final_max))
        self.min_dc_slider.setEnabled(True)
        self.min_dc_slider.setMinimum(0)
        self.min_dc_slider.setMaximum(int(final_max*100))
        self.max_dc_slider.setEnabled(True)
        self.process_dc_button.setText('DC View Mode: Map {0}'.format(
            self.scan_collection_tabs.currentIndex()))
        return

    def ui_draw_dc(self):
        for x in range(0, self.scanobj.rf_files.__len__()):
            if x == 0:
                tabstr = 'Reference Angle'
            else:
                tabstr = 'Scan {0}'.format(x)
            
            self.scan_collection_tabs.removeTab(x)
            self.tab_objects[x] = uic.loadUi(self.gfx_ui)
            fig = Figure()
            axes = fig.subplots()
            axes.imshow(self.scanobj.scan_collection[x].dc_map)
            self.canvas_objects[x] = FigureCanvas(fig)
            self.plot_navigation_objects[x] = NavigationToolbar(self.canvas_objects[x], None)
            self.tab_objects[x].gfx_pane.addWidget(self.canvas_objects[x])
            self.tab_objects[x].gfx_pane.addWidget(self.plot_navigation_objects[x])
            self.scan_collection_tabs.insertTab(x, self.tab_objects[x], tabstr)
            self.scan_collection_tabs.setCurrentIndex(0)
        return

    
        
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Ui()
    app.exec_()