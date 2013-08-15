local real target, offset, tsr, U, rpm, tacc, endpos 
 
tsr = 1.5
U = 1.0

rpm = tsr*U/0.5*60/6.28318530718

offset = 0      ! Offset caused by ADV traverse (m)
target = 24.9   ! Do not exceed 24.9 for traverse at x/D = 1
endpos = 0      ! Where to move carriage at end of tow
tacc = 5        ! Time (in seconds) for turbine angular acceleration

ACC(tow) = 1
DEC(tow) = 0.5
VEL(tow) = U
JERK(tow)= ACC(tow)*10

ACC(turbine) = rpm/tacc
VEL(turbine) = rpm
DEC(turbine) = ACC(turbine)
JERK(turbine)= ACC(turbine)*10

jog/v turbine, rpm
wait (tacc)*1000
ptp/e tow, target-offset
HALT(turbine)
VEL(tow) = 0.5
VEL(turbine) = 10
ptp tow, endpos
ptp/e turbine, 60

STOP
