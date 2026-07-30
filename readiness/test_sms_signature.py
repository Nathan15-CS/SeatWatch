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

    # ---- 4. CARRIER-LEVEL STOP self-heal (the path Twilio never forwards) -------------
    # Twilio intercepts the reserved keywords on toll-free: an exact "STOP" is answered by
    # Twilio itself and NEVER reaches our webhook, so section 3 above can't fire for it.
    # The student is genuinely protected (Twilio refuses delivery), but our sms_consent
    # row would still claim active consent. The send path is the only place reality gets
    # back to us: Twilio returns 21610 "attempt to send to unsubscribed recipient", and
    # send_sms writes the revocation at that moment. That code exists but had never been
    # executed — SMS is dormant — so this proves it actually works rather than merely
    # being present.
    app.PAID_ENABLED = True                       # effective_tier gates on this
    app.SMS_LIVE = True                           # exercise the real send path
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created,plan_tier,"
                  "plan_purchased_at) VALUES('g_stop','stop@umd.edu','t_stop',0,1,?)",
                  (time.time(),))
        u2 = c.execute("SELECT id FROM users WHERE google_sub='g_stop'").fetchone()["id"]
        c.execute("INSERT INTO sms_consent(user_id,phone,wording,ip,requested_at,"
                  "confirmed_at,revoked_at) VALUES(?,?,?,?,?,?,NULL)",
                  (u2, "+15557654321", "w", "127.0.0.1", time.time(), time.time()))
        c.execute("INSERT INTO watches(school,topic,course,section,term,alerted,created) "
                  "VALUES('umd','t_stop','CHEM231','0101','202608',0,?)", (time.time(),))
        w = c.execute("SELECT * FROM watches WHERE topic='t_stop'").fetchone()

    row = dict(w); row["user_id"] = u2
    class R(dict):                                 # sqlite3.Row-alike for send_sms
        def keys(self): return list(super().keys())
    r = R(row)

    check("consent active before any send", app._sms_phone(u2) == "+15557654321")

    sent_box = []
    app._twilio_post = lambda to, body: (sent_box.append(to), (False, 21610))[1]
    accepted = app.send_sms(u2, r, "CHEM231-0101 has 2 seats open.", "https://x.test/reg")

    with app.db() as c:
        rev = c.execute("SELECT revoked_at FROM sms_consent WHERE user_id=?",
                        (u2,)).fetchone()["revoked_at"]
    check("21610 send is reported as NOT delivered", accepted is False)
    check("carrier-level STOP revokes consent in our DB", rev is not None,
          "our records would keep claiming consent the student already withdrew")
    check("revoked number no longer resolves for sending", app._sms_phone(u2) is None,
          "we would keep attempting a number Twilio refuses")

    # a normal failure must NOT be mistaken for an opt-out
    with app.db() as c:
        c.execute("UPDATE sms_consent SET revoked_at=NULL WHERE user_id=?", (u2,))
        c.execute("DELETE FROM alert_log WHERE user_id=?", (u2,))
    app._twilio_post = lambda to, body: (False, 30034)      # unregistered sender
    app.send_sms(u2, r, "CHEM231-0101 has 2 seats open.", "https://x.test/reg")
    with app.db() as c:
        rev2 = c.execute("SELECT revoked_at FROM sms_consent WHERE user_id=?",
                         (u2,)).fetchone()["revoked_at"]
    check("a non-optout Twilio error does NOT revoke consent", rev2 is None,
          "an unrelated send failure would silently destroy a valid consent record")

    # ---- 5. CONSENT must come from a real ticked box, not a present-but-empty field ----
    # /sms/optin used to test `not oform.get("sms_consent")`, which inspects the LIST that
    # parse_qs returns. An empty `sms_consent=` is dropped today, so it was safe by side
    # effect of parsing -- but the Twilio fix above needs keep_blank_values, and the moment
    # anyone applies that flag here `['']` becomes truthy and an empty field reads as
    # consent. These assert the OUTCOME, so they keep holding either way. A consent record
    # with no consent behind it is the one TCPA record we could never defend.
    # paid tier: /sms/optin gates on effective_tier >= 1 BEFORE it reaches the consent check
    with app.db() as c:
        c.execute("INSERT INTO users(google_sub,email,topic,created,plan_tier,"
                  "plan_purchased_at) VALUES('g_opt','opt@umd.edu','t_opt',0,1,?)",
                  (time.time(),))
        uid3 = c.execute("SELECT id FROM users WHERE google_sub='g_opt'").fetchone()["id"]
    cookie = app.session_cookie(uid3).split(";")[0]
    csrf = app.csrf_token(uid3)

    def optin(consent_field):
        body = urlencode([("csrf", csrf), ("phone", "+15551112222")] + consent_field)
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/sms/optin", data=body.encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.read().decode("utf-8", "replace")

    def consented():
        with app.db() as c:
            return c.execute("SELECT COUNT(*) FROM sms_consent WHERE user_id=?",
                             (uid3,)).fetchone()[0]

    html_ = optin([("sms_consent", "")])
    check("empty sms_consent= is refused", "consent box" in html_ and consented() == 0,
          "an empty field was accepted as consent")
    html_ = optin([("sms_consent", "   ")])
    check("whitespace-only consent is refused", "consent box" in html_ and consented() == 0,
          "whitespace was accepted as consent")
    html_ = optin([])
    check("missing consent field is refused", "consent box" in html_ and consented() == 0)
    html_ = optin([("sms_consent", "on")])
    check("a genuinely ticked box IS accepted", consented() == 1,
          "the real opt-in path broke")

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
