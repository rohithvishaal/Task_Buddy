# ESP32 Smart Daily Calendar & Task Scheduler

A MicroPython-based task scheduler running on an ESP32 microcontroller with an OLED display. Displays your daily schedule, tracks task completions, shows weather, and provides smart reminders via a buzzer. Perfect for maintaining productivity with visual + audio cues.

**Key Features:**
- 📅 Separate schedules for **work days** and **off days**
- 🎯 Smart day detection (Mon–Fri auto-configured as work days)
- ✅ Task completion tracking with visual checkmarks
- 🌡️ Real-time temperature & humidity display
- 🔔 Smart alerts with customizable buzzer tones
- ⏰ Synchronized time via NTP with 4-server fallback
- 📱 Zero-touch WiFi provisioning (web portal via AP mode)
- 💾 Persistent settings & completions stored to flash
- 🖥️ Interactive OLED interface with 5 screens

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ESP32 Main Loop                          │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │          AsyncIO Task Orchestration                    │ │
│  │  (runs ~5 concurrent tasks with 1 shared state)        │ │
│  │                                                        │ │
│  │  ┌────────────────┐  ┌────────────────────────────┐    │ │
│  │  │  TimeKeeper    │  │ Schedule + Completions     │    │ │
│  │  ├────────────────┤  ├────────────────────────────┤    │ │
│  │  │ • NTP sync     │  │ EventScheduler             │    │ │
│  │  │ • WiFi conn.   │  │ • Resolve current/next evt │    │ │
│  │  │ • RTC tick     │  │ • Countdown calculation    │    │ │
│  │  │ • Status upd.  │  │ • Completion tracking      │    │ │
│  │  └────────────────┘  └────────────────────────────┘    │ │
│  │                                                        │ │
│  │  ┌────────────────┐  ┌────────────────────────────┐    │ │
│  │  │ InputHandler   │  │ AlertManager               │    │ │
│  │  ├────────────────┤  ├────────────────────────────┤    │ │
│  │  │ • Poll buttons │  │ • Buzzer control           │    │ │
│  │  │ • Debouncing   │  │ • Alert timing             │    │ │
│  │  │ • Long press   │  │ • Smart wind-down alerts   │    │ │
│  │  │ • Post events  │  │ • Completion signals       │    │ │
│  │  └────────────────┘  └────────────────────────────┘    │ │
│  │                                                        │ │
│  │  ┌────────────────┐  ┌────────────────────────────┐    │ │
│  │  │ SensorReader   │  │ DisplayManager             │    │ │
│  │  ├────────────────┤  ├────────────────────────────┤    │ │
│  │  │ • DHT22 poll   │  │ • OLED rendering (5 scr.)  │    │ │
│  │  │ • Temp/humidity│  │ • Input event handling     │    │ │
│  │  │ • Error retry  │  │ • Screen navigation        │    │ │
│  │  └────────────────┘  └────────────────────────────┘    │ │
│  │                                                        │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  SharedState (single instance, one lock)         │  │ │
│  │  │  Holds: time, schedule, completions, WiFi info,  │  │ │
│  │  │         screen state, sensor data, alerts        │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Module Descriptions

| Module | Purpose | Key Responsibilities |
|--------|---------|----------------------|
| **main.py** | Boot & orchestration | Initial splash, NTP sync, AP provisioning, task launch |
| **state.py** | Shared state container | Single source of truth, thread-safe via asyncio.Lock |
| **time_keeper.py** | Clock & NTP sync | WiFi connection, NTP sync (4 servers), RTC ticking |
| **scheduler.py** | Event resolution | Determine work/off day, current/next event, countdown |
| **display_manager.py** | OLED UI | 5 screens, input routing, visual feedback |
| **input_handler.py** | Button polling | Debounce, long-press detection, simultaneous UP+DN |
| **alert_manager.py** | Alerts & buzzer | Beep patterns, timing, wind-down tones |
| **sensor_reader.py** | DHT22 sensor | Temperature, humidity, retry on errors |
| **storage.py** | Flash persistence | Completions, settings, day overrides (JSON) |
| **config.py** | Hardware & schedule defaults | GPIO pins, WiFi SSID/password, default schedules |

---

## First-Time Setup: WiFi Provisioning

When the device boots without saved WiFi credentials, it enters **AP (access point) mode**:

### 1. AP Mode Discovery
The ESP32 creates its own WiFi network:
- **SSID:** `ESP32-Setup`
- **Password:** `setup1234`
- **Max clients:** 1 (only you can connect)

The OLED displays:
```
ESP32 Setup
AP: ESP32-Setup
PW: setup1234  
IP: 192.168.4.1
Waiting for client...
```

### 2. Connect & Open Web Form
1. Connect your phone/laptop to the `ESP32-Setup` WiFi network
2. Open browser → `http://192.168.4.1`
3. The OLED updates to show: `Waiting for client... Client connected!`

