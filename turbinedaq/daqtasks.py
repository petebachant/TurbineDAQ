"""DAQ tasks."""

import time
import warnings

try:
    import daqmx
except Exception as e:
    warnings.warn(f"Could not import daqmx: {e}")
import micronopt
import nidaqmx
import numpy as np
from acspy import acsc, prgs
from acspy.acsc import AcscError
from nidaqmx.stream_readers import (
    AnalogMultiChannelReader,
    CounterReader,
)
from nidaqmx.system.storage.persisted_channel import (
    PersistedChannel as GlobalVirtualChannel,
)
from pxl import fdiff
from pxl import timeseries as ts
from PyQt5 import QtCore

from turbinedaq.acsprgs import make_aft_prg


class NiDaqThread(QtCore.QThread):
    collecting = QtCore.pyqtSignal()
    cleared = QtCore.pyqtSignal()

    def __init__(self, usetrigger=True):
        QtCore.QThread.__init__(self)
        # Some parameters for the thread
        self.usetrigger = usetrigger
        self.collect = True
        # Create some meta data for the run
        self.metadata = {}
        # Initialize sample rate
        self.sr = 2000
        self.metadata["Sample rate (Hz)"] = self.sr
        self.nsamps = int(self.sr / 10)
        # Create a dict of arrays for storing data
        self.data = {
            "turbine_angle": np.array([]),
            "turbine_rpm": np.array([]),
            "torque_trans": np.array([]),
            "torque_arm": np.array([]),
            "drag_left": np.array([]),
            "drag_right": np.array([]),
            "time": np.array([]),
            "carriage_pos": np.array([]),
            "LF_left": np.array([]),
            "LF_right": np.array([]),
        }
        # Create tasks
        self.analogtask = nidaqmx.Task("analog-inputs")
        self.carpostask = nidaqmx.Task("carriage-pos")
        self.turbangtask = nidaqmx.Task("turbine-angle")
        self.odisistarttask = nidaqmx.Task("odisi-start")
        self.odisistarttask.do_channels.add_do_chan(
            "/cDAQ9188-16D66BBMod1/port0/line0"
        )
        self.odisistoptask = nidaqmx.Task("odisi-stop")
        self.odisistoptask.do_channels.add_do_chan(
            "/cDAQ9188-16D66BBMod1/port0/line1"
        )
        # Add channels to tasks
        self.analogchans = [
            "torque_trans",
            "torque_arm",
            "drag_left",
            "drag_right",
            "LF_left",
            "LF_right",
        ]
        self.carposchan = "carriage_pos"
        self.turbangchan = "turbine_angle"
        self.analogtask.add_global_channels(
            [GlobalVirtualChannel(c) for c in self.analogchans]
        )
        self.carpostask.add_global_channels(
            [GlobalVirtualChannel(self.carposchan)]
        )
        self.turbangtask.add_global_channels(
            [GlobalVirtualChannel(self.turbangchan)]
        )
        # Get channel information to add to metadata
        self.chaninfo = {}
        for channame in self.analogchans:
            self.chaninfo[channame] = {}
            scale = channame + "_scale"
            self.chaninfo[channame]["Scale name"] = scale
            self.chaninfo[channame]["Scale slope"] = daqmx.GetScaleLinSlope(
                scale
            )
            self.chaninfo[channame][
                "Scale y-intercept"
            ] = daqmx.GetScaleLinYIntercept(scale)
            self.chaninfo[channame][
                "Scaled units"
            ] = daqmx.GetScaleScaledUnits(scale)
            self.chaninfo[channame][
                "Prescaled units"
            ] = daqmx.GetScalePreScaledUnits(scale)
        self.chaninfo[self.turbangchan] = {}
        self.chaninfo[self.turbangchan][
            "Pulses per rev"
        ] = daqmx.GetCIAngEncoderPulsesPerRev(
            self.turbangtask._handle, self.turbangchan
        )
        self.chaninfo[self.turbangchan]["Units"] = daqmx.GetCIAngEncoderUnits(
            self.turbangtask._handle, self.turbangchan
        )
        self.chaninfo[self.carposchan] = {}
        self.chaninfo[self.carposchan][
            "Distance per pulse"
        ] = daqmx.GetCILinEncoderDisPerPulse(
            self.carpostask._handle, self.carposchan
        )
        self.chaninfo[self.carposchan]["Units"] = daqmx.GetCILinEncoderUnits(
            self.carpostask._handle, self.carposchan
        )
        self.metadata["Channel info"] = self.chaninfo
        # Configure sample clock timing
        daqmx.CfgSampClkTiming(
            self.analogtask._handle,
            "",
            self.sr,
            daqmx.Val_Rising,
            daqmx.Val_ContSamps,
            self.nsamps,
        )
        # Get source for analog sample clock
        trigname = daqmx.GetTerminalNameWithDevPrefix(
            self.analogtask._handle, "ai/SampleClock"
        )
        daqmx.CfgSampClkTiming(
            self.carpostask._handle,
            trigname,
            self.sr,
            daqmx.Val_Rising,
            daqmx.Val_ContSamps,
            self.nsamps,
        )
        daqmx.CfgSampClkTiming(
            self.turbangtask._handle,
            trigname,
            self.sr,
            daqmx.Val_Rising,
            daqmx.Val_ContSamps,
            self.nsamps,
        )
        # If using trigger for analog signals set source to chassis PFI0
        if self.usetrigger:
            daqmx.CfgDigEdgeStartTrig(
                self.analogtask._handle,
                "/cDAQ9188-16D66BB/PFI0",
                daqmx.Val_Falling,
            )
        # Set trigger functions for counter channels
        daqmx.SetStartTrigType(self.carpostask._handle, daqmx.Val_DigEdge)
        daqmx.SetStartTrigType(self.turbangtask._handle, daqmx.Val_DigEdge)
        trigsrc = daqmx.GetTrigSrcWithDevPrefix(
            self.analogtask._handle, "ai/StartTrigger"
        )
        daqmx.SetDigEdgeStartTrigSrc(self.carpostask._handle, trigsrc)
        daqmx.SetDigEdgeStartTrigSrc(self.turbangtask._handle, trigsrc)
        daqmx.SetDigEdgeStartTrigEdge(
            self.carpostask._handle, daqmx.Val_Rising
        )
        daqmx.SetDigEdgeStartTrigEdge(
            self.turbangtask._handle, daqmx.Val_Rising
        )

    def run(self):
        """Start DAQmx tasks."""
        stream = self.analogtask.in_stream
        reader = AnalogMultiChannelReader(stream)
        stream_cp = self.carpostask.in_stream
        reader_cp = CounterReader(stream_cp)
        stream_ta = self.turbangtask.in_stream
        reader_ta = CounterReader(stream_ta)
        data = np.zeros((len(self.analogchans), self.nsamps))
        carpos = np.zeros(self.nsamps)
        turbang = np.zeros(self.nsamps)

        def every_n_samples(
            task_handle, every_n_samps_event_type, n_samps, callback_data
        ):
            """Function called every N samples"""
            reader.read_many_sample(
                data, number_of_samples_per_channel=n_samps
            )
            self.data["torque_trans"] = np.append(
                self.data["torque_trans"], data[0, :], axis=0
            )
            self.data["torque_arm"] = np.append(
                self.data["torque_arm"], data[1, :], axis=0
            )
            self.data["drag_left"] = np.append(
                self.data["drag_left"], data[2, :], axis=0
            )
            self.data["drag_right"] = np.append(
                self.data["drag_right"], data[3, :], axis=0
            )
            self.data["LF_left"] = np.append(
                self.data["LF_left"], data[4, :], axis=0
            )
            self.data["LF_right"] = np.append(
                self.data["LF_right"], data[5, :], axis=0
            )
            self.data["time"] = (
                np.arange(len(self.data["torque_trans"]), dtype=float)
                / self.sr
            )
            reader_cp.read_many_sample_double(
                carpos, number_of_samples_per_channel=n_samps
            )
            self.data["carriage_pos"] = np.append(
                self.data["carriage_pos"], carpos
            )
            reader_ta.read_many_sample_double(
                turbang, number_of_samples_per_channel=n_samps
            )
            self.data["turbine_angle"] = np.append(
                self.data["turbine_angle"], turbang
            )
            self.data["turbine_rpm"] = ts.smooth(
                fdiff.second_order_diff(
                    self.data["turbine_angle"], self.data["time"]
                )
                / 6.0,
                8,
            )
            return 0  # The function should return an integer

        self.analogtask.register_every_n_samples_acquired_into_buffer_event(
            sample_interval=self.nsamps, callback_method=every_n_samples
        )
        # Start the tasks
        self.carpostask.start()
        self.turbangtask.start()
        self.analogtask.start()
        # Send trigger for ODiSI Interrogater
        self.odisistarttask.start()
        for n in range(1):
            self.odisistarttask.write(True)
            time.sleep(1e-6)  # make longer to see pulse width on oscilloscope
            self.odisistarttask.write(False)
            time.sleep(1e-6)  # make longer to see pulse width on oscilloscope
        self.odisistarttask.stop()
        self.odisistarttask.close()
        print("ODiSI interrogator starting measurements...")
        self.collecting.emit()
        # Keep the acquisition going until task it cleared
        while self.collect:
            time.sleep(0.2)

    def stopdaq(self):
        self.analogtask.stop()
        self.carpostask.stop()
        self.turbangtask.stop()
        # Send stop trigger to ODiSI Interrogator
        self.odisistoptask.start()
        for n in range(1):
            self.odisistoptask.write(True)
            time.sleep(1e-6)  # make longer to see pulse width on oscilloscope
            self.odisistoptask.write(False)
            time.sleep(1e-6)  # make longer to see pulse width on oscilloscope
        self.odisistoptask.stop
        self.odisistoptask.close()
        print("ODiSI interrogator stopping measurements...")

    def clear(self):
        self.stopdaq()
        self.analogtask.close()
        self.carpostask.close()
        self.turbangtask.close()
        self.collect = False
        self.cleared.emit()


