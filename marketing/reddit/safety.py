#!/usr/bin/env python3
"""The safety gate. Deterministic, versioned, and the ONLY thing standing between a draft
and Nathan's approval queue.

WHY THIS IS NOT AN LLM CALL. The three standing rules — no spam, no fake testimonials, no
rule breaking — are exactly the rules a language model can be argued out of, and the writer
agent has every incentive to argue. A regex cannot be persuaded that this one testimonial is
fine because it is "illustrative". SeatWatch has already shipped a fabricated testimonial to
production once (`★★★★★ "Saved my semester." — real students`, removed 2026-07-29 with zero
real users behind it). That is the exact failure this file exists to make structurally
impossible, so the check is mechanical and the writer does not get a vote.

The LLM safety-reviewer agent still exists and still reads every draft. It runs AFTER this
gate and can only ever be MORE strict — it may veto, it may not approve. A model is good at
"this reads as astroturf"; it is not trustworthy as the last line.

FAIL CLOSED. Unknown subreddit, missing rules, stale rules, unreadable product state — all
produce failures, never passes. The cost of a false failure is a draft that gets rewritten.
The cost of a false pass is a banned account and a burned community, which is unrecoverable
in the only three places that matter.

CHECKER_VER is recorded on every review. Change the rules, bump the version — an old pass
under old rules must never look like a pass under the new ones.
"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store

CHECKER_VER = "1.0.0"

DAY = 86400
RULES_MAX_AGE_DAYS = 14        # rules older than this are treated as unknown
SUBREDDIT_COOLDOWN_DAYS = 7    # one post per community per week, hard
GLOBAL_DAILY_CAP = 2           # across all of Reddit, per day
MAX_LINKS = 1
NEAR_DUP_THRESHOLD = 0.75      # token overlap above this = same post wearing a hat

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claims.json")


# --------------------------------------------------------------- claim rules
# Each entry: (rule_id, compiled pattern, human explanation).
# These are deliberately blunt. A false positive costs one rewrite; the alternative costs
# the community.
BANNED = [
    ("fabricated_testimonial",
     re.compile(r'["“][^"”]{8,}["”]\s*[-–—~]\s*[A-Za-z]"'
                r'|["“][^"”]{8,}["”]\s*[-–—]\s*(a |an |one )?'
                r'(student|user|classmate|sophomore|junior|senior|freshman)', re.I),
     "quoted praise attributed to a person — SeatWatch has no real testimonials"),

    ("star_rating", re.compile(r'[★☆]{2,}|\b\d(\.\d)?\s*/\s*5\b|\b5\s*stars?\b', re.I),
     "star rating or score implies collected reviews that do not exist"),

    ("invented_usercount",
     re.compile(r'\b\d[\d,]{2,}\+?\s*(students|users|people)\b'
                r'|\b(hundreds|thousands|tons)\s+of\s+(students|users|people)\b', re.I),
     "a user count we cannot evidence — the real number is tiny and public honesty is the moat"),

    ("guarantee", re.compile(r'\bguarantee\w*\b|\bnever\s+miss\b|\balways\s+get\b'
                             r'|\b100\s*%\s*(reliable|accurate|uptime)\b', re.I),
     "a promise the product cannot keep; seat data can be stale or a school can break"),

    ("superlative", re.compile(r'\bthe\s+best\b|\b#\s?1\b|\bno\.?\s?1\b|\btop[- ]rated\b'
                               r'|\bonly\s+(tool|app|service)\s+that\b', re.I),
     "unverifiable superlative — reads as marketing, gets removed as marketing"),

    ("false_scarcity", re.compile(r'\blimited\s+(spots|time|offer)\b|\bonly\s+\d+\s+left\b'
                                  r'|\bact\s+(now|fast)\b|\bhurry\b', re.I),
     "manufactured urgency; the real urgency is registration and it speaks for itself"),

    ("engagement_bait", re.compile(r'\bupvote\s+(this|if)\b|\bplease\s+share\b'
                                   r'|\bDM\s+me\s+for\b|\bcomment\s+below\s+and\s+I\b', re.I),
     "vote/engagement solicitation violates Reddit sitewide rules, not just subreddit rules"),

    ("url_shortener", re.compile(r'\b(bit\.ly|tinyurl|t\.co|goo\.gl|linktr\.ee|rb\.gy)\b', re.I),
     "shorteners are auto-removed by most subreddits and read as spam"),
]

# The post must sound like a person who built a thing, because that is what it is.
# The first-person subject and the build verb are allowed to be separated, within one
# sentence: "I got locked out of a required class and built a tool" is a disclosure, and an
# earlier version that demanded the literal phrase "I built" rejected it. A disclosure rule
# that fails honest disclosure trains the writer to reword until it passes, which is the
# opposite of what it is for.
DISCLOSURE = re.compile(r"\bI\b[^.!?\n]{0,90}?\b(built|made|created|wrote|put together)\b"
                        r"|\bmy\s+(project|side project|app|tool)\b", re.I)

LINK_RE = re.compile(r'https?://[^\s\)\]]+', re.I)
OWN_DOMAIN = "seatwatchapp.com"


def _tokens(text):
    return set(re.findall(r"[a-z']{4,}", (text or "").lower()))


def _similarity(a, b):
    """Jaccard on 4+ letter tokens. Crude on purpose — near-duplicate posting across
    communities is the single most reliable way to get an account flagged as spam, and we
    want this to fire early rather than cleverly."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def product_facts():
    """Verifiable claims about SeatWatch, derived from the system rather than remembered.

    A number in a post is only allowed if it matches reality at write time. This is what
    makes 'no fake testimonials' enforceable beyond testimonials: every factual claim has a
    source, or it does not go out.
    """
    facts = {}
    # THE PROVEN COUNT, NOT THE REGISTRY SIZE. `len(schools.SCHOOLS)` is 928; the site
    # advertises 890, because app.proven_count() only counts schools whose last probe
    # returned real sections showing open AND full side by side. The 38-school gap is
    # ALL_OPEN (adapters that report everything open — they would fire false alerts) and
    # EMPTY (return nothing at all). Advertising those sends a student to a school that
    # cannot alert them, which is the precise harm this gate exists to prevent.
    #
    # Mirrors app.py:2133 proven_count() by reading ops/coverage.json directly rather than
    # importing app, which starts a server. If the two ever diverge, the site is right and
    # this is a bug: marketing must never be able to claim more than the product shows.
    try:
        root = os.path.expanduser("~/seatwatch")
        with open(os.path.join(root, "ops", "coverage.json")) as fh:
            cov = json.load(fh)
        n = sum(1 for v in cov.values() if (v or {}).get("verdict") == "OK")
        if not n:
            raise ValueError("coverage.json has no OK verdicts")
        facts["schools"] = n
        facts["schools_source"] = "ops/coverage.json verdict=OK"
    except Exception as e:
        # Fail closed: no verifiable count means no numeric school claim may pass.
        facts["schools"] = None
        facts["schools_error"] = "%s: %s" % (type(e).__name__, e)
    try:
        with open(CONFIG) as f:
            facts.update(json.load(f))
    except Exception:
        # No config = the conservative answer to every optional claim.
        facts.setdefault("sms_claims_allowed", False)
        facts.setdefault("free_tier_courses", 1)
        facts.setdefault("free_tier_sections", 2)
    return facts


