"""This script collects data from the INF4 load cell amplifier as a system
integration test.
"""

import time

import pandas as pd
from acspy import acsc

SAMPLE_PERIOD_MS = 2

# First, define the ACSPL+ program text
prg_txt = f"""! AUTO-GENERATED -- CHANGES WILL BE OVERWRITTEN
! Here we will try to continuously collect data from the INF4
global int inf4_data(8)(100) ! 8 columns and 100 rows
global int collect_data
global real start_time
local int sample_period_ms = {SAMPLE_PERIOD_MS}
global real ch1_force, ch2_force, ch3_force, ch4_force
global real inf4_data_processed(5)(100) ! 5 columns and 100 rows

! Put into high res mode
! TODO: Check that this works okay
DO1 = 27

BLOCK
    ! Define start time from now
    start_time = TIME
    collect_data = 1
	! Collect raw data
	! This could be a problem because the guide claims we can collect up to 24, but maybe doesn't work with DC/c
	! Seems to error for more than 8 sampled variables
    ! DC/c inf4_data, 100, sample_period_ms, TIME, DI1, DI2, DI3, DI4, DI5, DI6, DI7
	! Instead let's store derived data
	! TODO: We probably want to collect FPOS and FVEL from the AFT axis as well
	DC/c inf4_data_processed, 100, sample_period_ms, TIME, ch1_force, ch2_force, ch3_force, ch4_force
END

! Continuously compute processed force values from the INF4
WHILE collect_data
	BLOCK
		! Compute all force values in the same controller cycle
		! TODO: Use the correct formula to make this a real number
		! in some kind of engineering units
		ch1_force = DI0 + DI1 + DI2 + DI3
		ch2_force = DI4 + DI5 + DI6 + DI7
	END
END

STOPDC
STOP
"""

if __name__ == "__main__":
    # First connect to the controller and get a communication handle
    # Note that when we want to connect to both the NTM and EC we will need
    # to change the IP address or port for the EC so they aren't identical
    print("Connecting to the controller")
    hc = acsc.openCommEthernetTCP()
    # Load our program into buffer 9 (arbitrary for now)
    print("Loading program into buffer 9:\n", prg_txt)
    acsc.loadBuffer(hc, 9, prg_txt, 4096)
    print("Running buffer 9")
    acsc.runBuffer(hc, 9)
    # Collect data for a bit then set collect_data=0 to stop data collection
    time_vals = []
    ch1_force_vals = []
    ch2_force_vals = []
    ch3_force_vals = []
    ch4_force_vals = []
    dblen = 100  # The number of rows in our buffer in the ACS program
    sr = 1000 / SAMPLE_PERIOD_MS
    sleeptime = float(dblen) / float(sr) / 2 * 1.05
    print(f"Sleeping for {sleeptime} seconds each iteration")
    for i in range(20):
        print("Data collection iteration", i + 1)
        # Sleep to let buffer accumulate
        time.sleep(sleeptime)
        t0 = acsc.readReal(hc, acsc.NONE, "start_time")
        newdata = acsc.readReal(
            hc, acsc.NONE, "inf4_data_processed", 0, 2, 0, dblen // 2 - 1
        )
        t = (newdata[0] - t0) / 1000.0
        time_vals += list(t)
        ch1_force_vals += list(newdata[1])
        ch2_force_vals += list(newdata[2])
        ch3_force_vals += list(newdata[3])
        ch4_force_vals += list(newdata[4])
        time.sleep(sleeptime)
        newdata = acsc.readReal(
            hc, acsc.NONE, "inf4_data_processed", 0, 2, dblen // 2, dblen - 1
        )
        t = (newdata[0] - t0) / 1000.0
        time_vals += list(t)
        ch1_force_vals += list(newdata[1])
        ch2_force_vals += list(newdata[2])
        ch3_force_vals += list(newdata[3])
        ch4_force_vals += list(newdata[4])
    # Set the variable in the controller that will stop data collection
    acsc.writeInteger(hc, "collect_data", 0)
    # Save data to CSV
    df = pd.DataFrame()
    df["time"] = time_vals
    df["ch1_force"] = ch1_force_vals
    df["ch2_force"] = ch2_force_vals
    df["ch3_force"] = ch3_force_vals
    df["ch4_force"] = ch4_force_vals
    print("Collected data:\n", df)
    fpath = "inf4-test-data.csv"
    print("Saving to", fpath)
    df.to_csv(fpath)
