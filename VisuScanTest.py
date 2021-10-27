'''
    VisuScan Test Harness
    Thomas Ales | Oct 2021

    For use with new data formatted scans.
'''

import VisuScan as vs

print('VisuScanCollection Data Test...\n\n')
test_object = vs.VisuScanCollection()
test_object.path_to_files = 'G:\\MURI\\WaveformsLoRes\\'
print('Data path set to: {0}\n'.format(test_object.path_to_files))
print('Attempting Directory Parse...\n')
test_object.parse_directory()
print('Found {0} angles'.format(
    test_object.rf_files.__len__()))

for idx, flist in enumerate(test_object.rf_files):
    print('Scan {0} has {1} files.'.format(
        idx, flist.__len__()
    ))

print('Angle increment set to {0} degrees.'.format(test_object.angle_increment))