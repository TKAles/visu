'''
TekCollection - An object to hold a collection of TekMaps which represent scans that need to be
                registered, aligned, then composed into the 'slowness' map.

Thomas Ales
June 2020
'''

import MapData
class TekCollection:

    

    def __init__(self):

        self.data_directories = []
        self.scans = []
        return

    def initalize_data(self, datadir, index):
        if(self.data_directories.__len__() == 0):
            self.data_directories = [datadir]
            self.scans = [MapData.TekMap(self.data_directories[index])]
            print("inital directory loaded")
        else:
            self.data_directories.append(datadir)
            self.scans.append(MapData.TekMap(self.data_directories[-1]))
            print("appended map {0} to scans list".format(self.data_directories.__len__()))
        return        

        
    def process_dc(self):
        for current in self.map_collections:
            current.mp_assemble_dcmap()
            current.compute_dcmask()
        return

    def process_fft(self):
        for current in self.map_collections:
            current.mp_assemble_fftmap()
        
        return

    def process_velocity(self):
        for current in self.map_collections:
            current.mp_assemble_velocitymap()

        return
        
    def add_map(self):
        for _currentdir in self.data_directories:
            self.map_collections.append(MapData.TekMap(_currentdir))
        return


