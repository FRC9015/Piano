import time
import board
import busio
from adafruit_servokit import ServoKit

# --- Configuration ---
I2C_ADDR = 0x41     # Set to 0x40, 0x41, or 0x42 depending on your board
TEST_PORT_1 = 5    # First physical port number (0 to 15) to test
TEST_PORT_2 = 6    # Second physical port number (0 to 15) to test
MIN_ANGLE = 0        # Starting angle (corresponds to "up")
MAX_ANGLE = 90       # Ending angle (corresponds to "down")

# Set up the shared I2C bus on GP0 (SDA) and GP1 (SCL)
# busio.I2C expects (scl, sda)
i2c = busio.I2C(board.GP1, board.GP0)

# Initialize the 16-channel servo kit
try:
    kit = ServoKit(channels=16, i2c=i2c, address=I2C_ADDR)
    print("I2C connection successful!")
except Exception as e:
    print("Error connecting to the I2C board. Check your wiring and address.", e)
    # Loop here to prevent the code from crashing completely
    while True:
        time.sleep(1)

# Calibrate both target servos' pulse ranges (standard for MG90S)
kit.servo[TEST_PORT_1].set_pulse_width_range(500, 2400)
kit.servo[TEST_PORT_2].set_pulse_width_range(500, 2400)

def get_target_angle(physical_channel, base_angle):
    """
    Inverts the physical direction of travel if the physical channel is odd.
    """
    if physical_channel % 2 != 0:  # Odd physical port (1, 3, 5, etc.)
        actuation_range = kit.servo[physical_channel].actuation_range  # Defaults to 180
        return actuation_range - base_angle
    return base_angle

print(f"Starting simultaneous test on Servo Ports {TEST_PORT_1} and {TEST_PORT_2}...")
print("Press Ctrl+C in Thonny to stop.")

while True:
    try:
        # 1. Move UP (MIN_ANGLE)
        target1_min = get_target_angle(TEST_PORT_1, MIN_ANGLE)
        target2_min = get_target_angle(TEST_PORT_2, MIN_ANGLE)
        
        print("Moving up...")
        kit.servo[TEST_PORT_1].angle = target1_min
        kit.servo[TEST_PORT_2].angle = target2_min
        time.sleep(1.5)  # Wait for them to finish moving
        
        # 2. Move DOWN (MAX_ANGLE)
        target1_max = get_target_angle(TEST_PORT_1, MAX_ANGLE)
        target2_max = get_target_angle(TEST_PORT_2, MAX_ANGLE)
        
        print("Moving down...")
        kit.servo[TEST_PORT_1].angle = target1_max
        kit.servo[TEST_PORT_2].angle = target2_max
        time.sleep(1.5)  # Wait for them to finish moving
        
    except KeyboardInterrupt:
        print("Test stopped by user.")
        break
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        break