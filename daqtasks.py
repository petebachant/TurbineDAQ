# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 10:51:28 2013

@author: Pete

This module contains the DAQ stuff for TurbineDAQ

"""

from PyQt4.QtCore import *
import numpy as np
import daqmx.daqmx as daqmx
import time
import json
from scipy.io import savemat


class TurbineTowDAQ(QThread):
    def __init__(self, name=None):
        QThread.__init__(self)
        
        # Crete some meta data for the run
        self.name = name
        self.timecreated = time.asctime()
        self.metadata = {"Name" : self.name,
                         "Time created" : self.timecreated}
        
        # Initialize sample rate
        self.sr = 2000.0
        self.metadata["Sample rate (Hz)"] = self.sr
        
        # Create a dict of arrays for storing data
        # Probably should be based on global channel names...
        self.data = {"carriage_pos": np.array([]),
                     "turbine_angle": np.array([]),
                     "torque_trans": np.array([]),
                     "torque_arm" : np.array([]),
                     "drag_left" : np.array([]),
                     "drag_right" : np.array([])}
        
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
        self.analogchans = ["Voltage"]
        self.carposchan = "LinEnc"
        self.turbangchan = "Angle"
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
        
        # Function that is called every N callback
        def EveryNCallback_py(taskHandle, everyNsamplesEventType, nSamples, 
                              callbackData_ptr):
                                  
            callbackdata = daqmx.get_callbackdata_from_id(callbackData_ptr)
            
            data, npoints = daqmx.ReadAnalogF64(taskHandle, int(self.sr/10), 
                    10.0, daqmx.Val_GroupByChannel, int(self.sr/10), 
                    len(self.analogchans))

            callbackdata.extend(data.tolist())
            self.data["torque_trans"] = np.append(self.data["torque_trans"], 
                                                  data[:,0], axis=0)
#            self.data["torque_arm"] = np.append(self.data["torque_arm"], 
#                                                data[:,1], axis=0)
                                                
            carpos, cpoints = daqmx.ReadCounterF64(self.carpostask,
                                                   int(self.sr/10), 10.0,
                                                   int(self.sr/10))
            turbang, cpoints = daqmx.ReadCounterF64(self.turbangtask,
                                                    int(self.sr/10), 10.0,
                                                    int(self.sr/10))


            self.data["carriage_pos"] = np.append(self.data["carriage_pos"],
                                                  carpos)
            self.data["turbine_angle"] = np.append(self.data["turbine_angle"],
                                                   turbang)                                                  
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
        daqmx.StartTask(self.carpostask)
        daqmx.StartTask(self.turbangtask)

        # Keep the acquisition going until task it cleared
        while True:
            pass
    
    
    def savedata(self):
        savedir = "test/"
        fmdata = open(savedir+self.name+".json", "w")
        json.dump(self.metadata, fmdata)
        fmdata.close()
        savemat(savedir+self.name, self.data)
    
    def cleartasks(self):
        daqmx.ClearTask(self.analogtask)
        daqmx.ClearTask(self.carpostask)
        daqmx.ClearTask(self.turbangtask)
        

def main():
    turbdaq = TurbineTowDAQ("run2_yz32")
    turbdaq.start()
    time.sleep(1.1)
    turbdaq.savedata()
    turbdaq.cleartasks()
    return turbdaq.data

if __name__ == "__main__":
    data = main()