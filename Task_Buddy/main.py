# ─────────────────────────────────────────────
#  main.py  —  boot + task launch
# ─────────────────────────────────────────────
# Boot order:
#   1. Show splash on OLED
#   2. Load saved completions + day override from flash
#   3. Sync NTP (blocking — all other tasks need valid time)
#   4. Launch all async tasks
#   5. Keep-alive loop

import uasyncio as asyncio
import machine
from machine import I2C, Pin
import ssd1306

import config
import storage
from state import SharedState
from time_keeper     import TimeKeeper
from scheduler       import EventScheduler
from sensor_reader   import SensorReader
from input_handler   import InputHandler
from alert_manager   import AlertManager
from display_manager import DisplayManager

import network
import socket


# ── helper helpers ─────────────────────────────

def _urldecode(value):
    value = value.replace("+", " ")
    i = 0
    out = ""
    while i < len(value):
        if value[i] == "%" and i + 2 < len(value):
            try:
                out += chr(int(value[i + 1 : i + 3], 16))
                i += 3
                continue
            except Exception:
                pass
        out += value[i]
        i += 1
    return out


def _parse_post(body):
    params = {}
    for pair in body.split("&"):
        if "=" not in pair:
            continue
        key, val = pair.split("=", 1)
        params[key] = _urldecode(val)
    return params


def _format_task_rows(tasks):
    rows = ""
    for h, m, name in tasks:
        rows += "<tr><td>{:02d}:{:02d}</td><td>{}</td></tr>".format(h, m, name)
    return rows


