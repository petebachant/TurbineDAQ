"""Tests for the ``acsprgs`` module."""

from modules.acsprgs import tare_drag_prg, tare_torque_prg, turbine_tow_prg


def test_turbine_tow():
    print(turbine_tow_prg(1.0, 1.9, 0.5, prgdir="../acsprgs"))


def test_tare_torque():
    print(tare_torque_prg(rpm=60, dur=10, prgdir="../acsprgs"))


def test_tare_drag():
    print(tare_drag_prg(tow_speed=1.0, prgdir="../acsprgs"))
