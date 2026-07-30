"""READINESS #11 — Twilio inbound signature validation (STOP must reach us).

THE BUG THIS EXISTS FOR: /sms/inbound parsed its POST body with parse_qs(), which drops
blank values by default. Twilio signs over EVERY parameter it sends, and for toll-free
numbers it routinely sends the geo fields (FromCity/FromState/FromZip/ToCity/ToState/ToZip)
as empty strings. Our signed string therefore omitted those keys while Twilio's included
them, so the HMAC never matched and EVERY genuine inbound text was rejected with 403.

Why that is severe rather than cosmetic: inbound is how STOP reaches us. A rejected
request means sms_apply_inbound() is never called, the opt-out is never recorded, and
texts keep going to someone who explicitly asked us to stop. That is a TCPA violation
with per-message statutory damages.

This test drives the REAL server over a real socket — the actual Handler, the actual
parse, the actual _twilio_verify — because the defect lived in the parsing step. A test
that reimplemented the parsing, or that used only non-blank parameters, would pass
against the broken code and prove nothing.
"""
import os, sys, json, base64, hmac, hashlib, tempfile, threading, time
import urllib.request, urllib.error
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer

TOKEN = "test_auth_token_0123456789abcd"     # stand-in; never a real credential


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "sig.db")
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()
    app.TWILIO_TOKEN = TOKEN          # gate is the token, not SMS_ENABLED
    app.SMS_LIVE = False              # pre-approval: validate + record, send nothing

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def sign(pairs):
        """Sign exactly the way Twilio does: over the CONFIGURED url + every param sent."""
        s = app.BASE_URL + "/sms/inbound" + "".join(k + v for k, v in sorted(pairs))
        return base64.b64encode(
            hmac.new(TOKEN.encode(), s.encode(), hashlib.sha1).digest()).decode()

    def post(pairs, sig):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/sms/inbound",
            data=urlencode(pairs).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "X-Twilio-Signature": sig})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")

    def payload(body, sid="SM_test_1"):
        """A realistic toll-free inbound. The empty geo fields are the whole point:
        Twilio really does send these blank, and they are inside the signature."""
        return [
            ("ToCountry", "US"), ("ToState", ""), ("SmsMessageSid", sid),
            ("NumMedia", "0"), ("ToCity", ""), ("FromZip", ""), ("SmsSid", sid),
            ("FromState", ""), ("SmsStatus", "received"), ("FromCity", ""),
            ("Body", body), ("FromCountry", "US"), ("To", "+18556130177"),
            ("ToZip", ""), ("NumSegments", "1"), ("MessageSid", sid),
            ("AccountSid", "AC" + "0" * 32), ("From", "+15551239791"),
            ("ApiVersion", "2010-04-01"),
        ]

    # ---- 1. the regression itself: a genuine signed request WITH blank params ----
    p = payload("HELP")
    blanks = sum(1 for _, v in p if v == "")
    code, _ = post(p, sign(p))
    check(f"genuine Twilio request validates ({blanks} blank params in signature)",
          code == 200, f"got HTTP {code} — blank params are being dropped before verify")

    # ---- 2. still rejects what it should ----
    code, _ = post(payload("HELP"), sign(payload("HELP"))[:-4] + "AAAA")
    check("tampered signature rejected", code == 403, f"got HTTP {code}")

    p2 = payload("STOP")
    forged = list(p2)
    forged[10] = ("Body", "START")                 # sign STOP, then send START
    code, _ = post(forged, sign(p2))
    check("body swapped after signing is rejected", code == 403, f"got HTTP {code}")

    code, _ = post(payload("HELP"), "")
    check("missing signature header rejected", code == 403, f"got HTTP {code}")

    # ---- 3. the consequence that actually matters: STOP records the opt-out ----
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created) "
                  "VALUES('g_sig','sig@umd.edu','t_sig',0)")
        uid = c.execute("SELECT id FROM users WHERE google_sub='g_sig'").fetchone()["id"]
        c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,"
                  "confirmed_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",
                  (uid, "+15551239791", "test wording", "127.0.0.1",
                   time.time(), time.time()))

    def revoked():
        with app.db() as c:
            r = c.execute("SELECT revoked_at FROM sms_consent WHERE user_id=? "
                          "ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
        return r and r["revoked_at"] is not None

    check("consent starts un-revoked", not revoked())
    ps = payload("STOP", sid="SM_stop")
    code, _ = post(ps, sign(ps))
    check("STOP text is accepted (HTTP 200)", code == 200, f"got HTTP {code}")
    check("STOP actually REVOKED consent in the DB", revoked(),
          "opt-out never recorded — texts would keep sending (TCPA exposure)")

    # a phone with no consent record must not blow up the endpoint
    pu = payload("STOP", sid="SM_unknown")
    pu[17] = ("From", "+15550000000")
    code, _ = post(pu, sign(pu))
    check("unknown number STOP handled without error", code == 200, f"got HTTP {code}")

    srv.shutdown()
    p_ = sum(ok for _, ok, _ in results)
    f_ = sum(not ok for _, ok, _ in results)
    return p_, f_, results


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
