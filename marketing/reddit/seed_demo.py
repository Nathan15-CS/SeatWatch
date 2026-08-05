#!/usr/bin/env python3
"""End-to-end test run on sample data. Proves the pipeline works AND that the gate bites.

This is deliberately not a happy-path demo. Five of the seven sample drafts are written to
fail, each on a different rule, because a safety system demonstrated only on things it
approves has not been demonstrated at all.

Run:  python3 seed_demo.py           (rebuilds a scratch DB, leaves it for inspection)
      python3 seed_demo.py --keep    (append to whatever is already there)
"""
import os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

if "--keep" not in sys.argv:
    os.environ["REDDIT_MKT_DB"] = os.path.join(HERE, "demo.db")
    if os.path.exists(os.environ["REDDIT_MKT_DB"]):
        os.remove(os.environ["REDDIT_MKT_DB"])

import safety, store  # noqa: E402

DAY = 86400
now = time.time()


def h(t):
    print("\n" + "=" * 74 + "\n  " + t + "\n" + "=" * 74)


store.init()

# ---------------------------------------------------------------- subreddits
h("1. SUBREDDIT FINDER — candidates recorded")
store.add_subreddit("umd", subscribers=180000, school="umd", relevance=0.95,
                    notes="campus sub for a covered school; add/drop threads every term")
store.add_subreddit("berkeley", subscribers=140000, school=None, relevance=0.6,
                    notes="covered school not confirmed")
store.add_subreddit("csmajors", subscribers=400000, school=None, relevance=0.45,
                    notes="major-specific, lower intent")
store.add_subreddit("sideproject", subscribers=250000, school=None, relevance=0.05,
                    notes="upvotes from people who will never register for a class")
for r in store.db().execute("SELECT name, subscribers, status FROM subreddits ORDER BY name"):
    print("   r/%-14s %8s  %s" % (r["name"], r["subscribers"] or "?", r["status"]))

# ---------------------------------------------------------------- rules
h("2. RULES CHECKER — real policies recorded, verbatim")
store.record_rules(
    "umd", "conditional", "https://www.reddit.com/r/UMD/about/rules/",
    promo_conditions="Self-promotion permitted if you are an active member and the post is "
                     "directly relevant to UMD students.",
    min_account_age_days=0, min_comment_karma=0)
print("   r/umd        conditional  -> approved")
store.set_status("umd", "approved", "Rule 5 permits relevant self-promo")

store.record_rules("sideproject", "forbidden", "https://www.reddit.com/r/SideProject/about/rules/",
                   promo_conditions="No link-only promotion.")
store.set_status("sideproject", "blocked", "promo forbidden; also wrong audience")
print("   r/sideproject forbidden   -> blocked (sticky)")

# stale on purpose: recorded 30 days ago
with store.db() as c:
    c.execute("""INSERT INTO subreddit_rules(subreddit,checked_at,self_promo,
        promo_conditions,min_account_age_days,min_comment_karma,mod_permission,source_url)
        VALUES('csmajors',?, 'conditional','Self-promo Saturdays only.',30,100,0,
        'https://www.reddit.com/r/csMajors/about/rules/')""", (now - 30 * DAY,))
store.set_status("csmajors", "approved", "conditional; account minimums apply")
print("   r/csmajors   conditional  -> approved, but rules read 30 days ago (STALE)")
print("   r/berkeley   never read   -> still candidate")

# ---------------------------------------------------------------- opportunities
h("3. OPPORTUNITY FINDER — live threads")
o1 = store.add_opportunity("umd", "comment_reply",
                           target_url="https://reddit.com/r/UMD/comments/aaa",
                           target_title="Waitlisted for CMSC216, does it ever open up?",
                           target_at=now - 5 * 3600, score=0.93,
                           signal="OP: been refreshing Testudo for three days straight")
o2 = store.add_opportunity("umd", "post",
                           target_title="add/drop megathread",
                           target_at=now - 20 * 3600, score=0.7,
                           signal="dozens of 'anyone dropping X' comments")
print("   #%d  r/umd  score 0.93  CMSC216 waitlist, 5h old" % o1)
print("   #%d  r/umd  score 0.70  add/drop megathread" % o2)

# ---------------------------------------------------------------- drafts
h("4. CONTENT WRITER — 7 drafts (1 intended to pass, 6 intended to fail)")

