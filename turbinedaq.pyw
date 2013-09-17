# -*- coding: utf-8 -*-
"""
Created on Thu Aug 15 20:43:44 2013

@author: Pete

This is the turbineDAQ main code.

"""

from __future__ import division
from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import *
import PyQt4.Qwt5 as Qwt
import numpy as np
from acspy import acsc
import daqtasks
import vectasks
import runtypes
from mainwindow import *
import json
import guiqwt
import time

# Some global constants
simulator = True

# Log run metadata as JSON
# Move Vectrino first?
# Start Vectrino and wait for it to enter data collection mode
# Start NI waiting for a trigger pulse
# Start ACS program

    
class MainWindow(QtGui.QMainWindow):
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Create time vector
        self.tvec = np.array([])
        self.tstart = time.time()
        
        # Add file path combobox to toolbar
        self.line_edit_wdir = QtGui.QLineEdit()
        self.ui.toolBar_directory.addWidget(self.line_edit_wdir)
        self.wdir = "C:\temp"
        self.line_edit_wdir.setText("C:\\temp")
        self.toolbutton_wdir = QtGui.QToolButton()
        self.ui.toolBar_directory.addWidget(self.toolbutton_wdir)
        self.toolbutton_wdir.setIcon(QtGui.QIcon(":icons/folder_yellow.png"))
        
        # Add labels to status bar
        self.add_labels_to_statusbar()
        
        # Read in metadata from previous session, i.e. last working directory
        with open("settings/settings.json", "r") as fn:
            self.settings = json.load(fn)
        if "Last working directory" in self.settings:
            self.wdir = self.settings["Last working directory"]
            self.line_edit_wdir.setText(self.wdir)
            
        # See what files exist in what folders using last path
        self.read_done()

        # Create a time
        self.timer = QtCore.QTimer()
        
        # Connect signals to slots
        self.connect_sigs_slots()
        
        # Start timer
        self.timer.start(100)
        
        # Connect to controller
        self.connect_to_controller()
        
        # Initialize plots
        self.initialize_plots()
        
    def read_done(self):
        """Look as subfolders to determine progress of experiment."""
        pass
        
    def connect_sigs_slots(self):
        """Connect signals to appropriate slots."""
        self.toolbutton_wdir.clicked.connect(self.on_tbutton_wdir)
        self.ui.actionQuit.triggered.connect(self.close)
        self.timer.timeout.connect(self.on_timer)
        
    def on_tbutton_wdir(self):
        self.wdir = QFileDialog.getExistingDirectory()
        if self.wdir:
            self.line_edit_wdir.setText(self.wdir)
        self.wdir = str(self.line_edit_wdir.text())
        self.settings["Last working directory"] = self.wdir
        
    def add_labels_to_statusbar(self):
        self.label_acs_connect = QLabel()
        self.ui.statusbar.addWidget(self.label_acs_connect)
        self.label_timer = QLabel()
        self.label_timer.setText(" Time since last run: ")
        self.ui.statusbar.addWidget(self.label_timer)
    
    def connect_to_controller(self):
        self.hc = acsc.openCommEthernetTCP()    
        if self.hc == acsc.INVALID:
            print "Cannot connect to controller"
            self.label_acs_connect.setText(" Not connected ")
            
    def initialize_plots(self):
        self.curve_drag = guiqwt.curve.CurveItem()
        self.curve_drag.setPen(QtGui.QPen(QtCore.Qt.red, 1.5))
        self.curve_dragL = guiqwt.curve.CurveItem()
        self.plotDrag = self.ui.plotDrag.get_plot()
        self.plotDrag.add_item(self.curve_drag)
            
    def makelatex(self):
        """Example from online. Doesn't work."""
        # Get window background color
        bg = self.palette().window().color()
        cl = (bg.redF(), bg.greenF(), bg.blueF())
    
        # Create figure, using window bg color
        self.fig = plt.Figure(edgecolor=cl, facecolor=cl)
    
        # Add FigureCanvasQTAgg widget to form
        self.canvas = plt.FigureCanvasQTAgg(self.fig)        
        self.tex_label_placeholder.layout().addWidget(self.canvas)
    
        # Clear figure
        self.fig.clear()
    
        # Set figure title
        self.fig.suptitle('$TeX$',
                          x=0.0, y=0.5, 
                          horizontalalignment='left',
                          verticalalignment='center')
        self.canvas.draw()        
            
    def connect_to_vectrino(self):
        """Connects to Vectrino."""
        
    def on_timer(self):
        self.update_acs()
        self.update_plots_ni()
        self.tvec = np.append(self.tvec, time.time() - self.tstart)
        self.curve_drag.set_data(self.tvec, (self.tvec)**2)
    
    def update_plots_ni(self):
        self.plotDrag.replot()
    
    def update_acs(self):
        """This function updates all the ACS controller data"""
        pass
    
    def closeEvent(self, event):
        with open("settings/settings.json", "w") as fn:
            json.dump(self.settings, fn)


def main():
    import sys
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()