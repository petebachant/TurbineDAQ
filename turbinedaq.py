# -*- coding: utf-8 -*-
"""
Created on Thu Aug 15 20:43:44 2013
@author: Pete Bachant

This is the TurbineDAQ main code.

To-do:
  * After "pausing" need some way to know a run is done to enable controls
    rather than enabling them right away
  * Add last couple of working directories to a dropdown list in directory
    selection box
  * Calculate statistics of various quantities during the run, including
    C_P. Use a window of 3 seconds maybe.
  * Make Vectrino stop thread
  * Can't tell if a section is done
  * Detect if Vec is saving to AQD, not VNO, then abort
  * At end of section, set run button unchecked
  * Change icon to top view of turbine
  * Refresh button on test plan tab
  * Allow scrolling while test plan is running
    Looks like this will involve enabling the table widget, then making it
    look disabled. 
  * Abort does weird things if pressed too early in a run
  * Highlight run in progress in table
  * Should check if tow and turbine axes are enabled in order to start a run,
    since they aren't enabled in the motion programs.
  * Autoprocess functionality for processing last run.
  * Checkboxes for enabling and disabling axes.
  * Scroll to latest run that isn't done on opening test plan.
  * Catch exceptions for autoprocessing so next run can begin. 
  * Run numbers per section must start from zero or else things go wacky. 
  * Doesn't end if section is done. 
"""

from __future__ import division, print_function
from PyQt4 import QtCore, QtGui
from PyQt4.QtGui import *
import numpy as np
from acspy import acsc
from modules import daqtasks
from modules import vectasks
from modules import runtypes
from modules.mainwindow import *
import json
import guiqwt
import time
from scipy.io import savemat
import xlrd
import os
import platform
import subprocess
from pxl import timeseries as ts
import shutil
import pandas as pd

                  
fluid_params = {"rho" : 1000.0}


