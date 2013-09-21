# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 10:51:28 2013

@author: Pete

This module contains the DAQ stuff for TurbineDAQ

"""
from PyQt4 import QtCore
import numpy as np
from daqmx import daqmx
import time
import json
from scipy.io import savemat
from acspy import acsc, prgs


class TurbineTowDAQ(QtCore.QThread):
    collecting = QtCore.pyqtSignal()
    finished = QtCore.pyqtSignal()
    def __init__(self, usetrigger=True):
        QtCore.QThread.__init__(self)
        
        # Some parameters for the thread
        self.usetrigger = usetrigger
        
        # Crete some meta data for the run
        self.timecreated = time.asctime()
        self.metadata = {"Time created" : self.timecreated}
        
        # Initialize sample rate
        self.sr = 2000.0
        self.metadata["Sample rate (Hz)"] = self.sr
        
        # Create a dict of arrays for storing data
        # Probably should be based on global channel names...
        self.data = {"carriage_pos" : np.array([]),
                     "turbine_angle" : np.array([]),
                     "turbine_rpm" : np.array([]),
                     "torque_trans": np.array([]),
                     "torque_arm" : np.array([]),
                     "drag_left" : np.array([]),
                     "drag_right" : np.array([]),
                     "t" : np.array([])}
        
        # Create one analog and one digital task
        # Probably should be a bridge task in there too!
        self.analogtask = daqmx.TaskHandle()
        self.carpostask = daqmx.TaskHandle()
        self.turbangtask = daqmx.TaskHandle()
        
        # Create tasks
        daqmx.CreateTask("", self.analogtask)
        daqmx.CreateTask("", self.carpostask)
        daqmx.CreateTask("", self.turbangtask)
        
        # Add channels to tasks -- rename global channels
        self.analogchans = ["torque_trans", "torque_arm", 
                            "drag_left", "drag_right"]
        self.carposchan = "carriage_pos"
        self.turbangchan = "turbine_angle"
        daqmx.AddGlobalChansToTask(self.analogtask, self.analogchans)
        daqmx.AddGlobalChansToTask(self.carpostask, self.carposchan)
        daqmx.AddGlobalChansToTask(self.turbangtask, self.turbangchan)
        self.metadata["Global analog channels"] = self.analogchans
        self.metadata["Global counter channels"] = [self.carposchan,
                                                    self.turbangchan]

        # Get channel information to add to metadata
        self.chaninfo = {}
        for channame in self.analogchans:
            self.chaninfo[channame] = {}
            scale = daqmx.GetAICustomScaleName(self.analogtask, channame)
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
                               int(self.sr/10))   
        # Get source for analog sample clock
        trigname = daqmx.GetTerminalNameWithDevPrefix(self.analogtask,
                                                      "ai/SampleClock")
        daqmx.CfgSampClkTiming(self.carpostask, trigname, self.sr,
                               daqmx.Val_Rising, daqmx.Val_ContSamps,
                               int(self.sr/10))
        daqmx.CfgSampClkTiming(self.turbangtask, trigname, self.sr,
                               daqmx.Val_Rising, daqmx.Val_ContSamps,
                               int(self.sr/10))
                               
        # Set trigger functions for counter channels
        daqmx.SetStartTrigType(self.carpostask, daqmx.Val_DigEdge)
        daqmx.SetStartTrigType(self.turbangtask, daqmx.Val_DigEdge)
        trigsrc = \
        daqmx.GetTrigSrcWithDevPrefix(self.analogtask, "ai/StartTrigger")
        daqmx.SetDigEdgeStartTrigSrc(self.carpostask, trigsrc)
        daqmx.SetDigEdgeStartTrigSrc(self.turbangtask, trigsrc)
        daqmx.SetDigEdgeStartTrigEdge(self.carpostask, daqmx.Val_Rising)
        daqmx.SetDigEdgeStartTrigEdge(self.turbangtask, daqmx.Val_Rising)
        
        
    def set_analog_trigger(self):
        """Sets the analog signals to be triggered from the chassis PFI"""
        # Setup trigger for analog channels
        

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
            data, npoints = daqmx.ReadAnalogF64(taskHandle, int(self.sr/10), 
                    10.0, daqmx.Val_GroupByChannel, int(self.sr/10), 
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
                                                   int(self.sr/10), 10.0,
                                                   int(self.sr/10))
            self.data["carriage_pos"] = np.append(self.data["carriage_pos"],
                                                  carpos)  
            turbang, cpoints = daqmx.ReadCounterF64(self.turbangtask,
                                                    int(self.sr/10), 10.0,
                                                    int(self.sr/10))
            self.data["turbine_angle"] = np.append(self.data["turbine_angle"],
                                                   turbang)
            if len(self.data["t"]) > 1:
                rpm = (turbang - self.data["turbine_angle"][-2])*self.sr/6
            else: 
                rpm = 0.0
                print "Zero rpm"
            self.data["turbine_rpm"] = np.append(self.data["turbine_rpm"],
                                                 rpm)                                                 
            return 0 # The function should return an integer
            
        # Convert the python callback function to a CFunction
        EveryNCallback = daqmx.EveryNSamplesEventCallbackPtr(EveryNCallback_py)
        daqmx.RegisterEveryNSamplesEvent(self.analogtask, 
                daqmx.Val_Acquired_Into_Buffer, int(self.sr/10), 0, 
                EveryNCallback, id_data)    
        def DoneCallback_py(taskHandle, status, callbackData_ptr):
            print "Status", status.value
            return 0
        DoneCallback = daqmx.DoneEventCallbackPtr(DoneCallback_py)
        daqmx.RegisterDoneEvent(self.analogtask, 0, DoneCallback, None) 

        # Start the tasks
        daqmx.StartTask(self.analogtask)
#        daqmx.StartTask(self.carpostask)
#        daqmx.StartTask(self.turbangtask)
        self.collecting.emit()

        # Keep the acquisition going until task it cleared
        while True:
            pass
    
    def savedata(self):
        savedir = "test/"
#        fmdata = open(savedir+self.name+".json", "w")
        json.dump(self.metadata, fmdata)
        fmdata.close()
#        savemat(savedir+self.name, self.data)
        
    def stopdaq(self):
        daqmx.StopTask(self.analogtask)
        daqmx.StopTask(self.carpostask)
        daqmx.StopTask(self.turbangtask)
    
    def clear(self):
        self.stopdaq()
        daqmx.ClearTask(self.analogtask)
        daqmx.ClearTask(self.carpostask)
        daqmx.ClearTask(self.turbangtask)
        self.finished.emit()

class TareTorqueDAQ(QtCore.QThread):
    pass

class TareDragDAQ(QtCore.QThread):
    pass

class AcsDaqThread(QtCore.QThread):
    def __init__(self, acs_hc):
        QtCore.QThread.__init__(self)
        self.hc = acs_hc
        self.collectdata = True
        self.data = {"carriage_vel" : np.array([]),
                     "turbine_rpm" : np.array([]),
                     "turbine_tsr" : np.array([]),
                     "t" : np.array([])}
        self.dblen = 100
        self.sr = 200.0
        self.sleeptime = self.dblen/self.sr/2*1.05
        # Create an ACSPL+ program to load into the controller
        self.prg = prgs.ACSPLplusPrg()
        self.prg.declare_2darray("global", "real", "data", 3, self.dblen)
        self.prg.addline("GLOBAL INT collect_data")
        self.prg.addline("collect_data = 1")
        self.prg.add_dc("data", self.dblen, self.sr, "TIME, FVEL(5), FVEL(4)", "/c")
        self.prg.addline("TILL collect_data = 0")
        self.prg.addline("STOPDC")
        self.prg.addstopline()
    def run(self):
        acsc.loadBuffer(self.hc, 20, self.prg, 1024)
        acsc.runBuffer(self.hc, 20)
        while self.collectdata:
            time.sleep(self.sleeptime)
            newdata = acsc.readReal(self.hc, acsc.NONE, "data", 0, 2, 0, self.dblen/2-1)
            self.data["t"] = np.append(self.data["t"], newdata[0])
            self.data["carriage_vel"] = np.append(self.data["carriage_vel"], newdata[1])
            self.data["turbine_rpm"] = np.append(self.data["turbine_rpm"], newdata[2])
            time.sleep(self.sleeptime)
            newdata = acsc.readReal(self.hc, acsc.NONE, "data", 0, 2, self.dblen/2, self.dblen-1)
            self.data["t"] = np.append(self.data["t"], newdata[0])
            self.data["carriage_vel"] = np.append(self.data["carriage_vel"], newdata[1])
            self.data["turbine_rpm"] = np.append(self.data["turbine_rpm"], newdata[2])
    def stop(self):
        self.collectdata = False
        acsc.writeInteger(self.hc, "collect_data", 0)

def main():
    turbdaq = TurbineTowDAQ("run2_yz32")
    turbdaq.start()
    time.sleep(1.1)
    turbdaq.savedata()
    turbdaq.cleartasks()
    return turbdaq.data

if __name__ == "__main__":
    data = main()