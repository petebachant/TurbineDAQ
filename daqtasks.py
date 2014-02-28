# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 10:51:28 2013

@author: Pete

This module contains the DAQ stuff for TurbineDAQ

"""
from PyQt4 import QtCore
import numpy as np
import daqmx
import time
from acspy import acsc, prgs
import fdiff
import timeseries as ts

class NiDaqThread(QtCore.QThread):
    collecting = QtCore.pyqtSignal()
    cleared = QtCore.pyqtSignal()
    def __init__(self, usetrigger=True):
        QtCore.QThread.__init__(self)
        
        # Some parameters for the thread
        self.usetrigger = usetrigger
        
        # Create some meta data for the run
        self.metadata = {}
        
        # Initialize sample rate
        self.sr = 2000.0
        self.metadata["Sample rate (Hz)"] = self.sr
        self.nsamps = int(self.sr/10)
        
        # Create a dict of arrays for storing data
        self.data = {"turbine_angle" : np.array([]),
                     "turbine_rpm" : np.array([]),
                     "torque_trans": np.array([]),
                     "torque_arm" : np.array([]),
                     "drag_left" : np.array([]),
                     "drag_right" : np.array([]),
                     "t" : np.array([]),
                     "carriage_pos" : np.array([])}
        # Create one analog and one digital task
        # Probably should be a bridge task in there too!
        self.analogtask = daqmx.TaskHandle()
        self.carpostask = daqmx.TaskHandle()
        self.turbangtask = daqmx.TaskHandle()
        
        # Create tasks
        daqmx.CreateTask("", self.analogtask)
        daqmx.CreateTask("", self.carpostask)
        daqmx.CreateTask("", self.turbangtask)
        
        # Add channels to tasks
        self.analogchans = ["torque_trans", "torque_arm", 
                            "drag_left", "drag_right"]
        self.carposchan = "carriage_pos"
        self.turbangchan = "turbine_angle"
        daqmx.AddGlobalChansToTask(self.analogtask, self.analogchans)
        daqmx.AddGlobalChansToTask(self.carpostask, self.carposchan)
        daqmx.AddGlobalChansToTask(self.turbangtask, self.turbangchan)

        # Get channel information to add to metadata
        self.chaninfo = {}
        for channame in self.analogchans:
            self.chaninfo[channame] = {}
            scale = channame + "_scale"
            self.chaninfo[channame]["Scale name"] = scale
            self.chaninfo[channame]["Scale slope"] = \
            daqmx.GetScaleLinSlope(scale)
            self.chaninfo[channame]["Scale y-intercept"] = \
            daqmx.GetScaleLinYIntercept(scale)
            self.chaninfo[channame]["Scaled units"] = \
            daqmx.GetScaleScaledUnits(scale)
            self.chaninfo[channame]["Prescaled units"] = \
            daqmx.GetScalePreScaledUnits(scale)
            
        self.chaninfo[self.turbangchan] = {}
        self.chaninfo[self.turbangchan]["Pulses per rev"] = \
        daqmx.GetCIAngEncoderPulsesPerRev(self.turbangtask, self.turbangchan)
        self.chaninfo[self.turbangchan]["Units"] = \
        daqmx.GetCIAngEncoderUnits(self.turbangtask, self.turbangchan)

        self.chaninfo[self.carposchan] = {}
        self.chaninfo[self.carposchan]["Distance per pulse"] = \
        daqmx.GetCILinEncoderDisPerPulse(self.carpostask, self.carposchan)
        self.chaninfo[self.carposchan]["Units"] = \
        daqmx.GetCILinEncoderUnits(self.carpostask, self.carposchan)
        self.metadata["Channel info"] = self.chaninfo
        
        # Configure sample clock timing
        daqmx.CfgSampClkTiming(self.analogtask, "", self.sr, 
                               daqmx.Val_Rising, daqmx.Val_ContSamps, 
                               self.nsamps)   
        # Get source for analog sample clock
        trigname = daqmx.GetTerminalNameWithDevPrefix(self.analogtask,
                                                      "ai/SampleClock")
        daqmx.CfgSampClkTiming(self.carpostask, trigname, self.sr,
                               daqmx.Val_Rising, daqmx.Val_ContSamps,
                               self.nsamps)
        daqmx.CfgSampClkTiming(self.turbangtask, trigname, self.sr,
                               daqmx.Val_Rising, daqmx.Val_ContSamps,
                               self.nsamps)
                               
        # If using trigger for analog signals set source to chassis PFI0
        if self.usetrigger:
            daqmx.CfgDigEdgeStartTrig(self.analogtask, "/cDAQ9188-16D66BB/PFI0",
                                      daqmx.Val_Falling)
                               
        # Set trigger functions for counter channels
        daqmx.SetStartTrigType(self.carpostask, daqmx.Val_DigEdge)
        daqmx.SetStartTrigType(self.turbangtask, daqmx.Val_DigEdge)
        trigsrc = \
        daqmx.GetTrigSrcWithDevPrefix(self.analogtask, "ai/StartTrigger")
        daqmx.SetDigEdgeStartTrigSrc(self.carpostask, trigsrc)
        daqmx.SetDigEdgeStartTrigSrc(self.turbangtask, trigsrc)
        daqmx.SetDigEdgeStartTrigEdge(self.carpostask, daqmx.Val_Rising)
        daqmx.SetDigEdgeStartTrigEdge(self.turbangtask, daqmx.Val_Rising)
        

    def run(self):
        """Start DAQmx tasks."""
        # Acquire and throwaway samples for alignment
        # Need to set these up on a different task?
        # Callback code from PyDAQmx
        class MyList(list):
            pass
        # List where the data are stored
        data = MyList()
        id_data = daqmx.create_callbackdata_id(data)
        
        def EveryNCallback_py(taskHandle, everyNsamplesEventType, nSamples, 
                              callbackData_ptr):
            """Function called every N samples"""
            callbackdata = daqmx.get_callbackdata_from_id(callbackData_ptr)
            data, npoints = daqmx.ReadAnalogF64(taskHandle, self.nsamps, 
                    10.0, daqmx.Val_GroupByChannel, self.nsamps, 
                    len(self.analogchans))
            callbackdata.extend(data.tolist())
            self.data["torque_trans"] = np.append(self.data["torque_trans"], 
                                                  data[:,0], axis=0)
            self.data["torque_arm"] = np.append(self.data["torque_arm"], 
                                                data[:,1], axis=0)
            self.data["drag_left"] = np.append(self.data["drag_left"], 
                                                data[:,2], axis=0)
            self.data["drag_right"] = np.append(self.data["drag_right"], 
                                                data[:,3], axis=0)
            self.data["t"] = np.arange(len(self.data["torque_trans"]), 
                                       dtype=float)/self.sr                                                
            carpos, cpoints = daqmx.ReadCounterF64(self.carpostask,
                                                   self.nsamps, 10.0,
                                                   self.nsamps)
            self.data["carriage_pos"] = np.append(self.data["carriage_pos"],
                                                  carpos)  
            turbang, cpoints = daqmx.ReadCounterF64(self.turbangtask,
                                                    self.nsamps, 10.0,
                                                    self.nsamps)
            self.data["turbine_angle"] = np.append(self.data["turbine_angle"],
                                                   turbang)
            self.data["turbine_rpm"] \
                = ts.smooth(fdiff.second_order_diff(self.data["turbine_angle"], 
                                          self.data["t"])/6.0, 50)
            return 0 # The function should return an integer
            
        # Convert the python callback function to a CFunction
        EveryNCallback = daqmx.EveryNSamplesEventCallbackPtr(EveryNCallback_py)
        daqmx.RegisterEveryNSamplesEvent(self.analogtask, 
                daqmx.Val_Acquired_Into_Buffer, self.nsamps, 0, 
                EveryNCallback, id_data)    
        def DoneCallback_py(taskHandle, status, callbackData_ptr):
            print "Status", status.value
            return 0
        DoneCallback = daqmx.DoneEventCallbackPtr(DoneCallback_py)
        daqmx.RegisterDoneEvent(self.analogtask, 0, DoneCallback, None) 

        # Start the tasks
        daqmx.StartTask(self.carpostask)
        daqmx.StartTask(self.turbangtask)
        daqmx.StartTask(self.analogtask)
        self.collecting.emit()

        # Keep the acquisition going until task it cleared
        while True:
            pass
        
    def stopdaq(self):
        daqmx.StopTask(self.analogtask)
        daqmx.StopTask(self.carpostask)
        daqmx.StopTask(self.turbangtask)
    
    def clear(self):
        self.stopdaq()
        daqmx.ClearTask(self.analogtask)
        daqmx.ClearTask(self.carpostask)
        daqmx.ClearTask(self.turbangtask)
        self.cleared.emit()

class TareTorqueDAQ(QtCore.QThread):
    pass

class TareDragDAQ(QtCore.QThread):
    pass

class AcsDaqThread(QtCore.QThread):
    def __init__(self, acs_hc, sample_rate=1000, bufflen=100, makeprg=False):
        QtCore.QThread.__init__(self)
        self.hc = acs_hc
        self.collectdata = True
        self.data = {"carriage_vel" : np.array([]),
                     "turbine_rpm" : np.array([]),
                     "t" : np.array([])}
        self.dblen = bufflen
        self.sr = sample_rate
        self.sleeptime = float(self.dblen)/float(self.sr)/2*1.05
        self.makeprg = makeprg
    def run(self):
        if self.makeprg:
            self.makedaqprg()
            acsc.loadBuffer(self.hc, 19, self.prg, 1024)
            acsc.runBuffer(self.hc, 19)
        collect = acsc.readInteger(self.hc, acsc.NONE, "collect_data")
        while collect == 0:
            time.sleep(0.01)
            collect = acsc.readInteger(self.hc, acsc.NONE, "collect_data")
        while self.collectdata:
            time.sleep(self.sleeptime)
            t0 = acsc.readReal(self.hc, acsc.NONE, "start_time")
            newdata = acsc.readReal(self.hc, acsc.NONE, "data", 0, 2, 0, self.dblen/2-1)
            t = (newdata[0] - t0)/1000.0
            self.data["t"] = np.append(self.data["t"], t)
            self.data["carriage_vel"] = np.append(self.data["carriage_vel"], newdata[1])
            self.data["turbine_rpm"] = np.append(self.data["turbine_rpm"], newdata[2])
            time.sleep(self.sleeptime)
            newdata = acsc.readReal(self.hc, acsc.NONE, "data", 0, 2, self.dblen/2, self.dblen-1)
            t = (newdata[0] - t0)/1000.0
            self.data["t"] = np.append(self.data["t"], t)
            self.data["t"] = self.data["t"] - self.data["t"][0]
            self.data["carriage_vel"] = np.append(self.data["carriage_vel"], newdata[1])
            self.data["turbine_rpm"] = np.append(self.data["turbine_rpm"], newdata[2])
    def makedaqprg(self):
        """Create an ACSPL+ program to load into the controller"""
        self.prg = prgs.ACSPLplusPrg()
        self.prg.declare_2darray("GLOBAL", "real", "data", 3, self.dblen)
        self.prg.addline("GLOBAL REAL start_time")
        self.prg.addline("GLOBAL INT collect_data")
        self.prg.addline("collect_data = 1")
        self.prg.add_dc("data", self.dblen, self.sr, "TIME, FVEL(5), FVEL(4)", "/c")
        self.prg.addline("start_time = TIME")        
        self.prg.addline("TILL collect_data = 0")
        self.prg.addline("STOPDC")
        self.prg.addstopline()
    def stop(self):
        self.collectdata = False
        try:
            acsc.writeInteger(self.hc, "collect_data", 0)
        except:
            print "Could not write collect_data = 0"


if __name__ == "__main__":
    spam = NiDaqThread(False)
    spam.clear()