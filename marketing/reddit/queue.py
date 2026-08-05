#!/usr/bin/env python3
"""The approval queue — the only path from a draft to something Nathan posts.

DESIGN INTENT: minimise founder minutes, not clicks. Drafts accumulate quietly and surface
as a BATCH, so review is one five-minute sitting rather than a trickle of notifications. The
metric this whole system is judged on is alerts created per founder-minute, and a queue that
interrupts him ten times a day loses on the denominator no matter how good the posts are.

NOTHING HERE POSTS. There is deliberately no Reddit write path anywhere in this codebase.
`posted` records something a human already did. That is a decision, not a missing feature:
automated posting is what turns a marketing system into a spam operation, and the accounts
it burns are not recoverable.

USAGE
  python3 queue.py build            # gather passing drafts into a new batch
  python3 queue.py show             # print the open batch for review
  python3 queue.py approve 12 14    # approve specific items (by draft id)
  python3 queue.py reject  13 --note "too salesy"
  python3 queue.py close --minutes 6
  python3 queue.py posted 12 https://reddit.com/r/UMD/comments/...
"""
import argparse, json, os, sys, textwrap, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import safety, store

W = 78


def _open_batch(c):
    return c.execute("SELECT * FROM batches WHERE status='pending' "
                     "ORDER BY created_at DESC LIMIT 1").fetchone()


def build(args):
    """Collect every draft whose NEWEST safety review is a pass and that is not already in a
    batch. Re-running is safe: it tops up the open batch rather than creating a second one,
    because two open batches means two places to look, which is how a queue gets abandoned."""
    store.init()
    with store.db() as c:
        b = _open_batch(c)
        if not b:
            cur = c.execute("INSERT INTO batches(created_at) VALUES(?)", (store.now(),))
            bid = cur.lastrowid
        else:
            bid = b["id"]

        rows = c.execute("""
            SELECT d.id, d.subreddit FROM drafts d
            JOIN safety_reviews s ON s.id = (
                SELECT id FROM safety_reviews WHERE draft_id=d.id
                ORDER BY reviewed_at DESC LIMIT 1)
            WHERE s.verdict='pass'
              AND d.id NOT IN (SELECT draft_id FROM batch_items)
              AND d.id NOT IN (SELECT draft_id FROM posts)
            ORDER BY d.written_at
        """).fetchall()
        for r in rows:
            c.execute("INSERT OR IGNORE INTO batch_items(batch_id,draft_id) VALUES(?,?)",
                      (bid, r["id"]))
    print("batch %d: added %d draft(s)" % (bid, len(rows)))
    if not rows:
        print("  nothing passing the gate. `python3 safety.py` shows why.")
    return bid


def show(args):
    with store.db() as c:
        b = _open_batch(c)
        if not b:
            print("no open batch — run: python3 queue.py build")
            return
        items = c.execute("""
            SELECT bi.decision, d.* FROM batch_items bi
            JOIN drafts d ON d.id=bi.draft_id
            WHERE bi.batch_id=? ORDER BY d.subreddit, d.id""", (b["id"],)).fetchall()

    print("=" * W)
    print("  APPROVAL QUEUE — batch %d · %d item(s)" % (b["id"], len(items)))
    print("  every item below already passed the safety gate (%s)" % safety.CHECKER_VER)
    print("=" * W)
    for it in items:
        mark = {"pending": "[ ]", "approved": "[x]", "rejected": "[-]",
                "edited": "[~]"}.get(it["decision"], "[?]")
        print("\n%s draft %-4d r/%-18s %s" % (mark, it["id"], it["subreddit"], it["kind"]))
        if it["title"]:
            print("    TITLE  %s" % it["title"])
        for line in textwrap.wrap(it["body"], W - 11):
            print("           %s" % line)
        if it["attrib_code"]:
            print("    LINK   https://seatwatchapp.com/?r=%s" % it["attrib_code"])
        if it["writer_notes"]:
            print("    WHY    %s" % it["writer_notes"])
    print("\n" + "-" * W)
    print("  approve:  python3 queue.py approve %s"
          % " ".join(str(i["id"]) for i in items[:2]) or "<draft ids>")
    print("  reject :  python3 queue.py reject <draft id> --note \"reason\"")
    print("  when done: python3 queue.py close --minutes <how long this took you>")


def _decide(args, decision):
    with store.db() as c:
        b = _open_batch(c)
        if not b:
            print("no open batch")
            return
        n = 0
        for did in args.draft_ids:
            cur = c.execute("UPDATE batch_items SET decision=?, decided_at=?, note=? "
                            "WHERE batch_id=? AND draft_id=? AND decision='pending'",
                            (decision, store.now(), args.note, b["id"], did))
            n += cur.rowcount
    print("%s %d item(s)" % (decision, n))


def close(args):
    """Close the batch and record the founder minutes it cost. That number is the
    denominator of the only metric this system is judged on, so it is required, not
    optional — an unmeasured cost always looks like zero."""
    with store.db() as c:
        b = _open_batch(c)
        if not b:
            print("no open batch")
            return
        pend = c.execute("SELECT COUNT(*) n FROM batch_items WHERE batch_id=? "
                         "AND decision='pending'", (b["id"],)).fetchone()["n"]
        if pend and not args.force:
            print("%d item(s) still undecided. Decide them, or re-run with --force." % pend)
            return
        c.execute("UPDATE batches SET status='closed', founder_minutes=? WHERE id=?",
                  (args.minutes, b["id"]))
    store.log_founder_time(args.minutes, "review batch %d" % b["id"])
    print("batch %d closed · %.0f founder-minutes recorded" % (b["id"], args.minutes))


def posted(args):
    """Record a post AFTER a human published it. store.record_post refuses any draft that
    was not approved, so this cannot be used to backfill something nobody signed off."""
    try:
        pid = store.record_post(args.draft_id, permalink=args.permalink)
    except PermissionError as e:
        print("REFUSED: %s" % e)
        return 1
    print("recorded post %d for draft %d" % (pid, args.draft_id))


def main():
    store.init()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").set_defaults(fn=build)
    sub.add_parser("show").set_defaults(fn=show)

    for name in ("approve", "reject", "edited"):
        p = sub.add_parser(name)
        p.add_argument("draft_ids", nargs="+", type=int)
        p.add_argument("--note")
        p.set_defaults(fn=lambda a, d=name: _decide(a, "approved" if d == "approve"
                                                    else "rejected" if d == "reject"
                                                    else "edited"))
    p = sub.add_parser("close")
    p.add_argument("--minutes", type=float, required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=close)

    p = sub.add_parser("posted")
    p.add_argument("draft_id", type=int)
    p.add_argument("permalink")
    p.set_defaults(fn=posted)

    a = ap.parse_args()
    sys.exit(a.fn(a) or 0)


if __name__ == "__main__":
    main()