class TareTorqueDAQ(QtCore.QThread):
    pass


class TareDragDAQ(QtCore.QThread):
    pass


class AcsDaqThread(QtCore.QThread):
    def __init__(self, acs_hc, sample_rate=1000, bufflen=100, makeprg=False):
        QtCore.QThread.__init__(self)
        self.hc = acs_hc
        self.collectdata = True
        self.data = {
            "carriage_vel": np.array([]),
            "turbine_rpm": np.array([]),
            "time": np.array([]),
        }
        self.dblen = bufflen
        self.sr = sample_rate
        self.sleeptime = float(self.dblen) / float(self.sr) / 2 * 1.05
        self.makeprg = makeprg

    def run(self):
        def collecting_data() -> bool:
            try:
                return bool(
                    acsc.readInteger(self.hc, acsc.NONE, "collect_data")
                )
            except AcscError as e:
                warnings.warn(f"Failed to read 'collect_data': {e}")
                return False

        if self.makeprg:
            self.makedaqprg()
            acsc.loadBuffer(self.hc, 19, self.prg, 1024)
            acsc.runBuffer(self.hc, 19)
        while not collecting_data():
            time.sleep(0.01)
        while self.collectdata:
            time.sleep(self.sleeptime)
            t0 = acsc.readReal(self.hc, acsc.NONE, "start_time")
            newdata = acsc.readReal(
                self.hc, acsc.NONE, "data", 0, 2, 0, self.dblen // 2 - 1
            )
            t = (newdata[0] - t0) / 1000.0
            self.data["time"] = np.append(self.data["time"], t)
            self.data["carriage_vel"] = np.append(
                self.data["carriage_vel"], newdata[1]
            )
            self.data["turbine_rpm"] = np.append(
                self.data["turbine_rpm"], newdata[2]
            )
            time.sleep(self.sleeptime)
            newdata = acsc.readReal(
                self.hc,
                acsc.NONE,
                "data",
                0,
                2,
                self.dblen // 2,
                self.dblen - 1,
            )
            t = (newdata[0] - t0) / 1000.0
            self.data["time"] = np.append(self.data["time"], t)
            self.data["time"] = self.data["time"] - self.data["time"][0]
            self.data["carriage_vel"] = np.append(
                self.data["carriage_vel"], newdata[1]
            )
            self.data["turbine_rpm"] = np.append(
                self.data["turbine_rpm"], newdata[2]
            )

    def makedaqprg(self):
        """Create an ACSPL+ program to load into the controller"""
        self.prg = prgs.ACSPLplusPrg()
        self.prg.addline(
            "! This is a data collection program auto-generated by TurbineDAQ"
        )
        self.prg.declare_2darray("GLOBAL", "real", "data", 3, self.dblen)
        self.prg.addline("GLOBAL REAL start_time")
        self.prg.addline("GLOBAL INT collect_data")
        self.prg.addline("collect_data = 1")
        self.prg.add_dc(
            "data", self.dblen, self.sr, "TIME, FVEL(5), FVEL(4)", "/c"
        )
        self.prg.addline("start_time = TIME")
        self.prg.addline("TILL collect_data = 0")
        self.prg.addline("STOPDC")
        self.prg.addstopline()

    def stop(self):
        self.collectdata = False
        try:
            acsc.writeInteger(self.hc, "collect_data", 0)
        except:
            print("Could not write collect_data = 0")


