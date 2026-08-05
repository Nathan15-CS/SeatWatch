#!/usr/bin/env python3
"""Regression tests for the safety gate and the approval invariant.

Every test here asserts something that would be a real incident if it regressed: a
fabricated testimonial reaching a queue, a post going to a community that banned us, or a
draft becoming a post without a human approving it.

Run: python3 test_safety.py
"""
import os, sys, tempfile, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["REDDIT_MKT_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")

import safety, store  # noqa: E402

DAY = 86400
CLEAN = ("I built a tool that watches a full class and emails you when a seat opens. "
         "Free for one course. https://seatwatchapp.com/?r=rd-test1")


def mkdraft(body, sub="umd", kind="post", title="Built a seat watcher", code=None):
    return store.add_draft(sub, kind, body, title=title, attrib_code=code)


class Base(unittest.TestCase):
    def setUp(self):
        for t in ("safety_reviews", "batch_items", "batches", "posts", "drafts",
                  "opportunities", "subreddit_rules", "subreddits", "attrib_codes"):
            with store.db() as c:
                c.execute("DELETE FROM %s" % t)
        store.add_subreddit("umd", school="umd")
        store.record_rules("umd", "allowed", "https://reddit.com/r/UMD/about/rules/")
        store.set_status("umd", "approved")

    def rules(self, draft_id):
        return {f["rule"] for f in safety.check(
            store.db().execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone())}


class TestClaims(Base):
    def test_clean_draft_passes(self):
        self.assertEqual(self.rules(mkdraft(CLEAN)), set())

    def test_fabricated_testimonial_blocked(self):
        d = mkdraft(CLEAN + '\n"Saved my semester." - a student')
        self.assertIn("fabricated_testimonial", self.rules(d))

    def test_star_rating_blocked(self):
        self.assertIn("star_rating", self.rules(mkdraft(CLEAN + " Rated 5/5 by users.")))

    def test_invented_usercount_blocked(self):
        self.assertIn("invented_usercount",
                      self.rules(mkdraft(CLEAN + " 4,000 students use it.")))
        self.assertIn("invented_usercount",
                      self.rules(mkdraft(CLEAN + " Thousands of students rely on it.")))

    def test_guarantee_blocked(self):
        self.assertIn("guarantee", self.rules(mkdraft(CLEAN + " You will never miss a seat.")))

    def test_school_count_must_not_exceed_reality(self):
        real = safety.product_facts()["schools"]
        self.assertTrue(real, "coverage.json must be readable for this test to mean anything")
        self.assertIn("false_claim",
                      self.rules(mkdraft(CLEAN + " Covers %d universities." % (real + 50))))
        # the true number is fine
        self.assertNotIn("false_claim",
                         self.rules(mkdraft(CLEAN + " Covers %d universities." % real)))

    def test_school_count_is_the_proven_count_not_the_registry(self):
        """The registry is larger than what the site advertises. Claiming registry size
        would promise schools whose adapters are known broken (ALL_OPEN / EMPTY)."""
        import json
        with open(os.path.expanduser("~/seatwatch/ops/coverage.json")) as f:
            cov = json.load(f)
        self.assertLess(safety.product_facts()["schools"], len(cov),
                        "proven count must be strictly below the registry size")

    def test_sms_claims_blocked_by_config(self):
        self.assertIn("sms_claim_blocked",
                      self.rules(mkdraft(CLEAN + " You also get a text message.")))

    def test_disclosure_required(self):
        d = mkdraft("Found a neat tool for waitlisted students. https://seatwatchapp.com/")
        self.assertIn("no_disclosure", self.rules(d))

    def test_shortener_and_foreign_link_blocked(self):
        d = mkdraft("I built a seat watcher for full classes. https://bit.ly/xyz")
        r = self.rules(d)
        self.assertIn("url_shortener", r)
        self.assertIn("foreign_link", r)


