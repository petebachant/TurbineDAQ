# -*- coding: utf-8 -*-
"""
Created on Tue Aug 20 18:58:38 2013

@author: Pete
"""

import pdcommpy.pdcommpy as pd
from PyQt4 import QtCore
import numpy as np
import time


class DataGet(pd.EventHandler):
    def OnNewData(self, hType=1):
        print "Got new data"


class VectrinoRun(QtCore.QThread):
    def __init__(self, usetrigger=True):
        QtCore.QThread.__init__(self)
        
        self.usetrigger = usetrigger
        self.comport = "COM5"
        self.record = True
        self.isconnected = pd.is_connected()
        
        self.data = {"u" : np.array([]),
                     "v" : np.array([]),
                     "w" : np.array([]),
                     "w2" : np.array([]),
                     "snr" : np.array([]),
                     "corr" : np.array([])}
                     
        self.dataget = pd.EventHandler()
        self.dataget.init_data(self.data)
        
    def connectvec(self):
        pd.set_serial_port(self.comport)
        conthread = VectrinoConnect(self)
        conthread.start()
        
    def setconfig(self):
        pd.set_start_on_synch(self.usetrigger)
        pd.set_synch_master(not self.usetrigger)
        pd.set_sample_on_synch(False)
        pd.set_sampling_rate(200)
        pd.set_vel_range(2)
        pd.set_config()

    def run(self):
        self.setconfig()
        # Not sure about the order of events here
        if not self.isconnected:
            self.connectvec()
            while not self.isconnected:
                self.isconnected = pd.is_connected()
                time.sleep(0.3)
                
        pd.stop()
        
        if self.record:
            pd.start_disk_recording("test/test.vno")
        
        pd.start()

    def getstatus(self):
        self.status = pd.inquire_state()
        return self.status
        
class VectrinoConnect(QtCore.QThread):
    def __init__(self, vecrun):
        QtCore.QThread.__init__(self)
        self.vecrun = vecrun
        
    def run(self):
        pd.connect()
        self.vecrun.isconnected = pd.is_connected()
        while not self.vecrun.isconnected:
            time.sleep(0.3)
            self.vecrun.isconnected = pd.is_connected()
            
            
if __name__ == "__main__":
    print "Yo"