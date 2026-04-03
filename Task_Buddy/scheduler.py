# ─────────────────────────────────────────────
#  scheduler.py  —  event resolution
# ─────────────────────────────────────────────
# Runs every second. Determines:
#   - Whether today is a work day or off day
#   - Which event is currently active (current_idx)
#   - Which event is next (next_idx)
#   - Seconds until the next event (secs_to_next)
#   - Sets state.alert_pending when an event just started

import uasyncio as asyncio
import config


class EventScheduler:
    def __init__(self, state):
        self.state = state
        self._last_notified_idx = -1   # prevents double-alerting

    async def run(self):
        while True:
            self._resolve()
            await asyncio.sleep(1)

    # ── resolution logic ──────────────────────

    def _resolve(self):
        s = self.state

        # ── determine day type ────────────────
        if s.day_override is not None:
            is_work = s.day_override
        else:
            # 0–4 = Mon–Fri = work days
            is_work = s.weekday < 5
        s.is_work_day = is_work
        work_schedule = s.work_days if s.work_days else config.WORK_DAYS
        off_schedule  = s.off_days  if s.off_days  else config.OFF_DAYS
        s.schedule    = work_schedule if is_work else off_schedule

        # ── current time in minutes since midnight ─
        now_min = s.hour * 60 + s.minute
        now_sec = now_min * 60 + s.second

        current_idx = -1
        next_idx    = len(s.schedule)   # sentinel: past last event

        for i, (h, m, _) in enumerate(s.schedule):
            event_min = h * 60 + m
            if event_min <= now_min:
                current_idx = i
            else:
                next_idx = i
                break

        s.current_idx = current_idx
        s.next_idx    = next_idx if next_idx < len(s.schedule) else -1

        # ── countdown to next event ───────────
        if s.next_idx >= 0:
            nh, nm, _ = s.schedule[s.next_idx]
            next_sec   = (nh * 60 + nm) * 60
            s.secs_to_next = max(0, next_sec - now_sec)
        else:
            # all events done for the day — count to midnight
            s.secs_to_next = max(0, 86400 - now_sec)

        # ── fire alert when event first starts ─
        if current_idx >= 0 and current_idx != self._last_notified_idx:
            # only alert if we're within the first 30 s of the event
            h, m, _ = s.schedule[current_idx]
            event_sec = (h * 60 + m) * 60
            if now_sec - event_sec < 30:
                s.alert_pending = True
            self._last_notified_idx = current_idx
