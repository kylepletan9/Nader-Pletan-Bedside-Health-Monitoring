import serial
import pickle
import numpy as np
import time
import warnings
from mqtt_utils import send_data_line

# MQTT
BROKER = "2ea696aad32b4a47a1131f227d475e4f.s1.eu.hivemq.cloud"
PORTMQTT   = 8883
USER   = "project_tester"
PASS   = "ProjectTester1"
TOPIC  = "project/status"

# Warnings filter ignore, sklearn
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

# Load trained model
model = pickle.load(open("Random Forest_OPTIMAL_MODEL.sav", "rb"))

# Set Pico's serial port
PORT = "COM8"  # Change this if needed
BAUD = 115200

# Open serial connection
ser = serial.Serial(PORT, BAUD, timeout=1)
print(f"Connected to {PORT}, waiting for temperature values...")

while True:
    try:
        line = ser.readline().decode().strip()
        if not line:
            continue

        # Try to interpret the line as a temperature value
        if line.replace(".", "", 1).isdigit():
            temp = float(line)
            X = np.array([[temp]])
            pred = model.predict(X)[0]
            print(f"{temp:.2f},{pred}")
            ser.write((pred + "\n").encode())
        else:
            # Just print non-numeric lines (e.g., full status output from Pico)
            send_data_line(line, TOPIC, BROKER, PORTMQTT, USER, PASS)
            print(line)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)