import time
import board
import pwmio
from adafruit_motor import servo
import sys
import supervisor

# Set up PWM pin connected to the servo signal wire (change GP0 to your pin)
pwm = pwmio.PWMOut(board.GP2, duty_cycle=2**15, frequency=50)

# Create a servo object
my_servo = servo.Servo(pwm)

setangle = 0
while True:
    # Check if data is waiting in the serial console buffer
    if supervisor.runtime.serial_bytes_available:
        key = sys.stdin.read(1)
        
        # Only process if it is NOT a carriage return or newline
        if key not in ("\r", "\n"):
            if key == "a":
                setangle = 0
            elif key == "s":
                setangle = 90
            elif key == "d":
                setangle = 180
            elif key == "f":
                setangle = 60
            elif key == "g":
                setangle = 140
    # Move to 0 degrees
    my_servo.angle = setangle
    time.sleep(0.01)