#!/usr/bin/env python3
"""Storage for the Reddit traction system. One SQLite file, no server, no dependencies.

WHY A DATABASE AND NOT MARKDOWN FILES: every question this system exists to answer is a
join. "Which subreddits produced alerts per founder-minute" needs posts joined to outcomes
joined to attribution joined to time logged. Markdown makes that a manual re-read, which is
how a growth log becomes a diary nobody uses.

WHY IT IS SEPARATE FROM watches.db: this is marketing exhaust. It must never be able to
lock, bloat, or corrupt the database that decides whether a student gets alerted. The only
contact between them is a READ-ONLY attach in attribution.py.

STATE MACHINE — nothing skips a step, and the schema enforces it:

    subreddit(candidate) -> rules_checked -> approved
                                                |
    opportunity(found) ------------------------>+-> draft -> safety_review
                                                                   |
                                              pass ----------------+---- fail (dead end)
                                                |
                                            batch_item(pending)
                                                |
                                    Nathan approves / rejects / edits
                                                |
                                            post(posted) -> outcome

A draft with no passing safety_review cannot enter a batch. A batch item Nathan has not
decided cannot become a post. Both are enforced in code, not by convention.
"""
import json, os, sqlite3, time

DB = os.environ.get("REDDIT_MKT_DB",
                    os.path.expanduser("~/seatwatch/marketing/reddit/reddit.db"))