DRAFTS = [
    # --- should PASS
    dict(sub="umd", kind="comment_reply", opp=o1, code="rd-a1b2c3",
         note="answers the OP's actual question first, then discloses",
         body="Three days of refreshing is about where I gave up too. CMSC216 usually turns "
              "over in the first week of classes when people drop after the first project.\n\n"
              "I built a thing after getting shut out of it last spring — it watches the "
              "section and emails you when a seat frees up. Free for one class. "
              "https://seatwatchapp.com/?r=rd-a1b2c3\n\n"
              "It is new, so if you try it tell me whether the email actually reaches you."),

    # --- should FAIL: fabricated testimonial
    dict(sub="umd", kind="post", opp=o2, code="rd-fake01",
         note="INTENDED FAILURE: invented testimonial",
         title="I built a seat watcher for Testudo",
         body="I built a tool that watches for open seats at UMD.\n\n"
              '"Saved my semester." - a student who used it last term. '
              "https://seatwatchapp.com/?r=rd-fake01"),

    # --- should FAIL: invented user count + guarantee
    dict(sub="umd", kind="post", opp=None, code="rd-hype01",
         note="INTENDED FAILURE: unverifiable count and a promise we cannot keep",
         title="Never miss an open seat again",
         body="I made SeatWatch. Thousands of students use it and you will never miss a "
              "seat again, guaranteed. https://seatwatchapp.com/?r=rd-hype01"),

    # --- should FAIL: inflated school count
    dict(sub="umd", kind="post", opp=None, code="rd-count1",
         note="INTENDED FAILURE: claims more schools than the registry has",
         title="Seat alerts for 5000 universities",
         body="I built a seat alert tool that covers 5000 universities including UMD. "
              "https://seatwatchapp.com/?r=rd-count1"),

    # --- should FAIL: SMS claim while the published terms still say paid-only
    dict(sub="umd", kind="post", opp=None, code="rd-sms001",
         note="INTENDED FAILURE: advertises texts before the SMS copy is corrected",
         title="Get a text when a seat opens",
         body="I built a tool that sends you a text message the second a seat opens in a "
              "full class. Free to start. https://seatwatchapp.com/?r=rd-sms001"),

    # --- should FAIL: blocked subreddit + no disclosure + shortener
    dict(sub="sideproject", kind="post", opp=None, code="rd-block1",
         note="INTENDED FAILURE: blocked community, undisclosed, shortener",
         title="Check out this seat alert tool",
         body="Found a neat tool for college students who get stuck on waitlists. "
              "Worth a look: https://bit.ly/seatwatch"),

    # --- should FAIL: stale rules + account minimums unverified
    dict(sub="csmajors", kind="post", opp=None, code="rd-stale1",
         note="INTENDED FAILURE: rules 30 days old, karma minimum unverifiable",
         title="Built a course seat watcher",
         body="I built a tool that watches college course registration systems and emails "
              "you when a seat opens in a full class. Free for one course. "
              "https://seatwatchapp.com/?r=rd-stale1"),
]

ids = []
for d in DRAFTS:
    did = store.add_draft(d["sub"], d["kind"], d["body"], title=d.get("title"),
                          opportunity_id=d.get("opp"), attrib_code=d["code"],
                          writer_notes=d["note"])
    ids.append(did)
    print("   draft %-3d r/%-13s %s" % (did, d["sub"], d["note"]))

# ---------------------------------------------------------------- gate
h("5. SAFETY GATE — deterministic, version %s" % safety.CHECKER_VER)
passed = 0
for did in ids:
    verdict, failures = safety.review(did)
    flag = "PASS" if verdict == "pass" else "FAIL"
    passed += verdict == "pass"
    print("\n   draft %-3d %s" % (did, flag))
    for f in failures:
        print("       %-26s %s" % (f["rule"], f["detail"][:96]))
print("\n   %d/%d passed" % (passed, len(ids)))

# ---------------------------------------------------------------- queue
h("6. APPROVAL QUEUE")
sys.stdout.flush()
os.system("cd %s && REDDIT_MKT_DB=%s python3 queue.py build" % (HERE, store.DB))
os.system("cd %s && REDDIT_MKT_DB=%s python3 queue.py show" % (HERE, store.DB))

h("7. WHAT HAPPENS NEXT (not simulated — these are the real commands)")
print("""
   Nathan reviews and decides:
       python3 queue.py approve 1
       python3 queue.py close --minutes 4

   He posts it himself, then records it:
       python3 queue.py posted 1 https://reddit.com/r/UMD/comments/...

   Nothing in this system can post. store.record_post() refuses any draft without an
   approved batch item, so an unapproved draft cannot even be back-filled as posted.

   Then:
       python3 report.py --days 7
""")
print("demo database: %s" % store.DB)
