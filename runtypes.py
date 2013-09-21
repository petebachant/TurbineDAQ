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
from pdcommpy.pdcommpy import PdControl

class TurbineTow(QtCore.QThread):
    towfinished = QtCore.pyqtSignal()
    def __init__(self, acs_hcomm, U, tsr, y_R, z_H, 
                 R=0.5, H=1.0, nidaq=True, vectrino=True):
        """Turbine tow run object."""
        QtCore.QThread.__init__(self)
        
        self.acs_hcomm = acs_hcomm
        self.U = U
        self.tsr = tsr
        self.y_R = y_R
        self.z_H = z_H
        self.name = "Something" # Come up with a naming scheme
        self.vectrino = vectrino
        self.nidaq = nidaq 
        self.build_acsprg()
        
        if self.vectrino:
            print "Attempting to connect to Vectrino..."
            self.vecthread = vectasks.VectrinoThread()
            self.vecthread.collecting.connect(self.on_vec_collecting)
            self.vecdata = self.vecthread.vec.data
            
        if self.nidaq:
            self.daqthread = daqtasks.TurbineTowDAQ()
            self.daqthread.collecting.connect(self.on_nidaq_collecting)
            self.nidata = self.daqthread.data
        
    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.build_turbine_tow(self.U, self.tsr)

    def run(self):
        """Start the run. Comms should be open already with the controller"""
        if self.vectrino:
            self.vecthread.start()
        elif self.nidaq:
            self.daqthread.start()
        else:
            self.start_motion()

    def start_motion(self):
        time.sleep(2)
        self.towfinished.emit()
        if self.acs_hcomm != acsc.INVALID:
            acs_buffno = 17
            acsc.loadBuffer(self.acs_hcomm, acs_buffno, self.acs_prg, 512)
            acsc.enable(self.acs_hcomm, 0)
            acsc.runBuffer(self.acs_hcomm, acs_buffno)
    
    def on_vec_collecting(self):
        if self.nidaq:
            self.daqthread.start()
        else:
            self.start_motion()
        
    def on_nidaq_collecting(self):
        self.start_motion()
            
    def abort(self):
        """This should stop everything."""
        acsc.halt(self.acs_hcomm, 0)
        acsc.halt(self.acs_hcomm, 1)
        acsc.halt(self.acs_hcomm, 4)
        acsc.halt(self.acs_hcomm, 5)
        self.daqtask.clear()    
    
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
    run = TurbineTow(None, 1.0, 1.5)
    print run.acs_prg
    
if __name__ == "__main__":
    main()