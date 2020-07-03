'''
TekCollection - An object to hold a collection of TekMaps which represent scans that need to be
                registered, aligned, then composed into the 'slowness' map.

Thomas Ales
June 2020
'''

import MapData
from tqdm.notebook import tqdm
class TekCollection:

    map_collections = []

    def __init__(self, _datadir, _metadata):

        self.data_directories = []
        
        for _dir in tqdm(_datadir):
            self.data_directories.append(_dir)

        self.metadata = _metadata
        return

    def initalize_maps(self):
        for currentmap in tqdm(self.data_directories):
            self.map_collections.append(MapData.TekMap(currentmap))
        
        return

    def process_dc(self):
        for current in tqdm(self.map_collections):
            current.mp_assemble_dcmap()
            current.compute_dcmask()
        return

    def process_fft(self):
        for current in tqdm(self.map_collections):
            current.mp_assemble_fftmap()
        
        return

    def process_velocity(self):
        for current in tqdm(self.map_collections):
            current.mp_assemble_velocitymap()

        return
        
    def add_map(self):
        for _currentdir in self.data_directories:
            self.map_collections.append(MapData.TekMap(_currentdir))
        return


