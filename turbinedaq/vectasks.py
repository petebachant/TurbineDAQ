# -*- coding: utf-8 -*-
"""
Created on Tue Aug 20 18:58:38 2013

@author: Pete
"""

from nortek.controls import PdControl
from PyQt5 import QtCore
import time


class VectrinoThread(QtCore.QThread):
    """Thread for running Vectrino"""

    collecting = QtCore.pyqtSignal()
    connectsignal = QtCore.pyqtSignal(bool)

    def __init__(
        self, maxvel=2.5, usetrigger=True, record=False, salinity=0.0
    ):
        QtCore.QThread.__init__(self)
        print("Vectrino thread initialized")
        self.vec = PdControl()
        self.vecdata = self.vec.data
        self.usetrigger = usetrigger
        self.maxvel = maxvel
        self.comport = "COM2"
        self.record = record
        self.isconnected = self.vec.connected
        self.savepath = ""
        self.vecstatus = "Vectrino disconnected "
        self.enable = True
        self.salinity = salinity
        print("Vectrino thread init done")

    def setconfig(self):
        self.vec.start_on_sync = self.usetrigger
        self.vec.sync_master = not self.usetrigger
        self.vec.sample_on_sync = False
        self.vec.sample_rate = 200
        self.vec.transmit_length = 3
        self.vec.sampling_volume = 3
        self.vec.sound_speed_mode = "measured"
        self.vec.salinity = self.salinity
        self.vec.power_level = "High"
        if self.maxvel <= 4.0 and self.maxvel > 2.5:
            self.vec.vel_range = 0
        elif self.maxvel <= 2.5 and self.maxvel > 1.0:
            self.vec.vel_range = 1
        elif self.maxvel <= 1.0 and self.maxvel > 0.3:
            self.vec.vel_range = 2
        self.vec.set_config()
        print("Vectrino configuration set")

    def run(self):
        self.vec.serial_port = self.comport
        self.vec.connect()
        tstart = time.time()
        self.timeout = False
        self.vecstatus = "Connecting to Vectrino..."
        while not self.vec.connected:
            time.sleep(0.5)
            if time.time() - tstart > 10:
                print("Vectrino timed out")
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
                time.sleep(0.1)
            print("Vectrino in data collection mode")
            time.sleep(6)
            self.collecting.emit()
            print("Vectrino collecting")

    def getstatus(self):
        return self.vec.state

    def stop(self):
        self.enable = False
        if self.record:
            self.vec.stop_disk_recording()
        self.vec.stop()
        self.vec.disconnect()
        self.vecstatus = "Vectrino disconnected "


class StopThread(QtCore.QThread):
    def __init__(self, vec):
        QtCore.QThread.__init__(self)
        self.vec = vec

    def run(self):
        self.vec.stop()
        self.vec.disconnect()


class ResetThread(QtCore.QThread):
    """Thread for resetting Vectrino"""

    def __init__(self):
        QtCore.QThread.__init__(self)
        print("Vectrino reset thread initialized")
        self.vec = PdControl()
        self.comport = "COM2"
        self.isconnected = self.vec.connected
        self.vecstatus = "Vectrino disconnected "
        self.enable = True
        print("Vectrino thread init done")

    def run(self):
        self.vec.serial_port = self.comport
        self.vec.connect()
        tstart = time.time()
        self.timeout = False
        self.vecstatus = "Connecting to Vectrino..."
        while not self.vec.connected:
            time.sleep(0.3)
            if time.time() - tstart > 10:
                print("Vectrino timed out")
                self.timeout = True
                break
        if not self.timeout:
            self.vec.stop()
            self.vecstatus = "Vectrino connected "
            while self.vec.state != "Confirmation mode":
                time.sleep(0.3)
            print("Vectrino in data confirmation mode")
            self.stop()

    def stop(self):
        self.vec.stop_disk_recording()
        self.vec.stop()
        while self.vec.state != "Command mode":
            time.sleep(0.3)
        self.vec.disconnect()
        self.vecstatus = "Vectrino disconnected "


class ConnectThread(QtCore.QThread):
    connected = QtCore.pyqtSignal()

    def __init__(self, vecthread):
        QtCore.QThread.__init__(self)
        self.vecthread = vecthread
        print("Connect thread initiated...")

    def run(self):
        self.vecthread.vec.connect()
        while not self.vecthread.vec.connected:
            time.sleep(0.3)
        self.emit(self.connected)


class MonitorThread(QtCore.QThread):
    def __init__(self, vec):
        QtCore.QThread.__init__(self)
        self.vec = vec

    def run(self):
        while self.vec.state == "Confirmation mode":
            time.sleep(0.3)
            print(len(self.vec.data["t"]))


if __name__ == "__main__":
    pass
