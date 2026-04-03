# ─────────────────────────────────────────────
#  config.py  —  all hardware & schedule config
# ─────────────────────────────────────────────

# ── GPIO pins ──────────────────────────────────
OLED_SDA    = 21
OLED_SCL    = 22
DHT_PIN     = 4
BUZZER_PIN  = 25
SWITCH_PIN  = 33
BTN_UP      = 18   
BTN_DOWN    = 19   
BTN_SELECT  = 32   

# ── WiFi ───────────────────────────────────────
WIFI_SSID     = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

# ── Timezone ───────────────────────────────────
# IST = UTC+5:30 = 19800 seconds
TZ_OFFSET_SEC = 19800
NTP_SYNC_INTERVAL_MIN = 30
NTP_MAX_RETRIES = 5

# ── Display ────────────────────────────────────
OLED_WIDTH  = 128
OLED_HEIGHT = 64
FPS         = 5    # display refresh rate

# ── Button timing (ms) ─────────────────────────
DEBOUNCE_MS    = 20
LONG_PRESS_MS  = 600

# ── Buzzer ─────────────────────────────────────
BUZZER_FREQ_ALERT   = 1000   # Hz — normal event reminder
BUZZER_FREQ_WINDOWN = 600    # Hz — Dune / wind-down events
BUZZER_DUTY         = 512    # 0–1023
BUZZER_BEEP_MS      = 150    # single beep duration

# ── Schedules ──────────────────────────────────
# Each entry: (hour, minute, "Event name")
WORK_DAYS = [
    ( 7, 30, "Exercise"),
    ( 8, 45, "ML Study"),
    (11,  0, "Office"),
    (19,  0, "Dinner"),
    (19, 45, "DE Study"),
    (21, 30, "Gaming"),
    (22, 5, "Dune"),
]

OFF_DAYS = [
    ( 8, 30, "Long Exercise"),
    (10,  0, "Deep ML"),
    (12,  0, "DE Theory"),
    (14,  0, "Movie/Rest"),
    (21, 30, "Gaming"),
    (22, 45, "Dune"),
]

# ── Calendar helpers ───────────────────────────
DAYS   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
