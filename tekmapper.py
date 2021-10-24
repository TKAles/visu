from PyQt5.QtWidgets import QProgressDialog, QWidget
from PyQt5 import Qt
import tekwfm
import pandas
import numpy
import multiprocessing
import scipy.fftpack

class TekMapper:

    def __init__(self, _dcw, _rfw):
        self.dc_wfm = _dcw
        self.rf_wfm = _rfw
        
        self.frames_in_map = 0
        # Property variables
        self._xPos = []
        self._yDCMeans = []
        return
    
    
    def load_files(self):
        
        # Load one file to get the number of fast-frames
        _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(self.dc_wfm[0])
        samples, frames = _vt.shape
        self.frames_in_map = frames
        dc_map = []
        rf_map = []

        for currentfile in self.dc_wfm:
            dc_map.append(self.average_dc(currentfile))
        self.un_voltages = pandas.DataFrame(dc_map)
        self.voltages = self.un_voltages
        self.dc_mask = self.un_voltages > 0.02
        self.voltages = self.voltages * self.dc_mask

        for currentfile in self.rf_wfm:
            rf_map.append(self.calculate_fft(currentfile))
        self.un_ffts = pandas.DataFrame(rf_map)
        self.mask_fft = self.un_ffts * self.dc_mask

        

    def average_dc(self, wfm_file):
        # Read in the wfm file, get the number of samples and the number of frames, take the average
        # of the DC signal in each frame and return that as a list consisting of y-averages.
        volts, tstart, tscale, tfrac, tdatefrac, tdate = tekwfm.read_wfm(wfm_file)
        samples, frames = volts.shape
        dc_dataframe = pandas.DataFrame(volts)
        return dc_dataframe.mean()
   
    def calculate_fft(self, wfm_file, s_rate=6.25E9):
       # Calculate the FFT of each record and append it to the FFT Map
       # Convert the map into a dataframe and export as an object property
        volts, tstart, tscale, tfrac, tdatefrac, tdate = tekwfm.read_wfm(wfm_file)
        samples, frames = volts.shape
        frequencies = []
        for record_index in range(0, frames):
            wfmfft = list(numpy.abs(scipy.fftpack.fft(volts[:,record_index])))
            wfmfreqs = scipy.fftpack.fftfreq(wfmfft.__len__()) * s_rate
            frequencies.append(wfmfreqs[wfmfft.index(max(wfmfft))])
        
        return frequencies



        
