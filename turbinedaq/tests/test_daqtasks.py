"""Tests for the ``daqtasks`` module."""

import time

import numpy as np
import pytest
from acspy import acsc

from turbinedaq.daqtasks import AcsDaqThread, AftAcsDaqThread


@pytest.fixture
def acs_hcomm():
    hc = acsc.open_comm_simulator()
    yield hc
    acsc.closeComm(hc)


def test_aftacsdaqthread(acs_hcomm):
    thread = AftAcsDaqThread(acs_hc=acs_hcomm, makeprg=True)
    thread.start()
    time.sleep(2)
    thread.stop()
    assert np.all(np.round(np.diff(thread.data["time"]), decimals=6) == 0.001)


def test_acsdaqthread(acs_hcomm):
    thread = AcsDaqThread(acs_hc=acs_hcomm, makeprg=True)
    thread.start()
    time.sleep(2)
    thread.stop()
    assert np.all(np.round(np.diff(thread.data["time"]), decimals=6) == 0.001)
