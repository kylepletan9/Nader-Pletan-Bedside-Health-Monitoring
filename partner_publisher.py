# partner_publish.py
import time
from mqtt_utils import send_data_line

BROKER = "2ea696aad32b4a47a1131f227d475e4f.s1.eu.hivemq.cloud"
PORT   = 8883
USER   = "project_tester"
PASS   = "ProjectTester1"
TOPIC  = "project/status"

# send plain string
send_data_line("NORMAL,bpm=73.3,temp=34.0,tilt=0", TOPIC, BROKER, PORT, USER, PASS)  # works with your parser


