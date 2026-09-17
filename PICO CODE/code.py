import sys
import select
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
    "0x40": kit1, "0x41": kit2, "0x42": kit3, "0x44": kit4, "0x50": kit5
}

KEY_CALIBRATION = {
    # BOARD 0x42 (Bass - White keys)
    ("0x42", 0):  (10, 90),   # C2
    ("0x42", 1):  (15, 90),   # d2
    ("0x42", 2):  (10, 90),   # E2
    ("0x42", 3):  (20, 90),   # F2
    ("0x42", 4):  (40, 90),   # g2
    ("0x42", 5):  (20, 90),   # A2
    ("0x42", 6):  (43, 90),   # b2
    ("0x42", 7):  (3, 90),    # C3
    ("0x42", 8):  (20, 90),   # d3
    ("0x42", 9):  (20, 90),   # E3
    ("0x42", 10): (15, 90),   # F3
    ("0x42", 11): (17, 90),   # g3
    ("0x42", 12): (18, 90),   # A3
    ("0x42", 13): (20, 90),   # b3
    ("0x42", 14): (45, 90),   # C4
    ("0x42", 15): (25, 90),   # d4

    # BOARD 0x44 (Bass/Middle - Black keys)
    ("0x44", 0):  (65, 140),  # C2#
    ("0x44", 1):  (70, 140),  # D2#
    ("0x44", 2):  (65, 140),  # F2#
    ("0x44", 3):  (70, 140),  # g2#
    ("0x44", 4):  (65, 140),  # A2#
    ("0x44", 5):  (73, 140),  # C3#
    ("0x44", 6):  (65, 140),  # D3#
    ("0x44", 7):  (70, 140),  # F3#
    ("0x44", 8):  (125, 140),  # g3#
    ("0x44", 9):  (70, 140),  # A3#
    ("0x44", 10): (60, 140),  # C4#
    ("0x44", 11): (65, 140),  # D4#

    # BOARD 0x40 (Middle/High - White keys)
    ("0x40", 0):  (45, 90),   # E4
    ("0x40", 1):  (10, 90),   # F4
    ("0x40", 2):  (45, 90),   # g4
    ("0x40", 3):  (40, 110),  # A4
    ("0x40", 4):  (55, 90),   # b4
    ("0x40", 5):  (0, 90),    # C5
    ("0x40", 6):  (15, 90),   # d5
    ("0x40", 7):  (5, 90),    # E5


    # BOARD 0x41 (Middle/High - Black keys)
    ("0x41", 0):  (85, 140),  # F4#
    ("0x41", 1):  (65, 140),  # G4#
    ("0x41", 5):  (65, 140),  # A4#
    ("0x41", 6):  (90, 140),  # C5#
    ("0x41", 7):  (65, 140),  # D5#
    ("0x41", 8):  (105, 140), # F5#
    ("0x41", 9):  (70, 140),  # G5#
    ("0x41", 10): (70, 140),  # A5#
    ("0x41", 11): (70, 140),  # C6#
    ("0x41", 12): (65, 140),  # D6#
    ("0x41", 13): (80, 140),  # F6#
    ("0x41", 14): (65, 140),  # G6#
    ("0x41", 15): (100, 140),  # A6#

    # BOARD 0x50 (High - White keys)
    ("0x50", 0):  (25, 90),    # F5
    ("0x50", 1):  (0, 90),    # g5
    ("0x50", 2):  (50, 90),   # A5
    ("0x50", 3):  (5, 90),    # b5
    ("0x50", 4):  (15, 90),   # C6
    ("0x50", 5):  (8, 90),    # d6
    ("0x50", 6):  (20, 90),   # E6
    ("0x50", 7):  (0, 90),    # F6
    ("0x50", 8):  (18, 90),   # g6
    ("0x50", 9):  (3, 90),    # A6
    ("0x50", 10):  (25, 90),   # b6
    ("0x50", 11):  (8, 90)     # C7
}

for k in kits.values():
    for i in range(16):
        k.servo[i].set_pulse_width_range(500, 2400)

def which_release(is_black_key, board, servo_num):
   if is_black_key:
       for i,j in KEY_CAL_BLACK.items():
            if (i[0] == board) and (i[1] == servo_num):
                return j[1]
   else:
       for i,j in KEY_CALIBRATION.items():
           if (i[0] == board) and (i[1] == servo_num):
               return j[1]

def which_press(is_black_key, board, servo_num):
   if is_black_key:
       for i,j in KEY_CAL_BLACK.items():
            if (i[0] == board) and (i[1] == servo_num):
                return j[0]
   else:
       for i,j in KEY_CALIBRATION.items():
            if (i[0] == board) and (i[1] == servo_num):
                return j[0]

def get_target_angle(addr, physical_channel, base_angle):
    if addr in ("0x41", "0x44"):
        return base_angle
    if physical_channel % 2 != 0:
        return 180 - base_angle
    return base_angle

def reset_all():
    for addr, kit in kits.items():
        for i in range(16):
            try:
                release_angle, press_angle = KEY_CALIBRATION.get((addr, i))
                kit.servo[i].angle = get_target_angle(addr, i, release_angle)
            except Exception:
                pass
reset_all()
print("Pico ready for instant execution stream...")

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)

while True:
    events = poll.poll(50)
    if events:
        line = sys.stdin.readline()
        if line:
            line = line.strip()
            if not line:
                continue
            
            # Instant emergency / transition reset command
            if line == "RESET":
                reset_all()
                continue
                
            try:
                parts = line.split(',')
                if len(parts) == 4:
                    kit_addr = parts[1]
                    pin = int(parts[2])
                    is_down = int(parts[3]) == 1
                    
                    kit = kits.get(kit_addr)
                    if kit:
                        is_black_key = kit_addr in ("0x41", "0x44")
                        def_rel = BLACK_RELEASE_ANGLE if is_black_key else WHITE_RELEASE_ANGLE
                        def_press = BLACK_PRESS_ANGLE if is_black_key else WHITE_PRESS_ANGLE
                        release_angle, press_angle = KEY_CALIBRATION.get((kit_addr, pin))
                        
                        action_angle = press_angle if is_down else release_angle
                        kit.servo[pin].angle = get_target_angle(kit_addr, pin, action_angle)
            except Exception:
                pass