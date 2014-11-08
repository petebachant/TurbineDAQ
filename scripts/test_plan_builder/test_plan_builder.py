# -*- coding: utf-8 -*-
"""
Created on Thu Feb 20 19:15:28 2014

@author: Pete
"""
from __future__ import division, print_function
import numpy as np
import xlwt

# Constants
R = 0.5
A = 1.0
D = 1.0

tsrs = np.arange(0.1, 3.15, 0.1)
tsr_wake = 1.9
speeds = np.arange(0.4, 1.45, 0.2)
z_H = np.arange(0, 0.75, 0.125)
y_R = np.hstack([-3.,-2.75,-2.5,-2.25,-2.,-1.8, np.arange(-1.6,0.1,0.1)])
y_R = np.hstack([y_R, -np.flipud(y_R[0:-1])])
y_R = np.round(y_R, decimals=4)

# Add regular experiment sections and top level types
sections = []
types = []
for u in speeds:
    sections.append("Perf-" + str(u))
for u in speeds:
    sections.append("Wake-" + str(u))
    
# Add tare drag and tare torque to sections
sections.append("Tare drag")
sections.append("Tare torque")
# Compute highest and lowest RPMs for tare torque
rpm_low = np.min(tsrs)*np.min(speeds)/R*60/(2*np.pi)
rpm_high = np.max(tsrs)*np.max(speeds)/R*60/(2*np.pi)
rpms_tt = np.linspace(rpm_low, rpm_high)
times_tt = 30 # 30 second runs for tare torque

# Create Excel sheet
wb = xlwt.Workbook()
sheet_tl = wb.add_sheet("Top level")
sheet_tl.write(0, 0, "Type")
sheet_tl.write(0, 1, "U")
sheet_tl.write(0, 2, "TSR")

for n in range(len(sections)):
    if "Perf" in sections[n]:
        sheet_tl.write(n+1, 0, "Perf curve")
        sheet_tl.write(n+1, 1, float(sections[n].split("-")[-1]))
        sheet_tl.write(n+1, 2, str(tsrs[0]) + "--" + str(tsrs[-1]))
    elif "Wake" in sections[n]:
        sheet_tl.write(n+1, 0, "Wake map")
        sheet_tl.write(n+1, 1, float(sections[n].split("-")[-1]))
        sheet_tl.write(n+1, 2, tsr_wake)
    else:
        pass
    
print(rpms_tt)
for section in sections:
    sheet = wb.add_sheet(section)
