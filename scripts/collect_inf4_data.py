"""This script collects data from the INF4 load cell amplifier as a system
integration test.
"""

import time
import warnings

import pandas as pd
from acspy import acsc

from turbinedaq.acsprgs import make_aft_prg

SAMPLE_PERIOD_MS = 2
N_BUFFER_ROWS = 100
N_ITERATIONS = 10

if __name__ == "__main__":
    # First connect to the controller and get a communication handle
    # Note that when we want to connect to both the NTM and EC we will need
    # to change the IP address or port for the EC so they aren't identical
    print("Connecting to the controller")
    hc = acsc.openCommEthernetTCP("10.0.0.100")
    # Stop data collection if this failed last time
    try:
        acsc.writeInteger(hc, "collect_data", 0)
    except Exception as e:
        warnings.warn(f"Can't write 'collect_data': {e}")
    # Create and load our program into buffer 9 (arbitrary for now)
    prg_txt = make_aft_prg(
        sample_period_ms=SAMPLE_PERIOD_MS,
        n_buffer_rows=N_BUFFER_ROWS,
    )
    buffno = 17
    print(f"Loading program into buffer {buffno}:\n", prg_txt)
    acsc.loadBuffer(hc, buffno, prg_txt, 6000)
    print(f"Running buffer {buffno}")
    acsc.runBuffer(hc, buffno)
    # Collect data for a bit then set collect_data=0 to stop data collection
    normalized_time_vals = []
    ch1_force_vals = []
    ch2_force_vals = []
    ch3_force_vals = []
    ch4_force_vals = []
    aft_pos_vals = []
    aft_rpm_vals = []
    carriage_vel_vals = []
    sr = 1000 / SAMPLE_PERIOD_MS
    sleeptime = float(N_BUFFER_ROWS) / float(sr) / 2 * 1.05
    print(f"Sleeping for {sleeptime} seconds each iteration")
    for i in range(N_ITERATIONS):
        print("Data collection iteration", i + 1)
        # Sleep to let buffer accumulate
        time.sleep(sleeptime)
        t0 = acsc.readReal(hc, acsc.NONE, "start_time")
        newdata = acsc.readReal(
            hc,
            acsc.NONE,
            "aft_data",
            0,
            7,
            0,
            N_BUFFER_ROWS // 2 - 1,
        )
        t = (newdata[0] - t0) / 1000.0
        normalized_time_vals += list(t)
        ch1_force_vals += list(newdata[1])
        ch2_force_vals += list(newdata[2])
        ch3_force_vals += list(newdata[3])
        ch4_force_vals += list(newdata[4])
        aft_pos_vals += list(newdata[5])
        aft_rpm_vals += list(newdata[6])
        carriage_vel_vals += list(newdata[7])
        time.sleep(sleeptime)
        newdata = acsc.readReal(
            hc,
            acsc.NONE,
            "aft_data",
            0,
            7,
            N_BUFFER_ROWS // 2,
            N_BUFFER_ROWS - 1,
        )
        t = (newdata[0] - t0) / 1000.0
        normalized_time_vals += list(t)
        ch1_force_vals += list(newdata[1])
        ch2_force_vals += list(newdata[2])
        ch3_force_vals += list(newdata[3])
        ch4_force_vals += list(newdata[4])
        aft_pos_vals += list(newdata[5])
        aft_rpm_vals += list(newdata[6])
        carriage_vel_vals += list(newdata[7])
    # Set the variable in the controller that will stop data collection
    acsc.writeInteger(hc, "collect_data", 0)
    # Save data to CSV
    df = pd.DataFrame()
    df["time_s"] = normalized_time_vals
    df["ch1_force"] = ch1_force_vals
    df["ch2_force"] = ch2_force_vals
    df["ch3_force"] = ch3_force_vals
    df["ch4_force"] = ch4_force_vals
    df["aft_rpm"] = aft_rpm_vals
    df["aft_pos"] = aft_pos_vals
    df["carriage_vel"] = carriage_vel_vals
    print("Collected data:\n", df)
    fpath = "inf4-test-data.csv"
    print("Saving to", fpath)
    df.to_csv(fpath, index=False)
