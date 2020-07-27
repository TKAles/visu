
import os
import sys
import numpy as np
import functools
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas)
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QMessageBox

ui_path = '/home/tka/source/visu/'
ui_file = 'visu2.ui'
widget_file = 'visu2_worktab.ui'

class Ui(QtWidgets.QMainWindow):

    def __init__(self):
        super(Ui, self).__init__()
        os.chdir(ui_path)
        uic.loadUi(ui_file, self)
        self.tab_objects = [uic.loadUi(widget_file)]
        self.show()

        # Create the lists that contain each figure in
        # each tab + other supporting stuff
        self.tab_figures = [Figure()]
        self.canvas = []
        self.workspace_dir = [' ']
        self.data_loaded = [False]
        self.dc_processed = [False]
        self.fft_processed = [False]
        self.view_dc = [False]
        self.view_fft = [False]
        self.view_dcm = [False]
        self.view_vel = [False]

        self.mintab_voltage = [0.0]
        self.maxtab_voltage = [0.0]
        self.threshtab_voltage = [0.0]
        # Insert the initial tab into the view.
        self.tab_mainframe.insertTab(0, self.tab_objects[0], "Angle 1")
        self.tab_mainframe.setTabText(1, "Add Angle")
        self.tab_mainframe.setCurrentIndex(0)
        self.tab_axes = [self.tab_figures[0].add_subplot('111')]
        self.tab_axes[0].plot(np.random.rand(5), '.')
        self.tab_axes[0].text(0.5, 0.5, "No Data Loaded",
                              fontsize='x-large',
                              horizontalalignment='center',
                              transform=self.tab_axes[0].transAxes)
        self.add_mpl(0, self.tab_figures[0])

        # Inital UI setup
        self.init_angle_tab(0)

        # Setup trigger for adding another angle tab
        self.tab_mainframe.tabBarClicked.connect(self.add_angle_tab)

        # Create initial MapCollection object
        self.maps = MapCollection.TekCollection()

    def add_mpl(self, tab_index, fig):
        '''
        Ui.addmpl(tab_index, fig): Takes a tab index, and figure, then plots
        the figure into the tab.
        '''
        self.canvas.append(' ')
        _canvas = FigureCanvas(fig)
        _canvas.minimumWidth = 900
        _canvas.minimumHeight = 900
        self.tab_objects[tab_index].gfx_pane_layout.addWidget(_canvas)
        _canvas.draw()
        self.canvas[tab_index] = _canvas

        return

    def remove_mpl(self, tab_index):
        '''
        Ui.remove_mpl(tab_index): Removes whatever tab is passed to it.
        '''
        self.tab_objects[tab_index].gfx_pane_layout.removeWidget(
            self.canvas[tab_index])
        self.canvas[tab_index].close()
        return

    def add_angle_tab(self, index):
        '''
        Ui.add_angle_tab(): Catches the click on the Add Angle tab and creates
        a new copy of the tab. Then appends it to the end of the stack.
        '''
        # Switch to directory with ui files in it.
        os.chdir(ui_path)
        # Get length of object array, autogenerate text
        _tabcount = self.tab_objects.__len__()
        _tabstring = "Angle {0}".format(_tabcount + 1)
        if(index == _tabcount):
            self.tab_objects.append(uic.loadUi(widget_file))
            self.tab_mainframe.insertTab(_tabcount,
                                         self.tab_objects[_tabcount],
                                         _tabstring)
            self.tab_mainframe.setCurrentIndex(_tabcount)
            self.tab_figures.append(Figure())
            self.tab_axes.append(self.tab_figures[-1].add_subplot('111'))
            self.tab_axes[-1].plot(np.random.rand(5), '.')
            self.tab_axes[-1].text(0.5, 0.5, "No Data Loaded",
                                   fontsize='x-large',
                                   horizontalalignment='center',
                                   transform=self.tab_axes[-1].transAxes)
            self.add_mpl(_tabcount, self.tab_figures[-1])
            self.workspace_dir.append(' ')
            self.data_loaded.append(False)
            self.dc_processed.append(False)
            self.fft_processed.append(False)
            self.view_dc.append(False)
            self.view_fft.append(False)
            self.view_dcm.append(False)
            self.view_vel.append(False)
            # Tab UI connections
            self.init_angle_tab(_tabcount)

        return

    def init_angle_tab(self, index):
        '''
        Ui.init_angle_tab(index): Connects all common signals and slots
                                  for a given tab_index.
        '''
        # disable buttons except for load data or load previous data
        print("initializing index {0}".format(index))
        self.tab_objects[index].btn_prep_workspace.setEnabled(0)
        self.tab_objects[index].btn_process_dc.setEnabled(0)
        self.tab_objects[index].le_dc_min.setEnabled(0)
        self.tab_objects[index].le_dc_max.setEnabled(0)
        self.tab_objects[index].btn_compute_fft.setEnabled(0)
        self.tab_objects[index].le_fft_min.setEnabled(0)
        self.tab_objects[index].le_fft_max.setEnabled(0)
        self.tab_objects[index].btn_compute_vel.setEnabled(0)
        self.tab_objects[index].le_vel_min.setEnabled(0)
        self.tab_objects[index].le_vel_max.setEnabled(0)
        self.tab_objects[index].txt_saw_size.setEnabled(0)
        self.tab_objects[index].txt_sample_name.setEnabled(0)
        self.tab_objects[index].txt_md_acq_angle.setEnabled(0)
        self.tab_objects[index].txt_md_startx.setEnabled(0)
        self.tab_objects[index].txt_md_deltax.setEnabled(0)
        self.tab_objects[index].txt_md_starty.setEnabled(0)
        self.tab_objects[index].txt_md_deltay.setEnabled(0)

        # Set all flags to false
        self.data_loaded[index] = False
        self.dc_processed[index] = False
        self.fft_processed[index] = False

        # set default properties
        self.tab_objects[index].btn_load.clicked.connect(
                                functools.partial(self.select_workspace_folder,
                                                  index))
        self.tab_objects[index].btn_process_dc.clicked.connect(
                                functools.partial(self.ui_process_dc_voltage,
                                                  index))
        self.tab_objects[index].btn_compute_fft.clicked.connect(
                                functools.partial(self.ui_process_fft,
                                                  index))
        return

    def select_workspace_folder(self, tab_index):
        '''
        Ui.select_workspace_folder(tab_index): Pops a directory dialog and
        sets the directory in the workspace_dir[] list by tab_index.
        '''
        _selectedpath = str(QtWidgets.QFileDialog.getExistingDirectory(self,
                            "Select Workspace Directory..."))

        # Set the returned path to the proper position in the list.
        self.workspace_dir[tab_index] = _selectedpath

        # Update label with current path, and change
        # the button to 'Change Directory'
        self.tab_objects[tab_index].lbl_dataset_dir.setText(
            self.workspace_dir[tab_index] + '/')
        self.tab_objects[tab_index].btn_load.setText(
            "Change Dataset Directory")
        self.maps.initalize_data(self.workspace_dir[tab_index], tab_index)
        self.data_loaded[tab_index] = True
        self.tab_objects[tab_index].btn_process_dc.setEnabled(1)
        self.tab_objects[tab_index].btn_load.setEnabled(0)
        return

    def ui_process_dc_voltage(self, tab_index):
        '''
            Ui.ui_process_dc_voltage(self, tab_index): Causes the UI to
            update the DC voltage map and object for this particular tab.
        '''
        # if the data hasn't been processed before, process it using
        # the mp_assemble_dcmap function.
        if(self.dc_processed[tab_index] is not True):
            self.maps.scans[tab_index].mp_assemble_dcmap()
            self.maps.scans[tab_index].compute_dcmask()
            self.dc_processed[tab_index] = True
            # Remove current figure from the tab and replace with the
            # DC voltage view
            self.remove_mpl(tab_index)
            _dcfigure = Figure()
            _dcax = _dcfigure.add_subplot('111')
            _dcax.imshow(self.maps.scans[tab_index].dc_map,
                         aspect=self.maps.scans[tab_index].dc_map.shape[1] /
                         self.maps.scans[tab_index].dc_map.shape[0])
            self.add_mpl(tab_index, _dcfigure)
            self.view_dc[tab_index] = True
            # Update the UI to reflect the new state of the
            # controls.
            self.tab_objects[tab_index].btn_process_dc.setText(
                "Switch to DC Mask View")
            self.tab_objects[tab_index].btn_compute_fft.setEnabled(1)
            self.tab_objects[tab_index].txt_sample_name.setEnabled(1)
            self.tab_objects[tab_index].txt_md_acq_angle.setEnabled(1)
            self.tab_objects[tab_index].txt_md_startx.setEnabled(1)
            self.tab_objects[tab_index].txt_md_deltax.setEnabled(1)
            self.tab_objects[tab_index].txt_md_starty.setEnabled(1)
            self.tab_objects[tab_index].txt_md_deltay.setEnabled(1)

        else:
            # If the data was already processed, or logic is toggling
            # back from the dc mask view just redraw the dc map.
            if self.view_dc[tab_index] is not True:
                self.remove_mpl(tab_index)
                _dcfigure = Figure()
                _dcaxes = _dcfigure.add_subplot('111')
                _dcaxes.imshow(self.maps.scans[tab_index].dc_map,
                               aspect=self.maps.scans[tab_index].dc_map.shape[1] /
                               self.maps.scans[tab_index].dc_map.shape[0])
                self.view_dc[tab_index] = True
                self.view_dcm[tab_index] = False
                self.view_fft[tab_index] = False
                self.tab_objects[tab_index].btn_process_dc.setText(
                    "Switch to DC Mask View")
                self.add_mpl(tab_index, _dcfigure)
            else:
                # Toggle mask view.
                self.remove_mpl(tab_index)
                _dcmfigure = Figure()
                _dcmaxes = _dcmfigure.add_subplot('111')
                _dcmaxes.imshow(self.maps.scans[tab_index].dc_mask,
                                aspect=self.maps.scans[tab_index].dc_map.shape[1] /
                                self.maps.scans[tab_index].dc_map.shape[0])
                self.view_dc[tab_index] = False
                self.view_dcm[tab_index] = True
                self.view_fft[tab_index] = False
                self.tab_objects[tab_index].btn_process_dc.setText(
                    "Switch to DC Voltage View")
                self.add_mpl(tab_index, _dcmfigure)

        return

    def ui_process_fft(self, tab_index):
        self.tab_objects[tab_index].btn_process_dc.setText(
                   "Switch to DC Voltage View")
        if ((self.dc_processed[tab_index] is True) &
           (self.fft_processed[tab_index] is not True)):
            # Process FFTs
            self.maps.scans[tab_index].mp_assemble_fftmap()
            self.tab_objects[tab_index].le_fft_min.setEnabled(1)
            self.tab_objects[tab_index].le_fft_max.setEnabled(1)
            self.fft_processed[tab_index] = True
            self.tab_objects[tab_index].btn_compute_vel.setEnabled(1)
            self.tab_objects[tab_index].txt_saw_size.setEnabled(1)

        if ((self.fft_processed[tab_index] is True) &
           (self.view_fft[tab_index] is False)):
            # Show FFT on Canvas
            _fftfig = Figure()
            _fftax = _fftfig.add_subplot('111')
            _fftax.imshow(self.maps.scans[tab_index].rf_map,
                          aspect=self.maps.scans[tab_index].rf_map.shape[1] /
                          self.maps.scans[tab_index].rf_map.shape[0])
            self.view_fft[tab_index] = True
            self.remove_mpl(tab_index)
            self.add_mpl(tab_index, _fftfig)
        return

    def ui_process_velocity(self, tab_index):

        return


app = QtWidgets.QApplication(sys.argv)
window = Ui()
app.exec_()
