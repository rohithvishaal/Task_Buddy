# ─────────────────────────────────────────────
#  state.py  —  shared state across all tasks
# ─────────────────────────────────────────────
# One SharedState instance is created at boot and passed
# to every task. No global variables anywhere else.
# asyncio.Lock protects fields written from multiple tasks.

import uasyncio as asyncio

# Simple queue implementation since uasyncio.Queue is not available in this MicroPython version
class SimpleQueue:
    def __init__(self, maxsize=0):
        self._queue = []
        self._maxsize = maxsize

    def put_nowait(self, item):
        if self._maxsize > 0 and len(self._queue) >= self._maxsize:
            # Drop the item if full, as per original behavior
            return
        self._queue.append(item)

    def get_nowait(self):
        if not self._queue:
            raise IndexError("Queue empty")
        return self._queue.pop(0)

    def empty(self):
        return len(self._queue) == 0

    def full(self):
        return self._maxsize > 0 and len(self._queue) >= self._maxsize

# ── UI screen identifiers ──────────────────────
SCREEN_HOME    = "home"
SCREEN_DAY     = "day"
SCREEN_DETAIL  = "detail"
SCREEN_QUOTE   = "quote"
SCREEN_SETTINGS = "settings"

# ── Input event types ──────────────────────────
EVT_UP          = "up"
EVT_DOWN        = "down"
EVT_SELECT      = "select"
EVT_SELECT_LONG = "select_long"
EVT_RESET       = "reset"  # simultaneous UP+DOWN


class SharedState:
    def __init__(self):
        # ── Time ──────────────────────────────
        self.year   = 2025
        self.month  = 1
        self.day    = 1
        self.hour   = 0
        self.minute = 0
        self.second = 0
        self.weekday = 0        # 0=Mon … 6=Sun
        self.time_synced = False

        # ── TimeKeeper status ──────────────────
        self.wifi_status = "disconnected"  # connecting / connected / disconnected
        self.ntp_status = "pending"        # pending / synced / failed
        self.ntp_server = ""

        # ── Schedule ──────────────────────────
        self.schedule     = []  # list of (h, m, name) for today
        self.work_days    = []
        self.off_days     = []

        # AP provisioning status
        self.ap_mode      = False
        self.ap_ssid      = "ESP32-Setup"
        self.ap_password  = "setup1234"
        self.ap_ip        = ""
        self.ap_client_ip = ""
        self.current_idx  = -1  # index of current event (-1 = before first)
        self.next_idx     = 0   # index of next event
        self.secs_to_next = 0   # countdown seconds to next event
        self.is_work_day  = True
        self.day_override = None  # None | True | False (set from settings)

        # ── Sensor ────────────────────────────
        self.temperature = None
        self.humidity    = None
        self._sensor_lock = asyncio.Lock()

        # ── Alerts ────────────────────────────
        self.alarm_armed  = True   # slide switch state
        self.alert_pending = False  # set by scheduler, cleared by alert task

        # ── Completions ───────────────────────
        # dict keyed by event name → bool
        # loaded/saved by storage.py
        self.completions = {}

        # ── UI ────────────────────────────────
        self.screen          = SCREEN_HOME
        self.day_view_cursor = 0    # highlighted row in day view
        self.detail_idx      = 0    # which event is open in detail view
        self.quote_idx       = -1   # -1 = not yet picked
        self.input_queue     = SimpleQueue(maxsize=8)
        self._ui_lock        = asyncio.Lock()

        # ── Misc ──────────────────────────────
        self.needs_redraw = True    # display task checks this

    # ── Convenience helpers ───────────────────

    @property
    def current_event(self):
        if 0 <= self.current_idx < len(self.schedule):
            return self.schedule[self.current_idx][2]
        return "No Events"

    @property
    def next_event(self):
        if 0 <= self.next_idx < len(self.schedule):
            return self.schedule[self.next_idx][2]
        return "—"

    def time_str(self):
        return "{:02d}:{:02d}".format(self.hour, self.minute)

    def date_str(self):
        from config import DAYS, MONTHS
        return "{} {:02d} {}".format(
            DAYS[self.weekday],
            self.day,
            MONTHS[self.month - 1]
        )

    def countdown_str(self):
        m, s = divmod(self.secs_to_next, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return "{:d}h {:02d}m".format(h, m)
        return "{:d}m {:02d}s".format(m, s)
