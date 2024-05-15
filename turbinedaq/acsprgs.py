"""Functions to build ACS motion control programs."""

from __future__ import division, print_function

import os


AFT_TEMPLATE = """
! AUTO-GENERATED -- CHANGES WILL BE OVERWRITTEN
! Here we will try to continuously collect data from the INF4
global int inf4_data(8)(100) ! 8 columns and 100 rows
global int collect_data
global real start_time
local int sample_period_ms
sample_period_ms = {sample_period_ms}
global real ch1_force, ch2_force, ch3_force, ch4_force
global real inf4_data_processed({n_buffer_cols})({n_buffer_rows})

local int subtract_value
subtract_value = 16777215
local int sign_value

ECIN(ECGETOFFSET("1 Byte In (0)", 4), DI0) ! CH1, Byte 1 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (1)", 4), DI1) ! CH1, Byte 2 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (2)", 4), DI2) ! CH1, Byte 3 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (3)", 4), DI3) ! CH1, Byte 4 in Hi-Res Mode

ECIN(ECGETOFFSET("1 Byte In (4)", 4), DI4) ! CH2, Byte 1 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (5)", 4), DI5) ! CH2, Byte 2 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (6)", 4), DI6) ! CH2, Byte 3 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (7)", 4), DI7) ! CH2, Byte 4 in Hi-Res Mode

ECIN(ECGETOFFSET("1 Byte In (8)", 4), DI8) ! CH3, Byte 1 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (9)", 4), DI9) ! CH3, Byte 2 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (10)", 4), DI10) ! CH3, Byte 3 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (11)", 4), DI11) ! CH3, Byte 4 in Hi-Res Mode

ECIN(ECGETOFFSET("1 Byte In (12)", 4), DI12) ! CH4, Byte 1 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (13)", 4), DI13) ! CH4, Byte 2 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (14)", 4), DI14) ! CH4, Byte 3 in Hi-Res Mode
ECIN(ECGETOFFSET("1 Byte In (15)", 4), DI15) ! CH4, Byte 4 in Hi-Res Mode

ECIN(ECGETOFFSET("1 Byte In (16)", 4), DI16) ! Digital Outputs 1st Byte in Default Mode
ECIN(ECGETOFFSET("1 Byte In (17)", 4), DI17) ! Digital Outputs 2nd Byte in Default Mode

! Mapping all digital outputs from INF4 to ASCPL+ variables

ECOUT(ECGETOFFSET("1 Byte Out (0)", 4), DO0) ! Command Register 1st Byte
ECOUT(ECGETOFFSET("1 Byte Out (1)", 4), DO1) ! Command Register 2nd Byte

ECOUT(ECGETOFFSET("1 Byte Out (2)", 4), DO2) ! Digital Outputs Command 1st Byte
ECOUT(ECGETOFFSET("1 Byte Out (3)", 4), DO3) ! Digital Outputs Command 2nd Byte

ECOUT(ECGETOFFSET("1 Byte Out (4)", 4), DO4) ! Exchange Register 1st Byte
ECOUT(ECGETOFFSET("1 Byte Out (5)", 4), DO5) ! Exchange Register 2nd Byte
ECOUT(ECGETOFFSET("1 Byte Out (6)", 4), DO6) ! Exchange Register 3rd Byte
ECOUT(ECGETOFFSET("1 Byte Out (7)", 4), DO7) ! Exchange Register 4th Byte

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
        ch1_force = (DI1 * POW(2,16)) | (DI2 * POW(2,8)) | DI3
        if DI0
            sign_value = -1
            ch1_force = subtract_value - ch1_force
        else
            sign_value = 1
        end
        ! Convert to mV
        ch1_force = 5e-6 * ch1_force
        ! Convert to engineering units [N-m]
        ch1_force = ch1_force * 15.7085561 * sign_value
        
        ! Channel 2
        ch2_force = (DI5 * POW(2,16)) | (DI6 * POW(2,8)) | DI7
        if DI4
            sign_value = -1
            ch2_force = subtract_value - ch2_force
        else
            sign_value = 1
        end
        ! Convert to mV
        ch2_force = 5e-6 * ch2_force 
        ! Convert to engineering units [N-m]
        ch2_force = ch2_force * 15.7617411 * sign_value
        
        ! Channel 3
        ch3_force = (DI9 * POW(2,16)) | (DI10 * POW(2,8)) | DI11
        if DI8
            sign_value = 1
            ch3_force = subtract_value - ch3_force
        else
            sign_value = -1
        end
        ! Convert to mV
        ch3_force = 5e-6 * ch3_force
        ! Convert to engineering units [N]
        ch3_force = ch3_force * 390.354011 * sign_value

        ! Channel 4
        ch4_force = (DI13 * POW(2,16)) | (DI14 * POW(2,8)) | DI15
        if DI12
            sign_value = -1
            ch4_force = subtract_value - ch4_force
        else
            sign_value = 1
        end
        ! Convert to mV
        ch4_force = 5e-6 * ch4_force
        ! Convert to engineering units [N-m]
        ch4_force = ch4_force * 23.0479813 * sign_value
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
