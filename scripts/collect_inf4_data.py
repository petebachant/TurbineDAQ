"""This script collects data from the INF4 load cell amplifier as a system
integration test.
"""

import time

import pandas as pd
from acspy import acsc

from modules.acsprgs import make_aft_prg

SAMPLE_PERIOD_MS = 2
N_BUFFER_ROWS = 100
N_BUFFER_COLS = 5
N_ITERATIONS = 10

if __name__ == "__main__":
    # First connect to the controller and get a communication handle
    # Note that when we want to connect to both the NTM and EC we will need
    # to change the IP address or port for the EC so they aren't identical
    print("Connecting to the controller")
    hc = acsc.openCommEthernetTCP("10.0.0.102")
    target_serial_number = "ECM18038C"
    actual_serial_number = acsc.getSerialNumber(hc).strip()
    print("Connected to controller serial number:", actual_serial_number)
    if actual_serial_number != target_serial_number:
        raise RuntimeError("Connected to the wrong controller")
    # Stop data collection if this failed last time
    acsc.writeInteger(hc, "collect_data", 0)
    # Create and load our program into buffer 9 (arbitrary for now)
    prg_txt = make_aft_prg(
        sample_period_ms=SAMPLE_PERIOD_MS,
        n_buffer_rows=N_BUFFER_ROWS,
        n_buffer_cols=N_BUFFER_COLS,
    )
    print("Loading program into buffer 9:\n", prg_txt)
    acsc.loadBuffer(hc, 9, prg_txt, 4096)
    print("Running buffer 9")
    acsc.runBuffer(hc, 9)
    # Collect data for a bit then set collect_data=0 to stop data collection
    normalized_time_vals = []
    ch1_force_vals = []
    ch2_force_vals = []
    ch3_force_vals = []
    ch4_force_vals = []
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
            "inf4_data_processed",
            0,
            N_BUFFER_COLS - 1,
            0,
            N_BUFFER_ROWS // 2 - 1,
        )
        t = (newdata[0] - t0) / 1000.0
        normalized_time_vals += list(t)
        ch1_force_vals += list(newdata[1])
        ch2_force_vals += list(newdata[2])
        ch3_force_vals += list(newdata[3])
        ch4_force_vals += list(newdata[4])
        time.sleep(sleeptime)
        newdata = acsc.readReal(
            hc,
            acsc.NONE,
            "inf4_data_processed",
            0,
            N_BUFFER_COLS - 1,
            N_BUFFER_ROWS // 2,
            N_BUFFER_ROWS - 1,
        )
        t = (newdata[0] - t0) / 1000.0
        normalized_time_vals += list(t)
        ch1_force_vals += list(newdata[1])
        ch2_force_vals += list(newdata[2])
        ch3_force_vals += list(newdata[3])
        ch4_force_vals += list(newdata[4])
    # Set the variable in the controller that will stop data collection
    acsc.writeInteger(hc, "collect_data", 0)
    # Save data to CSV
    df = pd.DataFrame()
    df["time_s"] = normalized_time_vals
    df["ch1_force"] = ch1_force_vals
    df["ch2_force"] = ch2_force_vals
    df["ch3_force"] = ch3_force_vals
    df["ch4_force"] = ch4_force_vals
    print("Collected data:\n", df)
    fpath = "inf4-test-data.csv"
    print("Saving to", fpath)
    df.to_csv(fpath, index=False)
