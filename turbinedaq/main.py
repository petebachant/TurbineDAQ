#!/usr/bin/env python
"""TurbineDAQ main app module."""

import json
import os
import platform
import shutil
import subprocess
import time
from typing import Literal

import guiqwt
import guiqwt.curve
import numpy as np
import pandas as pd
import scipy.interpolate
from acspy import acsc
from pxl import timeseries as ts
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from turbinedaq import daqtasks, runtypes, vectasks
from turbinedaq.mainwindow import *

fluid_params = {"rho": 1000.0}
abort_on_bad_vecdata = True


class MainWindow(QMainWindow):
    badvecdata = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        QMainWindow.__init__(self)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # Create AFT dock widgets
        self.create_aft_dock_widget()
        self.create_aft_ni_dock_widget()
        # Add initial items to AFT row of ACS table widget
        for n in range(1, 6):
            item = QtWidgets.QTableWidgetItem()
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.ui.tableWidget_acs.setItem(4, n, item)
        # Add action group for determining the mode
        self.turbine_mode_action_group = QtWidgets.QActionGroup(
            self.ui.menuMode
        )
        self.turbine_mode_action_group.setExclusive(True)
        self.action_cft_mode = QtWidgets.QAction(
            "CFT", self.ui.menuMode, checkable=True, checked=True
        )
        self.action_aft_mode = QtWidgets.QAction(
            "AFT", self.ui.menuMode, checkable=True, checked=False
        )
        self.ui.menuMode.addAction(self.action_cft_mode)
        self.ui.menuMode.addAction(self.action_aft_mode)
        self.turbine_mode_action_group.addAction(self.action_cft_mode)
        self.turbine_mode_action_group.addAction(self.action_aft_mode)
        self.turbine_mode_action_group.triggered.connect(
            self.on_turbine_mode_change
        )
        # Create time vector
        self.t = np.array([])
        self.time_last_run = time.time()
        # Some operating parameters
        self.plot_len_sec = 30.0
        self.monitoracs = False
        self.monitorni = False
        self.monitorvec = False
        self.monitorfbg = False
        self.monitorodisi = False
        self.run_in_progress = False
        self.test_plan_loaded = False
        self.autoprocess = True
        self.enabled_axes = {}
        self.test_plan = {}
        self.turbinetow = None
        self.nidata = {}
        # Add file path combobox to toolbar
        self.line_edit_wdir = QLineEdit()
        self.ui.toolBar_directory.addWidget(self.line_edit_wdir)
        self.wdir = "C:\\temp"
        self.line_edit_wdir.setText("C:\\temp")
        self.toolbutton_wdir = QToolButton()
        self.ui.toolBar_directory.addWidget(self.toolbutton_wdir)
        self.toolbutton_wdir.setIcon(QIcon(":icons/folder_yellow.png"))
        # Add labels to status bar
        self.add_labels_to_statusbar()
        # Create timers
        self.timer = QtCore.QTimer()
        self.plot_timer = QtCore.QTimer()
        # Connect to controller
        self.connect_to_acs_controllers()
        # Read in and apply settings from last session
        self.load_settings()
        # Read turbine, vectrino, FBG, and ODIsi properties
        self.read_turbine_properties()
        self.ui.comboBox_turbine.addItems(self.turbine_properties.keys())
        self.read_vectrino_properties()
        self.read_fbg_properties()
        self.read_odisi_properties()
        # Import test plan
        self.load_test_plan()
        # Initialize plots
        self.initialize_plots()
        # Add checkboxes to ACS table widget
        self.add_acs_checkboxes()
        # Connect signals and slots
        self.connect_sigs_slots()
        # Return to last section in test plan if possible
        if "Last section index" in self.settings:
            try:
                self.ui.comboBox_testPlanSection.setCurrentIndex(
                    self.settings["Last section index"]
                )
            except:
                print("Previous test plan section index does not exist")
                pass
        # Start timers
        self.timer.start(200)
        self.plot_timer.start(100)
        # Remember FBG dock widget visibility from last session
        if "FBG visible" in self.settings:
            self.ui.dockWidget_FBG.setVisible(self.settings["FBG visible"])
            self.ui.actionFBG.setChecked(self.settings["FBG visible"])
        else:
            self.ui.dockWidget_FBG.close()
            self.ui.actionFBG.setChecked(False)
        # Remember ODiSI dock widget visibility from last session
        if "ODiSI visible" in self.settings:
            self.ui.dockWidget_ODiSI.setVisible(self.settings["ODiSI visible"])
            self.ui.actionODiSI.setChecked(self.settings["ODiSI visible"])
        else:
            self.ui.dockWidget_ODiSI.close()
            self.ui.actionODiSI.setChecked(False)
        # Remember Lateral Force dock widget visibility from last session
        if "Lateral forces visible" in self.settings:
            self.ui.dockWidget_LF.setVisible(
                self.settings["Lateral forces visible"]
            )
            self.ui.actionLF.setChecked(
                self.settings["Lateral forces visible"]
            )
        else:
            self.ui.dockWidget_LF.close()
            self.ui.actionLF.setChecked(False)
        # Remember Vectrino dock widget visibility from last session
        if "Vectrino visible" in self.settings:
            self.ui.dockWidgetVectrino.setVisible(
                self.settings["Vectrino visible"]
            )
            self.ui.actionVectrino_View.setChecked(
                self.settings["Vectrino visible"]
            )
        # Remember NI-DAQ dock widget visibility from last session
        if "NI visible" in self.settings:
            self.ui.dockWidgetNISignals.setVisible(self.settings["NI visible"])
            self.ui.actionNI_Signals.setChecked(self.settings["NI visible"])
        # Remember AFT dock widget visibility from last session
        if "AFT visible" in self.settings:
            self.dockWidget_AFT.setVisible(self.settings["AFT visible"])
            self.ui.actionViewAFT.setChecked(self.settings["AFT visible"])
        # Remember AFT NI dock widget visibility from last session
        if "AFT NI visible" in self.settings:
            self.dockwidget_aft_ni.setVisible(self.settings["AFT NI visible"])
            self.ui.actionNI_DAQ_AFT.setChecked(
                self.settings["AFT NI visible"]
            )

    def create_aft_dock_widget(self):
        self.dockWidget_AFT = QtWidgets.QDockWidget(self.ui.centralwidget)
        self.dockWidget_AFT.setMinimumSize(QtCore.QSize(224, 601))
        self.dockWidget_AFT.setFeatures(
            QtWidgets.QDockWidget.AllDockWidgetFeatures
        )
        self.dockWidget_AFT.setObjectName("dockWidget_AFT")
        self.dockWidget_AFT.setWindowTitle("AFT")
        self.dockWidgetContents_AFT = QtWidgets.QWidget()
        self.dockWidgetContents_AFT.setObjectName("dockWidgetContents_AFT")
        self.gridLayout_AFT = QtWidgets.QGridLayout(
            self.dockWidgetContents_AFT
        )
        self.gridLayout_AFT.setObjectName("gridLayout_AFT")
        self.verticalLayout_AFT = QtWidgets.QVBoxLayout()
        self.verticalLayout_AFT.setObjectName("verticalLayout_AFT")
        # Plot 1
        self.label_AFT_1 = QtWidgets.QLabel(self.dockWidgetContents_AFT)
        self.label_AFT_1.setAlignment(QtCore.Qt.AlignCenter)
        self.label_AFT_1.setObjectName("label_AFT_1")
        self.label_AFT_1.setText("             Edgewise Bending Moment (Nm)")
        self.verticalLayout_AFT.addWidget(self.label_AFT_1)
        self.plot_AFT_1 = CurveWidget(self.dockWidgetContents_AFT)
        self.plot_AFT_1.setOrientation(QtCore.Qt.Horizontal)
        self.plot_AFT_1.setObjectName("plot_AFT_1")
        self.verticalLayout_AFT.addWidget(self.plot_AFT_1)
        # Plot 2
        self.label_AFT_2 = QtWidgets.QLabel(self.dockWidgetContents_AFT)
        self.label_AFT_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_AFT_2.setObjectName("label_AFT_2")
        self.label_AFT_2.setText("             Flapwise Bending Moment (Nm)")
        self.verticalLayout_AFT.addWidget(self.label_AFT_2)
        self.plot_AFT_2 = CurveWidget(self.dockWidgetContents_AFT)
        self.plot_AFT_2.setOrientation(QtCore.Qt.Horizontal)
        self.plot_AFT_2.setObjectName("plot_AFT_2")
        self.verticalLayout_AFT.addWidget(self.plot_AFT_2)
        # Plot 3
        self.label_AFT_3 = QtWidgets.QLabel(self.dockWidgetContents_AFT)
        self.label_AFT_3.setAlignment(QtCore.Qt.AlignCenter)
        self.label_AFT_3.setObjectName("label_AFT_3")
        self.label_AFT_3.setText("             Rotor Thrust (N)")
        self.verticalLayout_AFT.addWidget(self.label_AFT_3)
        self.plot_AFT_3 = CurveWidget(self.dockWidgetContents_AFT)
        self.plot_AFT_3.setOrientation(QtCore.Qt.Horizontal)
        self.plot_AFT_3.setObjectName("plot_AFT_3")
        self.verticalLayout_AFT.addWidget(self.plot_AFT_3)
        # Plot 4
        self.label_AFT_4 = QtWidgets.QLabel(self.dockWidgetContents_AFT)
        self.label_AFT_4.setAlignment(QtCore.Qt.AlignCenter)
        self.label_AFT_4.setObjectName("label_AFT_4")
        self.label_AFT_4.setText("             Rotor Torque (Nm)")
        self.verticalLayout_AFT.addWidget(self.label_AFT_4)
        self.plot_AFT_4 = CurveWidget(self.dockWidgetContents_AFT)
        self.plot_AFT_4.setOrientation(QtCore.Qt.Horizontal)
        self.plot_AFT_4.setObjectName("plot_AFT_4")
        self.verticalLayout_AFT.addWidget(self.plot_AFT_4)
        # Finish and add to the central widget grid layout
        self.gridLayout_AFT.addLayout(self.verticalLayout_AFT, 0, 0, 1, 1)
        self.dockWidget_AFT.setWidget(self.dockWidgetContents_AFT)
        self.ui.gridLayout_4.addWidget(self.dockWidget_AFT, 0, 5, 6, 1)
        # Connect signals and slots for view menu action
        self.ui.actionViewAFT.toggled.connect(self.dockWidget_AFT.setVisible)
        self.dockWidget_AFT.visibilityChanged.connect(
            self.ui.actionViewAFT.setChecked
        )
        # Set invisible by default
        self.dockWidget_AFT.setVisible(False)

    def create_aft_ni_dock_widget(self) -> None:
        self.dockwidget_aft_ni = QtWidgets.QDockWidget(self.ui.centralwidget)
        self.dockwidget_aft_ni.setMinimumSize(QtCore.QSize(224, 601))
        self.dockwidget_aft_ni.setFeatures(
            QtWidgets.QDockWidget.AllDockWidgetFeatures
        )
        self.dockwidget_aft_ni.setObjectName("dockwidget_aft_ni")
        self.dockwidget_aft_ni.setWindowTitle("NI-DAQ (AFT)")
        self.dockwidgetcontents_aft_ni = QtWidgets.QWidget()
        self.dockwidgetcontents_aft_ni.setObjectName(
            "dockwidgetcontents_aft_ni"
        )
        self.gridlayout_aft_ni = QtWidgets.QGridLayout(
            self.dockwidgetcontents_aft_ni
        )
        self.gridlayout_aft_ni.setObjectName("gridlayout_aft_ni")
        self.verticallayout_aft_ni = QtWidgets.QVBoxLayout()
        self.verticallayout_aft_ni.setObjectName("verticallayout_aft_ni")
        # Plot 1
        self.label_aft_ni_1 = QtWidgets.QLabel(self.dockwidgetcontents_aft_ni)
        self.label_aft_ni_1.setAlignment(QtCore.Qt.AlignCenter)
        self.label_aft_ni_1.setObjectName("label_aft_ni_1")
        self.label_aft_ni_1.setText("             Resistor Temp. (°F)")
        self.verticallayout_aft_ni.addWidget(self.label_aft_ni_1)
        self.plot_aft_ni_1 = CurveWidget(self.dockwidgetcontents_aft_ni)
        self.plot_aft_ni_1.setOrientation(QtCore.Qt.Horizontal)
        self.plot_aft_ni_1.setObjectName("plot_aft_ni_1")
        self.verticallayout_aft_ni.addWidget(self.plot_aft_ni_1)
        # Plot 2
        self.label_aft_ni_2 = QtWidgets.QLabel(self.dockwidgetcontents_aft_ni)
        self.label_aft_ni_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_aft_ni_2.setObjectName("label_aft_ni_2")
        self.label_aft_ni_2.setText("             Yaskawa Temp. (°F)")
        self.verticallayout_aft_ni.addWidget(self.label_aft_ni_2)
        self.plot_aft_ni_2 = CurveWidget(self.dockwidgetcontents_aft_ni)
        self.plot_aft_ni_2.setOrientation(QtCore.Qt.Horizontal)
        self.plot_aft_ni_2.setObjectName("plot_aft_ni_2")
        self.verticallayout_aft_ni.addWidget(self.plot_aft_ni_2)
        # Plot 3
        self.label_aft_ni_3 = QtWidgets.QLabel(self.dockwidgetcontents_aft_ni)
        self.label_aft_ni_3.setAlignment(QtCore.Qt.AlignCenter)
        self.label_aft_ni_3.setObjectName("label_aft_ni_3")
        self.label_aft_ni_3.setText("             Fore Temp. (°F)")
        self.verticallayout_aft_ni.addWidget(self.label_aft_ni_3)
        self.plot_aft_ni_3 = CurveWidget(self.dockwidgetcontents_aft_ni)
        self.plot_aft_ni_3.setOrientation(QtCore.Qt.Horizontal)
        self.plot_aft_ni_3.setObjectName("plot_aft_ni_3")
        self.verticallayout_aft_ni.addWidget(self.plot_aft_ni_3)
        # Plot 4
        self.label_aft_ni_4 = QtWidgets.QLabel(self.dockwidgetcontents_aft_ni)
        self.label_aft_ni_4.setAlignment(QtCore.Qt.AlignCenter)
        self.label_aft_ni_4.setObjectName("label_aft_ni_4")
        self.label_aft_ni_4.setText("             Aft Temp. (°F)")
        self.verticallayout_aft_ni.addWidget(self.label_aft_ni_4)
        self.plot_aft_ni_4 = CurveWidget(self.dockwidgetcontents_aft_ni)
        self.plot_aft_ni_4.setOrientation(QtCore.Qt.Horizontal)
        self.plot_aft_ni_4.setObjectName("plot_aft_ni_4")
        self.verticallayout_aft_ni.addWidget(self.plot_aft_ni_4)
        # Finish and add to the central widget grid layout
        self.gridlayout_aft_ni.addLayout(
            self.verticallayout_aft_ni, 0, 0, 1, 1
        )
        self.dockwidget_aft_ni.setWidget(self.dockwidgetcontents_aft_ni)
        self.ui.gridLayout_4.addWidget(self.dockwidget_aft_ni, 0, 6, 6, 1)
        # Connect signals and slots for view menu action
        self.ui.actionNI_DAQ_AFT.toggled.connect(
            self.dockwidget_aft_ni.setVisible
        )
        self.dockwidget_aft_ni.visibilityChanged.connect(
            self.ui.actionNI_DAQ_AFT.setChecked
        )
        # Set invisible by default
        self.dockwidget_aft_ni.setVisible(False)

    @property
    def settings_fpath(self) -> str:
        return os.path.join(
            os.path.expanduser("~"), ".turbinedaq", "settings.json"
        )

    def load_settings(self):
        """Loads settings from JSON file."""
        self.pcid = platform.node()
        print("Attempting to load settings from:", self.settings_fpath)
        try:
            with open(self.settings_fpath, "r") as fn:
                self.settings = json.load(fn)
                print("Loaded settings:", self.settings)
        except IOError:
            print("Failed to load settings")
            self.settings = {}
        if "Last PC name" in self.settings:
            if self.settings["Last PC name"] == self.pcid:
                if "Last working directory" in self.settings:
                    if os.path.isdir(self.settings["Last working directory"]):
                        self.wdir = self.settings["Last working directory"]
                        self.line_edit_wdir.setText(self.wdir)
                if "Last window location" in self.settings:
                    self.move(
                        QtCore.QPoint(
                            self.settings["Last window location"][0],
                            self.settings["Last window location"][1],
                        )
                    )
        if "Last size" in self.settings:
            oldheight = self.settings["Last size"][0]
            oldwidth = self.settings["Last size"][1]
            self.resize(oldwidth, oldheight)
        if "Last tab index" in self.settings:
            self.ui.tabWidgetMode.setCurrentIndex(
                self.settings["Last tab index"]
            )
        if "Shakedown tow speed" in self.settings:
            val = self.settings["Shakedown tow speed"]
            self.ui.doubleSpinBox_singleRun_U.setValue(val)
        if "Shakedown turbine" in self.settings:
            self.ui.comboBox_turbine.setCurrentText(
                self.settings["Shakedown turbine"]
            )
        if "Shakedown TSR" in self.settings:
            val = self.settings["Shakedown TSR"]
            self.ui.doubleSpinBox_singleRun_tsr.setValue(val)
        if "Shakedown y/R" in self.settings:
            val = self.settings["Shakedown y/R"]
            self.ui.doubleSpinBox_singleRun_y_R.setValue(val)
        if "Shakedown z/H" in self.settings:
            val = self.settings["Shakedown z/H"]
            self.ui.doubleSpinBox_singleRun_z_H.setValue(val)
        if "Shakedown Vectrino" in self.settings:
            val = self.settings["Shakedown Vectrino"]
            self.ui.checkBox_singleRunVectrino.setChecked(val)
        if "Shakedown FBG" in self.settings:
            val = self.settings["Shakedown FBG"]
            self.ui.checkBox_singleRunFBG.setChecked(val)
        if "Shakedown ODiSI" in self.settings:
            val = self.settings["Shakedown ODiSI"]
            self.ui.checkBox_singleRunODiSI.setChecked(val)
        if "Shakedown lateral forces" in self.settings:
            val = self.settings["Shakedown lateral forces"]
            self.ui.checkBox_singleRunLF.setChecked(val)
        if "Mode" in self.settings:
            self.mode = self.settings["Mode"]

    @property
    def mode(self) -> Literal["CFT", "AFT"]:
        aft_checked = self.action_aft_mode.isChecked()
        cft_checked = self.action_cft_mode.isChecked()
        assert int(aft_checked) + int(cft_checked) == 1
        if aft_checked:
            return "AFT"
        elif cft_checked:
            return "CFT"

    @mode.setter
    def mode(self, val: Literal["CFT", "AFT"]):
        if val == "CFT":
            self.action_cft_mode.setChecked(True)
        elif val == "AFT":
            self.action_aft_mode.setChecked(True)

    def read_turbine_properties(self):
        """Reads turbine properties from `config/turbine_properties.json` in
        the experiment's working directory.

        TODO: Make this more explicitly required to handle the AFT.
        """
        self.turbine_properties = {
            "RVAT": {"kind": "CFT", "radius": 0.5, "height": 1.0},
            "RM2": {"kind": "CFT", "diameter": 1.075, "height": 0.807},
            "AFT": {"kind": "AFT", "diameter": 1.0, "height": 1.0},
        }
        fpath = os.path.join(self.wdir, "config", "turbine_properties.json")
        print(f"Attempting to read turbine properties from: {fpath}")
        try:
            with open(fpath) as f:
                new = json.load(f)
            self.turbine_properties.update(new)
            print("Turbine properties loaded")
        except IOError:
            print("No turbine properties file found")
        # Calculate radius if only diameter supplied and vice versa
        for turbine in self.turbine_properties:
            if not "radius" in self.turbine_properties[turbine]:
                self.turbine_properties[turbine]["radius"] = (
                    self.turbine_properties[turbine]["diameter"] / 2
                )
            if not "diameter" in self.turbine_properties[turbine]:
                self.turbine_properties[turbine]["diameter"] = (
                    self.turbine_properties[turbine]["radius"] * 2
                )

    def read_vectrino_properties(self):
        fpath = os.path.join(self.wdir, "config", "vectrino_properties.json")
        try:
            with open(fpath) as f:
                vecprops = json.load(f)
                self.vec_salinity = vecprops["salinity"]
            print("Vectrino properties loaded")
        except IOError:
            self.vec_salinity = 0.0

    def read_fbg_properties(self):
        fpath = os.path.join(self.wdir, "config", "fbg_properties.json")
        try:
            with open(fpath) as f:
                self.fbg_properties = json.load(f)
            print("FBG properties loaded")
        except IOError:
            self.fbg_properties = {}

    def read_odisi_properties(self):
        fpath = os.path.join(self.wdir, "config", "odisi_properties.json")
        try:
            with open(fpath) as f:
                self.odisi_properties = json.load(f)
            print("ODiSI properties loaded")
        except IOError:
            self.odisi_properties = {}

    def is_run_done(self, section, number):
        """Look as subfolders to determine progress of experiment."""
        runpath = os.path.join(self.wdir, "data", "raw", section, str(number))
        if os.path.isdir(runpath) and "metadata.json" in os.listdir(runpath):
            return True
        else:
            return False

    def is_section_done(self, section):
        """Detects if a test plan section is done."""
        done = True
        for nrun in self.test_plan[section]["run"]:
            if not self.is_run_done(section, nrun):
                done = False
        return done

    def load_test_plan(self):
        """Load test plan from CSVs in the 'Test plan' or 'test-plan'
        subdirectory.
        """
        tpdir = os.path.join(self.wdir, "config", "test-plan")
        tpdir_legacy = os.path.join(self.wdir, "config", "test plan")
        if not os.path.isdir(tpdir) and os.path.isdir(tpdir_legacy):
            print("Using legacy test plan directory")
            tpdir = tpdir_legacy
        self.test_plan_loaded = False
        self.test_plan = {}
        self.test_plan_sections = []
        self.test_plan_runs = []
        if os.path.isdir(tpdir):
            test_plan_files = os.listdir(os.path.join(tpdir))
            for f in test_plan_files:
                if ".csv" in f:
                    self.test_plan[f.replace(".csv", "")] = pd.read_csv(
                        os.path.join(tpdir, f)
                    )
                    self.test_plan_sections.append(f.replace(".csv", ""))
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
            self.ui.tableWidgetTestPlan.setColumnCount(len(paramlist) + 1)
            self.ui.tableWidgetTestPlan.setHorizontalHeaderLabels(
                paramlist + ["Done?"]
            )
            self.ui.tableWidgetTestPlan.setRowCount(
                len(self.test_plan[section][paramlist[0]])
            )
            for i in range(len(paramlist)):
                itemlist = self.test_plan[section][paramlist[i]]
                for n in range(len(itemlist)):
                    self.ui.tableWidgetTestPlan.setItem(
                        n, i, QTableWidgetItem(str(itemlist[n]))
                    )
                    # Check if run is done
                    if str(section).lower() != "top level":
                        isdone = self.is_run_done(section, n)
                        if isdone:
                            self.ui.tableWidgetTestPlan.setItem(
                                n, i + 1, QTableWidgetItem("Yes")
                            )
                            for j in range(i + 2):
                                self.ui.tableWidgetTestPlan.item(
                                    n, j
                                ).setForeground(QtCore.Qt.darkGreen)
                                self.ui.tableWidgetTestPlan.item(
                                    n, j
                                ).setBackground(QtCore.Qt.lightGray)
                        else:
                            self.ui.tableWidgetTestPlan.setItem(
                                n, i + 1, QTableWidgetItem("No")
                            )
                    elif str(section).lower() == "top level":
                        self.update_sections_done()
                    self.ui.tableWidgetTestPlan.item(n, i).setTextAlignment(
                        QtCore.Qt.AlignCenter
                    )
                    self.ui.tableWidgetTestPlan.item(
                        n, i + 1
                    ).setTextAlignment(QtCore.Qt.AlignCenter)
            # Set column widths
            self.ui.tableWidgetTestPlan.setColumnWidth(0, 31)
            self.ui.tableWidgetTestPlan.setColumnWidth(len(paramlist), 43)

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
                text = QTableWidgetItem("Yes")
            elif isdone == None:
                text = QTableWidgetItem("Maybe")
            else:
                text = QTableWidgetItem("No")
            self.ui.tableWidgetTestPlan.setItem(n + 1, -1, text)

    def add_acs_checkboxes(self):
        """Add checkboxes for axes being enabled."""
        self.checkbox_tow_axis = QCheckBox()
        self.checkbox_turbine_axis = QCheckBox()
        self.checkbox_y_axis = QCheckBox()
        self.checkbox_z_axis = QCheckBox()
        self.checkbox_aft_axis = QCheckBox()
        # Tow axis checkbox widget centering
        widget_tow = QWidget()
        layout_tow = QHBoxLayout(widget_tow)
        layout_tow.addWidget(self.checkbox_tow_axis)
        layout_tow.setAlignment(QtCore.Qt.AlignCenter)
        layout_tow.setContentsMargins(0, 0, 0, 0)
        widget_tow.setLayout(layout_tow)
        # Turbine axis checkbox widget centering
        widget_turbine = QWidget()
        layout_turbine = QHBoxLayout(widget_turbine)
        layout_turbine.addWidget(self.checkbox_turbine_axis)
        layout_turbine.setAlignment(QtCore.Qt.AlignCenter)
        layout_turbine.setContentsMargins(0, 0, 0, 0)
        widget_turbine.setLayout(layout_turbine)
        # y axis checkbox widget centering
        widget_y = QWidget()
        layout_y = QHBoxLayout(widget_y)
        layout_y.addWidget(self.checkbox_y_axis)
        layout_y.setAlignment(QtCore.Qt.AlignCenter)
        layout_y.setContentsMargins(0, 0, 0, 0)
        widget_y.setLayout(layout_y)
        # z axis checkbox widget centering
        widget_z = QWidget()
        layout_z = QHBoxLayout(widget_z)
        layout_z.addWidget(self.checkbox_z_axis)
        layout_z.setAlignment(QtCore.Qt.AlignCenter)
        layout_z.setContentsMargins(0, 0, 0, 0)
        widget_z.setLayout(layout_z)
        # AFT axis checkbox widget centering
        widget_aft = QWidget()
        layout_aft = QHBoxLayout(widget_aft)
        layout_aft.addWidget(self.checkbox_aft_axis)
        layout_aft.setAlignment(QtCore.Qt.AlignCenter)
        layout_aft.setContentsMargins(0, 0, 0, 0)
        widget_aft.setLayout(layout_aft)
        # Set cell widgets for all
        self.ui.tableWidget_acs.setCellWidget(0, 1, widget_tow)
        self.ui.tableWidget_acs.setCellWidget(1, 1, widget_turbine)
        self.ui.tableWidget_acs.setCellWidget(2, 1, widget_y)
        self.ui.tableWidget_acs.setCellWidget(3, 1, widget_z)
        self.ui.tableWidget_acs.setCellWidget(4, 1, widget_aft)

    def connect_sigs_slots(self):
        """Connect signals to appropriate slots."""
        self.toolbutton_wdir.clicked.connect(self.on_tbutton_wdir)
        self.ui.actionQuit.triggered.connect(self.close)
        self.timer.timeout.connect(self.on_timer)
        self.plot_timer.timeout.connect(self.on_plot_timer)
        self.ui.actionMonitor_Vectrino.triggered.connect(self.on_monitor_vec)
        self.ui.actionMonitor_NI.triggered.connect(self.on_monitor_ni)
        self.ui.actionMonitor_FBG.triggered.connect(self.on_monitor_fbg)
        self.ui.actionMonitor_ODiSI.triggered.connect(self.on_monitor_odisi)
        self.ui.actionMonitor_LF.triggered.connect(self.on_monitor_ni)
        self.ui.actionStart.triggered.connect(self.on_start)
        self.ui.actionAbort.triggered.connect(self.on_abort)
        self.ui.actionImportTestPlan.triggered.connect(self.load_test_plan)
        self.ui.comboBox_testPlanSection.currentIndexChanged.connect(
            self.test_plan_into_table
        )
        self.ui.tabWidgetMode.currentChanged.connect(self.on_tab_change)
        self.ui.comboBox_testPlanSection.currentIndexChanged.connect(
            self.on_section_change
        )
        self.ui.actionMonitor_ACS.triggered.connect(self.on_monitor_acs)
        self.ui.toolButtonOpenSection.clicked.connect(
            self.on_open_section_folder
        )
        self.ui.actionHome_Tow.triggered.connect(self.on_home_tow)
        self.ui.toolButtonOpenShakedown.clicked.connect(self.on_open_shakedown)
        self.ui.actionHome_Turbine.triggered.connect(self.on_home_turbine)
        self.ui.actionHome_y.triggered.connect(self.on_home_y)
        self.ui.actionHome_z.triggered.connect(self.on_home_z)
        self.ui.actionHome_AFT_axis.triggered.connect(self.on_home_aft)
        self.ui.commandLinkButton_process.clicked.connect(self.on_process)
        self.badvecdata.connect(self.on_badvecdata)
        self.checkbox_tow_axis.clicked.connect(self.on_checkbox_tow_axis)
        self.checkbox_turbine_axis.clicked.connect(
            self.on_checkbox_turbine_axis
        )
        self.checkbox_y_axis.clicked.connect(self.on_checkbox_y_axis)
        self.checkbox_z_axis.clicked.connect(self.on_checkbox_z_axis)
        self.checkbox_aft_axis.clicked.connect(self.on_checkbox_aft_axis)

    def on_tbutton_wdir(self):
        self.wdir = QFileDialog.getExistingDirectory()
        if self.wdir:
            self.line_edit_wdir.setText(self.wdir)
        self.wdir = str(self.line_edit_wdir.text())
        self.settings["Last working directory"] = self.wdir
        self.load_test_plan()
        self.read_turbine_properties()
        self.read_vectrino_properties()
        self.read_fbg_properties()
        self.read_odisi_properties()

    def on_tab_change(self):
        tabindex = self.ui.tabWidgetMode.currentIndex()
        tabitem = self.ui.tabWidgetMode.tabText(tabindex)
        section = str(self.ui.comboBox_testPlanSection.currentText())
        if tabitem == "Test Plan" and str(section).lower() == "top level":
            self.ui.actionStart.setDisabled(True)
        else:
            self.ui.actionStart.setEnabled(True)
        if tabitem == "Processing":
            savedir = os.path.join(self.wdir, "data", "raw", "shakedown")
            if os.path.isdir(savedir):
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

    def on_home_aft(self):
        acsc.runBuffer(self.hc, 21)

    def on_open_section_folder(self):
        section = str(self.ui.comboBox_testPlanSection.currentText())
        subdir = os.path.join(self.wdir, "data", "raw", section)
        try:
            os.startfile(subdir)
        except WindowsError:
            os.makedirs(subdir)
            os.startfile(subdir)

    def on_open_shakedown(self):
        subdir = os.path.join(self.wdir, "data", "raw", "shakedown")
        try:
            os.startfile(subdir)
        except WindowsError:
            os.makedirs(subdir)
            os.startfile(subdir)

    def on_section_change(self):
        section = str(self.ui.comboBox_testPlanSection.currentText())
        if str(section).lower() == "top level":
            self.ui.actionStart.setDisabled(True)
            self.update_sections_done()
        else:
            self.ui.actionStart.setEnabled(True)
        if section in self.test_plan:
            self.test_plan_into_table()

    def on_turbine_mode_change(self, action):
        """Respond to a change in turbine mode."""
        mode = action.text()
        print("Activating", mode, "mode")
        # TODO: More here if necessary, e.g., updating the EtherCAT
        # configuration in the controller

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

    def connect_to_acs_controllers(self):
        try:
            self.hc = acsc.open_comm_ethernet_tcp("10.0.0.100")
            ntm = "connected"
        except acsc.AcscError:
            print("Cannot connect to ACS NTM controller")
            print("Attempting to connect to simulator")
            self.hc = acsc.open_comm_simulator()
            ntm = "simulated"
        txt = f" ACS NTM controller: {ntm} "
        self.label_acs_connect.setText(txt)

    def initialize_plots(self):
        # Torque trans plot
        self.curve_torque_trans = guiqwt.curve.CurveItem()
        self.plot_torque = self.ui.plotTorque.get_plot()
        self.plot_torque.add_item(self.curve_torque_trans)
        # Torque arm plot
        self.curve_torque_arm = guiqwt.curve.CurveItem()
        self.curve_torque_arm.setPen(QPen(QtCore.Qt.red, 1))
        self.plot_torque.add_item(self.curve_torque_arm)
        # Drag plot
        self.curve_drag = guiqwt.curve.CurveItem()
        self.plot_drag = self.ui.plotDrag.get_plot()
        self.plot_drag.add_item(self.curve_drag)
        # Drag left plot
        self.curve_drag_left = guiqwt.curve.CurveItem()
        self.curve_drag_left.setPen(QPen(QtCore.Qt.darkGreen, 1))
        self.plot_drag_left = self.ui.plotDragL.get_plot()
        self.plot_drag_left.add_item(self.curve_drag_left)
        # Drag right plot
        self.curve_drag_right = guiqwt.curve.CurveItem()
        self.curve_drag_right.setPen(QPen(QtCore.Qt.red, 1))
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
        # Make list of FBG plots
        self.fbg_plot_list = [
            self.ui.plot_FBG_1.get_plot(),
            self.ui.plot_FBG_2.get_plot(),
            self.ui.plot_FBG_3.get_plot(),
            self.ui.plot_FBG_4.get_plot(),
            self.ui.plot_FBG_5.get_plot(),
        ]
        # Create list of FBG curves
        self.fbg_curves = []
        for n in range(len(self.fbg_properties)):
            self.fbg_curves.append(guiqwt.curve.CurveItem())
            if n > 4:
                self.fbg_curves[n].setPen(QPen(QtCore.Qt.blue, 1))
        # Iterate through FBG curves list and add curves to plots
        for n, curve in enumerate(self.fbg_curves):
            n = n % 5
            self.fbg_plot_list[n].add_item(curve)
        # ODiSI Plot
        # self.curve_odisi = guiqwt.curve.CurveItem()
        #       self.plot_odisi = self.ui.plotODiSI.get_plot()
        #       self.plot_odisi.add_item(self.curve_odisi)
        # Lateral force left plot
        self.curve_LF_left = guiqwt.curve.CurveItem()
        self.curve_LF_left.setPen(QtGui.QPen(QtCore.Qt.darkGreen, 1))
        self.plot_LF = self.ui.plotLF.get_plot()
        self.plot_LF.add_item(self.curve_LF_left)
        # Lateral force right plot
        self.curve_LF_right = guiqwt.curve.CurveItem()
        self.curve_LF_right.setPen(QtGui.QPen(QtCore.Qt.red, 1))
        self.plot_LF.add_item(self.curve_LF_right)
        # AFT plots
        # AFT plot 1
        self.curve_aft_1 = guiqwt.curve.CurveItem()
        self.curve_aft_1.setPen(QtGui.QPen(QtCore.Qt.black, 1))
        self.plot_aft_1 = self.plot_AFT_1.get_plot()
        self.plot_aft_1.add_item(self.curve_aft_1)
        # AFT plot 2
        self.curve_aft_2 = guiqwt.curve.CurveItem()
        self.curve_aft_2.setPen(QtGui.QPen(QtCore.Qt.black, 1))
        self.plot_aft_2 = self.plot_AFT_2.get_plot()
        self.plot_aft_2.add_item(self.curve_aft_2)
        # AFT pLot 3
        self.curve_aft_3 = guiqwt.curve.CurveItem()
        self.curve_aft_3.setPen(QtGui.QPen(QtCore.Qt.black, 1))
        self.plot_aft_3 = self.plot_AFT_3.get_plot()
        self.plot_aft_3.add_item(self.curve_aft_3)
        # AFT plot 4
        self.curve_aft_4 = guiqwt.curve.CurveItem()
        self.curve_aft_4.setPen(QtGui.QPen(QtCore.Qt.black, 1))
        self.plot_aft_4 = self.plot_AFT_4.get_plot()
        self.plot_aft_4.add_item(self.curve_aft_4)
        # AFT NI plots
        # Note that we do this a little differently here using getattr and
        # setattr since creating each is so similar
        for n in range(1, 5):
            curve = guiqwt.curve.CurveItem()
            curve.setPen(QtGui.QPen(QtCore.Qt.black, 1))
            plot_widget = getattr(self, f"plot_aft_ni_{n}")
            plot = plot_widget.get_plot()
            plot.add_item(curve)
            setattr(self, f"curve_aft_ni_{n}", curve)
            setattr(self, f"plot_aft_ni_{n}", plot)

    def on_start(self):
        """Start whatever is visible in the tab widget."""
        self.abort = False
        if self.ui.actionStart.isChecked():
            self.ui.actionStart.setIcon(QIcon(":icons/pause.png"))
            self.ui.actionStart.setToolTip("Stop after current run")
            self.ui.actionMonitor_NI.setChecked(False)
            self.ui.actionMonitor_Vectrino.setChecked(False)
            self.ui.actionMonitor_ODiSI.setChecked(False)
            self.ui.actionMonitor_LF.setChecked(False)
            self.ui.toolBar_DAQ.setDisabled(True)
            self.ui.toolBar_directory.setDisabled(True)
            self.ui.tabWidgetMode.setDisabled(True)
            if self.ui.tabTestPlan.isVisible():
                """Continue working on test plan"""
                section = str(self.ui.comboBox_testPlanSection.currentText())
                self.section = section
                if section.lower() != "top level":
                    self.do_test_plan()
            elif self.ui.tabSingleRun.isVisible():
                self.section = "Shakedown"
                self.do_shakedown()
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
        self.monitorfbg = False
        self.monitorodisi = False

        if self.ui.actionStart.isChecked():
            self.ui.actionStart.setChecked(False)
            print("Aborting current run")
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
        if self.ui.actionMonitor_ODiSI.isChecked():
            self.ui.actionMonitor_ODiSI.setChecked(False)
            self.odisithread.stop()
        if self.ui.actionMonitor_LF.isChecked():
            self.ui.actionMonitor_LF.setChecked(False)
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
        self.run_in_progress = False

    def auto_abort(self):
        """Abort run, don't save data, and automatically delete any files
        or folders generated. Also will move turbine and tow axes back
        to zero."""
        self.abort = True
        self.monitorni = False
        self.monitoracs = False
        self.monitorvec = False
        self.monitorfbg = False
        self.monitorodisi = False
        print("Automatically aborting current run")
        text = str(self.label_runstatus.text())
        self.label_runstatus.setText(text[:-13] + " autoaborted ")
        self.turbinetow.autoabort()
        self.run_in_progress = False

    def on_badvecdata(self):
        print("Bad Vectrino data detected")
        if abort_on_bad_vecdata:
            self.auto_abort()

    def do_shakedown(self):
        """Executes a single shakedown run."""
        U = self.ui.doubleSpinBox_singleRun_U.value()
        tsr = self.ui.doubleSpinBox_singleRun_tsr.value()
        turbine = self.ui.comboBox_turbine.currentText()
        y_R = self.ui.doubleSpinBox_singleRun_y_R.value()
        z_H = self.ui.doubleSpinBox_singleRun_z_H.value()
        vectrino = self.ui.checkBox_singleRunVectrino.isChecked()
        fbg = self.ui.checkBox_singleRunFBG.isChecked()
        odisi = self.ui.checkBox_singleRunODiSI.isChecked()
        self.savedir = os.path.join(self.wdir, "data", "raw", "shakedown")
        if not os.path.isdir(self.savedir):
            os.makedirs(self.savedir)
        runsdone = os.listdir(self.savedir)
        if len(runsdone) == 0:
            self.currentrun = 0
        else:
            self.currentrun = np.max([int(run) for run in runsdone]) + 1
        self.currentname = "Shakedown run " + str(self.currentrun)
        self.label_runstatus.setText(self.currentname + " in progress ")
        self.savesubdir = os.path.join(self.savedir, str(self.currentrun))
        os.mkdir(self.savesubdir)
        self.do_turbine_tow(
            U=U,
            tsr=tsr,
            y_R=y_R,
            z_H=z_H,
            turbine=turbine,
            vectrino=vectrino,
            fbg=fbg,
            odisi=odisi,
        )

    def do_test_plan(self):
        """Continue test plan"""
        section = str(self.ui.comboBox_testPlanSection.currentText())
        self.section = section
        if not self.is_section_done(section):
            print("Continuing", section)
            # Find next run to do by looking in the Done? column
            nruns = self.ui.tableWidgetTestPlan.rowCount()
            donecol = self.ui.tableWidgetTestPlan.columnCount() - 1
            for n in range(nruns):
                doneval = self.ui.tableWidgetTestPlan.item(n, donecol).text()
                if doneval == "No":
                    nextrun = int(
                        float(self.ui.tableWidgetTestPlan.item(n, 0).text())
                    )
                    break
            print("Starting run", str(nextrun))
            self.savedir = os.path.join(self.wdir, "data", "raw", section)
            self.currentrun = nextrun
            self.currentname = section + " run " + str(nextrun)
            self.label_runstatus.setText(self.currentname + " in progress ")
            if not os.path.isdir(self.savedir):
                os.makedirs(self.savedir)
            self.savesubdir = os.path.join(self.savedir, str(nextrun))
            try:
                os.mkdir(self.savesubdir)
            except WindowsError:
                print("Save subdirectory already exists")
                print("Files will be overwritten")
            # Get parameters from test plan
            run_props = self.test_plan[section]
            run_props = run_props[run_props.run == nextrun].iloc[0]
            if "tare" in section.lower() and "drag" in section.lower():
                self.do_tare_drag_tow(run_props.tow_speed)
            elif "tare" in section.lower() and "torque" in section.lower():
                rpm = run_props.rpm
                revs = run_props.revs
                dur = revs / rpm * 60
                self.do_tare_torque_run(rpm, dur)
            elif "strut" in section.lower() and "torque" in section.lower():
                if "turbine" in run_props:
                    turbine = run_props.turbine
                else:
                    turbine = self.turbine_properties.keys()[0]
                ref_speed = run_props.ref_speed
                tsr = run_props.tsr
                radius = self.turbine_properties[turbine]["radius"]
                revs = run_props.revs
                self.do_strut_torque_run(ref_speed, tsr, radius, revs)
            else:
                # Do turbine tow
                U = run_props.tow_speed
                tsr = run_props.tsr
                if "turbine" in run_props:
                    turbine = run_props["turbine"]
                else:
                    turbine = list(self.turbine_properties.keys())[0]
                if "vectrino" in run_props:
                    vectrino = run_props.vectrino
                else:
                    vectrino = True
                if vectrino:
                    y_R = run_props["y/R"]
                    z_H = run_props["z/H"]
                else:
                    y_R = z_H = None
                try:
                    fbg = run_props["fbg"]
                except KeyError:
                    fbg = False
                try:
                    odisi = run_props["odisi"]
                except KeyError:
                    odisi = False
                settling = "settling" in section.lower()
                self.do_turbine_tow(
                    U=U,
                    tsr=tsr,
                    y_R=y_R,
                    z_H=z_H,
                    vectrino=vectrino,
                    turbine=turbine,
                    fbg=fbg,
                    odisi=odisi,
                    settling=settling,
                )
        else:
            print("'{}' is done".format(section))
            self.ui.actionStart.trigger()

    def do_turbine_tow(
        self,
        U: float,
        tsr: float,
        y_R: float,
        z_H: float,
        turbine: str,
        vectrino=True,
        fbg=False,
        odisi=False,
        settling=False,
    ):
        """Executes a single turbine tow."""
        if acsc.getMotorState(self.hc, 5)["enabled"]:
            self.abort = False
            vecsavepath = os.path.join(self.savesubdir, "vecdata")
            turbine_properties = self.turbine_properties[turbine]
            self.turbinetow = runtypes.TurbineTow(
                acs_ntm_hcomm=self.hc,
                U=U,
                tsr=tsr,
                y_R=y_R,
                z_H=z_H,
                nidaq=True,
                vectrino=vectrino,
                vecsavepath=vecsavepath,
                turbine_properties=turbine_properties,
                fbg=fbg,
                fbg_properties=self.fbg_properties,
                odisi=odisi,
                odisi_properties=self.odisi_properties,
                settling=settling,
                vec_salinity=self.vec_salinity,
            )
            self.turbinetow.towfinished.connect(self.on_tow_finished)
            self.turbinetow.metadata["Name"] = self.currentname
            self.turbinetow.metadata["Turbine"] = turbine_properties
            self.turbinetow.metadata["Turbine"]["name"] = turbine
            self.acsdata = self.turbinetow.acsdaqthread.data
            self.nidata = self.turbinetow.daqthread.data
            if vectrino:
                self.vecdata = self.turbinetow.vec.data
            if fbg:
                self.fbgdata = self.turbinetow.fbgdata
                self.fbgs = self.turbinetow.fbgthread.interr.sensors
            # if odisi:
            #     self.odisidata = self.turbinetow.odisidata
            self.run_in_progress = True
            self.monitoracs = True
            self.monitorni = True
            self.monitorvec = vectrino
            self.monitorfbg = fbg
            self.monitorodisi = odisi
            self.turbinetow.start()
        else:
            print("Cannot start turbine tow because axis is disabled")
            text = str(self.label_runstatus.text()).split()
            text = " ".join(text[:3])
            self.label_runstatus.setText(text + " cannot start ")
            self.ui.actionStart.trigger()
            msg = "Run cannot start because the tow axis is disabled."
            QMessageBox.information(self, "Cannot Start", msg)

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
        self.monitorodisi = False
        self.run_in_progress = True
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
        self.monitorodisi = True
        self.monitorvec = False
        self.run_in_progress = True
        self.tarerun.start()

    def do_strut_torque_run(self, ref_speed, tsr, radius, revs):
        """Executes a single strut torque run."""
        self.tarerun = runtypes.StrutTorqueRun(
            self.hc, ref_speed, tsr, radius, revs
        )
        self.tarerun.runfinished.connect(self.on_tare_run_finished)
        self.tarerun.metadata["Name"] = self.currentname
        self.acsdata = self.tarerun.acsdata
        self.nidata = self.tarerun.nidata
        self.monitorni = True
        self.monitoracs = True
        self.monitorvec = False
        self.monitorodisi = False
        self.run_in_progress = True
        self.tarerun.start()

    def on_tare_run_finished(self):
        """
        Once a tare run is complete, saves data if necessary and updates
        the test plan table widget.
        """
        # Reset time of last run
        self.run_in_progress = False
        self.monitoracs = False
        self.monitorni = False
        self.monitorfbg = False
        self.monitorodisi = False
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
                json.dump(self.tarerun.metadata, fn, indent=4, default=str)
            text = str(self.label_runstatus.text())
            if "in progress" in text:
                self.label_runstatus.setText(text[:-13] + " saved ")
            print("Saved")
        elif self.tarerun.aborted:
            quit_msg = "Delete files from aborted run?"
            reply = QMessageBox.question(
                self, "Run Aborted", quit_msg, QMessageBox.Yes, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
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
                    if (
                        "strut" in self.section.lower()
                        and "torque" in self.section.lower()
                    ):
                        idlesec = 30
                    else:
                        idlesec = 5
                elif U <= 0.6:
                    idlesec = 30
                elif U <= 1.0:
                    idlesec = 60
                elif U <= 1.1:
                    idlesec = 90
                else:
                    idlesec = 120
                print("Waiting " + str(idlesec) + " seconds until next run")
                QtCore.QTimer.singleShot(idlesec * 1000, self.on_idletimer)
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
        self.run_in_progress = False
        self.monitoracs = False
        self.monitorni = False
        self.monitorvec = False
        self.monitorfbg = False
        self.monitorodisi = False
        self.time_last_run = time.time()
        # Save data from the run that just finished
        savedir = self.savesubdir
        if not self.turbinetow.aborted and not self.turbinetow.autoaborted:
            # Create directory and save the data inside
            print("Saving to " + savedir)
            nidata = dict(self.nidata)
            if "turbine_rpm" in nidata:
                del nidata["turbine_rpm"]
            self.save_raw_data(savedir, "acsdata.h5", self.acsdata)
            self.save_raw_data(savedir, "nidata.h5", nidata)
            if self.turbinetow.vectrino:
                self.save_raw_data(savedir, "vecdata.h5", self.vecdata)
            if self.turbinetow.fbg:
                self.save_raw_data(savedir, "fbgdata.h5", self.fbgdata)
            # if self.turbinetow.odisi:
            #     self.save_raw_data(savedir, "odisidata.h5", self.odisidata)
            with open(os.path.join(savedir, "metadata.json"), "w") as fn:
                json.dump(self.turbinetow.metadata, fn, indent=4, default=str)
            text = str(self.label_runstatus.text())
            if "in progress" in text:
                self.label_runstatus.setText(text[:-13] + " saved ")
            print("Saved")
            if self.autoprocess:
                section = self.section
                nrun = str(self.currentrun)
                print("Autoprocessing", section, "run", nrun)
                pycmd = (
                    "from py_package import processing; "
                    + "print(processing.process_run('{}',{}))".format(
                        section, nrun
                    )
                )
                cmdlist = ["cd", "/D", self.wdir, "&", "python", "-c", pycmd]
                subprocess.call(cmdlist, shell=True)
        elif self.turbinetow.aborted:
            quit_msg = "Delete files from aborted run?"
            reply = QMessageBox.question(
                self, "Run Aborted", quit_msg, QMessageBox.Yes, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                shutil.rmtree(self.savesubdir)
        elif self.turbinetow.autoaborted:
            print("Deleting files from aborted run")
            shutil.rmtree(self.savesubdir)
        # Update test plan table
        self.test_plan_into_table()
        # If executing a test plan start a single shot timer for next run
        if self.ui.tabTestPlan.isVisible():
            if self.ui.actionStart.isChecked():
                if self.turbinetow.autoaborted or self.turbinetow.settling:
                    idlesec = 5
                else:
                    tow_speed = self.turbinetow.U
                    stpath = os.path.join(
                        self.wdir, "config", "settling_times.csv"
                    )
                    stdf = pd.read_csv(stpath)
                    f_interp = scipy.interpolate.interp1d(
                        stdf.tow_speed, stdf.settling_time
                    )
                    idlesec = f_interp(tow_speed)
                print("Waiting " + str(idlesec) + " seconds until next run")
                QtCore.QTimer.singleShot(
                    int(idlesec * 1000), self.on_idletimer
                )
                # Scroll test plan so completed run is in view
                try:
                    i = int(self.currentrun) + 1
                    cr = self.ui.tableWidgetTestPlan.item(i, 0)
                    self.ui.tableWidgetTestPlan.scrollToItem(cr)
                except:
                    pass
        else:
            if not self.abort:
                self.ui.actionStart.trigger()
        self.vecdata = {}
        self.nidata = {}
        self.acsdata = {}
        self.fbgdata = {}
        # self.odisidata = {}

    def on_idletimer(self):
        if self.ui.actionStart.isChecked():
            self.do_test_plan()

    def on_monitor_acs(self):
        if self.ui.actionMonitor_ACS.isChecked():
            if self.mode == "CFT":
                self.acsthread = daqtasks.AcsDaqThread(self.hc, makeprg=True)
            else:
                self.acsthread = daqtasks.AftAcsDaqThread(
                    self.hc, makeprg=True
                )
            self.acsdata = self.acsthread.data
            self.acsthread.start()
            self.monitoracs = True
        else:
            self.acsthread.stop()
            self.monitoracs = False

    def on_monitor_ni(self):
        if self.ui.actionMonitor_NI.isChecked():
            if self.mode == "CFT":
                self.daqthread = daqtasks.NiDaqThread(usetrigger=False)
            else:
                self.daqthread = daqtasks.AftNiDaqThread(usetrigger=False)
            self.nidata = self.daqthread.data
            self.daqthread.start()
            self.monitorni = True
        else:
            self.daqthread.clear()
            self.monitorni = False

    def on_monitor_vec(self):
        if self.ui.actionMonitor_Vectrino.isChecked():
            self.vecthread = vectasks.VectrinoThread(
                usetrigger=False,
                maxvel=0.5,
                record=False,
                salinity=self.vec_salinity,
            )
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
            self.fbgs = self.fbgthread.interr.sensors
            self.fbgthread.start()
            self.monitorfbg = True
        else:
            self.fbgthread.stop()
            self.monitorfbg = False

    def on_monitor_odisi(self):
        if self.ui.actionMonitor_ODiSI.isChecked():
            odisi_props = self.odisi_properties
            self.odisithread = daqtasks.ODiSIDaqThread(odisi_props)
            # self.odisidata = self.odisithread.data
            self.odisithread.start()
            self.monitorodisi = True
        else:
            self.odisithread.stop()
            self.monitorodisi = False

    def on_checkbox_tow_axis(self):
        if self.checkbox_tow_axis.isChecked():
            acsc.enable(self.hc, 5)
        else:
            acsc.disable(self.hc, 5)

    def on_checkbox_turbine_axis(self):
        if self.checkbox_turbine_axis.isChecked():
            acsc.enable(self.hc, 4)
        else:
            acsc.disable(self.hc, 4)

    def on_checkbox_y_axis(self):
        if self.checkbox_y_axis.isChecked():
            acsc.enable(self.hc, 0)
        else:
            acsc.disable(self.hc, 0)

    def on_checkbox_z_axis(self):
        if self.checkbox_z_axis.isChecked():
            acsc.enable(self.hc, 1)
        else:
            acsc.disable(self.hc, 1)

    def on_checkbox_aft_axis(self):
        if self.checkbox_aft_axis.isChecked():
            acsc.enable(self.hc, 6)
        else:
            acsc.disable(self.hc, 6)

    def on_timer(self):
        self.update_acs()
        self.time_since_last_run = time.time() - self.time_last_run
        self.label_timer.setText(
            "Time since last run: "
            + str(int(self.time_since_last_run))
            + " s "
        )

    def on_plot_timer(self):
        if self.monitoracs:
            self.update_plots_acs()
            self.update_plots_aft()
        if self.monitorvec:
            self.update_plots_vec()
            try:
                if not self.run_in_progress:
                    self.label_vecstatus.setText(self.vecthread.vecstatus)
                else:
                    self.label_vecstatus.setText(self.turbinetow.vecstatus)
            except AttributeError:
                pass
        if self.monitorni:
            self.update_plots_ni()
        if self.monitorfbg:
            self.update_plots_fbg()
        # if self.monitorodisi:
        #     self.update_plots_odisi()

    def on_process(self):
        section = str(self.ui.comboBox_process_section.currentText())
        nrun = str(self.ui.comboBox_process_nrun.currentText())
        print(
            "Working on processing in {} on section {} run {}. ".format(
                self.wdir, section, nrun
            )
        )
        subprocess.call(
            [
                "cd",
                self.wdir,
                "&",
                "python",
                self.wdir + "/processing.py",
                section,
                nrun,
            ],
            shell=True,
        )

    def update_plots_acs(self):
        """Update the acs plots for carriage speed, rpm, and tsr"""
        t = self.acsdata["time"]
        self.curve_acs_carvel.set_data(t, self.acsdata["carriage_vel"])
        self.plot_acs_carvel.replot()
        self.curve_acs_rpm.set_data(t, self.acsdata["turbine_rpm"])
        self.plot_acs_rpm.replot()

    def update_plots_ni(self):
        t = self.nidata["time"]
        if "drag_left" in self.nidata:
            self.curve_drag_left.set_data(t, self.nidata["drag_left"])
            self.plot_drag_left.replot()
            self.curve_torque_trans.set_data(t, self.nidata["torque_trans"])
            self.curve_torque_arm.set_data(t, self.nidata["torque_arm"])
            self.plot_torque.replot()
            self.curve_drag_right.set_data(t, self.nidata["drag_right"])
            self.plot_drag_right.replot()
            if len(self.nidata["drag_left"]) == len(self.nidata["drag_right"]):
                self.curve_drag.set_data(
                    t, self.nidata["drag_left"] + self.nidata["drag_right"]
                )
                self.plot_drag.replot()
            self.curve_rpm_ni.set_data(t, self.nidata["turbine_rpm"])
            self.plot_rpm_ni.replot()
            self.curve_LF_left.set_data(t, self.nidata["LF_left"])
            self.curve_LF_right.set_data(t, self.nidata["LF_right"])
            self.plot_LF.replot()
        elif "resistor_temp" in self.nidata:
            # Create a list of keys in order of the plots
            signals = [
                "resistor_temp",
                "yaskawa_temp",
                "fore_temp",
                "aft_temp",
            ]
            for n, signal in enumerate(signals):
                n_plot = n + 1  # These are 1-indexed per their names
                curve = getattr(self, f"curve_aft_ni_{n_plot}")
                curve.set_data(t, self.nidata[signal])
                plot = getattr(self, f"plot_aft_ni_{n_plot}")
                plot.replot()

    def update_plots_vec(self):
        """This function updates the Vectrino plots."""
        t = self.vecdata["time"]
        if len(t) > 400 and len(t) < 600 and self.run_in_progress:
            if len(np.where(np.abs(self.vecdata["v"][:450]) > 0.5)[0]) > 50:
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
        for fbg, curve in zip(self.fbgs, self.fbg_curves):
            curve.set_data(t, self.fbgdata[fbg.name + "_strain"])
        for plot in self.fbg_plot_list:
            plot.replot()

    # def update_plots_odisi(self):
    #     """This function updates the ODiSI plots."""
    #     t = self.odisidata["time"]
    #     self.curve_odisi.set_data(t, self.odisidata[odisi.name + "_strain"])
    #     self.plot_odisi.replot()

    def update_plots_aft(self):
        """Update AFT plots."""
        t = self.acsdata["time"]
        for channel in [1, 2, 3, 4]:
            curve = getattr(self, f"curve_aft_{channel}")
            plot = getattr(self, f"plot_aft_{channel}")
            data = self.acsdata[f"load_cell_ch{channel}"]
            curve.set_data(t, data)
            plot.replot()

    def update_acs(self):
        """Update all the non-time-critical ACS controller data."""
        if self.hc is None:
            return
        self.checkbox_y_axis.setChecked(
            acsc.getMotorState(self.hc, 0)["enabled"]
        )
        self.checkbox_z_axis.setChecked(
            acsc.getMotorState(self.hc, 1)["enabled"]
        )
        self.checkbox_turbine_axis.setChecked(
            acsc.getMotorState(self.hc, 4)["enabled"]
        )
        self.checkbox_tow_axis.setChecked(
            acsc.getMotorState(self.hc, 5)["enabled"]
        )
        self.checkbox_aft_axis.setChecked(
            acsc.getMotorState(self.hc, 6)["enabled"]
        )
        # Put this data into table widget
        try:
            hc_tow = acsc.readInteger(self.hc, acsc.NONE, "homeCounter_tow")
        except acsc.AcscError:
            hc_tow = 0
        try:
            hc_turbine = acsc.readInteger(
                self.hc, acsc.NONE, "homeCounter_AKD"
            )
        except acsc.AcscError:
            hc_turbine = 0
        try:
            hc_y = acsc.readInteger(self.hc, acsc.NONE, "homeCounter_y")
        except acsc.AcscError:
            hc_y = 0
        try:
            hc_z = acsc.readInteger(self.hc, acsc.NONE, "homeCounter_z")
        except acsc.AcscError:
            hc_z = 0
        try:
            hc_aft = acsc.readInteger(self.hc, acsc.NONE, "homeCounter_AFT")
        except acsc.AcscError:
            hc_aft = 0
        self.ui.tableWidget_acs.item(0, 2).setText(str(hc_tow))
        self.ui.tableWidget_acs.item(1, 2).setText(str(hc_turbine))
        self.ui.tableWidget_acs.item(2, 2).setText(str(hc_y))
        self.ui.tableWidget_acs.item(3, 2).setText(str(hc_z))
        self.ui.tableWidget_acs.item(4, 2).setText(str(hc_aft))
        # Set reference position text
        self.ui.tableWidget_acs.item(0, 3).setText(
            str(acsc.getRPosition(self.hc, 5))
        )
        self.ui.tableWidget_acs.item(1, 3).setText(
            str(acsc.getRPosition(self.hc, 4))
        )
        self.ui.tableWidget_acs.item(2, 3).setText(
            str(acsc.getRPosition(self.hc, 0))
        )
        self.ui.tableWidget_acs.item(3, 3).setText(
            str(acsc.getRPosition(self.hc, 1))
        )
        self.ui.tableWidget_acs.item(4, 3).setText(
            str(acsc.getRPosition(self.hc, 6))
        )
        # Set feedback position text
        self.ui.tableWidget_acs.item(0, 4).setText(
            str(acsc.getFPosition(self.hc, 5))
        )
        self.ui.tableWidget_acs.item(1, 4).setText(
            str(acsc.getFPosition(self.hc, 4))
        )
        self.ui.tableWidget_acs.item(2, 4).setText(
            str(acsc.getFPosition(self.hc, 0))
        )
        self.ui.tableWidget_acs.item(3, 4).setText(
            str(acsc.getFPosition(self.hc, 1))
        )
        self.ui.tableWidget_acs.item(4, 4).setText(
            str(acsc.getFPosition(self.hc, 6))
        )
        # Set feedback velocity text
        self.ui.tableWidget_acs.item(0, 5).setText(
            str(acsc.getFVelocity(self.hc, 5))
        )
        self.ui.tableWidget_acs.item(1, 5).setText(
            str(acsc.getFVelocity(self.hc, 4))
        )
        self.ui.tableWidget_acs.item(2, 5).setText(
            str(acsc.getFVelocity(self.hc, 0))
        )
        self.ui.tableWidget_acs.item(3, 5).setText(
            str(acsc.getFVelocity(self.hc, 1))
        )
        self.ui.tableWidget_acs.item(4, 5).setText(
            str(acsc.getFVelocity(self.hc, 6))
        )

    def save_raw_data(self, savedir, fname, datadict, verbose=True):
        """Saves a dict of raw data in HDF5 format."""
        fpath = os.path.join(savedir, fname)
        if verbose:
            print("Saving {} to {}".format(fname, savedir))
        if not os.path.isdir(savedir):
            os.makedirs(savedir)
        ts.savehdf(fpath, datadict)

    def closeEvent(self, event):
        self.settings["Last working directory"] = self.wdir
        self.settings["Last window location"] = [
            self.pos().x(),
            self.pos().y(),
        ]
        self.settings["Last section index"] = (
            self.ui.comboBox_testPlanSection.currentIndex()
        )
        self.settings["Last tab index"] = self.ui.tabWidgetMode.currentIndex()
        self.settings["Last PC name"] = self.pcid
        self.settings["Last size"] = (
            self.size().height(),
            self.size().width(),
        )
        self.settings["NI visible"] = self.ui.dockWidgetNISignals.isVisible()
        self.settings["FBG visible"] = self.ui.dockWidget_FBG.isVisible()
        self.settings["ODiSI visible"] = self.ui.dockWidget_ODiSI.isVisible()
        self.settings["AFT visible"] = self.dockWidget_AFT.isVisible()
        self.settings["AFT NI visible"] = self.dockwidget_aft_ni.isVisible()
        self.settings["Lateral forces visible"] = (
            self.ui.dockWidget_LF.isVisible()
        )
        self.settings["Shakedown ODiSI"] = (
            self.ui.checkBox_singleRunODiSI.isChecked()
        )
        # TODO: Checkbox below does not exist
        # self.settings[
        #     "Shakedown lateral forces"
        # ] = self.ui.checkBox_singleRunLF.isChecked()
        self.settings["Vectrino visible"] = (
            self.ui.dockWidgetVectrino.isVisible()
        )
        self.settings["Shakedown tow speed"] = (
            self.ui.doubleSpinBox_singleRun_U.value()
        )
        self.settings["Shakedown turbine"] = (
            self.ui.comboBox_turbine.currentText()
        )
        self.settings["Shakedown TSR"] = (
            self.ui.doubleSpinBox_singleRun_tsr.value()
        )
        self.settings["Shakedown y/R"] = (
            self.ui.doubleSpinBox_singleRun_y_R.value()
        )
        self.settings["Shakedown z/H"] = (
            self.ui.doubleSpinBox_singleRun_z_H.value()
        )
        self.settings["Shakedown Vectrino"] = (
            self.ui.checkBox_singleRunVectrino.isChecked()
        )
        self.settings["Shakedown FBG"] = (
            self.ui.checkBox_singleRunFBG.isChecked()
        )
        self.settings["Mode"] = self.mode
        settings_dir = os.path.dirname(self.settings_fpath)
        print("Saving settings:", self.settings)
        if not os.path.isdir(settings_dir):
            os.mkdir(settings_dir)
        with open(self.settings_fpath, "w") as fn:
            json.dump(self.settings, fn, indent=4, default=str)
        acsc.closeComm(self.hc)
        self.hc = None
        if self.monitorni and not self.run_in_progress:
            self.daqthread.clear()
        if self.monitorvec and not self.run_in_progress:
            self.vecthread.stop()
        if self.monitorfbg and not self.run_in_progress:
            self.fbgthread.stop()
        if self.monitorodisi and not self.run_in_progress:
            self.odisithread.stop()


def main():
    import sys

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
