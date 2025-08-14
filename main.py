# Imports
import uasyncio as asyncio
import time
from machine import ADC, Pin
import utime

# Pin Initialization
heart_rate = ADC(Pin(28))
lm35_temp = ADC(Pin(26))
tilt = Pin(17, Pin.IN, Pin.PULL_UP)
button = Pin(15, Pin.IN, Pin.PULL_UP)

# Temperature Sensor Offset
temp_offset = 5.0 # Change based on sensor accuracy / calibration

# Tilt Switch Logic Initialization
tilt_active_high = False

# Sampling Periods
temp_pd_s = 2.0
tilt_pd_s = 0.2
classify_pd_s = 1.0

# Heart-rate sampling parameters
smoothing = 0.95 # for baseline EMA
peak_offset = 8000 # offset above baseline to detect a beat, may vary from patient to patient
min_bpm = 40
max_bpm = 180

# Thresholds for Health Metrics
# Heart rate (bpm)
hr_normal_min, hr_normal_max = 60, 100
hr_warn_min,  hr_warn_max  = 50, 120

# Temperature (°C) — ambient profile so ~27–28 °C is NORMAL
temp_normal_min, temp_normal_max = 20.0, 28.0    # CHANGED from core-body bands
temp_warn_min,   temp_warn_max   = 15.0, 32.0

# Tilt (deg) — we map digital tilt to 0 or 90
tilt_normal_max = 20
tilt_warn_max   = 40

# Health State
state = {
    "hr_bpm": None,
    "temp_c": None,
    "tilt_deg": None,
    "last_status": "UNKNOWN"
}

# Band severity order (ADDED)
ORDER = {"CRITICAL": 3, "WARNING": 2, "NORMAL": 1, "UNKNOWN": 0}

# Non-blocking button press detection (debounced, fires once per press)
btn_last = 1
btn_stable = 1
btn_last_ms = 0
btn_pressed_pending = False
debounce = 50

def check_button_press():
    global btn_last, btn_stable, btn_last_ms, btn_pressed_pending
    reading = button.value()           # 1 = not pressed, 0 = pressed with PULL_UP
    now = time.ticks_ms()

    if reading != btn_last:
        btn_last = reading
        btn_last_ms = now

    if time.ticks_diff(now, btn_last_ms) > debounce:
        if reading != btn_stable:
            btn_stable = reading
            if btn_stable == 0:       # pressed
                btn_pressed_pending = True
            elif btn_stable == 1:     # released
                if btn_pressed_pending:
                    btn_pressed_pending = False
                    return True
    return False

# Sensor Task Functions
async def heart_rate_task():
    baseline = heart_rate.read_u16()
    last_peak_time = None
    bpm_vals = []
    peak_active = False

    while True:
        raw = heart_rate.read_u16()
        baseline = (smoothing * baseline) + ((1.0 - smoothing) * raw)

        if (not peak_active) and (raw > baseline + peak_offset):
            peak_active = True
            now = utime.ticks_ms()

            if last_peak_time is not None:
                ibi = utime.ticks_diff(now, last_peak_time)
                if ibi > 0:
                    bpm = 60000.0 / ibi
                    if min_bpm <= bpm <= max_bpm:
                        bpm_vals.append(bpm)
                        if len(bpm_vals) > 5:
                            bpm_vals.pop(0)
                        state["hr_bpm"] = sum(bpm_vals) / len(bpm_vals)
            last_peak_time = now

        if peak_active and (raw < baseline):
            peak_active = False

        await asyncio.sleep_ms(10)

async def temperature_task():
    while True:
        samples = 16
        acc = 0
        for _ in range(samples):
            acc += lm35_temp.read_u16()
            await asyncio.sleep_ms(1)
        raw = acc / samples
        voltage = raw * (3.3 / 65535.0)
        temp_c = voltage / 0.01
        if temp_c < -20: temp_c = -20
        if temp_c > 120: temp_c = 120
        state["temp_c"] = temp_c + temp_offset
        await asyncio.sleep(temp_pd_s)

