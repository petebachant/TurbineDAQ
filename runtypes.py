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
from pdcommpy.pdcommpy import PdControl

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
        self.vectrino = vectrino
        self.nidaq = nidaq 
        self.build_acsprg()
        self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.acsdata = self.acsdaqthread.data
        self.maxvel = U*1.2
        self.usetrigger = False
        self.vecsavepath = vecsavepath
        self.record = False
        self.vecstatus = "Vectrino disconnected "
        
        self.metadata = {"Tow speed (m/s)" : U,
                         "Tip speed ratio" : tsr,
                         "Vectrino y/R" : y_R,
                         "Vectrino z/H" : z_H, 
                         "Time created" : time.asctime()}
        
        if self.vectrino:
            self.vec = PdControl()
            self.vecdata = self.vec.data
            self.metadata["Vectrino metadata"] = {}
            
        if self.nidaq:
            self.daqthread = daqtasks.NiDaqThread(usetrigger=False)
            self.nidata = self.daqthread.data
            self.metadata["NI metadata"] = self.daqthread.metadata
        
    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.turbine_tow_prg(self.U, self.tsr, self.y_R,
                                               self.z_H)
                                               
    def setvecconfig(self):
        self.vec.set_start_on_synch(self.usetrigger)
        self.vec.set_synch_master(not self.usetrigger)
        self.vec.set_sample_on_synch(False)
        self.vec.set_sample_rate(200)
        if self.maxvel <= 4.0 and self.maxvel > 2.5:
            self.vec.set_vel_range(0)
        elif self.maxvel <= 2.5 and self.maxvel > 1.0:
            self.vec.set_vel_range(1)
        elif self.maxvel <= 1.0 and self.maxvel > 0.3:
            self.vec.set_vel_range(2)
        self.vec.set_config()
        self.metadata["Vectrino metadata"]["Velocity range (m/s)"] = \
                self.vec.get_vel_range()
        self.metadata["Vectrino metadata"]["Sample rate (Hz)"] = \
                self.vec.sample_rate
        print "Vectrino configuration set"

    def run(self):
        """Start the run. Comms should be open already with the controller.
        Maybe the vectrino shouldn't have its own thread here..."""
        if self.vectrino:
            self.vec.set_serial_port("COM2")
            self.vec.connect()
            tstart = time.time()
            self.timeout = False
            self.vecstatus = "Connecting to Vectrino..."
            while not self.vec.connected:
                time.sleep(0.5)
                self.vec.is_connected()
                if time.time() - tstart > 10:
                    print "Vectrino timed out"
                    self.timeout = True
                    break
            if not self.timeout:
                self.vec.stop()
                self.setvecconfig()
                if self.record:
                    self.vec.start_disk_recording(self.vecsavepath)
                self.vec.start()
                self.vecstatus = "Vectrino connected "
                while self.vec.state != "Confirmation mode":
                    self.vec.inquire_state()
                    time.sleep(0.1)
                print "Vectrino collecting"
                time.sleep(5)
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
        acsc.enable(self.hc, 0)
        acsc.enable(self.hc, 1)
        acsc.enable(self.hc, 4)
        acsc.enable(self.hc, 5)
        acsc.runBuffer(self.hc, nbuf)
        prgstate = acsc.getProgramState(self.hc, nbuf)
        while prgstate == 3:
            time.sleep(0.3)
            prgstate = acsc.getProgramState(self.hc, nbuf)
        if self.nidaq:
            self.daqthread.clear()
        if self.vectrino:
            self.vec.stop()
            self.vec.disconnect()
        self.towfinished.emit()
    
    def on_vec_collecting(self):
        self.metadata["Vectrino velocity range (m/s)"] = self.vecthread.vec.get_vel_range()
        print "Starting NI DAQ"
        if self.nidaq:
            self.daqthread.start()
        self.start_motion()
            
    def abort(self):
        """This should stop everything."""
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 0)
        acsc.halt(self.hc, 1)
        acsc.halt(self.hc, 4)
        acsc.halt(self.hc, 5)
        self.acsdaqthread.stop()
        self.daqthread.clear()
        if self.vectrino:
            self.vec.stop()
            self.vec.stop_disk_recording()
            self.vec.disconnect()
    

class TareDragRun(QtCore.QThread):
    runfinished = QtCore.pyqtSignal()
    def __init__(self, acs_hc, U):
        QtCore.QThread.__init__(self)        
        self.hc = acs_hc
        self.U = U
        self.build_acsprg()
        self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.acsdata = self.acsdaqthread.data
        
        self.metadata = {"Tow speed (m/s)" : U,
                         "Time created" : time.asctime()}
            
        self.daqthread = daqtasks.NiDaqThread(usetrigger=False)
        self.nidata = self.daqthread.data
        self.metadata["NI metadata"] = self.daqthread.metadata
        
    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.tare_drag_prg(self.U)

    def run(self):
        """Start the run"""
        self.daqthread.start()
        self.start_motion()

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
        self.daqthread.clear()
        self.runfinished.emit()
            
    def abort(self):
        """This should stop everything."""
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 5)
        self.acsdaqthread.stop()
        self.daqthread.clear()


class TareTorqueRun(QtCore.QThread):
    runfinished = QtCore.pyqtSignal()
    def __init__(self, acs_hcomm, U, tsr):
        """Tare torque run object."""
        QtCore.QThread.__init__(self)        
        self.hc = acs_hcomm
        self.U = U
        self.tsr = tsr
        self.build_acsprg()
        self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.acsdata = self.acsdaqthread.data
        self.vecsavepath = ""
        
        self.metadata = {"Tow speed (m/s)" : U,
                         "Tip speed ratio" : tsr,
                         "Time created" : time.asctime()}
        
            
        if self.nidaq:
            self.daqthread = daqtasks.NiDaqThread(usetrigger=False)
            self.nidata = self.daqthread.data
            self.metadata["NI metadata"] = self.daqthread.metadata
        
    def build_acsprg(self):
        """Create the ACSPL+ program for the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.tare_torque_prg(self.U, self.tsr)

    def run(self):
        """Start the run"""
        self.daqthread.start()
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
        self.daqthread.clear()
        self.runfinished.emit()
            
    def abort(self):
        """This should stop everything."""
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 4)
        self.acsdaqthread.stop()
        self.daqthread.clear()


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