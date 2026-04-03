# ─────────────────────────────────────────────
#  sensor_reader.py  —  DHT temperature/humidity
# ─────────────────────────────────────────────
# Reads the DHT sensor every 30 s and updates
# state.temperature / state.humidity.
# DHT sensors have a 1–2 s minimum read interval;
# 30 s is conservative and sufficient for display.

import uasyncio as asyncio
import dht
import machine
import config


SENSOR_INTERVAL_SEC = 30


class SensorReader:
    def __init__(self, state):
        self.state  = state
        # Change dht.DHT22 to dht.DHT11 if you're using a DHT11
        self._sensor = dht.DHT11(machine.Pin(config.DHT_PIN))

    async def run(self):
        while True:
            await self._read()
            await asyncio.sleep(SENSOR_INTERVAL_SEC)

    async def _read(self):
        try:
            self._sensor.measure()
            async with self.state._sensor_lock:
                self.state.temperature = self._sensor.temperature()
                self.state.humidity    = self._sensor.humidity()
            print("[sensor] {:.1f}°C  {:.1f}%".format(
                self.state.temperature, self.state.humidity))
        except OSError as e:
            print("[sensor] read error:", e)
            # Keep previous values; don't blank the display
