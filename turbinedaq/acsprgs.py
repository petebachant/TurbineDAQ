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
global real inf4_data_processed({n_buffer_cols})({n_buffer_rows})

BLOCK
    ! Define start time from now
    start_time = TIME
    collect_data = 1
    ! TODO: We probably want to collect FPOS and FVEL from the AFT axis as well
    DC/c inf4_data_processed, {n_buffer_rows}, sample_period_ms, TIME, ch1_force, ch2_force, ch3_force, ch4_force
END

! Continuously compute processed force values from the INF4
WHILE collect_data
    WAIT 1
END

STOPDC
STOP
"""


def turbine_tow_prg(
    tow_speed, tsr, turbine_radius, endpos=0.0, prgdir="./acsprgs"
):
    """This function builds an ACSPL+ program for turbine towing."""
    with open(os.path.join(prgdir, "turbine_tow.prg")) as f:
        prg = f.read().format(
            tow_speed=tow_speed,
            tsr=tsr,
            turbine_radius=turbine_radius,
            endpos=endpos,
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


def make_aft_prg(
    sample_period_ms=2, n_buffer_rows=100, n_buffer_cols=5
) -> str:
    """Create an AFT program to load into the controller."""
    return AFT_TEMPLATE.format(
        sample_period_ms=sample_period_ms,
        n_buffer_rows=n_buffer_rows,
        n_buffer_cols=n_buffer_cols,
    )
