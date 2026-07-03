#!/usr/bin/env python3
"""
SeatWatch — prototype core engine.
Monitors UMD course sections for open seats via the public umd.io API and
fires an alert the instant a watched section goes from full -> open.

This is the heart of the product. Notifications are console-only for now;
SMS/push/email plug in at the ALERT point later.

Run:  python3 watch.py
Test: WATCH_ITERATIONS=2 POLL_SECONDS=4 python3 watch.py   (runs a few cycles then exits)
"""
import json
import os
import time
import urllib.request
from datetime import datetime

# --- what to watch ---------------------------------------------------------
# course_id -> list of section numbers to watch ([] = watch ALL sections)
WATCH = {
    "CMSC131": [],      # watch every section of CMSC131
    "MATH140": ["0101", "0111"],
}

POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "30"))
MAX_ITERATIONS = int(os.environ.get("WATCH_ITERATIONS", "0"))  # 0 = run forever
API = "https://api.umd.io/v1/courses/sections?course_id={}"


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def fetch_sections(course_id):
    url = API.format(course_id)
    req = urllib.request.Request(url, headers={"User-Agent": "SeatWatch/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def notify(section_id, open_seats, info):
    # >>> plug SMS / push / email in here later <<<
    log(f"🚨 SEAT OPENED: {section_id} — {open_seats} open seat(s)!"
        f"  ({info})  -> NOTIFY USER NOW")


def main():
    state = {}  # section_id -> last known open_seats
    log(f"SeatWatch starting. Poll every {POLL_SECONDS}s. Watching: "
        + ", ".join(f"{c}({'all' if not s else ','.join(s)})" for c, s in WATCH.items()))

    iteration = 0
    while True:
        iteration += 1
        checked = 0
        for course_id, sections in WATCH.items():
            try:
                data = fetch_sections(course_id)
            except Exception as e:
                log(f"ERROR fetching {course_id}: {e}")
                continue
            for s in data:
                num = s.get("number")
                if sections and num not in sections:
                    continue
                sid = s["section_id"]
                openn = int(s.get("open_seats", 0))
                total = s.get("seats")
                prev = state.get(sid)
                state[sid] = openn
                checked += 1
                if prev is None:
                    status = "OPEN" if openn > 0 else "FULL"
                    log(f"  watching {sid}: {openn}/{total} open  [{status}]")
                elif prev == 0 and openn > 0:
                    instr = ", ".join(s.get("instructors", []))
                    notify(sid, openn, f"{course_id} with {instr}")
                elif openn != prev:
                    log(f"  {sid}: {prev} -> {openn} open")

        log(f"cycle {iteration} done — {checked} sections checked")
        if MAX_ITERATIONS and iteration >= MAX_ITERATIONS:
            log("done (test mode).")
            break
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
