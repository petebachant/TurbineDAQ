"""
This bitch be a test of generating a text file for running as an ACS program
then uploading it to the controller and running it.
"""
import acsc
import time

file = open("test/test.prg", "w+")

acs_prg = """
ENABLE 1""" + \
"""
VEL(1) = 1000
PTP/r 1, -900
STOP
"""

file.write(acs_prg)
file.close()

print acs_prg
hc = acsc.OpenCommDirect()
acsc.LoadBuffer(hc, 0, acs_prg, 512)
acsc.Enable(hc, 0)
#acsc.LoadBuffersFromFile(hc, "test/test.prg")
acsc.RunBuffer(hc, 0)
time.sleep(1)
print acsc.GetRPosition(hc, 1)
print acsc.acsc.GetMotorState(hc, 1)
acsc.CloseComm(hc)