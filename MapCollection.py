'''
TekCollection - An object to hold a collection of TekMaps which represent scans that need to be
                registered, aligned, then composed into the 'slowness' map.

Thomas Ales
June 2020
'''

import MapData

class TekCollection:

    map_collections = []

    def __init__(self, _datadir, _metadata):

        self.data_directories = []
        
        for _dir in _datadir:
            self.data_directories.append(_dir)

        self.metadata = _metadata
        return

    def add_map(self):
        for _currentdir in self.data_directories:
            self.map_collections.append(MapData.TekMap(_currentdir))
        return

    def populate_maps(self):
        
        return