### 3. Fill WiFi Credentials
The web form shows:
- **WiFi SSID** (required): Your home WiFi network name
- **WiFi Password** (required): Your home WiFi password
- **Work Tasks** (optional): Daily schedule for Mon–Fri in format `HH:MM Event Name`
- **Off Tasks** (optional): Daily schedule for Sat–Sun in format `HH:MM Event Name`

Example work schedule:
```
07:30 Exercise
08:45 ML Study
11:00 Office
19:00 Dinner
19:45 DE Study
21:30 Gaming
22:05 Dune Book Reading
```

### 4. Submit & Synchronize
Click "Save and Connect":
1. Settings saved to ESP32 flash (`/settings.json`)
2. Device exits AP mode, connects to your WiFi
3. Syncs time from NTP (tries 4 servers with 15s timeout each)
4. Displays splash: "Syncing time..." then WiFi/NTP status
5. Once synced, launches all tasks and shows **HOME screen**

If WiFi credentials are incorrect, device reboots and re-enters AP mode.

---

## Using the Device: 5 Screens

### Screen 1: HOME (Default)
Displays your current task and countdown to next event.

```
Mon 04 Apr 09:47
 exercise (current)
Next: ML Study in 58m
25°C  60%
```

**Buttons:**
- **UP:** Jump to previous day
- **DOWN:** Jump to next day
- **SELECT (short):** Mark task as complete ✓
- **SELECT (long):** Go to SETTINGS

### Screen 2: DAY View
Full daily schedule with checkmarks for completed tasks.

```
Mon 04 Apr (work)
 ✓ 07:30 Exercise
   08:45 ML Study
   11:00 Office
→ (scroll with UP/DOWN)
```

**Buttons:**
- **UP/DOWN:** Scroll through today's events
- **SELECT:** Mark highlighted event complete
- **SELECT (long):** Return to HOME

### Screen 3: DETAIL View
Task details and your completion notes.

```
Event: Exercise
Time: 07:30
Status: Completed ✓
Notes: 30min run
```

**Buttons:**
- **SELECT:** Return to HOME

### Screen 4: QUOTE View
Inspirational quotes (rotates daily).

```
"The only way to do
great work is to love
what you do."
— Steve Jobs
```

**Buttons:**
- **SELECT:** Return to HOME

### Screen 5: SETTINGS
Configure day type (work/off) and reset onboarding.

```
Day type: work day
Alarm: ON

SEL=auto
UP+DN=reset
```

**Buttons:**
- **UP/DOWN:** Toggle between "work day" and "off day" (overrides auto-detection)
- **SELECT:** Clear override (return to Mon–Fri auto-detection)
- **UP + DOWN (simultaneous):** Reset all settings & WiFi credentials (reboots into AP mode)
- **SELECT (long):** Return to HOME

---

## Hardware Setup

### Components Required
- **ESP32-WROOM-32D** microcontroller
- **SSD1306 OLED 128×64 display** (I2C, address 0x3C)
- **DHT22 temperature/humidity sensor** (digital)
- **3× pushbuttons** (momentary, active-low)
- **Piezo buzzer** (8-16Ω, ~5V)
- **Slide switch** (alarm on/off, internal pull-up)
- **3.3V USB power supply**

### Wiring Diagram

```
ESP32 Pin         Component
─────────────────────────────────────
21 (SDA)      →  OLED SDA
22 (SCL)      →  OLED SCL
GND, 3.3V    →  OLED power

4             →  DHT22 "data" pin
GND, 3.3V    →  DHT22 power

18 (GPIOx)    →  UP button → GND
19 (GPIOx)    →  DOWN button → GND
32 (GPIOx)    →  SELECT button → GND

25 (PWM)      →  Buzzer + terminal
GND           →  Buzzer − terminal

33 (input)    →  Slide switch (internal pull-up)
GND           →  Slide switch other end
```

### Configuration

Edit [config.py](calender_esp32/config.py) to customize:

```python
# GPIO Pins
BTN_UP      = 18
BTN_DOWN    = 19
BTN_SELECT  = 32
DHT_PIN     = 4
BUZZER_PIN  = 25

# WiFi (can also be set via web form on first boot)
WIFI_SSID     = "YourNetworkSSID"
WIFI_PASSWORD = "YourPassword"

# Timezone (IST = UTC+5:30)
TZ_OFFSET_SEC = 19800

# Buzzer Tones
BUZZER_FREQ_ALERT   = 1000   # Hz for normal events
BUZZER_FREQ_WINDOWN = 600    # Hz for "wind-down" events

# Default Schedules (fallback if not set via web form)
WORK_DAYS = [
    (7, 30, "Exercise"),
    (8, 45, "ML Study"),
    # ...
]
OFF_DAYS = [
    (8, 30, "Long Exercise"),
    # ...
]
```