class AftAcsDaqThread(QtCore.QThread):
    """A thread for collecting data from the ACS EC controller that runs the
    AFT test bed.
    """

    def __init__(self, acs_hc, sample_rate=1000, bufflen=100, makeprg=False):
        QtCore.QThread.__init__(self)
        self.hc = acs_hc
        self.collectdata = True
        self.data = {
            "time": np.array([]),
            "load_cell_ch1": np.array([]),
            "load_cell_ch2": np.array([]),
            "load_cell_ch3": np.array([]),
            "load_cell_ch4": np.array([]),
            "turbine_pos": np.array([]),
            "turbine_rpm": np.array([]),
            "carriage_vel": np.array([]),
        }
        self.dblen = bufflen
        self.sr = sample_rate
        self.sleeptime = float(self.dblen) / float(self.sr) / 2 * 1.05
        self.makeprg = makeprg

    def run(self):
        def collecting_data() -> bool:
            try:
                return bool(
                    acsc.readInteger(self.hc, acsc.NONE, "collect_data")
                )
            except AcscError as e:
                warnings.warn(f"Failed to read 'collect_data': {e}")
                return False

        if self.makeprg:
            self.makedaqprg()
            acsc.loadBuffer(self.hc, 17, self.prg, 1024)
            acsc.runBuffer(self.hc, 17)
        while not collecting_data():
            time.sleep(0.01)
        while self.collectdata:
            time.sleep(self.sleeptime)
            t0 = acsc.readReal(self.hc, acsc.NONE, "start_time")
            newdata = acsc.readReal(
                self.hc, acsc.NONE, "aft_data", 0, 7, 0, self.dblen // 2 - 1
            )
            t = (newdata[0] - t0) / 1000.0
            self.data["time"] = np.append(self.data["time"], t)
            self.data["load_cell_ch1"] = np.append(
                self.data["load_cell_ch1"], newdata[1]
            )
            self.data["load_cell_ch2"] = np.append(
                self.data["load_cell_ch2"], newdata[2]
            )
            self.data["load_cell_ch3"] = np.append(
                self.data["load_cell_ch3"], newdata[3]
            )
            self.data["load_cell_ch4"] = np.append(
                self.data["load_cell_ch4"], newdata[4]
            )
            self.data["turbine_pos"] = np.append(
                self.data["turbine_pos"], newdata[5]
            )
            self.data["turbine_rpm"] = np.append(
                self.data["turbine_rpm"], newdata[6]
            )
            self.data["carriage_vel"] = np.append(
                self.data["carriage_vel"], newdata[7]
            )
            time.sleep(self.sleeptime)
            newdata = acsc.readReal(
                self.hc,
                acsc.NONE,
                "aft_data",
                0,
                7,
                self.dblen // 2,
                self.dblen - 1,
            )
            t = (newdata[0] - t0) / 1000.0
            self.data["time"] = np.append(self.data["time"], t)
            self.data["time"] = self.data["time"] - self.data["time"][0]
            self.data["load_cell_ch1"] = np.append(
                self.data["load_cell_ch1"], newdata[1]
            )
            self.data["load_cell_ch2"] = np.append(
                self.data["load_cell_ch2"], newdata[2]
            )
            self.data["load_cell_ch3"] = np.append(
                self.data["load_cell_ch3"], newdata[3]
            )
            self.data["load_cell_ch4"] = np.append(
                self.data["load_cell_ch4"], newdata[4]
            )
            self.data["turbine_pos"] = np.append(
                self.data["turbine_pos"], newdata[5]
            )
            self.data["turbine_rpm"] = np.append(
                self.data["turbine_rpm"], newdata[6]
            )
            self.data["carriage_vel"] = np.append(
                self.data["carriage_vel"], newdata[7]
            )

    def makedaqprg(self):
        """Create an ACSPL+ program to load into the controller"""
        self.prg = make_aft_prg(
            sample_period_ms=int(1 / self.sr * 1000), n_buffer_rows=self.dblen
        )

    def stop(self):
        self.collectdata = False
        try:
            acsc.writeInteger(self.hc, "collect_data", 0)
        except:
            print("Could not write collect_data = 0")


