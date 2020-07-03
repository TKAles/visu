'''
    MapData Objects
    Thomas Ales
    June 2020
'''
import gc
import glob
import os

import matplotlib.pyplot as plt
import pandas as pd

import TekData
import pyfftw
import tekwfm

from multiprocessing import Pool

class TekMap:

    rf_map = []
    dc_map = []
    dc_mask = []

    rf_filelist = []
    dc_filelist = []

    map_directory = ""
    map_aspect = 0
    
    waveforms = []

    rf_voltagemap = []

    
    def __init__(self, _datadir):
        '''
        TekMap(_datadir): Constructor, requires _datadir which is an absolute path to the WFM directory.
        '''
        
        self.map_directory = _datadir
        self.rf_filelist = []
        self.dc_filelist = []
        self.dc_map = []
        self.dc_mask = []
        self.fft_map = []
        self.velocity_map = []
        self.waveforms = []
        self.thresholddc = 0.100            # Starting mask voltage 
        self.metadata = {"acq_angle": 0, 
                "x_start": 0, 
                "y_start": 0, 
                "x_delta": 0, 
                "y_delta": 0,
                "sample_desc": ""}
        # Search for files in the map_directory. Sort into RF and DC waveforms
        os.chdir(self.map_directory)
        for current_file in glob.glob("*.wfm"):
            if(current_file.startswith("RF")):
                self.rf_filelist.append(self.map_directory + "/" + current_file)

            elif(current_file.startswith("DC")):
                self.dc_filelist.append(self.map_directory + "/" + current_file)

        self.rf_filelist.sort()
        self.dc_filelist.sort()
        print("Found {0} & {1} DC / RF Files".format(self.rf_filelist.__len__(),
                                                      self.dc_filelist.__len__()))

        self.tekwfmclass = TekData.TekWaveForm(self.rf_filelist[0], self.dc_filelist[0])

    def mp_assemble_dcmap(self, _plot=False):
        _mpool = Pool()
        _outputlist = list(_mpool.map(self.tekwfmclass.mp_compute_dcvoltage, self.dc_filelist))
        _outputdf = pd.DataFrame(_outputlist)
        _mpool.close()
        _mpool.join()
        self.dc_map = _outputdf
    
        return
    
    def compute_dcmask(self, _plot=False):
        self.dc_mask = (self.dc_map > self.thresholddc)
        return
    

    def mp_assemble_fftmap(self, _plot=False):
        # Map the rf_filelist through the FFT function and store as rf_map
        _mpool = Pool()
        _outputlist = list(_mpool.map(
            self.tekwfmclass.mp_compute_fft, self.rf_filelist
        ))
        _outputdf = pd.DataFrame(_outputlist)
        self.rf_map = _outputdf * self.dc_mask
        _mpool.close()
        _mpool.join()
        
        return

    def plot_fftmap(self, _limits=[80e6, 300e6], _color="gray"):
        _margin = 1.0
        _fftplot = plt.figure(figsize=[12, 12])
        plt.imshow(self.fft_map,aspect=self.waveforms[0].frames_in_file/self.rf_filelist.__len__(), 
                   cmap=_color)
        plt.title("FFT Frequency")
        plt.text(0, 0, "SAW Angle:     $\\alpha$=" + self.metadata["acq_angle"].__str__() + r"$\degree$" +
                "\nSample ID:     " + self.metadata["sample_desc"])
        plt.clim(0.080, 0.300)
        fft_colorbar = plt.colorbar()
        plt.clim(_limits)
        fft_colorbar.set_label("Main Frequency [Hz]")
        plt.xlabel("Record # [200/mm]")
        plt.ylabel("Row # [10/mm]")
        x0, x1, y0, y1 = plt.axis()
        plt.axis((x0-_margin,
                  x1+_margin,
                  y0-_margin,
                  y1+_margin))
        return

    def mp_assemble_velocitymap(self, _spacing=12.5E-6):
        self.velocity_map = self.rf_map.multiply(_spacing)
        return
        
    def assemble_velocitymap(self, _spacing=12.5):
        _tempmap = []
        
        for fileidx in range(0, self.waveforms.__len__()):
            self.waveforms[fileidx].compute_velocity(_spacing)
            _tempmap.append(list(self.waveforms[fileidx].velocity_data[0]))

        self.velocity_map = pd.DataFrame(_tempmap) * self.dc_mask
        
        return
    
    def plot_velocitymap(self, _limits=[2500, 4000], _color="gray"):
        _margin = 1.0
        _velplot = plt.figure(figsize=[12, 12])
        plt.imshow(self.velocity_map, aspect=self.waveforms.frames_in_file/self.rf_filelist.__len__(), cmap=_color)
        plt.title("Velocity Map")
        plt.text(0, 0, "SAW Angle:     $\\alpha$=" + self.metadata["acq_angle"].__str__() + r"$\degree$" +
                "\nSample ID:     " + self.metadata["sample_desc"])
        plt.clim(0.080, 0.300)
        fft_colorbar = plt.colorbar()
        plt.clim(_limits)
        fft_colorbar.set_label("Velocity [m$^{1}s^{-1}$]")
        plt.xlabel("Record # [200/mm]")
        plt.ylabel("Row # [10/mm]")
        x0, x1, y0, y1 = plt.axis()
        plt.axis((x0-_margin,
                  x1+_margin,
                  y0-_margin,
                  y1+_margin))
        return

    def assemble_rf_voltagemap(self):
        self.rf_voltagemap = []
        _rec = []
        for fileidx in range(0, self.waveforms.__len__()):
            _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(self.waveforms[fileidx][1].rf_filename)
            _vtdf = pd.DataFrame(_vt)
            _record = []
            for record_idx in range(0, self.waveforms[0][1].frames_in_file):
                _maxvoltidx = _vtdf[record_idx].argmax()
                _record.append(_vtdf.loc[_maxvoltidx, record_idx])
            _rec.append(_record)
        self.rf_voltagemap = pd.DataFrame(_rec)

        return 