def run_ap_config_portal(default_work, default_off, state, oled):
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=state.ap_ssid, password=state.ap_password, authmode=network.AUTH_WPA_WPA2_PSK, max_clients=1)
    import time
    time.sleep(2)  # Wait for AP to be ready
    ip = ap.ifconfig()[0]
    state.ap_mode = True
    state.ap_ip = ip
    state.ap_client_ip = ""
    print("[setup] AP mode on {} (user: {})".format(ip, state.ap_password))
    
    # Update OLED immediately with AP info
    _show_splash(oled, state)

    addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    s.settimeout(30)  # 30 second timeout

    html_form = """
<html>
<head><title>ESP32 WiFi Setup</title></head>
<body>
<h3>ESP32 setup</h3>
<p>This is required so that the ESP32 can connect to your WiFi network and query for NTP (time)</p>
<p>Open: http://{}</p>
<form method='POST'>
<label>WiFi SSID:<br><input name='ssid' required></label><br>
<label>WiFi Password:<br><input name='password' type='password' required></label><br>
<label>Work tasks (hh:mm:label per line):<br><textarea name='work_days' rows='6' cols='30'>{}</textarea></label><br>
<label>Off tasks (hh:mm:label per line):<br><textarea name='off_days' rows='6' cols='30'>{}</textarea></label><br>
<button type='submit'>Save and Connect</button>
</form>
<hr>
<h4>Current Work Schedule</h4>
<table border='1'><tr><th>Time</th><th>Task</th></tr>{}</table>
<h4>Current Off Schedule</h4>
<table border='1'><tr><th>Time</th><th>Task</th></tr>{}</table>
</body>
</html>
""".format(ip, "", "", _format_task_rows(default_work), _format_task_rows(default_off))

    user_settings = {}

    while True:
        try:
            cl, addr = s.accept()
            state.ap_client_ip = addr[0]
            print("[setup] client", addr)
            cl.settimeout(10)
            
            # Read the entire HTTP request (headers + body in one go)
            request_data = b""
            try:
                request_data = cl.recv(2048)
            except:
                cl.close()
                continue
                
            if not request_data:
                cl.close()
                continue
            
            request_text = request_data.decode("utf-8", "ignore")
            
            # Split headers from body at the double line break
            if "\r\n\r\n" in request_text:
                header_part, body_part = request_text.split("\r\n\r\n", 1)
            else:
                header_part = request_text
                body_part = ""
            
            lines = header_part.split("\r\n")
            if not lines[0]:
                cl.close()
                continue
                
            parts = lines[0].split()
            if len(parts) < 3:
                cl.close()
                continue
            method, path, _ = parts[0], parts[1], parts[2]
            
            print("[setup] {} {}".format(method, path))
        except Exception as e:
            print("[setup] socket error:", e)
            try:
                cl.close()
            except:
                pass
            continue
        
        content_length = 0
        for header_line in lines[1:]:
            if not header_line:
                break
            if header_line.lower().startswith("content-length:"):
                try:
                    content_length = int(header_line.split(":", 1)[1].strip())
                except Exception:
                    content_length = 0

        if method == "POST":
            # Form data is already in body_part from initial recv
            content = body_part
            print("[setup] got body: {} bytes".format(len(body_part)))
            
            form = _parse_post(content)
            wifi_ssid = form.get("ssid", "").strip()
            wifi_password = form.get("password", "").strip()
            work_days_txt = form.get("work_days", "").strip()
            off_days_txt = form.get("off_days", "").strip()

            print("[setup] parsed: ssid={}, passwd={}, work_len={}, off_len={}".format(
                len(wifi_ssid), len(wifi_password), len(work_days_txt), len(off_days_txt)))

            if wifi_ssid and wifi_password:
                user_settings["wifi_ssid"] = wifi_ssid
                user_settings["wifi_password"] = wifi_password

                def parse_list(text):
                    rows = []
                    for line in text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split(":", 2)
                        if len(parts) == 3:
                            try:
                                h = int(parts[0])
                                m = int(parts[1])
                                name = parts[2].strip()
                                rows.append([h, m, name])
                            except ValueError:
                                pass
                    return rows

                work_schedule = parse_list(work_days_txt) if work_days_txt else default_work
                off_schedule = parse_list(off_days_txt) if off_days_txt else default_off
                user_settings["work_days"] = work_schedule
                user_settings["off_days"] = off_schedule

                response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\nContent-Length: 68\r\n\r\n<html><body><h2>Saved settings. Rebooting...<br></h2></body></html>"
                try:
                    cl.send(response.encode("utf-8"))
                except:
                    pass
                cl.close()
                print("[setup] settings saved, exiting AP mode")
                break

            else:
                print("[setup] validation failed: ssid empty={}, passwd empty={}".format(
                    not wifi_ssid, not wifi_password))
                response = "HTTP/1.0 400 Bad Request\r\nContent-Type: text/html\r\n\r\n<html><body><h2>Invalid input. Please try again.</h2></body></html>"
                try:
                    cl.send(response.encode("utf-8"))
                except:
                    pass
                cl.close()
                continue

        else:
            response = "HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + html_form
            try:
                cl.send(response.encode("utf-8"))
            except Exception as e:
                print("[setup] send error:", e)
            cl.close()
            continue

    s.close()
    ap.active(False)
    state.ap_mode = False
    return user_settings


def _show_splash(oled, state=None):
    oled.fill(0)
    oled.text("  Daily Planner", 0, 8)

    if state is not None and getattr(state, 'ap_mode', False):
        oled.text("AP:{}".format(state.ap_ssid), 0, 20)
        oled.text("PW:{}".format(state.ap_password), 0, 30)
        if state.ap_client_ip:
            oled.text("Client:{}".format(state.ap_client_ip), 0, 40)
            oled.text("Submitting...", 0, 50)
        else:
            oled.text("Open browser:", 0, 40)
            oled.text("{}".format(state.ap_ip), 0, 50)
    elif state is None or not hasattr(state, 'wifi_status'):
        oled.text("  Syncing time..", 0, 40)
    else:
        wifi = getattr(state, 'wifi_status', 'Unknown')
        ntp = getattr(state, 'ntp_status', 'Unknown')
        server = getattr(state, 'ntp_server', '')

        if not isinstance(wifi, str):
            wifi = str(wifi)
        if not isinstance(ntp, str):
            ntp = str(ntp)
        if not isinstance(server, str):
            server = str(server)

        oled.text("WiFi: {}".format(wifi), 0, 40)
        oled.text("NTP: {}".format(ntp), 0, 50)
        if server:
            oled.text("srv: {}".format(server), 0, 60)

    oled.show()