class FbgDaqThread(QtCore.QThread):
    def __init__(self, fbg_props, usetrigger=False):
        QtCore.QThread.__init__(self)
        self.interr = micronopt.Interrogator(fbg_props=fbg_props)
        self.interr.connect()
        self.interr.flush_buffer()
        if usetrigger:
            self.interr.trig_start_edge = "falling"
            self.interr.trig_stop_type = "edge"
            self.interr.trig_stop_edge = "rising"
            self.interr.trig_num_acq = 1
            self.interr.auto_retrig = False
            self.interr.trig_mode = "hardware"
        else:
            self.interr.trig_mode = "untriggered"
        self.interr.create_sensors()
        self.interr.data_interleave = 2
        self.interr.num_averages = 2
        self.interr.zero_strain_sensors()
        self.interr.setup_append_data()
        self.collectdata = True
        self.metadata = {}
        self.metadata["Sensors"] = fbg_props.copy()
        self.metadata["Data interleave"] = self.interr.data_interleave
        self.metadata["Num averages"] = self.interr.num_averages
        self.data = self.interr.data

    def run(self):
        while self.collectdata:
            self.interr.get_data()
            self.interr.sleep()

    def stop(self):
        self.collectdata = False
        self.interr.disconnect()


class ODiSIDaqThread(QtCore.QThread):
    collecting = QtCore.pyqtSignal()
    cleared = QtCore.pyqtSignal()

    def __init__(self, odisi_props):
        QtCore.QThread.__init__(self)

        ## AT SOME POINT I SHOULD FIGURE OUT HOW TO MAKE IT WORK THROUGH ITS OWN THREAD AND ALSO ACQUIRE DATA FROM INTERROGATOR

        # self.starttask = nidaqmx.Task()
        # self.starttask.do_channels.add_do_chan("/cDAQ9188-16D66BBMod1/port0/line0")
        # self.starttask.start()
        # for n in range(1):
        #     self.starttask.write(True)
        #     time.sleep(1) # make longer to see pulse width on oscilloscope
        #     self.starttask.write(False)
        #     time.sleep(1) # make longer to see pulse width on oscilloscope
        # self.starttask.stop
        # self.starttask.close()
        # print("ODiSI interrogator starting measurements...")

    # def stop(self):
    # nidaqmx.StopTask(self.starttask)
    # nidaqmx.StopTask(self.stoptask)
    # print("ODiSI disengaged.")
    # self.stoptask = nidaqmx.Task()
    # self.stoptask.do_channels.add_do_chan("/cDAQ9188-16D66BBMod1/port0/line1")
    # self.stoptask.start()
    # for n in range(1):
    #     self.stoptask.write(True)
    #     time.sleep(1) # make longer to see pulse width on oscilloscope
    #     self.stoptask.write(False)
    #     time.sleep(1) # make longer to see pulse width on oscilloscope (1e-6)
    # self.stoptask.stop
    # self.stoptask.close()
    # print("ODiSI interrogator stopping measurements...")