class MainWindow(QtGui.QMainWindow):
    badvecdata = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        QtGui.QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Create time vector
        self.t = np.array([])
        self.time_last_run = time.time()
        
        # Some operating parameters
        self.plot_len_sec = 30.0
        self.monitoracs = False
        self.monitorni = False
        self.monitorvec = False
        self.monitorfbg = False
        self.exp_running = False
        self.towinprogress = False
        self.test_plan_loaded = False
        self.autoprocess = True
        self.enabled_axes = {}
        self.test_plan = {}
        
        # Add file path combobox to toolbar
        self.line_edit_wdir = QtGui.QLineEdit()
        self.ui.toolBar_directory.addWidget(self.line_edit_wdir)
        self.wdir = "C:\\temp"
        self.line_edit_wdir.setText("C:\\temp")
        self.toolbutton_wdir = QtGui.QToolButton()
        self.ui.toolBar_directory.addWidget(self.toolbutton_wdir)
        self.toolbutton_wdir.setIcon(QtGui.QIcon(":icons/folder_yellow.png"))
        
        # Add labels to status bar
        self.add_labels_to_statusbar()
        # Read in and apply settings from last session
        self.load_settings()
        # Create timers
        self.timer = QtCore.QTimer()
        self.plot_timer = QtCore.QTimer()
        # Connect to controller
        self.connect_to_controller()
        # Initialize plots
        self.initialize_plots()
        # Import test plan
        self.import_test_plan()
        # Read turbine and fbg properties
        self.read_turbine_properties()
        self.read_fbg_properties()
        # Connect signals and slots
        self.connect_sigs_slots()
        # Set test plan visible in tab widget
        self.ui.tabWidgetMode.setCurrentWidget(self.ui.tabTestPlan)
        if "Last section" in self.settings:
            self.ui.comboBox_testPlanSection.setCurrentIndex(self.settings["Last section"])
        # Start timers
        self.timer.start(200)
        self.plot_timer.start(10)
        # Remember FBG dock widget visibility from last session
        if "FBG visible" in self.settings:
            self.ui.dockWidget_FBG.setVisible(self.settings["FBG visible"])
            self.ui.actionFBG.setChecked(self.settings["FBG visible"])
        else:
            self.ui.dockWidget_FBG.close()
            self.ui.actionFBG.setChecked(False)
        # Remember Vectrino dock widget visibility from last session
        if "Vectrino visible" in self.settings:
            self.ui.dockWidgetVectrino.setVisible(self.settings["Vectrino visible"])
            self.ui.actionVectrino_View.setChecked(self.settings["Vectrino visible"])
        
    def load_settings(self):
        """Loads settings"""
        self.pcid = platform.node()
        try:
            with open("settings/settings.json", "r") as fn:
                self.settings = json.load(fn)
        except FileNotFoundError:
            self.settings = {}
        if "Last PC name" in self.settings:
            if self.settings["Last PC name"] == self.pcid:
                if "Last working directory" in self.settings:
                    if os.path.isdir(self.settings["Last working directory"]):
                        self.wdir = self.settings["Last working directory"]
                        self.line_edit_wdir.setText(self.wdir)
                if "Last window location" in self.settings:
                    self.move(QtCore.QPoint(self.settings["Last window location"][0],
                                            self.settings["Last window location"][1]))
        if "Last size" in self.settings:
            oldheight = self.settings["Last size"][0]
            oldwidth = self.settings["Last size"][1]
            self.resize(oldwidth, oldheight)
            
    def read_turbine_properties(self):
        """Reads turbine properties from `Config/turbine_properties.json` in 
        the experiment's working directory."""
        fpath = os.path.join(self.wdir, "Config", "turbine_properties.json")
        try:
            with open(fpath) as f:
                self.turbine_properties = json.load(f)
            print("Turbine properties loaded")
        except IOError:
            print("No turbine properties file found")
            self.turbine_properties = {"RVAT" : {"radius" : 0.5,
                                                 "height" : 1.0}}
                                                 
    def read_fbg_properties(self):
        fpath = os.path.join(self.wdir, "Config", "fbg_properties.json")
        try:
            with open(fpath) as f:
                self.fbg_properties = json.load(f)
            print("FBG properties loaded")
        except IOError:
            self.fbg_properties = {}
        
    def is_run_done(self, section, number):
        """Look as subfolders to determine progress of experiment."""
        runpath = os.path.join(self.wdir, "Data", "Raw", section, str(number))
        if os.path.isdir(runpath) and "metadata.json" in os.listdir(runpath):
            return True
        else:
            return False
    
    def is_section_done(self, section):
        """Currently does not work."""
        return False
    
    def import_test_plan(self):
        """Imports test plan from CSVs in "Test plan" subdirectory"""
        tpdir = os.path.join(self.wdir, "Config", "Test plan")
        self.test_plan_loaded = False
        self.test_plan = {}
        self.test_plan_sections = []
        if os.path.isdir(tpdir):
            test_plan_files = os.listdir(os.path.join(tpdir))
            for f in test_plan_files:
                if ".csv" in f:
                    self.test_plan[f.replace(".csv","")] \
                    = pd.read_csv(os.path.join(tpdir, f))
                    self.test_plan_sections.append(f.replace(".csv",""))
        if not self.test_plan:
            """Clear everything from table widget. Doesn't work right now."""
            self.ui.tableWidgetTestPlan.clearContents()
            print("No test plan found in working directory")
        else:
            # Set combobox items to reflect test plan sections
            self.ui.comboBox_testPlanSection.clear()
            self.ui.comboBox_process_section.clear()
            self.ui.comboBox_testPlanSection.addItems(self.test_plan_sections)
            self.ui.comboBox_process_section.addItem("Shakedown")
            self.ui.comboBox_process_section.addItems(self.test_plan_sections)
            self.test_plan_loaded = True
            print("Test plan loaded")
            self.test_plan_into_table()
         
    def test_plan_into_table(self):
        """Takes test plan values and puts them in table widget"""
        section = str(self.ui.comboBox_testPlanSection.currentText())
        if section in self.test_plan:
            paramlist = list(self.test_plan[section].columns)
            self.ui.tableWidgetTestPlan.setColumnCount(len(paramlist)+1)
            self.ui.tableWidgetTestPlan.setHorizontalHeaderLabels(paramlist+["Done?"])       
            self.ui.tableWidgetTestPlan.setRowCount(
                    len(self.test_plan[section][paramlist[0]]))
            for i in range(len(paramlist)):
                itemlist = self.test_plan[section][paramlist[i]]
                for n in range(len(itemlist)):
                    self.ui.tableWidgetTestPlan.setItem(n, i, 
                                QtGui.QTableWidgetItem(str(itemlist[n])))
                    # Check if run is done
                    if str(section).lower() != "top level":
                        isdone = self.is_run_done(section, n)
                        if isdone:
                            self.ui.tableWidgetTestPlan.setItem(n, i+1,
                                    QtGui.QTableWidgetItem("Yes"))
                            for j in range(i+2):
                                self.ui.tableWidgetTestPlan.item(n, j).\
                                        setTextColor(QtCore.Qt.darkGreen)
                                self.ui.tableWidgetTestPlan.item(n, j).\
                                        setBackgroundColor(QtCore.Qt.lightGray)                                    
                        else:
                            self.ui.tableWidgetTestPlan.setItem(n, i+1,
                                    QtGui.QTableWidgetItem("No"))
                    elif str(section).lower() == "top level":
                        self.update_sections_done()
                                    
    def update_sections_done(self):
        for n in range(self.ui.tableWidgetTestPlan.rowCount()):
