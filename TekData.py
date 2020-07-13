'''
    TekData Class
    Thomas Ales
    June 2020
'''
import math
import tekwfm
import pandas as pd
import numpy as np
import scipy.signal
import scipy as sp
import pyfftw
from multiprocessing import Pool
class TekWaveForm:
    '''
        TekData: Data structure for waveforms captured from Tektronix MSO 5/6 Oscilloscopes
                 Represents a single row of data in the scan.
    '''
    rf_filename = ""
    dc_filename = ""

    frequencies = []
    velocity_data = []
    rf_voltage_data = []
    sample_timestart = 0.0
    sample_timestep = 0.0
    sample_rate = 0

    mean_dc_level = []
    dc_mask = []
    mask_threshold_voltage = 0.080
    saw_packet_centerpoint = 0
    saw_window_points = []
    saw_packet_window = [512, 512]

    points_per_record = 0
    frames_in_file = 0

    psd_fits = []
    _rec = []
  
    def __init__(self, _rf_file, _dc_file):
        '''
            TekData(rf_file, dc_file): Constructor for the TekData class. Requires the absolute path to a DC and RF file
                                       rf_file - absolute path to RF file. Usually CH1
                                       dc_file - absolute path to DC file. Usually CH4
        '''
        self.rf_filename = _rf_file
        self.dc_filename = _dc_file

        # Read in RF and DC file using Tektronix import util.
        _vtdc, _tsdc, _tscdc, _tfdc, _tdfdc, _tddc = tekwfm.read_wfm(_dc_file)
        _vtdf = pd.DataFrame(_vtdc)
        self.mean_dc_level = pd.Series(list(_vtdf.mean()))
        self.points_per_record, self.frames_in_file = _vtdf.shape
        # Timestep and trigger-start information.
        self.sample_timestart = _tsdc
        self.sample_timestep = _tscdc
        # Infer the sample rate from the timestep in the RF file.
        self.sample_rate = 1 / self.sample_timestep

        # Clear out the temp variables from the .wfm file import to save RAM.
        del _vtdc, _tsdc, _tscdc, _tfdc, _tdfdc, _tddc, _vtdf
        pyfftw.interfaces.cache.enable()

        # 'monkey-patch' the pyfftw interface into scipy.fft
        sp.fftpack = pyfftw.interfaces.scipy_fftpack
        
        return
    '''
    LEGACY FUNCTION
    def compute_fft(self, _mode="Window", _memory=False):
        
        compute_fft(_mode="Full|Window", _memory=False|True): Computes the FFT of the waveform 
                for either the full record, or windowed record depending on mode. Will keep RF waveform
                data in memory if you have the RAM to spare (VERY HUNGRY, YOU'VE BEEN WARNED).
        
        _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(self.rf_filename)
        _vtdf = pd.DataFrame(_vt)
        maxfreqs = []
        self.psd_fits = []
        if(_mode == "Full"):
            for record_index in range(0, self.frames_in_file):
                fftrec = list(pyfftw.interfaces.scipy_fft.rfft(list(_vtdf[record_index]), 8192, 
                         planner_effort='FFTW_MEASURE', threads=2))
                freq = list(pyfftw.interfaces.scipy_fft.fftfreq(fftrec.__len__()) * self.sample_rate)
                maxfreqs.append(freq[fftrec.index(max(fftrec))])
                #self.psd_fits.append(self.fit_gaussian_model(np.abs(freq), np.abs(fftrec)))
            self.frequencies = maxfreqs 
            
        elif(_mode == "Window"):

            for record_index in range(0, self.frames_in_file):
                _record = _vtdf[record_index]
                _recordmaxidx = _record.argmax()
                if(_recordmaxidx < 512):
                    _recordmaxidx = 512
                    _winrecord = _record.loc[0:1023]
                else:
                    _winrecord = _record.loc[_recordmaxidx - self.saw_packet_window[0]:_recordmaxidx + self.saw_packet_window[1]]
                fftrec = list(sp.fft.rfft(_winrecord.tolist()))
                freq = list(sp.fft.fftfreq(_winrecord.__len__()) * self.sample_rate)
                maxfreqs.append(freq[fftrec.index(max(fftrec))])
            # self.psd_fits.append(self.fit_gaussian_model(freq, fftrec))
            self.frequencies = maxfreqs
        del _vt, _ts, _tsc, _tf, _tdf, _td
        
        return self.frequencies
    '''
    def mp_compute_velocity(self, fft_data, spacing=0.25):

        return

    def mp_compute_dcvoltage(self, file_name=""):
        if(file_name == ""):
            file_name = self.dc_filename
        # Read in the file_name and convert to Dataframe. Use mean() to get
        # average of rows.
        _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(file_name)
        _vtdf = pd.DataFrame(_vt)
        mean_dc = _vtdf.mean()
        # Return DC dataframe
        return mean_dc

    def mp_compute_fft(self, file_name="", _fftsize=int(4096)):
        '''
        mp_compute_fft(file_name): mappable function to compute the pixel FFT for a given file.
        '''
        if(file_name == ""):
            file_name = self.rf_filename

        diag = False    # Diagnostic output flag
        # Read in file and determine sample rate
        _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(file_name)
        sample_rate = int(1 / _tsc)

        if(diag):
            print("Loaded {0}".format(file_name))
            print("Detected Sample Rate: {0}".format(sample_rate))

        # Convert to DataFrame, retrieve the length of each waveform record
        # and the number of records in the row file.
        _vtdf = pd.DataFrame(_vt)
        
        
        _recordlen, _numrecords = _vtdf.shape

        if(diag):
            print("Records: {0}\tLength: {1} points".format(_numrecords, _recordlen))

        # Iterate through each waveform record and compute FFT, find frequency
        # with highest power and select as pixel frequency.
        # Window input to +/- 512 points around maximum voltage sample. If center is less
        # than 512, default to record length of 0:1024
        results = []
        for record_idx in range(0, _numrecords):
            _vtr = np.array(_vtdf[record_idx])
            _vtidxmax = _vtr.argmax()
            if(_vtidxmax < 512):
                _vtidxmax = 512
                _vts = _vtr[0:1024]
            else:
                _min = _vtidxmax - 512
                _max = _vtidxmax + 511
                _vts = _vtr[_min:_max]

            _fftpower = np.array(sp.fft.rfft(_vts, n=_fftsize))
            _fftfreq = sp.fft.fftfreq(_fftpower.__len__())  * sample_rate
            _fftmax = _fftpower.argmax()
            _fftmaxval = _fftfreq[_fftmax]
            # Append to results 
            results.append(_fftmaxval)
        # Return list of frequencies for row.
        return results

    def compute_velocity(self, _spacing=12.5):
        '''
        compute_velocity(_spacing=12.5): Compute the velocity map with a given _spacing in microns.
                                         Will populate the velocity_data property of the class.
        '''
        
        _freqpd = pd.DataFrame(self.frequencies)
        self.velocity_data = _freqpd * (_spacing * (1E-6)) #* self.dc_mask
        
        return self.velocity_data

    def map_rf_voltage(self):
        _vtdf = []
        _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(self.rf_filename)
        _vtdf = pd.DataFrame(_vt)
        _record = []
        for record_index in range(0, self.frames_in_file):
            _maxvoltidx = _vtdf[record_index].idxmax()
            _record.append(_vtdf.loc[_maxvoltidx, record_index])


class Utilities:

    def __init__(self):

        pass

    def gaussian(self, x, amp, cen, wid):
        return amp * np.exp(-(x-cen)**2 / wid)

    def window_data(self, _amplitudes, _frequencies, _winsize=16):
        _absamps = np.abs(_amplitudes)
        _absamparray = pd.DataFrame(_absamps)
        _freqarray = pd.DataFrame(_frequencies)
        _max = _absamparray.max()
        _maxindex = _absamparray.idxmax()
        _winmin = _maxindex - (_winsize/2)
        _winmax = _maxindex + (_winsize/2)

        return _absamparray[int(_winmin):int(_winmax)], _freqarray[int(_winmin):int(_winmax)]

    def fit_gaussian(self, _winamps, _winfreqs):
        _minfreq = float(_winfreqs.min())
        _maxfreq = float(_winfreqs.max())


        return
    def fit_gaussian_to_normfft(self, _normdata, _frequencies):
        _frequncies = pd.Series(_frequencies)
        _minx = _frequencies.min()
        _maxx = _frequncies.max()
        _fitX = np.arange(float(_minx), float(_maxx), 1E6)
        X = _frequencies
        x = np.sum(X*_frequencies)/np.sum(_frequencies)
        return _fitX, x

        

    

        
