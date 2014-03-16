# -*- coding: utf-8 -*-
"""
Created on Mon Aug 05 14:17:51 2013

@author: Pete

This module contains classes for experiment run types

"""
import acsprgs
from acspy import acsc
import daqtasks
import time
from PyQt4 import QtCore
from pdcommpy import PdControl

class TurbineTow(QtCore.QThread):
    towfinished = QtCore.pyqtSignal()
    def __init__(self, acs_hcomm, U, tsr, y_R, z_H, 
                 R=0.5, H=1.0, nidaq=True, vectrino=True, vecsavepath=""):
        """Turbine tow run object."""
        QtCore.QThread.__init__(self)        
        self.hc = acs_hcomm
        self.U = U
        self.tsr = tsr
        self.y_R = y_R
        self.z_H = z_H
        self.R = R
        self.H = H
        self.vectrino = vectrino
        self.nidaq = nidaq 
        self.build_acsprg()
        self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.maxvel = U*1.3
        self.usetrigger = True
        self.vecsavepath = vecsavepath
        self.recordvno = True
        self.vecstatus = "Vectrino disconnected "
        self.autoaborted = False
        self.aborted = False
        
        self.metadata = {"Tow speed (m/s)" : U,
                         "Tip speed ratio" : tsr,
                         "Vectrino y/R" : y_R,
                         "Vectrino z/H" : z_H, 
                         "Time created" : time.asctime()}
        
        if self.vectrino:
            self.vec = PdControl()
            self.metadata["Vectrino metadata"] = {}
            
        if self.nidaq:
            self.daqthread = daqtasks.NiDaqThread(usetrigger=self.usetrigger)
            self.nidata = self.daqthread.data
            self.metadata["NI metadata"] = self.daqthread.metadata
        
    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.turbine_tow_prg(self.U, self.tsr)
                                               
    def setvecconfig(self):
        self.vec.start_on_sync = self.usetrigger
        self.vec.sync_master = not self.usetrigger
        self.vec.sample_on_sync = False
        self.vec.sample_rate = 200
        self.vec.coordinate_system = "XYZ"
        self.vec.power_level = "High"
        self.vec.transmit_length = 3
        self.vec.sampling_volume = 3
        self.vec.salinity = 0.0
        
        if self.maxvel <= 4.0 and self.maxvel > 2.5:
            self.vec.vel_range = 0
        elif self.maxvel <= 2.5 and self.maxvel > 1.0:
            self.vec.vel_range = 1
        elif self.maxvel <= 1.0 and self.maxvel > 0.3:
            self.vec.vel_range = 2
        self.vec.set_config()
        self.metadata["Vectrino metadata"]["Velocity range (index)"] = \
                self.vec.vel_range
        self.metadata["Vectrino metadata"]["Sample rate (Hz)"] = \
                self.vec.sample_rate
        self.metadata["Vectrino metadata"]["Coordinate system"] = \
                self.vec.coordinate_system
        print "Vectrino configuration set"

    def run(self):
        """Start the run. Comms should be open already with the controller."""
        if not acsc.getOutput(self.hc, 1, 16):
            acsc.setOutput(self.hc, 1, 16, 1)
        acsc.enable(self.hc, 0)
        acsc.enable(self.hc, 1)
        while not acsc.getMotorState(self.hc, 0)["enabled"] or not \
        acsc.getMotorState(self.hc, 1)["enabled"]:
            self.msleep(100)
        acsc.toPoint(self.hc, None, 0, self.y_R*self.R)
        acsc.toPoint(self.hc, None, 1, self.z_H*self.H)
        while not acsc.getMotorState(self.hc, 0)["in position"] or not \
        acsc.getMotorState(self.hc, 1)["in position"]:
            self.msleep(300)
        print "y- and z-axes in position"
        acsc.disable(self.hc, 0)
        acsc.disable(self.hc, 1)
        if self.vectrino:
            self.vec.serial_port = "COM2"
            self.vec.connect()
            tstart = time.time()
            self.timeout = False
            self.vecstatus = "Connecting to Vectrino..."
            while not self.vec.connected:
                self.msleep(300)
                if time.time() - tstart > 10:
                    print "Vectrino timed out"
                    self.timeout = True
                    break
            if not self.timeout:
                self.vec.stop()
                self.setvecconfig()
                if self.recordvno:
                    self.vec.start_disk_recording(self.vecsavepath)
                self.vec.start()
                self.vecstatus = "Vectrino connected "
                while self.vec.state != "Confirmation mode":
                    self.msleep(100)
                print "Vectrino in data collection mode"
                print "Waiting 6 seconds..."
                self.sleep(6)
                self.daqthread.start()
                self.start_motion()
        elif self.nidaq:
            self.daqthread.start()
            self.start_motion()
        else:
            # Start motion
            self.start_motion()

    def start_motion(self):
        self.acsdaqthread.start()
        nbuf = 19
        acsc.loadBuffer(self.hc, nbuf, self.acs_prg, 2048)
        acsc.enable(self.hc, 4)
        acsc.enable(self.hc, 5)
        acsc.runBuffer(self.hc, nbuf)
        prgstate = acsc.getProgramState(self.hc, nbuf)
        while prgstate == 3:
            time.sleep(0.3)
            prgstate = acsc.getProgramState(self.hc, nbuf)
        self.acsdaqthread.stop()
        if self.nidaq:
            self.daqthread.clear()
            print "NI tasks cleared"
        if self.vectrino:
            if self.recordvno:
                self.vec.stop_disk_recording()
            self.vec.stop()
            self.vec.disconnect()
        print "Tow finished"
        if self.vec.state == "Not connected":
            self.vecstatus = "Vectrino disconnected "
        if self.vectrino:
            print "Resetting Vectrino..."
            self.reset_vec()
        self.towfinished.emit()
        
    def reset_vec(self):
        self.vec.connect()
        self.vec.stop_disk_recording()
        self.vec.stop()
        self.vec.disconnect()
        self.vec.data = {}
        print "Vectrino reset"

    def abort(self):
        """This should stop everything."""
        self.aborted = True
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 0)
        acsc.halt(self.hc, 1)
        acsc.halt(self.hc, 4)
        acsc.halt(self.hc, 5)
        
    def autoabort(self):
        """This should stop everything and return carriage and turbine back
        to zero."""
        self.autoaborted = True
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 0)
        acsc.halt(self.hc, 1)
        acsc.halt(self.hc, 4)
        acsc.halt(self.hc, 5)
        acsc.toPoint(self.hc, None, 4, 0.0)
        acsc.setVelocity(self.hc, 5, 0.5)
        acsc.toPoint(self.hc, None, 5, 0.0)
    