class AftNiDaqThread(QtCore.QThread):
    collecting = QtCore.pyqtSignal()
    cleared = QtCore.pyqtSignal()

    def __init__(self, usetrigger=True):
        QtCore.QThread.__init__(self)
        # Some parameters for the thread
        self.usetrigger = usetrigger
        self.collect = True
        # Create some meta data for the run
        self.metadata = {}
        # Initialize sample rate
        self.sr = 100
        self.metadata["Sample rate (Hz)"] = self.sr
        self.nsamps = int(self.sr / 10)
        # Create a dict of arrays for storing data
        self.data = {
            "resistor_temp": np.array([]),
            "yaskawa_temp": np.array([]),
            "fore_temp": np.array([]),
            "aft_temp": np.array([]),
            "time": np.array([]),
            "carriage_pos": np.array([]),
        }
        # Create tasks
        self.analogtask = nidaqmx.Task("analog-inputs")
        self.carpostask = nidaqmx.Task("carriage-pos")
        # Add channels to tasks
        self.analogchans = [
            "resistor_temp",
            "yaskawa_temp",
            "fore_temp",
            "aft_temp",
        ]
        self.carposchan = "carriage_pos"
        self.analogtask.add_global_channels(
            [GlobalVirtualChannel(c) for c in self.analogchans]
        )
        self.carpostask.add_global_channels(
            [GlobalVirtualChannel(self.carposchan)]
        )
        # Get channel information to add to metadata
        self.chaninfo = {}
        for channame in self.analogchans:
            self.chaninfo[channame] = {}
            scale = channame + "_scale"
            self.chaninfo[channame]["Scale name"] = scale
            self.chaninfo[channame]["Scale slope"] = daqmx.GetScaleLinSlope(
                scale
            )
            self.chaninfo[channame][
                "Scale y-intercept"
            ] = daqmx.GetScaleLinYIntercept(scale)
            self.chaninfo[channame][
                "Scaled units"
            ] = daqmx.GetScaleScaledUnits(scale)
            self.chaninfo[channame][
                "Prescaled units"
            ] = daqmx.GetScalePreScaledUnits(scale)
        self.chaninfo[self.carposchan] = {}
        self.chaninfo[self.carposchan][
            "Distance per pulse"
        ] = daqmx.GetCILinEncoderDisPerPulse(
            self.carpostask._handle, self.carposchan
        )
        self.chaninfo[self.carposchan]["Units"] = daqmx.GetCILinEncoderUnits(
            self.carpostask._handle, self.carposchan
        )
        self.metadata["Channel info"] = self.chaninfo
        # Configure sample clock timing
        daqmx.CfgSampClkTiming(
            self.analogtask._handle,
            "",
            self.sr,
            daqmx.Val_Rising,
            daqmx.Val_ContSamps,
            self.nsamps,
        )
        # Get source for analog sample clock
        trigname = daqmx.GetTerminalNameWithDevPrefix(
            self.analogtask._handle, "ai/SampleClock"
        )
        daqmx.CfgSampClkTiming(
            self.carpostask._handle,
            trigname,
            self.sr,
            daqmx.Val_Rising,
            daqmx.Val_ContSamps,
            self.nsamps,
        )
        # If using trigger for analog signals set source to chassis PFI0
        if self.usetrigger:
            daqmx.CfgDigEdgeStartTrig(
                self.analogtask._handle,
                "/cDAQ9188-16D66BB/PFI0",
                daqmx.Val_Falling,
            )
        # Set trigger functions for counter channels
        daqmx.SetStartTrigType(self.carpostask._handle, daqmx.Val_DigEdge)
        trigsrc = daqmx.GetTrigSrcWithDevPrefix(
            self.analogtask._handle, "ai/StartTrigger"
        )
        daqmx.SetDigEdgeStartTrigSrc(self.carpostask._handle, trigsrc)
        daqmx.SetDigEdgeStartTrigEdge(
            self.carpostask._handle, daqmx.Val_Rising
        )

    def run(self):
        """Start DAQmx tasks."""
        stream = self.analogtask.in_stream
        reader = AnalogMultiChannelReader(stream)
        stream_cp = self.carpostask.in_stream
        reader_cp = CounterReader(stream_cp)
        data = np.zeros((len(self.analogchans), self.nsamps))
        carpos = np.zeros(self.nsamps)

        def every_n_samples(
            task_handle, every_n_samps_event_type, n_samps, callback_data
        ):
            """Function called every N samples"""
            reader.read_many_sample(
                data, number_of_samples_per_channel=n_samps
            )
            self.data["resistor_temp"] = np.append(
                self.data["resistor_temp"], data[0, :], axis=0
            )
            self.data["yaskawa_temp"] = np.append(
                self.data["yaskawa_temp"], data[1, :], axis=0
            )
            self.data["fore_temp"] = np.append(
                self.data["fore_temp"], data[2, :], axis=0
            )
            self.data["aft_temp"] = np.append(
                self.data["aft_temp"], data[3, :], axis=0
            )
            self.data["time"] = (
                np.arange(len(self.data["resistor_temp"]), dtype=float)
                / self.sr
            )
            reader_cp.read_many_sample_double(
                carpos, number_of_samples_per_channel=n_samps
            )
            self.data["carriage_pos"] = np.append(
                self.data["carriage_pos"], carpos
            )
            return 0  # The function should return an integer

        self.analogtask.register_every_n_samples_acquired_into_buffer_event(
            sample_interval=self.nsamps, callback_method=every_n_samples
        )
        # Start the tasks
        self.carpostask.start()
        self.analogtask.start()
        self.collecting.emit()
        # Keep the acquisition going until task is cleared
        while self.collect:
            time.sleep(0.2)

    def stopdaq(self):
        self.analogtask.stop()
        self.carpostask.stop()

    def clear(self):
        self.stopdaq()
        self.analogtask.close()
        self.carpostask.close()
        self.collect = False
        self.cleared.emit()


if __name__ == "__main__":
    pass
