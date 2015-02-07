# -*- coding: utf-8 -*-
"""
Created on Thu Jan 08 23:39:51 2015

@author: Pete
"""
from __future__ import division, print_function
from turbinedaq import *
import sys

def test_read_turbine_properties():
    print("Testing read_turbine_properties")
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    w.wdir = os.path.join(os.getcwd(), "test")
    w.read_turbine_properties()
    print(w.turbine_properties)
    sys.exit(app.exec_())
    
def test_save_raw_data():
    """Test whether data is being saved correctly."""
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    savedir = os.path.join(w.wdir, "data_save_test")
    data = {"arange(5)" : np.arange(5), "zeros(5)" : np.zeros(5)}
    w.save_raw_data(savedir, "testdata.h5", data)
    try:
        data = ts.loadhdf(os.path.join(savedir, "testdata.h5"))
        shutil.rmtree(savedir)
        print("test_save_raw_data passed")
    except IOError:
        print("test_save_raw_data failed")
    sys.exit(app.exec_())
    
def test_import_test_plan():
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    print("Test plan has {} sections".format(len(w.test_plan)))
    for k,v in w.test_plan.items():
        print(k + ":")
        print(v)
    sys.exit(app.exec_())
    
def test_is_section_done():
    print("Testing 'is_section_done'")
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    assert w.is_section_done("test")
    print("PASS")
    sys.exit(app.exec_())
    
def test_autoprocess():
    print("Testing autoprocessing functionality")
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    w.wdir = os.path.join(os.getcwd(), "test")
    print(w.wdir)
    w.turbinetow = pd.DataFrame()
    w.turbinetow.metadata = {"test" : [1]}
    w.turbinetow.vectrino = False
    w.turbinetow.fbg = False
    w.turbinetow.aborted = False
    w.turbinetow.autoaborted = False
    w.savesubdir = "test/Data/Raw/test/0"
    w.nidata = {"test" : np.zeros(10)}
    w.acsdata = {"test" : np.zeros(10)}
    w.currentrun = 0
    if os.path.isfile("test/Data/Raw/test/0/acsdata.h5"):
        os.remove("test/Data/Raw/test/0/acsdata.h5")
    if os.path.isfile("test/Data/Raw/test/0/nidata.h5"):
        os.remove("test/Data/Raw/test/0/nidata.h5")
    w.on_tow_finished()
    if os.path.isfile("test/Data/Raw/test/0/acsdata.h5"):
        os.remove("test/Data/Raw/test/0/acsdata.h5")
    if os.path.isfile("test/Data/Raw/test/0/nidata.h5"):
        os.remove("test/Data/Raw/test/0/nidata.h5")
    print("PASS")
    sys.exit(app.exec_())
    
def test_read_vec_salinity():
    """
    Tests if the salinity for the Vectrino can be read and set from
    `Config/vectrino_properties.json`.
    """
    print("Testing the ability to read vectrino salinity")
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
    w.wdir = os.path.join(os.getcwd(), "test")
    assert(w.vec_salinity==6.6)
    print("PASS")
    sys.exit(app.exec_())
    
def test_strut_torque_run():
    """Tests the `StrutTorqueRun` object."""
    print("Testing runtypes.StrutTorqueRun")
    ref_speed = 1.0
    tsr = 2.0
    radius = 0.5
    rpm = tsr/radius*ref_speed*60.0/(2*np.pi)
    run = runtypes.StrutTorqueRun(1, ref_speed, tsr, radius, 10)
    print(run.rpm, "==", rpm)
    assert(run.rpm == rpm)
    print("PASS")
    
if __name__ == "__main__":
#    test_autoprocess()
#    test_read_vec_salinity()
#    test_strut_torque_run()
    test_read_turbine_properties()