def check(draft, *, account=None, facts=None):
    """Return a list of {rule, detail} failures. Empty list means pass.

    `draft` is a sqlite3.Row or dict with at least: id, subreddit, kind, title, body.
    `account` optionally carries {'age_days': int, 'comment_karma': int} for the Reddit
    account that would post — omitted means the account requirements cannot be verified,
    which is a failure, not a pass.
    """
    f = []
    body = draft["body"] or ""
    title = draft["title"] or ""
    blob = title + "\n" + body
    facts = facts or product_facts()

    # ---- 1. banned claim patterns
    for rule_id, pat, why in BANNED:
        m = pat.search(blob)
        if m:
            f.append({"rule": rule_id, "detail": "%s -> matched %r" % (why, m.group(0)[:60])})

    # ---- 2. builder disclosure
    if not DISCLOSURE.search(blob):
        f.append({"rule": "no_disclosure",
                  "detail": "post must state plainly that you built it; undisclosed "
                            "promotion is the definition of astroturf"})

    # ---- 3. links: at most one, ours, no shorteners
    links = LINK_RE.findall(blob)
    if len(links) > MAX_LINKS:
        f.append({"rule": "too_many_links",
                  "detail": "%d links; max %d" % (len(links), MAX_LINKS)})
    for u in links:
        if OWN_DOMAIN not in u.lower():
            f.append({"rule": "foreign_link", "detail": "links off-site: %s" % u[:60]})

    # ---- 4. numeric claims must match reality
    for m in re.finditer(r'\b(\d[\d,]{1,5})\+?\s*(schools|universities|colleges)\b', blob, re.I):
        claimed = int(m.group(1).replace(",", ""))
        real = facts.get("schools")
        if real is None:
            f.append({"rule": "unverifiable_claim",
                      "detail": "claims %d schools but the registry could not be read (%s)"
                                % (claimed, facts.get("schools_error", "unknown"))})
        elif claimed > real:
            f.append({"rule": "false_claim",
                      "detail": "claims %d schools; the registry has %d" % (claimed, real)})

    # ---- 5. product-state claims: SMS
    if re.search(r'\btext(s| alert| message)?\b|\bSMS\b', blob, re.I) \
            and not facts.get("sms_claims_allowed"):
        f.append({"rule": "sms_claim_blocked",
                  "detail": "text alerts may not be advertised until claims.json sets "
                            "sms_claims_allowed — the published SMS Terms and /text-alerts "
                            "page still describe texts as a paid-plan feature, and the "
                            "toll-free number was verified against that description"})

    # ---- 5b. never claim to attend a school you do not attend
    # The product serves 890 campuses; the founder attends one. "Here at UConn" posted to
    # r/uconn by someone who does not go there is a lie about identity, which is both the
    # fastest way to be exposed and a worse offence than any marketing claim. The honest
    # framing — "I got stuck in a full class and built this" — travels everywhere.
    with store.db() as c:
        _s = c.execute("SELECT school FROM subreddits WHERE name=?",
                       (draft["subreddit"],)).fetchone()
    target_school = (_s["school"] if _s else None)
    if target_school and target_school != facts.get("founder_school"):
        AFFIL = re.compile(r'\b(here\s+at|i\s+go\s+to|i\'?m\s+a\s+\w+\s+at|i\s+attend|'
                           r'my\s+school|our\s+campus|we\s+at)\b', re.I)
        m = AFFIL.search(blob)
        if m:
            f.append({"rule": "false_affiliation",
                      "detail": "implies attending %s (founder's school is %s) -> matched %r"
                                % (target_school, facts.get("founder_school") or "unset",
                                   m.group(0))})

    # ---- 6. subreddit must be approved
    with store.db() as c:
        sub = c.execute("SELECT * FROM subreddits WHERE name=?",
                        (draft["subreddit"],)).fetchone()
    if not sub:
        f.append({"rule": "unknown_subreddit",
                  "detail": "r/%s is not in the registry" % draft["subreddit"]})
    elif sub["status"] == "blocked":
        f.append({"rule": "blocked_subreddit",
                  "detail": "r/%s is blocked: %s" % (draft["subreddit"], sub["notes"] or "")})
    elif sub["status"] != "approved":
        f.append({"rule": "subreddit_not_approved",
                  "detail": "r/%s is still '%s'; rules must be checked and the community "
                            "approved first" % (draft["subreddit"], sub["status"])})

    # ---- 7. rules must exist, be fresh, and permit this
    r = store.latest_rules(draft["subreddit"])
    if not r:
        f.append({"rule": "no_rules_on_file",
                  "detail": "nobody has read r/%s's rules" % draft["subreddit"]})
    else:
        age_days = (time.time() - r["checked_at"]) / DAY
        if age_days > RULES_MAX_AGE_DAYS:
            f.append({"rule": "stale_rules",
                      "detail": "rules last read %.0f days ago (max %d)"
                                % (age_days, RULES_MAX_AGE_DAYS)})
        if r["self_promo"] == "forbidden":
            f.append({"rule": "promo_forbidden",
                      "detail": "r/%s forbids self-promotion: %s"
                                % (draft["subreddit"], (r["promo_conditions"] or "")[:120])})
        if r["self_promo"] == "unknown":
            f.append({"rule": "promo_unknown",
                      "detail": "self-promotion policy unread; treat as forbidden"})
        if r["mod_permission"]:
            f.append({"rule": "mod_permission_required",
                      "detail": "r/%s requires mod permission before posting; get it in "
                                "writing and record it" % draft["subreddit"]})
        if r["requires_flair"]:
            f.append({"rule": "flair_required",
                      "detail": "must be flaired %r" % r["requires_flair"]})
        # account requirements — unverifiable means fail
        if (r["min_account_age_days"] or 0) > 0 or (r["min_comment_karma"] or 0) > 0:
            if not account:
                f.append({"rule": "account_unverified",
                          "detail": "r/%s has account minimums (age %s d, karma %s) and no "
                                    "account facts were supplied"
                                    % (draft["subreddit"], r["min_account_age_days"],
                                       r["min_comment_karma"])})
            else:
                if account.get("age_days", 0) < (r["min_account_age_days"] or 0):
                    f.append({"rule": "account_too_new",
                              "detail": "account %s d < required %s d"
                                        % (account.get("age_days"), r["min_account_age_days"])})
                if account.get("comment_karma", 0) < (r["min_comment_karma"] or 0):
                    f.append({"rule": "account_low_karma",
                              "detail": "karma %s < required %s"
                                        % (account.get("comment_karma"), r["min_comment_karma"])})

    # ---- 8. frequency caps
    with store.db() as c:
        recent_sub = c.execute(
            "SELECT posted_at FROM posts WHERE subreddit=? AND posted_at>? "
            "ORDER BY posted_at DESC LIMIT 1",
            (draft["subreddit"], time.time() - SUBREDDIT_COOLDOWN_DAYS * DAY)).fetchone()
        if recent_sub:
            f.append({"rule": "subreddit_cooldown",
                      "detail": "posted to r/%s %.1f days ago; cooldown is %d days"
                                % (draft["subreddit"],
                                   (time.time() - recent_sub["posted_at"]) / DAY,
                                   SUBREDDIT_COOLDOWN_DAYS)})
        today = c.execute("SELECT COUNT(*) n FROM posts WHERE posted_at>?",
                          (time.time() - DAY,)).fetchone()["n"]
        if today >= GLOBAL_DAILY_CAP:
            f.append({"rule": "daily_cap",
                      "detail": "%d posts in the last 24h; cap is %d"
                                % (today, GLOBAL_DAILY_CAP)})

        # ---- 9. near-duplicate across other drafts and posted bodies
        others = c.execute(
            "SELECT id, subreddit, body FROM drafts WHERE id<>? AND written_at>?",
            (draft["id"] if "id" in draft.keys() else -1, time.time() - 30 * DAY)).fetchall()
    for o in others:
        s = _similarity(body, o["body"])
        if s >= NEAR_DUP_THRESHOLD:
            f.append({"rule": "near_duplicate",
                      "detail": "%.0f%% token overlap with draft %d (r/%s) — same post in "
                                "two communities is the clearest spam signal there is"
                                % (s * 100, o["id"], o["subreddit"])})
            break

    # ---- 10. shape
    if draft["kind"] not in ("post", "comment_reply"):
        f.append({"rule": "bad_kind", "detail": "kind %r not allowed" % draft["kind"]})
    if draft["kind"] == "post" and not title.strip():
        f.append({"rule": "no_title", "detail": "a post needs a title"})
    if len(body.strip()) < 40:
        f.append({"rule": "too_short", "detail": "body under 40 chars reads as a drive-by"})

    # Same claim in the title and the body is one problem, not two. Duplicate lines make a
    # short failure list look like a catastrophe and train the reader to skim it.
    seen, uniq = set(), []
    for x in f:
        k = (x["rule"], x["detail"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


def review(draft_id, account=None):
    """Run the gate on one draft and persist the verdict. Returns (verdict, failures)."""
    with store.db() as c:
        d = c.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
    if not d:
        raise ValueError("no draft %s" % draft_id)
    failures = check(d, account=account)
    verdict = "pass" if not failures else "fail"
    store.record_review(draft_id, verdict, failures, CHECKER_VER)
    return verdict, failures


if __name__ == "__main__":
    store.init()
    ids = [int(a) for a in sys.argv[1:]] or [
        r["id"] for r in store.db().execute("SELECT id FROM drafts ORDER BY id")]
    for i in ids:
        v, fs = review(i)
        print("draft %-4d %s" % (i, v.upper()))
        for x in fs:
            print("    %-26s %s" % (x["rule"], x["detail"]))
