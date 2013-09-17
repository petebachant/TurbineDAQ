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

class TurbineTow(object):
    def __init__(self, acs_hcomm, towspeed, tsr, y_R=None, z_H=None, 
                 R=0.5, H=1.0, nidaq=True, vectrino=True):
        """Turbine tow run object."""
        self.acs_hcomm = acs_hcomm
        self.towspeed = towspeed
        self.tsr = tsr
        self.y_R = y_R
        self.z_H = z_H
        self.name = "Something" # Come up with a naming scheme
        self.vectrino = True
        self.nidaq = True
        
        if self.acs_hcomm == None:
            self.acs_hcomm = acsc.openCommDirect()
        
        self.build_acsprg()
        
    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.build_turbine_tow(self.towspeed, self.tsr)

    def go(self):
        """Start the run. Comms should be open already with the controller"""
        if self.vectrino:
            self.start_vec()
            vecstatus = self.vectask.getstatus()
            while vecstatus != "Confimation mode":
                time.sleep(0.3)
        # Wait for Vectrino to start
            
        if self.nidaq:
            self.start_nidaq()
        
        acs_buffno = 15
        acsc.loadBuffer(self.acs_hcomm, acs_buffno, self.acs_prg, 512)
        acsc.enable(self.acs_hcomm, 0)
        acsc.runBuffer(self.acs_hcomm, acs_buffno)
    
    def halt(self):
        """This should stop everything."""
        acsc.halt(self.acs_hcomm, 0)
        acsc.halt(self.acs_hcomm, 1)
        acsc.halt(self.acs_hcomm, 4)
        acsc.halt(self.acs_hcomm, 5)
        self.daqtask.clear()
    
    def start_nidaq(self):
        self.daqtask = daqtasks.TurbineTowDAQ()
        self.daqtask.start()
    
    def start_vec(self):
        self.vectask = vectasks.VectrinoRun()
        self.vectask.start()
    
    def process(self, t1, t2):
        """This shit should load in the data and spit out mean values"""
        pass
        self.cp = 0
    
    def plot(self):
        pass


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