async def tilt_task():
    while True:
        ones = 0
        for _ in range(5):
            sample = tilt.value()
            if not tilt_active_high:
                sample = 1 - sample
            ones += 1 if sample else 0
            await asyncio.sleep_ms(2)
        tilted = ones >= 3
        state["tilt_deg"] = 90.0 if tilted else 0.0
        await asyncio.sleep(tilt_pd_s)

# Classification helpers
def _band(x, nmin=None, nmax=None, wmin=None, wmax=None):
    if x is None:
        return "UNKNOWN"
    if nmin is not None and nmax is not None and nmin <= x <= nmax:
        return "NORMAL"
    in_warn = True
    if wmin is not None and x < wmin: in_warn = False
    if wmax is not None and x > wmax: in_warn = False
    return "WARNING" if in_warn else "CRITICAL"

def get_patient_status(hr_bpm, temp_c, tilt_deg):
    hr_band   = _band(hr_bpm, hr_normal_min, hr_normal_max, hr_warn_min, hr_warn_max)
    temp_band = _band(temp_c,  temp_normal_min, temp_normal_max, temp_warn_min, temp_warn_max)

    if tilt_deg == 90.0:
        tilt_band = "CRITICAL"
    elif tilt_deg == 0.0:
        tilt_band = "NORMAL"
    else:
        tilt_band = "UNKNOWN"

    order = {"CRITICAL": 3, "WARNING": 2, "NORMAL": 1, "UNKNOWN": 0}
    overall = max([hr_band, temp_band, tilt_band], key=lambda b: order.get(b, 0))
    return overall

# Implementation (MODIFIED to combine client label, HR band, and tilt band)
def print_status():
    temp_c = state["temp_c"]
    bpm = state["hr_bpm"]
    tilt_deg = state["tilt_deg"]

    if temp_c is None:
        print("UNKNOWN,bpm=NA,temp=NA,tilt=NA")
        return

    # Send temperature to client for ML classification
    print(f"{temp_c:.2f}")

    # Read label back from client (NORMAL/WARNING/CRITICAL)
    import sys
    import select
    label = "UNKNOWN"
    timeout = 1000  # ms
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < timeout:
        if select.select([sys.stdin], [], [], 0)[0]:
            label = sys.stdin.readline().strip().upper()
            break

    # Local bands: HR thresholds, and tilt discrete mapping
    hr_band = _band(bpm, hr_normal_min, hr_normal_max, hr_warn_min, hr_warn_max)
    if tilt_deg == 90.0:
        tilt_band = "CRITICAL"
    elif tilt_deg == 0.0:
        tilt_band = "NORMAL"
    else:
        tilt_band = "UNKNOWN"

    # Combine severity
    overall = max([label, hr_band, tilt_band], key=lambda b: ORDER.get(b, 0))
    bpm_str = "NA" if bpm is None else f"{bpm:.1f}"
    tilt_str = "NA" if tilt_deg is None else f"{tilt_deg:.0f}"
    print(f"{overall},bpm={bpm_str},temp={temp_c:.1f},tilt={tilt_str}")

async def main():
    asyncio.create_task(heart_rate_task())
    asyncio.create_task(temperature_task())
    asyncio.create_task(tilt_task())

    monitoring = False
    period_ms = int(classify_pd_s * 1000)
    next_ts = time.ticks_add(time.ticks_ms(), period_ms)

    while True:
        if check_button_press():
            monitoring = not monitoring
            print("Monitoring STARTED" if monitoring else "Monitoring STOPPED")

        now = time.ticks_ms()
        if time.ticks_diff(now, next_ts) >= 0:
            if monitoring:
                print_status()
            next_ts = time.ticks_add(next_ts, period_ms)

        await asyncio.sleep_ms(20)

asyncio.run(main())