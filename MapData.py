'''
    MapData Objects
    Thomas Ales
    June 2020
'''
import glob
import os
import gc
from joblib import Parallel, delayed
import pandas as pd
import matplotlib.pyplot as plt
import tqdm.notebook as tqdm
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

    metadata = {"acq_angle": 0, "x_start": 0, "y_start": 0, "x_delta": 0, "y_delta": 0}
    def __init__(self, _datadir):
        '''
        TekMap(_datadir): Constructor, requires _datadir which is an absolute path to the WFM directory.
        '''
        gc.enable()
        self.map_directory = _datadir
        self.rf_filelist = []
        self.dc_filelist = []
        self.dc_map = []
        self.dc_mask = []
        self.fft_map = []
        self.waveforms = []
        # Search for files in the map_directory. Sort into RF and DC waveforms
        os.chdir(self.map_directory)
        for current_file in glob.glob("*.wfm"):
            if(current_file.startswith("RF")):
                self.rf_filelist.append(self.map_directory + "/" + current_file)

            elif(current_file.startswith("DC")):
                self.dc_filelist.append(self.map_directory + "/" + current_file)

        self.rf_filelist.sort()
        self.dc_filelist.sort()
        print("Loading {0} & {1} DC / RF Files".format(self.rf_filelist.__len__(),
                                                      self.dc_filelist.__len__()))

        for idx, current_file in enumerate(self.rf_filelist):
            self.waveforms.append([idx, TekData.TekWaveForm(current_file, self.dc_filelist[idx])])
            

        gc.collect()
        return

    def assemble_dcmap(self, _plot=False):
        '''
        assemble_dcmap(_plot=False): Assemble the collection of loaded files into a DC map.
                                     Sorts the files by correct Y-offset and can output a 
                                     plot if _plot=True. 
        '''
        # Assemble DC information from each TekData object
        _tempmap = []

        for fileidx in range(0, self.waveforms.__len__()):
            _tempmap.append([fileidx, self.waveforms[fileidx][1].mean_dc_level])
        # Sort map
        
        _tempmap.sort
        for line in _tempmap:
            self.dc_map.append(line[1])
        
        _dcm = pd.DataFrame(self.dc_map)
        self.dc_mask = _dcm >= 0.080
        if(_plot):
            self.plot_dcmap()
        return

    def plot_dcmap(self):
        _margin = 1.0
        _dcplot = plt.figure(figsize=[12, 12])
        plt.imshow(self.dc_map,aspect=self.waveforms[0][1].frames_in_file/self.rf_filelist.__len__())
        plt.title("DC Level")
        plt.text(0, 0, "SAW Angle:     $\\alpha$=" + self.metadata["acq_angle"].__str__() + r"$\degree$" +
                "\nSample ID:     " + self.metadata["sample_desc"])
        plt.clim(0.080, 0.300)
        dc_colorbar = plt.colorbar()
        dc_colorbar.set_label("Voltage [V]")
        plt.xlabel("Record # [200/mm]")
        plt.ylabel("Row # [10/mm]")
        x0, x1, y0, y1 = plt.axis()
        plt.axis((x0-_margin,
                  x1+_margin,
                  y0-_margin,
                  y1+_margin))
        return

    def assemble_fftmap(self, _plot=False):
        '''
        assemble_fftmap(_plot=False): Assemble the collection of the loaded files into a FFT map.
        '''
        _tempmap = []
        for fileidx in tqdm.tqdm(range(0, self.waveforms.__len__())):
            _tempmap.append([fileidx, self.waveforms[fileidx][1].compute_fft("Full")])
            
        
        _tempmap.sort

        for line in _tempmap:
            self.fft_map.append(line[1])
        
        self.fft_map = pd.DataFrame(self.fft_map)
        self.fft_map = self.fft_map * self.dc_mask
        return

    def plot_fftmap(self, _limits=[80e6, 300e6]):
        _margin = 1.0
        _fftplot = plt.figure(figsize=[12, 12])
        plt.imshow(self.fft_map,aspect=self.waveforms[0][1].frames_in_file/self.rf_filelist.__len__())
        plt.title("FFT Frequency - Full")
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




