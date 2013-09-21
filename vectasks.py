# -*- coding: utf-8 -*-
"""
Created on Tue Aug 20 18:58:38 2013

@author: Pete
"""

from pdcommpy.pdcommpy import PdControl
from PyQt4 import QtCore
import time


class VectrinoThread(QtCore.QThread):
    def __init__(self, usetrigger=True):
        QtCore.QThread.__init__(self)
        print "Vectrino thread initiated..."
        self.vec = PdControl()
        self.usetrigger = usetrigger
        self.comport = "COM2"
        self.record = True
        self.isconnected = self.vec.is_connected()
        self.savepath = ""
        self.savename = "vectrino"
        self.vecstatus = "Vectrino disconnected "
        print "Vectrino thread init done"
        
    def setconfig(self):
        self.vec.set_start_on_synch(self.usetrigger)
        self.vec.set_synch_master(not self.usetrigger)
        self.vec.set_sample_on_synch(False)
        self.vec.set_sample_rate(200)
        self.vec.set_vel_range(2)
        self.vec.set_config()
        print "Vectrino configuration set"

    def run(self):
        print "Vectrino thread started..."
        self.vec.set_serial_port(self.comport)
        self.vec.connect()
        tstart = time.time()
        self.timeout = False
        self.vecstatus = "Connecting to Vectrino..."
        while not self.vec.connected:
            time.sleep(0.5)
            self.vec.is_connected()
            if time.time() - tstart > 10:
                print "Vectrino timed out"
                self.timeout = True
                break
        if not self.timeout:
            self.vec.stop()
            self.setconfig()
            if self.record:
                self.vec.start_disk_recording(self.savepath+"/"+self.savename)
            self.vec.start()
            self.vecstatus = "Vectrino connected "

    def getstatus(self):
        self.status = self.vec.inquire_state()
        return self.status
        
    def stop(self):
        if self.record:
            self.vec.stop_disk_recording()
        self.vec.stop()
        self.vec.disconnect()

class ConnectThread(QtCore.QThread):
    def __init__(self, vecthread):
        QtCore.QThread.__init__(self)
        self.vecthread = vecthread
        print "Connect thread initiated..."
        connected = QtCore.pyqtSignal()
        
    def run(self):
        self.vecthread.vec.connect()
        self.isconnected = self.vecthread.vec.is_connected()
        while not self.isconnected:
            time.sleep(0.3)
            self.isconnected = self.vecthread.vec.is_connected()
        self.emit(self.connected)
            
            
if __name__ == "__main__":
    pass