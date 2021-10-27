'''
    Visu2 Scan Collection Class
    Thomas K Ales | October 2021
    Version 2.1.0-a
'''

import glob
import os

import MapData as mapdat

class VisuScanCollection:

    def __init__(self):
        self.number_of_scans = 0;
        self.rf_files = []
        self.dc_files = []
        
        self.rf_scan_canvas = []
        self.rf_scan_nav = []
        self.dc_scan_canvas = []
        self.dc_scan_nav = []
        self.vel_scan_canvas = []
        self.vel_scan_nav = []
        self.scan_collection = []

        self.path_to_files = ''
        self.angle_increment = 0

        self.sample_name = ''
        self.scan_coords = []
        self.scan_speed = 100.0
        self.laser_frequency = 2000.0
        
    def parse_directory(self):
        '''
        parse_directory(self): looks for files matching the standard output
            pattern of the oscilloscope in the .path_to_files variable.
            Expects that path_to_files is set prior to execution or will error.
        '''

        scan_count = 0
        scanning = True
        os.chdir(self.path_to_files)

        
        while scanning == True:
            temp_file_list_rf = []
            temp_file_list_dc = []
            for current_file in glob.glob('*.WFM'):
                if(current_file[3:5] == '{0:02d}'.format(scan_count)):
                    if(current_file.startswith('DC')):
                        temp_file_list_dc.append(current_file)
                    elif(current_file.startswith('RF')):
                        temp_file_list_rf.append(current_file)
            
            if(temp_file_list_rf.__len__() != 0):
                scan_count = scan_count + 1
                self.dc_files.append(temp_file_list_dc)
                self.rf_files.append(temp_file_list_rf)
            elif(temp_file_list_rf.__len__() == 0):
                scanning = False

        self.angle_increment = 180 / self.dc_files.__len__()        
            
        for idx in range(0, self.dc_files.__len__()):
            self.scan_collection.append(mapdat.TekData(''))
            self.scan_collection[-1].rf_filelist = self.rf_files[idx]
            self.scan_collection[-1].dc_filelist = self.dc_files[idx]
        return