---

## Boot Sequence

```
1. ESP32 powers on
   ↓
2. main.py runs boot.py (if exists)
   ↓
3. Show OLED splash: "Starting..."
   ↓
4. Load from flash:
   - settings.json (WiFi SSID/password, custom schedules)
   - completions.json (today's task status)
   - day_override.json (work/off day override)
   ↓
5. Check WiFi credentials:
   
   IF no credentials saved:
   → Launch AP provisioning server
   → Show AP SSID/password on OLED
   → Wait for web form submission
   → Save settings and reboot
   
   ELSE:
   → Continue to NTP sync
   ↓
6. TimeKeeper.sync_time():
   - Connect to WiFi (one-time)
   - Try NTP servers in order (15s timeout each):
     pool.ntp.org → time.google.com → time.nist.gov → ntp.ubuntu.com
   - Infinite retries until success
   - Apply timezone offset (IST = UTC+5:30)
   - Disconnect WiFi to save power
   - Show status on splash
   ↓
7. Once time synced:
   - Launch all async tasks
   - DisplayManager shows HOME screen
   - Ready for user interaction
```

---

## Data Persistence

All data stored locally on ESP32 flash in JSON format:

### `/settings.json` (WiFi + custom schedules)
```json
{
  "wifi_ssid": "MyNetwork",
  "wifi_password": "encrypted_or_plain",
  "work_days": [
    [7, 30, "Exercise"],
    [8, 45, "ML Study"]
  ],
  "off_days": [
    [8, 30, "Long Exercise"]
  ]
}
```
**Note:** Editable via web form on first boot. Cleared only via SETTINGS → UP+DN reset.

### `/completions.json` (task status by date)
```json
{
  "2025-04-04": {
    "Exercise": true,
    "ML Study": false,
    "Office": true
  },
  "2025-04-03": {
    "Long Exercise": true,
    "Deep ML": true
  }
}
```
**Behavior:** Auto-pruned daily; old entries removed to keep file small.

### `/day_override.json` (work/off day override)
```json
{
  "override": true,
  "is_work_day": false
}
```
**Behavior:** Set via SETTINGS UP/DN buttons. Cleared by SELECT button.

---

## Async Task Concurrency Model

The system runs **5 concurrent async tasks** (+ main event loop), all coordinated via a single `SharedState` object with an `asyncio.Lock`:

```python
async def main():
    state = SharedState()
    
    tasks = [
        asyncio.create_task(time_keeper.run()),
        asyncio.create_task(scheduler.run()),
        asyncio.create_task(sensor_reader.run()),
        asyncio.create_task(input_handler.run()),
        asyncio.create_task(alert_manager.run()),
        asyncio.create_task(display_manager.run()),
    ]
    
    await asyncio.gather(*tasks)  # never returns
```

**Task Interactions:**
- **TimeKeeper** updates: `state.time_synced`, `state.hour/minute/second`, `state.wifi_status`, `state.ntp_status`
- **Scheduler** reads: `state.hour/minute/second`, `state.weekday`, `state.day_override`, `state.work_days/off_days`
- **Scheduler** writes: `state.schedule`, `state.current_idx`, `state.secs_to_next`, `state.alert_pending`
- **SensorReader** writes: `state.temperature`, `state.humidity`
- **InputHandler** writes: buttons to `state.input_queue`
- **DisplayManager** reads: all state fields; renders to OLED; pops from `state.input_queue`
- **AlertManager** reads: `state.alert_pending`, `state.schedule`; controls buzzer

No task blocks; all cooperate via `await asyncio.sleep()`.

---

## NTP Synchronization Flow

**Problem:** ESP32 has no RTC battery; time is lost on reboot.

**Solution:**
1. On boot, TimeKeeper connects to WiFi
2. Tries NTP in order: `pool.ntp.org` → `time.google.com` → `time.nist.gov` → `ntp.ubuntu.com`
3. **Each server gets 15 seconds before timeout**
4. **Infinite retries** (never gives up; will eventually sync)
5. Applies IST offset: UTC time + 19800 seconds
6. Disconnects WiFi (power saving)
7. ESP32 internal RTC ticks from that point forward (until next reboot)
8. Re-syncs every 30 minutes in background (WiFi brief reconnect)

**OLED Status Display:**
```
Syncing time...
WiFi: connecting
NTP: pending → (15s)
Server: pool.ntp.org
       ↓ (timeout)
NTP: pending
Server: time.google.com
       ↓ (success!)
NTP: synced ✓
Time: 09:47
```

---

## Alert & Buzzer System

