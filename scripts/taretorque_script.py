"""This is a non-GUI tare torque running program.

It does not work in its current form!
"""

import matplotlib.pyplot as plt
import numpy as np

# Create arrays for U and tsr
speeds = np.array([0.5, 1.0, 1.5, 2.0])
tsrs = np.arange(0.1, 3.2, 0.1)
rpms = []

# Set working directory
working_dir = ""

# Turbine parameters
r = 0.5

# Start recording data

for U in speeds:
    filename = "something"
    savepath = working_dir + "/tare drag/" + filename
    for tsr in tsrs:
        omega = tsr*U/r
        rpm = omega/(2*np.pi)*60
        rpms.append(rpm)
        print(rpm)
        # Run experiment
