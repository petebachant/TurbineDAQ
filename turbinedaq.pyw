# -*- coding: utf-8 -*-
"""
Created on Thu Aug 15 20:43:44 2013

@author: Pete

This is the turbineDAQ main code.

To-do:
  * Do some data acquisition in the ACS controller as well...
  
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
from scipy.io import savemat

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
        self.t = np.array([])
        self.time_last_run = time.time()
        
        # Some operating parameters
        self.monitorni = False
        self.monitorvec = False
        self.exp_running = False
        self.enabled_axes = {}
        
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
            try:
                self.settings = json.load(fn)
            except ValueError:
                self.settings = {}
        if "Last working directory" in self.settings:
            self.wdir = self.settings["Last working directory"]
            self.line_edit_wdir.setText(self.wdir)
        if "Last window location" in self.settings:
            self.move(QtCore.QPoint(self.settings["Last window location"][0],
                                    self.settings["Last window location"][1]))
            
        # See what files exist in what folders using last path
        self.read_done()

        # Create a timer
        self.timer = QtCore.QTimer()
        
        # Connect signals to slots
        self.connect_sigs_slots()
        
        # Start timer
        self.timer.start(200)
        
        # Connect to controller
        self.connect_to_controller()
        
        # Initialize plots
        self.initialize_plots()
        
        # Set single run visible in tab widget
        self.ui.tabWidgetMode.setCurrentWidget(self.ui.tabSingleRun)
        
    def read_done(self):
        """Look as subfolders to determine progress of experiment."""
        pass
        
    def connect_sigs_slots(self):
        """Connect signals to appropriate slots."""
        self.toolbutton_wdir.clicked.connect(self.on_tbutton_wdir)
        self.ui.actionQuit.triggered.connect(self.close)
        self.timer.timeout.connect(self.on_timer)
        self.ui.actionMonitor_Vectrino.triggered.connect(self.on_monitor_vec)
        self.ui.actionMonitor_NI.triggered.connect(self.on_monitor_ni)
        self.ui.actionStart.triggered.connect(self.on_start)
        self.ui.actionAbort.triggered.connect(self.on_abort)
        
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
        self.label_timer.setText("Time since last run: ")
        self.ui.statusbar.addWidget(self.label_timer)
        self.label_vecstatus = QLabel()
        self.label_vecstatus.setText("Vectrino disconnected ")
        self.ui.statusbar.addWidget(self.label_vecstatus)
    
    def connect_to_controller(self):
        self.hc = acsc.openCommEthernetTCP()    
        if self.hc == acsc.INVALID:
            print "Cannot connect to ACS controller"
            self.label_acs_connect.setText(" Not connected to ACS controller ")
            
    def initialize_plots(self):
        # Torque trans plot
        self.curve_torque_trans = guiqwt.curve.CurveItem()
        self.plot_torque = self.ui.plotTorque.get_plot()
        self.plot_torque.add_item(self.curve_torque_trans)
        # Drag plot
        self.curve_drag = guiqwt.curve.CurveItem()
        self.plot_drag = self.ui.plotDrag.get_plot()
        self.plot_drag.add_item(self.curve_drag)
        # Drag left plot
        self.curve_drag_left = guiqwt.curve.CurveItem()
        self.curve_drag_left.setPen(QtGui.QPen(QtCore.Qt.green, 1))
        self.plot_drag_left = self.ui.plotDragL.get_plot()
        self.plot_drag_left.add_item(self.curve_drag_left)
        # Drag right plot
        self.curve_drag_right = guiqwt.curve.CurveItem()
        self.curve_drag_right.setPen(QtGui.QPen(QtCore.Qt.red, 1))
        self.plot_drag_right = self.ui.plotDragR.get_plot()
        self.plot_drag_right.add_item(self.curve_drag_right)
        # NI turbine RPM plot
        self.curve_rpm_ni = guiqwt.curve.CurveItem()
        self.plot_rpm_ni = self.ui.plotRPM_ni.get_plot()
        self.plot_rpm_ni.add_item(self.curve_rpm_ni)
        # Vectrino u plot
        self.curve_vecu = guiqwt.curve.CurveItem()
        self.plot_vecu = self.ui.plotVecU.get_plot()
        self.plot_vecu.add_item(self.curve_vecu)
        # Vectrino v plot
        self.curve_vecv = guiqwt.curve.CurveItem()
        self.plot_vecv = self.ui.plotVecV.get_plot()
        self.plot_vecv.add_item(self.curve_vecv)
        # Vectrino w plot
        self.curve_vecw = guiqwt.curve.CurveItem()
        self.plot_vecw = self.ui.plotVecW.get_plot()
        self.plot_vecw.add_item(self.curve_vecw)
        # Vectrino correlation plot
        self.curve_vec_corr = guiqwt.curve.CurveItem()
        self.plot_vec_corr = self.ui.plotVecCorr.get_plot()
        self.plot_vec_corr.add_item(self.curve_vec_corr)
        # Vectrino SNR plot
        self.curve_vec_snr = guiqwt.curve.CurveItem()
        self.plot_vec_snr = self.ui.plotVecSNR.get_plot()
        self.plot_vec_snr.add_item(self.curve_vec_snr)
        # ACS plot
        # ACS plot
        # ACS plot
        # Add a panel
        
        
    def on_start(self):
        """Start whatever is visibile in the tab widget"""
        if self.ui.actionStart.isChecked():
            self.ui.actionStart.setIcon(QIcon(":icons/pause.png"))
            self.ui.actionStart.setToolTip("Stop after current run")
            self.ui.actionMonitor_NI.setChecked(False)
            self.ui.actionMonitor_Vectrino.setChecked(False)
            self.ui.toolBar_DAQ.setDisabled(True)
            self.ui.toolBar_directory.setDisabled(True)
            self.ui.tabWidgetMode.setDisabled(True)
            if self.ui.tabTestPlan.isVisible():
                """Continue working on test plan"""
                print "Test plan"
            elif self.ui.tabSingleRun.isVisible():
                """Do a single run"""
                U = self.ui.doubleSpinBox_singleRun_U.value()
                tsr = self.ui.doubleSpinBox_singleRun_tsr.value()
                y_R = self.ui.doubleSpinBox_singleRun_y_R.value()
                z_H = self.ui.doubleSpinBox_singleRun_z_H.value()
                self.do_turbine_tow(U, tsr, y_R, z_H)
            elif self.ui.tabTareDrag.isVisible():
                """Do tare drag runs"""
            elif self.ui.tabTareTorque.isVisible():
                """Do tare torque runs"""
            elif self.ui.tabProcessing.isVisible():
                """Process a run"""
        else:
            """Stop after current run completes"""
            print "Stopping after current run..."
            self.ui.actionStart.setIcon(QIcon(":icons/play.png"))
            self.ui.toolBar_DAQ.setEnabled(True)
            self.ui.toolBar_directory.setEnabled(True)
            self.ui.tabWidgetMode.setEnabled(True)
            
    def on_abort(self):
        if self.ui.actionStart.isChecked():
            self.ui.actionStart.trigger()
        self.ui.actionMonitor_NI.setChecked(False)
        self.ui.actionMonitor_Vectrino.setChecked(False)
        acsc.halt(self.hc, 0)
        acsc.halt(self.hc, 1)
        acsc.halt(self.hc, 4)
        acsc.halt(self.hc, 5)
        
    def do_turbine_tow(self, U, tsr, y_R, z_H):
        """Exectutes a single turbine tow"""
        print "Towing a turbine..."
        print U
        
    def on_monitor_ni(self):
        if self.ui.actionMonitor_NI.isChecked():
            self.daqthread = daqtasks.TurbineTowDAQ()
            self.daqthread.usetrigger = False
            self.nidata = self.daqthread.data
            self.daqthread.start()
            self.monitorni = True
        else:
            self.daqthread.clear()
            self.monitorni = False

    def on_monitor_vec(self):
        if self.ui.actionMonitor_Vectrino.isChecked():
            self.vecthread = vectasks.VectrinoThread()
            self.vecdata = self.vecthread.vec.data
            self.vecthread.record = False
            self.vecthread.savepath = self.wdir
            self.vecthread.usetrigger = False
            self.vecthread.start()
            self.monitorvec = True
        else:
            self.vecthread.stop()
            print self.vecthread.vec.get_vel_range()
            self.monitorvec = False
        
    def on_timer(self):
        self.update_acs()
        self.time_since_last_run = time.time() - self.time_last_run
        self.label_timer.setText("Time since last run: " + \
        str(int(self.time_since_last_run)) + " s ")
        
        if self.monitorvec or self.exp_running:
            self.update_plots_vec()
            self.label_vecstatus.setText(self.vecthread.vecstatus)
        if self.monitorni or self.exp_running:
            self.update_plots_ni()
    
    def update_plots_ni(self):
        self.curve_drag.set_data(self.nidata["t"], self.nidata["drag_left"])
        self.plot_drag.replot()
        self.curve_torque_trans.set_data(self.nidata["t"],
                                         self.nidata["torque_trans"])
        self.plot_torque.replot()
        
    def update_plots_vec(self):
        """This function updates the Vectrino plots."""
        self.curve_vecu.set_data(self.vecdata["t"], self.vecdata["u"])
        self.plot_vecu.replot()
        self.curve_vecv.set_data(self.vecdata["t"], self.vecdata["v"])
        self.plot_vecv.replot()
        self.curve_vecw.set_data(self.vecdata["t"], self.vecdata["w"])
        self.plot_vecw.replot()
    
    def update_acs(self):
        """This function updates all the ACS controller data"""
        if acsc.getMotorState(self.hc, 0) == "disabled":
            self.enabled_axes["y"] = False 
    
    def closeEvent(self, event):
        self.settings["Last window location"] = [self.pos().x(), 
                                                 self.pos().y()]
        with open("settings/settings.json", "w") as fn:
            json.dump(self.settings, fn)
        acsc.closeComm(self.hc)


def main():
    import sys
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()