# -*- coding: utf-8 -*-
"""
Created on Thu Jan 08 23:39:51 2015

@author: Pete
"""
from __future__ import division, print_function
from turbinedaq import *
import sys

def test_read_turbine_properties():
    app = QtGui.QApplication(sys.argv)
    w = MainWindow()
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
    
if __name__ == "__main__":
    test_is_section_done()
