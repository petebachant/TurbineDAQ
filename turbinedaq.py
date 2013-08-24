# -*- coding: utf-8 -*-
"""
Created on Thu Aug 15 20:43:44 2013

@author: Pete

This is the turbineDAQ main code.

"""

from __future__ import division
from PyQt4.QtCore import *
from PyQt4.QtGui import *
import PyQt4.Qwt5 as qwt
import numpy as np
from acsc import acsc
import daqtasks
import vectasks


# Log run metadata as JSON
# Move Vectrino first?
# Start Vectrino and wait for it to enter data collection mode
# Start NI waiting for a trigger pulse
# Start ACS program


def movetraverse(y, z):
    """Maybe this shouldn't even be a function?"""
    pass


def main():
    vecrun = vectasks.VectrinoRun("Some name")
    vecrun.comport = "COM1"
    vecrun.start()

if __name__ == "__main__":
    main()