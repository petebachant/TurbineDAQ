# -*- coding: utf-8 -*-
"""
Created on Wed Aug 14 21:13:07 2013

@author: Pete

This module contains functions for generating ACS programs
"""

def build_turbine_tow(towspeed, tsr, y_R=None, z_H=None):
    """This function builds an ACS program for turbine towing. Turbine
    radius is assumed to be 0.5 m"""
    
    initvars = "local real target, offset, tsr, U, rpm, tacc, endpos, tzero \n \n"
    prgbody = \
"""
rpm = tsr*U/0.5*60/6.28318530718

offset = 0      ! Offset caused by ADV traverse (m)
target = 24.9   ! Do not exceed 24.9 for traverse at x/D = 1
endpos = 0      ! Where to move carriage at end of tow
tacc = 5        ! Time (in seconds) for turbine angular acceleration
tzero = 2       ! Time (in seconds) to wait before starting

ACC(tow) = 1
DEC(tow) = 0.5
VEL(tow) = U
JERK(tow)= ACC(tow)*10

ACC(turbine) = rpm/tacc
VEL(turbine) = rpm
DEC(turbine) = ACC(turbine)
JERK(turbine)= ACC(turbine)*10

! If turbine is not at 0 degrees RPOS, move it there

! Send trigger pulse for data acquisition
wait tzero*1000
jog/v turbine, rpm
wait tacc*1000
ptp/e tow, target-offset
HALT(turbine)
VEL(tow) = 0.5
VEL(turbine) = 10
ptp tow, endpos
ptp/e turbine, 60

STOP
"""
    
    prg = initvars 
    prg += "tsr = " + str(tsr) + "\n" + "U = " + str(towspeed) + "\n"
    if y_R != None:
        prg += "ptp/e y, " + str(y_R*0.5)
    if z_H != None:
        prg += "ptp/e z, " + str(z_H)
        
    # Set this up as a linear 2 ax-s move?
    prg += prgbody
    return prg