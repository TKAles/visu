'''
    MapData Objects
    Thomas Ales
    June 2020

    CHANGELOG:
    v0.0 - Initial Release.
    v0.1 - Cleaned up code to conform to FLAKE8.
           Removed vestigal functions/properties.
           Removed unnecessary dependencies.
'''
import glob
from multiprocessing import Pool
import os

import pandas as pd

import TekData


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

    def __init__(self, _datadir=""):
        '''
        TekMap(_datadir): Constructor, requires _datadir which is an absolute
        path to the WFM directory.
        '''

        self.map_directory = _datadir
        self.rf_filelist = []
        self.dc_filelist = []
        self.dc_map = []
        self.dc_mask = []
        self.fft_map = []
        self.velocity_map = []
        self.waveforms = []
        self.thresholddc = 0.03
        self.metadata = {"acq_angle": 0,
                         "x_start": 0,
                         "y_start": 0,
                         "x_delta": 0,
                         "y_delta": 0,
                         "sample_desc": ""}

        # Search for files in the map_directory.
        # Sort into RF and DC waveforms
        os.chdir(self.map_directory)
        for current_file in glob.glob("*.wfm"):
            if(current_file.startswith("RF")):
                self.rf_filelist.append(self.map_directory +
                                        "/" + current_file)

            elif(current_file.startswith("DC")):
                self.dc_filelist.append(self.map_directory +
                                        "/" + current_file)

        self.rf_filelist.sort()
        self.dc_filelist.sort()
        self.tekwfmclass = TekData.TekWaveForm(self.rf_filelist[0],
                                               self.dc_filelist[0])

    def mp_assemble_dcmap(self, _threads=4):
        _mpool = Pool(processes=_threads)
        _outputlist = list(_mpool.map(self.tekwfmclass.mp_compute_dcvoltage,
                           self.dc_filelist))
        _outputdf = pd.DataFrame(_outputlist)
        _mpool.close()
        
        self.dc_map = _outputdf

        return

    def compute_dcmask(self):
        self.dc_mask = (self.dc_map > self.thresholddc)
        return

    def mp_assemble_fftmap(self, _threads=4):
        # Map the rf_filelist through the FFT function and store as rf_map
        _mpool = Pool(processes=_threads)
        _outputlist = list(_mpool.map(
            self.tekwfmclass.mp_compute_fft, self.rf_filelist
        ))
        _outputdf = pd.DataFrame(_outputlist)
        self.rf_map = _outputdf * self.dc_mask
        _mpool.close()
        _mpool.join()

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