### When Alerts Fire
- **Event start time reached** → Buzzer beeps (frequency based on event name)
- **Completion trigger** → Quick double-beep confirmation
- **Wind-down events** (e.g., "Dune") → Lower frequency (600 Hz) for calming effect
- **Normal events** → Higher frequency (1000 Hz) for alertness

### Buzzer Control

```python
# Customizable in config.py:
BUZZER_FREQ_ALERT   = 1000   # Hz for most events
BUZZER_FREQ_WINDOWN = 600    # Hz for "Dune" or chill events
BUZZER_DUTY         = 512    # volume (0-1023)
BUZZER_BEEP_MS      = 150    # single beep duration
```

### Slide Switch
- **ON:** Alarm enabled (buzzer responds to events)
- **OFF:** Silent mode (visual alerts only)

---

## Troubleshooting

### Device keeps rebooting into AP mode
**Cause:** Invalid WiFi credentials saved in settings.json
**Fix:** AP mode automatically re-enters if connection fails; re-submit form with correct SSID/password

### NTP never syncs
**Cause:** No internet connection or all NTP servers unreachable
**Fix:** Check WiFi SSID/password; move closer to router; ensure WiFi is 2.4GHz (not 5GHz)

### OLED display blank
**Cause:** I2C connection issue or display address mismatch
**Fix:** Check SDA/SCL wiring; verify display address is 0x3C

### Button presses not registering
**Cause:** GPIO pin configuration mismatch
**Fix:** Verify BTN_UP/BTN_DOWN/BTN_SELECT pins in config.py match your wiring

### Temperature reads as 0°C
**Cause:** DHT22 sensor issue or timing error
**Fix:** Check sensor wiring; reseat connector; sensor may need 2 seconds warm-up after power-on

### Tasks marked complete don't save
**Cause:** Flash write error
**Fix:** Check flash space availability; clear old completions.json if present

---

## Development Tips

### Running on Pymakr
1. Install MicroPython ESP32 firmware ([official guide](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html))
2. Use Pymakr VS Code extension to deploy files
3. Open device console to view debug output:
   ```
   [time_keeper] WiFi connecting...
   [time_keeper] NTP syncing... pool.ntp.org
   [time_keeper] NTP synced ✓
   [setup] got body: ssid=MyNet, passwd=MyPassword
   ```

### Adding Custom Events
Edit `config.WORK_DAYS` and `config.OFF_DAYS`:
```python
WORK_DAYS = [
    (7, 30, "Exercise"),      # 7:30 AM
    (8, 45, "Study"),         # 8:45 AM
    (14, 0, "Lunch Break"),   # 2:00 PM (24-hour format)
]
```

### Changing Alert Tones
Modify buzzer frequency by event name in [alert_manager.py](calender_esp32/alert_manager.py):
```python
if "Dune" in event_name or "Rest" in event_name:
    freq = config.BUZZER_FREQ_WINDOWN  # 600 Hz (calming)
else:
    freq = config.BUZZER_FREQ_ALERT    # 1000 Hz (alert)
```

### Debugging State
Print state from any async task:
```python
print("Current event:", state.current_event_name)
print("Time to next:", state.secs_to_next, "seconds")
print("WiFi status:", state.wifi_status)
print("Completions:", state.completions)
```

---

## Performance & Power Considerations

- **Display refresh:** 5 FPS (200ms between renders)
- **Button polling:** 20ms debounce, 600ms long-press threshold
- **Sensor polling:** DHT22 every 5 seconds (sensor limitation)
- **WiFi:** Off except during NTP sync (power saving)
- **Async tasks:** Sleep between updates (CPU efficient)

**Estimated current draw:**
- Idle: ~60 mA (display + ESP32)
- WiFi sync: ~150 mA (brief, ~10 seconds every 30 min)
- Full operation: ~100 mA average

---

## Files Reference

```
calender_esp32/
├── main.py                 # Boot sequence, AP provisioning
├── state.py                # Shared state container
├── config.py               # GPIO pins, WiFi, defaults
├── time_keeper.py          # NTP sync + clock ticking
├── scheduler.py            # Event resolution
├── display_manager.py      # OLED UI (5 screens)
├── input_handler.py        # Button polling & events
├── alert_manager.py        # Buzzer & alert timing
├── sensor_reader.py        # DHT22 temperature/humidity
├── storage.py              # Flash persistence (JSON)
├── ssd1306.py              # OLED driver (SSD1306)
├── quotes.py               # Inspirational quotes
├── pymakr.conf             # Pymakr project config
└── README.md               # This file
```

---

## License & Attribution

Built for personal productivity. Feel free to adapt for your own use case.

- **MicroPython ESP32:** https://docs.micropython.org/
- **SSD1306 driver:** Micropython community
- **NTP:** ntptime module (MicroPython standard library)

---

## Questions or Issues?

Check [Troubleshooting](#troubleshooting) section or review debug output in Pymakr console.

Happy scheduling! 📅✨
