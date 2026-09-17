import serial
import time

print("Attempting to connect to Pico...")
try:
    # Change '/dev/ttyACM0' if your ls command showed a different port
    ser = serial.Serial('/dev/ttyACM1', 115200, timeout=1)
    print("SUCCESS: Connected to serial port!")
except Exception as e:
    print(f"FAILED to connect: {e}")
    exit()

print("Sending test packet in 2 seconds...")
time.sleep(2)

# Send a test string
test_packet = "0,0x42,0,1\n"
ser.write(test_packet.encode('utf-8'))
print(f"Sent: {test_packet.strip()}")
