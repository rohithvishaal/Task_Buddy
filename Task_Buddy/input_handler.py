# ─────────────────────────────────────────────
#  input_handler.py  —  button & switch polling
# ─────────────────────────────────────────────
# Polls all inputs every DEBOUNCE_MS milliseconds.
# Detects:
#   - Short press  (<  LONG_PRESS_MS)
#   - Long press   (>= LONG_PRESS_MS)
# Posts InputEvent strings to state.input_queue for
# the display/UI task to consume.
#
# GPIO 34 & 35 are input-only on ESP32 — no internal
# pull-up. Wire 10kΩ resistors from each to 3.3V.
# Buttons connect pin to GND (active-low).

import uasyncio as asyncio
import machine
import time
import config
from state import EVT_UP, EVT_DOWN, EVT_SELECT, EVT_SELECT_LONG, EVT_RESET


class InputHandler:
    def __init__(self, state):
        self.state = state

        # BTN_UP / BTN_DOWN: no internal pull-up (input-only pins)
        self._btn_up  = machine.Pin(config.BTN_UP,   machine.Pin.IN, machine.Pin.PULL_UP)
        self._btn_dn  = machine.Pin(config.BTN_DOWN,  machine.Pin.IN, machine.Pin.PULL_UP)
        # BTN_SELECT: pull-up enabled — button connects to GND
        self._btn_sel = machine.Pin(config.BTN_SELECT, machine.Pin.IN,
                                    machine.Pin.PULL_UP)
        # Slide switch — PULL_UP, switch connects to GND = alarm OFF
        self._switch  = machine.Pin(config.SWITCH_PIN, machine.Pin.IN,
                                    machine.Pin.PULL_UP)

        # Internal state for each button
        # { pin_obj: {"pressed": bool, "press_time": ms, "fired": bool} }
        self._btns = {
            self._btn_up:  {"evt": EVT_UP,     "pressed": False, "t": 0, "fired": False},
            self._btn_dn:  {"evt": EVT_DOWN,   "pressed": False, "t": 0, "fired": False},
            self._btn_sel: {"evt": EVT_SELECT, "pressed": False, "t": 0, "fired": False},
        }

    async def run(self):
        while True:
            self._poll_switch()
            self._poll_buttons()
            await asyncio.sleep_ms(config.DEBOUNCE_MS)

    # ── private ───────────────────────────────

    def _poll_switch(self):
        # Switch pulled up — 0 = switch closed = alarm ARMED
        # Invert so True = armed = alarm on
        armed = (self._switch.value() == 0)
        if armed != self.state.alarm_armed:
            self.state.alarm_armed = armed
            print("[input] alarm", "ARMED" if armed else "disarmed")

    def _poll_buttons(self):
        now = time.ticks_ms()
        q   = self.state.input_queue

        for pin, info in self._btns.items():
            active = (pin.value() == 0)   # active-low

            if active and not info["pressed"]:
                # leading edge — button just pressed
                info["pressed"] = True
                info["t"]       = now
                info["fired"]   = False
                print("[input] press start", info["evt"])

            elif not active and info["pressed"]:
                # trailing edge — button released
                held = time.ticks_diff(now, info["t"])
                info["pressed"] = False
                print("[input] release", info["evt"], "held", held)

                if not info["fired"]:
                    if held >= config.LONG_PRESS_MS and info["evt"] == EVT_SELECT:
                        self._post(q, EVT_SELECT_LONG)
                    else:
                        self._post(q, info["evt"])

            elif active and info["pressed"] and not info["fired"]:
                # still held — fire long press immediately at threshold
                held = time.ticks_diff(now, info["t"])
                if held >= config.LONG_PRESS_MS and info["evt"] == EVT_SELECT:
                    self._post(q, EVT_SELECT_LONG)
                    info["fired"] = True   # don't re-fire on release
        
        # Check for simultaneous UP+DOWN (reset gesture)
        up_pressed = self._btn_up.value() == 0
        dn_pressed = self._btn_dn.value() == 0
        if up_pressed and dn_pressed:
            # Both buttons held — detect long press
            if not hasattr(self, '_simultaneous_start'):
                self._simultaneous_start = now
            elif time.ticks_diff(now, self._simultaneous_start) >= config.LONG_PRESS_MS:
                if not hasattr(self, '_simultaneous_fired') or not self._simultaneous_fired:
                    self._post(q, EVT_RESET)
                    self._simultaneous_fired = True
        else:
            # Released
            self._simultaneous_start = None
            self._simultaneous_fired = False

    @staticmethod
    def _post(queue, event):
        try:
            queue.put_nowait(event)
            # For SimpleQueue, raw data structure is queue._queue
            # (for debugging only, not guaranteed in production)
            size = len(getattr(queue, '_queue', []))
            print("[input] queued", event, "size", size)
        except Exception as e:
            print("[input] queue full/drop", e)

