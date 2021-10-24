'''
    Visu 2.0-a
    Thomas K Ales

    VISU with support for 'new data' format.
'''
from PyQt5 import QtWidgets, uic

import sys

ui_file = './visu.ui'

class Ui(QtWidgets.QMainWindow):

    def __init__(self) -> None:
        super(Ui, self).__init__()
        uic.loadUi(ui_file, self)
        self.show()



if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Ui()
    app.exec_()