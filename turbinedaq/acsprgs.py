"""Functions to build ACS motion control programs."""

from __future__ import division, print_function

import os


AFT_TEMPLATE = """
! AUTO-GENERATED -- CHANGES WILL BE OVERWRITTEN
! Here we will try to continuously collect data from the INF4
global int inf4_data(8)(100) ! 8 columns and 100 rows
global int collect_data
global real start_time
local int sample_period_ms = {sample_period_ms}
global real ch1_force, ch2_force, ch3_force, ch4_force
global real inf4_data_processed({n_buffer_cols})({n_buffer_rows})

local int subtract_value = 16777215
local int sign_value

! Put into high res mode
DO1 = 25

BLOCK
    ! Define start time from now
    start_time = TIME
    collect_data = 1
    ! TODO: We probably want to collect FPOS and FVEL from the AFT axis as well
    DC/c inf4_data_processed, {n_buffer_rows}, sample_period_ms, TIME, ch1_force, ch2_force, ch3_force, ch4_force
END

! Continuously compute processed force values from the INF4
WHILE collect_data
    BLOCK
        ! Compute all force values in the same controller cycle
        ! Channel 1
        ch1_force = (DI1 << 16) | (DI2 << 8) | DI3
        if DI0
            sign_value = -1
            ch1_force = subtract_value - ch1_force
        else
            sign_value = 1
        end
        ! Convert to mV
        ch1_force = 5e-6 * ch1_force
        ! Convert to engineering units [N-m]
        ch1_force = ch1_force * 15.7085561
        
        ! Channel 2
        ch2_force = (DI5 << 16) | (DI6 << 8) | DI7
        if DI4
            sign_value = -1
            ch2_force = subtract_value - ch2_force
        else
            sign_value = 1
        end
        ! Convert to mV
        ch2_force = 5e-6 * ch2_force 
        ! Convert to engineering units [N-m]
        ch2_force = ch2_force * 15.7617411 
        
        ! Channel 3
        ch3_force = (DI9 << 16) | (DI10 << 8) | DI11
        if DI8
            sign_value = -1
            ch3_force = subtract_value - ch3_force
        else
            sign_value = 1
        end
        ! Convert to mV
        ch3_force = 5e-6 * ch3_force
        ! Convert to engineering units [N]
        ch3_force = ch3_force * 390.354011

        ! Channel 4
        ch4_force = (DI13 << 16) | (DI14 << 8) | DI15
        if DI12
            sign_value = -1
            ch4_force = subtract_value - ch4_force
        else
            sign_value = 1
        end
        ! Convert to mV
        ch4_force = 5e-6 * ch4_force
        ! Convert to engineering units [N-m]
        ch4_force = ch4_force * 23.0479813 
    END
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
