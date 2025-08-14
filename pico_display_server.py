import network, socket, time, ure, ujson, ntptime
from machine import Pin, PWM

SSID = ""
PASS = ""

red   = Pin(10, Pin.OUT)
yellow= Pin(11, Pin.OUT)
green = Pin(12, Pin.OUT)
buzzer= PWM(Pin(15)); buzzer.duty_u16(0)

LEVEL="normal"; UPDATED_MS=time.ticks_ms()
BPM=None; TEMP=None; TILT=None

WARNING_PERIOD_MS=10_000
WARNING_PULSE_MS =200
_last_warning_ms =0

UNIX_EPOCH_OFFSET = 946_684_800
UPDATED_UNIX_MS = 0

def unix_ms():
    # Returns Unix epoch milliseconds
    return int((time.time() + UNIX_EPOCH_OFFSET) * 1000)

def set_display(level:str):
    global LEVEL, UPDATED_MS, UPDATED_UNIX_MS
    LEVEL=level
    UPDATED_MS = time.ticks_ms()
    UPDATED_UNIX_MS = unix_ms()
    red.value(level=="critical")
    yellow.value(level=="warning")
    green.value(level=="normal")

def normalize_tilt(v):
    if v is None: return None
    s = str(v).strip().lower()
    truthy = {"1","true","on","tilt","tilted","inclined","high"}
    falsy  = {"0","false","off","flat","level","declined","upright","low"}
    if s in truthy: return "inclined"
    if s in falsy:  return "declined"
    return s

def update_metrics(bpm=None,temp=None,tilt=None):
    global BPM,TEMP,TILT,UPDATED_MS,UPDATED_UNIX_MS
    if bpm  is not None: BPM  = bpm
    if temp is not None: TEMP = temp
    if tilt is not None: TILT = normalize_tilt(tilt)
    UPDATED_MS = time.ticks_ms()
    UPDATED_UNIX_MS = unix_ms()

def beep_on():  buzzer.freq(2000); buzzer.duty_u16(20000)
def beep_off(): buzzer.duty_u16(0)

def drive_buzzer():
    global _last_warning_ms
    now=time.ticks_ms()
    if LEVEL=="critical":
        beep_on(); return
    if LEVEL=="warning":
        if time.ticks_diff(now,_last_warning_ms)>=WARNING_PERIOD_MS:
            _last_warning_ms=now
        if time.ticks_diff(now,_last_warning_ms)<WARNING_PULSE_MS:
            beep_on()
        else:
            beep_off()
        return
    beep_off()

# wifi
w=network.WLAN(network.STA_IF); w.active(True); w.connect(SSID,PASS)
t0=time.ticks_ms()
while not w.isconnected():
    if time.ticks_diff(time.ticks_ms(),t0)>15000: raise RuntimeError("Wi-Fi failed")
    time.sleep(0.2)
ip=w.ifconfig()[0]; print("IP:",ip)
set_display("normal")

try:
    ntptime.host = "pool.ntp.org"
    ntptime.settime()
    print("NTP synced")
except Exception as e:
    print("NTP failed:", e)

