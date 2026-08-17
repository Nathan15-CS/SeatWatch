"""READINESS #29 — the Meta Pixel measures an activated NEW USER, and leaks nothing.

Two ways a conversion pixel goes wrong, and both are invisible on the dashboard:

  IT OVER-COUNTS. One student adding four classes reports as four acquisitions, so
  cost-per-signup reads 4x better than reality and ad spend is optimised against a number
  that is wrong. CompleteRegistration therefore fires at most ONCE PER STUDENT, on their
  first successful watch, enforced by an atomic UPDATE on users.pixel_activated_at —
  exactly one statement can flip a NULL, whatever the browser does.

  IT LEAKS. Meta's Automatic Advanced Matching reads the page's own form fields and sends
  back anything shaped like an email or a phone number. SeatWatch renders BOTH — the
  signed-in address and the SMS opt-in box — so leaving it on would ship precisely the
  identifiers the privacy policy promises never to share. autoConfig=false, set before
  init, is what stops it.

Also asserted: the pixel is OFF unless META_PIXEL_ID is set in the environment (no
hardcoded production id riding along in the source), the disclosure is reachable from
every page the pixel runs on, and the policy does not assert that any particular privacy
statute applies to SeatWatch.
"""
import os
import re
import sys
import tempfile


def run():
    os.environ["SEATWATCH_DB"] = os.path.join(tempfile.mkdtemp(), "pixel.db")
    os.environ["META_PIXEL_ID"] = "1062384542870956"      # production sets this explicitly
    sys.path.insert(0, os.path.expanduser("~/seatwatch"))
    import app
    app.init_db()

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    src = open(os.path.expanduser("~/seatwatch/app.py")).read()
    BASE, CONV, PID = "connect.facebook.net/en_US/fbevents.js", "CompleteRegistration", app.META_PIXEL_ID

    def mkuser(sub, email, topic):
        with app.db() as c:
            c.execute("INSERT INTO users(google_sub,email,topic,created) VALUES(?,?,?,0)",
                      (sub, email, topic))
            return c.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
    u = mkuser("g_px", "px@umd.edu", "t_px")

    # ------------------------------------------------------------------ DEFAULT OFF
    check("the source carries NO hardcoded production pixel id",
          'os.getenv("META_PIXEL_ID", "")' in src and '"META_PIXEL_ID", "1062' not in src,
          "a default in code follows every copy of this repo to every environment")

    # --------------------------------------------------------- ADVANCED MATCHING OFF
    check("Automatic Advanced Matching is explicitly disabled",
          "fbq('set','autoConfig',false" in app.META_PIXEL_BASE,
          "left on, Meta's script harvests the email and phone fields on our own pages")
    check("...and it is set BEFORE init",
          app.META_PIXEL_BASE.index("autoConfig") < app.META_PIXEL_BASE.index("fbq('init'"),
          "after init the first PageView has already been sent")

    # ------------------------------------------------------------------- PLACEMENT
    landing, form = app.landing_page(), app.form_page(user=u)
    check("base pixel loads on the logged-out landing page", BASE in landing)
    check("base pixel loads on signed-in pages", BASE in form)
    check("the landing page does NOT fire the conversion", CONV not in landing)
    check("the watch form does NOT fire it", CONV not in form)
    check("a REJECTED submission fires nothing",
          CONV not in app.form_page("<div class='err'><span>bad code</span></div>", user=u),
          "a bad course code or a plan limit must never count as a signup")

    # ------------------------------------------- ACTIVATION: once per STUDENT, ever
    first = app.done_page("CMSC250 0101 @ University of Maryland", u)
    check("brand-new student's FIRST watch fires exactly ONE event",
          first.count(CONV) == 1, f"{first.count(CONV)} occurrences")
    check("...the same student's SECOND watch fires NOTHING",
          CONV not in app.done_page("CMSC132 0201 @ University of Maryland", u),
          "four classes from one student is one acquisition, not four")
    check("...and re-rendering their first success page fires nothing",
          CONV not in app.done_page("CMSC250 0101 @ University of Maryland", u),
          "refresh, Back and a replayed flash cookie all land on this page again")
    with app.db() as c:
        stamp = c.execute("SELECT pixel_activated_at FROM users WHERE id=?",
                          (u["id"],)).fetchone()[0]
    check("...and they are stamped as activated", stamp is not None)

    # THE MIGRATION CASE. A student who has been watching classes since before the column
    # existed: row present, pixel_activated_at NULL, and a watch already on file. Without
    # the backfill their next watch flips that NULL and reports a months-old account to
    # Meta as a fresh acquisition. Reproduced exactly, then init_db() is re-run the way a
    # deploy re-runs it.
    old_u = mkuser("g_old", "old@umd.edu", "t_old")
    with app.db() as c:
        c.execute("INSERT INTO watches(school,topic,course,section,term,created,user_id) "
                  "VALUES('umd',?,'CMSC216','0101','202608',?,?)",
                  (old_u["topic"], 1_000_000.0, old_u["id"]))
        c.execute("UPDATE users SET pixel_activated_at=NULL WHERE id=?", (old_u["id"],))
    app.init_db()                       # a deploy restart runs the migration again
    with app.db() as c:
        back = c.execute("SELECT pixel_activated_at FROM users WHERE id=?",
                         (old_u["id"],)).fetchone()[0]
        old_u = c.execute("SELECT * FROM users WHERE google_sub='g_old'").fetchone()
    check("BACKFILL stamps an existing student who already has a watch", back is not None,
          "their column arrived NULL; their next watch would have looked like a signup")
    check("...with the time of their FIRST watch, not the time of the migration",
          back == 1_000_000.0, f"got {back}")
    check("EXISTING student with an old watch creating another fires NOTHING",
          CONV not in app.done_page("CHEM271 0101 @ University of Maryland", old_u),
          "this is the regression the backfill exists to prevent")

    # Idempotent: running it again must not move a stamp or touch anyone new.
    with app.db() as c:
        before = c.execute("SELECT id,pixel_activated_at FROM users ORDER BY id").fetchall()
    app.init_db(); app.init_db()
    with app.db() as c:
        after = c.execute("SELECT id,pixel_activated_at FROM users ORDER BY id").fetchall()
    check("the backfill is idempotent across repeated restarts",
          [tuple(r) for r in before] == [tuple(r) for r in after],
          "init_db runs on every boot; a second pass must be a no-op")

    # A signed-up student who never created a watch must still convert on their real first.
    never = mkuser("g_never", "never@umd.edu", "t_never")
    app.init_db()
    with app.db() as c:
        n_stamp = c.execute("SELECT pixel_activated_at FROM users WHERE id=?",
                            (never["id"],)).fetchone()[0]
    check("a student with NO watches is left unstamped by the backfill", n_stamp is None,
          "they have not activated yet; their genuine first watch must still count")
    check("...and their genuine first watch DOES fire", CONV in app.done_page("X 1 @ Y", never))

    # ------------------------------------------------------------------- NO LEAKS
    # Item 4, asserted rather than asserted-about: scan every rendered page for the actual
    # values, and scan the event call for parameters of any kind.
    leaky = mkuser("g_leak", "leaky.student@terpmail.umd.edu", "t_leak")
    with app.db() as c:
        c.execute("UPDATE users SET phone_e164=? WHERE id=?", ("+15551234567", leaky["id"])) \
            if "phone_e164" in [r[1] for r in c.execute("PRAGMA table_info(users)")] else None
        leaky = c.execute("SELECT * FROM users WHERE google_sub='g_leak'").fetchone()
    page = app.done_page("CMSC250 0101 @ University of Maryland", leaky)
    script = "".join(re.findall(r"fbq\([^)]*\)", page))
    for label, needle in (("email address", "leaky.student@terpmail.umd.edu"),
                          ("phone number", "5551234567"),
                          ("school name", "University of Maryland"),
                          ("course code", "CMSC250"),
                          ("section", "0101")):
        check(f"no {label} in any fbq() call", needle not in script,
              f"found {needle!r} in: {script[:120]}")
    check("the conversion call carries NO parameters at all",
          re.search(r"fbq\('track','CompleteRegistration'\)", script) is not None,
          f"expected a bare call, got: {script[:160]}")
    check("no eventID derived from identity or watch text", "eventID" not in page,
          "pixel-only tracking has nothing to deduplicate against; the DB guard is the rule")
    check("the tracked URL is the bare site root, carrying no watch details",
          '"Location", "/"' in src,
          "a redirect like /?course=CMSC250 would hand Meta the class in the page address")

    # --------------------------------------------------------------- DISCLOSURE
    priv = app.PRIVACY if hasattr(app, "PRIVACY") else src
    check("the policy names the Meta Pixel", "Meta Pixel" in priv)
    check("...states the purpose (measurement AND ad targeting)",
          "measure" in priv and ("target" in priv or "optimise" in priv))
    check("...states that automatic matching is switched off",
          "automatic matching" in priv.lower())
    check("...gives an opt-out", "Off-Facebook activity" in priv and "opt out" in priv.lower())
    check("...no longer promises we never share for advertising",
          "share your data for advertising. Ever." not in priv)
    check("...no longer claims no cross-site tracking",
          "&ldquo;fingerprinting&rdquo; or cross-site tracking" not in priv)

    # Item 1: describe the choice offered, never assert which statutes bind the business.
    check("the policy does NOT assert that the CCPA/CPRA applies to SeatWatch",
          "Under California law this counts" not in priv
          and "as the law requires" not in priv,
          "SeatWatch is nowhere near the CCPA thresholds; claiming coverage invents an "
          "obligation and misstates the law")
    check("...and offers California rights 'where applicable'",
          "Where these rights apply to you" in priv,
          "the rights are offered to anyone who asks, without a claim about coverage")

    # ------------------------------------------------- REACHABLE WHERE IT RUNS
    check("a 'Privacy & Ad Choices' link appears on signed-in pages",
          "/privacy#adchoices" in form)
    check("...and on the logged-out landing page", "/privacy#adchoices" in landing,
          "Meta Business Tools requires the disclosure wherever the tool runs")
    check("...and the anchor it points at exists", 'id="adchoices"' in priv)

    # --------------------------------------------------------------- OFF SWITCH
    keep = (app.META_PIXEL_ID, app.META_PIXEL_BASE)
    app.META_PIXEL_ID, app.META_PIXEL_BASE = "", ""
    off = mkuser("g_off", "off@umd.edu", "t_off")
    check("unset META_PIXEL_ID removes the pixel everywhere",
          BASE not in app.form_page(user=off) and CONV not in app.done_page("X 1 @ Y", off))
    with app.db() as c:
        stamped_off = c.execute("SELECT pixel_activated_at FROM users WHERE id=?",
                                (off["id"],)).fetchone()[0] is not None
    # Deliberately the opposite of what an earlier draft asserted. Activation is a fact
    # about the product — "when did this student first create a watch" — so it is recorded
    # whether or not advertising happens to be switched on, and the pixel merely READS it.
    # Recording it only while the pixel is live leaves a hole: anyone who activates during
    # a pixel-off window keeps a NULL, and their SECOND watch reports later as a first.
    check("...but activation is STILL recorded, so nobody can false-fire later",
          stamped_off,
          "a student who activates while the pixel is off must not look brand new when "
          "it is turned back on")
    app.META_PIXEL_ID, app.META_PIXEL_BASE = keep

    p = sum(x for _, x, _ in results)
    f = sum(not x for _, x, _ in results)
    return p, f, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
