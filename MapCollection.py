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
        '''
        TekCollection.initalize_data(datadir, index): expects an absolute path and index
                                                      so that it can populate the data_directories
                                                      property of the object.
        '''
        # In the zero case, the data_directories property isn't initialized.
        if(self.data_directories.__len__() == 0):
            self.data_directories = [datadir]
            self.scans = [MapData.TekMap(self.data_directories[index])]
            
        # append to end of list.
        else:
            self.data_directories.append(datadir)
            self.scans.append(MapData.TekMap(self.data_directories[-1]))
        return        

        
    def process_dc(self, _index=0, _threads=4):
        '''

        '''
        self.scans[_index].mp_assemble_dcmap(_threads)
        self.scans[_index].compute_dcmask()
        return

    def process_fft(self, _index=0, _threads=4):
        
        self.scans[_index].mp_assemble_fftmap(_threads)
        return

    def process_velocity(self, _index=0):
        self.scans[_index].mp_assemble_velocitymap()
        return
        
    def add_map(self):
        for _currentdir in self.data_directories:
            self.map_collections.append(MapData.TekMap(_currentdir))
        return


