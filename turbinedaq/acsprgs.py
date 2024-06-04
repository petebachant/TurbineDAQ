"""Functions to build ACS motion control programs."""

from __future__ import division, print_function

import os


AFT_TEMPLATE = """
! AUTO-GENERATED -- CHANGES WILL BE OVERWRITTEN
! Here we will try to continuously collect data from the INF4
global int collect_data
global real start_time
local int sample_period_ms
sample_period_ms = {sample_period_ms}
global real ch1_force, ch2_force, ch3_force, ch4_force
global real aft_data(8)({n_buffer_rows})

BLOCK
    ! Define start time from now
    start_time = TIME
    collect_data = 1
    DC/c aft_data, {n_buffer_rows}, sample_period_ms, TIME, ch1_force, ch2_force, ch3_force, ch4_force, FPOS(6), FVEL(6), FVEL(5)
END

! Continuously compute processed force values from the INF4
WHILE collect_data
    WAIT 1
END

STOPDC
STOP
"""


AFT_TOW_TEMPLATE = """
! This is a turbine tow program auto-generated by TurbineDAQ
! AUTO-GENERATED -- CHANGES WILL BE OVERWRITTEN
local real target, tsr, U, rpm, tacc, endpos, tzero, R
global real data(3)(100)
global real start_time
global int collect_data
local int sample_period_ms
sample_period_ms = {sample_period_ms}
global real ch1_force, ch2_force, ch3_force, ch4_force
global real aft_data(8)({n_buffer_rows})

collect_data = 0

tsr = {tsr}
U = {tow_speed}
R = {turbine_radius}

rpm = tsr*U/R*60/6.28318530718

target = 24.5       ! Do not exceed 24.9 for traverse at x/D = 1
endpos = {endpos}        ! Where to move carriage at end of tow
tacc = 5            ! Time (in seconds) for turbine angular acceleration
tzero = 2.5         ! Time (in seconds) to wait before starting

VEL(5) = 0.5
ptp/e 5, 0

ACC(5) = 1.0
DEC(5) = 0.3
VEL(5) = U
JERK(5)= ACC(5)*10

! Set modulo on turbine axis (only needed if using simulator)
! DISABLE 6
! SLPMAX(6) = 60
! SLPMIN(6) = 0
! MFLAGS(6).#MODULO = 1

ACC(6) = rpm/tacc
VEL(6) = rpm
DEC(6) = ACC(6)
JERK(6)= ACC(6)*10

! Move turbine to zero if necessary
if RPOS(6) <> 60 & RPOS(6) <> 0
    VEL(6) = -10 ! CCW PTP move
    ptp/e 6, 0
end

! Allow oscillations in shaft to damp out
wait 3000

! Start controller data acquisition and send trigger pulse in same cycle
BLOCK
    ! Define start time from now
    start_time = TIME
    collect_data = 1
    DC/c aft_data, {n_buffer_rows}, sample_period_ms, TIME, ch1_force, ch2_force, ch3_force, ch4_force, FPOS(6), FVEL(6), RVEL(5)
    ! Send trigger pulse for data acquisition
    OUT1.16 = 1
END

wait tzero*1000
jog/v 6, rpm
wait tacc*1000
ptp/e 5, target
HALT(6)
ACC(5) = 0.1 ! Reduce carriage axis motion param. on tow-back to prevent AFT shaft from being pulled out
JERK(5)= ACC(5)*10
VEL(5) = 0.5
VEL(6) = -10 ! CCW PTP move
ptp/e 6, 0 ! Perform PTP(6) before carriage returns to right limit 
ptp/e 5, endpos
STOPDC
collect_data = 0
OUT1.16 = 0

STOP
"""


def turbine_tow_prg(
    tow_speed,
    tsr,
    turbine_radius,
    endpos=0.0,
    prgdir="./acsprgs",
    turbine_type="CFT",
):
    """This function builds an ACSPL+ program for turbine towing."""
    if turbine_type == "CFT":
        with open(os.path.join(prgdir, "turbine_tow.prg")) as f:
            prg = f.read().format(
                tow_speed=tow_speed,
                tsr=tsr,
                turbine_radius=turbine_radius,
                endpos=endpos,
            )
    elif turbine_type == "AFT":
        prg = AFT_TOW_TEMPLATE.format(
            sample_period_ms=1,
            tow_speed=tow_speed,
            tsr=tsr,
            turbine_radius=turbine_radius,
            endpos=endpos,
            n_buffer_rows=100,
        )
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


def make_aft_prg(sample_period_ms=2, n_buffer_rows=100) -> str:
    """Create an AFT program to load into the controller."""
    return AFT_TEMPLATE.format(
        sample_period_ms=sample_period_ms,
        n_buffer_rows=n_buffer_rows,
    )
