'''
    MapData Objects
    Thomas Ales
    June 2020
'''
import glob
import os
import gc
from joblib import Parallel, delayed

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
    def __init__(self, _datadir):
        '''
        TekMap: Constructor, requires _datadir which is an absolute path to the WFM directory.
        '''
        gc.enable()
        self.map_directory = _datadir
        
        # Search for files in the map_directory. Sort into RF and DC waveforms
        os.chdir(self.map_directory)
        for current_file in glob.glob("*.wfm"):
            if(current_file.startswith("RF")):
                self.rf_filelist.append(self.map_directory + "/" + current_file)

            elif(current_file.startswith("DC")):
                self.dc_filelist.append(self.map_directory + "/" + current_file)

        self.rf_filelist.sort()
        self.dc_filelist.sort()
        print("Loaded {0} & {1} DC / RF Files".format(self.rf_filelist.__len__(),
                                                      self.dc_filelist.__len__()))

        for idx, current_file in enumerate(self.rf_filelist):
            self.waveforms.append([idx, TekData.TekWaveForm(current_file, self.dc_filelist[idx])])
            print(idx.__str__())

        gc.collect()
        return




