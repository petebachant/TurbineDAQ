# -*- coding: utf-8 -*-
"""
Created on Mon Aug 05 14:17:51 2013

@author: Pete

This module contains classes for experiment run types

"""
# Strings for ACS programs that stay constant each run
acs_prg_init = "local real target, offset, tsr, U, rpm, tacc, endpos \n \n"
acs_prg_exec = \
"""
rpm = tsr*U/0.5*60/6.28318530718

offset = 0      ! Offset caused by ADV traverse (m)
target = 24.9   ! Do not exceed 24.9 for traverse at x/D = 1
endpos = 0      ! Where to move carriage at end of tow
tacc = 5        ! Time (in seconds) for turbine angular acceleration

ACC(tow) = 1
DEC(tow) = 0.5
VEL(tow) = U
JERK(tow)= ACC(tow)*10

ACC(turbine) = rpm/tacc
VEL(turbine) = rpm
DEC(turbine) = ACC(turbine)
JERK(turbine)= ACC(turbine)*10

jog/v turbine, rpm
wait (tacc)*1000
ptp/e tow, target-offset
HALT(turbine)
VEL(tow) = 0.5
VEL(turbine) = 10
ptp tow, endpos
ptp/e turbine, 60

STOP
"""


class TowRun(object):
    def __init__(self, towspeed, tsr, y_R, z_H):
        self.towspeed = towspeed
        self.tsr = tsr
        self.y_R = y_R
        self.z_H = z_H
        
        self.acs_prg = acs_prg_init + "tsr = " + str(self.tsr) + "\n" +\
        "U = " + str(self.towspeed) + "\n" + acs_prg_exec

    def go(self):
        pass
    
    def halt(self):
        pass
    
    def process(self):
        pass
    
    def plot(self):
        pass
    

def main():
    run = TowRun(1.0, 1.5, 1, 1)
    file = open("testing/test.prg", "w")
    file.write(run.acs_prg)
    file.close()
    print run.acs_prg
    
if __name__ == "__main__":
    main()