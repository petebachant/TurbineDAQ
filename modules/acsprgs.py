# -*- coding: utf-8 -*-
"""
Created on Sun Sep 08 12:20:14 2013

@author: Pete
"""
from __future__ import division, print_function
from acspy.prgs import ACSPLplusPrg
import os

def turbine_tow_prg(tow_speed, tsr, turbine_radius, prgdir="./acsprgs"):
    """This function builds an ACSPL+ program for turbine towing."""
    with open(os.path.join(prgdir, "turbine_tow.prg")) as f:
        prg = f.read().format(tow_speed=tow_speed, tsr=tsr, 
                              turbine_radius=turbine_radius)
    return prg

def tare_torque_prg(rpm, dur):
    """Builds a tare torque ACSPL+ program"""
    prg = """REAL rpm, dur, tzero, tacc
global real data(3)(100)
global real start_time
global int collect_data
collect_data = 0

""" 
    prg += "rpm = " + str(rpm) + "\n"
    prg += "dur = " + str(dur)
    prg += """
tacc = 2
tzero = 2.5

! Move turbine to zero if necessary
if RPOS(4) <> 60 & RPOS(4) <> 0
    ptp 4, 0
end

ACC(turbine) = rpm/tacc
DEC(turbine) = ACC(turbine)
VEL(turbine) = rpm
JERK(turbine) = ACC(turbine)*10

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
jog/v turbine, rpm
WAIT dur*1000
HALT turbine
ptp/e turbine, 0
OUT1.16 = 1
STOPDC
collect_data = 0
STOP
"""
    return prg


def tare_drag_prg(U):
    prg = """global real data(3)(100)
global real start_time, tzero
global int collect_data
collect_data = 0
tzero = 2.5

"""
    prg += "VEL(5) = " + str(U)
    prg += \
"""
ACC(5) = 1
DEC(5) = 1

! Start controller data acquisition and send trigger pulse in same cycle
BLOCK
    start_time = TIME
    collect_data = 1
    DC/c data, 100, 1.0, TIME, FVEL(5), FVEL(4)
    ! Send trigger pulse for data acquisition
    OUT1.16 = 0
END

WAIT tzero*1000

PTP/e 5, 24.5
VEL(5) = 0.6
PTP/e 5, 0
STOPDC
collect_data = 0
OUT1.16 = 1
STOP
"""
    return prg

def test_turbine_tow():
    print(turbine_tow_prg(1.0, 1.9, 0.5, prgdir="../acsprgs"))

if __name__ == "__main__":
    test_turbine_tow()