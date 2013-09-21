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
import xlrd
import os
import re

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
        self.test_plan_data = {}
        
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
        
        # Import test plan
        self.import_test_plan()
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
        
    def is_run_done(self, section, number):
        """Look as subfolders to determine progress of experiment."""
        if "Perf" in section:
            subdir = self.wdir + "/Performance/" + section[-5:]
            runpath = subdir + "/" + str(number)
        elif "Wake" in section:
            subdir = self.wdir + "/Wake/" + section[-5:]
            runpath = subdir + "/" + str(number)
        elif section == "Tare Drag":
            runpath = self.wdir + "/Tare Drag/" + str(number)
        else: runpath = ""
        if os.path.isdir(runpath):
            return True
        else:
            return False
    
    def is_section_done(self, section):
        pass
    
    def import_test_plan(self):
        """Imports test plan from Excel spreadsheet in working directory"""
        test_plan_found = False
        for item in os.listdir(self.wdir):
            if "Test plan" in item or "Test Plan" in item:
                wb = xlrd.open_workbook(self.wdir + "/" + item)
                test_plan_found = True
        if test_plan_found:
            # Set combobox items to reflect sheet names
            self.ui.comboBox_testPlanSection.clear()
            self.test_plan_sections = wb.sheet_names()
            self.ui.comboBox_testPlanSection.addItems(QtCore.QStringList(self.test_plan_sections))
            # Pull data from each sheet
            for sheetname in self.test_plan_sections:
                self.test_plan_data[sheetname] = {}
                self.test_plan_data[sheetname]["Parameter list"] = []
                ws = wb.sheet_by_name(sheetname)
                for column in range(ws.ncols):
                    colname = ws.cell(0,column).value
                    if colname != "Notes":
                        self.test_plan_data[sheetname]["Parameter list"].append(colname) 
                        self.test_plan_data[sheetname][colname] = ws.col_values(column)[1:]
                    if colname == "Run":
                        for run in self.test_plan_data[sheetname][colname]:
                            if run != "":
                                run = int(run)
            self.test_plan_into_table()
        else:
            print "No test plan found in working directory"
            
    def test_plan_into_table(self):
        """Takes test plan values and puts them in table widget"""
        section = str(self.ui.comboBox_testPlanSection.currentText())
        paramlist = self.test_plan_data[section]["Parameter list"]
        self.ui.tableWidgetTestPlan.setColumnCount(len(paramlist)+1)
        self.ui.tableWidgetTestPlan.setHorizontalHeaderLabels(
                QtCore.QStringList(paramlist+["Done?"]))
        self.ui.tableWidgetTestPlan.setRowCount(
                len(self.test_plan_data[section][paramlist[0]]))
        for i in range(len(paramlist)):
            itemlist = self.test_plan_data[section][paramlist[i]]
            for n in range(len(itemlist)):
                self.ui.tableWidgetTestPlan.setItem(n, i, 
                            QtGui.QTableWidgetItem(str(itemlist[n])))
                # Check if run is done
                isdone = self.is_run_done(section, n)
                if isdone:
                    self.ui.tableWidgetTestPlan.setItem(n, i+1,
                            QtGui.QTableWidgetItem("Yes"))
                    self.ui.tableWidgetTestPlan.item(n, i+1).setBackgroundColor(QtCore.Qt.green)
                else:
                    self.ui.tableWidgetTestPlan.setItem(n, i+1,
                            QtGui.QTableWidgetItem("No"))
                    self.ui.tableWidgetTestPlan.item(n, i+1).setBackgroundColor(QtCore.Qt.red)
        
    def connect_sigs_slots(self):
        """Connect signals to appropriate slots."""
        self.toolbutton_wdir.clicked.connect(self.on_tbutton_wdir)
        self.ui.actionQuit.triggered.connect(self.close)
        self.timer.timeout.connect(self.on_timer)
        self.ui.actionMonitor_Vectrino.triggered.connect(self.on_monitor_vec)
        self.ui.actionMonitor_NI.triggered.connect(self.on_monitor_ni)
        self.ui.actionStart.triggered.connect(self.on_start)
        self.ui.actionAbort.triggered.connect(self.on_abort)
        self.ui.actionImportTestPlan.triggered.connect(self.import_test_plan)
        self.ui.comboBox_testPlanSection.currentIndexChanged.connect(self.test_plan_into_table)
        self.ui.tabWidgetMode.currentChanged.connect(self.on_tab_change)
        self.ui.comboBox_testPlanSection.currentIndexChanged.connect(self.on_section_change)
        
    def on_tbutton_wdir(self):
        self.wdir = QFileDialog.getExistingDirectory()
        if self.wdir:
            self.line_edit_wdir.setText(self.wdir)
        self.wdir = str(self.line_edit_wdir.text())
        self.settings["Last working directory"] = self.wdir
    
    def on_tab_change(self):
        tabindex = self.ui.tabWidgetMode.currentIndex()
        tabitem = self.ui.tabWidgetMode.tabText(tabindex)
        section = self.ui.comboBox_testPlanSection.currentText()
        if tabitem == "Test Plan" and section == "Top Level":
            self.ui.actionStart.setDisabled(True)
        else:
            self.ui.actionStart.setEnabled(True)
            
    def on_section_change(self):
        section = self.ui.comboBox_testPlanSection.currentText()
        if section == "Top Level":
            self.ui.actionStart.setDisabled(True)
        else:
            self.ui.actionStart.setEnabled(True)
        self.test_plan_into_table()
        
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
            print "Cannot connect to ACS controller. Attempting to connect to simulator..."
            self.label_acs_connect.setText(" Not connected to ACS controller ")
            self.hc = acsc.openCommDirect()
            if self.hc == acsc.INVALID:
                print "Cannot connect to simulator"
            else:
                self.label_acs_connect.setText(" Connected to SPiiPlus simulator ")
            
    def initialize_plots(self):
        # Torque trans plot
        self.curve_torque_trans = guiqwt.curve.CurveItem()
        self.plot_torque = self.ui.plotTorque.get_plot()
        self.plot_torque.add_item(self.curve_torque_trans)
        # Torque arm plot
        self.curve_torque_arm = guiqwt.curve.CurveItem()
        self.curve_torque_arm.setPen(QtGui.QPen(QtCore.Qt.red, 1))
        self.plot_torque.add_item(self.curve_torque_arm)
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
                print "Continuing test plan..."
                self.do_test_plan()
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
        """Abort current run and delete all data"""
        if self.ui.actionStart.isChecked():
            self.ui.actionStart.setChecked(False)
            print "Aborting current run..."
        self.ui.actionMonitor_NI.setChecked(False)
        self.ui.actionMonitor_Vectrino.setChecked(False)
        self.ui.actionStart.setIcon(QIcon(":icons/play.png"))
        self.ui.toolBar_DAQ.setEnabled(True)
        self.ui.toolBar_directory.setEnabled(True)
        self.ui.tabWidgetMode.setEnabled(True)
        acsc.halt(self.hc, 0)
        acsc.halt(self.hc, 1)
        acsc.halt(self.hc, 4)
        acsc.halt(self.hc, 5)
        
    def do_turbine_tow(self, U, tsr, y_R, z_H):
        """Exectutes a single turbine tow"""
        print "Executing a turbine tow..."
        print "U =", U, "TSR =", tsr, "y/R =", y_R, "z/H =", z_H
        self.turbinetow = runtypes.TurbineTow(self.hc, U, tsr, y_R, z_H, 
                                              nidaq=False, vectrino=False)
        self.turbinetow.towfinished.connect(self.on_tow_finished)
        self.turbinetow.start()
        # First step is to 
        
    def on_tow_finished(self):
        """Current tow complete."""
        # Reset time of last run
        self.time_last_run = time.time()
        self.test_plan_into_table()
        # If executing a test plan start a single shot timer for next run
        if self.ui.tabTestPlan.isVisible() and self.ui.actionStart.isChecked():
            idlesec = 5
            QtCore.QTimer.singleShot(idlesec*1000, self.on_idletimer)
        else: 
            self.ui.actionStart.trigger()
        
    def on_idletimer(self):
        self.do_test_plan()
        
    def do_test_plan(self):
        """Continue test plan"""
        section = self.ui.comboBox_testPlanSection.currentText()
        print "Continuing", section+"..."
        # Find next run to do by looking in the Done? column
        nruns = self.ui.tableWidgetTestPlan.rowCount()
        donecol = self.ui.tableWidgetTestPlan.columnCount()-1
        for n in range(nruns):
            doneval = self.ui.tableWidgetTestPlan.item(n, donecol).text()
            if doneval == "No":
                nextrun = int(float(self.ui.tableWidgetTestPlan.item(n, 0).text()))
                break
        print "Starting run", str(nextrun) + "..."
        if "Perf" in section or "Wake" in section:
            U = float(self.ui.tableWidgetTestPlan.item(nextrun, 1).text())
            tsr = float(self.ui.tableWidgetTestPlan.item(nextrun, 2).text())
            y_R = float(self.ui.tableWidgetTestPlan.item(nextrun, 3).text())
            z_H = float(self.ui.tableWidgetTestPlan.item(nextrun, 4).text())
            self.do_turbine_tow(U, tsr, y_R, z_H)
        
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
        t = self.nidata["t"]
        self.curve_drag_left.set_data(t, self.nidata["drag_left"])
        self.plot_drag_left.replot()
        self.curve_torque_trans.set_data(t, self.nidata["torque_trans"])
        self.curve_torque_arm.set_data(t, self.nidata["torque_arm"])        
        self.plot_torque.replot()
        self.curve_drag_right.set_data(t, self.nidata["drag_right"])
        self.plot_drag_right.replot()
        self.curve_drag.set_data(t, self.nidata["drag_left"]+self.nidata["drag_right"])
        self.plot_drag.replot()
        self.curve_rpm_ni.set_data(t, self.nidata["turbine_rpm"])
        self.plot_rpm_ni.replot()
        
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
        if self.monitorni:
            self.daqthread.clear()


def main():
    import sys
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()