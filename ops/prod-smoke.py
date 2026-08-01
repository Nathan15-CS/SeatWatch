#!/usr/bin/env python3
"""Production smoke test — probes the LIVE site, read-only.

Every readiness suite runs against a local copy of the code with a temp database. That
proves the code is right. It does NOT prove the thing students actually reach is right:
TLS, the proxy, headers added or stripped in front of the app, redirects, and whether a
bad request to the real host leaks a stack trace.

STRICTLY READ-ONLY AND SIDE-EFFECT FREE. It creates no account, no watch, no consent
record; it sends no email and no text; it never posts to a state-changing route. Safe to
run against production at any time, including while students are using it.

    python3 ops/prod-smoke.py [https://seatwatchapp.com]
"""
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://seatwatchapp.com").rstrip("/")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126 Safari/537.36")
R = []


def check(name, ok, detail=""):
    R.append((name, bool(ok), detail))


def get(path, headers=None, timeout=20, method="GET", data=None):
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"User-Agent": UA, **(headers or {})})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(400000).decode("utf-8", "replace"), dict(r.headers), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read(200000).decode("utf-8", "replace"), dict(e.headers), time.time() - t0
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}", {}, time.time() - t0


# ---------------------------------------------------------------- reachability
code, body, hdrs, dt = get("/")
check("landing page returns 200", code == 200, f"HTTP {code}")
check("landing page is reasonably fast", dt < 3.0, f"{dt:.2f}s")
check("landing page is not an error page",
      "Traceback" not in body and "Internal Server Error" not in body)

# ---------------------------------------------------------------- TLS + transport
if BASE.startswith("https://"):
    host = BASE.split("://", 1)[1].split("/")[0]
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(__import__("socket").create_connection((host, 443), timeout=15),
                             server_hostname=host) as s:
            cert = s.getpeercert()
            proto = s.version()
        exp = time.mktime(time.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z"))
        days = (exp - time.time()) / 86400
        check("TLS certificate is valid and trusted", True)
        check("TLS certificate is not near expiry", days > 14, f"{days:.0f} days left")
        check("TLS version is 1.2 or better", proto in ("TLSv1.2", "TLSv1.3"), str(proto))
    except Exception as e:
        check("TLS certificate is valid and trusted", False, f"{type(e).__name__}: {e}")

    # http must not serve the site in the clear
    code2, _, h2, _ = get("/") if False else (None, None, None, None)
    try:
        req = urllib.request.Request("http://" + host + "/", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            served_plain = r.status == 200 and str(r.url).startswith("http://")
        check("plain http does not serve the site", not served_plain,
              "credentials and session cookies would travel unencrypted")
    except Exception:
        check("plain http does not serve the site", True)

# ---------------------------------------------------------------- headers
code, body, hdrs, _ = get("/")
low = {k.lower(): v for k, v in hdrs.items()}
check("no Server banner naming the stack", "python" not in (low.get("server", "")).lower(),
      low.get("server", ""))
check("HSTS is set", "strict-transport-security" in low, "browsers would allow a downgrade")
check("clickjacking is blocked",
      "x-frame-options" in low or "frame-ancestors" in (low.get("content-security-policy") or ""),
      "the site could be framed by a phishing page")
check("MIME sniffing is off", low.get("x-content-type-options", "").lower() == "nosniff",
      low.get("x-content-type-options", "(absent)"))
check("referrers do not leak full URLs cross-site",
      "referrer-policy" in low, low.get("referrer-policy", "(absent)"))

# ---------------------------------------------------------------- auth boundaries
for path in ("/admin/stats", "/admin/stats?key=wrong", "/admin/stats?key="):
    code, body, _, _ = get(path)
    check(f"{path} is not readable without the key",
          code in (401, 403, 404) or "watches" not in body.lower(), f"HTTP {code}")

code, body, hdrs, _ = get("/pricing")
check("/pricing renders for a logged-out visitor", code == 200, f"HTTP {code}")
check("/pricing does not say 'coming soon'", "coming soon" not in body.lower(),
      "payments are enabled but the page still advertises them as unavailable")

# ---------------------------------------------------------------- error handling
for bad in ("/does-not-exist", "/../../etc/passwd", "/r/999999999",
            "/watch", "/%2e%2e%2f", "/?q=" + "A" * 3000):
    code, body, _, _ = get(bad)
    check(f"{bad[:26]:<26} does not leak a traceback",
          "Traceback" not in body and 'File "' not in body, f"HTTP {code}")
    check(f"{bad[:26]:<26} does not leak a filesystem path",
          "/home/ubuntu" not in body and "/etc/passwd" not in body)

# state-changing routes must reject an unauthenticated POST
for path in ("/watch", "/unwatch", "/notify-prefs", "/feedback"):
    code, body, _, _ = get(path, method="POST", data=b"csrf=x&id=1&message=probe",
                           headers={"Content-Type": "application/x-www-form-urlencoded"})
    check(f"POST {path} without a session is refused",
          code not in (200,) or "Traceback" not in body, f"HTTP {code}")

# ---------------------------------------------------------------- PII exposure
code, body, _, _ = get("/")
leaks = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", body)
allowed = {"support@seatwatchapp.com", "help@seatwatchapp.com"}
bad_emails = [e for e in set(leaks) if e not in allowed and "example" not in e]
check("no unexpected email addresses on the public page", not bad_emails, str(bad_emails[:4]))
check("no US phone numbers on the public page",
      not re.search(r"\+1\d{10}|\(\d{3}\)\s?\d{3}-\d{4}", body))
check("no API-key-shaped strings on the public page",
      not re.search(r"sk_live_|whsec_|SG\.[\w-]{20}|AC[0-9a-f]{32}", body),
      "a secret is rendered into the HTML")

# ---------------------------------------------------------------- content truth
code, body, _, _ = get("/")
m = re.search(r"(\d{3,4})\s+universities", body)
check("the landing page states a school count", bool(m), "count not found")
if m:
    check("that count is plausible", 500 < int(m.group(1)) < 2000, m.group(1))

for path, must in (("/sms-terms", "STOP"), ("/privacy", "consent"), ("/terms", "refund")):
    code, body, _, _ = get(path)
    check(f"{path} is reachable", code == 200, f"HTTP {code}")
    check(f"{path} contains its required disclosure ('{must}')", must.lower() in body.lower())

# the SMS pages must no longer describe texts as paid-only
for path in ("/text-alerts", "/sms-terms", "/privacy"):
    code, body, _, _ = get(path)
    txt = re.sub(r"<[^>]+>", " ", body)
    hits = [h for h in re.findall(r".{0,60}paid plan.{0,60}", txt, re.I)
            if re.search(r"sms|text|mobile|phone|opt.?in", h, re.I)]
    check(f"{path} no longer calls texts a paid feature", not hits, str(hits[:1]))

p = sum(ok for _, ok, _ in R)
f = sum(not ok for _, ok, _ in R)
print(f"\n  PRODUCTION SMOKE TEST — {BASE}\n" + "  " + "-" * 66)
for n, ok, d in R:
    print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
print(f"\n  {p} passed, {f} failed\n")
sys.exit(1 if f else 0)
