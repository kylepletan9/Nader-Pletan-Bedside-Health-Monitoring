# alert_bridge.py
import os, time, json, smtplib, certifi, requests
from email.message import EmailMessage
import paho.mqtt.client as mqtt

# config
BROKER   = ""
PORT     = 8883
USER     = "project_tester"
PASS     = "ProjectTester1"
TOPIC    = "project/status"

PICO_URL = ""  # <- include :8080

TO_EMAIL   = ""
FROM_EMAIL = os.getenv("ALERT_FROM",  "")
APP_PASS   = os.getenv("ALERT_APP_PASS", "")

ALERT_LEVELS = {"warning","critical"}
DUPLICATE_SUPPRESS_SEC = 60

def send_email(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)  # UTF-8 text

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as s:
        s.starttls()
        s.login(FROM_EMAIL, APP_PASS)
        s.send_message(msg)

def _to_num(x):
    try:
        if x is None: return None
        if isinstance(x, (int,float)): return x
        sx = str(x)
        return float(sx) if "." in sx else int(sx)
    except:
        return None

def normalize_tilt(v):
    if v is None: return None
    s = str(v).strip().lower()
    truthy = {"1","true","on","tilt","tilted","inclined","high"}
    falsy  = {"0","false","off","flat","level","declined","upright","low"}
    if s in truthy: return "inclined"
    if s in falsy:  return "declined"
    return s

def parse_payload(payload: bytes):
    """
    Accepts:
      b'warning,bpm=78,temp=98.6,tilt=inclined'
      b'warning'
      b'"warning"'
      b'{"status":"warning","bpm":78,"temp":98.6,"tilt":"declined"}'
    Returns: (status, bpm, temp, tilt)
    """
    allowed = {"normal","warning","critical"}
    try:
        s = payload.decode().strip()
    except:
        return (None,None,None,None)

    if "," in s and "=" in s:
        parts = [p.strip() for p in s.split(",")]
        status = parts[0].lower()
        if status not in allowed: status = None
        vals = {}
        for p in parts[1:]:
            if "=" in p:
                k,v = p.split("=",1)
                vals[k.strip().lower()] = v.strip()
        bpm  = _to_num(vals.get("bpm"))
        temp = _to_num(vals.get("temp"))
        tilt = normalize_tilt(vals.get("tilt"))
        return (status, bpm, temp, tilt)

    if s in allowed:
        return (s,None,None,None)

    try:
        obj = json.loads(s)
        if isinstance(obj, str) and obj in allowed:
            return (obj,None,None,None)
        if isinstance(obj, dict):
            status = str(obj.get("status","")).lower()
            if status not in allowed: status = None
            bpm  = _to_num(obj.get("bpm"))
            temp = _to_num(obj.get("temp"))
            tilt = normalize_tilt(obj.get("tilt"))
            return (status, bpm, temp, tilt)
    except:
        pass
    return (None,None,None,None)

def set_pico(level:str, bpm=None, temp=None, tilt=None, attempts=3, timeout=5.0):
    params={"level": level}
    if bpm is not None:  params["bpm"]  = bpm
    if temp is not None: params["temp"] = temp
    if tilt is not None: params["tilt"] = tilt  # string
    url = f"{PICO_URL}/update"
    for i in range(attempts):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            print(f"[PICO] {params} -> {r.status_code} {r.text[:40]!r}")
            return
        except Exception as e:
            print(f"[PICO] attempt {i+1} failed: {e}")
            time.sleep(0.5 * (i+1))

_last_alert = {"level": None, "t": 0.0}
def maybe_email(level, bpm, temp, tilt):
    global _last_alert
    now = time.time()
    if level not in ALERT_LEVELS:
        _last_alert = {"level": level, "t": now}
        return
    if _last_alert["level"] == level and (now - _last_alert["t"]) < DUPLICATE_SUPPRESS_SEC:
        return
    _last_alert = {"level": level, "t": now}

    subject = f"PATIENT STATUS: {level.upper()}"
    body = (
        f"Status: {level}\n"
        f"BPM: {bpm if bpm is not None else '-'}\n"
        f"Temp: {temp if temp is not None else '-'}\n"
        f"Tilt: {tilt if tilt is not None else '-'}\n"
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        send_email(subject, body)
        print("[EMAIL] sent to", TO_EMAIL)
    except Exception as e:
        print("[EMAIL] failed:", e)

def on_connect(c, u, flags, rc, properties=None):
    print(f"[MQTT] connected rc={rc}")
    if rc == 0:
        c.subscribe(TOPIC, qos=1)

def on_message(c, u, msg):
    status, bpm, temp, tilt = parse_payload(msg.payload)
    if not status:
        print("[MQTT] ignored:", msg.payload[:80])
        return
    print(f"[MQTT] {status}  bpm={bpm} temp={temp} tilt={tilt}")
    set_pico(status, bpm, temp, tilt)
    maybe_email(status, bpm, temp, tilt)

# client setup
if hasattr(mqtt, "CallbackAPIVersion"):
    client = mqtt.Client(
        client_id="alert-bridge-001",
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
else:
    client = mqtt.Client(client_id="alert-bridge-001", protocol=mqtt.MQTTv311)

client.tls_set(ca_certs=certifi.where())
client.username_pw_set(USER, PASS)
client.on_connect = on_connect
client.on_message = on_message
client.reconnect_delay_set(1, 30)
client.connect(BROKER, PORT, keepalive=60)
client.loop_forever()
