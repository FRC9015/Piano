import time
import board
import busio
from adafruit_servokit import ServoKit

# ==============================================================================
# CONFIGURATION
# ==============================================================================
WHITE_PRESS_ANGLE = 90    # Down position for white keys
BLACK_PRESS_ANGLE = 80    # Down position for black keys

WHITE_RELEASE_ANGLE = 15  # Up position for white keys (avoids absolute 0/180)
BLACK_RELEASE_ANGLE = 15  # Up position for black keys

# Time (in seconds) to wait between actions
HOLD_TIME = 0.3   # How long the key stays pressed down
PAUSE_TIME = 0.2  # Delay before moving to the next key

# ==============================================================================
# INITIALIZATION
# ==============================================================================
print("Initializing I2C bus...")
i2c = busio.I2C(board.GP1, board.GP0)

print("Initializing ServoKit boards...")
# We use a dictionary matching your board hex addresses
kits = {
    "0x40": ServoKit(channels=16, i2c=i2c, address=0x40)
}

# Calibrate pulse width range for all 5 boards to match MG90S limits
print("Calibrating servo pulse ranges...")
for addr, kit in kits.items():
    for i in range(16):
        kit.servo[i].set_pulse_width_range(500, 2400)

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def get_target_angle(addr, physical_channel, base_angle):
    # Black key boards (0x41, 0x44) do not reverse direction.
    if addr in ("0x41", "0x44"):
        return base_angle
    
    # White key boards (0x40, 0x42, 0x50) alternate direction on odd physical channels.
    if physical_channel % 2 != 0:
        return 180 - base_angle
    return base_angle

def disable_all():
    print("Releasing all servos (making them limp)...")
    for kit in kits.values():
        for i in range(16):
            kit.servo[i].fraction = None

# ==============================================================================
# MAIN TEST LOOP
# ==============================================================================
try:
    print("\nStarting Keyboard Diagnostics...")
    disable_all()
    time.sleep(1)

    # We test the boards in order: white keys first, then black keys
    board_order = ["0x40"]

    for addr in board_order:
        kit = kits[addr]
        print(f"\n--- Testing Board {addr} ---")
        
        is_black_key = addr in ("0x41", "0x44")
        press_angle = BLACK_PRESS_ANGLE if is_black_key else WHITE_PRESS_ANGLE
        release_angle = BLACK_RELEASE_ANGLE if is_black_key else WHITE_RELEASE_ANGLE

        for channel in range(16):
            print(f"Board {addr} | Pin {channel:02d} -> Playing")
            
            # 1. Calculate angles based on the board and channel
            down_angle = get_target_angle(addr, channel, press_angle)
            up_angle = get_target_angle(addr, channel, release_angle)
            
            # 2. Press Down
            kit.servo[channel].angle = down_angle
            time.sleep(HOLD_TIME)
            
            # 3. Return Up
            kit.servo[channel].angle = up_angle
            time.sleep(PAUSE_TIME)
            
            # 4. Turn off signal to this specific servo to prevent holding strain/heat
            kit.servo[channel].fraction = None

    print("\nTest completed successfully!")
    disable_all()

except KeyboardInterrupt:
    print("\nTest stopped by user.")
    disable_all()