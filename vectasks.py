# -*- coding: utf-8 -*-
"""
Created on Tue Aug 20 18:58:38 2013

@author: Pete
"""

from pdcommpy.pdcommpy import PdControl
from PyQt4 import QtCore
import time


class VectrinoThread(QtCore.QThread):
    """Thread for running Vectrino"""
    collecting = QtCore.pyqtSignal()
    connectsignal = QtCore.pyqtSignal(bool)
    def __init__(self, maxvel=2.5, usetrigger=True, record=False):
        QtCore.QThread.__init__(self)
        print "Vectrino thread initialized"
        self.vec = PdControl()
        self.vecdata = self.vec.data
        self.usetrigger = usetrigger
        self.maxvel = maxvel
        self.comport = "COM2"
        self.record = record
        self.isconnected = self.vec.is_connected()
        self.savepath = ""
        self.vecstatus = "Vectrino disconnected "
        self.enable = True
        print "Vectrino thread init done"
        
    def setconfig(self):
        self.vec.set_start_on_synch(self.usetrigger)
        self.vec.set_synch_master(not self.usetrigger)
        self.vec.set_sample_on_synch(False)
        self.vec.set_sample_rate(200)
        self.vec.set_transmit_length(1.8)
        self.vec.set_sampling_volume(7.0)
        self.vec.set_salinity(0.0)
        self.vec.set_power_level()
        if self.maxvel <= 4.0 and self.maxvel > 2.5:
            self.vec.set_vel_range(0)
        elif self.maxvel <= 2.5 and self.maxvel > 1.0:
            self.vec.set_vel_range(1)
        elif self.maxvel <= 1.0 and self.maxvel > 0.3:
            self.vec.set_vel_range(2)
        self.vec.set_config()
        print "Vectrino configuration set"

    def run(self):
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
                self.connectsignal.emit(False)
                break
        if not self.timeout:
            self.connectsignal.emit(True)
            self.vec.stop()
            self.setconfig()
            if self.record:
                self.vec.start_disk_recording(self.savepath)
            self.vec.start()
            self.vecstatus = "Vectrino connected "
            while self.vec.state != "Confirmation mode":
                self.vec.inquire_state()
                time.sleep(0.1)
            self.collecting.emit()
            print "Vectrino collecting"

    def getstatus(self):
        self.status = self.vec.inquire_state()
        return self.status
        
    def stop(self):
        self.enable = False
        if self.record:
            self.vec.stop_disk_recording()
        self.vec.stop()
        self.vec.disconnect()
        self.vecstatus = "Vectrino disconnected "
        

class ConnectThread(QtCore.QThread):
    connected = QtCore.pyqtSignal()
    def __init__(self, vecthread):
        QtCore.QThread.__init__(self)
        self.vecthread = vecthread
        print "Connect thread initiated..."
        
    def run(self):
        self.vecthread.vec.connect()
        self.isconnected = self.vecthread.vec.is_connected()
        while not self.isconnected:
            time.sleep(0.3)
            self.isconnected = self.vecthread.vec.is_connected()
        self.emit(self.connected)
        

class MonitorThread(QtCore.QThread):
    def __init__(self, vec):
        QtCore.QThread.__init__(self)
        self.vec = vec
    
    def run(self):
        while self.vec.state == "Confirmation mode":
            self.vec.inquire_state()
            time.sleep(0.3)
            print len(self.vec.data["t"])
            
            
if __name__ == "__main__":
    pass