def _show_ready(oled, state):
    oled.fill(0)
    oled.text("Ready!", 0, 20)
    oled.text(state.time_str(), 48, 36)
    oled.show()


async def _splash_status_updater(oled, state):
    """Refresh splash while waiting for initial NTP sync."""
    while not state.time_synced:
        _show_splash(oled, state)
        await asyncio.sleep(1)


# ── main coroutine ────────────────────────────

async def main():
    # ── hardware init ─────────────────────────
    i2c  = I2C(0, sda=Pin(config.OLED_SDA), scl=Pin(config.OLED_SCL),
               freq=400_000)
    oled = ssd1306.SSD1306_I2C(config.OLED_WIDTH, config.OLED_HEIGHT, i2c)
    _show_splash(oled)

    # ── shared state ──────────────────────────
    state = SharedState()

    # load existing settings (wifi + tasks) from flash
    user_settings = storage.load_settings()
    wifi_ssid = user_settings.get("wifi_ssid", "").strip()
    wifi_password = user_settings.get("wifi_password", "").strip()

    work_days = user_settings.get("work_days", config.WORK_DAYS)
    off_days = user_settings.get("off_days", config.OFF_DAYS)

    # start AP portal if no WiFi credentials
    if not wifi_ssid or not wifi_password:
        _show_splash(oled, state)
        splash_task = asyncio.create_task(_splash_status_updater(oled, state))
        user_settings = run_ap_config_portal(work_days, off_days, state, oled)
        splash_task.cancel()
        if user_settings:
            storage.save_settings(user_settings)
            wifi_ssid = user_settings.get("wifi_ssid", "").strip()
            wifi_password = user_settings.get("wifi_password", "").strip()
            work_days = user_settings.get("work_days", work_days)
            off_days = user_settings.get("off_days", off_days)

    # set schedules from user settings or fallback defaults
    state.work_days = work_days
    state.off_days = off_days

    _show_splash(oled, state)

    # ── load persisted data ───────────────────
    storage.load_day_override(state)

    # ── NTP sync (blocking until success or 3 retries) ──
    keeper = TimeKeeper(state, wifi_ssid, wifi_password)
    splash_task = asyncio.create_task(_splash_status_updater(oled, state))
    await keeper.sync_time()
    splash_task.cancel()

    # now that we have a valid date, load today's completions
    storage.load_completions(state)

    _show_ready(oled, state)
    await asyncio.sleep_ms(800)

    # ── instantiate all tasks ─────────────────
    scheduler = EventScheduler(state)
    sensor    = SensorReader(state)
    input_h   = InputHandler(state)
    alert     = AlertManager(state)
    display   = DisplayManager(state)

    # ── schedule all coroutines ───────────────
    asyncio.create_task(keeper.run())
    asyncio.create_task(scheduler.run())
    asyncio.create_task(sensor.run())
    asyncio.create_task(input_h.run())
    asyncio.create_task(alert.run())
    asyncio.create_task(display.run())

    print("[main] all tasks running")

    # ── keep-alive: midnight reset ────────────
    while True:
        await asyncio.sleep(60)
        # reset completed tasks at midnight
        if state.hour == 0 and state.minute == 0 and state.second < 60:
            print("[main] midnight reset")
            state.completions  = {}
            state.day_override = None
            storage.save_day_override(state)


# ── entry point ───────────────────────────────

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("[main] interrupted")
except Exception as e:
    import sys
    print("[main] fatal:", e)
    sys.print_exception(e)
    # reboot after crash to avoid bricking the device
    machine.reset()
