# -*- coding: utf-8 -*-
"""
Created on Tue Jan 27 15:09:30 2015

@author: Pete

This module is a test processing module for data created with TurbineDAQ.

"""

from __future__ import division, print_function
import pandas as pd

print("Imported processing module")

def process_run(section, nrun):
    print("Processing", section, "run", nrun)
    summary = pd.Series()
    summary["mean_cp"] = 0.3
    return summary

def process_latest_run(section):
    print("Processing latest run of", section)