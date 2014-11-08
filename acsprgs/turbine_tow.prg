local real target, tsr, U, rpm, tacc, endpos, tzero, R
global real data(3)(100)
global real start_time
global int collect_data

collect_data = 0

tsr = {tsr}
U = {tow_speed}
R = {turbine_radius}

rpm = tsr*U/R*60/6.28318530718

target = 24.5   ! Do not exceed 24.9 for traverse at x/D = 1
endpos = 0      ! Where to move carriage at end of tow
tacc = 5        ! Time (in seconds) for turbine angular acceleration
tzero = 2.5     ! Time (in seconds) to wait before starting

VEL(5) = 0.5
ptp/e 5, 0

ACC(5) = 1
DEC(5) = 0.5
VEL(5) = U
JERK(5)= ACC(5)*10

! Set modulo on turbine axis (only needed if using simulator)
! DISABLE 4
! SLPMAX(4) = 60
! SLPMIN(4) = 0
! MFLAGS(4).#MODULO = 1

ACC(4) = rpm/tacc
VEL(4) = rpm
DEC(4) = ACC(4)
JERK(4)= ACC(4)*10

! Move turbine to zero if necessary
if RPOS(4) <> 60 & RPOS(4) <> 0
    ptp 4, 0
end

! Allow oscillations in shaft to damp out
wait 3000

! Start controller data acquisition and send trigger pulse in same cycle
BLOCK
    ! Define start time from now
    start_time = TIME
    collect_data = 1
    DC/c data, 100, 1.0, TIME, FVEL(5), FVEL(4)
    ! Send trigger pulse for data acquisition
    OUT1.16 = 0
END

wait tzero*1000
jog/v 4, rpm
wait tacc*1000
ptp/e 5, target
HALT(4)
VEL(5) = 0.5
VEL(4) = 10
ptp 4, 0
ptp/e 5, 0
STOPDC
collect_data = 0
OUT1.16 = 1

STOP