# -*- coding: utf-8 -*-
"""
Created on Tue Jan 13 12:47:12 2015

@author: Pete

This is a test run script to be placed in an experiment working directory.

"""
from __future__ import print_function
import argparse
import Modules

parser = argparse.ArgumentParser()
parser.add_argument("function", help="Function to run in the script",
                    nargs="?")
parser.add_argument("section", help="Test plan section", nargs="?")
parser.add_argument("nrun", type=int, help="Run number", nargs="?")
args = parser.parse_args()

print("Running run.py")

if args.function == "process":
    print("Processing {} run {}".format(args.section, args.nrun))