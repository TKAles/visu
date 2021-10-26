'''
    Visu 2.0-a
    Thomas K Ales

    VISU with support for 'new data' format.
'''
import PyQt5
from matplotlib import gridspec
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
from matplotlib.figure import Figure
from PyQt5 import QtWidgets, QtGui, uic

from functools import partial
import os
import sys

ui_file = './visu.ui'

class Ui(QtWidgets.QMainWindow):

    def __init__(self) -> None:
        super(Ui, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()
        self.default_element_state()
        self.tab_objects = []
        self.canvas_objects = []
        self.plot_navigation_objects = []
        self.create_figure()
        

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
        


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Ui()
    app.exec_()