#            section_type = str(self.ui.tableWidgetTestPlan.item(n, 0).text())
#            section_u = str(self.ui.tableWidgetTestPlan.item(n, 0).text())
#            print section_u
#            section = section_type + "-" + section_u
#            isdone = self.is_section_done(section)
#            print section
            isdone = None
            if isdone:
                text = QtGui.QTableWidgetItem("Yes")
            elif isdone == None:
                text = QtGui.QTableWidgetItem("Maybe")
            else:
                text = QtGui.QTableWidgetItem("No")
            self.ui.tableWidgetTestPlan.setItem(n+1, -1, text)
        
    def connect_sigs_slots(self):
        """Connect signals to appropriate slots."""
        self.toolbutton_wdir.clicked.connect(self.on_tbutton_wdir)
        self.ui.actionQuit.triggered.connect(self.close)
        self.timer.timeout.connect(self.on_timer)
        self.plot_timer.timeout.connect(self.on_plot_timer)
        self.ui.actionMonitor_Vectrino.triggered.connect(self.on_monitor_vec)
        self.ui.actionMonitor_NI.triggered.connect(self.on_monitor_ni)
        self.ui.actionMonitor_FBG.triggered.connect(self.on_monitor_fbg)
        self.ui.actionStart.triggered.connect(self.on_start)
        self.ui.actionAbort.triggered.connect(self.on_abort)
        self.ui.actionImportTestPlan.triggered.connect(self.import_test_plan)
        self.ui.comboBox_testPlanSection.currentIndexChanged.connect(self.test_plan_into_table)
        self.ui.tabWidgetMode.currentChanged.connect(self.on_tab_change)
        self.ui.comboBox_testPlanSection.currentIndexChanged.connect(self.on_section_change)
        self.ui.actionMonitor_ACS.triggered.connect(self.on_monitor_acs)
        self.ui.toolButtonOpenSection.clicked.connect(self.on_open_section_folder)
        self.ui.actionHome_Tow.triggered.connect(self.on_home_tow)
        self.ui.toolButtonOpenShakedown.clicked.connect(self.on_open_shakedown)
        self.ui.actionHome_Turbine.triggered.connect(self.on_home_turbine)
        self.ui.actionHome_y.triggered.connect(self.on_home_y)
        self.ui.actionHome_z.triggered.connect(self.on_home_z)
        self.ui.commandLinkButton_process.clicked.connect(self.on_process)
        self.badvecdata.connect(self.on_badvecdata)
        
    def on_tbutton_wdir(self):
        self.wdir = QFileDialog.getExistingDirectory()
        if self.wdir:
            self.line_edit_wdir.setText(self.wdir)
        self.wdir = str(self.line_edit_wdir.text())
        self.settings["Last working directory"] = self.wdir
        self.import_test_plan()
    
    def on_tab_change(self):
        tabindex = self.ui.tabWidgetMode.currentIndex()
        tabitem = self.ui.tabWidgetMode.tabText(tabindex)
        section = self.ui.comboBox_testPlanSection.currentText()
        if tabitem == "Test Plan" and str(section).lower() == "top level":
            self.ui.actionStart.setDisabled(True)
        else:
            self.ui.actionStart.setEnabled(True)
        if tabitem == "Processing":
            savedir = os.path.join(self.wdir, "Data", "Raw", "Shakedown")
            runsdone = sorted([int(n) for n in os.listdir(savedir)])
            runsdone = [str(n) for n in runsdone]
            self.ui.comboBox_process_nrun.clear()
            self.ui.comboBox_process_nrun.addItems(runsdone)
    
    def on_home_tow(self):
        acsc.runBuffer(self.hc, 2)
    
    def on_home_turbine(self):
        acsc.runBuffer(self.hc, 8)
        
    def on_home_y(self):
        acsc.runBuffer(self.hc, 12)
        
    def on_home_z(self):
        acsc.runBuffer(self.hc, 11)
    
    def on_open_section_folder(self):
        section = str(self.ui.comboBox_testPlanSection.currentText())
        subdir = os.path.join(self.wdir, "Data", "Raw", section)
        try:
            os.startfile(subdir)
        except WindowsError:
            os.makedirs(subdir)
            os.startfile(subdir)
        
    def on_open_shakedown(self):
        subdir = os.path.join(self.wdir, "Data", "Raw", "Shakedown")
        try:
            os.startfile(subdir)
        except WindowsError:
            os.makedirs(subdir)
            os.startfile(subdir)
            
    def on_section_change(self):
        section = self.ui.comboBox_testPlanSection.currentText()
        if str(section).lower() == "top level":
            self.ui.actionStart.setDisabled(True)
            self.update_sections_done()
        else:
            self.ui.actionStart.setEnabled(True)
        if section in self.test_plan:
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
        self.label_runstatus = QLabel()
        self.label_runstatus.setText("Not running ")
        self.ui.statusbar.addWidget(self.label_runstatus)
    
    def connect_to_controller(self):
        self.hc = acsc.openCommEthernetTCP()    
        if self.hc == acsc.INVALID:
            print("Cannot connect to ACS controller. Attempting to connect to simulator...")
            self.label_acs_connect.setText(" Not connected to ACS controller ")
            self.hc = acsc.openCommDirect()
            if self.hc == acsc.INVALID:
                print("Cannot connect to simulator")
            else:
                print("Connected to simulator")
                self.label_acs_connect.setText(" Connected to SPiiPlus simulator ")
        else:
            self.label_acs_connect.setText(" Connected to ACS controller ")
            
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
        self.curve_drag_left.setPen(QtGui.QPen(QtCore.Qt.darkGreen, 1))
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
        # ACS carriage speed plot
        self.curve_acs_carvel = guiqwt.curve.CurveItem()
        self.plot_acs_carvel = self.ui.plotTowSpeed.get_plot()
        self.plot_acs_carvel.add_item(self.curve_acs_carvel)
        # ACS turbine RPM plot
        self.curve_acs_rpm = guiqwt.curve.CurveItem()
        self.plot_acs_rpm = self.ui.plotRPM_acs.get_plot()
        self.plot_acs_rpm.add_item(self.curve_acs_rpm)
        # FBG plot 1
        self.curve_fbg_1 = guiqwt.curve.CurveItem()
        self.plot_fbg_1 = self.ui.plot_FBG_1.get_plot()
        self.plot_fbg_1.add_item(self.curve_fbg_1)
        # FBG plot 2
        self.curve_fbg_2 = guiqwt.curve.CurveItem()
        self.plot_fbg_2 = self.ui.plot_FBG_2.get_plot()
        self.plot_fbg_2.add_item(self.curve_fbg_2)
        
    def on_start(self):
        """Start whatever is visible in the tab widget."""
        self.abort = False
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
                if self.ui.comboBox_testPlanSection.currentText() != "Top Level":
                    self.do_test_plan()
            elif self.ui.tabSingleRun.isVisible():
                """Do a single run"""
                U = self.ui.doubleSpinBox_singleRun_U.value()
                tsr = self.ui.doubleSpinBox_singleRun_tsr.value()
                radius = self.ui.doubleSpinBox_turbineRadius.value()
                height = self.ui.doubleSpinBox_turbineHeight.value()
                self.turbine_properties["shakedown"] = {}
                self.turbine_properties["shakedown"]["radius"] = radius
                self.turbine_properties["shakedown"]["height"] = height
                y_R = self.ui.doubleSpinBox_singleRun_y_R.value()
                z_H = self.ui.doubleSpinBox_singleRun_z_H.value()
                vectrino = self.ui.checkBox_singleRunVectrino.isChecked()
                fbg = self.ui.checkBox_singleRunFBG.isChecked()
                self.savedir = os.path.join(self.wdir, "Data", "Raw", "Shakedown")
                if not os.path.isdir(self.savedir):
                    os.makedirs(self.savedir)
                runsdone = os.listdir(self.savedir)
                if len(runsdone) == 0:
                    self.currentrun = 0
                else:
                    self.currentrun = np.max([int(run) for run in runsdone])+1
                self.currentname = "Shakedown run " + str(self.currentrun)
                self.label_runstatus.setText(self.currentname + " in progress ")
                self.savesubdir = os.path.join(self.savedir, str(self.currentrun))
                os.mkdir(self.savesubdir)
                self.do_turbine_tow(U, tsr, y_R, z_H, turbine="shakedown",
                                    vectrino=vectrino, fbg=fbg)
            elif self.ui.tabTareDrag.isVisible():
                """Do tare drag runs"""
            elif self.ui.tabTareTorque.isVisible():
                """Do tare torque runs"""
            elif self.ui.tabProcessing.isVisible():
                """Process a run"""
        else:
            """Stop after current run completes"""
            self.ui.actionStart.setIcon(QIcon(":icons/play.png"))
            self.ui.toolBar_DAQ.setEnabled(True)
            self.ui.toolBar_directory.setEnabled(True)
            self.ui.tabWidgetMode.setEnabled(True)
            
    def on_abort(self):
        """Abort current run and don't save data, but ask whether or not to
        delete folder created."""
        self.abort = True
        self.monitorni = False
        self.monitoracs = False
        self.monitorvec = False
        if self.ui.actionStart.isChecked():
            self.ui.actionStart.setChecked(False)
            print("Aborting current run...")
            text = str(self.label_runstatus.text())
            self.label_runstatus.setText(text[:-13] + " aborted ")
        if self.ui.actionMonitor_ACS.isChecked():
            self.ui.actionMonitor_ACS.setChecked(False)
            self.acsthread.stop()
        if self.ui.actionMonitor_NI.isChecked():
            self.ui.actionMonitor_NI.setChecked(False)
            self.daqthread.stopdaq()
        if self.ui.actionMonitor_Vectrino.isChecked():
            self.ui.actionMonitor_Vectrino.setChecked(False)
            self.vecthread.stop()
        self.ui.actionStart.setIcon(QIcon(":icons/play.png"))
        self.ui.toolBar_DAQ.setEnabled(True)
        self.ui.toolBar_directory.setEnabled(True)
        self.ui.tabWidgetMode.setEnabled(True)
        try:
            if self.turbinetow.isRunning():
                self.turbinetow.abort()
        except AttributeError:
            pass
        try:
            if self.tarerun.isRunning():
                self.tarerun.abort()
        except AttributeError:
            pass
        self.towinprogress = False
        
    def auto_abort(self):
        """Abort run, don't save data, and automatically delete any files
        or folders generated. Also will move turbine and tow axes back
        to zero."""
        self.abort = True
        self.monitorni = False
        self.monitoracs = False
        self.monitorvec = False
        self.monitorfbg = False
        print("Automatically aborting current run...")
        text = str(self.label_runstatus.text())
        self.label_runstatus.setText(text[:-13] + " autoaborted ")
        self.turbinetow.autoabort()
        self.towinprogress = False

    def on_badvecdata(self):
        print("Bad Vectrino data detected")
        self.auto_abort()
        
    def do_turbine_tow(self, U, tsr, y_R, z_H, turbine="RVAT", 
                       vectrino=True, fbg=False):
        """Exectutes a single turbine tow"""
        if acsc.getMotorState(self.hc, 5)["enabled"]:
            self.abort = False
            vecsavepath = os.path.join(self.savesubdir, "vecdata")
            radius = self.turbine_properties[turbine]["radius"]
            height = self.turbine_properties[turbine]["height"]
            self.turbinetow = runtypes.TurbineTow(self.hc, U, tsr, y_R, z_H, 
                    nidaq=True, vectrino=vectrino, vecsavepath=vecsavepath,
                    R=radius, H=height, fbg=fbg, fbg_prop_fpath=self.fbg_prop_fpath)
            self.turbinetow.towfinished.connect(self.on_tow_finished)
            self.turbinetow.metadata["Name"] = self.currentname
            self.turbinetow.metadata["Turbine"] = self.turbine_properties[turbine]
            self.turbinetow.metadata["Turbine"]["Name"] = turbine
            self.acsdata = self.turbinetow.acsdaqthread.data
            self.nidata = self.turbinetow.daqthread.data
            if vectrino:
                self.vecdata = self.turbinetow.vec.data
            if fbg:
                self.fbgdata = self.turbinetow.fbgdata
            self.towinprogress = True
            self.monitoracs = True
            self.monitorni = True
            self.monitorvec = vectrino
            self.monitorfbg = fbg
            self.turbinetow.start()
        else:
            print("Cannot start turbine tow because axis is disabled")
            text = str(self.label_runstatus.text()).split()
            text = " ".join(text[:3])
            self.label_runstatus.setText(text + " cannot start ")
        
    def do_tare_drag_tow(self, U):
        """Executes a single tare drag run"""
        self.tarerun = runtypes.TareDragRun(self.hc, U)
        self.tarerun.runfinished.connect(self.on_tare_run_finished)
        self.tarerun.metadata["Name"] = self.currentname
        self.acsdata = self.tarerun.acsdata
        self.nidata = self.tarerun.nidata
        self.monitorni = True
        self.monitoracs = True
        self.monitorvec = False
        self.towinprogress = True
        self.tarerun.start()
        
    def do_tare_torque_run(self, rpm, dur):
        """Executes a single tare torque run"""
        self.tarerun = runtypes.TareTorqueRun(self.hc, rpm, dur)
        self.tarerun.runfinished.connect(self.on_tare_run_finished)
        self.tarerun.metadata["Name"] = self.currentname
        self.acsdata = self.tarerun.acsdata
        self.nidata = self.tarerun.nidata
        self.monitorni = True
        self.monitoracs = True
        self.monitorvec = False
        self.towinprogress = True
        self.tarerun.start()
        
    def on_tare_run_finished(self):
        """Current tow complete."""
        # Reset time of last run
        self.towinprogress = False
        self.monitoracs = False
        self.monitorni = False
        self.monitorfbg = False
        self.time_last_run = time.time()
        # Save data from the run that just finished
        savedir = self.savesubdir
        if not self.tarerun.aborted:
            nidata = dict(self.nidata)
            if "turbine_rpm" in nidata:
                del nidata["turbine_rpm"]
            self.save_raw_data(savedir, "acsdata.h5", self.acsdata)
            self.save_raw_data(savedir, "nidata.h5", nidata)
            with open(os.path.join(savedir, "metadata.json"), "w") as fn:
                json.dump(self.tarerun.metadata, fn, indent=4)
            text = str(self.label_runstatus.text())
            if "in progress" in text:
                self.label_runstatus.setText(text[:-13] + " saved ")
            print("Saved")
        elif self.tarerun.aborted:
            quit_msg = "Delete files from aborted run?"
            reply = QtGui.QMessageBox.question(self, 'Run Aborted', 
                     quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if reply == QtGui.QMessageBox.Yes:
                shutil.rmtree(self.savesubdir)
        # Update test plan table
        self.test_plan_into_table()
        # If executing a test plan start a single shot timer for next run
        if self.ui.tabTestPlan.isVisible():
            if self.ui.actionStart.isChecked():
                # Move y and z axes to next location if applicable?
                try:
                    U = self.tarerun.U
                except AttributeError:
                    U = None
                if U == None:
                    idlesec = 5
                elif U <= 0.6:
                    idlesec = 30
                elif U <= 1.0:
                    idlesec = 60
                elif U <= 1.1:
                    idlesec = 90
                else:
                    idlesec = 120
                print("Waiting " + str(idlesec) + " seconds until next run...")
                QtCore.QTimer.singleShot(idlesec*1000, self.on_idletimer)
                # Scroll test plan so completed run is in view
                try:
                    i = int(self.currentrun) + 1
                    cr = self.ui.tableWidgetTestPlan.item(i, 0)
                    self.ui.tableWidgetTestPlan.scrollToItem(cr)
                except:
                    pass
        else: 
            self.ui.actionStart.setChecked(False)
            self.on_start()
        self.nidata = {}
        self.acsdata = {}
        
    def on_tow_finished(self):
        """Current tow complete."""
        # Reset time of last run
        self.towinprogress = False
        self.monitoracs = False
        self.monitorni = False
        self.monitorvec = False
        self.monitorfbg = False
        self.time_last_run = time.time()
        # Save data from the run that just finished
        savedir = self.savesubdir
        if not self.turbinetow.aborted and not self.turbinetow.autoaborted:
            # Create directory and save the data inside
            print("Saving to " + savedir + "...")
            nidata = dict(self.nidata)
            if "turbine_rpm" in nidata:
                del nidata["turbine_rpm"]
            self.save_raw_data(savedir, "acsdata.h5", self.acsdata)
            self.save_raw_data(savedir, "nidata.h5", nidata)
            if self.turbinetow.vectrino:
                self.save_raw_data(savedir, "vecdata.h5", self.vecdata)
            if self.turbinetow.fbg:
                self.save_raw_data(savedir, "fbgdata.h5", self.fbgdata)
            with open(os.path.join(savedir, "metadata.json"), "w") as fn:
                json.dump(self.turbinetow.metadata, fn, indent=4)
            text = str(self.label_runstatus.text())
            if "in progress" in text:
                self.label_runstatus.setText(text[:-13] + " saved ")
            print("Saved")
            if self.autoprocess:
                section = str(self.ui.comboBox_testPlanSection.currentText())
                nrun = str(self.currentrun)
                subprocess.call(["cd", self.wdir, "&", "python", 
                         self.wdir+"/processing.py", section, nrun], shell=True)
        elif self.turbinetow.aborted:
            quit_msg = "Delete files from aborted run?"
            reply = QtGui.QMessageBox.question(self, 'Run Aborted', 
                     quit_msg, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
            if reply == QtGui.QMessageBox.Yes:
                shutil.rmtree(self.savesubdir)
        elif self.turbinetow.autoaborted:
            print("Deleting files from aborted run...")
            shutil.rmtree(self.savesubdir)
        # Update test plan table
        self.test_plan_into_table()
        # If executing a test plan start a single shot timer for next run
        if self.ui.tabTestPlan.isVisible():
            if self.ui.actionStart.isChecked():
                # Move y and z axes to next location if applicable?
                if self.turbinetow.autoaborted:
                    idlesec = 5
                elif self.turbinetow.U <= 0.4:
                    idlesec = 150
                elif self.turbinetow.U <= 0.6:
                    idlesec = 180
                elif self.turbinetow.U <= 0.8:
                    idlesec = 210
                elif self.turbinetow.U <= 1.0:
                    idlesec = 240
                elif self.turbinetow.U <= 1.2:
                    idlesec = 300
                elif self.turbinetow.U <= 1.4:
                    idlesec = 360
                else:
                    idlesec = 480
                print("Waiting " + str(idlesec) + " seconds until next run...")
                QtCore.QTimer.singleShot(idlesec*1000, self.on_idletimer)
                # Scroll test plan so completed run is in view
                try:
                    i = int(self.currentrun) + 1
                    cr = self.ui.tableWidgetTestPlan.item(i, 0)
                    self.ui.tableWidgetTestPlan.scrollToItem(cr)
                except:
                    pass
        else: 
            self.ui.actionStart.setChecked(False)
            self.on_start()
        self.vecdata = {}
        self.nidata = {}
        self.acsdata = {}
        self.fbgdata = {}
        self.turbinetow.vec.data = {}
        self.turbinetow.vec = None
        self.turbinetow.deleteLater()
        self.turbinetow = None
        
    def on_idletimer(self):
        if self.ui.actionStart.isChecked():
            self.do_test_plan()
        
    def do_test_plan(self):
        """Continue test plan"""
        section = str(self.ui.comboBox_testPlanSection.currentText())
        print("Continuing", section+"...")
        # Find next run to do by looking in the Done? column
        nruns = self.ui.tableWidgetTestPlan.rowCount()
        donecol = self.ui.tableWidgetTestPlan.columnCount()-1
        for n in range(nruns):
            doneval = self.ui.tableWidgetTestPlan.item(n, donecol).text()
            if doneval == "No":
                nextrun = int(float(self.ui.tableWidgetTestPlan.item(n, 0).text()))
                break
        print("Starting run", str(nextrun) + "...")
        self.savedir = os.path.join(self.wdir, "Raw", section)
        self.currentrun = nextrun
        self.currentname = section + " run " + str(nextrun)
        self.label_runstatus.setText(self.currentname + " in progress ")
        if not os.path.isdir(self.savedir):
            os.mkdir(self.savedir)
        self.savesubdir = os.path.join(self.savedir, str(nextrun))
        try:
            os.mkdir(self.savesubdir)
        except WindowsError:
            print("Save subdirectory already exists. Files will be overwritten.")
        if section.lower() == "tare drag":
            U = float(self.ui.tableWidgetTestPlan.item(nextrun, 1).text())
            self.do_tare_drag_tow(U)
        elif section.lower() == "tare torque":
            rpm = float(self.ui.tableWidgetTestPlan.item(nextrun, 1).text())
            dur = float(self.ui.tableWidgetTestPlan.item(nextrun, 2).text())
            self.do_tare_torque_run(rpm, dur)
        else:
            run_df = self.test_plan[section]
            run_df = run_df[run_df.run == nextrun].iloc[0]
            U = run_df.tow_speed
            tsr = run_df.tsr
            vectrino = run_df.vectrino
            if vectrino:
                y_R = run_df.y_R
                z_H = run_df.z_H
            else:
                y_R = z_H = None
            try: 
                fbg = run_df["fbg"]
            except KeyError:
                fbg = False
            self.do_turbine_tow(U, tsr, vectrino, y_R, z_H, fbg)
        
    def on_monitor_acs(self):
        if self.ui.actionMonitor_ACS.isChecked():
            self.acsthread = daqtasks.AcsDaqThread(self.hc, makeprg=True,
                                     sample_rate=1000, bufflen=100)
            self.acsdata = self.acsthread.data            
            self.acsthread.start()
            self.monitoracs = True
        else:
            self.acsthread.stop()
            self.monitoracs = False
        
    def on_monitor_ni(self):
        if self.ui.actionMonitor_NI.isChecked():
            self.daqthread = daqtasks.NiDaqThread(usetrigger=False)
            self.nidata = self.daqthread.data
            self.daqthread.start()
            self.monitorni = True
        else:
            self.daqthread.clear()
            self.monitorni = False

    def on_monitor_vec(self):
        if self.ui.actionMonitor_Vectrino.isChecked():
            self.vecthread = vectasks.VectrinoThread(usetrigger=False, 
                                                     maxvel=0.5,
                                                     record=False)
            self.vecdata = self.vecthread.vecdata
            self.vecthread.start()
            self.monitorvec = True
        else:
            self.vecthread.stop()
            self.monitorvec = False
            self.label_vecstatus.setText(self.vecthread.vecstatus)
            
    def on_monitor_fbg(self):
        if self.ui.actionMonitor_FBG.isChecked():
            fbg_props = self.fbg_properties
            self.fbgthread = daqtasks.FbgDaqThread(fbg_props, usetrigger=False)
            self.fbgdata = self.fbgthread.data
            self.fbgthread.start()
            self.monitorfbg = True
        else:
            self.fbgthread.stop()
            self.monitorfbg = False
    
    def on_timer(self):
        self.update_acs()
        self.time_since_last_run = time.time() - self.time_last_run
        self.label_timer.setText("Time since last run: " + \
        str(int(self.time_since_last_run)) + " s ")
            
    def on_plot_timer(self):
        if self.monitoracs:
            self.update_plots_acs()
        if self.monitorvec:
            self.update_plots_vec()
            try:
                if not self.towinprogress:
                    self.label_vecstatus.setText(self.vecthread.vecstatus)
                else:
                    self.label_vecstatus.setText(self.turbinetow.vecstatus)
            except AttributeError:
                pass
        if self.monitorni:
            self.update_plots_ni()
        if self.monitorfbg:
            self.update_plots_fbg()
            
    def on_process(self):
        section = str(self.ui.comboBox_process_section.currentText())
        nrun = str(self.ui.comboBox_process_nrun.currentText())
        subprocess.call(["cd", self.wdir, "&", "python", 
                         self.wdir+"/processing.py", section, nrun], shell=True)
    
    def update_plots_acs(self):
        """Update the acs plots for carriage speed, rpm, and tsr"""
        t = self.acsdata["t"]
        self.curve_acs_carvel.set_data(t, self.acsdata["carriage_vel"])
        self.plot_acs_carvel.replot()
        self.curve_acs_rpm.set_data(t, self.acsdata["turbine_rpm"])
        self.plot_acs_rpm.replot()
        
    def update_plots_ni(self):
        t = self.nidata["t"]
        self.curve_drag_left.set_data(t, self.nidata["drag_left"])
        self.plot_drag_left.replot()
        self.curve_torque_trans.set_data(t, self.nidata["torque_trans"])
        self.curve_torque_arm.set_data(t, self.nidata["torque_arm"])        
        self.plot_torque.replot()
        self.curve_drag_right.set_data(t, self.nidata["drag_right"])
        self.plot_drag_right.replot()
        if len(self.nidata["drag_left"]) == len(self.nidata["drag_right"]):
            self.curve_drag.set_data(t, self.nidata["drag_left"]\
                    +self.nidata["drag_right"])
            self.plot_drag.replot()
        self.curve_rpm_ni.set_data(t, self.nidata["turbine_rpm"])
        self.plot_rpm_ni.replot()
        
    def update_plots_vec(self):
        """This function updates the Vectrino plots."""
        t = self.vecdata["t"]
        if len(t) > 400 and len(t) < 600 and self.towinprogress:
            if len(np.where(np.abs(self.vecdata["u"][:450]) > 0.5)[0]) > 50:
                self.badvecdata.emit()
        meancorr = self.vecdata["corr_u"]
        meansnr = self.vecdata["snr_u"]
        self.curve_vecu.set_data(t, self.vecdata["u"])
        self.plot_vecu.replot()
        self.curve_vecv.set_data(t, self.vecdata["v"])
        self.plot_vecv.replot()
        self.curve_vecw.set_data(t, self.vecdata["w"])
        self.plot_vecw.replot()
        self.curve_vec_corr.set_data(t, meancorr)
        self.plot_vec_corr.replot()
        self.curve_vec_snr.set_data(t, meansnr)
        self.plot_vec_snr.replot()
        
    def update_plots_fbg(self):
        """This function updates the FBG plots."""
        t = self.fbgdata["time"]
        fbgs = self.fbgthread.interr.sensors
        self.curve_fbg_1.set_data(t, self.fbgdata[fbgs[0].name + "_wavelength"])
        self.plot_fbg_1.replot()
        self.curve_fbg_2.set_data(t, self.fbgdata[fbgs[1].name + "_wavelength"])
        self.plot_fbg_2.replot()
    
    def update_acs(self):
        """This function updates all the non-time-critical 
        ACS controller data"""
        if acsc.getMotorState(self.hc, 0)["enabled"]:
            self.enabled_axes["y"] = "Yes"
        else:
            self.enabled_axes["y"] = "No"
        if acsc.getMotorState(self.hc, 1)["enabled"]:
            self.enabled_axes["z"] = "Yes"
        else:
            self.enabled_axes["z"] = "No"            
        if acsc.getMotorState(self.hc, 4)["enabled"]:
            self.enabled_axes["turbine"] = "Yes"
        else:
            self.enabled_axes["turbine"] = "No"
        if acsc.getMotorState(self.hc, 5)["enabled"]:
            self.enabled_axes["tow"] = "Yes"
        else:
            self.enabled_axes["tow"] = "No"            
        # Put this data into table widget
        self.ui.tableWidget_acs.setItem(0, 1, 
                QtGui.QTableWidgetItem(str(self.enabled_axes["tow"])))
        self.ui.tableWidget_acs.setItem(1, 1, 
                QtGui.QTableWidgetItem(str(self.enabled_axes["turbine"])))
        self.ui.tableWidget_acs.setItem(2, 1, 
                QtGui.QTableWidgetItem(str(self.enabled_axes["y"])))
        self.ui.tableWidget_acs.setItem(3, 1, 
                QtGui.QTableWidgetItem(str(self.enabled_axes["z"])))
        hc_tow = acsc.readInteger(self.hc, acsc.NONE, "homeCounter_tow")
        hc_turbine = acsc.readInteger(self.hc, acsc.NONE, "homeCounter_AKD")
        hc_y = acsc.readInteger(self.hc, acsc.NONE, "homeCounter_y")
        hc_z = acsc.readInteger(self.hc, acsc.NONE, "homeCounter_z")
        self.ui.tableWidget_acs.setItem(0, 2, QtGui.QTableWidgetItem(str(hc_tow)))
        self.ui.tableWidget_acs.setItem(1, 2, QtGui.QTableWidgetItem(str(hc_turbine)))
        self.ui.tableWidget_acs.setItem(2, 2, QtGui.QTableWidgetItem(str(hc_y)))
        self.ui.tableWidget_acs.setItem(3, 2, QtGui.QTableWidgetItem(str(hc_z)))
        self.ui.tableWidget_acs.setItem(0, 3, 
                QtGui.QTableWidgetItem(str(acsc.getRPosition(self.hc, 5))))
        self.ui.tableWidget_acs.setItem(1, 3, 
                QtGui.QTableWidgetItem(str(acsc.getRPosition(self.hc, 4))))
        self.ui.tableWidget_acs.setItem(2, 3, 
                QtGui.QTableWidgetItem(str(acsc.getRPosition(self.hc, 0))))
        self.ui.tableWidget_acs.setItem(3, 3, 
                QtGui.QTableWidgetItem(str(acsc.getRPosition(self.hc, 1))))
                
    def save_raw_data(self, savedir, fname, datadict, verbose=True):
        """Saves a dict of raw data in HDF5 format."""
        fpath = os.path.join(savedir, fname)
        if verbose:
            print("Saving {} to {}".format(fname, savedir))
        if not os.path.isdir(savedir):
            os.makedirs(savedir)
        ts.savehdf(fpath, datadict)
    
    def closeEvent(self, event):
        self.settings["Last window location"] = [self.pos().x(), 
                                                 self.pos().y()]
        self.settings["Last section"] = \
                self.ui.comboBox_testPlanSection.currentIndex()
        self.settings["Last PC name"] = self.pcid
        self.settings["Last size"] = (self.size().height(), 
                                      self.size().width())
        self.settings["FBG visible"] = self.ui.dockWidget_FBG.isVisible()
        self.settings["Vectrino visible"] = self.ui.dockWidgetVectrino.isVisible()
        if not os.path.isdir("settings"):
            os.mkdir("settings")
        with open("settings/settings.json", "w") as fn:
            json.dump(self.settings, fn, indent=4)
        acsc.closeComm(self.hc)
        if self.monitorni and not self.towinprogress:
            self.daqthread.clear()
        if self.monitorvec and not self.towinprogress:
            self.vecthread.stop()
        if self.monitorfbg and not self.towinprogress:
            self.fbgthread.stop()

def test_read_turbine_properties():
    import sys
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    w.read_turbine_properties()
    print(w.turbine_properties)
    sys.exit(app.exec_())
    
def test_save_raw_data():
    """Test whether data is being saved correctly."""
    import sys
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    savedir = os.path.join(w.wdir, "data_save_test")
    data = {"arange(5)" : np.arange(5), "zeros(5)" : np.zeros(5)}
    w.save_raw_data(savedir, "testdata.h5", data)
    try:
        data = ts.loadhdf(os.path.join(savedir, "testdata.h5"))
        shutil.rmtree(savedir)
        print("test_save_raw_data passed")
    except IOError:
        print("test_save_raw_data failed")
    sys.exit(app.exec_())
    
def test_import_test_plan():
    import sys
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    print("Test plan has {} sections".format(len(w.test_plan)))
    for k,v in w.test_plan.items():
        print(k + ":")
        print(v)
    sys.exit(app.exec_())

def main():
    import sys
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
#    test_read_turbine_properties()
#    test_save_raw_data()
#    test_import_test_plan()