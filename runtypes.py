# -*- coding: utf-8 -*-
"""
Created on Mon Aug 05 14:17:51 2013

@author: Pete

This module contains classes for experiment run types

"""
import acsprgs
import acsc

class TurbineTow(object):
    def __init__(self, towspeed, tsr, y_R, z_H):
        """Turbine tow run object."""
        self.towspeed = towspeed
        self.tsr = tsr
        self.y_R = y_R
        self.z_H = z_H
        self.acs_prg = acsprgs.build_turbine_tow(self.towspeed, self.tsr)
        self.name = "Something" # Come up with a naming scheme

    def start_tow(self):
        """Start the run. Comms should be open already with the controller"""
        acs_buff = 15
        self.acs_hcomm = acsc.OpenCommDirect()
        acsc.LoadBuffer(self.acs_hcomm, acs_buff, self.acs_prg, 512)
    
    def halt(self):
        pass
    
    def start_daq(self):
        pass
    
    def process(self):
        pass
    
    def plot(self):
        pass
    

def main():
    run = TurbineTow(1.0, 1.5, 1, 1)
    print run.acs_prg
    
if __name__ == "__main__":
    main()