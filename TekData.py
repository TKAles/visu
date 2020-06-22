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
        
        return

    def compute_mask(self):
        self.dc_mask = self.mean_dc_level >= self.mask_threshold_voltage
        return

    def compute_fft(self, _mode="Window", _memory=False):
        '''
        compute_fft(_mode="Full|Window", _memory=False|True): Computes the FFT of the waveform 
                for either the full record, or windowed record depending on mode. Will keep RF waveform
                data in memory if you have the RAM to spare (VERY HUNGRY, YOU'VE BEEN WARNED).
        '''
        _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(self.rf_filename)
        _vtdf = pd.DataFrame(_vt)
        maxfreqs = []
        self.psd_fits = []
        if(_mode == "Full"):
            for record_index in range(0, self.frames_in_file):
                fftrec = list(sp.fft.rfft(list(_vtdf[record_index])))
                freq = list(sp.fft.fftfreq(fftrec.__len__()) * self.sample_rate)
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
#                self.psd_fits.append(self.fit_gaussian_model(freq, fftrec))
            self.frequencies = maxfreqs
        del _vt, _ts, _tsc, _tf, _tdf, _td
        
        return self.frequencies

    def compute_velocity(self, _spacing=25.0):
        '''
        compute_velocity(_spacing=25.0): Compute the velocity map with a given _spacing in microns.
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
        
        self.rf_voltage_data = pd.DataFrame(_record)
        return self.rf_voltage_data

    def gaussian_model(self, x, x0, y0, sigma):
        p = [x0, y0, sigma]
        return p[1] * np.exp(-(((x/1e8)-p[0])/p[1])**2)

    def fit_gaussian_model(self, _psdfreqs, _psddata):
        _p = [1., 1., 1.]
        _psdfreqs = np.array(_psdfreqs)
        _psddata = np.array(_psddata)
        fit, tmp = sp.optimize.curve_fit(self.gaussian_model, _psdfreqs, _psddata, p0=_p)
        return fit

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

        

    

        