class TestCommunity(Base):
    def test_blocked_subreddit_refused(self):
        store.add_subreddit("sideproject")
        store.set_status("sideproject", "blocked", "mods removed our post")
        self.assertIn("blocked_subreddit", self.rules(mkdraft(CLEAN, sub="sideproject")))

    def test_blocked_is_sticky_against_rediscovery(self):
        store.add_subreddit("sideproject")
        store.set_status("sideproject", "blocked", "removed")
        store.add_subreddit("sideproject", subscribers=999)      # finder re-finds it
        row = store.db().execute("SELECT status FROM subreddits WHERE name='sideproject'"
                                 ).fetchone()
        self.assertEqual(row["status"], "blocked")

    def test_unapproved_subreddit_refused(self):
        store.add_subreddit("berkeley")
        self.assertIn("subreddit_not_approved", self.rules(mkdraft(CLEAN, sub="berkeley")))

    def test_stale_rules_refused(self):
        with store.db() as c:
            c.execute("UPDATE subreddit_rules SET checked_at=? WHERE subreddit='umd'",
                      (time.time() - 30 * DAY,))
        self.assertIn("stale_rules", self.rules(mkdraft(CLEAN)))

    def test_forbidden_promo_refused(self):
        store.record_rules("umd", "forbidden", "u", promo_conditions="No promotion.")
        self.assertIn("promo_forbidden", self.rules(mkdraft(CLEAN)))

    def test_account_minimums_unverified_is_a_failure_not_a_pass(self):
        store.record_rules("umd", "allowed", "u", min_comment_karma=100)
        self.assertIn("account_unverified", self.rules(mkdraft(CLEAN)))

    def test_account_minimums_met_passes(self):
        store.record_rules("umd", "allowed", "u", min_comment_karma=100,
                           min_account_age_days=30)
        d = store.db().execute("SELECT * FROM drafts WHERE id=?",
                               (mkdraft(CLEAN),)).fetchone()
        f = safety.check(d, account={"age_days": 400, "comment_karma": 250})
        self.assertEqual(f, [])


class TestSpam(Base):
    def test_near_duplicate_across_subreddits_blocked(self):
        store.add_subreddit("berkeley")
        store.record_rules("berkeley", "allowed", "u")
        store.set_status("berkeley", "approved")
        mkdraft(CLEAN, sub="umd")
        d2 = mkdraft(CLEAN + " Really useful.", sub="berkeley")
        self.assertIn("near_duplicate", self.rules(d2))

    def test_subreddit_cooldown(self):
        d1 = mkdraft(CLEAN)
        safety.review(d1)
        with store.db() as c:
            b = c.execute("INSERT INTO batches(created_at) VALUES(?)", (time.time(),)).lastrowid
            c.execute("INSERT INTO batch_items(batch_id,draft_id,decision) VALUES(?,?,'approved')",
                      (b, d1))
        store.record_post(d1, permalink="x")
        d2 = mkdraft("I made a different seat watching tool for full college classes here. "
                     "https://seatwatchapp.com/?r=rd-2")
        self.assertIn("subreddit_cooldown", self.rules(d2))


class TestApprovalInvariant(Base):
    def test_unapproved_draft_cannot_become_a_post(self):
        """The single most important guarantee in this system: nothing reaches Reddit
        without an explicit human decision, and it cannot be back-filled either."""
        d = mkdraft(CLEAN)
        with self.assertRaises(PermissionError):
            store.record_post(d, permalink="https://reddit.com/whatever")

    def test_approved_draft_can(self):
        d = mkdraft(CLEAN)
        with store.db() as c:
            b = c.execute("INSERT INTO batches(created_at) VALUES(?)", (time.time(),)).lastrowid
            c.execute("INSERT INTO batch_items(batch_id,draft_id,decision) VALUES(?,?,'approved')",
                      (b, d))
        self.assertTrue(store.record_post(d, permalink="x"))

    def test_failing_draft_never_enters_a_batch(self):
        bad = mkdraft(CLEAN + '\n"Best app ever." - a student')
        safety.review(bad)
        good = mkdraft("I built a seat alert tool for one specific full class you need. "
                       "https://seatwatchapp.com/?r=rd-ok")
        safety.review(good)
        import queue as _q  # noqa: F401  (module name is local, not stdlib queue)
        sys.path.insert(0, HERE)
        import importlib
        q = importlib.import_module("queue")
        bid = q.build(None)
        rows = store.db().execute("SELECT draft_id FROM batch_items WHERE batch_id=?",
                                  (bid,)).fetchall()
        got = {r["draft_id"] for r in rows}
        self.assertIn(good, got)
        self.assertNotIn(bad, got)


if __name__ == "__main__":
    store.init()
    unittest.main(verbosity=2)
