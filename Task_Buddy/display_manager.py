# ─────────────────────────────────────────────
#  display_manager.py  —  UI state machine + renderer
# ─────────────────────────────────────────────
# Owns the SSD1306 exclusively.
# Consumes state.input_queue to drive navigation.
# Renders at FPS = 5.
#
# Screens:
#   HOME     — clock, current event, countdown, temp/humidity
#   DAY      — scrollable event list with completion checkboxes
#   DETAIL   — single event with toggle
#   QUOTE    — quote of the day / random quote
#   SETTINGS — work/off day override toggle

import uasyncio as asyncio
import machine
from machine import I2C, Pin
import ssd1306
import time
import config
import storage
import quotes
from state import (
    SCREEN_HOME, SCREEN_DAY, SCREEN_DETAIL, SCREEN_QUOTE, SCREEN_SETTINGS,
    EVT_UP, EVT_DOWN, EVT_SELECT, EVT_SELECT_LONG, EVT_RESET
)

# SSD1306 is 128×64 with 8×8 pixel font
# Rows at y=0,10,20,30,40,50 give 6 usable lines (slight overlap at 10px)
# We use y spacing of 11px for tighter packing


class DisplayManager:
    def __init__(self, state):
        self.state = state
        i2c  = I2C(0, sda=Pin(config.OLED_SDA), scl=Pin(config.OLED_SCL),
                   freq=400_000)
        self.oled = ssd1306.SSD1306_I2C(
            config.OLED_WIDTH, config.OLED_HEIGHT, i2c)
        self.oled.fill(0)
        self.oled.show()

    # ── main loop ─────────────────────────────

    async def run(self):
        interval_ms = 1000 // config.FPS
        while True:
            # drain all queued inputs before redrawing
            await self._process_inputs()
            self._render()
            await asyncio.sleep_ms(interval_ms)

    # ── input routing ─────────────────────────

    async def _process_inputs(self):
        q = self.state.input_queue
        while not q.empty():
            try:
                evt = q.get_nowait()
                self._handle_event(evt)
            except Exception:
                break

    def _handle_event(self, evt):
        s  = self.state
        sc = s.screen

        if sc == SCREEN_HOME:
            if evt == EVT_UP:
                s.quote_idx = -1   # reset so quote_of_day is shown first
                s.screen = SCREEN_QUOTE
            elif evt == EVT_DOWN:
                s.day_view_cursor = 0
                s.screen = SCREEN_DAY
            elif evt == EVT_SELECT_LONG:
                s.screen = SCREEN_SETTINGS

        elif sc == SCREEN_DAY:
            max_idx = len(s.schedule) - 1
            if evt == EVT_UP:
                s.day_view_cursor = max(0, s.day_view_cursor - 1)
            elif evt == EVT_DOWN:
                s.day_view_cursor = min(max_idx, s.day_view_cursor + 1)
            elif evt == EVT_SELECT:
                s.detail_idx = s.day_view_cursor
                s.screen = SCREEN_DETAIL
            elif evt == EVT_SELECT_LONG:
                s.screen = SCREEN_HOME

        elif sc == SCREEN_DETAIL:
            if evt == EVT_SELECT:
                _, _, name = s.schedule[s.detail_idx]
                storage.toggle_completion(s, name)
            elif evt == EVT_UP:
                s.screen = SCREEN_DAY
            elif evt == EVT_SELECT_LONG:
                s.screen = SCREEN_HOME

        elif sc == SCREEN_QUOTE:
            if evt == EVT_DOWN:
                # cycle to a different random quote
                s.quote_idx, _, _ = quotes.random_quote(
                    exclude_idx=s.quote_idx)
            elif evt in (EVT_SELECT, EVT_SELECT_LONG, EVT_UP):
                s.screen = SCREEN_HOME

        elif sc == SCREEN_SETTINGS:
            # UP / DOWN toggle override
            if evt in (EVT_UP, EVT_DOWN):
                if s.day_override is None:
                    s.day_override = not s.is_work_day   # flip from auto
                else:
                    s.day_override = not s.day_override
                storage.save_day_override(s)
            elif evt == EVT_SELECT:
                # clear override → auto detect
                s.day_override = None
                storage.save_day_override(s)
            elif evt == EVT_RESET:
                # reset onboarding credentials and schedules (UP+DOWN simultaneous)
                storage.save_settings({})
                s.work_days = []
                s.off_days = []
                s.day_override = None
                s.ap_mode = False
                # force reboot to start AP flow on next boot
                machine.reset()
            elif evt == EVT_SELECT_LONG:
                # go back to home
                s.screen = SCREEN_HOME

        s.needs_redraw = True

    # ── render dispatcher ─────────────────────

    def _render(self):
        s = self.state
        if not s.needs_redraw:
            return
        self.oled.fill(0)
        {
            SCREEN_HOME:     self._draw_home,
            SCREEN_DAY:      self._draw_day,
            SCREEN_DETAIL:   self._draw_detail,
            SCREEN_QUOTE:    self._draw_quote,
            SCREEN_SETTINGS: self._draw_settings,
        }.get(s.screen, self._draw_home)()
        self.oled.show()
        s.needs_redraw = False

    # ── screen renderers ──────────────────────

    def _draw_home(self):
        s   = self.state
        oled = self.oled

        # row 0: date + time  (y=0)
        date_time = "{} {}".format(s.date_str(), s.time_str())
        oled.text(date_time, 0, 0)

        # divider
        oled.hline(0, 10, 128, 1)

        # row 1: current event (large — doubled)
        evt_name = s.current_event[:10]   # truncate for safety
        self._big_text(evt_name, 0, 16)

        # row 2: next event + countdown  (y=36)
        if s.next_idx >= 0:
            nxt = s.next_event[:8]
            countdown = s.countdown_str()
            oled.text(">" + nxt, 0, 36)
            oled.text(countdown, 128 - len(countdown) * 8, 36)

        # divider
        oled.hline(0, 47, 128, 1)

        # row 3: temp / humidity  (y=50)
        if s.temperature is not None:
            sensor_str = "{:.0f}C {:.0f}%".format(
                s.temperature, s.humidity)
        else:
            sensor_str = "-- C --%"
        oled.text(sensor_str, 0, 53)

    def _draw_day(self):
        s    = self.state
        oled = self.oled

        # header
        oled.text("Tasks " + ("W" if s.is_work_day else "O"), 0, 0)
        oled.hline(0, 10, 128, 1)

        # visible window: 4 rows starting at cursor - offset
        visible = 4
        start   = max(0, s.day_view_cursor - visible + 1)
        start   = min(start, max(0, len(s.schedule) - visible))

        for i in range(visible):
            idx = start + i
            if idx >= len(s.schedule):
                break
            h, m, name = s.schedule[idx]
            done  = s.completions.get(name, False)
            check = "[x]" if done else "[ ]"
            time_str = "{:02d}:{:02d}".format(h, m)
            row   = "{} {} {}".format(check, time_str, name[:7])
            y     = 16 + i * 12
            if idx == s.day_view_cursor:
                # highlight selected row
                oled.fill_rect(0, y - 1, 128, 11, 1)
                oled.text(row, 0, y, 0)   # black text on white bg
            else:
                oled.text(row, 0, y)

    def _draw_detail(self):
        s    = self.state
        oled = self.oled
        idx  = s.detail_idx

        if idx >= len(s.schedule):
            s.screen = SCREEN_DAY
            return

        h, m, name = s.schedule[idx]
        done = s.completions.get(name, False)

        oled.text("Event detail", 0, 0)
        oled.hline(0, 10, 128, 1)

        # event name (wrap at 16 chars per line)
        oled.text(name[:16], 0, 16)
        if len(name) > 16:
            oled.text(name[16:32], 0, 25)

        oled.text("{:02d}:{:02d}".format(h, m), 0, 38)

        status = "[DONE]" if done else "[TODO]"
        oled.text(status, 0, 50)
        oled.text("SEL=toggle UP=back", 0, 57)

    def _draw_quote(self):
        s    = self.state
        oled = self.oled

        if s.quote_idx < 0:
            # show quote of the day
            text, author = quotes.quote_of_the_day(s)
            label = "Quote of the day"
        else:
            _, text, author = quotes.random_quote.__func__(s.quote_idx) \
                if False else (None, None, None)  # placeholder
            # resolve properly:
            text   = quotes.QUOTES[s.quote_idx][0]
            author = quotes.QUOTES[s.quote_idx][1]
            label  = "Random quote"

        oled.text(label, 0, 0)
        oled.hline(0, 10, 128, 1)

        # word-wrap the quote into 16-char lines
        lines = self._wrap(text, 16)
        for i, line in enumerate(lines[:4]):
            oled.text(line, 0, 16 + i * 11)

        if author:
            oled.text("- " + author[:14], 0, 57)
        else:
            oled.text("DN=next SEL=back", 0, 57)

    def _draw_settings(self):
        s    = self.state
        oled = self.oled

        oled.text("Settings", 0, 0)
        oled.hline(0, 10, 128, 1)

        # day type override
        if s.day_override is None:
            mode = "Auto (" + ("Work" if s.is_work_day else "Off") + ")"
        else:
            mode = "Manual: " + ("Work" if s.day_override else "Off")

        oled.text("Day type:", 0, 16)
        oled.text(mode[:16], 0, 26)

        # alarm status
        alarm_str = "Alarm: " + ("ON" if s.alarm_armed else "OFF")
        oled.text(alarm_str, 0, 38)

        oled.text("SEL=auto", 0, 50)
        oled.text("UP+DN=reset", 0, 58)

    # ── helpers ───────────────────────────────

    def _big_text(self, text, x, y):
        """Draw 2× scaled text using manual pixel doubling via framebuf."""
        import framebuf
        # render to a small 1-bit buffer at normal size, then double
        w   = len(text) * 8
        buf = bytearray(w)
        fb  = framebuf.FrameBuffer(buf, w, 8, framebuf.MONO_VLSB)
        fb.fill(0)
        fb.text(text, 0, 0, 1)
        # blit pixels at 2× scale
        for row in range(8):
            for col in range(w):
                byte_idx = col
                if buf[byte_idx] & (1 << row):
                    # draw a 2×2 block
                    self.oled.pixel(x + col * 2,     y + row * 2,     1)
                    self.oled.pixel(x + col * 2 + 1, y + row * 2,     1)
                    self.oled.pixel(x + col * 2,     y + row * 2 + 1, 1)
                    self.oled.pixel(x + col * 2 + 1, y + row * 2 + 1, 1)

    @staticmethod
    def _wrap(text, width):
        """Simple word-wrap into lines of ≤ width chars."""
        words  = text.split()
        lines  = []
        line   = ""
        for word in words:
            if len(line) + len(word) + (1 if line else 0) <= width:
                line = (line + " " + word).strip()
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines
