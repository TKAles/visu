'''
    TekData Class
    Thomas Ales
    June 2020
'''
import math
import tekwfm
import pandas as pd
import scipy.signal
import scipy as sp

class TekWaveForm:
    '''
        TekData: Data structure for waveforms captured from Tektronix MSO 5/6 Oscilloscopes
                 Represents a single row of data in the scan.
    '''
    rf_filename = ""
    dc_filename = ""

    rf_data = []
    windowed_rf_data = []
    full_frequencies = []
    windowed_frequencies = []
    sample_timestart = 0.0
    sample_timestep = 0.0
    sample_rate = 0

    mean_dc_level = []
    dc_mask = []
    mask_threshold_voltage = 0.080
    saw_packet_centerpoint = 0
    saw_window_points = []
    saw_packet_window = [512, 511]

    points_per_record = 0
    frames_in_file = 0


  
    def __init__(self, _rf_file, _dc_file):
        '''
            TekData(rf_file, dc_file): Constructor for the TekData class. Requires the absolute path to a DC and RF file
                                       rf_file - absolute path to RF file. Usually CH1
                                       dc_file - absolute path to DC file. Usually CH4
        '''
        self.rf_filename = _rf_file
        self.dc_filename = _dc_file
        _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(_rf_file)
        self.rf_data = pd.DataFrame(_vt)
        self.sample_timestart = _ts
        self.sample_timestep = _tsc
        self.sample_rate = 1 / self.sample_timestep
        _vt, _ts, _tsc, _tf, _tdf, _td = tekwfm.read_wfm(_dc_file)
        _vtdf = pd.DataFrame(_vt)
        self.mean_dc_level = _vtdf.mean()
        self.points_per_record, self.frames_in_file = _vtdf.shape
        return

    def compute_mask(self):
        self.dc_mask = self.mean_dc_level >= self.mask_threshold_voltage
        return

    def isolate_packet(self):
        '''
        isolate_packet(): Isolates the saw packet based off of maximum voltage.
        '''
        for current_frame in range(0, self.frames_in_file):
            self.saw_packet_centerpoint = self.rf_data[current_frame].argmax()
            start_window = self.saw_packet_centerpoint - self.saw_packet_window[0]
            if(start_window < 0):
                end_window = (start_window * -1) + self.saw_packet_window[1] + self.saw_packet_centerpoint
                start_window = 0
            else:
                end_window = self.saw_packet_centerpoint + self.saw_packet_window[1]

            self.windowed_rf_data = self.rf_data[current_frame].loc[start_window:end_window]
            print("Window Start: {0} End: {1} Length: {2}".format(start_window, end_window, end_window-start_window))
            self.saw_window_points.append([start_window, end_window])
        return

    def compute_fft(self, _mode="Full", _memory=False):
        '''
        compute_fft(_mode="Full|Window", _memory=False|True): Computes the FFT of the waveform 
                for either the full record, or windowed record depending on mode. Will keep RF waveform
                data in memory if you have the RAM to spare (VERY HUNGRY, YOU'VE BEEN WARNED).
        '''
        maxfreqs = []
        if(_mode == "Full"):
            for record_index in range(0, self.frames_in_file):
                fftrec = list(sp.fft.rfft(list(self.rf_data[record_index])))
                freq = list(sp.fft.fftfreq(self.rf_data.__len__()) * self.sample_rate)
                maxfreqs.append(freq[fftrec.index(max(fftrec))])

            self.full_frequencies = maxfreqs * self.dc_mask

        elif(_mode == "Window"):
            for record_index in range(0, self.frames_in_file):
                window = list(self.rf_data[record_index].loc[self.saw_window_points[record_index][0]:self.saw_window_points[record_index][1]])
                fftrec = list(sp.fft.rfft(window))
                freq = list(sp.fft.fftfreq(window.__len__()) * self.sample_rate)
                maxfreqs.append(freq[fftrec.index(max(fftrec))])

            self.windowed_frequencies = maxfreqs * self.dc_mask

        return