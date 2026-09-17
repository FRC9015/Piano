import serial
import time

# Open serial connection to Pico
ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
print("Listening to Pico port /dev/ttyACM0...")

while True:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        print(f"Received: {line}")
    time.sleep(0.01)
