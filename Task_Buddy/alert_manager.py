# ─────────────────────────────────────────────
#  alert_manager.py  —  buzzer alert patterns
# ─────────────────────────────────────────────
# Watches state.alert_pending.
# When set, plays a tone pattern and clears the flag.
# Slide switch (state.alarm_armed) gates all sounds.
#
# Patterns:
#   Normal event  → two short beeps (1000 Hz)
#   Wind-down     → three slow beeps (600 Hz)  ["Dune" / "Gaming"]

import uasyncio as asyncio
import machine
import config


# Events that use the slower wind-down pattern
WINDOWN_EVENTS = {"Dune", "Gaming"}


class AlertManager:
    def __init__(self, state):
        self.state = state
        self._pwm  = None   # created lazily to avoid noise at boot

    async def run(self):
        while True:
            if self.state.alert_pending:
                self.state.alert_pending = False
                if self.state.alarm_armed:
                    await self._play_for_current_event()
            await asyncio.sleep_ms(100)

    # ── pattern selection ─────────────────────

    async def _play_for_current_event(self):
        event = self.state.current_event
        if event in WINDOWN_EVENTS:
            await self._pattern_windown()
        else:
            await self._pattern_alert()

    # ── beep patterns ─────────────────────────

    async def _pattern_alert(self):
        """Two short beeps — normal event reminder."""
        for _ in range(2):
            await self._beep(config.BUZZER_FREQ_ALERT, config.BUZZER_BEEP_MS)
            await asyncio.sleep_ms(120)

    async def _pattern_windown(self):
        """Three slower beeps — wind-down / sleep-prep events."""
        for _ in range(3):
            await self._beep(config.BUZZER_FREQ_WINDOWN, 250)
            await asyncio.sleep_ms(200)

    # ── low-level buzzer control ───────────────

    async def _beep(self, freq, duration_ms):
        pwm = self._get_pwm()
        pwm.freq(freq)
        pwm.duty(config.BUZZER_DUTY)
        await asyncio.sleep_ms(duration_ms)
        pwm.duty(0)

    def _get_pwm(self):
        if self._pwm is None:
            self._pwm = machine.PWM(
                machine.Pin(config.BUZZER_PIN),
                freq=1000,
                duty=0
            )
        return self._pwm

    def deinit(self):
        if self._pwm:
            self._pwm.deinit()
            self._pwm = None
