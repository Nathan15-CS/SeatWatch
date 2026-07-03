#!/usr/bin/env python3
"""
SeatWatch — production engine (UMD / Testudo).

Design principles (earned the hard way):
  1. LIVE DATA ONLY. We poll Testudo's Schedule of Classes directly — never a
     cached third party (umd.io was shown to be stale and would have produced
     false "seat open" alerts). Trust is the product.
  2. NEVER SEND FALSE DATA. If a fetch fails or a page doesn't parse cleanly,
     we SKIP that cycle and log it. We never assume "full" or "open" from bad
     data, and we never notify on anything we didn't truly observe.
  3. CATCH THE MAJORITY, BE HONEST ABOUT THE REST. Fast, focused polling +
     reliable delivery. We do not promise "foolproof."
  4. RELIABLE DELIVERY. Notifications go out via ntfy (instant phone push) with
     retries; an opening is announced once per open-episode (no spam, no misses).

Notifications: free, no-signup push via https://ntfy.sh
  -> install the "ntfy" app (iOS/Android), subscribe to your NTFY_TOPIC below,
     and you'll get an instant push the moment a seat opens (tap it to register).
"""

import json
import os
import random
import re
import time
import urllib.request
import urllib.error
from datetime import datetime

# ============================ CONFIG (edit me) =============================

# Term code from the Testudo URL: Fall 2026 = 202608, Spring 2026 = 202601, etc.
TERM = "202608"

# Classes to watch.  course -> list of section numbers, or [] to watch ALL sections.
WATCH = {
    "CMSC132": ["0101", "0201"],
    "MATH140": [],          # [] = watch every section
}

# How often to check (seconds). Focused + polite. 15-25s is a good range.
POLL_SECONDS = 20
POLL_JITTER = 5            # +/- random seconds, to look human and spread load

# Your private push channel. KEEP THIS SECRET-ish (anyone who knows it can read
# your alerts). Install the ntfy app and subscribe to exactly this string.
NTFY_TOPIC = "seatwatch-umd-a7f3k9q2x"

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

# ===========================================================================

SOC_URL = "https://app.testudo.umd.edu/soc/{term}/{dept}/{course}"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SeatWatch/1.0"


def log(*a):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def dept_of(course):
    m = re.match(r"^[A-Za-z]+", course)
    return m.group(0).upper() if m else course[:4].upper()


def http_get(url, attempts=3):
    """Fetch with retries + timeout. Returns text, or None on failure (never raises)."""
    for i in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                if r.status != 200:
                    log(f"  [warn] {url} -> HTTP {r.status} (attempt {i})")
                    continue
                return r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            log(f"  [warn] fetch failed ({i}/{attempts}) {url}: {e}")
            time.sleep(1.5 * i)
    return None


def parse_testudo(html):
    """
    Parse a Testudo course page into {section_number: {open,total,waitlist}}.
    Robust: anchors on each section-id, then searches the bounded block after it,
    so it can't mis-pair across sections. Returns {} if nothing parsed.
    """
    out = {}
    for m in re.finditer(r'section-id"[^>]*>\s*([A-Za-z0-9]+)\s*<', html):
        num = m.group(1)
        block = html[m.end():m.end() + 3000]
        om = re.search(r'open-seats-count">\s*(\d+)', block)
        if not om:
            continue  # can't read open seats -> skip, never guess
        tm = re.search(r'total-seats-count">\s*(\d+)', block)
        wm = re.search(r'waitlist-count">\s*(\d+)', block)
        out[num] = {
            "open": int(om.group(1)),
            "total": int(tm.group(1)) if tm else None,
            "waitlist": int(wm.group(1)) if wm else None,
        }
    return out


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)  # atomic


def notify(title, message, click_url=None, topic=None):
    """Instant push via ntfy, with retries. Returns True on success.
    `topic` lets each user get their own private channel (multi-user)."""
    topic = topic or NTFY_TOPIC
    # HTTP headers must be ASCII — strip anything else so a push can NEVER
    # silently fail on encoding. The 🚨 visual comes from the Tags header below.
    safe_title = title.encode("ascii", "ignore").decode().strip() or "SeatWatch alert"
    headers = {
        "Title": safe_title,
        "Priority": "urgent",
        "Tags": "rotating_light",
        "User-Agent": UA,
    }
    if click_url:
        headers["Click"] = click_url
    data = message.encode("utf-8")
    for i in range(1, 4):
        try:
            req = urllib.request.Request(
                f"https://ntfy.sh/{topic}", data=data, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status in (200, 201):
                    return True
        except Exception as e:
            log(f"  [warn] notify failed ({i}/3): {e}")
            time.sleep(1.5 * i)
    return False


def check_once(state):
    """One full pass over all watched courses. Mutates + returns state."""
    for course, want in WATCH.items():
        url = SOC_URL.format(term=TERM, dept=dept_of(course), course=course.upper())
        html = http_get(url)
        if html is None:
            log(f"  [skip] {course}: fetch failed — NOT updating state (no false data)")
            continue
        sections = parse_testudo(html)
        if not sections:
            log(f"  [skip] {course}: parsed 0 sections — page format change? NOT acting")
            continue

        for num, info in sections.items():
            if want and num not in want:
                continue
            sid = f"{course}-{num}"
            openn = info["open"]
            prev = state.get(sid, {})
            was_alerted = prev.get("alerted", False)

            if openn > 0 and not was_alerted:
                wl = info.get("waitlist")
                msg = (f"{openn} seat(s) just opened in {sid}!"
                       + (f" (waitlist: {wl})" if wl else "")
                       + " Tap to register — go now.")
                ok = notify(f"🚨 Seat open: {sid}", msg, click_url=url)
                log(f"  ALERT {sid}: {openn} open  -> push {'sent' if ok else 'FAILED'}")
                state[sid] = {"open": openn, "alerted": True, "ts": time.time()}
            elif openn == 0:
                # full again -> reset so a future reopening re-alerts
                state[sid] = {"open": 0, "alerted": False, "ts": time.time()}
            else:
                state[sid] = {"open": openn, "alerted": was_alerted, "ts": time.time()}
    return state


def main():
    if "CHANGEME" in NTFY_TOPIC:
        log("[!] Set NTFY_TOPIC to your own private string before going live.")
    log(f"SeatWatch live. term={TERM}  poll≈{POLL_SECONDS}s  topic={NTFY_TOPIC}")
    log("Watching: " + ", ".join(
        f"{c}({'ALL' if not s else ','.join(s)})" for c, s in WATCH.items()))
    state = load_state()
    cycle = 0
    while True:
        cycle += 1
        try:
            state = check_once(state)
            save_state(state)
        except Exception as e:
            # never let one bad cycle kill the engine
            log(f"  [error] cycle {cycle} crashed but recovering: {e}")
        wait = max(5, POLL_SECONDS + random.randint(-POLL_JITTER, POLL_JITTER))
        if os.environ.get("WATCH_ITERATIONS") and cycle >= int(os.environ["WATCH_ITERATIONS"]):
            log("done (test mode).")
            break
        log(f"cycle {cycle} ok — next check in {wait}s")
        time.sleep(wait)


if __name__ == "__main__":
    main()