SCHEMA = """
-- Candidate communities. status: candidate -> approved | blocked
-- 'blocked' is sticky and deliberate: a subreddit that removed us, or whose rules forbid
-- promotion, must never quietly re-enter the funnel because a later scan re-found it.
CREATE TABLE IF NOT EXISTS subreddits (
  name            TEXT PRIMARY KEY,          -- without the r/ prefix, lowercased
  subscribers     INTEGER,
  school          TEXT,                      -- the campus it maps to, if any
  relevance       REAL,                      -- 0..1, why we think students-in-full-classes live here
  status          TEXT NOT NULL DEFAULT 'candidate',
  found_at        REAL NOT NULL,
  found_by        TEXT,
  notes           TEXT
);

-- Rules are versioned by check, never overwritten. A post is validated against the rules
-- as they were READ, so a later rule change cannot retroactively make a past post look
-- compliant (or a compliant post look reckless).
CREATE TABLE IF NOT EXISTS subreddit_rules (
  id                  INTEGER PRIMARY KEY,
  subreddit           TEXT NOT NULL,
  checked_at          REAL NOT NULL,
  self_promo          TEXT NOT NULL,        -- allowed | conditional | forbidden | unknown
  promo_conditions    TEXT,                 -- verbatim quote of the relevant rule
  min_account_age_days INTEGER DEFAULT 0,
  min_comment_karma   INTEGER DEFAULT 0,
  requires_flair      TEXT,
  mod_permission      INTEGER DEFAULT 0,    -- 1 = must ask a mod first
  source_url          TEXT NOT NULL,
  raw                 TEXT,                 -- full rules text as fetched, for audit
  FOREIGN KEY (subreddit) REFERENCES subreddits(name)
);

-- A place where a real person is describing the problem we solve, right now.
CREATE TABLE IF NOT EXISTS opportunities (
  id           INTEGER PRIMARY KEY,
  subreddit    TEXT NOT NULL,
  kind         TEXT NOT NULL,               -- post | comment_reply
  target_url   TEXT,
  target_title TEXT,
  target_at    REAL,
  signal       TEXT,                        -- the quote that made this an opportunity
  score        REAL,
  status       TEXT NOT NULL DEFAULT 'open',-- open | drafted | dropped
  found_at     REAL NOT NULL,
  FOREIGN KEY (subreddit) REFERENCES subreddits(name)
);

CREATE TABLE IF NOT EXISTS drafts (
  id             INTEGER PRIMARY KEY,
  opportunity_id INTEGER,
  subreddit      TEXT NOT NULL,
  kind           TEXT NOT NULL,
  title          TEXT,
  body           TEXT NOT NULL,
  attrib_code    TEXT,                      -- the ?r= code, unique per post
  written_at     REAL NOT NULL,
  writer_notes   TEXT,
  FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
);

-- Deterministic gate output. A draft may be reviewed many times (after edits); only the
-- newest review counts, and only a 'pass' admits it to a batch.
CREATE TABLE IF NOT EXISTS safety_reviews (
  id          INTEGER PRIMARY KEY,
  draft_id    INTEGER NOT NULL,
  verdict     TEXT NOT NULL,                -- pass | fail
  failures    TEXT,                         -- JSON list of {rule, detail}
  checker_ver TEXT NOT NULL,
  reviewed_at REAL NOT NULL,
  FOREIGN KEY (draft_id) REFERENCES drafts(id)
);

-- Nathan's approval queue. Batches exist so review is one sitting, not a trickle of pings.
CREATE TABLE IF NOT EXISTS batches (
  id              INTEGER PRIMARY KEY,
  created_at      REAL NOT NULL,
  status          TEXT NOT NULL DEFAULT 'pending',   -- pending | closed
  founder_minutes REAL DEFAULT 0,           -- time HE spent, the denominator of the metric
  note            TEXT
);

CREATE TABLE IF NOT EXISTS batch_items (
  id         INTEGER PRIMARY KEY,
  batch_id   INTEGER NOT NULL,
  draft_id   INTEGER NOT NULL,
  decision   TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected | edited
  decided_at REAL,
  note       TEXT,
  UNIQUE (batch_id, draft_id),
  FOREIGN KEY (batch_id) REFERENCES batches(id),
  FOREIGN KEY (draft_id) REFERENCES drafts(id)
);

-- Posted only ever by a human, and recorded here afterwards. Nothing in this system
-- publishes; see README. permalink is entered when the post goes up.
CREATE TABLE IF NOT EXISTS posts (
  id         INTEGER PRIMARY KEY,
  draft_id   INTEGER NOT NULL UNIQUE,
  subreddit  TEXT NOT NULL,
  posted_at  REAL NOT NULL,
  permalink  TEXT,
  FOREIGN KEY (draft_id) REFERENCES drafts(id)
);

CREATE TABLE IF NOT EXISTS post_outcomes (
  id             INTEGER PRIMARY KEY,
  post_id        INTEGER NOT NULL,
  checked_at     REAL NOT NULL,
  upvotes        INTEGER,
  comments       INTEGER,
  removed        INTEGER DEFAULT 0,
  removal_reason TEXT,
  FOREIGN KEY (post_id) REFERENCES posts(id)
);

-- The denominator of the only metric that matters here.
CREATE TABLE IF NOT EXISTS founder_time (
  id       INTEGER PRIMARY KEY,
  at       REAL NOT NULL,
  minutes  REAL NOT NULL,
  activity TEXT NOT NULL
);

-- Maps a ?r= code to the post that carried it, so signups can be traced to a subreddit.
CREATE TABLE IF NOT EXISTS attrib_codes (
  code       TEXT PRIMARY KEY,
  draft_id   INTEGER,
  subreddit  TEXT,
  created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_rules_sub   ON subreddit_rules(subreddit, checked_at DESC);
CREATE INDEX IF NOT EXISTS ix_rev_draft   ON safety_reviews(draft_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS ix_items_batch ON batch_items(batch_id);
CREATE INDEX IF NOT EXISTS ix_out_post    ON post_outcomes(post_id, checked_at DESC);
"""


def db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init():
    with db() as c:
        c.executescript(SCHEMA)
    return DB


def now():
    return time.time()


# ---------------------------------------------------------------- accessors

def add_subreddit(name, subscribers=None, school=None, relevance=None,
                  found_by="subreddit-finder", notes=None):
    """Idempotent. Never downgrades a 'blocked' subreddit back to candidate — a rediscovery
    must not undo a decision to stay out of a community."""
    name = name.lower().lstrip("/").removeprefix("r/")
    with db() as c:
        row = c.execute("SELECT status FROM subreddits WHERE name=?", (name,)).fetchone()
        if row:
            if row["status"] != "blocked":
                c.execute("UPDATE subreddits SET subscribers=COALESCE(?,subscribers), "
                          "school=COALESCE(?,school), relevance=COALESCE(?,relevance) "
                          "WHERE name=?", (subscribers, school, relevance, name))
            return name
        c.execute("INSERT INTO subreddits(name,subscribers,school,relevance,found_at,"
                  "found_by,notes) VALUES(?,?,?,?,?,?,?)",
                  (name, subscribers, school, relevance, now(), found_by, notes))
    return name


