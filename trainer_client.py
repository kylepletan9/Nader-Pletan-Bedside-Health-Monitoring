# Activate m6 VM: run "m6\Scripts\activate" for PC
# Once Pico is plugged in, run this to collect labeled temperature data into a CSV

import serial
import platform

filename = "temp1.csv"

# Determine the operating system
os_type = platform.system()

# Set the serial port based on the OS
if os_type == "Windows":
    port = "COM8"  # Adjust this to the correct port on your PC
elif os_type == "Darwin":  # macOS
    port = "/dev/tty.usbmodem11101"  # Adjust this to the correct port on your Mac
else:
    raise Exception("Unsupported OS")

# Open serial connection to the Pico
s = serial.Serial(port, 115200)

while True:
    try:
        line = s.readline().decode(errors="ignore").strip()
        if not line:
            continue

        parts = line.split(",")
        if len(parts) == 2 and parts[0].replace(".", "", 1).isdigit():
            with open(filename, 'a') as f:
                f.write(f"{line}\n")
            print(line)
    except Exception as e:
        print(f"Error: {e}")
