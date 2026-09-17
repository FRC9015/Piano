import time
import json
import board
import busio
from adafruit_servokit import ServoKit

# --- Configuration ---
WHITE_PRESS_ANGLE = 90    # Down position for white keys
WHITE_RELEASE_ANGLE = 0  # Up position for white keys (avoids absolute 0/180)

i2c = busio.I2C(board.GP1, board.GP0)

# Initialize ONLY Board 0x40 (the new unsoldered board)
kit = ServoKit(channels=16, i2c=i2c, address=0x40)

# Calibrate all 16 channels on Board 0x40
for i in range(16):
    kit.servo[i].set_pulse_width_range(500, 2400)

def get_target_angle(physical_channel, base_angle):
    # Board 0x40 contains white keys (reverses on odd channels)
    if physical_channel % 2 != 0:
        return 180 - base_angle
    return base_angle

def play_song(filename):
    print(f"Loading {filename} into memory...")
    events = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except Exception as e:
        print("Error loading file:", e)
        return

    print(f"Playing song from memory ({len(events)} events)...")
    try:
        for event in events:
            if event['d'] > 0:
                time.sleep(event['d'] / 1000.0)
            
            kit_addr = event.get('addr', "0x40")
            
            # Process the event if it targets our only active board (0x40)
            if kit_addr == "0x40":
                physical_channel = event['s']
                
                # Assume white key angles
                action_angle = WHITE_PRESS_ANGLE if event['a'] == "down" else WHITE_RELEASE_ANGLE
                target = get_target_angle(physical_channel, action_angle)
                
                # Print output to watch transitions in real-time
                print(f"[PLAY] Board 0x40 Pin {physical_channel} commanded to {target} (Action: {event['a']})")
                kit.servo[physical_channel].angle = target
                
    except Exception as e:
        print("Error during playback:", e)

def reset_all():
    print("Resetting all servos on Board 0x40...")
    for i in range(16):
        target = get_target_angle(i, WHITE_RELEASE_ANGLE)
        kit.servo[i].angle = target
        time.sleep(0.5)
    time.sleep(1)

try:
    reset_all()
    # Execute the single-board test file
    play_song('test.jsonl')
    print("Song finished.")
except KeyboardInterrupt:
    print("Stopped.")
    reset_all()