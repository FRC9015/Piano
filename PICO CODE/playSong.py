import time
import json
import board
import busio
from adafruit_servokit import ServoKit

# --- Configuration ---
WHITE_PRESS_ANGLE = 90    
BLACK_PRESS_ANGLE = 140    

WHITE_RELEASE_ANGLE = 0  
BLACK_RELEASE_ANGLE = 60  

i2c = busio.I2C(board.GP1, board.GP0)

kit1 = ServoKit(channels=16, i2c=i2c, address=0x40)
kit2 = ServoKit(channels=16, i2c=i2c, address=0x41)
kit3 = ServoKit(channels=16, i2c=i2c, address=0x42)
kit4 = ServoKit(channels=16, i2c=i2c, address=0x44)
kit5 = ServoKit(channels=16, i2c=i2c, address=0x50)

kits = {
    "0x40": kit1,
    "0x41": kit2,
    "0x42": kit3,
    "0x44": kit4,
    "0x50": kit5
}

# Calibrate all
for k in kits.values():
    for i in range(16):
        k.servo[i].set_pulse_width_range(500, 2400)

def get_target_angle(addr, physical_channel, base_angle):
    # Black key boards (0x41, 0x44) do not reverse direction.
    if addr in ("0x41", "0x44"):
        return base_angle
    
    # White key boards (0x40, 0x42, 0x50) alternate direction on odd physical channels.
    if physical_channel % 2 != 0:
        return 180 - base_angle
    return base_angle

def play_song(filename):
    print(f"Playing file: {filename}")
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                event = json.loads(line)
                
                if event['d'] > 0:
                    time.sleep(event['d'] / 1000.0)
                
                kit_addr = event.get('addr', "0x40")
                kit = kits.get(kit_addr)
                if kit:
                    physical_channel = event['s']
                    is_black_key = kit_addr in ("0x41", "0x44")
                    
                    release_angle = BLACK_RELEASE_ANGLE if is_black_key else WHITE_RELEASE_ANGLE
                    press_angle = BLACK_PRESS_ANGLE if is_black_key else WHITE_PRESS_ANGLE
                    
                    action_angle = press_angle if event['a'] == "down" else release_angle
                    target = get_target_angle(kit_addr, physical_channel, action_angle)
                    kit.servo[physical_channel].angle = target
    except Exception as e:
        print("Error during playback:", e)

def reset_all():
    print("Resetting all servos...")
    for addr, kit in kits.items():
        is_black_key = addr in ("0x41", "0x44")
        release_angle = BLACK_RELEASE_ANGLE if is_black_key else WHITE_RELEASE_ANGLE
        
        for i in range(16):
            target = get_target_angle(addr, i, release_angle)
            kit.servo[i].angle = target
    time.sleep(1)

try:
    reset_all()
    play_song('test.jsonl')
    print("Song finished.")
except KeyboardInterrupt:
    print("Stopped.")
    reset_all()