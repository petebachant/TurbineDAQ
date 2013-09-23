# -*- coding: utf-8 -*-
"""
Created on Sun Sep 08 12:20:14 2013

@author: Pete
"""
from acspy.prgs import ACSPLplusPrg

def build_turbine_tow(towspeed, tsr, y_R, z_H):
    """This function builds an ACSPL+ program for turbine towing. Turbine
    radius is assumed to be 0.5 m"""
    
    initvars = "local real target, tsr, U, rpm, tacc, endpos, tzero \n"
    initvars += "global real data(3)(100) \n"
    initvars += "global real start_time \n"
    initvars += "global int collect_data \n"
    initvars += "collect_data = 0 \n \n"
    prgbody = \
"""
rpm = tsr*U/0.5*60/6.28318530718

target = 24.9   ! Do not exceed 24.9 for traverse at x/D = 1
endpos = 0      ! Where to move carriage at end of tow
tacc = 5        ! Time (in seconds) for turbine angular acceleration
tzero = 2       ! Time (in seconds) to wait before starting

ACC(5) = 1
DEC(5) = 0.5
VEL(5) = U
JERK(5)= ACC(5)*10

! Reset modulo on turbine axis
DISABLE 4
SLPMAX(4) = 60
SLPMIN(4) = 0
MFLAGS(4).#MODULO = 1
ENABLE 4

ACC(4) = rpm/tacc
VEL(4) = rpm
DEC(4) = ACC(4)
JERK(4)= ACC(4)*10

! Wait a little after moving Vectrino
WAIT 3000

! Move turbine to zero
ptp/e(4), 0

! Start controller data acquisition and send trigger pulse in same cycle
BLOCK
    collect_data = 1
    DC/c data, 100, 5.0, TIME, FVEL(5), FVEL(4)
    ! Send trigger pulse for data acquisition (may need work)
    ! OUT4.0 = 1
END

! Define start time from now
start_time = TIME

wait tzero*1000
jog/v 4, rpm
wait tacc*1000
ptp/e 5, target
HALT(4)
VEL(5) = 0.5
VEL(4) = 10
ptp/e 4, 0
ptp/e 5, 0

! OUT4.0 = 0
STOPDC
collect_data = 0
STOP
"""
    
    prg = initvars 
    prg += "tsr = " + str(tsr) + "\n" + "U = " + str(towspeed) + "\n"
    if y_R != None:
        prg += "ptp/e 0, " + str(y_R*0.5) + "\n"
    if z_H != None:
        prg += "ptp/e 1, " + str(z_H)
        
    # Set this up as a linear 2 ax-s move?
    prg += prgbody
    return prg
    

    

class TurbineTow(ACSPLplusPrg):
    """A class for creating turbine tows."""
    def __init__(self, towspeed, tsr, y_R=None, z_H=None):
        ACSPLplusPrg.__init__(self)
        
if __name__ == "__main__":
    print build_turbine_tow(1.0, 1.9, 0.0, 0.25)