import time
from machine import Pin, ADC

# Pin Initialization
lm35_temp = ADC(Pin(26))
button = Pin(15, Pin.IN, Pin.PULL_UP)

# Sample size
samples_per_label = 30
labels = ["NORMAL", "WARNING", "CRITICAL"]

# Debounced button press
btn_last = 1
btn_stable = 1
btn_last_ms = 0
btn_pressed_pend = False
debounce_ms = 50

def check_button_press():
    global btn_last, btn_stable, btn_last_ms, btn_pressed_pend
    reading = button.value()
    now = time.ticks_ms()

    if reading != btn_last:
        btn_last = reading
        btn_last_ms = now

    if time.ticks_diff(now, btn_last_ms) > debounce_ms:
        if reading != btn_stable:
            btn_stable = reading
            if btn_stable == 0:
                btn_pressed_pend = True
            elif btn_stable == 1:
                if btn_pressed_pend:
                    btn_pressed_pend = False
                    return True
    return False

# Read Temp, Convert to Voltage, Convert to Deg. C
def read_lm35_temp():
    acc = 0
    for _ in range(16):
        acc += lm35_temp.read_u16()
        time.sleep(0.001)
    raw = acc / 16
    voltage = raw * (3.3 / 65535.0)
    temp_c = voltage / 0.01
    return temp_c

# Main Collector
for label in labels:
    # Wait for a full press-release
    while not check_button_press():
        time.sleep(0.01)

    for _ in range(samples_per_label):
        temp = read_lm35_temp()
        print(f"{temp:.2f},{label}")
        time.sleep(0.5)