# -*- coding: utf-8 -*-
"""
Created on Mon Aug 05 14:17:51 2013

@author: Pete

This module contains classes for experiment run types

"""
import acsprgs
from acspy import acsc
import daqtasks
import vectasks
import time
from PyQt4 import QtCore

class TurbineTow(QtCore.QThread):
    towfinished = QtCore.pyqtSignal()
    def __init__(self, acs_hcomm, U, tsr, y_R, z_H, 
                 R=0.5, H=1.0, nidaq=True, vectrino=True):
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
        self.vecsavepath = ""
        
        self.metadata = {"Tow speed" : U,
                         "Tip speed ratio" : tsr,
                         "Vectrino y/R" : y_R,
                         "Vectrino z/H" : z_H, 
                         "Time created" : time.asctime()}
        
        if self.vectrino:
            print "Attempting to connect to Vectrino..."
            self.vecthread = vectasks.VectrinoThread()
            self.vecthread.collecting.connect(self.on_vec_collecting)
            self.vecdata = self.vecthread.vec.data
            self.vecthread.savepath = self.vecsavepath
            
        if self.nidaq:
            self.daqthread = daqtasks.NiDaqThread(usetrigger=False)
#            self.daqthread.started.connect(self.on_nidaq_collecting)
            self.nidata = self.daqthread.data
            self.metadata["NI metadata"] = self.daqthread.metadata
        
    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.build_turbine_tow(self.U, self.tsr, self.y_R,
                                                 self.z_H)

    def run(self):
        """Start the run. Comms should be open already with the controller"""
        if self.vectrino:
            self.vecthread.start()
        elif self.nidaq:
            self.daqthread.start()
            self.start_motion()
        else:
            # Start motion
            self.start_motion()

    def start_motion(self):
        print "Starting motion..."
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
            time.sleep(0.5)
            prgstate = acsc.getProgramState(self.hc, nbuf)
        self.towfinished.emit()
        if self.nidaq:
            self.daqthread.clear()
    
    def on_vec_collecting(self):
        if self.nidaq:
            self.daqthread.start()
        else:
            self.start_motion()
        
    def on_nidaq_collecting(self):
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
            self.vecthread.stop()
    
    def process(self, t1, t2):
        """This shit should load in the data and spit out mean values"""
        pass
        self.cp = 0
    
    def save_data(self, fullpath):
        pass
    
    def compile_metadata(self):
        pass
        self.daqthread.metadata


class TareTorqueRun(object):
    pass

class TareDragRun(object):
    pass    
    

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


def main():
    hc = acsc.openCommDirect()
    run = TurbineTow(hc, 1.0, 1.5, 0.0, 0.25, vectrino=False, nidaq=False)
    run.start_motion()
    acsc.closeComm(hc)
    
if __name__ == "__main__":
    main()