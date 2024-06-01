"""Tests for the ``daqtasks`` module."""

import time

import numpy as np
import pytest
from acspy import acsc

from turbinedaq.daqtasks import AftAcsDaqThread


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
    assert np.all(np.diff(thread.data["time"] == 0.001))
