"""This is a test run script to be placed in an experiment working directory.
"""

import argparse
import Modules

parser = argparse.ArgumentParser()
parser.add_argument(
    "function", help="Function to run in the script", nargs="?"
)
parser.add_argument("section", help="Test plan section", nargs="?")
parser.add_argument("nrun", type=int, help="Run number", nargs="?")
args = parser.parse_args()

print("Running run.py")

if args.function == "process":
    print("Processing {} run {}".format(args.section, args.nrun))
