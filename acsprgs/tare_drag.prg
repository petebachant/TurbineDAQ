! This is a tare drag program auto-generated by TurbineDAQ
global real data(3)(100)
global real start_time, tzero
global int collect_data
collect_data = 0
tzero = 2.5

VEL(5) = {tow_speed}
ACC(5) = 1
DEC(5) = 0.5

! Start controller data acquisition and send trigger pulse in same cycle
BLOCK
    start_time = TIME
    collect_data = 1
    DC/c data, 100, 1.0, TIME, RVEL(5), FVEL(4)
    ! Send trigger pulse for data acquisition
    OUT1.16 = 1
END

WAIT tzero*1000

PTP/e 5, 24.5
VEL(5) = 0.6
ACC(5) = 0.5
PTP/e 5, 0
STOPDC
collect_data = 0
OUT1.16 = 1
STOP
