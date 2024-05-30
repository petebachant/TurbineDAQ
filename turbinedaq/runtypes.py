"""This module contains classes for experiment run types."""

from __future__ import division, print_function

import time
from subprocess import check_output

import numpy as np
from acspy import acsc
from nortek.controls import PdControl
from PyQt5 import QtCore

from . import acsprgs, daqtasks


class TurbineTow(QtCore.QThread):
    """Turbine tow run object."""

    towfinished = QtCore.pyqtSignal()

    def __init__(
        self,
        acs_ntm_hcomm: int,
        U: float,
        tsr: float,
        y_R: float,
        z_H: float,
        turbine_properties: dict,
        nidaq=True,
        vectrino=True,
        vecsavepath="",
        fbg=False,
        fbg_properties={},
        odisi=False,
        odisi_properties={},
        settling=False,
        vec_salinity=0.0,
    ):
        QtCore.QThread.__init__(self)
        self.hc = acs_ntm_hcomm
        self.U = float(U)
        self.tsr = tsr
        self.y_R = y_R
        self.z_H = z_H
        self.R = turbine_properties["radius"]
        self.H = turbine_properties["height"]
        self.turbine_type = turbine_properties["kind"]
        self.vectrino = vectrino
        self.nidaq = nidaq
        self.fbg = fbg
        self.odisi = odisi
        self.settling = settling
        self.build_acsprg()
        if self.turbine_type == "AFT":
            self.acsdaqthread = daqtasks.AftAcsDaqThread(self.hc)
        else:
            self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.maxvel = U * 1.3
        self.usetrigger = True
        self.vecsavepath = vecsavepath
        self.recordvno = True
        self.vecstatus = "Vectrino disconnected "
        self.autoaborted = False
        self.aborted = False
        self.vec_salinity = vec_salinity
        commit = check_output(["git", "rev-parse", "--verify", "HEAD"])[:-1]
        self.metadata = {
            "Tow speed (m/s)": float(U),
            "Tip speed ratio": tsr,
            "Time created": time.asctime(),
            "TurbineDAQ version": commit,
        }
        if self.vectrino:
            self.vec = PdControl()
            self.metadata["Vectrino metadata"] = {"y/R": y_R, "z/H": z_H}
        if self.nidaq:
            if self.turbine_type == "AFT":
                self.daqthread = daqtasks.AftNiDaqThread(
                    usetrigger=self.usetrigger
                )
            else:
                self.daqthread = daqtasks.NiDaqThread(
                    usetrigger=self.usetrigger
                )
            self.nidata = self.daqthread.data
            self.metadata["NI metadata"] = self.daqthread.metadata
        if self.fbg:
            self.fbgthread = daqtasks.FbgDaqThread(
                fbg_properties, usetrigger=self.usetrigger
            )
            self.metadata["FBG metadata"] = self.fbgthread.metadata
            self.fbgdata = self.fbgthread.data
        if self.odisi:
            self.odisithread = daqtasks.ODiSIDaqThread(odisi_properties)
            self.metadata["ODiSI metadata"] = self.odisithread.metadata
            # self.odisidata = self.odisithread.data

    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.

        This run should send a trigger pulse.
        """
        if self.settling:
            endpos = 9.0
        else:
            endpos = 0.0
        self.acs_prg = acsprgs.turbine_tow_prg(
            self.U,
            self.tsr,
            self.R,
            endpos=endpos,
            turbine_type=self.turbine_type,
        )

    def setvecconfig(self):
        self.vec.start_on_sync = self.usetrigger
        self.vec.sync_master = not self.usetrigger
        self.vec.sample_on_sync = False
        self.vec.sample_rate = 200
        self.vec.coordinate_system = "XYZ"
        self.vec.power_level = "High"
        self.vec.transmit_length = 3
        self.vec.sampling_volume = 3
        self.vec.sound_speed_mode = "measured"
        self.vec.salinity = self.vec_salinity
        if self.maxvel <= 4.0 and self.maxvel > 2.5:
            self.vec.vel_range = 0
        elif self.maxvel <= 2.5 and self.maxvel > 1.0:
            self.vec.vel_range = 1
        elif self.maxvel <= 1.0 and self.maxvel > 0.3:
            self.vec.vel_range = 2
        elif self.maxvel <= 0.3 or self.settling:
            self.vec.vel_range = 3
        self.vec.set_config()
        self.metadata["Vectrino metadata"][
            "Velocity range (index)"
        ] = self.vec.vel_range
        self.metadata["Vectrino metadata"][
            "Sample rate (Hz)"
        ] = self.vec.sample_rate
        self.metadata["Vectrino metadata"][
            "Coordinate system"
        ] = self.vec.coordinate_system
        self.metadata["Vectrino metadata"][
            "Salinity (ppt)"
        ] = self.vec.salinity
        self.metadata["Vectrino metadata"][
            "Transmit length"
        ] = self.vec.transmit_length
        self.metadata["Vectrino metadata"][
            "Sampling volume"
        ] = self.vec.sampling_volume
        print("Vectrino configuration set")

    def run(self):
        """Start the run.

        Comms should be open already with the controller.
        """
        acsc.setOutput(self.hc, 1, 16, 0)
        if self.vectrino:
            acsc.enable(self.hc, 0)
            acsc.enable(self.hc, 1)
            while (
                not acsc.getMotorState(self.hc, 0)["enabled"]
                or not acsc.getMotorState(self.hc, 1)["enabled"]
            ):
                self.msleep(100)
            acsc.toPoint(self.hc, None, 0, self.y_R * self.R)
            acsc.toPoint(self.hc, None, 1, self.z_H * self.H)
            while (
                not acsc.getMotorState(self.hc, 0)["in position"]
                or not acsc.getMotorState(self.hc, 1)["in position"]
            ):
                self.msleep(300)
            print("y- and z-axes in position")
            acsc.disable(self.hc, 0)
            acsc.disable(self.hc, 1)
            self.vec.serial_port = "COM2"
            self.vec.connect()
            tstart = time.time()
            self.timeout = False
            self.vecstatus = "Connecting to Vectrino..."
            while not self.vec.connected:
                self.msleep(300)
                if time.time() - tstart > 10:
                    print("Vectrino timed out")
                    self.timeout = True
                    break
            if not self.timeout:
                self.vec.stop()
                self.setvecconfig()
                if self.recordvno:
                    self.vec.start_disk_recording(self.vecsavepath)
                self.vec.start()
                self.vecstatus = "Vectrino connected "
                while self.vec.state != "Confirmation mode":
                    self.msleep(100)
                print("Vectrino in data collection mode")
                print("Waiting 6 seconds")
                self.sleep(6)
                self.daqthread.start()
                if self.fbg:
                    self.fbgthread.start()
                if self.odisi:
                    self.odisithread.start()
                self.start_motion()
        elif self.nidaq:
            self.daqthread.start()
            if self.fbg:
                self.fbgthread.start()
            if self.odisi:
                self.odisithread.start()
            # Sleep so the DAQ can start listening for the trigger
            time.sleep(1)
            self.start_motion()
        else:
            # Start motion
            self.start_motion()

    def start_motion(self):
        self.acsdaqthread.start()
        nbuf = 19
        acsc.loadBuffer(self.hc, nbuf, self.acs_prg, 2048)
        if not self.turbine_type != "AFT":
            acsc.enable(self.hc, 4)
        else:
            acsc.enable(self.hc, 6)
        acsc.enable(self.hc, 5)
        acsc.runBuffer(self.hc, nbuf)
        # Wait until the program is done executing
        prgstate = acsc.getProgramState(self.hc, nbuf)
        while prgstate == 3:
            time.sleep(0.3)
            prgstate = acsc.getProgramState(self.hc, nbuf)
        self.acsdaqthread.stop()
        if self.nidaq:
            self.daqthread.clear()
            print("NI tasks cleared")
        if self.fbg:
            self.fbgthread.stop()
        if self.odisi:
            self.odisithread.stop()
        if self.vectrino:
            if self.settling:
                # Wait 10 minutes to measure tank settling time
                print("Waiting 10 minutes")
                t0 = time.time()
                dt = 0.0
                while not self.aborted and dt < 600:
                    time.sleep(0.5)
                    dt = time.time() - t0
            if self.recordvno:
                self.vec.stop_disk_recording()
            self.vec.stop()
            self.vec.disconnect()
        print("Tow finished")
        if self.vectrino:
            if self.vec.state == "Not connected":
                self.vecstatus = "Vectrino disconnected "
            print("Resetting Vectrino")
            self.reset_vec()
        self.towfinished.emit()

    def reset_vec(self):
        self.vec.connect()
        self.vec.stop_disk_recording()
        self.vec.stop()
        self.vec.disconnect()
        self.vec.data = {}
        print("Vectrino reset")

    def abort(self):
        """This should stop everything."""
        print("Aborting turbine tow")
        self.aborted = True
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 0)
        acsc.halt(self.hc, 1)
        acsc.halt(self.hc, 4)
        acsc.halt(self.hc, 5)

    def autoabort(self):
        """This should stop everything and return carriage and turbine back
        to zero."""
        self.autoaborted = True
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 0)
        acsc.halt(self.hc, 1)
        acsc.halt(self.hc, 4)
        acsc.halt(self.hc, 5)
        acsc.toPoint(self.hc, None, 4, 0.0)
        acsc.setVelocity(self.hc, 5, 0.5)
        acsc.toPoint(self.hc, None, 5, 0.0)


class TareDragRun(QtCore.QThread):
    runfinished = QtCore.pyqtSignal()

    def __init__(self, acs_hc, U):
        QtCore.QThread.__init__(self)
        self.aborted = False
        self.hc = acs_hc
        self.U = U
        self.build_acsprg()
        self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.acsdata = self.acsdaqthread.data
        commit = check_output(["git", "rev-parse", "--verify", "HEAD"])[:-1]
        self.metadata = {
            "Tow speed (m/s)": U,
            "Time created": time.asctime(),
            "TurbineDAQ version": commit,
        }
        self.daqthread = daqtasks.NiDaqThread(usetrigger=False)
        self.nidata = self.daqthread.data
        self.metadata["NI metadata"] = self.daqthread.metadata

    def build_acsprg(self):
        """Create the ACSPL+ program for running the run.
        This run should send a trigger pulse."""
        self.acs_prg = acsprgs.tare_drag_prg(self.U)

    def run(self):
        """Start the run."""
        if not acsc.getOutput(self.hc, 1, 16):
            acsc.setOutput(self.hc, 1, 16, 1)
        self.daqthread.start()
        self.msleep(2000)  # Wait for NI to start waiting for trigger
        self.start_motion()

    def start_motion(self):
        self.acsdaqthread.start()
        nbuf = 19
        acsc.loadBuffer(self.hc, nbuf, self.acs_prg, 2048)
        acsc.enable(self.hc, 5)
        acsc.runBuffer(self.hc, nbuf)
        prgstate = acsc.getProgramState(self.hc, nbuf)
        while prgstate == 3:  # means the program is running in the controller
            time.sleep(0.3)
            prgstate = acsc.getProgramState(self.hc, nbuf)
        self.acsdaqthread.stop()
        self.daqthread.clear()
        self.runfinished.emit()

    def abort(self):
        """This should stop everything."""
        self.aborted = True
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 5)
        self.acsdaqthread.stop()
        self.daqthread.clear()


class TareTorqueRun(QtCore.QThread):
    """Tare torque run object."""

    runfinished = QtCore.pyqtSignal()

    def __init__(self, acs_hcomm, rpm, dur, odisi_properties={}):
        QtCore.QThread.__init__(self)
        self.aborted = False
        self.hc = acs_hcomm
        self.rpm = rpm
        self.dur = dur
        self.build_acsprg()
        self.acsdaqthread = daqtasks.AcsDaqThread(self.hc)
        self.acsdata = self.acsdaqthread.data
        self.vecsavepath = ""
        commit = check_output(["git", "rev-parse", "--verify", "HEAD"])[:-1]
        self.metadata = {
            "RPM": rpm,
            "Duration": dur,
            "Time created": time.asctime(),
            "TurbineDAQ version": commit,
        }
        self.daqthread = daqtasks.NiDaqThread(usetrigger=True)
        self.nidata = self.daqthread.data
        self.metadata["NI metadata"] = self.daqthread.metadata
        self.odisithread = daqtasks.ODiSIDaqThread(odisi_properties)
        # self.metadata["ODiSI metadata"] = self.odisithread.metadata

    def build_acsprg(self):
        """Create the ACSPL+ program for the run.

        This run should send a trigger pulse.
        """
        self.acs_prg = acsprgs.tare_torque_prg(self.rpm, self.dur)

    def run(self):
        """Start the run."""
        if not acsc.getOutput(self.hc, 1, 16):
            acsc.setOutput(self.hc, 1, 16, 1)
        self.daqthread.start()
        self.msleep(2000)  # Wait for NI to start waiting for trigger
        self.start_motion()

    def start_motion(self):
        self.acsdaqthread.start()
        nbuf = 19
        acsc.loadBuffer(self.hc, nbuf, self.acs_prg, 2048)
        acsc.enable(self.hc, 4)
        acsc.runBuffer(self.hc, nbuf)
        prgstate = acsc.getProgramState(self.hc, nbuf)
        while prgstate == 3:
            time.sleep(0.3)
            prgstate = acsc.getProgramState(self.hc, nbuf)
        self.acsdaqthread.stop()
        self.daqthread.clear()
        self.runfinished.emit()

    def abort(self):
        """This should stop everything."""
        acsc.stopBuffer(self.hc, 19)
        acsc.halt(self.hc, 4)
        self.acsdaqthread.stop()
        self.daqthread.clear()
        self.aborted = True


class StrutTorqueRun(TareTorqueRun):
    """A strut torque run measures the parasitic torque on the shaft caused by
    the blade support struts.

    Parameters
    ----------
    acs_hcomm : int
        ACS controller communication handle
    ref_speed : float
        Reference tow speed (m/s) for calculating RPM
    tsr : float
        Reference tip speed ratio for calculating RPM
    radius : float
        Turbine radius (m) for calculating RPM
    revs : float
        Test duration in revolutions

    """

    def __init__(self, acs_hcomm, ref_speed, tsr, radius, revs):
        # Convert ref_speed and tsr into RPM
        omega = tsr / radius * ref_speed
        self.rpm = omega / (2 * np.pi) * 60.0
        self.hc = acs_hcomm
        self.ref_speed = ref_speed
        self.tsr = tsr
        self.radius = radius
        dur = revs / self.rpm * 60
        self.dur = dur
        self.metadata = {
            "Reference speed (m/s)": ref_speed,
            "Tip speed ratio": tsr,
            "Turbine radius (m)": radius,
        }
        TareTorqueRun.__init__(self, self.hc, self.rpm, dur)
