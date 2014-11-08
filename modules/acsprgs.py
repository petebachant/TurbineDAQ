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

def tare_torque_prg(rpm, dur, prgdir="./acsprgs"):
    """Builds a tare torque ACSPL+ program"""
    with open(os.path.join(prgdir, "tare_torque.prg")) as f:
        prg = f.read().format(rpm=rpm, dur=dur)
    return prg

def tare_drag_prg(tow_speed, prgdir="./acsprgs"):
    with open(os.path.join(prgdir, "tare_drag.prg")) as f:
        prg = f.read().format(tow_speed=tow_speed)
    return prg

def test_turbine_tow():
    print(turbine_tow_prg(1.0, 1.9, 0.5, prgdir="../acsprgs"))
    
def test_tare_torque():
    print(tare_torque_prg(rpm=60, dur=10, prgdir="../acsprgs"))
    
def test_tare_drag():
    print(tare_drag_prg(tow_speed=1.0, prgdir="../acsprgs"))

if __name__ == "__main__":
#    test_turbine_tow()
#    test_tare_torque()
    test_tare_drag()