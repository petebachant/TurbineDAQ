# -*- coding: utf-8 -*-
"""
Created on Sun Sep 08 12:20:14 2013

@author: Pete
"""
from acspy.prgs import ACSPLplusPrg

def turbine_tow_prg(towspeed, tsr):
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

target = 24.5   ! Do not exceed 24.9 for traverse at x/D = 1
endpos = 0      ! Where to move carriage at end of tow
tacc = 5        ! Time (in seconds) for turbine angular acceleration
tzero = 2.5       ! Time (in seconds) to wait before starting

VEL(5) = 0.5
ptp/e 5, 0

ACC(5) = 1
DEC(5) = 0.5
VEL(5) = U
JERK(5)= ACC(5)*10

! Set modulo on turbine axis (only needed if using simulator)
! DISABLE 4
! SLPMAX(4) = 60
! SLPMIN(4) = 0
! MFLAGS(4).#MODULO = 1

ACC(4) = rpm/tacc
VEL(4) = rpm
DEC(4) = ACC(4)
JERK(4)= ACC(4)*10

! Move turbine to zero if necessary
if RPOS(4) <> 60 & RPOS(4) <> 0
    ptp 4, 0
end

! Allow oscillations in shaft to damp out
wait 3000

! Start controller data acquisition and send trigger pulse in same cycle
BLOCK
    ! Define start time from now
    start_time = TIME
    collect_data = 1
    DC/c data, 100, 1.0, TIME, FVEL(5), FVEL(4)
    ! Send trigger pulse for data acquisition
    OUT1.16 = 0
END

wait tzero*1000
jog/v 4, rpm
wait tacc*1000
ptp/e 5, target
HALT(4)
VEL(5) = 0.5
VEL(4) = 10
ptp 4, 0
ptp/e 5, 0
STOPDC
collect_data = 0
OUT1.16 = 1

STOP
"""
    prg = initvars 
    prg += "tsr = " + str(tsr) + "\n" + "U = " + str(towspeed) + "\n"
    prg += prgbody
    return prg


def tare_trq_prg(U, tsr):
    """Builds a tare torque ACSPL+ program"""
    prg = """GLOBAL INT homeCounter_AKD
REAL tsr, U, rpm, tacc

tsr = 2.3
U = 1
rpm = tsr*U/0.5*60/6.28318530718
tacc = 2

ACC(turbine) = rpm/tacc
DEC(turbine) = ACC(turbine)
VEL(turbine) = rpm
JERK(turbine) = ACC(turbine)*10

IF homeCounter_AKD > 0
	jog/v turbine, rpm
END

WAIT 32*1000
! HALT turbine
ptp/e turbine, 0

STOP
"""
    return prg


def tare_drag_prg(U):
    prg = """global real data(3)(100)
global real start_time
global int collect_data
collect_data = 0

"""
    prg += "VEL(5) = " + str(U)
    prg += \
"""
ACC(5) = 1
DEC(5) = 1

! Start controller data acquisition and send trigger pulse in same cycle
BLOCK
    collect_data = 1
    DC/c data, 100, 5.0, TIME, FVEL(5), FVEL(4)
    ! Send trigger pulse for data acquisition (may need work)
    OUT1.16 = 0
END

! Define start time from now
start_time = TIME

PTP/e 5, 24.5
PTP/e 5, 0
OUT1.16 = 1
STOP
"""
    return prg


## Possible make this object oriented... ##
class TurbineTow(ACSPLplusPrg):
    """A class for creating turbine tows."""
    def __init__(self, towspeed, tsr, y_R=None, z_H=None):
        ACSPLplusPrg.__init__(self)
        
if __name__ == "__main__":
    print turbine_tow_prg(0.5, 1.9)