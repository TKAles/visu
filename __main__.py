
from functools import partial
from matplotlib.figure import Figure
from matplotlib import gridspec
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
import numpy as np
import os
import pandas as pd
from PyQt5 import QtWidgets, uic

import sys

import MapCollection

ui_path = 'C:\\Users\\Thomas Ales\\source\\repos\\TKAles\\visu\\'
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
        self.navbar = []
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
        self.navbar = NavigationToolbar(self.canvas[tab_index], self,
                                        coordinates=True)
        self.tab_objects[tab_index].gfx_pane_layout.addWidget(self.navbar)
        return

    def remove_mpl(self, tab_index):
        '''
        Ui.remove_mpl(tab_index): Removes whatever tab is passed to it.
        '''
        self.tab_objects[tab_index].gfx_pane_layout.removeWidget(
            self.canvas[tab_index])
        self.canvas[tab_index].close()
        self.tab_objects[tab_index].gfx_pane_layout.removeWidget(self.navbar)
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
                                partial(self.select_workspace_folder,
                                                  index))
        self.tab_objects[index].btn_process_dc.clicked.connect(
                                partial(self.ui_process_dc_voltage,
                                                  index))
        self.tab_objects[index].btn_compute_fft.clicked.connect(
                                partial(self.ui_process_fft,
                                                  index))
        self.tab_objects[index].btn_compute_vel.clicked.connect(
                                partial(self.ui_process_velocity,
                                                  index))
        # Link edit events in the voltage min/maxes to replot voltage
        self.tab_objects[index].le_dc_min.editingFinished.connect(
            partial(self.ui_voltage_limit_changed, index))
        self.tab_objects[index].le_dc_max.editingFinished.connect(
            partial(self.ui_voltage_limit_changed, index))
        # Link edit events in FFT min/maxes to replot FFT
        self.tab_objects[index].le_fft_min.editingFinished.connect(
            partial(self.ui_fft_limit_changed, index))
        self.tab_objects[index].le_fft_max.editingFinished.connect(
            partial(self.ui_fft_limit_changed, index))
        # Link edit events in velocity min/max to replot velocity.
        self.tab_objects[index].le_vel_min.editingFinished.connect(
            partial(self.ui_velocity_limit_changed, index))
        self.tab_objects[index].le_vel_max.editingFinished.connect(
            partial(self.ui_velocity_limit_changed, index))
        # Link metadata field edit events.
        self.tab_objects[index].txt_sample_name.editingFinished.connect(
            partial(self.ui_metadata_changed, index))
        self.tab_objects[index].txt_md_acq_angle.editingFinished.connect(
            partial(self.ui_metadata_changed, index))
        self.tab_objects[index].txt_md_startx.editingFinished.connect(
            partial(self.ui_metadata_changed, index))
        self.tab_objects[index].txt_md_starty.editingFinished.connect(
            partial(self.ui_metadata_changed, index))
        self.tab_objects[index].txt_md_deltax.editingFinished.connect(
            partial(self.ui_metadata_changed, index))
        self.tab_objects[index].txt_md_deltay.editingFinished.connect(
            partial(self.ui_metadata_changed, index))
        
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

    def ui_process_dc_voltage(self, tab_index, _maxv=0, _minv=0):
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
            # Axis labelling logic
            if(self.maps.scans[tab_index].metadata['x_start'] != 0.0):
                _dcmap = _dcax.imshow(self.maps.scans[tab_index].dc_map,
                                      extent=[self.maps.scans[tab_index].metadata['x_start'],
                                               self.maps.scans[tab_index].metadata['x_start'] +
                                               self.maps.scans[tab_index].metadata['x_delta'], 
                                               self.maps.scans[tab_index].metadata['y_start'],
                                               self.maps.scans[tab_index].metadata['y_start'] +
                                               self.maps.scans[tab_index].metadata['y_delta']])
                _dcax.text(-1, 0, 'SAW Angle: ' + str(self.maps.scans[tab_index].metadata['acq_angle']) + r'$\degree$')
            else:
                _dcmap = _dcax.imshow(self.maps.scans[tab_index].dc_map,
                                      aspect=self.maps.scans[tab_index].dc_map.shape[1] /
                                      self.maps.scans[tab_index].dc_map.shape[0])
            _dcbar = _dcfigure.colorbar(_dcmap, ax=_dcax)
            _dcbar.set_label('Detector Bias Voltage [V]')
            _scanres = self.maps.scans[tab_index].metadata['x_delta'] / self.maps.scans[tab_index].dc_map.shape[1] 
            _dcax.set_xlabel('Scan Direction | X-Axis\n{0:.3f} mm/px'.format(_scanres))
            _dcax.set_ylabel('Step Direction | Y-Axis\n0.100 mm/px')
            if(self.maps.scans[tab_index].metadata['sample_desc'] is not ''):
                _dcax.set_title(self.maps.scans[tab_index].metadata['sample_desc'])

            _dcfigure.tight_layout()
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
            self.tab_objects[tab_index].le_dc_min.setEnabled(1)
            self.tab_objects[tab_index].le_dc_max.setEnabled(1)
            _min = np.array(self.maps.scans[tab_index].dc_map.min()).min()
            _max = np.array(self.maps.scans[tab_index].dc_map.max()).max()
            if(_minv == 0) and (_maxv == 0):
                self.tab_objects[tab_index].le_dc_min.setText('{0:.3f}'.format(_min))
                self.tab_objects[tab_index].le_dc_max.setText('{0:.3f}'.format(_max))

        else:
            # If the data was already processed, or logic is toggling
            # back from the dc mask view just redraw the dc map.
            if (self.view_dc[tab_index] is not True):
                self.remove_mpl(tab_index)
                #_dcfigure = Figure()
                _dcfigure = Figure()
                _dcaxes = _dcfigure.add_subplot('111')
                if(self.maps.scans[tab_index].metadata['x_start'] != 0.0):
                    _dcmap = _dcaxes.imshow(self.maps.scans[tab_index].dc_map,
                                      extent=[self.maps.scans[tab_index].metadata['x_start'],
                                               self.maps.scans[tab_index].metadata['x_start'] +
                                               self.maps.scans[tab_index].metadata['x_delta'], 
                                               self.maps.scans[tab_index].metadata['y_start'],
                                               self.maps.scans[tab_index].metadata['y_start'] +
                                               self.maps.scans[tab_index].metadata['y_delta']])
                    _dcaxes.text(self.maps.scans[tab_index].metadata['x_start'],
                                 self.maps.scans[tab_index].metadata['y_start'] + self.maps.scans[tab_index].metadata['y_delta'] + 1.0,
                                 'SAW Angle: ' + str(self.maps.scans[tab_index].metadata['acq_angle']) + r'$\degree$')
                else:
                    _dcmap = _dcaxes.imshow(self.maps.scans[tab_index].dc_map,
                                      aspect=self.maps.scans[tab_index].dc_map.shape[1] /
                                      self.maps.scans[tab_index].dc_map.shape[0])

                if(self.maps.scans[tab_index].metadata['sample_desc'] is not ''):
                    _dcaxes.set_title(self.maps.scans[tab_index].metadata['sample_desc'] +
                    '\nDC Voltage Map')
                _scanres = self.maps.scans[tab_index].metadata['x_delta'] / self.maps.scans[tab_index].dc_map.shape[1] 
                _dcaxes.set_xlabel('Scan Direction | X-Axis\n{0:.3f} mm/sample'.format(_scanres))
                _dcaxes.set_ylabel('Step Direction | Y-Axis\n0.100 mm/sample')
                _dcbar = _dcfigure.colorbar(_dcmap, ax=_dcaxes)
                _dcbar.set_label('Detector Bias Voltage [V]')
                if(_maxv is not 0) and (_minv is not 0):
                    _dcmap.set_clim([_minv, _maxv])
                
                _dcfigure.tight_layout()
                self.view_dc[tab_index] = True
                self.view_dcm[tab_index] = False
                self.view_fft[tab_index] = False
                self.view_vel[tab_index] = False
                self.tab_objects[tab_index].btn_process_dc.setText(
                    "Switch to DC Mask View")
                self.add_mpl(tab_index, _dcfigure)
            else:
                # Toggle mask view.
                self.remove_mpl(tab_index)
                _dcmfigure = Figure()
                _dcmaxes = _dcmfigure.add_subplot('111')
                # Check to see if the metadata has been added, if so plot using
                # extent= instead of aspect=
                if(self.maps.scans[tab_index].metadata['sample_desc'] is not ''):
                    _dcmaxes.imshow(self.maps.scans[tab_index].dc_mask,
                                    extent=[self.maps.scans[tab_index].metadata['x_start'],
                                               self.maps.scans[tab_index].metadata['x_start'] +
                                               self.maps.scans[tab_index].metadata['x_delta'], 
                                               self.maps.scans[tab_index].metadata['y_start'],
                                               self.maps.scans[tab_index].metadata['y_start'] +
                                               self.maps.scans[tab_index].metadata['y_delta']])
                    _dcmaxes.text(self.maps.scans[tab_index].metadata['x_start'],
                            self.maps.scans[tab_index].metadata['y_start'] + self.maps.scans[tab_index].metadata['y_delta'] + 1.0,
                            'SAW Angle: ' + str(self.maps.scans[tab_index].metadata['acq_angle']) + r'$\degree$')
                    _dcmaxes.set_title(self.maps.scans[tab_index].metadata['sample_desc'] + '\nDC Mask View')
                else:
                    _dcmaxes.imshow(self.maps.scans[tab_index].dc_mask,
                                    aspect=self.maps.scans[tab_index].dc_map.shape[1] /
                                    self.maps.scans[tab_index].dc_map.shape[0])
                    _dcmaxes.text(0, -1.0,
                                 'SAW Angle: ' + str(self.maps.scans[tab_index].metadata['acq_angle']) + r'$\degree$')
                _scanres = self.maps.scans[tab_index].metadata['x_delta'] / self.maps.scans[tab_index].dc_map.shape[1] 
                _dcmaxes.set_xlabel('Scan Direction | X-Axis\n{0:.3f} mm/sample'.format(_scanres))
                _dcmaxes.set_ylabel('Step Direction | Y-Axis\n0.100 mm/sample')
                self.view_dc[tab_index] = False
                self.view_dcm[tab_index] = True
                self.view_fft[tab_index] = False
                self.view_vel[tab_index] = False
                self.tab_objects[tab_index].btn_process_dc.setText(
                    "Switch to DC Voltage View")
                self.add_mpl(tab_index, _dcmfigure)

        return

    def ui_process_fft(self, tab_index, _minf=0, _maxf=0):
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
            self.tab_objects[tab_index].btn_compute_fft.setText('Switch to FFT View')

        if ((self.fft_processed[tab_index] is True) &
           (self.view_fft[tab_index] is False)):
            # Show FFT on Canvas
            _fftfig = Figure()
            _fftax = _fftfig.add_subplot('111')
            if(self.maps.scans[tab_index].metadata['sample_desc'] is not ''):
                _fftmap = _fftax.imshow(self.maps.scans[tab_index].rf_map,
                            extent=[self.maps.scans[tab_index].metadata['x_start'],
                                               self.maps.scans[tab_index].metadata['x_start'] +
                                               self.maps.scans[tab_index].metadata['x_delta'], 
                                               self.maps.scans[tab_index].metadata['y_start'],
                                               self.maps.scans[tab_index].metadata['y_start'] +
                                               self.maps.scans[tab_index].metadata['y_delta']])
                _fftax.text(self.maps.scans[tab_index].metadata['x_start'],
                                self.maps.scans[tab_index].metadata['y_start'] + self.maps.scans[tab_index].metadata['y_delta'] + 1.0,
                                'SAW Angle: ' + str(self.maps.scans[tab_index].metadata['acq_angle']) + r'$\degree$')
            else:
                _fftmap = _fftax.imshow(self.maps.scans[tab_index].rf_map,
                            aspect=self.maps.scans[tab_index].rf_map.shape[1] /
                            self.maps.scans[tab_index].rf_map.shape[0])
            _fftbar = _fftfig.colorbar(_fftmap, ax=_fftax)
            
            _fftbar.set_label('FFT Frequency [Hz]')
            _scanres = self.maps.scans[tab_index].metadata['x_delta'] / self.maps.scans[tab_index].dc_map.shape[1] 
            _fftax.set_xlabel('Scan Direction | X-Axis\n{0:.3f} mm/sample'.format(_scanres))
            _fftax.set_ylabel('Step Direction | Y-Axis\n0.100 mm/sample')
            _fftax.set_title(self.maps.scans[tab_index].metadata['sample_desc'] + '\nFFT View')
            if(_minf is not 0) and (_maxf is not 0):
                _fftmap.set_clim([_minf, _maxf])
            
            # Set view state flags
            self.view_fft[tab_index] = True
            self.view_dc[tab_index] = False
            self.view_vel[tab_index] = False
            self.view_dcm[tab_index] = False
            # Add FFT plot to view.
            self.remove_mpl(tab_index)
            self.add_mpl(tab_index, _fftfig)
            _min = np.array(self.maps.scans[tab_index].rf_map.min()).min()
            _max = np.array(self.maps.scans[tab_index].rf_map.max()).max()
            if(_minf == 0) and (_maxf == 0):
                self.tab_objects[tab_index].le_fft_min.setText('{0:.1f}'.format(_min / (10**6)))
                self.tab_objects[tab_index].le_fft_max.setText('{0:.1f}'.format(_max / (10**6)))
        return

    def ui_process_velocity(self, tab_index, _minvel=0, _maxvel=0):
        self.maps.scans[tab_index].mp_assemble_velocitymap()
        _velfig = Figure()
        _velax = _velfig.add_subplot('111')
        if(self.maps.scans[tab_index].metadata['sample_desc'] is not ''):
            _velmap = _velax.imshow(self.maps.scans[tab_index].velocity_map,
                            extent=[self.maps.scans[tab_index].metadata['x_start'],
                                               self.maps.scans[tab_index].metadata['x_start'] +
                                               self.maps.scans[tab_index].metadata['x_delta'], 
                                               self.maps.scans[tab_index].metadata['y_start'],
                                               self.maps.scans[tab_index].metadata['y_start'] +
                                               self.maps.scans[tab_index].metadata['y_delta']])
            _velax.text(self.maps.scans[tab_index].metadata['x_start'],
                        self.maps.scans[tab_index].metadata['y_start'] + self.maps.scans[tab_index].metadata['y_delta'] + 1.0,
                        'SAW Angle: ' + str(self.maps.scans[tab_index].metadata['acq_angle']) + r'$\degree$')                                   
        else:
                _velmap = _velax.imshow(self.maps.scans[tab_index].velocity_map, aspect=self.maps.scans[tab_index].velocity_map.shape[1] /
                                                                self.maps.scans[tab_index].velocity_map.shape[0])
        _velbar = _velfig.colorbar(_velmap, ax=_velax)
        _velbar.set_label(r'SAW packet velocity [m$^{1} \cdot $s$^{-1}$]')
        _velax.text(self.maps.scans[tab_index].metadata['x_start'],
                self.maps.scans[tab_index].metadata['y_start'] + self.maps.scans[tab_index].metadata['y_delta'] + 1.0,
                'SAW Angle: ' + str(self.maps.scans[tab_index].metadata['acq_angle']) + r'$\degree$')
        if(_minvel is not 0) and (_maxvel is not 0):
            _velmap.set_clim([_minvel, _maxvel])

        _min = np.array(self.maps.scans[tab_index].velocity_map.min()).min()
        _max = np.array(self.maps.scans[tab_index].velocity_map.max()).max()
        if(_minvel == 0) and (_maxvel == 0):
            self.tab_objects[tab_index].le_vel_min.setText('{0:.0f}'.format(_min))
            self.tab_objects[tab_index].le_vel_max.setText('{0:.0f}'.format(_max))
        self.tab_objects[tab_index].le_vel_min.setEnabled(1)
        self.tab_objects[tab_index].le_vel_max.setEnabled(1)
        self.remove_mpl(tab_index)
        self.view_dc[tab_index] = False
        self.view_dcm[tab_index] = False
        self.view_fft[tab_index] = False
        self.view_vel[tab_index] = True
        self.remove_mpl(tab_index)
        self.add_mpl(tab_index, _velfig)
        return

    def ui_voltage_limit_changed(self, tab_index):
        '''
        ui_voltage_limit_changed(self, tab_index): Signal for Qt that fires whenever the voltage min/max values are
        changed in the visu2 GUI. Not meant to be called otherwise.
        '''
        # Reset view flag so the new data is replotted.
        self.view_dc[tab_index] = False
        # Get latest min/max values and re-trigger ui_process_dc_voltage to update the image.
        _fmaxvoltage = float(self.tab_objects[tab_index].le_dc_min.text())
        _fminvoltage = float(self.tab_objects[tab_index].le_dc_max.text())
        self.ui_process_dc_voltage(tab_index, _fmaxvoltage, _fminvoltage)
        return

    def ui_fft_limit_changed(self, tab_index):
        '''
        ui_voltage_limit_changed(self, tab_index): Signal for Qt that fires whenever the FFT min/max values are
        changed in the visu2 GUI. Not meant to be called otherwise.
        '''
        # Reset view flag so the new data is replotted.
        self.view_fft[tab_index] = False
        # Get latest min/max values and re-trigger ui_process_fft to update the image.
        # FFT is specified as MHz in the lineedits, so multiply by 1^6 to get
        # hertz.
        _fftmin = float(self.tab_objects[tab_index].le_fft_min.text()) * 1E6
        _fftmax = float(self.tab_objects[tab_index].le_fft_max.text()) * 1E6
        self.ui_process_fft(tab_index, _fftmin, _fftmax)
        return

    def ui_velocity_limit_changed(self, tab_index):
        '''
        ui_voltage_limit_changed(self, tab_index): Signal for Qt that fires whenever the velocity min/max values are
        changed in the visu2 GUI. Not meant to be called otherwise.
        '''
        # Reset view flag so the new data is replotted.
        self.view_vel[tab_index] = False
        # Get latest min/max values and re-trigger ui_process_velocity to update the image.
        _fmaxvel = float(self.tab_objects[tab_index].le_vel_max.text())
        _fminvel = float(self.tab_objects[tab_index].le_vel_min.text())
        self.ui_process_velocity(tab_index, _fminvel, _fmaxvel)
        return

    def ui_metadata_changed(self, tab_index):
        # Update the linked metadata common parameters       
        for current in self.maps.scans:
                current.metadata['sample_desc'] = self.tab_objects[tab_index].txt_sample_name.text()
                current.metadata['x_start'] = float(self.tab_objects[tab_index].txt_md_startx.text())
                current.metadata['y_start'] = float(self.tab_objects[tab_index].txt_md_starty.text())
                current.metadata['x_delta'] = float(self.tab_objects[tab_index].txt_md_deltax.text())
                current.metadata['y_delta'] = float(self.tab_objects[tab_index].txt_md_deltay.text())
        
        # Update tab-specific metadata parameters
        self.maps.scans[tab_index].metadata['acq_angle'] = int(self.tab_objects[tab_index].txt_md_acq_angle.text())

        # Depending on view context, reset flag to force redraw and call 
        # appropriate function.
        if(self.view_dc[tab_index] is True):
            self.view_dc[tab_index] = False
            self.ui_process_dc_voltage(tab_index)
        elif(self.view_fft[tab_index] is True):
            self.view_fft[tab_index] = False
            self.ui_process_fft(tab_index)
        elif(self.view_vel[tab_index] is True):
            self.view_vel[tab_index] = False
            self.ui_process_velocity(tab_index)

        return

app = QtWidgets.QApplication(sys.argv)
window = Ui()
app.exec_()
