# ─────────────────────────────────────────────
#  storage.py  —  flash persistence (JSON)
# ─────────────────────────────────────────────
# Completions are stored at /completions.json as:
#   { "2025-04-03": { "Exercise": true, "ML Study": false, ... } }
# Entries older than today are pruned on load to keep the file small.

import ujson
import uos


COMPLETIONS_FILE = "/completions.json"


def _date_key(state):
    return "{:04d}-{:02d}-{:02d}".format(state.year, state.month, state.day)


def _load_raw():
    try:
        with open(COMPLETIONS_FILE, "r") as f:
            return ujson.load(f)
    except (OSError, ValueError):
        return {}


def _save_raw(data):
    try:
        with open(COMPLETIONS_FILE, "w") as f:
            ujson.dump(data, f)
    except OSError as e:
        print("[storage] write error:", e)


def load_completions(state):
    """Load today's completions into state.completions. Prune old dates."""
    today = _date_key(state)
    data  = _load_raw()

    # prune stale dates
    stale = [k for k in data if k != today]
    for k in stale:
        del data[k]

    state.completions = data.get(today, {})

    # persist pruned version
    if stale:
        data[today] = state.completions
        _save_raw(data)

    print("[storage] loaded {} completions for {}".format(
        len(state.completions), today))


def save_completions(state):
    """Persist state.completions to flash."""
    today = _date_key(state)
    data  = _load_raw()
    data[today] = state.completions
    _save_raw(data)


def toggle_completion(state, event_name):
    """Toggle completion for event_name, persist immediately."""
    current = state.completions.get(event_name, False)
    state.completions[event_name] = not current
    save_completions(state)
    return state.completions[event_name]


def save_day_override(state):
    """Persist the work/off day override setting."""
    try:
        with open("/day_override.json", "w") as f:
            ujson.dump({"override": state.day_override}, f)
    except OSError:
        pass


def load_day_override(state):
    """Load override on boot; returns None if not set."""
    try:
        with open("/day_override.json", "r") as f:
            d = ujson.load(f)
            state.day_override = d.get("override", None)
    except (OSError, ValueError):
        state.day_override = None


SETTINGS_FILE = "/settings.json"


def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            return ujson.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            ujson.dump(settings, f)
    except OSError as e:
        print("[storage] settings save error:", e)
