# ─────────────────────────────────────────────
#  time_keeper.py  —  NTP sync + clock ticker
# ─────────────────────────────────────────────
# Responsibilities:
#   1. Connect to WiFi (with retries)
#   2. Sync RTC from NTP, applying IST offset
#   3. Re-sync every NTP_SYNC_INTERVAL_MIN minutes
#   4. Update state time fields every second from RTC
# WiFi is disconnected after each sync to save power.

import uasyncio as asyncio
import network
import ntptime
import time
import config


class TimeKeeper:
    def __init__(self, state, wifi_ssid=None, wifi_password=None):
        self.state = state
        self._wlan = network.WLAN(network.STA_IF)
        self._last_sync_sec = 0
        self.wifi_ssid = wifi_ssid or config.WIFI_SSID
        self.wifi_password = wifi_password or config.WIFI_PASSWORD

    # ── public entry point ────────────────────

    async def run(self):
        # assumes initial sync already done by main()
        self._last_sync_sec = time.time()

        while True:
            self._tick()
            await asyncio.sleep(1)

            elapsed_min = (time.time() - self._last_sync_sec) // 60
            if elapsed_min >= config.NTP_SYNC_INTERVAL_MIN:
                asyncio.create_task(self._background_sync())
                self._last_sync_sec = time.time()

    # ── sync ──────────────────────────────────

    async def sync_time(self):
        """Connect to WiFi once, sync NTP until successful, disconnect only on success."""
        ntp_servers = ["pool.ntp.org", "time.google.com", "time.nist.gov", "ntp.ubuntu.com"]
        
        # Connect WiFi once for all attempts
        await self._wifi_connect()
        await asyncio.sleep(2)  # Ensure network is stable
        
        attempt = 1
        while attempt <= config.NTP_MAX_RETRIES:
            print("[time] NTP sync attempt {}".format(attempt))
            
            for server in ntp_servers:
                try:
                    print("[time] Trying NTP server:", server)
                    ntptime.timeout = 15
                    ntptime.host = server
                    ntptime.settime()  # sets UTC in RTC
                    print("[time] Success with server:", server)
                    
                    # NTP sync successful, apply timezone and update state
                    self.state.ntp_status = "synced"
                    self.state.ntp_server = server
                    await asyncio.sleep(1)  # Wait for RTC to update
                    self._apply_tz_offset()
                    self.state.time_synced = True
                    self._tick()
                    print("[time] synced →", self.state.time_str())
                    
                    # Disconnect WiFi only after successful sync
                    self._wifi_disconnect()
                    return  # Exit function on success
                    
                except Exception as e:
                    print("[time] Failed with server {}: {}".format(server, e))
                    self.state.ntp_status = "failed"
                    self.state.ntp_server = server
                    continue  # Try next server
            
            # All servers failed for this attempt, wait before retry
            attempt += 1
            print("[time] All servers failed, retrying in 5 seconds...")
            await asyncio.sleep(5)

    async def _background_sync(self):
        await self.sync_time()

    # ── helpers ───────────────────────────────

    async def _wifi_connect(self):
        print("[wifi] disconnecting any existing connection...")
        self._wifi_disconnect()
        self.state.wifi_status = "connecting"

        print("[wifi] activating...")
        self._wlan.active(True)
        await asyncio.sleep(2)  # Wait for activation
        if not self._wlan.isconnected():
            print("[wifi] connecting to", self.wifi_ssid)
            self._wlan.connect(self.wifi_ssid, self.wifi_password)
            print("[wifi] status after connect:", self._wlan.status())
            for i in range(40):  # 20 s timeout
                if self._wlan.isconnected():
                    print("[wifi] connected!")
                    self.state.wifi_status = "connected"
                    break
                await asyncio.sleep(2)
                if i % 4 == 0:  # Print every 2 seconds
                    print("[wifi] waiting... status:", self._wlan.status())
        if not self._wlan.isconnected():
            print("[wifi] final status:", self._wlan.status())
            self.state.wifi_status = "disconnected"
            raise OSError("WiFi connect timeout")

    def _wifi_disconnect(self):
        try:
            self._wlan.disconnect()
            self._wlan.active(False)
        except Exception:
            pass
        self.state.wifi_status = "disconnected"

    def _apply_tz_offset(self):
        """Add IST offset to RTC (MicroPython RTC holds UTC after ntptime)."""
        import machine

        rtc = machine.RTC()
        dt = rtc.datetime()
        # dt = (year, month, day, weekday, hour, min, sec, subsec)
        utc_epoch = time.mktime((dt[0], dt[1], dt[2], dt[4], dt[5], dt[6], 0, 0))
        ist_epoch = utc_epoch + config.TZ_OFFSET_SEC
        ist_tuple = time.localtime(ist_epoch)
        # weekday: MicroPython RTC weekday 0=Mon
        rtc.datetime(
            (
                ist_tuple[0],
                ist_tuple[1],
                ist_tuple[2],
                ist_tuple[6],  # weekday
                ist_tuple[3],
                ist_tuple[4],
                ist_tuple[5],
                0,
            )
        )

    def _tick(self):
        """Read RTC and update state time fields."""
        import machine

        dt = machine.RTC().datetime()
        s = self.state
        s.year = dt[0]
        s.month = dt[1]
        s.day = dt[2]
        s.weekday = dt[3]
        s.hour = dt[4]
        s.minute = dt[5]
        s.second = dt[6]
        s.needs_redraw = True
