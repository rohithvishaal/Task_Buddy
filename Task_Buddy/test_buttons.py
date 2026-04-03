import machine
import time
import config

# Initialize pins as in input_handler.py
btn_up = machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_UP)
btn_down = machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_UP)
btn_select = machine.Pin(32, machine.Pin.IN, machine.Pin.PULL_UP)
switch = machine.Pin(config.SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)

print("Button test started. Press buttons to see value changes.")
print("Active-low: 0 = pressed, 1 = released")
print("Press Ctrl+C to stop.")

try:
    while True:
        up_val = btn_up.value()
        down_val = btn_down.value()
        select_val = btn_select.value()
        switch_val = switch.value()

        print(f"UP: {up_val} | DOWN: {down_val} | SELECT: {select_val} | SWITCH: {switch_val}")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Test stopped.")