# html
page_t = """<!doctype html><html><head><meta charset="utf-8">
<title>Pico Status</title>
<style>
 body{font-family:system-ui;background:#0b0f12;color:#e7ecf1;margin:0;padding:24px}
 .card{max-width:560px;background:#141a20;border-radius:16px;padding:24px;box-shadow:0 8px 30px rgba(0,0,0,.4)}
 h1{margin:0 0 8px 0}.kv{display:grid;grid-template-columns:120px 1fr;gap:6px 16px}
 .badge{display:inline-block;padding:4px 10px;border:1px solid #334155;border-radius:999px;font-size:12px;color:#94a3b8}
 .dot{width:14px;height:14px;border-radius:50%;display:inline-block;margin-right:8px}
 .green{background:#22c55e}.yellow{background:#f59e0b}.red{background:#ef4444}
</style></head>
<body><div class="card">
<div class="badge">Pico 2 W · {ip}</div>
<h1>Status: <span id="st">…</span></h1>
<div class="kv">
  <div>BPM</div><div id="bpm">–</div>
  <div>Temp</div><div id="temp">–</div>
  <div>Tilt</div><div id="tilt">–</div>
  <div>Updated</div><div id="ts">never</div>
  <div>Buzzer</div><div id="bz">off</div>
</div>
<p style="margin-top:12px"><span class="dot green"></span>normal &nbsp; <span class="dot yellow"></span>warning &nbsp; <span class="dot red"></span>critical</p>
</div>
<script>
async function refresh(){try{
  const r=await fetch('/state',{cache:'no-store'}); const j=await r.json();
  const fmt=v=> (v===null||v===undefined)?'–':v;
  // Prefer real Unix timestamp from the Pico, else fall back to browser time
  const ms = (j.updated_unix_ms && j.updated_unix_ms > 978307200000) ? j.updated_unix_ms : Date.now();

  document.getElementById('st').textContent   = j.status;
  document.getElementById('bpm').textContent  = fmt(j.bpm);
  document.getElementById('temp').textContent = fmt(j.temp);
  document.getElementById('tilt').textContent = fmt(j.tilt);
  document.getElementById('ts').textContent   = new Date(ms).toLocaleTimeString();
  document.getElementById('bz').textContent   =
    j.status==='critical' ? 'constant' :
    (j.status==='warning' ? 'chirp (10s)' : 'off');
}catch(e){}}
refresh(); setInterval(refresh,1000);
</script>
</body></html>"""
PAGE = page_t.replace("{ip}", ip).encode("utf-8")

def send_response(cl, body, ctype="text/plain"):
    if isinstance(body,str): body=body.encode("utf-8")
    hdr = ("HTTP/1.1 200 OK\r\n"
           "Connection: close\r\n"
           f"Content-Type: {ctype}\r\n"
           f"Content-Length: {len(body)}\r\n\r\n").encode("utf-8")
    cl.send(hdr); cl.send(body)

def send_404(cl): send_response(cl, b"not found", "text/plain")

def parse_qs(path:str):
    out={}
    if "?" not in path: return out
    qs=path.split("?",1)[1]
    for pair in qs.split("&"):
        if "=" in pair:
            k,v=pair.split("=",1)
            out[k.strip().lower()]=v.strip()
    return out

pat_status = ure.compile(r"/status\?level=([A-Za-z]+)")

# server
srv=socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
srv.bind(("0.0.0.0",8080)); srv.listen(4); print("Listening on",("0.0.0.0",8080))

while True:
    try:
        cl, addr = srv.accept()
        cl.settimeout(3.0)
        req=b""
        while b"\r\n\r\n" not in req:
            chunk=cl.recv(256)
            if not chunk: break
            req+=chunk
        try:
            start=req.split(b"\r\n",1)[0]
            path=start.split(b" ")[1].decode("utf-8","ignore")
        except: path="/"

        if path=="/" or path.startswith("/index"):
            send_response(cl, PAGE, "text/html; charset=utf-8")

        elif path.startswith("/state"):
            body = ujson.dumps({
                "status": LEVEL,
                "bpm": BPM, "temp": TEMP, "tilt": TILT,
                "updated_ms": (time.ticks_ms() & 0x7fffffff),         # keep if you want
                "age_ms": int(time.ticks_diff(time.ticks_ms(), UPDATED_MS))
            })
            send_response(cl, body, "application/json")

        elif path.startswith("/update"):
            qs=parse_qs(path)
            lv=qs.get("level","").lower()
            if lv in ("normal","warning","critical"):
                set_display(lv)
            # vitals
            def _num(s):
                try:
                    if s is None: return None
                    return float(s) if "." in s else int(s)
                except: return None
            update_metrics(_num(qs.get("bpm")),
                           _num(qs.get("temp")),
                           qs.get("tilt"))
            send_response(cl, "ok")

        elif path.startswith("/status"):  # backward-compat
            m=pat_status.search(path)
            if m:
                lv=m.group(1).lower()
                if lv in ("normal","warning","critical"):
                    set_display(lv); send_response(cl,"ok")
                else: send_response(cl,"bad level")
            else:
                send_response(cl,"usage: /status?level=normal|warning|critical")
        else:
            send_404(cl)

    except Exception:
        try: send_response(cl,"error")
        except: pass
    finally:
        try: cl.close()
        except: pass

    drive_buzzer()
    time.sleep(0.02)