class TareDragRun(QtCore.QThread):
    runfinished = QtCore.pyqtSignal()
    def __init__(self, acs_hc, U):
        QtCore.QThread.__init__(self)
        self.aborted = False
        self.hc = acs_hc
        self.U = U
        self.build_acsprg()
        self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.acsdata = self.acsdaqthread.data
        
        self.metadata = {"Tow speed (m/s)" : U,
                         "Time created" : time.asctime()}
            
        self.daqthread = daqtasks.NiDaqThread(usetrigger=True)
        self.nidata = self.daqthread.data
        self.metadata["NI metadata"] = self.daqthread.metadata
        
    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.tare_drag_prg(self.U)

    def run(self):
        """Start the run"""
        """Start the run"""
        if not acsc.getOutput(self.hc, 1, 16):
            acsc.setOutput(self.hc, 1, 16, 1)
        self.daqthread.start()
        self.msleep(2000) # Wait for NI to start waiting for trigger

    def start_motion(self):
        self.acsdaqthread.start()
        nbuf = 19
        acsc.loadBuffer(self.hc, nbuf, self.acs_prg, 2048)
        acsc.enable(self.hc, 5)
        acsc.runBuffer(self.hc, nbuf)
        prgstate = acsc.getProgramState(self.hc, nbuf)
        while prgstate == 3: # means the program is running in the controller
            time.sleep(0.3)
            prgstate = acsc.getProgramState(self.hc, nbuf)
        self.acsdaqthread.stop()
        self.daqthread.clear()
        self.runfinished.emit()
            
    def abort(self):
        """This should stop everything."""
        self.aborted = True
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 5)
        self.acsdaqthread.stop()
        self.daqthread.clear()


class TareTorqueRun(QtCore.QThread):
    runfinished = QtCore.pyqtSignal()
    def __init__(self, acs_hcomm, rpm, dur):
        """Tare torque run object."""
        QtCore.QThread.__init__(self)  
        self.aborted = False
        self.hc = acs_hcomm
        self.rpm = rpm
        self.dur = dur
        self.build_acsprg()
        self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.acsdata = self.acsdaqthread.data
        self.vecsavepath = ""
        
        self.metadata = {"RPM" : rpm,
                         "Duration" : dur,
                         "Time created" : time.asctime()}
        
        self.daqthread = daqtasks.NiDaqThread(usetrigger=True)
        self.nidata = self.daqthread.data
        self.metadata["NI metadata"] = self.daqthread.metadata
        
    def build_acsprg(self):
        """Create the ACSPL+ program for the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.tare_torque_prg(self.rpm, self.dur)

    def run(self):
        """Start the run"""
        if not acsc.getOutput(self.hc, 1, 16):
            acsc.setOutput(self.hc, 1, 16, 1)
        self.daqthread.start()
        self.msleep(2000) # Wait for NI to start waiting for trigger
        self.start_motion()

    def start_motion(self):
        self.acsdaqthread.start()
        nbuf = 19
        acsc.loadBuffer(self.hc, nbuf, self.acs_prg, 2048)
        acsc.enable(self.hc, 4)
        acsc.runBuffer(self.hc, nbuf)
        prgstate = acsc.getProgramState(self.hc, nbuf)
        while prgstate == 3:
            time.sleep(0.3)
            prgstate = acsc.getProgramState(self.hc, nbuf)
        self.acsdaqthread.stop()
        self.daqthread.clear()
        self.runfinished.emit()
            
    def abort(self):
        """This should stop everything."""
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 4)
        self.acsdaqthread.stop()
        self.daqthread.clear()
        self.aborted = True


## Classes that won't be used for now ##
class MultiTurbineTow(object):
    def __init__(self, testplandict):
        pass

class WakeTraverse(object):
    def __init__(self, towspeed, tsr, y_H_array, z_H):
        pass
    
class WakeMap(object):
    """An array of wake traverses."""

class PowerCurve(object):
    """An array of turbine tows."""
    def __init__(self, towspeed, tsr_start, tsr_stop, tsr_step):
        pass
    
    def start(self):
        pass
    
    def plot(self):
        """Plots a power curve."""
        pass
## ----------------------------------- ##


def main():
    hc = acsc.openCommDirect()
    run = TurbineTow(hc, 1.0, 1.5, 0.0, 0.25, vectrino=False, nidaq=False)
    run.start_motion()
    acsc.closeComm(hc)
    
if __name__ == "__main__":
    main()