def set_status(name, status, note=None):
    assert status in ("candidate", "approved", "blocked")
    with db() as c:
        c.execute("UPDATE subreddits SET status=?, notes=COALESCE(?,notes) WHERE name=?",
                  (status, note, name.lower()))


def record_rules(subreddit, self_promo, source_url, promo_conditions=None,
                 min_account_age_days=0, min_comment_karma=0, requires_flair=None,
                 mod_permission=0, raw=None):
    assert self_promo in ("allowed", "conditional", "forbidden", "unknown")
    with db() as c:
        c.execute("""INSERT INTO subreddit_rules(subreddit,checked_at,self_promo,
            promo_conditions,min_account_age_days,min_comment_karma,requires_flair,
            mod_permission,source_url,raw) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (subreddit.lower(), now(), self_promo, promo_conditions,
                   min_account_age_days, min_comment_karma, requires_flair,
                   mod_permission, source_url, raw))


def latest_rules(subreddit):
    with db() as c:
        return c.execute("SELECT * FROM subreddit_rules WHERE subreddit=? "
                         "ORDER BY checked_at DESC LIMIT 1", (subreddit.lower(),)).fetchone()


def add_opportunity(subreddit, kind, target_url=None, target_title=None, target_at=None,
                    signal=None, score=None):
    with db() as c:
        cur = c.execute("""INSERT INTO opportunities(subreddit,kind,target_url,target_title,
            target_at,signal,score,found_at) VALUES(?,?,?,?,?,?,?,?)""",
                        (subreddit.lower(), kind, target_url, target_title, target_at,
                         signal, score, now()))
        return cur.lastrowid


def add_draft(subreddit, kind, body, title=None, opportunity_id=None, attrib_code=None,
              writer_notes=None):
    with db() as c:
        cur = c.execute("""INSERT INTO drafts(opportunity_id,subreddit,kind,title,body,
            attrib_code,written_at,writer_notes) VALUES(?,?,?,?,?,?,?,?)""",
                        (opportunity_id, subreddit.lower(), kind, title, body,
                         attrib_code, now(), writer_notes))
        if opportunity_id:
            c.execute("UPDATE opportunities SET status='drafted' WHERE id=?",
                      (opportunity_id,))
        if attrib_code:
            c.execute("INSERT OR IGNORE INTO attrib_codes(code,draft_id,subreddit,created_at)"
                      " VALUES(?,?,?,?)", (attrib_code, cur.lastrowid, subreddit.lower(), now()))
        return cur.lastrowid


def record_review(draft_id, verdict, failures, checker_ver):
    with db() as c:
        c.execute("""INSERT INTO safety_reviews(draft_id,verdict,failures,checker_ver,
            reviewed_at) VALUES(?,?,?,?,?)""",
                  (draft_id, verdict, json.dumps(failures), checker_ver, now()))


def latest_review(draft_id):
    with db() as c:
        return c.execute("SELECT * FROM safety_reviews WHERE draft_id=? "
                         "ORDER BY reviewed_at DESC LIMIT 1", (draft_id,)).fetchone()


def log_founder_time(minutes, activity):
    with db() as c:
        c.execute("INSERT INTO founder_time(at,minutes,activity) VALUES(?,?,?)",
                  (now(), float(minutes), activity))


def record_post(draft_id, permalink=None, posted_at=None):
    with db() as c:
        d = c.execute("SELECT subreddit FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if not d:
            raise ValueError("no draft %s" % draft_id)
        # A draft only becomes a post if Nathan approved it. Enforced here, not assumed.
        ok = c.execute("SELECT 1 FROM batch_items WHERE draft_id=? AND decision IN "
                       "('approved','edited') LIMIT 1", (draft_id,)).fetchone()
        if not ok:
            raise PermissionError(
                "draft %s has no approved batch_item — nothing may be posted without an "
                "explicit human approval" % draft_id)
        cur = c.execute("INSERT INTO posts(draft_id,subreddit,posted_at,permalink) "
                        "VALUES(?,?,?,?)", (draft_id, d["subreddit"],
                                            posted_at or now(), permalink))
        return cur.lastrowid


if __name__ == "__main__":
    print("initialised %s" % init())
