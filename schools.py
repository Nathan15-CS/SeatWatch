"""
SeatWatch — school registry.

Each school is a small module that knows how to fetch LIVE seat data for that
school. Adding a school = add a tested class here and register it below.

Hard quality rule (the thing that protects the reputation): every fetcher returns
ONLY data it truly read. On any failure it returns {} — it NEVER guesses, never
fabricates "open". The engine's guard treats {} as "skip", so a broken school goes
silent instead of sending false alerts.

Normalized section shape:  {section_id: {"open": bool, "seats": int|None}}
"""
import datetime
import gzip
import html
import http.cookiejar
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SeatWatch/1.0"


def _http(url):
    """GET with gzip support. Raises on failure (callers catch and return {})."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", "replace")


# --- Auto term-detection (keeps schools self-maintaining across semesters) ----------
_SUBTERM = ("week", "online", "late", "early", "law", "vet", "med ", "session", "module",
            "mini", "dynamic", "part of", "continuing", "study abroad", "maymester",
            "intersession", "weekend", "express", "flex", "saturday", "evening", "sprint",
            "ccp", "dual", "high school", "workforce", "abroad", "noncredit", "non-credit")
_SEASON = {"spring": 1, "summer": 5, "fall": 8, "autumn": 8, "winter": 12}
# Seasons a picker is allowed to AUTO-ADOPT. Winter is deliberately absent everywhere.
_AUTO_SEASONS = ("spring", "summer", "fall", "autumn")


def _auto_season(season):
    """May a term with this season word be auto-adopted? Winter: never.

    A winter label cannot be dated from the label alone. At a semester school 'Winter
    2027' is a 3-week December/January intersession carrying a handful of courses; at a
    quarter school (the UCs, Oregon) 'Winter 2026' is the full Jan-Mar quarter, NAMED for
    the year it runs in. _SEASON has to pick one month for both and picks December — which
    for a quarter school points ~11 months into the FUTURE, so a quarter that ENDED last
    March outranks the real next term and the picker rolls BACKWARD into it.

    Live-verified 2026-07-20: on Oct 1 2026 UCLA/UCI/UCSC would each have adopted the
    completed Winter 2026 quarter, passed the live-data gate, and reported its sections as
    OPEN (UCLA COM SCI 32: 42/43/23 seats) — a false alert, the one thing we never do.
    UCSB the same with 0 open (silent miss). Miami Ohio and Montclair would have adopted a
    3-week winter intersession in place of a full semester.

    Holding the pinned term instead costs a manual bump at rollover. That is the trade the
    VSB adapter already makes (see VSB.refresh_term): a term we cannot date is a term we
    do not adopt, and rolling late is the only safe direction to be wrong in."""
    return str(season).lower() in _AUTO_SEASONS


def _season_of(desc):
    """('fall', 2026) from a human term description, or None. Handles both orderings."""
    d = (desc or "").lower()
    m = (re.search(r"(spring|summer|fall|autumn|winter)\D{0,14}(20\d\d)", d) or
         re.search(r"(20\d\d)\D{0,14}(spring|summer|fall|autumn|winter)", d))
    if not m:
        return None
    g = m.groups()
    return (g[0] if g[0] in _SEASON else g[1]), int(g[1] if g[0] in _SEASON else g[0])


def _pick_current_term(terms, today=None, cur=None):
    """From a Banner getTerms list, pick the MAIN term students are registering for.
    Anchored on the human-readable description — term CODES are not portable across
    schools, but 'Fall 2026' always is. Returns code or None. Validated to reproduce all
    43 hand-verified hardcoded terms.

    ROLL-OFF is delta < -1, i.e. the current term is KEPT until ~2 months past its start
    month, so it survives add/drop — the peak seat-watch window. Dropping it at its start
    month instead (delta < 1) hands the whole school to the next published term the moment
    the semester begins: on Aug 1 a Fall watcher would silently be switched to Winter and
    never alerted again all semester. refresh_term's live-data gate does NOT protect
    against that, because a school publishing its next term early satisfies the gate.

    Pass `cur` (the term we are on) to also forbid rolling BACKWARD: candidates strictly
    EARLIER than `cur` are dropped. Defence in depth behind _auto_season — a mis-parsed
    description must not be able to hand a school an older term.

    `cur` itself deliberately stays in the running: it has the smallest delta of anything
    at-or-after it, so while it is still in-window it keeps winning and the pick is a
    no-op. Excluding it instead (<= rather than <) hands the school to the next published
    term immediately — gate-caught doing exactly that to 8 live schools (SD regental,
    Kettering, Lake Michigan, Touro, WCCS)."""
    if today is None:
        today = datetime.date.today()
    cur_rank = None
    if cur is not None:
        for t in terms:
            if str(t.get("code")) == str(cur):
                p = _season_of(t.get("description"))
                if p:
                    cur_rank = (p[1], _SEASON[p[0]])
                break
    best, best_delta = None, None
    for t in terms:
        d = (t.get("description") or "").lower()
        if "view only" in d or any(s in d for s in _SUBTERM):
            continue
        p = _season_of(d)
        if not p:
            continue
        season, year = p
        if not _auto_season(season):
            continue                       # winter: undateable from a label, never adopt
        delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
        if delta < -1:                     # keep the current term through add/drop
            continue
        if cur_rank and (year, _SEASON[season]) < cur_rank:
            continue                       # never roll back onto a term older than ours
        if best_delta is None or delta < best_delta:
            best_delta, best = delta, t.get("code")
    return best


# ===========================================================================
class UMD:
    id = "umd"
    name = "University of Maryland"
    example = "CMSC216"
    term = "202608"
    _re = re.compile(r"^[A-Z]{2,4}\d{3,4}[A-Z]?$")

    def valid_course(self, course):
        return bool(self._re.match(course.upper().replace(" ", "")))

    def reg_url(self, course):
        dept = re.match(r"^[A-Za-z]+", course.upper()).group(0)
        return f"https://app.testudo.umd.edu/soc/{self.term}/{dept}/{course.upper()}"

    def fetch(self, courses):
        """Per-course pages on Testudo. Returns only courses it truly parsed."""
        out = {}
        for course in courses:
            course = course.upper()
            dept = re.match(r"^[A-Za-z]+", course).group(0)
            try:
                html = _http(f"https://app.testudo.umd.edu/soc/{self.term}/{dept}/{course}")
            except Exception:
                continue
            secs = {}
            for m in re.finditer(r'section-id"[^>]*>\s*([A-Za-z0-9]+)\s*<', html):
                blk = html[m.end():m.end() + 3000]
                om = re.search(r'open-seats-count">\s*(\d+)', blk)
                if not om:
                    continue
                n = int(om.group(1))
                secs[m.group(1)] = {"open": n > 0, "seats": n}
            if secs:
                out[course] = secs
        return out


# ===========================================================================
class Rutgers:
    id = "rutgers-nb"
    name = "Rutgers–New Brunswick"
    example = "01:198:111"
    _re = re.compile(r"^\d{2}:\d{3}:\d{3}$")
    api = "https://classes.rutgers.edu/soc/api/courses.json?year=2026&term=9&campus=NB"

    def valid_course(self, course):
        return bool(self._re.match(course.strip()))

    def reg_url(self, course):
        return "https://classes.rutgers.edu/soc/"

    def fetch(self, courses):
        """ONE API call covers the whole term -> efficient no matter how many users."""
        try:
            data = json.loads(_http(self.api))
        except Exception:
            return {}
        want = {c.strip() for c in courses}
        out = {}
        for c in data:
            cs = c.get("courseString")
            if cs in want:
                secs = {}
                for s in c.get("sections", []):
                    num = s.get("number")
                    if num is not None:
                        secs[str(num)] = {"open": bool(s.get("openStatus")), "seats": None}
                if secs:
                    out[cs] = secs
        return out


# ===========================================================================
class Cornell:
    id = "cornell"
    name = "Cornell University"
    example = "CS 1110"
    roster = "FA26"
    _re = re.compile(r"^[A-Z]{2,6}\s\d{4}$")

    @staticmethod
    def _norm(course):
        m = re.match(r"^([A-Za-z]{2,6})\s*(\d{4})$", course.strip())
        return f"{m.group(1).upper()} {m.group(2)}" if m else course.upper().strip()

    def valid_course(self, course):
        return bool(self._re.match(self._norm(course)))

    def reg_url(self, course):
        return f"https://classes.cornell.edu/browse/roster/{self.roster}"

    def fetch(self, courses):
        """One API call per SUBJECT covers all its courses -> efficient."""
        bysubj = {}
        for course in courses:
            c = self._norm(course)
            bysubj.setdefault(c.split(" ")[0], set()).add(c)
        out = {}
        for subj, want in bysubj.items():
            try:
                url = ("https://classes.cornell.edu/api/2.0/search/classes.json"
                       f"?roster={self.roster}&subject={subj}")
                data = json.loads(_http(url))
            except Exception:
                continue
            for c in data.get("data", {}).get("classes", []):
                cs = f"{c.get('subject')} {c.get('catalogNbr')}"
                if cs in want:
                    secs = {}
                    for eg in c.get("enrollGroups", []):
                        for s in eg.get("classSections", []):
                            num = s.get("section")
                            if num is not None:
                                secs[str(num)] = {"open": s.get("openStatus") == "O", "seats": None}
                    if secs:
                        out[cs] = secs
        return out


# ===========================================================================
class OhioState:
    id = "osu"
    name = "Ohio State University"
    example = "CSE 2221"
    term = "1268"   # Autumn 2026
    _re = re.compile(r"^[A-Z]{2,8}\s\d{3,4}(?:\.\d+)?[A-Z]?$")

    @staticmethod
    def _norm(course):
        m = re.match(r"^([A-Za-z]{2,8})\s*(\d{3,4}(?:\.\d+)?[A-Za-z]?)$", course.strip())
        return f"{m.group(1).upper()} {m.group(2).upper()}" if m else course.upper().strip()

    def valid_course(self, course):
        return bool(self._re.match(self._norm(course)))

    def reg_url(self, course):
        return "https://classes.osu.edu/"

    def fetch(self, courses):
        """Query per course (q=full code) so we get the COMPLETE section list."""
        out = {}
        for course in courses:
            c = self._norm(course)
            try:
                url = ("https://content.osu.edu/v2/classes/search"
                       f"?q={urllib.parse.quote(c)}&campus=col&term={self.term}")
                data = json.loads(_http(url)).get("data", {})
            except Exception:
                continue
            for item in data.get("courses", []):
                cc = item.get("course", {})
                if f"{cc.get('subject')} {cc.get('catalogNumber')}" == c:
                    secs = {}
                    for s in item.get("sections", []):
                        num = s.get("section")   # OSU's section id lives in 'section'
                        st = s.get("enrollmentStatus")
                        if num and st:           # only trust rows with a real status
                            secs[str(num)] = {"open": st == "Open", "seats": None}
                    if secs:
                        out[c] = secs
                    break
        return out


# ===========================================================================
class VirginiaTech:
    """Big non-Banner school added via a BESPOKE adapter (like UMD/Cornell/Penn).
    VT publishes its full Timetable of Classes with no login and — critically — an
    authoritative 'open only' filter. We ask VT twice per course: all sections, and
    open-only sections. A section is open iff VT itself lists it as open. We never
    guess; on any error we return {} (skip), so a broken fetch is silent, not false.
    Section id = CRN (how VT students register). ~37k students, top-70 by enrollment.
    """
    id = "vt"
    name = "Virginia Tech"
    example = "CS 1114"
    term = "202609"   # Fall 2026 (VT TERMYEAR format)
    _url = "https://selfservice.banner.vt.edu/ssb/HZSKVTSC.P_ProcRequest"
    _re = re.compile(r"^[A-Z]{2,4}\s?\d{4}$")

    @staticmethod
    def _code(course):
        m = re.match(r"^([A-Za-z]{2,4})[\s-]*(\d{4})$", course.strip())
        return (m.group(1).upper(), m.group(2)) if m else (None, None)

    def valid_course(self, course):
        return self._code(course)[0] is not None

    def reg_url(self, course):
        return "https://selfservice.banner.vt.edu/ssb/HZSKVTSC.P_ProcRequest"

    def _query(self, subj, num, open_only):
        """Return the set of CRNs VT lists for this course (optionally open-only)."""
        fields = {"CAMPUS": "0", "TERMYEAR": self.term, "CORE_CODE": "AR%",
                  "subj_code": subj, "SCHDTYPE": "%", "CRSE_NUMBER": num, "crn": "",
                  "open_only": "on" if open_only else "",
                  "BTN_PRESSED": "FIND class sections", "inst_name": ""}
        data = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(self._url, data=data,
                                     headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
        html = raw.decode("utf-8", "replace")
        # Each listed section links to its detail page as ...CRN=83510 — unambiguous.
        return set(re.findall(r"CRN=(\d{5})", html))

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._code(course)
            if not subj:
                continue
            try:
                allc = self._query(subj, num, False)
                if not allc:                     # no sections parsed -> skip, never guess
                    continue
                openc = self._query(subj, num, True)
            except Exception:
                continue                          # fail-safe: silence, never false-open
            if not openc.issubset(allc):          # sanity: open must be subset of all
                continue
            out[course] = {crn: {"open": crn in openc, "seats": None} for crn in allc}
        return out


# ===========================================================================
class Fose:
    """Generic adapter for the widely-used 'fose' class-search API (CU Boulder,
    Brown, Yale, and others run the identical engine). One POST per course returns
    every section with an authoritative status flag: 'A'=available/open, 'F'=full.
    We treat ONLY 'A' as open (conservative — never false-open). seats=None (fose
    reports status, not counts). Subclass sets: id, name, example, api, srcdb.
    Fail-safe: {} on any error, so a broken fetch is silent, never fabricated.

    srcdb term codes are per-semester and used to be pinned by hand — a stale code
    dies silently at rollover (the API answers with a 'Cannot open database' fatal
    and zero rows, so watches would just never alert). Every fose host embeds its
    own term list in the search page as a JS `srcDBs:[...]` array (verified on all
    11 hosts), so resolve_term/refresh_term now auto-roll it with the same
    verify-before-adopt rule as the Banner/PeopleSoft/MinnState/UIUC pickers; the
    hardcoded srcdb is just the seed / last-known-good."""
    # subclass sets: id, name, example, api, srcdb
    _active_srcdb = None

    def cur_srcdb(self):
        return self._active_srcdb or self.srcdb

    @staticmethod
    def _norm(course):
        # 3-5 digit numbers: Emory "CS 170", CU/Brown/Yale 4-digit, Notre Dame "CSE 20110"
        m = re.match(r"^([A-Za-z]{2,5})[\s-]*(\d{3,5}[A-Za-z]?)$", course.strip())
        return f"{m.group(1).upper()} {m.group(2).upper()}" if m else None

    def valid_course(self, course):
        return self._norm(course) is not None

    def reg_url(self, course):
        return self.api.split("/api/")[0] + "/"

    def resolve_term(self):
        """Nearest upcoming MAIN term's srcdb from the host's own srcDBs list; None on
        failure. Anchored on the human 'Fall 2026' name (codes aren't portable across
        fose hosts); catch-alls ('Any Term', 'Past Terms') carry no season+year and are
        skipped naturally, as are combined/sub terms via the shared _SUBTERM screen."""
        try:
            page = _http(self.reg_url(""))
            m = re.search(r"srcDBs\s*:\s*(\[.*?\])", page, re.S)
            if not m:
                return None
            today = datetime.date.today()
            best, best_delta = None, None
            for t in json.loads(m.group(1)):
                name = (t.get("name") or "").lower()
                if any(s in name for s in _SUBTERM) or "&" in name:
                    continue
                sm = (re.search(r"(spring|summer|fall|autumn|winter)\D{0,12}(20\d\d)", name) or
                      re.search(r"(20\d\d)\D{0,12}(spring|summer|fall|autumn|winter)", name))
                if not sm:
                    continue
                g = sm.groups()
                season, year = (g[0], int(g[1])) if g[0] in _SEASON else (g[1], int(g[0]))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, t.get("code")
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        """Adopt a newly-detected srcdb ONLY after the example returns live sections
        under it; else keep last-known-good."""
        new = self.resolve_term()
        if not new or new == self.cur_srcdb():
            return
        prev = self._active_srcdb
        self._active_srcdb = new
        ok = bool(self.fetch({self.example}).get(self.example)) if getattr(self, "example", "") else False
        if not ok:
            self._active_srcdb = prev
            if log:
                log(f"[term] {self.id}: detected srcdb {new} but no live data yet — keeping {self.cur_srcdb()}")
            return
        if log:
            log(f"[term] {self.id}: srcdb auto-updated {prev or self.srcdb} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            code = self._norm(course)
            if not code:
                continue
            try:
                body = json.dumps({"other": {"srcdb": self.cur_srcdb()},
                                   "criteria": [{"field": "keyword", "value": code}]}).encode()
                req = urllib.request.Request(self.api, data=body,
                                             headers={"User-Agent": UA,
                                                      "Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read().decode("utf-8", "replace"))
            except Exception:
                continue                       # fail-safe: silence, never false data
            secs = {}
            for row in data.get("results", []):
                if (row.get("code") or "").upper() != code:   # keyword returns neighbors
                    continue
                num, stat = row.get("no"), row.get("stat")
                if num and stat:               # only trust rows that report a status
                    secs[str(num)] = {"open": stat == "A", "seats": None}
            if secs:
                out[course] = secs
        return out


class CUBoulder(Fose):
    id = "cuboulder"; name = "University of Colorado Boulder"
    example = "CSCI 1300"; srcdb = "2267"     # Fall 2026 (fose default for CU)
    api = "https://classes.colorado.edu/api/?page=fose&route=search"

class Brown(Fose):
    id = "brown"; name = "Brown University"
    example = "CSCI 0150"; srcdb = "202610"    # Fall 2026 (verified via term list)
    api = "https://cab.brown.edu/api/?page=fose&route=search"

class Yale(Fose):
    id = "yale"; name = "Yale University"
    example = "CPSC 2230"; srcdb = "202603"    # Fall 2026 (verified via term list)
    api = "https://courses.yale.edu/api/?page=fose&route=search"

class NotreDame(Fose):
    id = "notredame"; name = "University of Notre Dame"
    example = "CSE 20110"; srcdb = "202610"    # Fall 2026 (verified via term list)
    api = "https://classsearch.nd.edu/api/?page=fose&route=search"

class Emory(Fose):
    id = "emory"; name = "Emory University"
    example = "CS 170"; srcdb = "5269"         # Fall 2026 (verified via term list)
    api = "https://atlas.emory.edu/api/?page=fose&route=search"

class Dartmouth(Fose):
    id = "dartmouth"; name = "Dartmouth College"
    example = "COSC 001"; srcdb = "202609"     # Fall 2026
    api = "https://courses.dartmouth.edu/api/?page=fose&route=search"

class UArk(Fose):
    id = "uark"; name = "University of Arkansas"
    example = "ENGL 10103"; srcdb = "1269"     # Fall 2026 (verified live)
    api = "https://classes.uark.edu/api/?page=fose&route=search"

class SLU(Fose):
    id = "slu"; name = "Saint Louis University"
    example = "ENGL 1900"; srcdb = "202710"    # Fall 2026 (verified live)
    api = "https://courses.slu.edu/api/?page=fose&route=search"

class SouthCarolina(Fose):
    id = "southcarolina"; name = "University of South Carolina"
    example = "ENGL 101"; srcdb = "202608"     # Fall 2026 (verified live)
    api = "https://classes.sc.edu/api/?page=fose&route=search"

class UConn(Fose):
    # UConn's PeopleSoft classic search is SSO-gated; this public fose search is
    # the guest path in. Gated with REAL mixed A/F statuses (not an all-open trap).
    id = "uconn"; name = "University of Connecticut"
    example = "ENGL 1007"; srcdb = "1268"      # Fall 2026 (auto-rolls)
    api = "https://classes.uconn.edu/api/?page=fose&route=search"

class OregonState(Fose):
    # OSU's English subject is "ENG", not "ENGL" — the first handoff example used the
    # wrong code and gated to zero; corrected and re-gated clean (real A/F mix). The
    # srcDBs auto-roll correctly skips OSU's "999999 All Terms" catch-all.
    # QUARTER CALENDAR — auto_term is OFF, same reason as the UC adapters: OSU's real next
    # term on Oct 1 is Winter 2027, which _auto_season refuses (a winter label cannot be
    # dated), so auto-rolling could only ever skip it. Pinned term, bumped by hand.
    auto_term = False
    id = "oregonstate"; name = "Oregon State University"
    example = "ENG 104Z"; srcdb = "202701"     # Fall 2026 (bumped by hand — see auto_term)
    api = "https://classes.oregonstate.edu/api/?page=fose&route=search"


class UIUC:
    """University of Illinois Urbana-Champaign 'Course Explorer' (courses.illinois.edu)
    — a plain server-rendered, guest-accessible schedule page (no login, no AJAX API).
    robots.txt allows /schedule/ (only blocks /cisapp/, /cisdocs/, /search/, /user/,
    PDFs). Page states 'Section Status updates every 10 minutes'.

    One GET per course: https://courses.illinois.edu/schedule/{year}/{term}/{SUBJ}/{NUM}
    Each section's CRN is embedded in its own 'favorite' link
    (/userredirect/favorite/{year}/{term}/{SUBJ}/{NUM}/{CRN}); its Availability sits in
    the SAME per-row chunk (<dt>Availability:</dt><dd>{status}</dd>), so sections are
    paired by ROW, never by parallel-list order (a row with a missing field would
    silently misalign a global zip).

    Status enum (from the page's own legend): Closed, Open, Open (Restricted), Pending,
    Unknown. Cross-listed sections render concatenated: 'CrossListOpen (Restricted)'.
    TRUE-OPEN RULE: status contains 'Open' AND does NOT contain 'Closed' -> open.
    Pending/Unknown are conservatively NOT open (never a false alert). No seat counts
    published -> seats=None. A course with literally 'No Sections' on the page, or a
    duplicate CRN (collapse guard), is skipped rather than guessed."""
    id = "uiuc"; name = "University of Illinois Urbana-Champaign"
    example = "CS 101"
    term = "2026/fall"                    # {year}/{season}; auto-rolls via refresh_term
    _active_term = None
    _CODE_RE = re.compile(r"^([A-Za-z]{2,4})\s+(\d{2,3}[A-Za-z]?)$")
    _ANCHOR_FMT = "/userredirect/favorite/{term}/{subj}/{num}/(\\d+)"

    def cur_term(self):
        return self._active_term or self.term

    def _norm(self, course):
        m = self._CODE_RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        subj, num = self._norm(course)
        return f"https://courses.illinois.edu/schedule/{self.cur_term()}/{subj}/{num}"

    def _fetch_term(self, term, course):
        subj, num = self._norm(course)
        if not subj:
            return None
        try:
            html = _http(f"https://courses.illinois.edu/schedule/{term}/{subj}/{num}")
        except Exception:
            return None
        if "No Sections" in html:
            return {}
        pat = re.compile(self._ANCHOR_FMT.format(term=term, subj=subj, num=num))
        anchors = list(pat.finditer(html))
        if not anchors:
            return None                          # unexpected shape — don't guess
        secs, dup = {}, False
        for i, m in enumerate(anchors):
            crn = m.group(1)
            if crn in secs:
                dup = True
                break
            start = m.end()
            end = anchors[i + 1].start() if i + 1 < len(anchors) else len(html)
            sm = re.search(r"<dt>Availability:</dt>\s*<dd>([^<]*)</dd>", html[start:end])
            status = sm.group(1) if sm else ""
            secs[crn] = {"open": "Open" in status and "Closed" not in status, "seats": None}
        return None if dup else secs

    def resolve_term(self):
        """Nearest UPCOMING term as {year}/{season} — same delta-months-ahead logic as
        every other adapter's term picker (_pick_current_term, PeopleSoft.resolve_term):
        keep the current term until ~2 months past its start so it survives add/drop
        (delta < -1), then pick the smallest remaining delta. Existence/live-data is
        verified separately by refresh_term's own fetch of the example course before
        adopting — this method only computes the calendar-correct candidate. 'winter' is
        skipped via _auto_season: UIUC does run a winter session, but it is a handful of
        courses over the December break, and adopting it on Oct 1 would point the whole
        campus at it right through spring registration."""
        today = datetime.date.today()
        best, best_delta = None, None
        for season, mon in _SEASON.items():
            if season == "autumn" or not _auto_season(season):
                continue
            for year in (today.year, today.year + 1):
                delta = (year - today.year) * 12 + (mon - today.month)
                if delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, f"{year}/{season}"
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self._fetch_term(new, self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            secs = self._fetch_term(self.cur_term(), course)
            if secs:
                out[course] = secs
        return out


class UCI:
    """UC Irvine 'WebSoc' — the university's famous public Schedule of Classes.
    Plain GET, no auth, server-rendered HTML with authoritative per-section status
    in the LAST cell: 'OPEN' / 'FULL' / 'Waitl' / 'NewOnly'. ONLY 'OPEN' counts as
    open ('NewOnly' seats are reserved for incoming students — alerting a continuing
    student on those would be a false open). seats = Max - Enr when parseable.

    WebSoc's CourseNum filter matches LOOSELY (CourseNum=2A also returns 2AX), so
    rows are scoped to the exact course-header block — a watcher of MATH 2A must
    never receive a 2AX section. Sections keyed by WebSoc's 5-digit course code
    (unique per section; it's what UCI students enroll with).

    YearTerm auto-rolls from the landing page's own <select> ('2026-92' = 2026 Fall
    Quarter), skipping Law/Summer/COM sub-terms; verify-before-adopt as usual."""
    # QUARTER CALENDAR — auto_term is OFF. The shared season model dates a term by one
    # nominal month per season and cannot express a quarter year: "Winter 2027" runs
    # Jan-Mar 2027, not December. _auto_season therefore refuses winter outright, which
    # leaves this school jumping Fall -> Spring and silently skipping the whole winter
    # quarter (gate-verified on UCLA: 26F -> 27S on Oct 1). Holding the pinned term and
    # bumping it by hand is the honest trade until a per-adapter quarter month-map lands.
    auto_term = False
    id = "uci"; name = "University of California, Irvine"
    example = "I&C SCI 31"
    term = "2026-92"                    # Fall 2026 (bumped by hand — see auto_term)
    _active_term = None
    base = "https://www.reg.uci.edu/perl/WebSoc"
    _RE = re.compile(r"^(.+?)\s+(\d+[A-Za-z]{0,3})$")

    @staticmethod
    def _canon(s):
        return re.sub(r"\s+", " ", s.replace("&amp;", "&")).strip().upper()

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (self._canon(m.group(1)), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.base

    def resolve_term(self):
        """Nearest upcoming MAIN quarter's YearTerm code from the landing page's own
        select; None on failure. Sub-terms (Law semesters, Summer sessions, COM) are
        screened out via the shared _SUBTERM list plus WebSoc-specific markers."""
        try:
            page = _http(self.base)
            i = page.find('name="YearTerm"')
            if i < 0:
                return None
            today = datetime.date.today()
            best, best_delta = None, None
            for code, name in re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)', page[i:i + 6000]):
                n = name.lower()
                if any(s in n for s in _SUBTERM) or "(" in n or "summer" in n:
                    continue
                sm = re.search(r"(20\d\d)\D{0,4}(fall|winter|spring)", n)
                if not sm:
                    continue
                year, season = int(sm.group(1)), sm.group(2)
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    _HDR_RE = re.compile(r"&nbsp;\s*([A-Za-z&; ]+?)\s*&nbsp;\s*(\d+[A-Za-z]{0,3})\s*&nbsp;")

    def fetch(self, courses):
        out = {}
        for course in courses:
            dept, num = self._norm(course)
            if not dept:
                continue
            try:
                q = urllib.parse.urlencode({"YearTerm": self.cur_term(), "Dept": dept,
                                            "CourseNum": num, "Submit": "Display Web Results"})
                html = _http(self.base + "?" + q)
            except Exception:
                continue
            # scope to the EXACT course's header block (CourseNum matches loosely)
            hdrs = [(m.start(), self._canon(m.group(1)), m.group(2).upper())
                    for m in self._HDR_RE.finditer(html)]
            blocks = [(hdrs[i][0], hdrs[i + 1][0] if i + 1 < len(hdrs) else len(html))
                      for i, hd in enumerate(hdrs) if hd[1] == dept and hd[2] == num]
            if len(blocks) != 1:                 # missing or ambiguous — never guess
                if "no classes" in html.lower() or (hdrs and not blocks):
                    out[course] = {"none": {"open": False, "seats": None}}
                continue
            secs, dup = {}, False
            for row in re.finditer(r"<tr[^>]*>(.*?)</tr>", html[blocks[0][0]:blocks[0][1]], re.S):
                cells = [re.sub(r"<[^>]+>|\s+", " ", c).strip()
                         for c in re.findall(r"<td[^>]*>(.*?)</td>", row.group(1), re.S)]
                if len(cells) < 15 or not re.fullmatch(r"\d{5}", cells[0]):
                    continue
                code, status = cells[0], cells[-1]
                if code in secs:
                    dup = True
                    break
                try:
                    seats = max(int(cells[8]) - int(cells[9]), 0)
                except ValueError:
                    seats = None
                secs[code] = {"open": status == "OPEN", "seats": seats}
            if dup or not secs:
                continue
            out[course] = secs
        return out


class UCSC:
    """UC Santa Cruz 'pisa' public class search (PeopleSoft-backed). One POST per
    course (reg_status=all so closed/waitlisted sections are visible and correctly
    marked not-open). Status is a per-section icon PS_CS_STATUS_{OPEN|CLOSED|WAITLIST};
    ONLY 'OPEN' is open — this guest view shows REAL live status (verified: a full
    section reads WAITLIST with '15 of 15 Enrolled', and other courses show a genuine
    open/closed mix — NOT the always-open trap some guest views have). seats=None.

    PARSE SAFETY: the status icon and the section's class_id live in the SAME
    <div class="panel-heading"> element, so results are split into per-panel blocks
    and the status is taken ONLY from within each section's own panel (a naive
    'nearest icon' regex mis-pairs the legend/previous-section icon — caught and
    avoided). Exact catalog_nbr search returns only that course (verified no 11A->11B
    sibling leak), and rows are still scoped to the exact watched code as a backstop.
    Sections keyed by pisa's section id (01/02/...). Term auto-rolls from the form's
    own term dropdown ('2268' = 2026 Fall Quarter)."""
    # QUARTER CALENDAR — auto_term is OFF. The shared season model dates a term by one
    # nominal month per season and cannot express a quarter year: "Winter 2027" runs
    # Jan-Mar 2027, not December. _auto_season therefore refuses winter outright, which
    # leaves this school jumping Fall -> Spring and silently skipping the whole winter
    # quarter (gate-verified on UCLA: 26F -> 27S on Oct 1). Holding the pinned term and
    # bumping it by hand is the honest trade until a per-adapter quarter month-map lands.
    auto_term = False
    id = "ucsc"; name = "University of California, Santa Cruz"
    example = "CSE 30"
    term = "2268"                       # Fall 2026 (bumped by hand — see auto_term)
    _active_term = None
    base = "https://pisa.ucsc.edu/class_search/index.php"
    _RE = re.compile(r"^([A-Za-z&]{1,6})\s+(\d+[A-Za-z]{0,2})$")
    _PANEL_RE = re.compile(
        r'id="class_id_\d+"[^>]*>\s*([A-Z&]{2,6})\s+(\d+[A-Z]?)\s*-\s*(\d+)')

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.base

    def resolve_term(self):
        """Nearest upcoming main quarter's code from the form's term dropdown; None on
        failure. pisa term codes are 2+YY+quarter-digit (Winter0/Spring2/Summer4/Fall8).
        Anchored on the human 'Fall 2026'-style label, sub-terms screened."""
        try:
            page = _http(self.base)
            i = page.find('term_dropdown')
            if i < 0:
                return None
            today = datetime.date.today()
            best, best_delta = None, None
            for code, name in re.findall(r'''<option value=['"](\d{4})['"][^>]*>\s*([^<]+)''', page[i:i + 4000]):
                n = name.lower()
                if any(s in n for s in _SUBTERM) or "summer" in n:
                    continue
                sm = re.search(r"(20\d\d)\D{0,6}(fall|winter|spring)", n)
                if not sm:
                    continue
                year, season = int(sm.group(1)), sm.group(2)
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            body = {"action": "results", "binds[:term]": self.cur_term(),
                    "binds[:reg_status]": "all", "binds[:subject]": subj,
                    "binds[:catalog_nbr_op]": "=", "binds[:catalog_nbr]": num,
                    "binds[:title]": "", "binds[:instr_name_op]": "=",
                    "binds[:instructor]": "", "binds[:ge]": "",
                    "binds[:crse_units_op]": "=", "binds[:crse_units_from]": "",
                    "binds[:crse_units_to]": "", "binds[:days]": "", "binds[:times]": "",
                    "binds[:acad_career]": "", "rec_start": "0", "rec_dur": "200"}
            try:
                req = urllib.request.Request(
                    self.base, data=urllib.parse.urlencode(body).encode(),
                    headers={"User-Agent": UA,
                             "Content-Type": "application/x-www-form-urlencoded"})
                html = self._retry(lambda: urllib.request.urlopen(req, timeout=30)
                                   .read().decode("utf-8", "replace"))
            except Exception:
                continue
            secs, dup = {}, False
            for panel in re.split(r'(?=<div class="panel-heading)', html):
                cm = self._PANEL_RE.search(panel)
                if not cm:
                    continue
                if cm.group(1).upper() != subj or cm.group(2).upper() != num:
                    continue                       # backstop: exact watched code only
                sec = cm.group(3)
                # status from THIS panel only, before the class_id anchor
                icn = re.findall(r"PS_CS_STATUS_([A-Z]+)_ICN", panel[:cm.start()])
                if not icn:
                    continue                       # no status -> skip, never guess open
                if sec in secs:
                    dup = True
                    break
                secs[sec] = {"open": icn[-1] == "OPEN", "seats": None}
            if dup:
                continue
            out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out

    @staticmethod
    def _retry(fn, tries=3):
        last = None
        for i in range(tries):
            try:
                return fn()
            except Exception as e:
                last = e
                time.sleep(0.5 * (i + 1))
        raise last


class UCSB:
    """UC Santa Barbara public course search (ASP.NET WebForms). GET the page for the
    __VIEWSTATE/__VIEWSTATEGENERATOR/__EVENTVALIDATION tokens, then POST them back with
    __EVENTTARGET set to the (image-button) search control — subject-wide, no course#
    field. Results are scoped to the exact watched course on parse.

    OPEN DETECTION (the accuracy crux — the research handoff flagged it as unproven, so
    it was PROVEN before shipping): UCSB never renders an explicit 'Open' word — the
    Status cell is 'Full', 'Closed', or BLANK. Cross-checking every section's Status
    against its own 'Enrolled / Capacity' cell across 390 live sections showed the rule
    holds with ZERO violations: BLANK <=> enrolled < capacity, 'Full' <=> at/over cap.
    So we treat a section open ONLY when Status is blank AND enrolled < capacity (both
    conditions — double-safe). 'Closed' sections can have empty seats but are
    administratively closed, so they are NEVER open. seats = capacity - enrolled.

    One row per section (the course title repeats per row); sections keyed by UCSB's
    5-digit enroll code. Term auto-rolls from the server-rendered quarterList <select>
    ('20264' = FALL 2026; format 2026 + quarter-digit, Winter1/Spring2/Summer3/Fall4)."""
    # QUARTER CALENDAR — auto_term is OFF. The shared season model dates a term by one
    # nominal month per season and cannot express a quarter year: "Winter 2027" runs
    # Jan-Mar 2027, not December. _auto_season therefore refuses winter outright, which
    # leaves this school jumping Fall -> Spring and silently skipping the whole winter
    # quarter (gate-verified on UCLA: 26F -> 27S on Oct 1). Holding the pinned term and
    # bumping it by hand is the honest trade until a per-adapter quarter month-map lands.
    auto_term = False
    id = "ucsb"; name = "University of California, Santa Barbara"
    example = "WRIT 2"
    term = "20264"                      # Fall 2026 (bumped by hand — see auto_term)
    _active_term = None
    base = "https://my.sa.ucsb.edu/public/curriculum/coursesearch.aspx"
    _RE = re.compile(r"^([A-Za-z][A-Za-z ]{0,7}?)\s+(\d+[A-Za-z]{0,2})$")
    _ROW_RE = re.compile(
        r'id="CourseTitle"[^>]*>\s*([A-Z]+)\s+(\d+[A-Z]{0,2})', re.S)

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (re.sub(r"\s+", " ", m.group(1)).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.base

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        page = op.open(self.base, timeout=30).read().decode("utf-8", "replace")
        def tok(n):
            m = re.search(rf'id="{n}" value="([^"]*)"', page)
            return m.group(1) if m else ""
        toks = {k: tok(k) for k in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")}
        return op, page, toks

    def resolve_term(self):
        """Nearest upcoming main quarter's code from the server-rendered quarterList."""
        try:
            _, page, _ = self._session()
            i = page.find("quarterList")
            if i < 0:
                return None
            today = datetime.date.today()
            best, best_delta = None, None
            for code, name in re.findall(r'<option[^>]*value="(\d{5})"[^>]*>\s*([A-Z ]+\d{4})', page[i:i + 4000]):
                n = name.lower()
                if "summer" in n:
                    continue
                sm = re.search(r"(fall|winter|spring)\D{0,4}(20\d\d)", n)
                if not sm:
                    continue
                season, year = sm.group(1), int(sm.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        # group by subject: one subject-wide POST serves every watched course in it
        want = {}
        for course in courses:
            subj, num = self._norm(course)
            if subj:
                want.setdefault(subj, []).append((course, num))
        if not want:
            return {}
        out = {}
        for subj, items in want.items():
            try:
                op, _, toks = self._session()
                body = urllib.parse.urlencode({
                    "__EVENTTARGET": "ctl00$pageContent1$searchButton", "__EVENTARGUMENT": "",
                    **toks,
                    "ctl00$pageContent1$quarterList": self.cur_term(),
                    "ctl00$pageContent1$courseList": subj,
                    "ctl00$pageContent1$dropDownCourseLevels": "All"}).encode()
                html = op.open(urllib.request.Request(self.base, data=body), timeout=90
                               ).read().decode("utf-8", "replace")
            except Exception:
                continue
            found = {course: {} for course, _ in items}
            dups = set()
            for row in re.split(r'(?=<tr class="CourseInfoRow">)', html):
                tm = self._ROW_RE.search(row)
                if not tm:
                    continue
                rsubj, rnum = tm.group(1).upper(), tm.group(2).upper()
                if rsubj != subj:
                    continue
                ec = re.search(r'HyperLinkEnrollCode[^>]*>\s*(\d+)', row)
                fr = re.search(r'>\s*(\d+)\s*/\s*(\d+)\s*<', row)
                st = re.search(r'class="Status">\s*([^<]*?)\s*</td>', row)
                if not (ec and fr):
                    continue
                status = (st.group(1).strip() if st else "")
                enr, cap = int(fr.group(1)), int(fr.group(2))
                is_open = (status == "") and (enr < cap)     # blank AND seats left
                for course, num in items:
                    if rnum == num:
                        d = found[course]
                        if ec.group(1) in d:
                            dups.add(course)
                        d[ec.group(1)] = {"open": is_open, "seats": max(cap - enr, 0) if is_open else 0}
            for course, secs in found.items():
                if course in dups:
                    continue
                out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class UCLA:
    """UCLA public Schedule of Classes (sa.ucla.edu/ro/public/soc) — fully headless,
    no token reverse-engineering: the per-course model (incl. its Token) is embedded in
    the subject-results page's inline JS. Two GETs: (1) the subject page for the course
    models, (2) a GetCourseSummary XHR per watched course for its sections.

    Course lookup keys on the HUMAN-DISPLAYED number ('32', 'M51A', '35L', 'C121'),
    read straight off the page's own title buttons and joined to each model by element
    id (SubjectAreaCode+CatalogNumber, spaces stripped) — verified 25/25. We never
    reconstruct UCLA's path encoding; we read it. seats = the section's true 'N Spots
    Left' int (0 when 'Class Full'). Status word is authoritative: ONLY 'Open' is open
    ('Closed'/'Waitlist'/'Cancelled'/'Tentative' are not) — verified real via a
    completed-term test (Fall 2025 shows genuine Closed/Waitlist, not an all-open trap).
    Sections keyed by their 9-digit class_id (unique). Enrollment status is refreshed
    hourly by the registrar (not real-time) — same data Coursicle sees; still real.

    FilterFlags sends NO time-of-day window (start/end null) so an evening section is
    never hidden from a watcher — the handoff's suggested 8am-8pm window was verified
    harmless on MATH but we drop it entirely to be safe. Term auto-rolls from the
    page's own term <select> (26F = Fall 2026; code = YY + F/W/S)."""
    # QUARTER CALENDAR — auto_term is OFF. The shared season model dates a term by one
    # nominal month per season and cannot express a quarter year: "Winter 2027" runs
    # Jan-Mar 2027, not December. _auto_season therefore refuses winter outright, which
    # leaves this school jumping Fall -> Spring and silently skipping the whole winter
    # quarter (gate-verified on UCLA: 26F -> 27S on Oct 1). Holding the pinned term and
    # bumping it by hand is the honest trade until a per-adapter quarter month-map lands.
    auto_term = False
    id = "ucla"; name = "University of California, Los Angeles"
    example = "COM SCI 32"
    term = "26F"                        # Fall 2026 (bumped by hand — see auto_term)
    _active_term = None
    root = "https://sa.ucla.edu/ro/public/soc"
    _RE = re.compile(r"^([A-Za-z][A-Za-z& ]{0,24}?)\s+([A-Z]?\d+[A-Z]{0,2})$")
    _FLAGS = ('{"enrollment_status":"O,W,C,X,T,S","advanced":"n","meet_days":null,'
              '"start_time":null,"end_time":null,"meet_locations":null,"meet_units":null,'
              '"instructor":null,"class_career":null,"impacted":null,'
              '"enrollment_restrictions":null,"enforced_requisites":null,'
              '"individual_studies":"n","summer_session":null}')

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (re.sub(r"\s+", " ", m.group(1)).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.root

    def _get(self, url, xhr=False):
        hdrs = {"User-Agent": UA}
        if xhr:
            hdrs["X-Requested-With"] = "XMLHttpRequest"
        return urllib.request.urlopen(urllib.request.Request(url, headers=hdrs),
                                      timeout=30).read().decode("utf-8", "replace")

    def resolve_term(self):
        """Nearest upcoming main term (F/W/S) from the page's term select; None on
        failure. Summer codes (YY1/YY2) carry no F/W/S letter and are skipped."""
        try:
            page = self._get(self.root)
            today = datetime.date.today()
            best, best_delta = None, None
            for code, yeartext in re.findall(
                    r'class="select_term" value="(\d\d[FWS])"[^>]*data-yearText="([^"]*)"', page):
                sm = re.search(r"(fall|winter|spring)\s*(20\d\d)", yeartext, re.I)
                if not sm:
                    continue
                season, year = sm.group(1).lower(), int(sm.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def _subject_models(self, subj):
        """{displayed_number -> model_json_str} for one subject in the current term."""
        q = urllib.parse.urlencode({"SubjectAreaName": "x", "t": self.cur_term(),
                                    "sBy": "subject", "subj": subj, "catlg": "",
                                    "cls_no": "", "btnIsInIndex": "btn_inIndex"})
        page = self._get(self.root + "/Results?" + q)
        titles = {m.group(1).upper(): m.group(2).strip()
                  for m in re.finditer(r'id="([A-Z0-9]+)-title"[^>]*>\s*([0-9A-Z]+)\s*-', page)}
        out = {}
        for raw in re.findall(r'AddToCourseData\("[^"]+",(\{.*?\})\);', page):
            try:
                d = json.loads(raw)
            except Exception:
                continue
            elid = (d.get("SubjectAreaCode", "") + d.get("CatalogNumber", "")).replace(" ", "").upper()
            disp = titles.get(elid)
            if disp:
                out[disp.upper()] = raw
        return out

    def _sections(self, model):
        u = (self.root + "/Results/GetCourseSummary?" +
             urllib.parse.urlencode({"model": model, "FilterFlags": self._FLAGS,
                                     "_": str(int(time.time() * 1000))}))
        html = self._get(u, xhr=True)
        secs, dup = {}, False
        for cid, blob in re.findall(r'id="(\d+)_[^"]*-status_data"><p>(.*?)</p>', html, re.S):
            txt = re.sub(r"<[^>]+>", " ", blob)
            st = re.search(r"\b(Open|Closed|Waitlist|Cancelled|Tentative)\b", txt)
            if not st:
                continue                              # no status word -> skip, never guess
            status = st.group(1)
            spots = re.search(r"(\d+)\s+Spots?\s+Left", txt)
            seats = int(spots.group(1)) if spots else (0 if "Class Full" in txt else None)
            if cid in secs:
                dup = True
                break
            secs[cid] = {"open": status == "Open", "seats": seats}
        return None if dup else secs

    def fetch(self, courses):
        by_subj = {}
        for course in courses:
            subj, num = self._norm(course)
            if subj:
                by_subj.setdefault(subj, []).append((course, num))
        out = {}
        for subj, items in by_subj.items():
            try:
                models = self._subject_models(subj)
            except Exception:
                continue
            for course, num in items:
                model = models.get(num)
                if not model:
                    out[course] = {"none": {"open": False, "seats": None}}
                    continue
                try:
                    secs = self._sections(model)
                except Exception:
                    continue
                if secs is None:                      # duplicate class_id -> skip
                    continue
                out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class SFSU:
    """San Francisco State University public class schedule (webapps.sfsu.edu) — the
    official student-facing search, no auth/token. Two GETs per course sharing a cookie
    jar: (1) /results?searchFor=SUBJ+NUM primes the server session, (2) /searchresultsjson
    returns {"aaData":[[...13 cols...]]}. Column map (verified numerically): [0]=course
    label 'MATH 226 [53]', [4]=classNumber (UNIQUE per section — section key), [9]=seats
    available (int, already clamped >=0 on over-enrolled sections), [10]=capacity.

    open = seats>0 (standard Banner semantic — SFSU is PeopleSoft/CSU, auto-processes
    waitlists, so an available seat is a real one; waitlist counts live only on the
    detail page and aren't needed to decide open). Freshness is registrar-live (detail
    page timestamps 'Seats As of <minute>'). searchFor is an EXACT match (verified no
    sibling leak: 'ENG 114' returns only ENG 114), and rows are still scoped to the
    exact watched code from col[0] as a backstop. classCategory=REG only (CEL =
    continuing-ed catalog, excluded). Term auto-rolls from the search page's term radios
    ('2267' = Fall 2026, CSU strm coding)."""
    id = "sfsu"; name = "San Francisco State University"
    example = "MATH 226"
    term = "2267"                       # Fall 2026 (auto-rolls)
    _active_term = None
    root = "https://webapps.sfsu.edu/public/classservices/classsearch"
    _RE = re.compile(r"^([A-Za-z]{2,6})\s+(\d+[A-Za-z]{0,2})$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.root

    def resolve_term(self):
        """Nearest upcoming main term from the search page's term radios; None on
        failure. Summer excluded via label."""
        try:
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            op.addheaders = [("User-Agent", UA)]
            page = op.open(self.root, timeout=30).read().decode("utf-8", "replace")
            today = datetime.date.today()
            best, best_delta = None, None
            for code, label in re.findall(
                    r'name="classScheduleQuick\[term\]"[^>]*value="(\d{4})"[^>]*>\s*([^<]+)', page):
                sm = re.search(r"(fall|winter|spring)\s*(20\d\d)", label, re.I)
                if not sm:
                    continue
                season, year = sm.group(1).lower(), int(sm.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            want = f"{subj} {num}"
            try:
                cj = http.cookiejar.CookieJar()
                op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                op.addheaders = [("User-Agent", UA)]
                op.open(self.root + "/results?" + urllib.parse.urlencode(
                    {"searchFor": want, "term": self.cur_term(), "classCategory": "REG"}),
                    timeout=30).read()
                data = json.loads(op.open(
                    "https://webapps.sfsu.edu/public/classservices/searchresultsjson",
                    timeout=30).read().decode("utf-8", "replace"))
            except Exception:
                continue
            secs, dup = {}, False
            for row in data.get("aaData") or []:
                if len(row) < 13:
                    continue
                label = re.sub(r"<[^>]+>", "", str(row[0]))
                code = re.sub(r"\s*\[\d+\].*$", "", label).strip().upper()
                if code != want:                     # backstop: exact watched course only
                    continue
                key = str(row[4])
                try:
                    seats = int(row[9])
                except (TypeError, ValueError):
                    continue                          # no count -> skip, never guess
                if key in secs:
                    dup = True
                    break
                secs[key] = {"open": seats > 0, "seats": max(seats, 0)}
            if dup:
                continue
            out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class SacState:
    """Sacramento State (CSU) public class-schedule JSON API — no auth, plain GETs.
    ONE call per subject returns every course + all sections inline:
    GET classschedule.webhost.csus.edu/api/cs/{term-slug}/{SUBJ}. open = seats_available
    > 0 (standard Banner semantic); seat fields are numeric STRINGS (int-coerced, skip
    non-numeric — never guess).

    Multi-MEETING sections REPEAT the same class_number across rows (meeting_number 1/2/…)
    with IDENTICAL seats — verified 63 such dups in MATH, all seat-identical — so we
    DEDUPE by class_number (the unique section key) before keying, or one section would
    double-count. Status verified real via completed-term test (fall-2025 shows genuine
    closed sections). Term is a URL SLUG ('fall-2026'), built from the nearest upcoming
    term and verified against live data before adoption."""
    id = "sacstate"; name = "California State University, Sacramento"
    example = "CSC 10A"
    term = "fall-2026"                  # slug (auto-rolls)
    _active_term = None
    base = "https://classschedule.webhost.csus.edu/api/cs"
    _RE = re.compile(r"^([A-Za-z]{2,6})\s+(\d+[A-Za-z]{0,2})$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return "https://www.csus.edu/class-schedule/"

    def _get(self, path):
        return json.loads(_http(f"{self.base}/{path}"))

    def resolve_term(self):
        """Build the nearest-upcoming term slug ('fall-2026') and confirm the API serves
        it (the subject list is non-empty). Only 3 CSU main seasons use this schedule."""
        try:
            today = datetime.date.today()
            best, best_delta = None, None
            for season, mon in (("spring", 1), ("summer", 5), ("fall", 8)):
                for year in (today.year, today.year + 1):
                    delta = (year - today.year) * 12 + (mon - today.month)
                    if delta < -1:
                        continue
                    if best_delta is None or delta < best_delta:
                        best_delta, best = delta, f"{season}-{year}"
            if not best:
                return None
            return best if self._get(best) else None      # non-empty subject list == live
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        by_subj = {}
        for course in courses:
            subj, num = self._norm(course)
            if subj:
                by_subj.setdefault(subj, []).append((course, num))
        out = {}
        for subj, items in by_subj.items():
            try:
                data = self._get(f"{self.cur_term()}/{subj}")
            except Exception:
                continue
            courses_by_cat = {}
            for c in data:
                courses_by_cat[str(c.get("catalog_number", "")).upper()] = c.get("sections") or []
            for course, num in items:
                sections = courses_by_cat.get(num)
                if sections is None:
                    out[course] = {"none": {"open": False, "seats": None}}
                    continue
                secs = {}
                for s in sections:
                    key = str(s.get("class_number"))
                    if key in secs:                        # multi-meeting dup -> already keyed
                        continue
                    try:
                        avail = int(s.get("seats_available"))
                    except (TypeError, ValueError):
                        continue                           # no clean count -> skip
                    secs[key] = {"open": avail > 0, "seats": max(avail, 0)}
                out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class CSUN:
    """CSU Northridge — CSUN's OWN PeopleSoft schedule component
    (NR_SSS_COMMON_MENU.NR_SSS_SOC_BASIC_C.GBL), NOT the stock COMMUNITY_ACCESS classic
    search. This distinction matters for accuracy: the stock classic-PS guest view shows
    every section 'Open' even in finished terms (fake) and was scrapped; CSUN's custom
    component returns REAL availability — proven by a completed-term test (Fall 2025
    ENGL 115 = 43 Closed / 22 Open, genuine closed sections).

    Stateful flow: GET the .GBL entry TWICE with a shared cookie jar (1st bounces on the
    'ckreq' cookie check, 2nd serves the form), scrape ICSID + ICStateNum, then POST the
    exact-match search. Grid fields are per-row-indexed ($0,$1,...): CLASS_NBR (unique
    section key), DESCRSHORT ('Open'/'Closed'), AVAILABLE_SEATS (int). open = status
    'Open' AND seats>0 (double-safe; verified 66/66 consistent). Some subject codes carry
    spaces ('A E','A M') — passed verbatim. strm 2267 = Fall 2026 (CSU coding)."""
    id = "csun"; name = "California State University, Northridge"
    example = "ENGL 115"
    term = "2267"                       # Fall 2026 (auto-rolls)
    _active_term = None
    base = "https://cmsweb.csun.edu/psc/CNRPRD/EMPLOYEE/SA/c/NR_SSS_COMMON_MENU.NR_SSS_SOC_BASIC_C.GBL"
    _RE = re.compile(r"^([A-Za-z][A-Za-z /]{0,5}?)\s+(\d+[A-Za-z]{0,2})$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (re.sub(r"\s+", " ", m.group(1)).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.base

    def _form(self):
        """Double-GET (ckreq) then scrape the session tokens."""
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        op.open(self.base, timeout=30).read()
        h = op.open(self.base, timeout=30).read().decode("utf-8", "replace")
        icsid = re.search(r"id='ICSID' value='([^']+)'", h)
        state = re.search(r"id='ICStateNum'[^>]*value='(\d+)'", h)
        if not (icsid and state):
            raise RuntimeError("csun: no session tokens")
        return op, icsid.group(1), state.group(1)

    def resolve_term(self):
        """Nearest upcoming term's strm from the STRM dropdown; None on failure. CSU strm
        = 4 digits; anchored on the 'Fall 2026'-style option label."""
        try:
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            op.addheaders = [("User-Agent", UA)]
            op.open(self.base, timeout=30).read()          # ckreq bounce
            h = op.open(self.base, timeout=30).read().decode("utf-8", "replace")
            i = h.find("id='NR_SSS_SOC_NWRK_STRM'")
            if i < 0:
                return None
            today = datetime.date.today()
            best, best_delta = None, None
            for code, label in re.findall(r"""<option value=['\"](\d{4})['\"][^>]*>\s*([^<]+)""", h[i:i + 4000]):
                sm = re.search(r"(fall|winter|spring|summer)\D{0,10}(20\d\d)", label, re.I)
                if not sm or sm.group(1).lower() == "summer":
                    continue
                season, year = sm.group(1).lower(), int(sm.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    @staticmethod
    def _grid(html, field):
        return dict(re.findall(rf"{field}\$(\d+)'[^>]*>\s*([^<]+?)\s*<", html))

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                op, icsid, state = self._form()
                form = {"ICAction": "NR_SSS_SOC_NWRK_BASIC_SEARCH_PB", "ICSID": icsid,
                        "ICStateNum": state, "ICType": "Panel", "ICElementNum": "0",
                        "ICActionPrompt": "false", "NR_SSS_SOC_NWRK_STRM": self.cur_term(),
                        "GROUP": "1. Regular", "NR_SSS_SOC_NWRK_SUBJECT": subj,
                        "NR_SSS_SOC_NWRK_NR_SRCH_MATCH": "E",
                        "NR_SSS_SOC_NWRK_CATALOG_NBR_SRCH": num}
                html = op.open(urllib.request.Request(
                    self.base, data=urllib.parse.urlencode(form).encode()), timeout=45
                    ).read().decode("utf-8", "replace")
            except Exception:
                continue
            cn = self._grid(html, "NR_SSS_SOC_NSEC_CLASS_NBR")
            stt = self._grid(html, "NR_SSS_SOC_NWRK_DESCRSHORT")
            seat = self._grid(html, "NR_SSS_SOC_NWRK_AVAILABLE_SEATS")
            secs, dup = {}, False
            for i, key in cn.items():
                if i not in stt or i not in seat:
                    continue
                try:
                    sv = int(seat[i])
                except ValueError:
                    continue
                if key in secs:
                    dup = True
                    break
                # open ONLY when status says Open AND a seat is actually free (double-safe)
                secs[key] = {"open": stt[i].strip() == "Open" and sv > 0, "seats": max(sv, 0)}
            if dup:
                continue
            out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class UtahU:
    """University of Utah, Salt Lake City (~35k) — bespoke PUBLIC class-availability
    schedule (class-schedule.app.utah.edu), no login, server-rendered HTML, REAL numeric
    seats. One GET per subject returns every section as ordered div.col cells: CRN,
    Subject, CatalogNbr, Section, Title, Cap, WaitList, Enrolled, SeatsAvailable.
    open = SeatsAvailable > 0, seats = SeatsAvailable (verified == Cap-Enrolled 100%,
    live arithmetic not a sentinel). Section key = CRN (globally unique). Page is
    subject-wide -> filtered to the exact CatalogNbr.

    Freshness: server sends Cache-Control no-store/must-revalidate (generated per
    request, not a daily snapshot) — real-time. Status verified real via completed-term
    test (Fall 2025 MATH: 13 genuinely full sections). Note Utah's English/writing
    subject code is 'WRTG', not 'ENGL'. Term auto-rolls from the landing page's term
    list ('1268' = Fall 2026, PeopleSoft strm)."""
    id = "utah"; name = "University of Utah"
    example = "MATH 1050"
    term = "1268"                       # Fall 2026 (auto-rolls)
    _active_term = None
    root = "https://class-schedule.app.utah.edu"
    _RE = re.compile(r"^([A-Za-z]{2,6})\s+(\d+[A-Za-z]{0,2})$")
    _CELL_RE = re.compile(r'<div class="col[^"]*"[^>]*>\s*(.*?)\s*</div>', re.S)

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.root + "/"

    def resolve_term(self):
        """Nearest upcoming term's strm from the landing page's term list."""
        try:
            land = _http(self.root + "/")
            today = datetime.date.today()
            best, best_delta = None, None
            for code, label in re.findall(r"/main/(\d{4})/index\.html[^>]*>([^<]+)", land):
                sm = re.search(r"(spring|summer|fall|winter)\s*(20\d\d)", label, re.I)
                if not sm:
                    continue
                season, year = sm.group(1).lower(), int(sm.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        by_subj = {}
        for course in courses:
            subj, num = self._norm(course)
            if subj:
                by_subj.setdefault(subj, []).append((course, num))
        out = {}
        for subj, items in by_subj.items():
            try:
                html = _http(f"{self.root}/main/{self.cur_term()}/seating_availability.html?subject={subj}")
            except Exception:
                continue
            cells = [re.sub(r"<[^>]+>", "", c).strip() for c in self._CELL_RE.findall(html)]
            # collect this subject's sections, grouped by catalog number
            per_num = {}
            i, n = 0, len(cells)
            while i < n - 8:
                if re.fullmatch(r"\d{5}", cells[i]) and cells[i + 1].upper() == subj:
                    crn, cat = cells[i], cells[i + 2].upper()
                    try:
                        avail = int(cells[i + 8])
                    except ValueError:
                        i += 1
                        continue
                    per_num.setdefault(cat, {})[crn] = {"open": avail > 0, "seats": max(avail, 0)}
                    i += 9
                else:
                    i += 1
            for course, num in items:
                secs = per_num.get(num)
                out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class Purdue:
    """Purdue University, West Lafayette (~50k) — classic Banner 8 self-service
    (bwckschd, HTML scrape, guest-accessible). Same family as VirginiaTech but Purdue
    SUPPRESSES the seat table from the course listing, so seats need one detail GET per
    CRN. To avoid hammering Purdue with ~40 detail calls every poll cycle, each course's
    full section+seat map is built at most once per _TTL into a class-level cache and
    served from it (same pattern as TAMU; alerts lag at most _TTL).

    Real NUMERIC Banner seats: per-CRN detail page 'Availability' table gives Capacity /
    Actual / Remaining on the 'Seats' row (the 'Waitlist Seats' row is ignored). open =
    Remaining > 0, seats = Remaining (standard Banner semantic, consistent with the ~400
    other Banner schools; major-restrictions aren't parsed here, same as everywhere).
    Verified real via completed-term test (finished terms show genuinely full sections).
    Sections keyed by CRN (unique). Term auto-rolls from the dyn-sched OPTION list,
    skipping '(View only)' archive terms."""
    id = "purdue"; name = "Purdue University"
    example = "CS 18000"
    term = "202710"                     # Fall 2026 (auto-rolls)
    _TTL = 600                          # 10 min between per-course seat rebuilds
    base = "https://selfservice.mypurdue.purdue.edu/prod"
    _RE = re.compile(r"^([A-Za-z]{2,4})\s+(\d+[A-Za-z]{0,2})$")

    def __init__(self):
        # PER-INSTANCE state — mandatory once this class is subclassed for other Banner-8
        # schools. The cache key is (term, subj, num) with NO school id, so a shared cache
        # would serve one school's seats for another when term+subj+num coincide (e.g.
        # Toledo & SFA both on term 202710). Each instance gets its own cache/lock/term.
        self._active_term = None
        self._lock = threading.Lock()
        self._cache = {}                # (term, subj, num) -> (ts, {crn: {open, seats}})

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.base + "/bwckschd.p_disp_dyn_sched"

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        op.open(self.base + "/bwckschd.p_disp_dyn_sched", timeout=30).read()
        return op

    def resolve_term(self):
        """Nearest upcoming non-'(View only)' term from the dyn-sched OPTION list."""
        try:
            op = self._session()
            h = op.open(self.base + "/bwckschd.p_disp_dyn_sched", timeout=30).read().decode("utf-8", "replace")
            today = datetime.date.today()
            best, best_delta = None, None
            for code, desc in re.findall(r'<OPTION VALUE="(\d{6})"[^>]*>([^<]+)', h):
                if "view only" in desc.lower():
                    continue
                sm = re.search(r"(spring|summer|fall|winter)\s*(20\d\d)", desc, re.I)
                if not sm:
                    continue
                season, year = sm.group(1).lower(), int(sm.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self._build(new, *self._norm(self.example)))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def _listing(self, op, term, subj, num):
        """Section listing HTML for one course. Default = the class-schedule search form;
        ListcrseBanner8 overrides with the catalog route for hosts whose guest search
        form answers 'No classes were found' for everything."""
        form = [("term_in", term), ("sel_subj", "dummy"), ("sel_day", "dummy"),
                ("sel_schd", "dummy"), ("sel_insm", "dummy"), ("sel_camp", "dummy"),
                ("sel_levl", "dummy"), ("sel_sess", "dummy"), ("sel_instr", "dummy"),
                ("sel_ptrm", "dummy"), ("sel_attr", "dummy"), ("sel_subj", subj),
                ("sel_crse", num), ("sel_title", ""), ("sel_schd", "%"),
                ("sel_from_cred", ""), ("sel_to_cred", ""), ("sel_camp", "%"),
                ("sel_ptrm", "%"), ("sel_instr", "%"), ("sel_attr", "%"),
                ("begin_hh", "0"), ("begin_mi", "0"), ("begin_ap", "a"),
                ("end_hh", "0"), ("end_mi", "0"), ("end_ap", "a")]
        return op.open(urllib.request.Request(
            self.base + "/bwckschd.p_get_crse_unsec",
            data=urllib.parse.urlencode(form).encode()), timeout=45).read().decode("utf-8", "replace")

    def _section_ok(self, detail_html):
        """Hook: include this section's detail page? Default yes. CampusBanner8 overrides
        to keep ONLY its own campus on a shared multi-college host."""
        return True

    def _crns(self, listing, subj, num):
        """Extract this course's CRNs from the listing. Default = classic Banner-8
        title-line format ('- 12345 - SUBJ NUM - Title'). CRN is 4-5 digits (most hosts
        5, some like HGTC 4) — the surrounding '- ... - SUBJ NUM -' scoping keeps it exact.
        TabularBanner8 overrides for column-table listings with a bare CRN."""
        return re.findall(rf"- (\d{{4,5}}) - {re.escape(subj)}\s+{re.escape(num)} - ", listing)

    def _build(self, term, subj, num):
        """Listing -> CRNs, then one detail GET per CRN -> {crn: {open, seats}}. Caches on
        success; returns {} on failure (cache untouched)."""
        try:
            op = self._session()
            listing = self._listing(op, term, subj, num)
        except Exception:
            return {}
        crns = self._crns(listing, subj, num)
        if not crns:
            return {}
        secs = {}
        for crn in dict.fromkeys(crns):        # unique, preserve order
            try:
                d = op.open(self.base + f"/bwckschd.p_disp_detail_sched?term_in={term}&crn_in={crn}",
                            timeout=30).read().decode("utf-8", "replace")
            except Exception:
                continue                        # a missing detail -> skip that section, never guess
            if not self._section_ok(d):         # shared-host campus guard
                continue
            m = re.search(r'>Seats</SPAN></th>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(-?\d+)</td>', d)
            if not m:
                continue
            rem = int(m.group(3))
            secs[crn] = {"open": rem > 0, "seats": max(rem, 0)}
        if secs:
            self._cache[(term, subj, num)] = (time.time(), secs)
        return secs

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            key = (self.cur_term(), subj, num)
            cached = self._cache.get(key)
            if cached and time.time() - cached[0] < self._TTL:
                out[course] = cached[1]
                continue
            blocking = cached is None
            if not self._lock.acquire(blocking=blocking):
                out[course] = cached[1] if cached else {"none": {"open": False, "seats": None}}
                continue
            try:
                again = self._cache.get(key)
                if again and time.time() - again[0] < self._TTL:
                    secs = again[1]
                else:
                    secs = self._build(*key) or (again[1] if again else {})
            finally:
                self._lock.release()
            out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


# --- Batch 23: Banner-8 (bwckschd) real-seat schools on the Purdue adapter. Each sets its
# own `base` (host + base_path), term, and example; per-instance cache (Purdue.__init__)
# keeps them isolated. Real numeric Banner seats (Remaining = Capacity - Actual) — cannot be
# faked open. Only the 2 that gated FLAWLESS live shipped. The other 5 in the handoff
# (Missouri State, Toledo, Stephen F. Austin, Alabama A&M, Utica) were CUT: their guest Fall
# schedules returned "No classes were found" for EVERY subject probed (English/Math/Bio/Psy/
# Hist/Chem) — schedule not published to guest search yet. Revisit when their term loads.
class BristolCC(Purdue):
    id = "bristolcc"; name = "Bristol Community College"
    example = "ENG 101"; term = "202609"       # Fall 2026; 65 sec, 57 open/8 full, Rem==Cap-Act
    base = "https://selfservice.bristolcc.edu/PROD"

class Clovis(Purdue):
    id = "clovis"; name = "Clovis Community College (NM)"   # != Clovis CC (CA, State Center CCD)
    example = "ENGL 1110"; term = "202630"     # Fall 2026; 6 sec, Rem==Cap-Act verified
    base = "https://prodssb.clovis.edu/PROD"


class ListcrseBanner8(Purdue):
    """Banner-8 hosts whose guest CLASS-SEARCH form answers 'No classes were found' for
    EVERYTHING, while the catalog section-listing route (bwckctlg.p_disp_listcrse) serves
    the same sections fine (NCCU — and the same pattern showed live sections at the
    batch-23 cut hosts). CRN discovery becomes one GET; seats still come from the same
    per-CRN detail pages, same conservative parse, same per-instance cache."""
    def _listing(self, op, term, subj, num):
        return op.open(self.base + f"/bwckctlg.p_disp_listcrse?term_in={term}"
                       f"&subj_in={subj}&crse_in={num}&schd_in=",
                       timeout=45).read().decode("utf-8", "replace")

class NCCU(ListcrseBanner8):
    id = "nccu"; name = "North Carolina Central University"
    example = "BIOL 1100"; term = "202710"     # Fall 2026; detail pages Cap/Act/Rem verified
    base = "https://ssbprod-nccu.uncecs.edu/pls/NCCUPROD"

class WSSU(ListcrseBanner8):
    id = "wssu"; name = "Winston-Salem State University"   # NCCU's UNC-ECS sibling host
    example = "BIO 1113"; term = "202680"      # Fall 2026 HERE (per-host codes; labels win)
    base = "https://ssbprod-wssu.uncecs.edu/pls/WSSUPROD"

class MTSU(ListcrseBanner8):
    # ENGL 1010 is 147 sections -> ~42s cold N+1 build, then 10-min cache (0ms warm);
    # in line with the accepted TAMU/Purdue cache-backed pattern, lock-guarded.
    id = "mtsu"; name = "Middle Tennessee State University"
    example = "ENGL 1010"; term = "202680"     # Fall 2026 (completed Spring = 202610)
    base = "https://ssb.mtsu.edu/pls/PROD"

class ETSU(ListcrseBanner8):
    # base MUST be lowercase /pls/prod — uppercase /pls/PROD silently returns
    # "No classes found". TN sibling of MTSU on the same catalog route.
    id = "etsu"; name = "East Tennessee State University"
    example = "BIOL 1010"; term = "202680"     # Fall 2026; pro-school 202681/202682 pinned out
    base = "https://selfserv.etsu.edu/pls/prod"

class SEMO(ListcrseBanner8):
    # base MUST stay lowercase /prod (ETSU-style). EN 100 is heavy (67 sections, ~35s cold
    # then 10-min cache) but valid; kept as the canary. term 202710 = Fall 2026.
    id = "semo"; name = "Southeast Missouri State University"
    example = "EN 100"; term = "202710"; base = "https://banssb.semo.edu/prod"

class Cameron(ListcrseBanner8):
    # ORDS-served Banner 8 (base /ords/ssb). The GUEST-SEARCH route (plain Purdue) returns
    # "No classes found" here, so the CATALOG route (ListcrseBanner8) is required — it
    # parses cleanly (CRN extraction + Seats/Remaining detail table both standard). 1004 vs
    # 1004L (lab) are correctly separate. term 202710 = Fall 2026.
    id = "cameron"; name = "Cameron University"
    example = "BIOL 1004"; term = "202710"; base = "https://ssb.cameron.edu/ords/ssb"

class Lamar(ListcrseBanner8):
    # catalog route on /btdb (parses clean, not the Cameron /ords issue). term 202690
    # = Fall 2026 (per-host code). Remaining>0 rule.
    id = "lamar"; name = "Lamar University"   # != Lamar CC (Colorado)
    example = "ENGL 1301"; term = "202690"; base = "https://ssbprod.lamar.edu/btdb"

class IndianaState(ListcrseBanner8):
    # Guest class-search returns "No classes found" -> the catalog route is required, not
    # plain Purdue. base needs /pls/prod (bare /bwckschd 403s). 202605 = Fall 2026 (ISU
    # YYYYMM, 05=Fall); pinned (Summer 202603 also live), family pins anyway.
    id = "indianastate"; name = "Indiana State University"
    example = "MATH 131"; term = "202605"
    base = "https://prodinteract.indstate.edu/pls/prod"

class Framingham(ListcrseBanner8):
    id = "framingham"; name = "Framingham State University"
    example = "PSYC 101"; term = "202690"      # Fall 2026 HERE (per-host codes differ)
    base = "https://selfservice.framingham.edu/PROD"

class UNM(ListcrseBanner8):
    # UNM Albuquerque flagship (≠ Central/Highlands/Western NM). NM 4-DIGIT common-course
    # numbers (ENGL 1110, not 110). ENGL 1110 = 122 sections -> ~74s cold N+1 build then
    # 10-min cache (warm 0ms); Purdue/TAMU cache-backed envelope, lock-guarded.
    id = "unm"; name = "University of New Mexico"
    example = "ENGL 1110"; term = "202680"     # Fall 2026 (completed Spring = 202610)
    base = "https://lobowebapp.unm.edu/ban_ssb"

class WrightState(ListcrseBanner8):
    # Guest search form answers "No classes were found" for everything; catalog route
    # serves the same sections (ENG 1100 = 12+ CRNs live). Detail pages carry numeric
    # Cap/Act/Rem (Codex archived Fall full 15/15/0 + Spring 60/53/7 + over-cap -5;
    # re-gated live here before ship).
    id = "wrightstate"; name = "Wright State University"
    example = "ENG 1100"; term = "202680"      # Fall 2026 (Spring 2027 = 202730 not yet live)
    base = "https://wingsexpress.wright.edu/pls/PROD"

class RPI(ListcrseBanner8):
    # sis.rpi.edu catalog route. Live Fall is currently ALL-OPEN (RPI's cycle hasn't
    # filled yet) — the completed-term read through THIS exact parse shows real mixed
    # enrollment (Spring 202601: CSCI 2600 = 4 open/6 FULL), disproving fake-open at
    # host level per the NCCU/Shorter standard; all-open-now is an unfilled term, and
    # empty/skip stays safe by design until sections fill in August.
    id = "rpi"; name = "Rensselaer Polytechnic Institute"
    example = "CSCI 1100"; term = "202609"     # Fall 2026 (completed Spring = 202601)
    base = "https://sis.rpi.edu/rss"


class CampusBanner8(Purdue):
    """Banner-8 host shared by SEVERAL colleges in one district (Chabot-Las Positas), where
    the plain listing mixes campuses. TWO independent guards keep each school's sections
    separate (a watched CRN must be unambiguously one campus, never cross-alerted):
    (1) the search form's sel_camp=<code> returns only this campus's CRNs (live-verified
    disjoint: ENGL 1 Chabot=76/LasPositas=0, MATH 1 =0/44, zero overlap); (2) belt-and-
    suspenders, each CRN's detail page carries a structured '{Campus} College Campus' field
    that must equal this school's campus_name (the shared-district chrome names both
    colleges, so this is the ONE authoritative per-section signal). Subclass sets:
    id, name, example, campus (sel_camp code), campus_name."""
    campus = ""          # sel_camp code, e.g. 'C' / 'L'
    campus_name = ""     # exact structured-field name, e.g. 'Chabot' / 'Las Positas'
    _CAMPRE = re.compile(r'([A-Za-z][A-Za-z ]+?) College Campus')

    def _listing(self, op, term, subj, num):
        form = [("term_in", term), ("sel_subj", "dummy"), ("sel_day", "dummy"),
                ("sel_schd", "dummy"), ("sel_insm", "dummy"), ("sel_camp", "dummy"),
                ("sel_levl", "dummy"), ("sel_sess", "dummy"), ("sel_instr", "dummy"),
                ("sel_ptrm", "dummy"), ("sel_attr", "dummy"), ("sel_subj", subj),
                ("sel_crse", num), ("sel_title", ""), ("sel_schd", "%"),
                ("sel_from_cred", ""), ("sel_to_cred", ""), ("sel_camp", self.campus),
                ("sel_ptrm", "%"), ("sel_instr", "%"), ("sel_attr", "%"),
                ("begin_hh", "0"), ("begin_mi", "0"), ("begin_ap", "a"),
                ("end_hh", "0"), ("end_mi", "0"), ("end_ap", "a")]
        return op.open(urllib.request.Request(
            self.base + "/bwckschd.p_get_crse_unsec",
            data=urllib.parse.urlencode(form).encode()), timeout=45).read().decode("utf-8", "replace")

    def _section_ok(self, d):
        m = self._CAMPRE.search(d)
        return bool(m) and m.group(1).strip() == self.campus_name

class Chabot(CampusBanner8):
    id = "chabot"; name = "Chabot College"
    example = "ENGL 1"; term = "202602"        # Fall 2026 (shared clpccd host)
    base = "https://banssprod.clpccd.cc.ca.us/ssbprod"
    campus = "C"; campus_name = "Chabot"

class LasPositas(CampusBanner8):
    id = "laspositas"; name = "Las Positas College"   # LP uses its own numbering (MATH 1, STAT L40)
    example = "MATH 1"; term = "202602"
    base = "https://banssprod.clpccd.cc.ca.us/ssbprod"
    campus = "L"; campus_name = "Las Positas"


class TabularBanner8(ListcrseBanner8):
    """Banner-8 hosts whose catalog listing is a COLUMN TABLE (CRN | Subj | Crse | Sec,
    bare CRN as link text) instead of the classic '- CRN - SUBJ NUM - Title' line — so
    the base title-line CRN regex matched ZERO and these schools looked dead (seats=None)
    despite standard, parseable detail pages. Only CRN DISCOVERY differs; seats come from
    the same per-CRN detail parse. Scoping is STRICT — a CRN is kept only when its Subj AND
    Crse cells equal the request exactly (num '1010' never catches '1010L'/'10100'); a
    wrong-course CRN would false-alert, so exact-match is the guard, not a nicety."""
    _ROW = re.compile(r'crn_in=(\d{4,5})[^<]*</a></td>\s*'
                      r'<td[^>]*>(?:<abbr[^>]*>)?\s*([A-Za-z]{2,5})\s*(?:</abbr>)?\s*</td>\s*'
                      r'<td[^>]*>\s*([0-9A-Za-z]+)\s*</td>', re.I)

    def _crns(self, listing, subj, num):
        return [crn for crn, s, c in self._ROW.findall(listing)
                if s.upper() == subj and c.upper() == num]

class CCRI(TabularBanner8):
    id = "ccri"; name = "Community College of Rhode Island"
    example = "ENGL 1010"; term = "202630"      # Fall 2026
    base = "https://bannerweb.ccri.edu/pls/DORA"

class NCAT(ListcrseBanner8):
    # UNC-ECS host family (like NCCU/WSSU) — classic listing, plain ListcrseBanner8.
    id = "ncat"; name = "North Carolina A&T State University"
    example = "ENGL 100"; term = "202710"        # Fall 2026
    base = "https://ssbprod-ncat.uncecs.edu/pls/NCATPROD"

class HGTC(ListcrseBanner8):
    # classic listing BUT 4-digit CRNs (handled by the widened _crns pattern).
    id = "hgtc"; name = "Horry-Georgetown Technical College"
    example = "PSY 201"; term = "202610"         # Fall 2026
    base = "https://ssb.hgtc.edu/PROD9"


class SDCCD:
    """San Diego CCD — ONE public district JSON dump (mws-api.sdccd.edu) serves City/Mesa/
    Miramar; rows separated by CAMPUS. The whole dump (~4,200 rows, ~5.7MB, ~3s) is fetched
    ONCE per TTL into a SHARED class-level cache — all 3 campus subclasses read the same
    dump, so watching any SDCCD course costs at most one district fetch per 10 min, not
    three. Each school filters CAMPUS + SUBJECT + exact CATALOG_NBR. open = ENRL_STAT=='O'
    AND ENRL_CAP-ENRL_TOT>0 — TWO signals: the status enum AND a real unreserved seat, so a
    reserved-but-'closed' section (status C with positive raw capacity) is correctly
    withheld (Codex's reserved-seat flag). Waitlist (WAIT_*) ignored. Section key =
    CLASS_NBR. Subclass sets id, name, example, campus."""
    term = "2267"                 # Fall 2026 (PeopleSoft strm); pinned, bump per term
    campus = ""
    _API = "https://mws-api.sdccd.edu/?term=%s&career=ugrd"
    _TTL = 600
    _lock = threading.Lock()
    _dump = {}                    # term -> (ts, rows) — SHARED across the 3 campuses
    _RE = re.compile(r"^([A-Za-z]{2,5})\s*(\d{1,4}[A-Za-z]?)$")

    def cur_term(self):
        return self.term

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return "https://www.sdccd.edu/students/class-search/"

    def _rows(self):
        term = self.cur_term()
        with SDCCD._lock:
            c = SDCCD._dump.get(term)
            if c and time.time() - c[0] < self._TTL:
                return c[1]
            try:
                req = urllib.request.Request(self._API % term, headers={"User-Agent": UA})
                rows = json.loads(urllib.request.urlopen(req, timeout=40).read())["data"]["query"]["rows"]
            except Exception:
                return c[1] if c else []        # stale-if-error; never guess
            if isinstance(rows, list) and rows:
                SDCCD._dump[term] = (time.time(), rows)
                return rows
            return c[1] if c else []

    def fetch(self, courses):
        out = {}
        rows = None
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            if rows is None:
                rows = self._rows()
            secs = {}
            for r in rows:
                if r.get("CAMPUS") != self.campus:
                    continue
                if (r.get("SUBJECT") or "").upper() != subj:
                    continue
                if (r.get("CATALOG_NBR") or "").strip().upper() != num:   # ' 124' -> '124'
                    continue
                key = str(r.get("CLASS_NBR") or "")
                try:
                    remain = int(r.get("ENRL_CAP")) - int(r.get("ENRL_TOT"))
                except (TypeError, ValueError):
                    continue                     # no real counts -> skip, never guess
                if not key or key in secs:
                    continue
                secs[key] = {"open": r.get("ENRL_STAT") == "O" and remain > 0,
                             "seats": max(remain, 0)}
            if secs:
                out[course] = secs
        return out

class SanDiegoCity(SDCCD):
    id = "sdcity"; name = "San Diego City College"
    example = "MATH 121"; campus = "CITY"

class SanDiegoMesa(SDCCD):
    id = "sdmesa"; name = "San Diego Mesa College"
    example = "MATH 121"; campus = "MESA"

class SanDiegoMiramar(SDCCD):
    id = "sdmiramar"; name = "San Diego Miramar College"
    example = "BIOL 131"; campus = "MIRA"


class VCCCD:
    """Ventura County CCD — Moorpark / Oxnard / Ventura College (~37k) on ONE Django app
    (schedule.vcccd.edu). Its /filter/ POST IGNORES the subject filter and always returns
    the COMPLETE district catalog (~7.3MB embedded JSON), so we fetch it ONCE per TTL into
    a SHARED class-level cache and slice client-side by campus + course (Maricopa/SDCCD
    shape). Plain stdlib: GET / sets a Django csrftoken cookie; POST /filter/ echoes it in
    both the X-CSRFToken header and the csrfmiddlewaretoken field.

    Each JSON record: SUBJECT_CODE, COURSE_NUMBER (campus-specific — Moorpark ENGL M01A,
    Oxnard R101, Ventura V01A), COURSE_CRN, STATUS (OPEN/FULL/WAITLISTED, textual), and
    CAMPUS_DESC + CRSE_SEATS_AVAIL. CAMPUS ISOLATION = exact CAMPUS_DESC (live-verified
    100% coverage, ZERO cross-campus CRN collisions — cleaner than the Location-prefix a
    relay suggested, which left a ~5% residual). ⚠️ multi-MEETING sections repeat a CRN
    across records -> dedup by CRN. OPEN RULE: STATUS=='OPEN' AND CRSE_SEATS_AVAIL>0 (the
    two agreed on all 3,672 sampled rows). Section key = CRN. Term pinned (Fall 2026 =
    202607); bump per term."""
    term = "202607"                       # Fall 2026; pinned
    campus_desc = ""                      # 'Moorpark College' etc; subclass sets
    _TTL = 600
    _lock = threading.Lock()
    _cat = {}                             # term -> (ts, {(campus,subj,num): {crn: rec}})
    _OBJ = re.compile(r'\{"SUBJECT_CODE":.*?"RECORD_COUNT":\s*\d+\}')
    _RE = re.compile(r"^([A-Za-z]{2,5})\s*([A-Za-z]?\d+[A-Za-z]{0,2})$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self.term

    def reg_url(self, course):
        return "https://schedule.vcccd.edu/"

    def _catalog(self, term):
        with VCCCD._lock:
            c = VCCCD._cat.get(term)
            if c and time.time() - c[0] < self._TTL:
                return c[1]
            try:
                cj = http.cookiejar.CookieJar()
                op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
                op.addheaders = [("User-Agent", UA)]
                op.open("https://schedule.vcccd.edu/", timeout=30).read()
                tok = next((k.value for k in cj if k.name == "csrftoken"), None)
                if not tok:
                    return c[1] if c else {}
                form = {"csrfmiddlewaretoken": tok, "subjCombobox": "", "locCombobox": "",
                        "crse": "", "crn": "", "ctitle": "", "start_hh": "05", "start_mm": "00",
                        "start_ap": "a", "end_hh": "11", "end_mm": "00", "end_ap": "p",
                        "newc": "0", "noncrc": "0", "offc": "0", "mdCombobox": "", "pace": "0",
                        "ztc": "0", "geCombobox": "", "ge": "%", "csupport": "0", "term": term}
                req = urllib.request.Request("https://schedule.vcccd.edu/filter/",
                                             data=urllib.parse.urlencode(form).encode(),
                                             headers={"User-Agent": UA, "X-CSRFToken": tok,
                                                      "Referer": "https://schedule.vcccd.edu/"})
                resp = op.open(req, timeout=60).read().decode("utf-8", "replace")
            except Exception:
                return c[1] if c else {}             # stale-if-error; never guess
            index = {}
            for o in self._OBJ.findall(resp):
                try:
                    d = json.loads(o)
                except Exception:
                    continue
                subj, num, crn = d.get("SUBJECT_CODE"), d.get("COURSE_NUMBER"), d.get("COURSE_CRN")
                camp = d.get("CAMPUS_DESC")
                if not (subj and num and crn and camp):
                    continue
                index.setdefault((camp, subj, num.upper()), {}).setdefault(crn, d)  # dedup by CRN
            if index:
                VCCCD._cat[term] = (time.time(), index)
                return index
            return c[1] if c else {}

    def fetch(self, courses):
        cat = None
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            if cat is None:
                cat = self._catalog(self.cur_term())
            recs = cat.get((self.campus_desc, subj, num))
            if not recs:
                continue
            secs = {}
            for crn, d in recs.items():
                st = re.search(r"(OPEN|FULL|WAITLIST)", d.get("STATUS") or "")
                try:
                    avail = int(str(d.get("CRSE_SEATS_AVAIL")).strip())
                except (TypeError, ValueError):
                    continue                          # no count -> skip, never guess
                openb = bool(st) and st.group(1) == "OPEN" and avail > 0
                secs[str(crn)] = {"open": openb, "seats": max(avail, 0)}
            if secs:
                out[course] = secs
        return out

class Moorpark(VCCCD):
    id = "moorpark"; name = "Moorpark College"
    example = "ENGL M01A"; campus_desc = "Moorpark College"

class OxnardCollege(VCCCD):
    id = "oxnard"; name = "Oxnard College"
    example = "ENGL R101"; campus_desc = "Oxnard College"

class VenturaCollege(VCCCD):
    id = "venturacollege"; name = "Ventura College"
    example = "ENGL V01A"; campus_desc = "Ventura College"


class ClevelandState:
    """Cleveland State University — Jenzabar CampusNet, guest access (no login). One AJAX
    servlet returns an XML envelope whose CDATA holds an HTML class table.

    ⚠️ OPEN = Stat=='O' AND a real free seat. The seat pair is Enrl/Tot (enrolled /
    capacity), and a CANCELLED section (Stat=='X') shows 0/Tot — enrolled<capacity would
    read as maximally OPEN, so deriving open from the seat math alone false-alerts on
    every cancelled class (live-verified: all 14 MTH cancellations were 0/N). Stat is
    authoritative: O=open, C=full, X=cancelled -> fail closed. Requiring enr<tot too
    means an over-enrolled 'O' can never false-open either.

    ⚠️ Careers (UGRD/GRAD/LAW/CNED) are SEPARATE result sets — a subject's sections split
    across them (MTH: 84 undergrad + 7 grad; LAW lives only under LAW), so we query all
    four and merge by ClassNr (the unique key), or a grad/law watcher silently misses
    sections. catalognbr filters server-side to exactly one course, so each response is
    already course-scoped (no header-to-row association to parse).

    Future terms (118-Spring 2027, 119-Summer 2027) are already listed, so the term is
    PINNED and hand-bumped (auto_term off) — biasing late per the roll-off rule."""
    id = "clevelandstate"; name = "Cleveland State University"
    example = "MTH 167"
    host = "campusnet.csuohio.edu"
    term = "117-Fall 2026"                 # pinned; future terms already public
    auto_term = False
    _CAREERS = ("UGRD", "GRAD", "LAW", "CNED")
    _TTL = 120
    _lock = threading.Lock()
    _cache = {}                            # (subj, cat) -> (ts, {classnr: {open, seats}})
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{3}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self.term

    def reg_url(self, course):
        return f"https://{self.host}/guest/search_guest.jsp"

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        op.open(f"https://{self.host}/guest/search_guest.jsp", timeout=20).read()
        return op

    def _query(self, op, subj, cat, career):
        url = (f"https://{self.host}/AJAX/AJAXMasterServlet"
               "?AJAXClassName=AJAX.Ajax_ClassSearch&function=getClasessResults"
               f"&termVal={urllib.parse.quote(self.term)}&acadVal={career}"
               f"&subject={subj}&catalognbr={urllib.parse.quote(cat)}")
        raw = op.open(url, timeout=30).read().decode("utf-8", "replace")
        m = re.search(r"<!\[CDATA\[(.*?)\]\]>", raw, re.S)
        tbl = m.group(1) if m else ""
        out = {}
        for row in re.split(r"<tr[^>]*>", tbl):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            cells = [c for c in cells if c.strip()]
            # a class-header row LEADS with the numeric ClassNr; continuation rows (extra
            # meeting patterns) don't, so they're skipped and never overwrite the key
            if len(cells) < 4 or not re.match(r"^\d{3,6}$", cells[0]):
                continue
            sm = re.search(r"(\d+)\s*/\s*(\d+)", cells[-1])
            st = re.search(r"\b([OCX])\b", " ".join(cells[-3:]))
            if not (sm and st):
                continue                   # no seat pair or status -> skip, never guess
            enr, tot = int(sm.group(1)), int(sm.group(2))
            out[cells[0]] = {"open": st.group(1) == "O" and enr < tot,
                             "seats": max(tot - enr, 0)}
        return out

    def fetch(self, courses):
        out = {}
        op = None
        for course in courses:
            subj, cat = self._norm(course)
            if not subj:
                continue
            ckey = (subj, cat)
            with ClevelandState._lock:
                c = ClevelandState._cache.get(ckey)
            if c and time.time() - c[0] < self._TTL:
                if c[1]:
                    out[course] = dict(c[1])
                continue
            if op is None:
                try:
                    op = self._session()
                except Exception:
                    return out             # can't even prime a session -> silent
            merged = {}
            try:
                for career in self._CAREERS:
                    merged.update(self._query(op, subj, cat, career))
            except Exception:
                continue                   # fail-safe: skip this course, never partial-guess
            with ClevelandState._lock:
                ClevelandState._cache[ckey] = (time.time(), merged)
            if merged:
                out[course] = merged
        return out


class TennesseeTech:
    """Tennessee Tech — a CUSTOM Banner 8 package. The standard bwckschd/bwckctlg guest
    routes are DEAD here (empty/500), so this is bespoke: POST bwskttuclasses.P_DispClasses
    with my_term + my_subject returns the WHOLE subject as a flat labelled table, no
    session/reset needed. Columns: Subject | Course # | Section # | Call # | Title | Type
    | Credit Hrs | Days | Begin | End | Location | Enrollment | Seats Available | Max.

    open = 'Seats Available' > 0 (authoritative; clamp negatives to full). Key = Call #
    (CRN). One POST per subject covers every watched course in it -> cached by (term,
    subject); multi-meeting rows share a CRN and collapse in the CRN-keyed dict.

    Standard Banner term auto-detect can't be used (its routes are dead), so the term is
    PINNED and hand-bumped, like the ListcrseBanner8 siblings."""
    id = "tntech"; name = "Tennessee Technological University"
    example = "ENGL 1010"
    base = "https://ttuss1.tntech.edu/PROD"
    term = "202680"                        # Fall 2026; pinned (no auto-roll — routes dead)
    _TTL = 300
    _lock = threading.Lock()
    _cache = {}                            # (term, subj) -> (ts, {crn: {open, seats, num}})
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{3,4}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self.term

    def reg_url(self, course):
        return f"{self.base}/bwskttuclasses.P_DispClasses"

    def _subject(self, subj):
        """Whole-subject table -> {crn: {open, seats, num}}. Cached per (term, subject)."""
        key = (self.term, subj)
        with TennesseeTech._lock:
            c = TennesseeTech._cache.get(key)
            if c and time.time() - c[0] < self._TTL:
                return c[1]
        try:
            req = urllib.request.Request(
                f"{self.base}/bwskttuclasses.P_DispClasses",
                data=f"my_term={self.term}&my_subject={urllib.parse.quote(subj)}".encode(),
                headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                body = body.decode("utf-8", "replace")
        except Exception:
            return c[1] if c else {}       # transient -> last-known-good, never fabricate
        out = {}
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
                     for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            if len(cells) < 14 or cells[0] != subj:
                continue
            if not re.match(r"^\d{4,6}$", cells[3] or ""):   # col3 = Call#/CRN
                continue
            try:
                seats = int(cells[12])                       # col12 = Seats Available
            except (TypeError, ValueError):
                continue                   # no numeric count -> skip, never guess
            out[cells[3]] = {"open": seats > 0, "seats": max(seats, 0), "num": cells[1].upper()}
        if out:
            with TennesseeTech._lock:
                TennesseeTech._cache[key] = (time.time(), out)
        return out

    def fetch(self, courses):
        out = {}
        bysubj = {}
        for course in courses:
            subj, num = self._norm(course)
            if subj:
                bysubj.setdefault(subj, []).append((course, num))
        for subj, wanted in bysubj.items():
            table = self._subject(subj)
            for course, num in wanted:
                secs = {crn: {"open": v["open"], "seats": v["seats"]}
                        for crn, v in table.items() if v["num"] == num}
                if secs:
                    out[course] = secs
        return out


class TAMUCorpusChristi:
    """Texas A&M University-Corpus Christi — bespoke Banner-backed schedule app (standard
    Banner SSB paths 404). Form at GET /schedule/, results at POST /schedule/BPROD.php.
    Reachable only from some TLS stacks — the production poller handshakes it fine; some
    dev environments get SSLV3_ALERT_HANDSHAKE_FAILURE, so this is gated on the prod box.

    frmPrefix needs the full 'CODE-Description' option string (e.g. 'ACCT-Accounting'),
    scraped once from the form and cached {SUBJ: 'SUBJ-Desc'}; the description is truncated
    in the option so we keep the exact option string, never reconstruct it.

    ⚠️ ADDRESSABILITY — we must UNION the {term} x {campus} matrix or silently miss
    sections. Fall 2026 is THREE codes: 202609 (full term, ~2232 sections) + 202610
    (Fall-1 8-week mini) + 202611 (Fall-2 mini) — the minis carry accelerated graduate
    business courses (MGMT 5330, ACCT 5341, BAIS 5310…) that live in NO full-term code.
    And campus R (Firelands branch) carries ~50 general sections campus M lacks. A single
    202609/M query silently misses ~48 course-sections (live-verified). So fetch unions
    all _TERMS x campuses; CRNs are globally unique across the matrix (0 collisions
    verified), so the merge-by-CRN needs no special dedup. (Sub-terms 202610/202611 are
    empty on campus R, but we query the full matrix anyway — cheap insurance against a
    future term shuffling sections into a now-empty combo.)

    A section row's cells: [0]=CRN (unique key), [1]='SUBJ-NUM.SEC' (scope by NUM between
    '-' and '.'), [6]='Available / Capacity / WL'. open iff Available (1st int) > 0; the
    display clamps at 0, so an over-enrolled section shows 0 available = FULL (fail-closed).
    Terms pinned; hand-bump. Reachable only from some TLS stacks (prod poller handshakes it;
    some dev envs get SSLV3_ALERT_HANDSHAKE_FAILURE) — gate on the prod box."""
    id = "tamucc"; name = "Texas A&M University-Corpus Christi"
    example = "MATH 1314"
    base = "https://banner.tamucc.edu/schedule"
    term = "202609"                        # primary Fall term (cur_term / stale-guard)
    _TERMS = ("202609", "202610", "202611")   # full + Fall-1 + Fall-2 minis; union to avoid miss
    campuses = ("M", "R")                     # main + Firelands; both carry sections
    _TTL = 300
    _MAP_TTL = 21600
    _lock = threading.Lock()
    _cache = {}                            # (term, prefix_opt) -> (ts, {crn: {open,seats,num}})
    _prefixes = None                       # (ts, {SUBJ: "SUBJ-Description"})
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{3,4}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self.term

    def reg_url(self, course):
        return f"{self.base}/"

    def _get(self, url, data=None):
        headers = {"User-Agent": UA}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=(data.encode() if data else None), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body.decode("utf-8", "replace")

    def _prefix_map(self):
        with TAMUCorpusChristi._lock:
            c = TAMUCorpusChristi._prefixes
            if c and time.time() - c[0] < self._MAP_TTL:
                return c[1]
        try:
            page = self._get(f"{self.base}/")
        except Exception:
            return c[1] if c else {}
        m = {}
        # the form uses SINGLE-quoted option values (value='ACCT-Accounting'); match both
        for opt in re.findall(r"<option[^>]*value=['\"]([A-Z]{2,4}-[^'\"]+)['\"]", page):
            m.setdefault(opt.split("-", 1)[0], opt)      # SUBJ -> exact "SUBJ-Desc"; codes unique
        if m:
            with TAMUCorpusChristi._lock:
                TAMUCorpusChristi._prefixes = (time.time(), m)
        return m or (c[1] if c else {})

    def _parse(self, page, out):
        """Merge one BPROD.php result page's section rows into `out` (keyed by CRN)."""
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
                     for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
            if len(cells) < 7 or not re.match(r"^\d{5}$", cells[0] or ""):
                continue
            cm = re.match(r"^[A-Za-z]{2,4}-(\w+)\.", cells[1] or "")       # SUBJ-NUM.SEC
            am = re.match(r"^\s*(\d+)\s*/", cells[6] or "")                # Available / Cap / WL
            if not (cm and am):
                continue                    # no course-scope or no seat cell -> skip, never guess
            avail = int(am.group(1))
            out[cells[0]] = {"open": avail > 0, "seats": avail, "num": cm.group(1).upper()}

    def _subject(self, prefix_opt):
        """UNION every (term, campus) in the matrix — a section can live in a mini-term or
        the Firelands campus and nowhere else. Cached per subject."""
        key = prefix_opt
        with TAMUCorpusChristi._lock:
            c = TAMUCorpusChristi._cache.get(key)
            if c and time.time() - c[0] < self._TTL:
                return c[1]
        out = {}
        for term in self._TERMS:
            for campus in self.campuses:
                body = (f"frmTerm={term}&frmGroup=one&frmCampus={campus}"
                        f"&frmPrefix={urllib.parse.quote(prefix_opt)}&frmSelectSchedule=View ")
                try:
                    self._parse(self._get(f"{self.base}/BPROD.php", data=body), out)
                except Exception:
                    return c[1] if c else {}   # any leg failing -> last-known-good, never a
                                               # PARTIAL union (which would silent-miss)
        if out:
            with TAMUCorpusChristi._lock:
                TAMUCorpusChristi._cache[key] = (time.time(), out)
        return out

    def fetch(self, courses):
        out = {}
        pmap = None
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            if pmap is None:
                pmap = self._prefix_map()
            opt = pmap.get(subj)
            if not opt:
                continue
            secs = {crn: {"open": v["open"], "seats": v["seats"]}
                    for crn, v in self._subject(opt).items() if v["num"] == num}
            if secs:
                out[course] = secs
        return out


class Fairfield:
    """Fairfield University — public course-search API (course-search-net.fairfield.edu)
    returns the WHOLE catalog (~2,250 rows, ~1.7MB) with NO server-side term/course filter,
    and it's slow (~85s), so the dump is cached ONCE per TTL (lock-guarded, stale-if-error)
    and all filtering is client-side. Rows carry Course_Subject_Number ('ENGL 1101'),
    Section_Number, Section_Academic_Period (the term label), and Remaining_Seats — which
    the registrar treats as AUTHORITATIVE (over-cap sections read 'Enrolled_Capacity'
    33/31 with Remaining_Seats 0, correctly full; Remaining is never falsely positive). No
    reliable completed-term feed, so the disproof is the ~912 live full rows in the current
    term. open = int(Remaining_Seats) > 0; section key = Section_Number. Term self-maintains
    to the nearest 'Fall/Spring Semester 20YY' (the MAIN term — excludes Accelerated/Graduate
    sub-terms by exact prefix)."""
    _API = "https://course-search-net.fairfield.edu/api/course/courses"
    _TTL = 900                    # 15 min — the upstream is slow (~85s), fetch sparingly
    _lock = threading.Lock()
    _dump = None                  # (ts, rows)
    _RE = re.compile(r"^([A-Za-z]{2,5})\s*(\d{2,4}[A-Za-z]?)$")

    id = "fairfield"; name = "Fairfield University"; example = "ACCT 1011"

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return "https://course-search-net.fairfield.edu/"

    def _term(self):
        # nearest upcoming MAIN semester, matching the data's 'Season Semester YYYY' label
        t = datetime.date.today()
        if t.month <= 5:
            return f"Spring Semester {t.year}"
        return f"Fall Semester {t.year}"

    def _rows(self):
        with Fairfield._lock:
            c = Fairfield._dump
            if c and time.time() - c[0] < self._TTL:
                return c[1]
            try:
                req = urllib.request.Request(self._API, headers={"User-Agent": UA})
                data = json.loads(urllib.request.urlopen(req, timeout=120).read())
            except Exception:
                return c[1] if c else []
            if isinstance(data, list) and data:
                Fairfield._dump = (time.time(), data)
                return data
            return c[1] if c else []

    def fetch(self, courses):
        out = {}
        rows = None
        term = self._term()
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            if rows is None:
                rows = self._rows()
            want = f"{subj} {num}"
            secs = {}
            for r in rows:
                if not (r.get("Section_Academic_Period") or "").startswith(term):
                    continue
                if (r.get("Course_Subject_Number") or "").upper() != want:   # exact SUBJ NUM
                    continue
                key = str(r.get("Section_Number") or "")
                try:
                    rem = int(r.get("Remaining_Seats"))
                except (TypeError, ValueError):
                    continue                     # no real count -> skip, never guess
                if not key or key in secs:
                    continue
                secs[key] = {"open": rem > 0, "seats": max(rem, 0)}
            if secs:
                out[course] = secs
        return out

# --- batch-23 cuts RESURRECTED on the listcrse route (their guest search form answers
# 'No classes were found' for everything; the catalog route serves the same sections).
class MissouriState(ListcrseBanner8):
    id = "missouristate"; name = "Missouri State University"   # != Northwest Missouri State
    example = "ENG 110"; term = "202640"       # Fall 2026
    base = "https://prodssb.missouristate.edu/PROD"

class Toledo(ListcrseBanner8):
    id = "toledo"; name = "University of Toledo"
    example = "ENGL 1010"; term = "202640"     # Fall 2026 (202710 here = SPRING 2027)
    base = "https://selfservice.utoledo.edu/prod"

class SFAustin(ListcrseBanner8):
    id = "sfa"; name = "Stephen F. Austin State University"
    example = "ENGL 1301"; term = "202710"     # Fall 2026 in SFA's numbering
    base = "https://ssb.sfasu.edu/prod"

class AlabamaAM(ListcrseBanner8):
    id = "aamu"; name = "Alabama A&M University"
    example = "ENG 101"; term = "202670"       # Fall 2026
    base = "https://ssb1.aamu.edu/PROD"

class Utica(ListcrseBanner8):
    # Completed-term note: finished terms here show end-of-semester enrollment (post-drop
    # melt, no full rows), so the fake-open disproof is the LIVE term's real 18/18/0 full
    # sections — numeric Act==Cap can't be fabricated. Documented July 11 2026.
    id = "utica"; name = "Utica University"
    example = "ENG 101"; term = "202680"       # Fall 2026
    base = "https://bannerweb.utica.edu/PROD"


class Berkeley:
    """UC Berkeley — official public class pages (classes.berkeley.edu, Drupal). A quoted
    course search with the term facet returns the PRIMARY (enrollable) section pages;
    results are fuzzy, so sections are scoped by the slug fragment
    '-{subject-sans-spaces}-{number}-' (trailing dash: 1b can never match 1bl; spaced
    subjects slugify by deletion, POL SCI -> polsci, live-verified). Each section page
    embeds authoritative live enrollment JSON (ucb.enrollment.available.enrollmentStatus).

    RESERVED SEATS are why a naive seats adapter would false-alert here: a section can be
    'Open' with N seats where ALL N are cohort-reserved and unbookable by a general
    student (live-verified: BIOLOGY 1A = status O, 21 open, all 21 reserved). Rule:
    open = status 'O' AND (maxEnroll - enrolledCount - openReserved) > 0; seats = that
    unreserved remainder. Closed rows carry status 'C' (verified live, incl. completed-
    term rows with real mixed enrollment — not a fake-all-open source). Results cached
    per (term, course), 10-min TTL, per instance (one search + one GET per section per
    rebuild; alerts lag at most the TTL). Term facet auto-rolls from the search page's
    own term labels, verify-before-adopt."""
    id = "berkeley"; name = "University of California, Berkeley"
    example = "BIOLOGY 1B"
    term = "8588"                       # Fall 2026 facet id (auto-rolls)
    _TTL = 600
    _SITE = "https://classes.berkeley.edu"
    _RE = re.compile(r"^([A-Za-z][A-Za-z& ]*?)\s+([A-Za-z]{0,2}\d{1,4}[A-Za-z]{0,3})$")
    _JSON_RE = re.compile(r'data-drupal-selector="drupal-settings-json">(.*?)</script>', re.S)

    def __init__(self):
        self._lock = threading.Lock()
        self._cache = {}                # (term, subj, num) -> (ts, {sec: {open, seats}})
        self._active_term = None

    def cur_term(self):
        return self._active_term or self.term

    def _norm(self, course):
        m = self._RE.match(course.strip())
        if not m:
            return (None, None)
        return (re.sub(r"\s+", " ", m.group(1).strip()).upper(), m.group(2).upper())

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return self._SITE + "/"

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

    def _search(self, term, subj, num):
        q = urllib.parse.quote(f'"{subj} {num}"')
        return self._get(f"{self._SITE}/search/class?f%5B0%5D=term%3A{term}&search={q}")

    def resolve_term(self):
        """Nearest upcoming Fall/Spring from the search page's own term-facet labels."""
        try:
            h = self._search(self.cur_term(), *self._norm(self.example))
            today = datetime.date.today()
            best, best_delta = None, None
            for tid, blob in re.findall(
                    r'href="[^"]*f%5B1%5D=term%3A(\d+)[^"]*"[^>]*>(.{0,120}?)</a>', h, re.S):
                m = re.search(r"(Spring|Fall)\s+(20\d\d)", blob)
                if not m:
                    continue
                season, year = m.group(1).lower(), int(m.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, tid
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self._build(new, *self._norm(self.example)))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def _build(self, term, subj, num):
        try:
            h = self._search(term, subj, num)
        except Exception:
            return {}
        frag = "-" + subj.replace(" ", "").replace("&", "").lower() + "-" + num.lower() + "-"
        slugs = [s for s in dict.fromkeys(re.findall(r'href="(/content/[^"]+)"', h))
                 if frag in s]
        secs = {}
        for slug in slugs[:40]:                 # defensive cap; real courses sit far under
            try:
                m = self._JSON_RE.search(self._get(self._SITE + slug))
                e = ((((json.loads(m.group(1)).get("ucb") or {}).get("enrollment") or {})
                      .get("available") or {}).get("enrollmentStatus") or {})
                cap = int(e.get("maxEnroll"))
                enr = int(e.get("enrolledCount"))
                orv = int(e.get("openReserved") or 0)
            except Exception:
                continue                        # missing/odd detail -> skip, never guess
            code = ((e.get("status") or {}).get("code") or "")
            key = slug.rstrip("/").rsplit("-", 3)[-3]   # ...-1b-001-lec-001 -> '001'
            if key in secs:                     # collapse guard
                continue
            unres = cap - enr - orv             # seats a GENERAL student can actually take
            secs[key] = {"open": code == "O" and unres > 0, "seats": max(unres, 0)}
        if secs:
            self._cache[(term, subj, num)] = (time.time(), secs)
        return secs

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            key = (self.cur_term(), subj, num)
            cached = self._cache.get(key)
            if cached and time.time() - cached[0] < self._TTL:
                out[course] = cached[1]
                continue
            blocking = cached is None
            if not self._lock.acquire(blocking=blocking):
                out[course] = cached[1] if cached else {"none": {"open": False, "seats": None}}
                continue
            try:
                again = self._cache.get(key)
                if again and time.time() - again[0] < self._TTL:
                    secs = again[1]
                else:
                    secs = self._build(*key) or (again[1] if again else {})
            finally:
                self._lock.release()
            out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class CollegeScheduler:
    """College Scheduler (Civitas Learning) public Course Search GraphQL
    (api.collegescheduler.com) — institution scoped by the Origin header, no auth,
    no cookies. TWO traps, both live-verified July 12 2026:
    (1) findCourses is FUZZY/RANKED — query 'BIOL 101' ranks BIOL 221/211/201/240
        ABOVE 101, so edges are filtered to EXACT subject.shortName + courseNumber
        before the courseId is used (taking edge[0] = watching the wrong course).
    (2) getCourseSections paginates at 60 — Ivy Tech BIOL 101 is really 71 sections
        across 2 pages. Relay pageInfo/after is followed; if a course is STILL
        truncated at the defensive page cap, the course is skipped entirely (a
        watched section silently hidden by truncation must never be possible).
    open = openSeats > 0, seats = openSeats (clean numeric; live full rows verified
    per school — this family exposes no reliable completed term, same standard as
    SCF/Berkeley). Section key = registrationNumber (CRN, verified unique). Term
    auto-picks from the API's own courseSearchTerms list (nearest upcoming,
    verify-before-adopt via refresh_term). Subclass sets: id, name, example, slug."""
    example = ""
    slug = ""
    term = ""                            # pinned fallback; auto-rolls
    _API = "https://api.collegescheduler.com/graphql"
    _RE = re.compile(r"^([A-Za-z][A-Za-z& ]*?)\s+([A-Za-z]?\d{1,4}[A-Za-z]{0,2})$")

    def __init__(self):
        self._active_term = None

    def cur_term(self):
        return self._active_term or self.term

    def _norm(self, course):
        m = self._RE.match(course.strip())
        if not m:
            return (None, None)
        return (re.sub(r"\s+", " ", m.group(1).strip()).upper(), m.group(2).upper())

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return f"https://{self.slug}.search.collegescheduler.com/"

    def _gql(self, query):
        req = urllib.request.Request(self._API, data=json.dumps({"query": query}).encode(),
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": UA,
                                              "Origin": f"https://{self.slug}.search.collegescheduler.com"})
        return json.loads(urllib.request.urlopen(req, timeout=30).read())

    def resolve_term(self):
        """Nearest upcoming term from the API's own courseSearchTerms names."""
        try:
            d = self._gql('{ environment(name:"%s"){ courseSearchTerms{ code name } } }'
                          % self.slug)
            terms = (d.get("data") or {}).get("environment", {}).get("courseSearchTerms") or []
            today = datetime.date.today()
            best, best_delta = None, None
            for t in terms:
                nm = t.get("name") or ""
                # both orders live in this family: Ivy Tech 'Fall 2026', UTA '2026 Fall'
                m = (re.search(r"(spring|summer|fall|autumn|winter)\D{0,12}(20\d\d)", nm, re.I)
                     or re.search(r"(20\d\d)\D{0,12}(spring|summer|fall|autumn|winter)", nm, re.I))
                if not m:
                    continue
                g = m.groups()
                season, year = (g[0], g[1]) if g[0][0].isalpha() else (g[1], g[0])
                season = season.lower()
                mon = _SEASON.get(season if season != "autumn" else "fall", 8)
                delta = (int(year) - today.year) * 12 + (mon - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, str(t.get("code"))
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch([self.example]).get(self.example)) if self.example else False
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                term = self.cur_term()
                d = self._gql('{ environment(name:"%s"){ findCourses(termCode:"%s", '
                              'query:"%s %s", includeFullCourses:true, first:20){ edges{ '
                              'node{ id courseNumber subject{ shortName } } } } } }'
                              % (self.slug, term, subj, num))
                edges = ((d.get("data") or {}).get("environment", {})
                         .get("findCourses", {}) or {}).get("edges") or []
                # fuzzy-rank trap: EXACT subject+number only, never edge[0]
                cid = next((e["node"]["id"] for e in edges
                            if (e["node"]["subject"] or {}).get("shortName", "").upper() == subj
                            and str(e["node"].get("courseNumber", "")).upper() == num), None)
                if not cid:
                    continue
                secs, cursor = {}, ""
                for _page in range(6):               # 360 sections max, then bail out
                    after = ', after:"%s"' % cursor if cursor else ""
                    d = self._gql('{ environment(name:"%s"){ getCourseSections('
                                  'courseId:"%s", includeFullSections:true, first:60%s){ '
                                  'pageInfo{ hasNextPage endCursor } edges{ node{ '
                                  'registrationNumber openSeats totalSeats } } } } }'
                                  % (self.slug, cid, after))
                    g = ((d.get("data") or {}).get("environment", {})
                         .get("getCourseSections", {}) or {})
                    for e in g.get("edges") or []:
                        n = e.get("node") or {}
                        key = str(n.get("registrationNumber") or "")
                        try:
                            open_seats = int(n.get("openSeats"))
                        except (TypeError, ValueError):
                            continue                 # no real count -> skip, never guess
                        if not key or key in secs:   # collapse guard
                            continue
                        secs[key] = {"open": open_seats > 0, "seats": max(open_seats, 0)}
                    pi = g.get("pageInfo") or {}
                    if not pi.get("hasNextPage"):
                        break
                    cursor = pi.get("endCursor") or ""
                    if not cursor:
                        break
                else:
                    continue                         # STILL truncated at cap -> skip course
                if secs:
                    out[course] = secs
            except Exception:
                continue
        return out


class IvyTech(CollegeScheduler):
    id = "ivytech"; name = "Ivy Tech Community College"
    example = "BIOL 101"; slug = "ivytech"; term = "202620"

class UTArlington(CollegeScheduler):
    id = "uta"; name = "University of Texas at Arlington"
    example = "BIOL 1441"; slug = "uta"; term = "2268"

class UAlaska(CollegeScheduler):
    # One system-wide entry (UAF/UAA/UAS share the environment); sections are CRN-keyed
    # and campus-unique, so a student watching their CRN gets exactly their section.
    id = "alaska"; name = "University of Alaska"
    example = "BIOL F111L"; slug = "alaska"; term = "202603"


class UOregon:
    """University of Oregon — public DuckWeb class schedule (duckweb.uoregon.edu). NOT
    standard Banner-8: the per-CRN detail route parses inconsistently (some sections show
    seats, some don't — a silent-miss trap), so seats are read from the LISTING instead,
    which carries an authoritative 'Avail' column (header-confirmed: CRN | Avail | Max |
    ...). One POST per course to hwskdhnt.P_ListCrse (no N+1), then per section:
    open = Avail > 0, seats = Avail, key = CRN. EXACT-course scoping is mandatory (the
    result groups sections under a colspan course-title cell 'SUBJ NUM Title'; only the
    group whose code == the requested 'SUBJ NUM' is read — a search can render neighbor
    courses in a summary line). Numeric Avail can't fake open; verified real open/full mix
    live AND in a completed term. NOTE Oregon renames some courses with a 'Z' suffix
    (MATH 251 -> 251Z, WR 121 -> 121Z) — enter the exact catalog code. {} on any failure."""
    # QUARTER CALENDAR — auto_term is OFF. The shared season model dates a term by one
    # nominal month per season and cannot express a quarter year: "Winter 2027" runs
    # Jan-Mar 2027, not December. _auto_season therefore refuses winter outright, which
    # leaves this school jumping Fall -> Spring and silently skipping the whole winter
    # quarter (gate-verified on UCLA: 26F -> 27S on Oct 1). Holding the pinned term and
    # bumping it by hand is the honest trade until a per-adapter quarter month-map lands.
    auto_term = False
    id = "uoregon"; name = "University of Oregon"
    example = "MATH 251Z"
    term = "202601"                      # Fall 2026 (DuckWeb code; bumped by hand — see auto_term)
    _active_term = None
    _BASE = "https://duckweb.uoregon.edu/duckweb"
    _RE = re.compile(r"^([A-Za-z][A-Za-z ]*?)\s+(\d{2,3}[A-Za-z]?)$")
    _GROUP_RE = re.compile(r'<td colspan="\d+"[^>]*>(?:<[^>]+>)*\s*([A-Z]{2,4}\s+\d{2,3}[A-Z]?)\s')

    def cur_term(self):
        return self._active_term or self.term

    def _norm(self, course):
        m = self._RE.match(course.strip())
        if not m:
            return (None, None)
        return (re.sub(r"\s+", " ", m.group(1).strip()).upper(), m.group(2).upper())

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return f"{self._BASE}/hwskdhnt.p_search?term={self.cur_term()}"

    def _listing(self, op, term, subj, num):
        op.open(self._BASE + f"/hwskdhnt.p_search?term={term}", timeout=25).read()
        form = [("term_in", term)] + [(k, "dummy") for k in (
            "sel_subj", "sel_day", "sel_schd", "sel_insm", "sel_camp", "sel_levl",
            "sel_sess", "sel_instr", "sel_ptrm", "sel_attr", "sel_cred", "sel_tuition",
            "sel_open", "sel_weekend")] + [
            ("sel_subj", subj), ("sel_crse", num), ("sel_crn", ""), ("sel_title", ""),
            ("sel_from_cred", ""), ("sel_to_cred", ""),
            ("begin_hh", "0"), ("begin_mi", "0"), ("begin_ap", "a"),
            ("end_hh", "0"), ("end_mi", "0"), ("end_ap", "a"),
            ("submit_btn", "Show Classes")]
        return op.open(urllib.request.Request(
            self._BASE + "/hwskdhnt.P_ListCrse",
            data=urllib.parse.urlencode(form).encode()), timeout=30).read().decode("utf-8", "replace")

    def _parse(self, h, subj, num):
        want = f"{subj} {num}"
        txt = h.replace("&nbsp;", " ")
        bounds = [(m.start(), m.group(1).strip().upper()) for m in self._GROUP_RE.finditer(txt)]
        secs = {}
        for i, (pos, code) in enumerate(bounds):
            if code != want:                        # exact-course scope, never a neighbor
                continue
            end = bounds[i + 1][0] if i + 1 < len(bounds) else len(txt)
            block = txt[pos:end]
            for m in re.finditer(r'crn=(\d{5})\b', block):
                crn = m.group(1)
                cells = re.findall(r'<td[^>]*>\s*(-?\d+)\s*</td>', block[m.end():m.end() + 400])
                if len(cells) >= 2 and crn not in secs:   # [Avail, Max]; no count -> skip
                    avail = int(cells[0])
                    secs[crn] = {"open": avail > 0, "seats": max(avail, 0)}
        return secs

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        return op

    def resolve_term(self):
        """Nearest upcoming Fall/Spring from the public term list (season-labeled)."""
        try:
            op = self._session()
            h = op.open("https://classes.uoregon.edu/", timeout=20).read().decode("utf-8", "replace")
            today = datetime.date.today()
            best, best_delta = None, None
            for code, season, year in re.findall(
                    r'term=(\d{6})"[^>]*>\s*(Spring|Summer|Fall|Winter)\s+(20\d\d)', h):
                mon = _SEASON.get(season.lower(), 8)
                delta = (int(year) - today.year) * 12 + (mon - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch([self.example]).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        try:
            op = self._session()
        except Exception:
            return {}
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                h = self._listing(op, self.cur_term(), subj, num)
                secs = self._parse(h, subj, num)
                if secs:
                    out[course] = secs
            except Exception:
                continue
        return out


class UNCAsheville:
    """UNC Asheville — official public class-schedules JSON API (meteor.unca.edu). One
    GET per term returns EVERY section (~800 rows) with numeric enrollment and an
    authoritative Classification.Open flag; at gate time the flag agreed with
    EnrollmentMax - EnrollmentCurrent arithmetic on 1,654/1,654 rows across a LIVE and a
    COMPLETED term, and CRNs were unique in both. open = Open flag AND positive remaining
    (two independent signals — never seats alone, never flag alone). The whole-term
    response is cached per instance (10-min TTL, lock-guarded, stale-if-error) so polling
    many courses costs one upstream GET per TTL. Sections keyed by CRN."""
    id = "unca"; name = "University of North Carolina Asheville"
    example = "BIOL 344"
    _TTL = 600
    _API = "https://meteor.unca.edu/registrar/class-schedules/api/v1/courses"
    _RE = re.compile(r"^([A-Za-z]{2,5})\s+(\d{2,4}[A-Za-z]?)$")

    def __init__(self):
        self._lock = threading.Lock()
        self._cache = None            # (ts, (year, season), rows)

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return "https://www.unca.edu/class-schedules/"

    @staticmethod
    def _term():
        # Nearest registration-relevant term: spring through March, next spring from
        # November, fall otherwise. A wrong pick fails SAFE (empty dump -> no alerts).
        t = datetime.date.today()
        if t.month <= 3:
            return (t.year, "spring")
        if t.month >= 11:
            return (t.year + 1, "spring")
        return (t.year, "fall")

    def _rows(self):
        term = self._term()
        with self._lock:
            c = self._cache
            if c and c[1] == term and time.time() - c[0] < self._TTL:
                return c[2]
            try:
                req = urllib.request.Request(f"{self._API}/{term[0]}/{term[1]}",
                                             headers={"User-Agent": UA})
                rows = json.loads(urllib.request.urlopen(req, timeout=30).read())
            except Exception:
                rows = None
            if isinstance(rows, list) and rows:
                self._cache = (time.time(), term, rows)
                return rows
            return c[2] if c and c[1] == term else []   # stale-if-error; never guess

    def fetch(self, courses):
        out = {}
        rows = None
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            if rows is None:
                rows = self._rows()
            want = f"{subj} {num}."          # trailing dot: 'BIOL 344.' never matches 3440
            secs = {}
            for r in rows:
                if not (r.get("Code") or "").upper().startswith(want):
                    continue
                crn = r.get("CRN")
                try:
                    remain = int(r.get("EnrollmentMax")) - int(r.get("EnrollmentCurrent"))
                except (TypeError, ValueError):
                    continue                 # no real numbers -> skip, never guess
                if crn is None or str(crn) in secs:
                    continue
                is_open = bool((r.get("Classification") or {}).get("Open"))
                secs[str(crn)] = {"open": is_open and remain > 0, "seats": max(remain, 0)}
            if secs:
                out[course] = secs
        return out


class IowaState:
    """Iowa State University public class-search JSON API (api.classes.iastate.edu) — no
    auth. Term auto-detects via the academic-periods endpoint's `isCurrent` flag. One
    POST per course returns the course + its sections with REAL integer openSeats.
    open = openSeats > 0 (Banner semantic). courseNumber SUBSTRING-matches ('150' also
    returns '1500'), so results are filtered to the EXACT 'SUBJ NUM' before reading
    sections. Sections keyed by their unique id. Status verified real via completed-term
    test. The search POST requires ALL keys present and arrays as [] (null -> 500)."""
    id = "iowastate"; name = "Iowa State University"
    example = "MATH 1660"
    term = "ACADEMIC_PERIOD-2026Fall"   # auto-detected via isCurrent
    _active_term = None
    _api = "https://api.classes.iastate.edu/api"
    _RE = re.compile(r"^([A-Za-z]{2,6})\s+(\d+[A-Za-z]{0,2})$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return "https://classes.iastate.edu/"

    def _post(self, path, body):
        req = urllib.request.Request(self._api + path, data=json.dumps(body).encode(),
                                     headers={"User-Agent": UA, "Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace"))

    def resolve_term(self):
        try:
            d = json.loads(_http(self._api + "/academic-periods"))
            cur = [p for p in d.get("data", []) if p.get("isCurrent")]
            return cur[0]["id"] if cur else None
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            want = f"{subj} {num}"
            body = {"academicPeriodId": self.cur_term(), "courseSubject": subj,
                    "courseNumber": num, "level": None, "requirement": None,
                    "instructor": None, "semesterTag": None, "credits": None,
                    "openSeats": False, "daysOfTheWeek": [], "sectionStartDate": None,
                    "sectionEndDate": None, "title": None, "deliveryMode": None,
                    "allowedGradingBases": []}
            try:
                d = self._post("/courses/search", body)
            except Exception:
                continue
            match = next((c for c in d.get("data", [])
                          if (c.get("number") or "").upper() == want), None)   # exact, not substring
            if not match:
                out[course] = {"none": {"open": False, "seats": None}}
                continue
            secs, dup = {}, False
            for s in match.get("sections") or []:
                key = str(s.get("id"))
                try:
                    avail = int(s.get("openSeats"))
                except (TypeError, ValueError):
                    continue
                if key in secs:
                    dup = True
                    break
                secs[key] = {"open": avail > 0, "seats": max(avail, 0)}
            if dup:
                continue
            out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class TAMU:
    """Texas A&M University, College Station (~58k) public class search
    (howdyportal.tamu.edu). Its API IGNORES all filters and always returns the ENTIRE
    term (~21.7k rows / ~34MB / ~31s), so a per-poll fetch is impossible — instead the
    full term is pulled at most once per _TTL into a CLASS-LEVEL cache, and individual
    watched-course lookups are served from it.

    Concurrency: the poller fetches schools on a thread pool, so a lock ensures only ONE
    thread ever runs the 31s dump; concurrent callers get the (stale) cached copy rather
    than piling up duplicate 34MB fetches. Status-only: STUSEAT_OPEN is 'Y'/'N' (seat
    counts are 'NA' for public queries), open = 'Y', seats=None — verified REAL via
    completed-term tests (finished terms show ~50/50 Y/N, not fake all-open). Sections
    keyed by CRN (globally unique). Term auto-rolls from /api/all-terms, filtered to the
    '- College Station' campus variant (Galveston/Qatar/Half-Year excluded)."""
    id = "tamu"; name = "Texas A&M University"
    example = "ENGL 104"
    term = "202631"                     # Fall 2026 - College Station (auto-rolls)
    _active_term = None
    _TTL = 1200                         # 20 min between full-term dumps
    _lock = threading.Lock()
    _cache = {}                         # term -> (timestamp, {(subj,num): {crn: {...}}})
    _portal = "https://howdyportal.tamu.edu"
    _RE = re.compile(r"^([A-Za-z]{2,6})\s+(\d+[A-Za-z]{0,2})$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self._portal + "/uPortal/p/public-class-search-ui.ctf1/max/render.uP"

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        op.open(self.reg_url(""), timeout=30).read()
        return op

    def resolve_term(self):
        """Nearest upcoming '- College Station' term from /api/all-terms; None on fail."""
        try:
            op = self._session()
            terms = json.loads(op.open(urllib.request.Request(
                self._portal + "/api/all-terms", headers={"User-Agent": UA}), timeout=30).read())
            today = datetime.date.today()
            best, best_delta = None, None
            for t in terms:
                desc = t.get("STVTERM_DESC") or ""
                if "College Station" not in desc:
                    continue
                sm = re.search(r"(spring|summer|fall|winter)\s*(20\d\d)", desc, re.I)
                if not sm:
                    continue
                season, year = sm.group(1).lower(), int(sm.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, t.get("STVTERM_CODE")
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        if self._build_index(new):          # only adopt if the dump has real rows
            if log:
                log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")
        else:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")

    def _build_index(self, term):
        """The 31s full-term dump -> {(subj,num): {crn: {open, seats:None}}}. Caches on
        success and returns the index; returns {} on failure (cache untouched)."""
        try:
            op = self._session()
            req = urllib.request.Request(self._portal + "/api/course-sections",
                data=json.dumps({"startRow": 0, "endRow": 0, "termCode": term,
                                 "publicSearch": "Y"}).encode(),
                headers={"User-Agent": UA, "Content-Type": "application/json"})
            rows = json.loads(op.open(req, timeout=120).read().decode("utf-8", "replace"))
        except Exception:
            return {}
        if not rows:
            return {}
        idx = {}
        for r in rows:
            subj = (r.get("SWV_CLASS_SEARCH_SUBJECT") or "").upper()
            num = str(r.get("SWV_CLASS_SEARCH_COURSE") or "").upper()
            crn = str(r.get("SWV_CLASS_SEARCH_CRN") or "")
            if not (subj and num and crn):
                continue
            idx.setdefault((subj, num), {})[crn] = {
                "open": r.get("STUSEAT_OPEN") == "Y", "seats": None}
        self._cache[term] = (time.time(), idx)
        return idx

    def _index(self):
        """Return a course index for the current term, refreshing the cache at most once
        per _TTL. Only one thread does the expensive dump; others use the stale copy."""
        term = self.cur_term()
        now = time.time()
        cached = self._cache.get(term)
        if cached and now - cached[0] < self._TTL:
            return cached[1]
        # stale/cold: one thread refreshes. If another is already on it and we have a
        # stale copy, use the stale copy immediately instead of blocking/duplicating.
        blocking = cached is None
        if not self._lock.acquire(blocking=blocking):
            return cached[1] if cached else {}
        try:
            cached = self._cache.get(term)                 # re-check after acquiring
            if cached and time.time() - cached[0] < self._TTL:
                return cached[1]
            idx = self._build_index(term)
            if idx:
                return idx
            return cached[1] if cached else {}             # refresh failed -> keep stale
        finally:
            self._lock.release()

    def fetch(self, courses):
        idx = self._index()
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            secs = idx.get((subj, num))
            out[course] = dict(secs) if secs else {"none": {"open": False, "seats": None}}
        return out


class Iowa:
    """Bespoke adapter for the University of Iowa's public MAUI API. One call per
    DEPARTMENT returns every section with an authoritative sectionStatus
    ('Open'/'Pending'/'MAUI Waitlist'/'Closed'). We treat ONLY 'Open' as open
    (conservative). seats=None (public MAUI hides counts). Groups requested courses
    by department so each department is fetched once. ~30k students, #100.
    Fail-safe: {} on any error, so a broken fetch is silent, never false."""
    id = "uiowa"
    name = "University of Iowa"
    example = "CS 1210"
    legacy = "20263"   # Fall 2026 (MAUI legacyCode; from the public sessions list)
    _url = "https://api.maui.uiowa.edu/maui/api/pub/registrar/sections/{lc}/{dept}"

    @staticmethod
    def _code(course):
        m = re.match(r"^([A-Za-z]{2,5})[\s:]+(\d{4})$", course.strip())
        return (m.group(1).upper(), m.group(2)) if m else (None, None)

    def valid_course(self, course):
        return self._code(course)[0] is not None

    def reg_url(self, course):
        return "https://myui.uiowa.edu/my-ui/courses/dashboard.page"

    def fetch(self, courses):
        by_dept = {}
        for course in courses:
            dept, num = self._code(course)
            if dept:
                by_dept.setdefault(dept, {})[num] = course
        out = {}
        for dept, wanted in by_dept.items():
            try:
                rows = json.loads(_http(self._url.format(lc=self.legacy, dept=dept)))
            except Exception:
                continue                       # fail-safe: silence, never false data
            for r in rows:
                num = str(r.get("course"))
                if num not in wanted:
                    continue
                sec, status = r.get("section"), r.get("sectionStatus")
                if sec and status:
                    out.setdefault(wanted[num], {})[str(sec)] = {
                        "open": status == "Open", "seats": None}
        return out


class Wisconsin:
    """Bespoke adapter for UW-Madison's public enrollment API — the best kind of
    source: it reports both an authoritative status (OPEN/WAITLISTED/CLOSED) AND an
    exact availableSeats count. One search + one packages call per course. Open iff
    status == 'OPEN'. seats = availableSeats (real integer). ~44k students, #38.
    Fail-safe: {} on any error / bad data, so a broken fetch is silent, never false."""
    id = "wisc"
    name = "University of Wisconsin–Madison"
    example = "COMP SCI 300"
    term = "1272"   # Fall 2026 (from the public term list; termCode)
    _search = "https://public.enroll.wisc.edu/api/search/v1"
    _pkgs = "https://public.enroll.wisc.edu/api/search/v1/enrollmentPackages/{t}/{subj}/{cid}"

    @staticmethod
    def _norm(course):
        m = re.match(r"^([A-Za-z][A-Za-z ]*?)\s+(\d{2,3}[A-Za-z]?)$", course.strip())
        return f"{m.group(1).upper()} {m.group(2).upper()}" if m else None

    def valid_course(self, course):
        return self._norm(course) is not None

    def reg_url(self, course):
        return "https://public.enroll.wisc.edu/search"

    def fetch(self, courses):
        out = {}
        for course in courses:
            desig = self._norm(course)
            if not desig:
                continue
            try:
                body = json.dumps({"selectedTerm": self.term, "queryString": desig,
                                   "filters": [], "page": 1, "pageSize": 15,
                                   "sortOrder": "SCORE"}).encode()
                req = urllib.request.Request(self._search, data=body,
                                             headers={"User-Agent": UA,
                                                      "Content-Type": "application/json",
                                                      "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    hits = json.loads(r.read().decode("utf-8", "replace")).get("hits", [])
                hit = next((h for h in hits
                            if (h.get("courseDesignation") or "").upper() == desig), None)
                if not hit:
                    continue
                subj = hit.get("subject", {}).get("subjectCode")
                cid = hit.get("courseId")
                url = self._pkgs.format(t=self.term, subj=subj, cid=cid)
                pkgs = json.loads(_http(url))
            except Exception:
                continue                       # fail-safe: silence, never false data
            secs = {}
            for p in pkgs:
                es = p.get("packageEnrollmentStatus") or {}
                status = es.get("status")
                seatsraw = es.get("availableSeats")
                slist = p.get("sections") or []
                if not slist or status is None:
                    continue
                key = "".join(f"{s.get('type','')}{s.get('sectionNumber','')}" for s in slist)
                try:
                    n = int(seatsraw)
                except (TypeError, ValueError):
                    n = None
                is_open = status == "OPEN"
                if n is not None and is_open != (n > 0):   # sanity: status must match count
                    continue
                secs[key] = {"open": is_open, "seats": max(n, 0) if n is not None else None}
            if secs:
                out[course] = secs
        return out


# ===========================================================================
# ===========================================================================
class Penn:
    id = "penn"
    name = "University of Pennsylvania"
    example = "CIS 1200"
    sem = "2026C"   # Fall 2026

    @staticmethod
    def _code(course):
        m = re.match(r"^([A-Za-z]{2,4})[\s-]*(\d{3,4})$", course.strip())
        return f"{m.group(1).upper()}-{m.group(2)}" if m else None

    def valid_course(self, course):
        return self._code(course) is not None

    def reg_url(self, course):
        return "https://penncourseplan.com/"

    def fetch(self, courses):
        """One call per course. Keys output by the EXACT input string (robust)."""
        out = {}
        for course in courses:
            code = self._code(course)
            if not code:
                continue
            try:
                d = json.loads(_http(
                    f"https://penncourseplan.com/api/base/{self.sem}/courses/{code}/"))
            except Exception:
                continue
            secs = {}
            for s in d.get("sections", []):
                sid = s.get("id", "")
                num = sid.rsplit("-", 1)[-1] if "-" in sid else None
                if num:
                    secs[num] = {"open": s.get("status") == "O", "seats": None}
            if secs:
                out[course] = secs
        return out


# ===========================================================================
class Banner:
    """Generic Ellucian Banner 9 Self-Service fetcher.

    Banner is the most common US registration system and exposes an IDENTICAL
    JSON API at every school — only host + term code change. So each Banner
    school is just a 4-line subclass. We read `seatsAvailable` (the true count),
    NOT `openSection` (which can be True on a FULL section = false alerts).
    """
    # subclass sets: id, name, example, host, term
    base_path = "StudentRegistrationSsb"   # a few schools mount it elsewhere (e.g. Drexel)
    mep = ""                               # Multi-Entity code for shared multi-school hosts (TTU)
    campus = ""                            # campus filter for SHARED-POOL hosts (SD regental
                                           # system: one host serves 6 universities and rows are
                                           # distinguished ONLY by campusDescription — filtering
                                           # keeps each school's sections separate = no cross-
                                           # campus false alerts)

    def _mep(self, sep="&"):
        return f"{sep}mepCode={self.mep}" if self.mep else ""

    _active_term = None    # set by refresh_term() when a new semester is auto-detected

    def cur_term(self):
        return self._active_term or self.term

    def _get_terms(self):
        base = f"https://{self.host}/{self.base_path}/ssb"
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        self._retry(lambda: op.open(base + "/classSearch/classSearch" + self._mep("?"), timeout=30).read())
        mp = "&mepCode=" + self.mep if self.mep else ""
        raw = self._retry(lambda: op.open(
            base + f"/classSearch/getTerms?searchTerm=&offset=1&max=40{mp}&_=1", timeout=30).read())
        return json.loads(raw)

    def resolve_term(self):
        """Auto-detect the current registration term; None on failure. `cur` makes the
        pick forward-only, so a mis-dated row can never walk a school backward."""
        try:
            return _pick_current_term(self._get_terms(), cur=self.cur_term())
        except Exception:
            return None

    def refresh_term(self, log=None):
        """Adopt a newly-detected term ONLY after verifying it returns live data; otherwise
        keep the last-known-good term. Makes each school self-maintaining across semesters
        WITHOUT ever risking accuracy.

        Schools that run PARALLEL same-season terms (e.g. a "Fall 2026 Semester" undergrad
        term alongside a "Fall 2026 Quarter" grad term) set `auto_term = False`: the term
        picker can't tell those apart, and auto-adopting the wrong one would silently point
        the school at the wrong population. Those schools pin `term` and bump it manually."""
        if not getattr(self, "auto_term", True):
            return
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new                       # try the new term...
        ok = bool(self.fetch({self.example}).get(self.example)) if getattr(self, "example", "") else False
        if not ok:
            self._active_term = prev                  # ...roll back; keep last-known-good
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    @staticmethod
    def _code(course):
        # Handles contiguous ("CSCI 220"), spaced ("C S 2334"), and the full range of
        # real course-number widths: 1-2 digits (CA CCs: "MATH 1A"), 3-4 (most schools),
        # and 5 (Rowan "CS 01104", some SUNYs). Widening this is accuracy-SAFE: fetch
        # always re-queries the school's live API with the exact subject+number, so a
        # wrong format just returns nothing (never a false alert).
        m = re.match(r"^([A-Za-z][A-Za-z ]*?)\s*(\d{1,5}[A-Za-z]?)$", course.strip())
        if not m:
            return (None, None)
        return (re.sub(r"\s+", " ", m.group(1).strip()).upper(), m.group(2).upper())

    def _seckey(self, r):
        """Section key within a course — sequenceNumber ('001') by default, i.e. what
        students see in the schedule. A few hosts (SNHU, DeVry, Concordia-Moorhead)
        zero out sequenceNumber on EVERY row, which would collapse all sections into
        one key — those subclass CrnKeyedBanner, which keys by CRN instead (unique per
        term, and what students at those schools register with anyway)."""
        return r.get("sequenceNumber")

    def _campus_ok(self, r):
        """Per-row campus guard for SHARED-POOL hosts. Default: first word of
        campusDescription must equal `campus` (SD regental pattern, where campuses are
        'Brookings'/'Vermillion'/...). Hosts whose campus labels all share a first word
        (NMSU: 'NMSU - Las Cruces (Main)' vs 'NMSU - Alamogordo') override with an
        exact-match rule instead — first-word matching cannot separate those."""
        return not self.campus or (r.get("campusDescription") or "").split(" ")[0] == self.campus

    def _eligible(self, r):
        """Hook: is this section registerable by a normal student? Default yes. Schools
        with dual-enrollment / high-school-only sections (Murray State 'Racer Academy',
        UNA 'Taught at High School') override to exclude them: those carry real open seats
        a general watcher CANNOT actually register for — an eligibility false-open."""
        return True

    @staticmethod
    def _retry(fn, tries=3):
        """Retry transient network blips (timeouts under load) before giving up."""
        last = None
        for i in range(tries):
            try:
                return fn()
            except Exception as e:
                last = e
                time.sleep(0.5 * (i + 1))
        raise last

    def valid_course(self, course):
        return self._code(course)[0] is not None

    def reg_url(self, course):
        return f"https://{self.host}/{self.base_path}/ssb/classSearch/classSearch"

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        base = f"https://{self.host}/{self.base_path}/ssb"
        self._retry(lambda: op.open(base + "/classSearch/classSearch" + self._mep("?"), timeout=30).read())
        term_data = {"term": self.cur_term()}
        if self.mep:
            term_data["mepCode"] = self.mep
        data = urllib.parse.urlencode(term_data).encode()
        self._retry(lambda: op.open(
            urllib.request.Request(base + "/term/search?mode=search" + self._mep(), data=data),
            timeout=30).read())
        return op, base

    def fetch(self, courses):
        """One search per course (exact subject+number). Keyed by input string."""
        try:
            op, base = self._session()
        except Exception:
            return {}
        out = {}
        for course in courses:
            subj, num = self._code(course)
            if not subj:
                continue
            try:
                op.open(urllib.request.Request(base + "/classSearch/resetDataForm", data=b""),
                        timeout=15).read()
            except Exception:
                pass
            try:
                # Paginate: big schools exceed one page (FRCC ENG 1021 = 129 sections) and
                # rows past the page cap would otherwise be silently invisible — a watched
                # section that never appears. Cap pages defensively; if the API reports
                # more rows than we could read, skip the course (accuracy over coverage).
                rows, offset, total = [], 0, None
                while offset < 500:
                    q = urllib.parse.urlencode({"txt_subject": subj, "txt_courseNumber": num,
                                                "txt_term": self.cur_term(), "pageOffset": offset,
                                                "pageMaxSize": 100})
                    res = json.loads(self._retry(lambda: op.open(
                        base + "/searchResults/searchResults?" + q + self._mep(),
                        timeout=30).read().decode("utf-8", "replace")))
                    page = res.get("data") or []
                    rows += page
                    total = res.get("totalCount")
                    if not page or not isinstance(total, int) or len(rows) >= total:
                        break
                    offset += 100
                if isinstance(total, int) and total > len(rows):
                    continue                            # couldn't read every section — skip
            except Exception:
                continue
            secs = {}
            for r in rows:
                if str(r.get("courseNumber")) != num:   # txt_courseNumber is prefix-match
                    continue
                if (r.get("subject") or "").upper() != subj:   # guard cross-subject collisions
                    continue
                if not self._campus_ok(r):
                    continue                            # shared-pool host: only OUR campus
                if not self._eligible(r):
                    continue                            # dual-enroll/HS-only -> not a real open
                seq = self._seckey(r)
                try:
                    n = int(r.get("seatsAvailable"))    # no count -> skip, never guess
                except (TypeError, ValueError):
                    continue
                if seq is not None:
                    # Banner returns negative availability for over-enrolled sections;
                    # that's "full" (open stays False), but never show a negative count.
                    secs[str(seq)] = {"open": n > 0, "seats": max(n, 0)}
            if secs:
                out[course] = secs
        return out


class Tennessee(Banner):
    id = "utk"; name = "University of Tennessee–Knoxville"
    example = "COSC 101"; host = "bannerreg.utk.edu"; term = "202640"

class FAU(Banner):
    id = "fau"; name = "Florida Atlantic University"
    example = "COP 3035C"; host = "bannerxe.fau.edu"; term = "202608"

class ECU(Banner):
    # openSection is near-meaningless here (True on hundreds of 0-seat rows) — the base's
    # seatsAvailable rule is what keeps this school honest. Medical/Dental run in their own
    # View-Only terms, so the main term is the general population.
    id = "ecu"; name = "East Carolina University"
    example = "ENGL 1100"; host = "banprd-ssb-cld.ecu.edu"; term = "202680"

class SamHoustonState(Banner):
    # Summer 2026 (202640) is also non-View-Only, but the forward-only picker keeps Fall
    # (202680) through add/drop. seatsAvailable authoritative, as always.
    id = "shsu"; name = "Sam Houston State University"
    example = "MATH 1314"; host = "banxeappx.shsu.edu"; term = "202680"

class FerrisState(Banner):
    # Non-standard port :4020 (443 refuses) — verified reachable from the prod poller.
    # 202608 = Fall 2026 (only non-View-Only). seatsAvailable authoritative.
    id = "ferris"; name = "Ferris State University"
    example = "ACCT 201"; host = "banner.ferris.edu:4020"; term = "202608"

class MidwesternState(Banner):
    # Non-standard port :1808 — verified reachable from the prod poller. seatsAvailable rule.
    id = "msutexas"; name = "Midwestern State University"
    example = "ACCT 2143"; host = "bannerxefe4.msutexas.edu:1808"; term = "202710"

class UNCPembroke(Banner):
    # Port :9639 + non-default base_path (uncecs.edu:9xxx family). Verified reachable from
    # the poller. openSection is UNRELIABLE (True on seats=0 rows) — seatsAvailable rule
    # is load-bearing, as always.
    id = "uncp"; name = "UNC Pembroke"
    example = "ACC 2280"; host = "banxp-uncp.uncecs.edu:9639"
    base_path = "uncpprodStudentRegistrationSsb"; term = "202710"

class WesternCarolina(Banner):
    # Port :9939 + non-default base_path — same uncecs.edu:9xxx family as UNCP. Verified
    # reachable from the poller. seatsAvailable authoritative.
    id = "wcu"; name = "Western Carolina University"
    example = "BIOL 103"; host = "banxp-wcu.uncecs.edu:9939"
    base_path = "wcuprodStudentRegistrationSsb"; term = "202680"

class JacksonvilleState(Banner):
    # Dual-enrollment / high-school sections (instructionalMethodDescription) carry open
    # seats a general student cannot register for — an eligibility false-open, same as the
    # UNA sibling. 32 such sections had open seats at gate time; _eligible drops them.
    id = "jsu"; name = "Jacksonville State University"
    example = "ACC 200"; host = "studentreg.jsu.edu"; term = "202710"
    def _eligible(self, r):
        m = (r.get("instructionalMethodDescription") or "").lower()
        return "dual enroll" not in m and "high school" not in m

class OaklandU(Banner):
    # Use bstreg (JSON) NOT mysail (login SPA). auto_term OFF: getTerms lists a bogus
    # "Continuing Education 2027-2028" (202733) as the highest code, and Oakland's real
    # next primary term is a WINTER term the auto-picker won't adopt anyway — so pin Fall
    # and hand-roll to 202710 when it closes. openSection is unreliable (True on
    # waitlist-open full sections); seatsAvailable keeps it honest.
    id = "oaklandu"; name = "Oakland University"       # != Oakland CC (Colleague)
    example = "BIO 1200"; host = "bstreg.oakland.edu"; term = "202640"; auto_term = False

class CentralArkansas(Banner):
    # AY-numbered: 202710 = Fall 2026 (like Angelo State). Description-picker reads
    # "Fall 2026" and all 7 prior terms are View-Only, so auto_term is safe.
    id = "uca"; name = "University of Central Arkansas"
    example = "ACCT 2310"; host = "banssprod.uca.edu"; term = "202710"

class UTRGV(Banner):
    # auto_term=False is LOAD-BEARING. UTRGV runs School-of-Medicine terms (SOM/SOPM
    # Y1-Y4) whose codes (202749/202739/...) are HIGHER than the general Fall 2026
    # (202710) and tie it on delta, so the forward-only picker selects 202749 — 56
    # all-open clinical rotations, ZERO general courses, silently starving every
    # ENGL/MATH watcher (live-verified: resolve_term returns 202749). Pin the general
    # term; hand-roll to Spring 2027 (~202720) later. seatsAvailable authoritative.
    id = "utrgv"; name = "University of Texas Rio Grande Valley"
    example = "ACCT 2301"; host = "assist.utrgv.edu"; term = "202710"; auto_term = False

class Nicholls(Banner):
    # HOST TRAP: the public link advertises :8444, which is FIREWALLED (times out).
    # Use the bare 443 host — verified reachable. Self-hosted behind Imperva.
    id = "nicholls"; name = "Nicholls State University"
    example = "MATH 100"; host = "ssop.nicholls.edu"; term = "202680"

class AngeloState(Banner):
    # 202710 IS Fall 2026 — ASU numbers by ACADEMIC year (AY 2026-27, term 10), so the code
    # looks a year ahead. The picker reads the description ("2026 FALL SEMESTER"), not the code.
    id = "angelostate"; name = "Angelo State University"
    example = "ENGL 1301"; host = "registration.prod.angelo.edu"; term = "202710"

class BallState(Banner):
    id = "ballstate"; name = "Ball State University"
    example = "CS 120"; host = "banner.bsu.edu"; term = "202610"

class Wyoming(Banner):
    id = "uwyo"; name = "University of Wyoming"
    example = "COSC 1010"; host = "wyossb.uwyo.edu"; term = "202710"

class CNM(Banner):
    id = "cnm"; name = "Central New Mexico College"
    example = "CSCI 1220"; host = "banner.cnm.edu"; term = "202670"

class Duquesne(Banner):
    """Standard Banner 9 JSON except the default bootstrap page is broken FOR GUESTS:
    /classSearch/classSearch 302s to a plain-http registration URL whose port 80 is
    firewalled (3 retries x 30s hang = Drake-class latency and {} forever). The
    /term/termSelection?mode=search page sets the same session cookies and the rest of
    the flow is stock — so only the two bootstrap GETs are overridden. Live-verified:
    BIOL 111 returns numeric cap/enrolled/seatsAvailable (225/213/12)."""
    id = "duquesne"; name = "Duquesne University"
    example = "BIOL 111"; host = "bannerprodss.duq.edu"; term = "202710"  # Fall 2026

    def _bootstrap(self, op, base):
        self._retry(lambda: op.open(base + "/term/termSelection?mode=search", timeout=30).read())

    def _get_terms(self):
        base = f"https://{self.host}/{self.base_path}/ssb"
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        self._bootstrap(op, base)
        raw = self._retry(lambda: op.open(
            base + "/classSearch/getTerms?searchTerm=&offset=1&max=40&_=1", timeout=30).read())
        return json.loads(raw)

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        base = f"https://{self.host}/{self.base_path}/ssb"
        self._bootstrap(op, base)
        data = urllib.parse.urlencode({"term": self.cur_term()}).encode()
        self._retry(lambda: op.open(
            urllib.request.Request(base + "/term/search?mode=search", data=data),
            timeout=30).read())
        return op, base

class NMSU(Banner):
    """New Mexico State University — Las Cruces flagship ONLY, on the shared
    banner-public.nmsu.edu instance that also serves Alamogordo/Grants/Global and
    Doña Ana CC. Every campus label starts with 'NMSU'/'DACC', so the default
    first-word campus guard can't separate them — exact campusDescription match
    instead. Live disproof on THIS host: ENGL 1110G Las Cruces M01-M05 all
    cap27/enr27/avail0 (numeric enrolled=capacity) while openSection=True — the
    standard Banner lie; we read seatsAvailable only. (Supersedes the July 8
    exclusion, which was against a different, non-public host.)"""
    id = "nmsu"; name = "New Mexico State University"
    example = "ENGL 1110G"; host = "banner-public.nmsu.edu"; term = "202640"  # Fall 2026
    _CAMPUS = "NMSU - Las Cruces (Main)"

    def _campus_ok(self, r):
        return (r.get("campusDescription") or "") == self._CAMPUS


class USC:
    """University of Southern California — public same-origin REST API behind
    classes.usc.edu (Angular SPA; no auth, plain UA, 0.4-0.9s per course, one GET).

    /api/Terms/All gives status Active/Archived per term; termCode = YYYY + season
    digit (1=Spring 2=Summer 3=Fall). /api/Courses/Course?termCode=&courseCode= takes
    the code SMASHED ("CSCI104", no space). Re-gated live 2026-07-13: 533 sections
    audited, isFull vs (totalSeats-registeredSeats) agreed 533/533 including over-cap
    fulls (16/15); WRIT 150 Fall = 162 sec 11 open/151 FULL; completed Spring = 38
    open/112 FULL (real mixed history). sisSectionId = the 5-digit number students
    register with, verified unique per term.

    TRAPS (each live-verified):
    - DUAL RESPONSE SHAPE: usually a bare course object, sometimes {"courses":[...]}.
      Parse both — handling only one silently reads as 'not offered'.
    - Unknown/malformed codes can be HTTP 500, not just 204 -> any failure = {} skip.
    - SEVERAL terms are 'Active' at once (Spring stays Active into July): the term
      picker season-deltas among Actives, never 'first Active'.
    - isCancelled rows excluded. hasDClearance seats are REAL (a USC department-
      clearance step, not a fake open) — alert normally.
    - Cross-listing is server-side (CLAS202/ANTH202 -> same courseId + sections);
      exact courseCode is all the scoping needed.
    open = not isCancelled and not isFull and totalSeats-registeredSeats > 0;
    seats = max(totalSeats - registeredSeats, 0)."""
    id = "usc"; name = "University of Southern California"
    example = "WRIT 150"
    term = "20263"                       # Fall 2026 (auto-rolls via Terms/All)
    _active_term = None
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*-?\s*(\d{2,3}[A-Za-z]{0,2})$")

    def _smash(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1) + m.group(2)).upper() if m else None

    def valid_course(self, course):
        return self._smash(course) is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return "https://classes.usc.edu/"

    def _fetch_term(self, term, course):
        code = self._smash(course)
        if not code:
            return None
        try:
            req = urllib.request.Request(
                f"https://classes.usc.edu/api/Courses/Course?termCode={term}&courseCode={code}",
                headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
                if r.status == 204 or not body.strip():
                    return {}                      # not offered -> safe empty
                j = json.loads(body)
        except Exception:
            return None                            # incl. the HTTP-500-on-junk trap
        if isinstance(j, dict) and "courses" in j:
            courses = j["courses"]
        elif isinstance(j, list):
            courses = j
        else:
            courses = [j]
        secs = {}
        for c in courses or []:
            for s in (c.get("sections") or []) if isinstance(c, dict) else []:
                sid = str(s.get("sisSectionId") or "")
                if not sid or s.get("isCancelled"):
                    continue
                if sid in secs:
                    return None                    # collapse guard — never merge blind
                tot, reg = s.get("totalSeats"), s.get("registeredSeats")
                if not (isinstance(tot, int) and isinstance(reg, int)):
                    continue                       # no numbers -> skip, never guess
                avail = tot - reg
                secs[sid] = {"open": (not s.get("isFull")) and avail > 0,
                             "seats": max(avail, 0)}
        return secs

    def resolve_term(self):
        try:
            req = urllib.request.Request("https://classes.usc.edu/api/Terms/All",
                                         headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                terms = json.loads(r.read())
        except Exception:
            return None
        today = datetime.date.today()
        best, best_delta = None, None
        for t in terms:
            if t.get("status") != "Active":
                continue
            season = str(t.get("season") or "").lower()
            year = t.get("year")
            if season not in _SEASON or not isinstance(year, int):
                continue
            delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
            if not _auto_season(season) or delta < -1:
                continue                           # skip in-progress Actives
            if best_delta is None or delta < best_delta:
                best_delta, best = delta, str(t.get("termCode"))
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self._fetch_term(new, self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            secs = self._fetch_term(self.cur_term(), course)
            if secs:
                out[course] = secs
        return out


class Rice:
    """Rice University — custom public Banner catalog package (courses.rice.edu
    !SWKSCAT.cat), no auth. Listing per SUBJECT (?p_action=QUERY&p_term&p_subj) gives
    rows (cls-crn CRN link + cls-crs 'SUBJ NUM SEC'); seats need one detail GET per
    CRN (p_action=COURSE) with labeled '<b>Section Max Enrollment: </b>N' fields.
    N+1 with per-instance TTL cache + lock — Purdue/TAMU envelope (MATH 101 ≈ 11s
    cold / 0ms warm; FWIS-sized 63-section courses ~90s cold, MTSU/UNM precedent).

    TERM SEMANTICS (live-read from the picker; labels win): codes are ACADEMIC-YEAR
    based — 'Fall Semester 2026' = 202710 but 'Spring Semester 2026' = 202620. The
    picker parses the form's own <option> labels and REQUIRES the word 'Semester':
    Rice interleaves Quadmester sub-terms (202611/202615/202625/202705) that a bare
    season regex would collide with, and 'quadmester' is NOT in _SUBTERM. (A relayed
    spec had completed Spring 2026 as 202520 — that's actually Spring 2025.)

    OPEN RULE — all conditions mandatory, each live-verified:
    1. SectionMax - SectionEnrolled > 0. Completed Spring 202620 shows 16/109 ENGL
       rows genuinely full through THIS parse (host-level fake-open disproof; live
       Fall is an unfilled cycle — RPI-class rationale, empty/skip stays safe).
    2. If cross-list totals present: XlistMax - XlistEnrolled > 0 too (verified full
       example: section 10/10 with xlist 15/16 — the xlist pool binds).
    3. WAITLIST FAIL-CLOSED: Rice gives waitlist members priority for open seats.
       100+ fetched detail pages (fulls included) carry NO waitlist text when no
       queue exists — the field renders only when relevant. Rule: any 'waitlist'
       text WITHOUT a parseable 'Waitlisted: </b>0' -> NOT open (nonzero queue and
       unparseable format drift both fail closed).
    Belt: the detail page must echo 'SUBJ NUM' or the section is skipped. Sections
    keyed by CRN (verified unique per term; 5-digit, what students register with)."""
    id = "rice"; name = "Rice University"
    example = "MATH 101"
    term = "202710"                     # Fall Semester 2026 (auto-rolls; labels win)
    _TTL = 600
    base = "https://courses.rice.edu/courses/!SWKSCAT.cat"
    _RE = re.compile(r"^([A-Za-z&]{2,4})\s+(\d{2,3}[A-Za-z]?)$")
    _ROW = re.compile(
        r'class="cls-crn"><a href="[^"]*p_crn=(\d+)"[^>]*>\d+</a></td>'
        r'<td[^>]*class="cls-crs"><a[^>]*>([A-Z&]+)</a>\s*(\d+[A-Za-z]*)\s+(\S+)</td>', re.S)

    def __init__(self):
        self._active_term = None
        self._lock = threading.Lock()
        self._cache = {}                # (term, subj, num) -> (ts, {crn: {open, seats}})

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.base

    def _detail(self, term, crn, subj, num):
        """One section's {open, seats} from its detail page, or None to skip.
        Every parse failure lands on the not-open/skip side — never a guess."""
        try:
            d = _http(f"{self.base}?p_action=COURSE&p_term={term}&p_crn={crn}")
        except Exception:
            return None
        if not re.search(rf"{re.escape(subj)}\s*{re.escape(num)}", d):
            return None                             # belt: page must echo the course
        mx = re.search(r"Section Max Enrollment:\s*</b>\s*(\d+)", d)
        en = re.search(r"Section Enrolled:\s*</b>\s*(\d+)", d)
        if not mx or not en:
            return None                             # no numbers -> skip, never guess
        avail = int(mx.group(1)) - int(en.group(1))
        xm = re.search(r"Total Cross-list Max Enrollment:\s*</b>\s*(\d+)", d)
        xe = re.search(r"Total Cross-list Enrolled:\s*</b>\s*(\d+)", d)
        if xm and xe:
            avail = min(avail, int(xm.group(1)) - int(xe.group(1)))
        wl_block = False
        if "aitlist" in d:                          # field renders only when relevant
            w = re.search(r"Waitlisted\s*:\s*</b>\s*(\d+)", d)
            wl_block = (not w) or int(w.group(1)) != 0
        return {"open": avail > 0 and not wl_block, "seats": max(avail, 0)}

    def _build(self, term, subj, num):
        try:
            listing = _http(f"{self.base}?p_action=QUERY&p_term={term}&p_name=&p_subj={subj}")
        except Exception:
            return {}
        crns = [r[0] for r in self._ROW.findall(listing) if r[1] == subj and r[2] == num]
        if not crns or len(crns) != len(set(crns)):
            return {}                               # nothing, or CRN collapse -> skip
        secs = {}
        for crn in crns:
            s = self._detail(term, crn, subj, num)
            if s is not None:
                secs[crn] = s
        if secs:
            self._cache[(term, subj, num)] = (time.time(), secs)
        return secs

    def resolve_term(self):
        """Nearest upcoming 'Semester' term from the form's own option labels
        (Quadmester sub-terms and View Only screened out)."""
        try:
            h = _http(self.base)
        except Exception:
            return None
        today = datetime.date.today()
        best, best_delta = None, None
        for code, desc in re.findall(r'<option value="(\d{6})"[^>]*>([^<]+)', h):
            dl = desc.lower()
            if "semester" not in dl or "view only" in dl:
                continue
            m = re.search(r"(spring|summer|fall)\s*semester\s*(20\d\d)", dl)
            if not m:
                continue
            season, year = m.group(1), int(m.group(2))
            delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
            if not _auto_season(season) or delta < -1:
                continue
            if best_delta is None or delta < best_delta:
                best_delta, best = delta, code
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self._build(new, *self._norm(self.example)))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            key = (self.cur_term(), subj, num)
            cached = self._cache.get(key)
            if cached and time.time() - cached[0] < self._TTL:
                out[course] = cached[1]
                continue
            blocking = cached is None
            if not self._lock.acquire(blocking=blocking):
                out[course] = cached[1] if cached else {"none": {"open": False, "seats": None}}
                continue
            try:
                again = self._cache.get(key)
                if again and time.time() - again[0] < self._TTL:
                    secs = again[1]
                else:
                    secs = self._build(*key) or (again[1] if again else {})
            finally:
                self._lock.release()
            out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class Maricopa:
    """Maricopa County Community College District (~200k students, 10 colleges on ONE
    shared host classes.sis.maricopa.edu). Server-rendered search — the results HTML is
    in a plain GET, no browser/XHR needed. One GET per course, ~1.2s.

    URL: ?institutions[]={CODE}&terms[]={term}&keywords={SMASHED}&all_classes=true
    - all_classes=true is MANDATORY: the default search hides FULL sections entirely
      (BIO201 Phoenix: default 12 open/0 closed -> all_classes 12 open/5 closed). A
      hidden full section = a silent miss; the param is non-negotiable.
    - CAMPUS ISOLATION: institutions[]={CODE} hard-filters to one college — live-proven
      DISJOINT (Phoenix BIO201 17 secs vs Mesa BIO201 14 secs, class-number overlap
      EMPTY). Each subclass is one college; class_number is unique within it.
    - EXACT SCOPING: parse only the <div class="course"> block whose <h3> code equals
      the smashed target (keyword search can surface siblings; we never read them).
    - REAL NUMERIC seats: 'N of M seats available' -> open iff N>0, seats=N;
      'No seats available' -> full. status span 'open/closed' agreed with the numeric
      on 100% of gated rows; the number is authoritative. Any unparseable row is skipped
      (never guessed open). Section key = 5-digit class number.
    Term is opaque (Fall 2026 = 4266); auto-rolls by reading the form's own term
    checkbox labels (verify-before-adopt)."""
    campus = ""                          # institution code, e.g. PCC01; subclass sets
    term = "4266"                        # Fall 2026 (auto-rolls)
    _active_term = None
    base = "https://classes.sis.maricopa.edu/"
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{2,3}[A-Za-z]{0,2})$")
    _BLOCK = re.compile(r'<div class="course">(.*?)</table>', re.S)
    _H3 = re.compile(r'<h3>\s*([A-Z]+\d+[A-Z]*)\s*:')
    _ROW = re.compile(r'<tr class="class-specs.*?</tr>', re.S)
    _NUM = re.compile(r'class="class-number">\s*<div class="class-cell">\s*(\d+)')
    _SEATS = re.compile(r'(\d+) of (\d+) seats available')
    _NOSEAT = re.compile(r'No seats available')

    def _smash(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1) + m.group(2)).upper() if m else None

    def valid_course(self, course):
        return self._smash(course) is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self.base

    def _search(self, term, smashed):
        q = urllib.parse.urlencode({"institutions[]": self.campus, "terms[]": term,
                                    "keywords": smashed, "all_classes": "true"}, doseq=True)
        return _http(self.base + "?" + q)

    def _fetch_term(self, term, course):
        smashed = self._smash(course)
        if not smashed:
            return None
        try:
            html = self._search(term, smashed)
        except Exception:
            return None
        for blk in self._BLOCK.findall(html):
            m = self._H3.search(blk)
            if not m or m.group(1) != smashed:      # EXACT course only — no sibling leak
                continue
            secs = {}
            for row in self._ROW.findall(blk):
                n = self._NUM.search(row)
                if not n:
                    continue
                sm = self._SEATS.search(row)
                if sm:
                    secs[n.group(1)] = {"open": int(sm.group(1)) > 0, "seats": int(sm.group(1))}
                elif self._NOSEAT.search(row):
                    secs[n.group(1)] = {"open": False, "seats": 0}
                # else: unknown availability format -> skip row, never guess
            return secs
        return {}                                    # course not offered this term -> safe empty

    def resolve_term(self):
        """Nearest upcoming semester from the form's own term checkboxes (opaque codes,
        human labels win). Skips in-progress terms via the shared _SEASON delta logic."""
        try:
            h = _http(self.base)
        except Exception:
            return None
        today = datetime.date.today()
        best, best_delta = None, None
        for code, label in re.findall(
                r'name="terms\[\]"[^>]*value="(\d+)"[^>]*>\s*<label[^>]*>([^<]+)</label>', h):
            m = re.search(r"(spring|summer|fall|winter)\s+(20\d\d)", label, re.I)
            if not m:
                continue
            season, year = m.group(1).lower(), int(m.group(2))
            delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
            if not _auto_season(season) or delta < -1:
                continue
            if best_delta is None or delta < best_delta:
                best_delta, best = delta, code
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self._fetch_term(new, self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            secs = self._fetch_term(self.cur_term(), course)
            if secs:
                out[course] = secs
        return out

class PhoenixCollege(Maricopa):
    id = "phoenixcollege"; name = "Phoenix College"
    example = "BIO201"; campus = "PCC01"

class GlendaleCC(Maricopa):
    id = "glendalecc-az"; name = "Glendale Community College (AZ)"   # != Glendale CC (CA)
    example = "BIO201"; campus = "GCC02"

class MesaCC(Maricopa):
    id = "mesacc"; name = "Mesa Community College"
    example = "BIO201"; campus = "MCC04"

class ChandlerGilbert(Maricopa):
    id = "chandlergilbert"; name = "Chandler-Gilbert Community College"
    example = "BIO201"; campus = "CGC08"

class EstrellaMountain(Maricopa):
    id = "estrellamountain"; name = "Estrella Mountain Community College"
    example = "BIO201"; campus = "EMC10"

class GateWayCC(Maricopa):
    id = "gatewaycc"; name = "GateWay Community College"   # != Mountain Gateway CC
    example = "BIO201"; campus = "GWC03"

class ParadiseValleyCC(Maricopa):
    id = "paradisevalleycc"; name = "Paradise Valley Community College"
    example = "BIO201"; campus = "PVC09"

class RioSalado(Maricopa):
    id = "riosalado"; name = "Rio Salado College"
    example = "BIO201"; campus = "RSC06"

class ScottsdaleCC(Maricopa):
    id = "scottsdalecc"; name = "Scottsdale Community College"
    example = "BIO201"; campus = "SCC05"

class SouthMountainCC(Maricopa):
    id = "southmountaincc"; name = "South Mountain Community College"
    example = "BIO201"; campus = "SMC07"


class RCCD:
    """Riverside Community College District — 3 colleges (Moreno Valley, Norco,
    Riverside City), each its OWN SharePoint list on the shared msappproxy host, so
    campus isolation is inherent (no cross-college query possible). PnPjs→SharePoint
    REST, anonymous, real numeric seats. One small server-filtered GET per course.

    ⚠️ THE HEADER: 'Accept: application/json;odata=nometadata' is mandatory — a plain
    GET returns the SPA/atom XML shell (this is what made earlier probes look dead).
    ⚠️ THE LIST ACCUMULATES TERMS: a relay called it 'current-term-only', but the list
    actually holds Fall+Winter+Spring+Summer at once (MOV: 1004+255+939+284). We MUST
    filter Term server-side, or a watched Fall course pulls in stale past-term rows.
    Filtering to the current term also drops every college under the 5080 one-page cap
    (RIV 5410-all-terms -> 2330 Fall) so the paging trap disappears; we still follow
    odata.nextLink defensively and fail-closed if a page can't be read.

    OPEN RULE (matches RCCD's own app): Total_Seats - Seats_Used > 0 AND the section's
    Last_Day_to_Add is >= today. The date gate is also a stale-row backstop — any
    lingering past-term section has a past add deadline, so it can never alert. Over-cap
    rows (used>seats) go negative -> not open. Unparseable date -> not open (conservative;
    worst case a safe miss, never a false open). Section key = Section_x0020_ID (unique).
    Exact course scope = Primary_x0020_Subject 'SUBJ-NUM' (e.g. ENGL-C1000; ACC-1A must
    not catch ACC-1B). Term auto-rolls from the ScheduleTermOptions list."""
    list_name = ""                       # ScheduleData_MOV/NOR/RIV; subclass sets
    term = "26FAL"                       # Fall 2026 (auto-rolls)
    _active_term = None
    _host = "https://apps-studentrcc.msappproxy.net/schedule/_api/web/lists"
    _HDR = {"Accept": "application/json;odata=nometadata", "User-Agent": UA}
    _SEL = ("Section_x0020_ID,Primary_x0020_Subject,Total_x0020_Seats,"
            "Seats_x0020_Used,Last_x0020_Day_x0020_to_x0020_Ad")
    _RE = re.compile(r"^([A-Za-z]+)[\s-]+([A-Za-z]?\d+[A-Za-z]?)$")
    _SEASONS = {"fall": "FAL", "spring": "SPR", "summer": "SUM", "winter": "WIN"}

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return f"{m.group(1).upper()}-{m.group(2).upper()}" if m else None

    def valid_course(self, course):
        return self._norm(course) is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return "https://www.rccd.edu/"

    def _get(self, url):
        with urllib.request.urlopen(urllib.request.Request(url, headers=self._HDR), timeout=30) as r:
            return json.loads(r.read())

    @staticmethod
    def _addable(s):
        """True iff the MM/DD/YY add deadline is today or later. Unparseable -> False."""
        try:
            mo, dy, yr = s.split("/")
            return datetime.date(2000 + int(yr), int(mo), int(dy)) >= datetime.date.today()
        except Exception:
            return False

    def _fetch_term(self, term, course):
        subj = self._norm(course)
        if not subj:
            return None
        flt = urllib.parse.quote(f"Term eq '{term}' and Primary_x0020_Subject eq '{subj}'")
        url = (f"{self._host}/getByTitle('{self.list_name}')/items"
               f"?$select={self._SEL}&$filter={flt}&$top=5080")
        rows = []
        try:
            while url:
                j = self._get(url)
                rows += j.get("value", [])
                url = j.get("odata.nextLink")       # defensive; one term fits one page
        except Exception:
            return None                             # incl. an unreadable page -> fail closed
        secs = {}
        for r in rows:
            if r.get("Primary_x0020_Subject") != subj:   # exact course only
                continue
            key = str(r.get("Section_x0020_ID") or "")
            if not key:
                continue
            try:
                avail = int(float(r["Total_x0020_Seats"])) - int(float(r["Seats_x0020_Used"]))
            except (TypeError, ValueError, KeyError):
                continue                            # no numbers -> skip, never guess
            openb = avail > 0 and self._addable(r.get("Last_x0020_Day_x0020_to_x0020_Ad", ""))
            secs[key] = {"open": openb, "seats": max(avail, 0)}
        return secs

    def resolve_term(self):
        """Nearest upcoming term code from the district's ScheduleTermOptions list."""
        try:
            opts = self._get(f"{self._host}/getByTitle('ScheduleTermOptions')/items?$select=Title,Term")
        except Exception:
            return None
        today = datetime.date.today()
        best, best_delta = None, None
        for t in opts.get("value", []):
            m = re.search(r"(spring|summer|fall|winter)\s+(20\d\d)", (t.get("Title") or "").lower())
            if not m:
                continue
            season, year = m.group(1), int(m.group(2))
            delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
            if not _auto_season(season) or delta < -1:
                continue
            if best_delta is None or delta < best_delta:
                best_delta, best = delta, t.get("Term")
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self._fetch_term(new, self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        for course in courses:
            secs = self._fetch_term(self.cur_term(), course)
            if secs:
                out[course] = secs
        return out

class WVMCCD:
    """West Valley-Mission CCD — ONE public static Banner dump (schedule.wvm.edu) serves
    West Valley + Mission; rows separated by SSBSECT_CAMP_CODE. The whole per-term dump
    (~2,000 rows) is fetched ONCE per TTL into a SHARED class-level cache (both colleges
    read it), then filtered CAMP_CODE + SUBJ_CODE + exact course number. open =
    SSBSECT_SEATS_AVAIL > 0 AND SSBSECT_SSTS_CODE == 'A' (drop cancelled/inactive).
    Section key = CRN (unique per campus; cross-campus CRN overlap live-verified EMPTY).

    ⚠️ CAMPUS code in the DATA is WVC / MC — NOT the dropdown's 'WV' label (that returns 0).
    ⚠️ COURSE NUMBERS are zero-padded and irregular (ENGL '005A','010','099X' but also
    '10W'), so match on a canonical form (strip leading zeros both sides): user 'ENGL 5A'
    -> '5A' matches stored '005A'. Term auto-rolls from sobterm.json (Banner labels win)."""
    term = "202670"                  # Fall 2026 (auto-rolls)
    _active_term = None
    campus = ""                      # WVC / MC; subclass sets
    _FEED = "https://schedule.wvm.edu/data/%s/crns.json"
    _TERMS = "https://schedule.wvm.edu/data/sobterm.json"
    _TTL = 600
    _lock = threading.Lock()
    _dump = {}                       # term -> (ts, rows) — SHARED across both colleges
    _RE = re.compile(r"^([A-Za-z]{2,5})\s*(\d{1,4}[A-Za-z]{0,2})$")

    @staticmethod
    def _canon(n):
        return re.sub(r"^0+(\d)", r"\1", (n or "").strip().upper())   # 005A->5A, 010->10

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), self._canon(m.group(2))) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return "https://schedule.wvm.edu/"

    def _rows(self):
        term = self.cur_term()
        with WVMCCD._lock:
            c = WVMCCD._dump.get(term)
            if c and time.time() - c[0] < self._TTL:
                return c[1]
            try:
                req = urllib.request.Request(self._FEED % term, headers={"User-Agent": UA})
                rows = json.loads(urllib.request.urlopen(req, timeout=45).read())
            except Exception:
                return c[1] if c else []             # stale-if-error; never guess
            if isinstance(rows, list) and rows:
                WVMCCD._dump[term] = (time.time(), rows)
                return rows
            return c[1] if c else []

    def resolve_term(self):
        try:
            req = urllib.request.Request(self._TERMS, headers={"User-Agent": UA})
            terms = json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception:
            return None
        today = datetime.date.today()
        best, best_delta = None, None
        for t in terms:
            m = re.search(r"(spring|summer|fall|winter)\s+(20\d\d)", (t.get("STVTERM_DESC") or "").lower())
            if not m:
                continue
            season, year = m.group(1), int(m.group(2))
            delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
            if not _auto_season(season) or delta < -1:
                continue
            if best_delta is None or delta < best_delta:
                best_delta, best = delta, t.get("SOBTERM_TERM_CODE")
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example)) if getattr(self, "example", "") else False
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        out = {}
        rows = None
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            if rows is None:
                rows = self._rows()
            secs = {}
            for r in rows:
                if r.get("SSBSECT_CAMP_CODE") != self.campus:
                    continue
                if (r.get("SUBJ_CODE") or "").upper() != subj:
                    continue
                if self._canon(r.get("CRSE_NUMB")) != num:          # exact course, zero-pad-safe
                    continue
                if r.get("SSBSECT_SSTS_CODE") != "A":               # active only
                    continue
                key = str(r.get("CRN") or "")
                try:
                    avail = int(r.get("SSBSECT_SEATS_AVAIL"))
                except (TypeError, ValueError):
                    continue                                        # no count -> skip, never guess
                if not key or key in secs:
                    continue
                secs[key] = {"open": avail > 0, "seats": max(avail, 0)}
            if secs:
                out[course] = secs
        return out

class WestValley(WVMCCD):
    id = "westvalley"; name = "West Valley College"
    example = "ENGL 10W"; campus = "WVC"      # WVC numbers carry a 'W' suffix

class MissionCollege(WVMCCD):
    id = "missioncollege"; name = "Mission College (CA)"
    example = "ENGL 10M"; campus = "MC"       # MC numbers carry an 'M' suffix


class MorenoValley(RCCD):
    id = "morenovalley"; name = "Moreno Valley College"
    example = "ENGL C1000"; list_name = "ScheduleData_MOV"

class NorcoCollege(RCCD):
    id = "norco"; name = "Norco College"
    example = "ENGL C1000"; list_name = "ScheduleData_NOR"

class RiversideCity(RCCD):
    id = "riversidecity"; name = "Riverside City College"
    example = "ENGL C1000"; list_name = "ScheduleData_RIV"


class GeorgeMason(Banner):
    # ~40k R1 public. Guest Banner9 (patriotweb links this SSB host). ENGH 101 = 72 sec
    # 8 open/64 full live; completed Fall 2025 (202570) mixed; numeric seatsAvailable.
    id = "gmu"; name = "George Mason University"
    example = "ENGH 101"; host = "ssbstureg.gmu.edu"; term = "202670"   # Fall 2026

class NorthernMichigan(Banner):
    # 4-year public. Guest Banner9. EN 111 = 31 sec 1 open/30 full live; completed Fall
    # 2025 (202580) mixed. NMU subject codes are 2-letter (EN/BI/MA), handled by _code.
    id = "nmu"; name = "Northern Michigan University"
    example = "EN 111"; host = "bssrprod.nmu.edu:8443"; term = "202680"   # Fall 2026

class UTChattanooga(Banner):
    # ~12k public 4-year. Guest Banner9 (single institution — 'UT Chattanooga' +
    # 'UTC Hybrid/Online' are modalities of the same school, NOT a shared UT-system host;
    # UTK is a separate instance). ENGL 1010 = 41 sec 27 open/14 full live; completed
    # Spring 2026 (202620) = 7 sec 5 full. seq unique 41/41.
    id = "utc"; name = "University of Tennessee at Chattanooga"
    example = "ENGL 1010"; host = "sis-reg.utc.edu"; term = "202640"   # Fall 2026


class IUBloomington:
    """Indiana University Bloomington (~48k flagship) — public iGPS course API (no auth,
    plain JSON). Three calls, all scoped to inst=IUBLA (the shared host also serves 8
    other IU campuses; rows carry campus=BL — isolation live-verified, 0 non-IUBLA rows):
      1. terms.json?inst=IUBLA -> term codes (auto-roll; Fall 2026 = 4268).
      2. POST search/courses.json {inst,strm,filters:all-null,from} -> the CATALOG,
         paginated 50/page (~6,100 courses/123 pages). One catalog row = one
         courseId/courseOfferNumber/courseTopicId/effdt tuple; NO seats here.
      3. GET search/classes.json?courseId&courseOfferNumber&courseTopicId&effdt&strm&
         inst&car -> the SECTIONS WITH SEATS for that one catalog row.

    EFFICIENCY: the catalog (course->ids map) is STABLE per term, so it is scanned ONCE
    per term into a shared class-level cache (Purdue/TAMU envelope: ~36s cold, then warm);
    per poll we call ONLY classes.json for the watched courses. Partial scans are NEVER
    cached (a missing page = missing courses = silent miss), so a scan that hits any error
    is discarded and retried.

    ADDRESSABILITY: 478 subject+catalog combos are MULTI-ROW (variable-topic courses, e.g.
    AAAD-X 490 = 11 rows). A watched course maps to the LIST of its catalog rows and we
    AGGREGATE classes.json across all of them — complete-scope-then-filter, no split miss.
    If any row's classes fetch fails, the whole course is skipped that cycle (never a
    partial section set).

    OPEN RULE: closed is False AND openSeats > 0 (the boolean and arithmetic agreed 100%
    live). CROSS-LIST GUARD: for each combinedSections entry with separateEnrollmentControl
    FALSE (a shared pool), if combinedEnrollTotal >= combinedEnrollCapacity the section is
    full even if openSeats > 0 (when the control is separate, openSeats is authoritative).
    Consent flags are notes, not fake-open. Section key = classNbr (unique per term)."""
    id = "iub"; name = "Indiana University Bloomington"
    example = "ENG-W 131"                 # freshman comp; single catalog row
    inst = "IUBLA"; car = "UGRD"
    term = "4268"                         # Fall 2026 (auto-rolls via terms.json)
    _active_term = None
    _base = "https://sisjee.iu.edu/sisigps-prd/web/igps/course"
    _CAT_TTL = 21600                      # 6h; catalog is stable within a term
    _lock = threading.Lock()
    _catalog = {}                         # term -> (ts, {(subject,catalog): [rows]})
    _NULL_FILTERS = {"attributes": None, "level": None, "locations": None,
                     "meetingTimes": None, "mois": None, "sessions": None,
                     "subject": None, "units": None}
    _RE = re.compile(r"^(\S+)\s+(\S+)$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return "https://sisjee.iu.edu/sisigps-prd/web/igps/course/search/"

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def _post(self, url, body):
        req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                     headers={"User-Agent": UA, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def _scan_catalog(self, term):
        """Full catalog -> {(subject,catalog): [rows]}, or None on ANY failure (never
        cache a partial catalog — a missing page would silently drop watched courses)."""
        cat = {}
        offset = 0
        while offset < 12000:                        # defensive page cap (~240 pages)
            try:
                body = {"inst": self.inst, "strm": term,
                        "filters": dict(self._NULL_FILTERS), "from": offset}
                rows = (self._post(f"{self._base}/search/courses.json", body) or {}).get("courses") or []
            except Exception:
                return None
            if not rows:
                break
            for r in rows:
                key = (r.get("subject"), str(r.get("catalogNumber")))
                cat[key].append(r) if key in cat else cat.setdefault(key, [r])
            offset += 50
        return cat or None

    def _get_catalog(self, term):
        c = IUBloomington._catalog.get(term)
        if c and time.time() - c[0] < self._CAT_TTL:
            return c[1]
        if not IUBloomington._lock.acquire(blocking=(c is None)):
            return c[1] if c else {}                  # another thread building -> stale/empty
        try:
            again = IUBloomington._catalog.get(term)
            if again and time.time() - again[0] < self._CAT_TTL:
                return again[1]
            m = self._scan_catalog(term)
            if m:
                IUBloomington._catalog[term] = (time.time(), m)
                return m
            return again[1] if again else {}
        finally:
            IUBloomington._lock.release()

    def _classes(self, term, row):
        """Sections (with seats) for one catalog row, or None on failure."""
        try:
            url = (f"{self._base}/search/classes.json?courseId={row['courseId']}"
                   f"&courseOfferNumber={row['courseOfferNumber']}"
                   f"&courseTopicId={row['courseTopicId']}&effdt={row['effdt']}"
                   f"&strm={term}&inst={self.inst}&car={row.get('car', self.car)}")
            return (self._get(url) or {}).get("classes") or []
        except Exception:
            return None

    def fetch(self, courses):
        term = self.cur_term()
        cat = self._get_catalog(term)
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            rows = cat.get((subj, num))
            if not rows:
                continue
            secs, ok = {}, True
            for row in rows:                         # aggregate every catalog row (multi-topic)
                data = self._classes(term, row)
                if data is None:                     # a fetch failed -> skip whole course, no partial
                    ok = False
                    break
                for s in data:
                    key = str(s.get("classNbr") or "")
                    op = s.get("openSeats")
                    if not key or not isinstance(op, int) or key in secs:
                        continue
                    openb = (s.get("closed") is False) and op > 0
                    for cs in s.get("combinedSections") or []:
                        if not cs.get("separateEnrollmentControl"):   # shared pool binds
                            try:
                                if int(cs["combinedEnrollTotal"]) >= int(cs["combinedEnrollCapacity"]):
                                    openb = False
                            except (TypeError, ValueError, KeyError):
                                pass
                    secs[key] = {"open": openb, "seats": max(op, 0)}
            if ok and secs:
                out[course] = secs
        return out

    def resolve_term(self):
        try:
            terms = self._get(f"{self._base}/search/terms.json?inst={self.inst}")
        except Exception:
            return None
        today = datetime.date.today()
        best, best_delta = None, None
        for t in terms if isinstance(terms, list) else []:
            m = re.search(r"(spring|summer|fall|winter)\s+(20\d\d)", (t.get("descr") or "").lower())
            if not m:
                continue
            season, year = m.group(1), int(m.group(2))
            delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
            if not _auto_season(season) or delta < -1:
                continue
            if best_delta is None or delta < best_delta:
                best_delta, best = delta, t.get("strm")
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")


class MonroeCC:
    """Monroe Community College (NY, ~13k). Public static per-course HTML pages, no auth:
    GET /classes/{subj}-{num}-sections/ (lowercase-hyphenated, e.g. eng-101, mth-211) —
    each page IS the COMPLETE section list for exactly ONE course (headings confirm a
    single course code per page; no filtering, no pagination, NO cap — ENG-101 = the huge
    first-year course = 129 sections uncapped). So addressability is inherent.

    Each section block: '<span ...>CRN #{5-digit}</span>' then '<h4>Seats Remaining</h4>
    <p>{N}</p>'. Pair by CRN-BLOCK (split on CRN, take the Seats Remaining before the next
    CRN) — never a parallel-list zip, which would misalign if a section dropped a field.
    OPEN RULE: Seats Remaining > 0 (a full section shows 0, not a word). Waitlist counted
    separately, ignored. Section key = CRN (verified unique). The page is self-current
    (no term in the URL), so no term handling."""
    id = "monroecc-ny"; name = "Monroe Community College"
    example = "ENG 101"
    _base = "https://www.monroecc.edu/classes"
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{2,3}[A-Za-z]?)$")
    _CRN = re.compile(r"CRN\s*#?\s*(\d{4,6})")
    _SEATS = re.compile(r"<h4[^>]*>\s*Seats Remaining\s*</h4>\s*<p[^>]*>\s*(\d+)", re.I)

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).lower(), m.group(2).lower()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        subj, num = self._norm(course)
        return f"{self._base}/{subj}-{num}-sections/" if subj else f"{self._base}/"

    def fetch(self, courses):
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                req = urllib.request.Request(f"{self._base}/{subj}-{num}-sections/",
                                             headers={"User-Agent": UA})
                html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
            except Exception:
                continue
            parts = self._CRN.split(html)               # [pre, crn1, block1, crn2, block2, ...]
            secs = {}
            for i in range(1, len(parts), 2):
                crn = parts[i]
                block = parts[i + 1] if i + 1 < len(parts) else ""
                sm = self._SEATS.search(block)
                if not sm or crn in secs:               # no seat field -> skip; dedup by CRN
                    continue
                n = int(sm.group(1))
                secs[crn] = {"open": n > 0, "seats": n}
            if secs:
                out[course] = secs
        return out


class Wabash:
    """Wabash College (IN, ~900, private 4-yr men's college). Public GET HTML table, no
    auth: /apps/registrar/course-sections/?sortby=SectionName&term={term} (Fall 2026 =
    26/FA, completed Spring = 26/SP). Each row = SectionName (ACC-201-01) + textual status
    OPEN/CLOSED/WAITLISTED + 'enrolled / available / waitlist'.

    ⚠️ MULTI-MEETING TRAP: a section with >1 weekly meeting repeats as MULTIPLE rows with
    the SAME SectionName (status/seats identical) — dedup by SectionName or you double-
    count. OPEN RULE: status == 'OPEN' (WAITLISTED and CLOSED are their own statuses for
    full sections), and if the available number parses, require it > 0 (belt-and-suspenders;
    OPEN-with-0 -> not open). Section key = SectionName. Exact scope = SectionName starts
    with 'SUBJ-NUM-' (ACC 201 -> ACC-201-*, never ACC-202). Term auto-rolls from the page's
    own term dropdown."""
    id = "wabash"; name = "Wabash College"
    example = "ACC 201"
    term = "26/FA"                        # Fall 2026 (auto-rolls)
    _active_term = None
    _base = "https://www.wabash.edu/apps/registrar/course-sections/"
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{2,3}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return self._base

    def _get(self, term):
        url = self._base + "?sortby=SectionName&term=" + urllib.parse.quote(term)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")

    def fetch(self, courses):
        try:
            html = self._get(self.cur_term())
        except Exception:
            return {}
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            prefix = f"{subj}-{num}-"
            secs = {}
            for row in re.findall(r"<tr[^>]*>.*?</tr>", html, re.S):
                sm = re.search(r"\b(" + re.escape(subj) + r"-" + re.escape(num) + r"-\d{2,3})\b", row)
                if not sm:
                    continue
                key = sm.group(1)
                if key in secs:                     # dedup multi-meeting rows
                    continue
                st = re.search(r"\b(OPEN|CLOSED|WAITLISTED)\b", row)
                # available seats live in a dedicated span (NOT the flat 'e / a / w' text,
                # which a naive \d+/\d+/\d+ would mis-match to the m/d/yy date on the row)
                av = re.search(r'class="count available[^"]*">\s*(\d+)', row)
                avail = int(av.group(1)) if av else None
                openb = (st is not None and st.group(1) == "OPEN") and (avail is None or avail > 0)
                secs[key] = {"open": openb, "seats": avail if avail is not None else (0 if not openb else None)}
            if secs:
                out[course] = secs
        return out

    def resolve_term(self):
        """Nearest upcoming term from the page's own term <option>s (labels like
        '2026 Fall' -> value '26/FA'); skips past terms via the shared _SEASON delta."""
        try:
            html = self._get(self.cur_term())
        except Exception:
            return None
        today = datetime.date.today()
        best, best_delta = None, None
        for val, label in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>\s*(20\d\d\s+\w+)', html):
            m = re.search(r"(20\d\d)\s+(fall|spring|summer|winter)", label, re.I)
            if not m:
                continue
            year, season = int(m.group(1)), m.group(2).lower()
            delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
            if not _auto_season(season) or delta < -1:
                continue
            if best_delta is None or delta < best_delta:
                best_delta, best = delta, val.replace("&#x2f;", "/").replace("&#47;", "/")
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")


class PortlandCC:
    """Portland Community College (~70k, one of the largest CCs in the US). Public, no
    auth, REAL-TIME 2-step flow:
      1. GET /schedule/{termword}/{subj}/{subj}{num}/ -> the course's section rows carry
         data-crn (+ data-term = the PeopleSoft-style term code). Multi-MEETING sections
         repeat a CRN across rows; dedup by CRN (unique per section).
      2. POST /schedule/capacity/ {term, crn=comma-list} -> {CRN:{seat:[avail,cap],
         wait:[n,cap]}}. This is the AUTHORITATIVE real-time count.

    ⚠️ DO NOT trust the page's data-seats attribute — it is NOT the live available count
    (it reads '1' even on FULL sections; using it would FALSE-ALERT). Only the capacity
    POST's seat[0] is real. OPEN RULE: seat[0] (available) > 0. Waitlist (wait[]) is never
    a seat. Section key = CRN. Addressability: the course page lists exactly that course's
    CRNs (the wr121 path serves WR 121 / its Oregon-renumbered WR121Z as one course; the
    detail links confirm every CRN is that course), so complete-scope-then-POST is exact.

    Quarter system: only 1-2 terms are published at once; term auto-rolls to the newest
    published quarter (highest data-term across the four termword pages)."""
    id = "pcc-or"; name = "Portland Community College"
    example = "WR 121"
    _base = "https://www.pcc.edu/schedule"
    _CAP = "https://www.pcc.edu/schedule/capacity/"
    term = "202604"                       # Fall 2026 (auto-rolls)
    termword = "fall"
    _active = None                        # (termword, code) once resolved
    _WORDS = ("fall", "winter", "spring", "summer")
    _RE = re.compile(r"^([A-Za-z]{1,4})\s*(\d{2,3}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def _cur(self):
        return self._active or (self.termword, self.term)

    def cur_term(self):
        return self._cur()[1]

    def reg_url(self, course):
        subj, num = self._norm(course)
        tw = self._cur()[0]
        return f"{self._base}/{tw}/{subj.lower()}/{subj.lower()}{num.lower()}/" if subj else f"{self._base}/"

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")

    def fetch(self, courses):
        tw, code = self._cur()
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                page = self._get(f"{self._base}/{tw}/{subj.lower()}/{subj.lower()}{num.lower()}/")
            except Exception:
                continue
            crns = list(dict.fromkeys(re.findall(r'data-crn="(\d+)"', page)))
            if not crns:
                continue
            try:
                data = urllib.parse.urlencode({"term": code, "crn": ",".join(crns)}).encode()
                req = urllib.request.Request(self._CAP, data=data, headers={
                    "User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"})
                cap = json.loads(urllib.request.urlopen(req, timeout=30).read())
            except Exception:
                continue                            # capacity failed -> skip, never guess from page
            secs = {}
            for crn in crns:
                d = cap.get(crn) or cap.get(str(crn))
                seat = (d or {}).get("seat")
                if not seat or not isinstance(seat[0], int):
                    continue                        # no real count -> skip
                secs[str(crn)] = {"open": seat[0] > 0, "seats": max(seat[0], 0)}
            if secs:
                out[course] = secs
        return out

    def resolve_term(self):
        """Newest published quarter = highest data-term across the four termword pages
        (only 1-2 are live at once; the newest is the upcoming registration target)."""
        best = None
        for tw in self._WORDS:
            try:
                page = self._get(f"{self._base}/{tw}/{self.example.split()[0].lower()}/"
                                 f"{self.example.replace(' ', '').lower()}/")
            except Exception:
                continue
            codes = re.findall(r'data-term="(\d+)"', page)
            if codes:
                code = max(codes)
                if best is None or code > best[1]:
                    best = (tw, code)
        return best

    def refresh_term(self, log=None):
        new = self.resolve_term()
        if not new or new == self._cur():
            return
        prev = self._active
        self._active = new
        ok = bool(self.fetch({self.example}).get(self.example))
        if not ok:
            self._active = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self._cur()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or (self.termword, self.term)} -> {new}")


class UVI:
    """University of the Virgin Islands (~2k, ONE institution). Real-time ASP.NET
    schedule pages, one per campus (stt / stx / sxm — all UVI), combined into one
    school. ⚠️ The .aspx returns EMPTY on a plain GET unless a session cookie is
    carried (live-verified: plain GET flaky 0/384; cookiejar reliable 384) — so we
    fetch through a cookiejar opener, same as the Banner/Colleague families. The whole
    3-page dump is cached per term (TTL) and shared across courses.

    Columns (0-indexed): CRN(0) SUBJ(1) CRSE(2) SEC(3) ... MAX(11) ENROLL(12) AVAIL(13)
    ... STATUS(16). OPEN RULE: STATUS=='ACTIVE' AND AVAIL>0 (CANCELLED excluded — 19 in
    Fall). Section key = CRN (verified UNIQUE across all 3 campus pages — combining is
    safe). Exact scope = SUBJ + CRSE. Disproof: 66 live-term full ACTIVE rows + 41 in
    the completed term. Term pinned (bump per term)."""
    id = "uvi"; name = "University of the Virgin Islands"
    example = "ACC 201"
    term = "202608"                        # Fall 2026 (Spring 2026 = 202601)
    _PAGES = ("stt", "stx", "sxm")
    _URL = "https://schedclass.uvi.edu/{}schedule.aspx?term={}"
    _TTL = 300
    _lock = threading.Lock()
    _dump = {}                             # term -> (ts, rows)
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{2,3}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return self.term

    def reg_url(self, course):
        return self._URL.format(self._PAGES[0], self.cur_term())

    def _rows(self):
        term = self.cur_term()
        with UVI._lock:
            c = UVI._dump.get(term)
            if c and time.time() - c[0] < self._TTL:
                return c[1]
            cj = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            op.addheaders = [("User-Agent", UA)]
            rows = []
            for pg in self._PAGES:
                # These .aspx pages intermittently return an EMPTY table server-side.
                # Every real page has rows, so treat 0 as a flake and retry; if a page
                # never yields rows, DON'T cache a dump missing a whole campus — serve
                # the last complete dump instead (never a silent per-campus miss).
                pg_rows = []
                for _ in range(5):
                    try:
                        html = op.open(self._URL.format(pg, term), timeout=30).read().decode("utf-8", "replace")
                    except Exception:
                        continue
                    pg_rows = [cells for r in re.findall(r"<tr[^>]*>.*?</tr>", html, re.S)
                               for cells in [[re.sub(r"<[^>]+>", "", x).strip()
                                              for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]]
                               if len(cells) >= 17 and re.match(r"^\d{4,6}$", cells[0])]
                    if pg_rows:
                        break
                if not pg_rows:
                    return c[1] if c else []    # incomplete -> keep last-good, never partial
                rows += pg_rows
            UVI._dump[term] = (time.time(), rows)
            return rows

    def fetch(self, courses):
        rows = None
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            if rows is None:
                rows = self._rows()
            secs = {}
            for c in rows:
                if c[1].upper() != subj or c[2].upper() != num:
                    continue
                key = c[0]
                if key in secs:
                    continue
                try:
                    av = int(c[13])
                except (ValueError, IndexError):
                    continue                    # no numeric availability -> skip, never guess
                secs[key] = {"open": c[16] == "ACTIVE" and av > 0, "seats": max(av, 0)}
            if secs:
                out[course] = secs
        return out


class Cayuga:
    """Cayuga Community College (NY, ~4k). One public HTML page = the whole Fall
    catalog, frequently refreshed (page carries a live 'updated: <today> <time>'
    stamp, not a stale daily snapshot). Columns: CRN(0), Course(1)='SUBJ NUM-SEC',
    Course Title(2) with 'Availability: N' embedded. OPEN RULE: Availability > 0
    (a row with a blank Availability is skipped — never guessed open). Section key =
    CRN (verified unique). Exact scope = the Course cell's SUBJ+NUM. Term is in the
    URL path (/fall/)."""
    id = "cayuga"; name = "Cayuga Community College"
    example = "BIOL 100"
    _URL = "https://www.cayuga-cc.edu/academics/schedule-of-classes/fall/"
    _RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{2,3}[A-Za-z]?)$")
    _COURSE = re.compile(r"^([A-Za-z]{2,4})\s+(\d{2,3}[A-Za-z]?)-")

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return self._URL

    def fetch(self, courses):
        try:
            html = _http(self._URL)
        except Exception:
            return {}
        # parse once: rows -> (crn, subj, num, avail)
        parsed = []
        for r in re.findall(r"<tr[^>]*>.*?</tr>", html, re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
            if len(cells) < 3:
                continue
            crn = re.sub(r"<[^>]+>", " ", cells[0]).strip()
            if not re.match(r"^\d{4,6}$", crn):
                continue
            cm = self._COURSE.match(re.sub(r"<[^>]+>", " ", cells[1]).strip())
            am = re.search(r"Availability:\s*(\d+)", re.sub(r"<[^>]+>", " ", cells[2]))
            if not cm or not am:               # no course code or blank availability -> skip
                continue
            parsed.append((crn, cm.group(1).upper(), cm.group(2).upper(), int(am.group(1))))
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            secs = {}
            for crn, s, n, av in parsed:
                if s == subj and n == num and crn not in secs:
                    secs[crn] = {"open": av > 0, "seats": av}
            if secs:
                out[course] = secs
        return out


class GeorgiaTech(Banner):
    id = "gatech"; name = "Georgia Tech"
    example = "CS 1301"; host = "registration.banner.gatech.edu"; term = "202608"

class Northeastern(Banner):
    id = "northeastern"; name = "Northeastern University"
    example = "CS 2001"; host = "nubanner.neu.edu"; term = "202710"

class EmpireState(Banner):
    id = "suny-esc"; name = "SUNY Empire State University"
    example = "ACCT 1005"; host = "banner.esc.edu"; term = "202680"

class TexasState(Banner):
    id = "txst"; name = "Texas State University"
    example = "CS 1428"; host = "reg-prod.ec.txstate.edu"; term = "202710"

class Temple(Banner):
    id = "temple"; name = "Temple University"
    example = "CIS 1068"; host = "prd-xereg.temple.edu"; term = "202636"

class Villanova(Banner):
    id = "villanova"; name = "Villanova University"
    example = "CSC 1051"; host = "banssb9.villanova.edu"; term = "202720"

class CofC(Banner):
    id = "cofc"; name = "College of Charleston"
    example = "CSCI 220"; host = "ssb.cofc.edu"; term = "202710"

class SouthFlorida(Banner):
    id = "usf"; name = "University of South Florida"
    example = "COP 2510"; host = "studentssb9.it.usf.edu"; term = "202608"

class Oklahoma(Banner):
    id = "ou"; name = "University of Oklahoma"
    example = "C S 2334"; host = "sis.ou.edu"; term = "202610"

class GeorgiaState(Banner):
    id = "gsu"; name = "Georgia State University"
    example = "CSC 1301"; host = "registration.gosolar.gsu.edu"; term = "202608"

class PortlandState(Banner):
    id = "pdx"; name = "Portland State University"
    example = "CS 161"; host = "app.banner.pdx.edu"; term = "202604"

class Drexel(Banner):
    id = "drexel"; name = "Drexel University"
    example = "CS 171"; host = "banner.drexel.edu"; term = "202611"
    base_path = "registration"

# --- University System of Georgia: shared {code}.gabest.usg.edu Banner (term 202608) ---
class GeorgiaSouthern(Banner):
    id = "gasou"; name = "Georgia Southern University"
    example = "CSCI 1301"; host = "georgiasouthern.gabest.usg.edu"; term = "202608"

class WestGeorgia(Banner):
    id = "westga"; name = "University of West Georgia"
    example = "CS 1301"; host = "westga.gabest.usg.edu"; term = "202608"

class Valdosta(Banner):
    id = "valdosta"; name = "Valdosta State University"
    example = "CSCI 1301K"; host = "valdosta.gabest.usg.edu"; term = "202608"

class GeorgiaGwinnett(Banner):
    id = "ggc"; name = "Georgia Gwinnett College"
    example = "CSCI 1301K"; host = "ggc.gabest.usg.edu"; term = "202608"

class ColumbusState(Banner):
    id = "columbusst"; name = "Columbus State University"
    example = "CSCI 1301K"; host = "columbusstate.gabest.usg.edu"; term = "202608"

class GeorgiaCollege(Banner):
    id = "gcsu"; name = "Georgia College & State University"
    example = "CSCI 1301"; host = "gcsu.gabest.usg.edu"; term = "202608"

class MiddleGeorgia(Banner):
    id = "mga"; name = "Middle Georgia State University"
    example = "CSCI 1301"; host = "mga.gabest.usg.edu"; term = "202608"

class ClaytonState(Banner):
    id = "clayton"; name = "Clayton State University"
    example = "CSCI 1301"; host = "clayton.gabest.usg.edu"; term = "202608"

class GeorgiaSouthwestern(Banner):
    id = "gsw"; name = "Georgia Southwestern State University"
    example = "CSCI 1301"; host = "gsw.gabest.usg.edu"; term = "202608"

class FortValleyState(Banner):
    id = "fvsu"; name = "Fort Valley State University"
    example = "ENGL 1101"; host = "fvsu.gabest.usg.edu"; term = "202608"

# NOTE: Albany State University is served by AlbanyStateGA (id "asu-ga", the school's
# own host banner.asurams.edu) — the long-standing canonical entry. A duplicate on the
# USG shared gabest host (id "asurams") was added July 8 and REMOVED as a dup; do not
# re-add Albany State on gabest.
class AugustaUniversity(Banner):
    id = "augusta"; name = "Augusta University"
    example = "CSCI 1301"; host = "pounce.augusta.edu"; term = "202608"

# --- Ellucian-cloud-hosted (reg-prod.ec.{domain}) + individually verified ---
class VCU(Banner):
    id = "vcu"; name = "Virginia Commonwealth University"
    example = "CMSC 210"; host = "reg-prod.ec.vcu.edu"; term = "202710"

class OldDominion(Banner):
    id = "odu"; name = "Old Dominion University"
    example = "CS 115"; host = "reg-prod.ec.odu.edu"; term = "202610"

class ConnecticutState(Banner):
    id = "ctstate"; name = "Connecticut State Community College"
    example = "CSC 1201"; host = "reg-prod.ec.ct.edu"; term = "202710"

class LouisianaLafayette(Banner):
    id = "ull"; name = "University of Louisiana at Lafayette"
    example = "CMPS 150"; host = "reg-prod.ec.louisiana.edu"; term = "202720"

class GrandValley(Banner):
    id = "gvsu"; name = "Grand Valley State University"
    example = "CIS 150"; host = "xe3a.mybanner.gvsu.edu"; term = "202710"

class Radford(Banner):
    id = "radford"; name = "Radford University"
    example = "CS 101"; host = "reg-prod.ec.radford.edu"; term = "202610"

class Fordham(Banner):
    id = "fordham"; name = "Fordham University"
    example = "CISC 1600"; host = "reg-prod.ec.fordham.edu"; term = "202710"

# PARKED (2026-07-04): bannerxe.appstate.edu intermittently returns EMPTY even under
# gentle sequential polling (verified 34,34,34,0,0) — fail-safe keeps it from sending
# false data, but the flakiness risks MISSING openings. Removed per reliability-first
# rule. Re-add only if the host proves consistently stable.
class AppalachianState(Banner):
    id = "appstate"; name = "Appalachian State University"
    example = "CIS 1060"; host = "bannerxe.appstate.edu"; term = "202640"

class SouthernUtah(Banner):
    id = "suu"; name = "Southern Utah University"
    example = "CS 1400"; host = "bannerxe.suu.edu"; term = "202630"

class UtahState(Banner):
    id = "usu"; name = "Utah State University"
    example = "CS 1400"; host = "ss.banner.usu.edu"; term = "202640"

class MiamiOhio(Banner):
    id = "miamioh"; name = "Miami University (Ohio)"
    example = "CSE 148"; host = "banss.miamioh.edu"; term = "202710"

class MississippiState(Banner):
    id = "msstate"; name = "Mississippi State University"
    example = "CSE 1284"; host = "mybanner.msstate.edu"; term = "202630"

class Skidmore(Banner):
    id = "skidmore"; name = "Skidmore College"
    example = "CS 106"; host = "bannerxe.skidmore.edu"; term = "202690"

class Montclair(Banner):
    id = "montclair"; name = "Montclair State University"
    example = "CSIT 100"; host = "student-ssb-regis.montclair.edu"; term = "202640"

class MaryWashington(Banner):
    id = "umw"; name = "University of Mary Washington"
    example = "CPSC 110"; host = "reg-prod.ec.umw.edu"; term = "202608"

class UNCCharlotte(Banner):
    id = "uncc"; name = "UNC Charlotte"
    example = "ITCS 3050"; host = "selfservice.uncc.edu"; term = "202680"

class WesternMichigan(Banner):
    id = "wmich"; name = "Western Michigan University"
    example = "CS 1110"; host = "bannerweb.wmich.edu"; term = "202640"

class WichitaState(Banner):
    id = "wichita"; name = "Wichita State University"
    example = "CS 211"; host = "ssbprod.wichita.edu"; term = "202710"

class TexasTech(Banner):
    id = "ttu"; name = "Texas Tech University"
    example = "CS 1382"; host = "registration.texastech.edu"; term = "202727"; mep = "TTU"

class UCRiverside(Banner):
    id = "ucr"; name = "UC Riverside"
    example = "CS 009A"; host = "registrationssb.ucr.edu"; term = "202640"

class UTSA(Banner):
    id = "utsa"; name = "UT San Antonio"
    example = "CS 1083"; host = "ssbprod.utsa.edu"; term = "202710"

class UTEP(Banner):
    id = "utep"; name = "UT El Paso"
    example = "CS 2401"; host = "goldmine9reg.utep.edu"; term = "202710"

class Memphis(Banner):
    id = "memphis"; name = "University of Memphis"
    example = "COMP 1900"; host = "register.bannerprod.memphis.edu"; term = "202680"

class BuffaloState(Banner):
    id = "buffstate"; name = "SUNY Buffalo State University"
    example = "CIS 101"; host = "banner.buffalostate.edu"; term = "202630"

class CCSF(Banner):
    id = "ccsf"; name = "City College of San Francisco"
    example = "CS 110A"; host = "ssb1.ccsf.edu:8105"; term = "202670"

# --- South Dakota regental system: ONE shared Banner host + ONE shared course pool for
# --- all six public universities. Rows are separated ONLY by campusDescription, so each
# --- school subclass sets `campus` and fetch() filters to it (no cross-campus mixups).
class IECC(Banner):
    # Illinois Eastern CC — 3 colleges on one Banner-9 host (:8447), separated by
    # campusDescription first token (SD-regental pattern). Base seats>0 rule is
    # waitlist-safe. Subclasses set id, name, example, campus.
    host = "banprodss1.iecc.edu:8447"; term = "202730"   # Fall 2026 (auto-rolls)

class WabashValley(IECC):
    id = "wabashvalley"; name = "Wabash Valley College"
    example = "ENG 1111"; campus = "WABASH"

class OlneyCentral(IECC):
    id = "olneycentral"; name = "Olney Central College"
    example = "ENG 1111"; campus = "OLNEY"

class LincolnTrail(IECC):
    id = "lincolntrail"; name = "Lincoln Trail College"
    example = "ENG 1111"; campus = "LINCOLN"

# --- Codex batches 87/91-94 (Grab-relayed, re-gated live). Stock Banner9 unless noted. ---
class SUNYDelhi(Banner):
    id = "sunydelhi"; name = "SUNY Delhi"
    example = "ENGL 100"; host = "prod.banner.delhi.edu"; term = "202609"

class GuamCC(Banner):
    id = "guamcc"; name = "Guam Community College"   # != Univ of Guam (Colleague)
    example = "EN 110"; host = "reg-prod.gcctmsaas.elluciancloud.com:8103"; term = "202680"

class Washburn(Banner):
    id = "washburn"; name = "Washburn University"
    example = "EN 101"; host = "banssb-lb-prod.washburn.edu"; term = "202630"

class MurrayState(Banner):
    # REJECT 'Racer Academy' rows: concurrent/high-school sections with real open seats a
    # normal student can't register for = eligibility false-open.
    id = "murraystate"; name = "Murray State University"
    example = "ENG 105"; host = "prodssbstureg.murraystate.edu"; term = "202680"
    def _eligible(self, r):
        return "racer academy" not in (r.get("instructionalMethodDescription") or "").lower()

class NorthAlabama(Banner):
    # REJECT 'Taught at High School' rows (same eligibility false-open risk).
    id = "una"; name = "University of North Alabama"
    example = "EN 111"; host = "selfserve.una.edu"; term = "202710"
    def _eligible(self, r):
        return "taught at high school" not in (r.get("instructionalMethodDescription") or "").lower()

class SIUCarbondale(Banner):
    id = "siuc"; name = "Southern Illinois University Carbondale"   # != SIUE (shipped)
    example = "ENGL 101"; host = "banssb1.siu.edu"; term = "202660"

class PascoHernando(Banner):
    id = "phsc"; name = "Pasco-Hernando State College"
    example = "ENC 1101"; host = "reg-prod.phsc.elluciancloud.com:8103"; term = "202701"

class USI(Banner):
    # USI stores courseNumber with a LITERAL TRAILING PERIOD ('ENG 101.') — the base
    # regex would send '101' and match nothing. Append the period so txt_courseNumber
    # and the exact-row match both use '101.'.
    id = "usi"; name = "University of Southern Indiana"
    example = "ENG 101"; host = "banproxyp.usi.edu"; term = "202710"
    @staticmethod
    def _code(course):
        subj, num = Banner._code(course)
        return (subj, (num + ".") if num else num)

class SouthDakota(Banner):
    host = "registration.sdbor.edu"; term = "202680"; mep = "BOR"

class USD(SouthDakota):
    id = "usd"; name = "University of South Dakota"
    example = "MATH 114"; campus = "USD"

class SDStateU(SouthDakota):
    id = "sdstate"; name = "South Dakota State University"
    example = "MATH 114"; campus = "SDSU"

class BlackHillsState(SouthDakota):
    id = "bhsu"; name = "Black Hills State University"
    example = "MATH 114"; campus = "BHSU"

class NorthernStateU(SouthDakota):
    id = "northernst"; name = "Northern State University"
    example = "MATH 114"; campus = "NSU"

class DakotaState(SouthDakota):
    id = "dsu"; name = "Dakota State University"
    example = "CSC 105"; campus = "DSU"

class SDMines(SouthDakota):
    id = "sdmines"; name = "South Dakota Mines"
    example = "MATH 125"; campus = "SDSMT"

class Alabama(Banner):
    id = "ua"; name = "University of Alabama"
    example = "CS 100"; host = "bannerssb.ua.edu"; term = "202640"

class Idaho(Banner):
    id = "uidaho"; name = "University of Idaho"
    example = "CS 1120"; host = "banner.uidaho.edu"; term = "202610"

class OklahomaState(Banner):
    id = "okstate"; name = "Oklahoma State University"
    example = "CS 1113"; host = "studentregistrationssb.okstate.edu"; term = "202660"; mep = "OSU"

class WeberState(Banner):
    id = "weber"; name = "Weber State University"
    example = "CS 1030"; host = "selfservice.weber.edu"; term = "202720"

class Montana(Banner):
    id = "umontana"; name = "University of Montana"
    example = "CSCI 150"; host = "reg-prod.ec.umt.edu"; term = "202670"

class Tarleton(Banner):
    id = "tarleton"; name = "Tarleton State University"
    example = "COSC 1302"; host = "reg-prod.ec.tarleton.edu"; term = "202608"

class UNCWilmington(Banner):
    id = "uncw"; name = "UNC Wilmington"
    example = "CSC 131"; host = "registration.uncw.edu"; term = "202710"

class Longwood(Banner):
    id = "longwood"; name = "Longwood University"
    example = "CMSC 140"; host = "reg-prod.ec.longwood.edu"; term = "202710"

class WestChester(Banner):
    id = "wcupa"; name = "West Chester University"
    example = "CSC 112"; host = "reg-prod.ec.wcupa.edu"; term = "202630"

class SUNYPlattsburgh(Banner):
    id = "plattsburgh"; name = "SUNY Plattsburgh"
    example = "CSC 119"; host = "banner.plattsburgh.edu"; term = "202640"

class ULMonroe(Banner):
    id = "ulm"; name = "UL Monroe"
    example = "CSCI 1070"; host = "reg-prod.ec.ulm.edu"; term = "202740"

class McNeese(Banner):
    id = "mcneese"; name = "McNeese State University"
    example = "CSCI 100"; host = "reg-prod.ec.mcneese.edu"; term = "202660"

class Grambling(Banner):
    id = "grambling"; name = "Grambling State University"
    example = "CS 110"; host = "reg-prod.ec.gram.edu"; term = "202710"

class SUNYGeneseo(Banner):
    id = "geneseo"; name = "SUNY Geneseo"
    example = "MATH 140"; host = "bannerweb.geneseo.edu"; term = "202609"

class SUNYFarmingdale(Banner):
    id = "farmingdale"; name = "SUNY Farmingdale"
    example = "CSC 111"; host = "banner.farmingdale.edu"; term = "202609"

class SUNYPoly(Banner):
    id = "sunypoly"; name = "SUNY Polytechnic Institute"
    example = "MAT 110"; host = "banner.sunypoly.edu"; term = "202609"

class SUNYMorrisville(Banner):
    id = "morrisville"; name = "SUNY Morrisville"
    example = "COMP 101"; host = "banner.morrisville.edu"; term = "202608"

class SUNYAlfredState(Banner):
    id = "alfredstate"; name = "SUNY Alfred State"
    example = "COMP 1503"; host = "banner.alfredstate.edu"; term = "202608"

class CentralCTState(Banner):
    id = "ccsu"; name = "Central Connecticut State University"
    example = "CS 253"; host = "reg-prod.ec.ccsu.edu"; term = "202710"

class SouthernCTState(Banner):
    id = "scsu"; name = "Southern Connecticut State University"
    example = "CSC 200"; host = "reg-prod.ec.southernct.edu"; term = "202710"

class WesternCTState(Banner):
    id = "wcsu"; name = "Western Connecticut State University"
    example = "CS 110"; host = "reg-prod.ec.wcsu.edu"; term = "202710"

class EasternCTState(Banner):
    id = "ecsu"; name = "Eastern Connecticut State University"
    example = "CSC 180"; host = "reg-prod.ec.easternct.edu"; term = "202710"

class StJosephs(Banner):
    id = "sju"; name = "Saint Joseph's University"
    example = "MAT 115"; host = "registration.sju.edu"; term = "202640"

class Rider(Banner):
    id = "rider"; name = "Rider University"
    example = "MTH 102"; host = "reg-prod.ec.rider.edu"; term = "202710"

class Kennesaw(Banner):
    id = "kennesaw"; name = "Kennesaw State University"
    example = "CSE 1321L"; host = "srs-owlexpress.kennesaw.edu"; term = "202608"

class WayneState(Banner):
    id = "wayne"; name = "Wayne State University"
    example = "MAT 1010"; host = "registration.wayne.edu"; term = "202609"

class Dayton(Banner):
    id = "dayton"; name = "University of Dayton"
    example = "CPS 150"; host = "banner.udayton.edu"; term = "202680"

class Xavier(Banner):
    id = "xavier"; name = "Xavier University"
    example = "CSCI 170"; host = "reg-prod.ec.xavier.edu"; term = "202609"

class MSUDenver(Banner):
    id = "msudenver"; name = "Metropolitan State University of Denver"
    example = "CS 1030"; host = "ssb.msudenver.edu"; term = "202650"

class ColoradoMesa(Banner):
    id = "coloradomesa"; name = "Colorado Mesa University"
    example = "MATH 113"; host = "reg-prod.ec.coloradomesa.edu"; term = "202602"

class EasternWashington(Banner):
    id = "ewu"; name = "Eastern Washington University"
    example = "MATH 107"; host = "reg-prod.ec.ewu.edu"; term = "202640"

class SouthAlabama(Banner):
    id = "southalabama"; name = "University of South Alabama"
    example = "CSC 120"; host = "banssb.southalabama.edu"; term = "202710"

class TennesseeState(Banner):
    id = "tnstate"; name = "Tennessee State University"
    example = "MATH 1710"; host = "banner.tnstate.edu"; term = "202680"

class Stockton(Banner):
    id = "stockton"; name = "Stockton University"
    example = "CSCI 2101"; host = "banner.stockton.edu"; term = "202680"

class AlbanyStateGA(Banner):
    id = "asu-ga"; name = "Albany State University"
    example = "CSCI 1300"; host = "banner.asurams.edu"; term = "202608"

class SIUE(Banner):
    id = "siue"; name = "Southern Illinois University Edwardsville"
    example = "CS 140"; host = "banner.siue.edu"; term = "202635"

class SanJacinto(Banner):
    id = "sanjac"; name = "San Jacinto College"
    example = "COSC 1436"; host = "reg-prod.ec.sanjac.edu"; term = "202710"

class DMACC(Banner):
    id = "dmacc"; name = "Des Moines Area Community College"
    example = "CSC 116"; host = "reg-prod.ec.dmacc.edu"; term = "202701"

class PimaCC(Banner):
    id = "pima"; name = "Pima Community College"
    example = "CIS 120"; host = "ssb.pima.edu"; term = "202710"

class JohnsonCountyCC(Banner):
    id = "jccc"; name = "Johnson County Community College"
    example = "CS 134"; host = "reg-prod.ec.jccc.edu"; term = "202608"

class Vincennes(Banner):
    id = "vincennes"; name = "Vincennes University"
    example = "MATH 102"; host = "banssb.vinu.edu"; term = "202710"

class NortheasternStateOK(Banner):
    id = "nsuok"; name = "Northeastern State University"
    example = "MATH 1513"; host = "banner.nsuok.edu"; term = "202720"

class YoungstownState(Banner):
    id = "ysu"; name = "Youngstown State University"
    example = "MATH 1510"; host = "ssb.oci.ysu.edu"; term = "202640"

class USFSanFrancisco(Banner):
    id = "usfca"; name = "University of San Francisco"
    example = "CS 686"; host = "reg-prod.ec.usfca.edu"; term = "202640"

# --- Pennsylvania State System (PASSHE): ONE shared Ellucian-cloud host serving all
# --- campuses, distinguished by mepCode (6-digit federal OPEID). All verified clean
# --- (distinct section sequence numbers — no Pasadena-style collapse). Term 202630.
class PASSHE(Banner):
    host = "reg-prod.ec.passhe.edu"; term = "202630"

class IUP(PASSHE):
    id = "iup"; name = "Indiana University of Pennsylvania"
    example = "MATH 117"; mep = "003277"

class Bloomsburg(PASSHE):
    id = "bloomsburg"; name = "Bloomsburg University (Commonwealth U)"
    example = "MATH 118"; mep = "003315"

class CaliforniaPA(PASSHE):
    id = "calu"; name = "California University of Pennsylvania (PennWest)"
    example = "MATH 1010"; mep = "003316"

class Cheyney(PASSHE):
    id = "cheyney"; name = "Cheyney University"
    example = "MATH 1108"; mep = "003317"

class EastStroudsburg(PASSHE):
    id = "esu"; name = "East Stroudsburg University"
    example = "MATH 110"; mep = "003320"

class Kutztown(PASSHE):
    id = "kutztown"; name = "Kutztown University"
    example = "MATH 103"; mep = "003322"

class Millersville(PASSHE):
    id = "millersville"; name = "Millersville University"
    example = "MATH 101"; mep = "003325"

class Shippensburg(PASSHE):
    id = "ship"; name = "Shippensburg University"
    example = "MATH 100"; mep = "003326"

class SlipperyRock(PASSHE):
    id = "sru"; name = "Slippery Rock University"
    example = "MATH 117"; mep = "003327"

# --- Louisiana Community & Technical College System: shared host, letter mepCodes.
# --- Only campuses that pass the section-collapse screen are included.
class LCTCS(Banner):
    host = "reg-prod.ec.lctcs.edu"; term = "202710"

class BatonRougeCC(LCTCS):
    id = "brcc"; name = "Baton Rouge Community College"; example = "MATH 0213"; mep = "BRCC"

class Delgado(LCTCS):
    id = "delgado"; name = "Delgado Community College"; example = "MATH 030"; mep = "DCC"

class SouthLouisianaCC(LCTCS):
    id = "slcc-la"; name = "South Louisiana Community College"; example = "MATH 0088"; mep = "SLCC"

class BossierParish(LCTCS):
    id = "bpcc"; name = "Bossier Parish Community College"; example = "MATH 102"; mep = "BPCC"

class RiverParishes(LCTCS):
    id = "rpcc"; name = "River Parishes Community College"; example = "MATH 1203"; mep = "RPCC"

class SOWELA(LCTCS):
    id = "sowela"; name = "SOWELA Technical Community College"; example = "MATH 1106"; mep = "SOWELA"

class Nunez(LCTCS):
    id = "nunez"; name = "Nunez Community College"; example = "MATH 1310"; mep = "NUNEZ"

# --- Alabama Community College System: shared host, letter mepCodes. Half the campuses
# --- collapse sections (rejected); only the clean ones are here.
class ACCS(Banner):
    """Alabama CC System: ONE Ellucian Cloud host, mep per college. ACCS MIXES
    zero-seq and real-seq courses even within a single college (audited live July 8:
    Southern Union HIS 101 = 23 sections ALL sequenceNumber='0' — collapsing to ONE
    key under the default; Wallace-Dothan MTH 116 likewise), so EVERY ACCS college
    keys sections by CRN (verified distinct on zero-seq courses). This changed the
    section keys for the 9 originally-shipped colleges — any pre-existing watch
    pinned to an old-style section key on those schools must be re-created (checked
    at migration time; see deploy note in the July 8 commit)."""
    host = "reg-prod.ec.accs.edu"; term = "202710"

    def _seckey(self, r):
        return r.get("courseReferenceNumber")

class ChattahoocheeValley(ACCS):
    id = "cvcc"; name = "Chattahoochee Valley Community College"; example = "MTH 099"; mep = "CVCC"

class WallaceDothan(ACCS):
    id = "wcc-al"; name = "Wallace Community College (Dothan)"; example = "MTH 100"; mep = "WCC"

class GadsdenState(ACCS):
    id = "gscc"; name = "Gadsden State Community College"; example = "MTH 100"; mep = "GSCC"

class SheltonState(ACCS):
    id = "sscc"; name = "Shelton State Community College"; example = "MTH 100"; mep = "SSCC"

class CalhounCC(ACCS):
    id = "calhoun"; name = "Calhoun Community College"; example = "MTH 100"; mep = "CCC"

class SouthernUnion(ACCS):
    id = "suscc"; name = "Southern Union State Community College"; example = "MTH 100"; mep = "SUSCC"

class BishopState(ACCS):
    id = "bishop"; name = "Bishop State Community College"; example = "MTH 100"; mep = "BISHOP"

class CoastalAlabama(ACCS):
    id = "coastal-al"; name = "Coastal Alabama Community College"; example = "MTH 099"; mep = "COASTL"

class ReidState(ACCS):
    id = "reid"; name = "Reid State Technical College"; example = "MTH 100"; mep = "RSTC"

# July 8 batch 3 — the remaining 15 ACCS colleges (mep->college identity confirmed via
# campusDescription geography, per the research handoff; every one gated live).
class JeffersonStateCC(ACCS):
    id = "jeffstate"; name = "Jefferson State Community College"; example = "ACT 145"; mep = "JSCC"

class LawsonState(ACCS):
    id = "lawson"; name = "Lawson State Community College"; example = "ACR 111"; mep = "LAWSON"

class LurleenBWallace(ACCS):
    id = "lbwcc"; name = "Lurleen B. Wallace Community College"; example = "ART 100"; mep = "LBWCC"

class NorthwestShoals(ACCS):
    id = "nwscc"; name = "Northwest-Shoals Community College"; example = "ART 100"; mep = "NWSCC"

class TrenholmState(ACCS):
    id = "trenholm"; name = "Trenholm State Community College"; example = "ADM 100"; mep = "TSCC"

class WallaceSelma(ACCS):
    id = "wccs"; name = "Wallace Community College Selma"; example = "BIO 103"; mep = "WCCS"

class BevillState(ACCS):
    id = "bevill"; name = "Bevill State Community College"; example = "ADM 101"; mep = "BSCC"

class EnterpriseState(ACCS):
    id = "escc"; name = "Enterprise State Community College"; example = "ADM 110"; mep = "ESCC"

class SneadState(ACCS):
    id = "snead"; name = "Snead State Community College"; example = "ACR 128"; mep = "SNEAD"

class IngramState(ACCS):
    id = "ingram"; name = "J.F. Ingram State Technical College"; example = "ABR 111"; mep = "ISTC"

class CentralAlabama(ACCS):
    id = "cacc"; name = "Central Alabama Community College"; example = "ANT 200"; mep = "CACC"

class DrakeState(ACCS):
    id = "drakestate"; name = "J.F. Drake State Community & Technical College"; example = "ADM 101"; mep = "DRAKE"

class MarionMilitary(ACCS):
    id = "mmi"; name = "Marion Military Institute"; example = "ART 100"; mep = "MMI"

class NortheastAlabama(ACCS):
    id = "nacc"; name = "Northeast Alabama Community College"; example = "ADM 110"; mep = "NACC"

class WallaceHanceville(ACCS):
    id = "wallacestate"; name = "Wallace State Community College (Hanceville)"; example = "ART 100"; mep = "WSCC"

# --- Colorado Community College System: ONE Banner 9 host (selfservice.cccs.edu) serves
# --- all 13 state-system colleges via mepCode. Codes verified two ways: an invalid code
# --- fails LOUDLY (MepCodeNotFoundException, no silent wrong-college data), and each
# --- accepted code was identity-checked against live data (campusDescription prefixes
# --- match the college, e.g. mep PPCC -> 'PPSC ...' campuses = Pikes Peak State College).
# --- Colorado common course numbering: ENG 1021 = English Comp I system-wide.
class CCCS(Banner):
    host = "selfservice.cccs.edu"; term = "202720"

class ArapahoeCC(CCCS):
    id = "co-arapahoe"; name = "Arapahoe Community College"; example = "ENG 1021"; mep = "ACC"

class CCAurora(CCCS):
    id = "co-aurora"; name = "Community College of Aurora"; example = "ENG 1021"; mep = "CCA"

class CCDenver(CCCS):
    id = "co-denver"; name = "Community College of Denver"; example = "ENG 1021"; mep = "CCD"

class ColoradoNorthwestern(CCCS):
    id = "co-northwestern"; name = "Colorado Northwestern Community College"; example = "ENG 1021"; mep = "CNCC"

class FrontRange(CCCS):
    id = "co-frontrange"; name = "Front Range Community College"; example = "ENG 1021"; mep = "FRCC"

class LamarCC(CCCS):
    id = "co-lamar"; name = "Lamar Community College"; example = "ENG 1021"; mep = "LCC"

class MorganCC(CCCS):
    id = "co-morgan"; name = "Morgan Community College"; example = "ENG 1021"; mep = "MCC"

class NortheasternJC(CCCS):
    id = "co-njc"; name = "Northeastern Junior College"; example = "ENG 1021"; mep = "NJC"

class OteroCollege(CCCS):
    id = "co-otero"; name = "Otero College"; example = "ENG 1021"; mep = "OJC"

class PikesPeak(CCCS):
    id = "co-pikespeak"; name = "Pikes Peak State College"; example = "ENG 1021"; mep = "PPCC"

class PuebloCC(CCCS):
    id = "co-pueblo"; name = "Pueblo Community College"; example = "ENG 1021"; mep = "PCC"

class RedRocks(CCCS):
    id = "co-redrocks"; name = "Red Rocks Community College"; example = "ENG 1021"; mep = "RRCC"

class TrinidadState(CCCS):
    id = "co-trinidad"; name = "Trinidad State College"; example = "ENG 1021"; mep = "TSJC"

class ColoradoStateFC(Banner):
    id = "csu"; name = "Colorado State University"
    example = "CS 150B"; host = "reg-sis.colostate.edu"; term = "202690"; mep = "CSU"

class ArkansasTech(Banner):
    id = "atu"; name = "Arkansas Tech University"
    example = "MATH 1113"; host = "reg-prod.ec.atu.edu"; term = "202670"

class UtahTech(Banner):
    id = "utahtech"; name = "Utah Tech University"
    example = "CS 1400"; host = "banner.utahtech.edu"; term = "202640"

class MontanaTech(Banner):
    id = "mtech"; name = "Montana Technological University"
    example = "M 171"; host = "reg-prod.ec.mtech.edu"; term = "202670"

class NMHighlands(Banner):
    id = "nmhu"; name = "New Mexico Highlands University"
    example = "MATH 1215"; host = "reg-prod.ec.nmhu.edu"; term = "202710"

class WesternNM(Banner):
    id = "wnmu"; name = "Western New Mexico University"
    example = "MATH 1215"; host = "reg-prod.ec.wnmu.edu"; term = "202710"

class WesternOregon(Banner):
    id = "wou"; name = "Western Oregon University"
    example = "MTH 105Z"; host = "reg-prod.ec.wou.edu"; term = "202601"

class OregonTech(Banner):
    id = "oit"; name = "Oregon Institute of Technology"
    example = "CST 162"; host = "reg-prod.ec.oit.edu"; term = "202601"

class NJIT(Banner):
    id = "njit"; name = "New Jersey Institute of Technology"
    example = "CS 100"; host = "reg-prod.ec.njit.edu"; term = "202690"

class Lehigh(Banner):
    id = "lehigh"; name = "Lehigh University"
    example = "MATH 021"; host = "reg-prod.ec.lehigh.edu"; term = "202640"

class TexasSouthern(Banner):
    id = "txso"; name = "Texas Southern University"
    example = "MATH 1314"; host = "reg-prod.ec.tsu.edu"; term = "202710"

class SUNYMaritime(Banner):
    id = "maritime"; name = "SUNY Maritime College"
    example = "CS 101"; host = "banner.sunymaritime.edu"; term = "202650"

class Providence(Banner):
    id = "providence"; name = "Providence College"
    example = "MTH 108"; host = "selfservice.providence.edu"; term = "202710"

class Samford(Banner):
    id = "samford"; name = "Samford University"
    example = "COSC 107"; host = "ssb.samford.edu"; term = "202670"

class Belmont(Banner):
    id = "belmont"; name = "Belmont University"
    example = "MTH 1110"; host = "reg-prod.ec.belmont.edu"; term = "202710"

class DetroitMercy(Banner):
    id = "udmercy"; name = "University of Detroit Mercy"
    example = "CST 1010"; host = "reg-prod.ec.udmercy.edu"; term = "202710"

class Kettering(Banner):
    id = "kettering"; name = "Kettering University"
    example = "MATH 100"; host = "reg-prod.ec.kettering.edu"; term = "202604"

class Andrews(Banner):
    id = "andrews"; name = "Andrews University"
    example = "MATH 168"; host = "banner.andrews.edu"; term = "202641"

class JohnCarroll(Banner):
    id = "jcu"; name = "John Carroll University"
    example = "MT 1300"; host = "banner.jcu.edu"; term = "202630"

class Otterbein(Banner):
    id = "otterbein"; name = "Otterbein University"
    example = "MATH 1240"; host = "reg.otterbein.edu"; term = "202640"

class StEdwards(Banner):
    id = "stedwards"; name = "St. Edward's University"
    example = "MATH 1324"; host = "banner.stedwards.edu"; term = "202740"

class UPortland(Banner):
    id = "uportland"; name = "University of Portland"
    example = "MTH 161"; host = "registration.up.edu"; term = "202701"

class AuburnMontgomery(Banner):
    id = "aum"; name = "Auburn University at Montgomery"
    example = "CSCI 2000"; host = "ssb9.aum.edu"; term = "202701"

class SUNYOswego(Banner):
    id = "suny-oswego"; name = "SUNY Oswego"
    example = "CSC 212"; host = "banner-prod.oswego.edu"; term = "202609"

class SUNYBrockport(Banner):
    id = "suny-brockport"; name = "SUNY Brockport"
    example = "CSC 120"; host = "bannerprod.brockport.edu"; term = "202609"

class SUNYCobleskill(Banner):
    id = "suny-cobleskill"; name = "SUNY Cobleskill"
    example = "MATH 111"; host = "bannerprod.cobleskill.edu"; term = "202609"

class SUNYCortland(Banner):
    id = "suny-cortland"; name = "SUNY Cortland"
    example = "CAP 100"; host = "banner.cortland.edu"; term = "202690"

class SUNYNewPaltz(Banner):
    id = "suny-newpaltz"; name = "SUNY New Paltz"
    example = "CPS 210"; host = "banner.newpaltz.edu"; term = "202609"

class MissouriWestern(Banner):
    id = "missouriwestern"; name = "Missouri Western State University"
    example = "CSC 450"; host = "reg-prod.ec.missouriwestern.edu"; term = "202710"

class WestfieldState(Banner):
    id = "westfield"; name = "Westfield State University"
    example = "MATH 0108"; host = "myssb.westfield.ma.edu"; term = "202690"

class EasternIllinois(Banner):
    id = "eiu"; name = "Eastern Illinois University"
    example = "CSM 1000"; host = "banner.eiu.edu"; term = "202690"

class SUNYBroome(Banner):
    id = "suny-broome"; name = "SUNY Broome Community College"
    example = "CST 117"; host = "banner.sunybroome.edu"; term = "202630"

class DutchessCC(Banner):
    id = "suny-dutchess"; name = "SUNY Dutchess Community College"
    example = "CIS 111"; host = "banner.sunydutchess.edu"; term = "202609"

class JeffersonCC(Banner):
    id = "suny-jefferson"; name = "SUNY Jefferson Community College"
    example = "CIS 110"; host = "banner.sunyjefferson.edu"; term = "202608"

class AdirondackCC(Banner):
    id = "suny-adirondack"; name = "SUNY Adirondack"
    example = "CIS 125"; host = "banner.sunyacc.edu"; term = "202610"

class GeneseeCC(Banner):
    id = "genesee-cc"; name = "Genesee Community College"
    example = "CIS 117"; host = "bannerprod.genesee.edu"; term = "202609"

class UlsterCC(Banner):
    id = "suny-ulster"; name = "SUNY Ulster County Community College"
    example = "CSC 131"; host = "banner.sunyulster.edu"; term = "202608"

class CorningCC(Banner):
    id = "corning-cc"; name = "Corning Community College"
    example = "MATH 1310"; host = "banner.corning-cc.edu"; term = "202710"

class Concord(Banner):
    id = "concord"; name = "Concord University"
    example = "CS 272"; host = "ssb.concord.edu"; term = "202701"

class RaritanValley(Banner):
    id = "raritan"; name = "Raritan Valley Community College"
    example = "COMP 102"; host = "reg-prod.ec.raritanval.edu"; term = "202710"

class NassauCC(Banner):
    id = "nassau"; name = "Nassau Community College"
    example = "CSC 104"; host = "banner.ncc.edu"; term = "202710"

class MichiganFlint(Banner):
    id = "umflint"; name = "University of Michigan–Flint"
    example = "CSC 137"; host = "ssb.umflint.edu"; term = "202710"

class Wentworth(Banner):
    id = "wit"; name = "Wentworth Institute of Technology"
    example = "COMP 1000"; host = "selfservice.wit.edu"; term = "202710"

class Pellissippi(Banner):
    id = "pstcc"; name = "Pellissippi State Community College"
    example = "MATH 0030"; host = "ssbprod.pstcc.edu"; term = "202680"

class VolunteerState(Banner):
    id = "volstate"; name = "Volunteer State Community College"
    example = "MATH 1010"; host = "ssb.volstate.edu"; term = "202680"

class JacksonStateTN(Banner):
    id = "jscctn"; name = "Jackson State Community College (TN)"
    example = "MATH 0530"; host = "ssbprod.jscc.edu"; term = "202680"

class ColumbiaState(Banner):
    id = "columbiastate"; name = "Columbia State Community College"
    example = "COP 201"; host = "ssb.columbiastate.edu"; term = "202680"

class NortheastState(Banner):
    id = "northeaststate"; name = "Northeast State Community College"
    example = "MATH 1530"; host = "ssb.northeaststate.edu"; term = "202680"

class PiedmontTech(Banner):
    id = "piedmonttech"; name = "Piedmont Technical College"
    example = "MAT 120"; host = "banner.ptc.edu"; term = "202610"

class NortheastMississippi(Banner):
    id = "nemcc"; name = "Northeast Mississippi Community College"
    example = "CSC 1123"; host = "reg-prod.ec.nemcc.edu"; term = "202720"

class Itawamba(Banner):
    id = "iccms"; name = "Itawamba Community College"
    example = "CSC 1113"; host = "ssb9.iccms.edu"; term = "202710"

class MississippiDelta(Banner):
    id = "msdelta"; name = "Mississippi Delta Community College"
    example = "CSC 1123"; host = "selfservice.msdelta.edu"; term = "202710"

class LindseyWilson(Banner):
    id = "lindsey"; name = "Lindsey Wilson College"
    example = "MATH 1003"; host = "banner.lindsey.edu"; term = "202701"

class BartonCC(Banner):
    id = "bartoncc"; name = "Barton Community College"
    example = "MATH 1824"; host = "reg-prod.ec.bartonccc.edu"; term = "202701"

class Centenary(Banner):
    id = "centenary"; name = "Centenary College of Louisiana"
    example = "CSC 207"; host = "bannerweb.centenary.edu"; term = "202710"

class Catawba(Banner):
    id = "catawba"; name = "Catawba College"
    example = "CIS 2501"; host = "reg-prod.ec.catawba.edu"; term = "202710"

class EasternFlorida(Banner):
    id = "efsc"; name = "Eastern Florida State College"
    example = "CIS 2381"; host = "bannerweb.easternflorida.edu"; term = "202640"

class Oakton(Banner):
    id = "oakton"; name = "Oakton College"
    example = "CSC 157"; host = "banner.oakton.edu"; term = "202630"

class Washtenaw(Banner):
    id = "washtenaw"; name = "Washtenaw Community College"
    example = "CIS 110"; host = "banner.wccnet.edu"; term = "202609"

class ConcordiaTX(Banner):
    id = "concordia-tx"; name = "Concordia University Texas"
    example = "CSC 1401"; host = "banssb.concordia.edu"; term = "202710"

class TAMUSanAntonio(Banner):
    id = "tamusa"; name = "Texas A&M University–San Antonio"
    example = "CSCI 1436"; host = "banner.tamusa.edu"; term = "202710"

class TAMUCentralTexas(Banner):
    id = "tamuct"; name = "Texas A&M University–Central Texas"
    example = "COSC 4301"; host = "reg-prod.ec.tamuct.edu"; term = "202608"

class UDallas(Banner):
    id = "udallas"; name = "University of Dallas"
    example = "MAT 2305"; host = "reg-prod.ec.udallas.edu"; term = "202670"

class Immaculata(Banner):
    id = "immaculata"; name = "Immaculata University"
    example = "CIS 218"; host = "reg-prod.ec.immaculata.edu"; term = "202690"

class RoseHulman(Banner):
    id = "rosehulman"; name = "Rose-Hulman Institute of Technology"
    example = "CSSE 494"; host = "bannerweb.rose-hulman.edu"; term = "202710"

class Earlham(Banner):
    id = "earlham"; name = "Earlham College"
    example = "CS 266"; host = "ssb.earlham.edu"; term = "202710"

class EmporiaState(Banner):
    id = "emporia"; name = "Emporia State University"
    example = "CS 360"; host = "bannerssb.emporia.edu"; term = "202650"

class Harding(Banner):
    id = "harding"; name = "Harding University"
    example = "COSC 2010"; host = "ssb.harding.edu"; term = "202690"

class Spelman(Banner):
    id = "spelman"; name = "Spelman College"
    example = "HCSC 435"; host = "reg-prod.ec.spelman.edu"; term = "202609"

class Ramapo(Banner):
    id = "ramapo"; name = "Ramapo College of New Jersey"
    example = "CMPS 147"; host = "myssb.ramapo.edu"; term = "202640"

class Walsh(Banner):
    id = "walsh"; name = "Walsh University"
    example = "CS 108"; host = "ssb9.walsh.edu"; term = "202701"

class ConcordiaWI(Banner):
    id = "concordia-wi"; name = "Concordia University Wisconsin"
    example = "CSC 1010"; host = "ssb.cuw.edu"; term = "202710"

class Curry(Banner):
    id = "curry"; name = "Curry College"
    example = "CS 3500"; host = "ssb.curry.edu"; term = "202609"

class IllinoisWesleyan(Banner):
    id = "iwu"; name = "Illinois Wesleyan University"
    example = "CS 170"; host = "reg-prod.ec.iwu.edu"; term = "202610"

class Canisius(Banner):
    id = "canisius"; name = "Canisius University"
    example = "CSC 511"; host = "banner.canisius.edu"; term = "202630"

class IncarnateWord(Banner):
    id = "uiw"; name = "University of the Incarnate Word"
    example = "CIS 1100"; host = "reg-prod.ec.uiw.edu"; term = "202740"

class Citrus(Banner):
    id = "citrus"; name = "Citrus College"
    example = "CS 111"; host = "ssb.citruscollege.edu"; term = "202720"

class Cochise(Banner):
    id = "cochise"; name = "Cochise College"
    example = "CIS 116"; host = "ssb.cochise.edu"; term = "202640"

class AllanHancock(Banner):
    id = "hancock"; name = "Allan Hancock College"
    example = "CS 102"; host = "ssb.hancockcollege.edu"; term = "202720"

class LakeSumter(Banner):
    id = "lssc"; name = "Lake-Sumter State College"
    example = "CIS 2252"; host = "banner.lssc.edu"; term = "202710"

class NorthwestFlorida(Banner):
    id = "nwfsc"; name = "Northwest Florida State College"
    example = "CIS 1000"; host = "selfservice.nwfsc.edu"; term = "202710"

class AntelopeValley(Banner):
    id = "avc"; name = "Antelope Valley College"
    example = "CS 110"; host = "ssb.avc.edu"; term = "202670"

class Harford(Banner):
    id = "harford"; name = "Harford Community College"
    example = "CIS 102"; host = "banner.harford.edu"; term = "202640"

class Gavilan(Banner):
    id = "gavilan"; name = "Gavilan College"
    example = "CSIS 571A"; host = "reg-prod.ec.gavilan.edu"; term = "202670"

class JeffersonCollegeMO(Banner):
    id = "jeffco"; name = "Jefferson College (MO)"
    example = "CIS 125"; host = "ssb.jeffco.edu"; term = "202702"

class MeridianCC(Banner):
    id = "meridian"; name = "Meridian Community College"
    example = "CSC 1123"; host = "ssb.meridiancc.edu"; term = "202610"


# --- July 8 2026 IPEDS batch (each verified through the production fetcher: live
# term auto-resolved, example discovered from the school's own search API, raw
# section-collapse screen clean, latency < 3s). Drake re-tested and re-CUT at 136.8s
# (identical to its original cut — host still cold-starts per session).
class SCAD(Banner):
    id = "scad"; name = "Savannah College of Art and Design"
    example = "ENGL 142"; host = "ssb.scad.edu"; term = "202710"

class NWMissouri(Banner):
    id = "nwmissouri"; name = "Northwest Missouri State University"
    example = "ENGL 10111"; host = "banprod.nwmissouri.edu"; term = "202710"

class NortheastNE(Banner):
    id = "northeastne"; name = "Northeast Community College (NE)"
    example = "ENGL 0955"; host = "reg-prod.ec.northeast.edu"; term = "202710"

class AlfredU(Banner):
    id = "alfred"; name = "Alfred University"
    example = "ENGL 101"; host = "banweb.alfred.edu"; term = "202690"

class FITNYC(Banner):
    id = "fit"; name = "Fashion Institute of Technology"
    example = "CS 211"; host = "banner.fitnyc.edu"; term = "202701"

class Hofstra(Banner):
    id = "hofstra"; name = "Hofstra University"
    example = "ENGL 020"; host = "xe.hofstra.edu"; term = "202609"

class JamestownCC(Banner):
    id = "sunyjcc"; name = "Jamestown Community College"
    example = "ENG 1540"; host = "banprod.sunyjcc.edu"; term = "202612"

class SUNYCanton(Banner):
    id = "sunycanton"; name = "SUNY Canton"
    example = "ENGL 101"; host = "banweb.canton.edu"; term = "202609"

class SUNYSchenectady(Banner):
    id = "sunysccc"; name = "SUNY Schenectady"
    example = "ENG 123"; host = "banprod.sunysccc.edu"; term = "202609"

class UpstateMedical(Banner):
    id = "upstate"; name = "SUNY Upstate Medical University"
    example = "ENGL 325"; host = "bannerweb.upstate.edu"; term = "202680"

class Presbyterian(Banner):
    id = "presby"; name = "Presbyterian College"
    example = "ENGL 1001"; host = "banprod.presby.edu"; term = "202601"

# Prairie View A&M (myssb.pvamu.edu) tested and CUT — passed one gate fetch then went
# consistently empty (0 sections, fast responses): host serves inconsistent data.

class Gonzaga(Banner):
    id = "gonzaga"; name = "Gonzaga University"
    example = "ENGL 101"; host = "xe.gonzaga.edu"; term = "202710"

class PacificLutheran(Banner):
    id = "plu"; name = "Pacific Lutheran University"
    example = "ENGL 214"; host = "banweb.plu.edu"; term = "202674"

class CollegeOfTheSequoias(Banner):
    id = "cos"; name = "College of the Sequoias"
    example = "ACCT 210"; host = "banweb.cos.edu"; term = "202710"

class UCMerced(Banner):
    id = "ucmerced"; name = "UC Merced"
    example = "BIOE 021"; host = "reg-prod.ec.ucmerced.edu"; term = "202630"

class UOPacific(Banner):
    id = "pacific"; name = "University of the Pacific"
    example = "NURS 200"; host = "reg-prod.ec.pacific.edu"; term = "202684"

class UDC(Banner):
    id = "udc"; name = "University of the District of Columbia"
    example = "ACCT 201"; host = "reg-prod.ec.udc.edu"; term = "202710"

class MorehouseSOM(Banner):
    id = "msm"; name = "Morehouse School of Medicine"
    example = "NURS 602"; host = "reg-prod.ec.msm.edu"; term = "202701"

class BethelMN(Banner):
    id = "bethelmn"; name = "Bethel University (MN)"
    example = "BT 510"; host = "banner.bethel.edu"; term = "202713"

class MohawkValley(Banner):
    id = "mvcc"; name = "Mohawk Valley Community College"
    example = "AC 115"; host = "banprod.mvcc.edu"; term = "202608"

class RocklandCC(Banner):
    id = "sunyrockland"; name = "Rockland Community College"
    example = "BLR 30000"; host = "banner.sunyrockland.edu"; term = "202685"

class NewSchool(Banner):
    id = "newschool"; name = "The New School"
    example = "NURP 6900"; host = "selfservice.newschool.edu"; term = "202610"

# USG Georgia state colleges on the shared gabest.usg.edu Banner infra (same
# pattern as GeorgiaSouthern/WestGeorgia/etc; term 202608 = Fall 2026 systemwide).
class ABAC(Banner):
    id = "abac"; name = "Abraham Baldwin Agricultural College"
    example = "ENGL 1101"; host = "abac.gabest.usg.edu"; term = "202608"

class AtlantaMetro(Banner):
    id = "atlm"; name = "Atlanta Metropolitan State College"
    example = "ENGL 1101"; host = "atlm.gabest.usg.edu"; term = "202608"

class CoastalGeorgia(Banner):
    id = "ccga"; name = "College of Coastal Georgia"
    example = "ENGL 0999"; host = "ccga.gabest.usg.edu"; term = "202608"

class GordonState(Banner):
    id = "gordonstate"; name = "Gordon State College"
    example = "ENGL 1101"; host = "gordon.gabest.usg.edu"; term = "202608"

class SouthGeorgiaState(Banner):
    id = "sgsc"; name = "South Georgia State College"
    example = "ENGL 1101"; host = "sgsc.gabest.usg.edu"; term = "202608"

class DaltonState(Banner):
    id = "daltonstate"; name = "Dalton State College"
    example = "ACCT 2101"; host = "daltonstate.gabest.usg.edu"; term = "202608"

class EastGeorgiaState(Banner):
    id = "ega"; name = "East Georgia State College"
    example = "ACCT 2101"; host = "ega.gabest.usg.edu"; term = "202605"


class CACCD(Banner):
    """California multi-college district on ONE Ellucian Cloud Banner host, isolated by
    the campus filter (SD-regental pattern: first token of campusDescription — verified
    live: Coast CCD tokens Orange/Golden/Coastline, Kern CCD tokens BC/CC/Porterville,
    full ENGL pagination shows no other token on either host). CA course numbers carry
    a campus letter PREFIX ("ENGL A101", "ENGL B1A"), which the base Banner._code can't
    split, so _code is overridden HERE ONLY — a required space keeps it unambiguous and
    the base class (200+ live schools) is untouched. fetch() then exact-matches the full
    lettered number against the API's own courseNumber, so a bad parse returns nothing
    rather than the wrong course."""
    _CODE_RE = re.compile(r"^([A-Za-z]{2,6})\s+([A-Za-z]?\d{1,4}[A-Za-z]{0,2})$")

    @classmethod
    def _code(cls, course):
        m = cls._CODE_RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

class OrangeCoast(CACCD):
    id = "orangecoast"; name = "Orange Coast College"
    example = "ENGL A101"; host = "reg-prod.ec.cccd.edu"; term = "202670"; campus = "Orange"

class GoldenWest(CACCD):
    id = "goldenwest"; name = "Golden West College"
    example = "ENGL G100S"; host = "reg-prod.ec.cccd.edu"; term = "202670"; campus = "Golden"

class Coastline(CACCD):
    id = "coastline"; name = "Coastline College"
    example = "ENGL C102"; host = "reg-prod.ec.cccd.edu"; term = "202670"; campus = "Coastline"

class Bakersfield(CACCD):
    id = "bakersfield"; name = "Bakersfield College"
    example = "ENGL B1A"; host = "reg-prod.ec.kccd.edu"; term = "202670"; campus = "BC"

class CerroCoso(CACCD):
    id = "cerrocoso"; name = "Cerro Coso Community College"
    example = "ENGL C101"; host = "reg-prod.ec.kccd.edu"; term = "202670"; campus = "CC"

class Porterville(CACCD):
    id = "porterville"; name = "Porterville College"
    example = "ENGL P101A"; host = "reg-prod.ec.kccd.edu"; term = "202670"; campus = "Porterville"


class CrnKeyedBanner(Banner):
    """Banner hosts that return sequenceNumber='0' on EVERY section (verified live at
    all three schools below) — the default sequence key would collapse the whole course
    into one row. Key by CRN instead: unique per term (verified), and the number these
    schools' students actually register with."""
    def _seckey(self, r):
        return r.get("courseReferenceNumber")

class SNHU(CrnKeyedBanner):
    id = "snhu"; name = "Southern New Hampshire University"
    example = "ACC 550"; host = "reg-prod.ec.snhu.edu"; term = "202687"

class DeVry(CrnKeyedBanner):
    id = "devry"; name = "DeVry University"
    example = "ACCT 207"; host = "reg-prod.ec.devry.edu"; term = "202720"

class ConcordiaMoorhead(CrnKeyedBanner):
    id = "concordiamn"; name = "Concordia College (Moorhead)"
    example = "ANUR 425"; host = "banner.cord.edu"; term = "202609"


# July 8 handoff batch 2 (gated: accuracy AND latency, both hard):
# Lafayette College CUT — every guest-visible term incl. the newest is '(View Only)'
# archive data; passing a fetch on stale data is exactly the false-freshness trap.
class Touro(CrnKeyedBanner):
    # zero-seq confirmed on multi-section courses (single-section example masked it)
    id = "touro"; name = "Touro University (NY)"
    example = "MATH 104"; host = "reg-prod.ec.touro.edu"; term = "202630"

class SouthernOregon(CrnKeyedBanner):
    # zero-seq confirmed on multi-section courses (single-section example masked it)
    id = "sou"; name = "Southern Oregon University"
    example = "ARTH 205"; host = "reg-prod.ec.sou.edu"; term = "202504"  # Summer 2026 —
    # newest non-View-Only guest term; auto-rolls to Fall 2026 when SOU publishes it

class Hartford(CrnKeyedBanner):
    # University of Hartford. Guest Banner9, but EVERY section returns sequenceNumber='0'
    # (BIO 122 = 23 sections all seq '0' — plain-Banner would collapse them into 1 and
    # miss opens). CRN-keyed (23 unique CRNs). BIO 122 = 23 sec 16 full live disproof;
    # completed Fall 2025 (202540) mixed.
    id = "hartford"; name = "University of Hartford"
    example = "BIO 122"; host = "uhart-pxesa-003.hartford.edu:8103"; term = "202640"  # Fall 2026

class Massasoit(Banner):
    id = "massasoit"; name = "Massasoit Community College"
    example = "ACCT 104"; host = "banner.massasoit.mass.edu"; term = "202710"


class NumericSubjectBanner(Banner):
    """WI technical colleges use PURELY NUMERIC subject codes (subject '101' =
    Accounting at WCTC/Blackhawk) — the base _code requires a letter-first subject and
    would silently parse nothing. Digit subjects need the explicit space separator to
    stay unambiguous; fetch() still exact-matches subject AND courseNumber against the
    API's own fields, so a bad parse returns nothing rather than the wrong course."""
    _CODE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9 ]*?)\s+(\d{1,5}[A-Za-z]?)$")
    @classmethod
    def _code(cls, course):
        m = cls._CODE_RE.match(course.strip())
        return (re.sub(r"\s+", " ", m.group(1)).upper(), m.group(2).upper()) if m else (None, None)

class WCTC(NumericSubjectBanner):
    id = "wctc"; name = "Waukesha County Technical College"
    example = "101 105"; host = "reg-prod.ec.wctc.edu"; term = "202710"

class Blackhawk(NumericSubjectBanner):
    id = "blackhawk"; name = "Blackhawk Technical College"
    example = "101 111"; host = "reg-prod.ec.blackhawk.edu"; term = "202701"


# ===========================================================================
class PeopleSoft:
    """Oracle PeopleSoft Campus Solutions 'Class Search and Enroll' fetcher.

    Many schools (incl. big publics) run PeopleSoft, NOT Banner. PeopleSoft exposes a
    PUBLIC guest class-search JSON API (no login) at an identical set of IScript endpoints
    — only host + site + institution + term change, so each school is a ~4-line subclass.
    We read the authoritative `enrl_stat` ('O'=Open ONLY) and the true
    `enrollment_available` count. Wait List ('W') and Closed ('C') are NOT open, so we
    NEVER fabricate an opening. On ANY failure returns {} (the engine treats {} as skip).

    Subclass sets: id, name, example, host, site, inst, term (PeopleSoft 'strm' code).
    """
    _active_term = None
    node = "EMPLOYEE"          # PeopleSoft portal node; most use EMPLOYEE, some differ (UVA=UVSS)
    seg = "SA"                 # portal segment; nearly always SA, some differ (Illinois Central=CAMP)
    _SUBJ_RE = re.compile(r"^([A-Za-z]{1,6}&?)\s*(\d{2,4}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._SUBJ_RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return (f"https://{self.host}/psp/{self.site}/{self.node}/{self.seg}/s/"
                "WEBLIB_HCX_CM.H_BROWSE_CLASSES.FieldFormula.IScript_Main")

    def cur_term(self):
        return self._active_term or self.term

    def _cs(self):
        return (f"https://{self.host}/psc/{self.site}/{self.node}/{self.seg}/s/"
                "WEBLIB_HCX_CM.H_CLASS_SEARCH.FieldFormula")

    def _session(self):
        """Establish a guest session (no login) — the browse-classes page hands out the
        cookies the class-search IScript needs."""
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA), ("Accept", "application/json")]
        op.open(f"https://{self.host}/psp/{self.site}/{self.node}/{self.seg}/s/"
                "WEBLIB_HCX_CM.H_BROWSE_CLASSES.FieldFormula.IScript_Main", timeout=20).read()
        return op

    def resolve_term(self):
        """Auto-detect the nearest UPCOMING main term's strm from the options endpoint;
        None on failure. Anchored on the human 'Fall 2026'-style descr (strm codes aren't
        portable across schools), so it self-maintains across semesters."""
        try:
            op = self._session()
            d = json.loads(op.open(self._cs() + ".IScript_ClassSearchOptions?institution="
                                   + self.inst, timeout=20).read().decode("utf-8", "replace"))
            today = datetime.date.today()
            best, best_delta = None, None
            for t in d.get("terms", []):
                desc = (t.get("descr") or "")
                # handle BOTH 'Fall 2026' and '2026 Fall' orderings
                m = (re.search(r"(spring|summer|fall|autumn|winter)\D{0,6}(20\d\d)", desc, re.I) or
                     re.search(r"(20\d\d)\D{0,6}(spring|summer|fall|autumn|winter)", desc, re.I))
                if not m:
                    continue
                g = m.groups()
                if g[0].lower() in ("spring", "summer", "fall", "autumn", "winter"):
                    season, year = g[0].lower(), int(g[1])
                else:
                    season, year = g[1].lower(), int(g[0])
                mon = _SEASON.get(season if season != "autumn" else "fall", 8)
                delta = (year - today.year) * 12 + (mon - today.month)
                if not _auto_season(season) or delta < -1:                          # skip clearly-past terms
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, t.get("strm")
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        """Adopt a newly-detected term ONLY after verifying it returns live data; else keep
        last-known-good. Self-maintaining across semesters WITHOUT risking accuracy."""
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = self._active_term
        self._active_term = new
        ok = bool(self.fetch({self.example}).get(self.example)) if getattr(self, "example", "") else False
        if not ok:
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        """One structured search per course (exact subject+catalog). Keyed by input string.
        Sections keyed by class_section; if a course has duplicate section ids (collapse
        risk) we skip it rather than merge — accuracy over coverage."""
        try:
            op = self._session()
        except Exception:
            return {}
        out = {}
        for course in courses:
            subj, cat = self._norm(course)
            if not subj:
                continue
            try:
                rows, page = [], 1
                while page <= 6:
                    u = self._cs() + ".IScript_ClassSearch?" + urllib.parse.urlencode(
                        {"institution": self.inst, "term": self.cur_term(),
                         "subject": subj, "catalog_nbr": cat, "page": str(page)})
                    d = json.loads(op.open(u, timeout=30).read().decode("utf-8", "replace"))
                    rows += d.get("classes") or []
                    if page >= int(d.get("pageCount") or 1):
                        break
                    page += 1
            except Exception:
                continue
            secs, dup = {}, False
            for r in rows:
                if (r.get("subject") or "").upper() != subj:            # exact course only
                    continue
                if str(r.get("catalog_nbr") or "").upper() != cat:
                    continue
                try:
                    av = int(r.get("enrollment_available"))             # true count; no count -> skip
                except (TypeError, ValueError):
                    continue
                sec = str(r.get("class_section"))
                if sec in secs:                                         # duplicate id -> collapse
                    dup = True
                    break
                # open ONLY when PeopleSoft says 'O' (Open). 'W'/'C' => not open, never false-alert.
                secs[sec] = {"open": r.get("enrl_stat") == "O", "seats": max(av, 0)}
            if dup or not secs:
                continue
            out[course] = secs
        return out


class Towson(PeopleSoft):
    id = "towson"; name = "Towson University"
    example = "COSC 236"; host = "tuclasssearch.towson.edu"; site = "CS9PRD"
    inst = "TOWSN"; term = "1264"      # Fall 2026 (auto-refreshes via ClassSearchOptions)

class CSUChico(PeopleSoft):
    id = "csuchico"; name = "California State University, Chico"
    example = "MATH 105"; host = "cmsweb.csuchico.edu"; site = "CCHIPRD"
    inst = "CHICO"; term = "2268"      # Fall 2026

class CSUChannelIslands(PeopleSoft):
    # Host also answers on seg HRMS; SA is used for consistency with the rest of the fleet.
    id = "csuci"; name = "California State University Channel Islands"
    example = "BIOL 200"; host = "cmsweb.csuci.edu"; site = "CCIPRD"
    inst = "CI"; term = "2268"         # Fall 2026

class IllinoisCentral(PeopleSoft):
    # Portal segment is /CAMP/, not the usual /SA/ — see PeopleSoft.seg.
    id = "illinoiscentral"; name = "Illinois Central College"
    example = "ENGL 110"; host = "eservices.icc.edu"; site = "eservices"
    inst = "ICC"; term = "2273"; seg = "CAMP"      # Fall 2026

class UVA(PeopleSoft):
    id = "uva"; name = "University of Virginia"
    example = "CS 1110"; host = "sisuva.admin.virginia.edu"; site = "ihprd"
    node = "UVSS"; inst = "UVA01"; term = "1268"       # Fall 2026

class USM(PeopleSoft):
    id = "usm"; name = "University of Southern Mississippi"
    example = "CSC 101"; host = "soar.usm.edu"; site = "guest_1"
    inst = "USM01"; term = "4271"                       # Fall 2026

class Palomar(PeopleSoft):
    id = "palomar"; name = "Palomar College"
    example = "CS 101"; host = "my.palomar.edu"; site = "palc9prd"
    inst = "PALCC"; term = "2267"                       # Fall 2026

class Coppin(PeopleSoft):
    id = "coppin"; name = "Coppin State University"
    example = "ENGL 102"; host = "eaglecs.psoft.coppin.edu"; site = "csucsprd"
    inst = "COPPN"; term = "2268"                       # Fall 2026

class BostonUniversity(PeopleSoft):
    # BU uses college-prefixed subjects (CAS = College of Arts & Sciences, so
    # "CASMA 123" = CAS Math 123). Gate found REAL mixed status on the example
    # (16 sections, Open/Waitlisted mix, integer seat counts) — proof this guest
    # view is live data, not the NAU-style always-Open trap.
    id = "bu"; name = "Boston University"
    example = "CASMA 123"; host = "public.mybustudent.bu.edu"; site = "BUPRD"
    inst = "BU001"; term = "2268"                       # Fall 2026


class CtcLink(PeopleSoft):
    """Washington State ctcLink: ONE PeopleSoft host (csprd.ctclink.us) serves 30+
    community/technical colleges, isolated by institution code. Isolation verified —
    institution=WAxxx returns ONLY that college's classes (acad_org prefix matches). An
    INVALID code silently returns ANOTHER college's data, so we hardcode ONLY the
    authoritative institution codes (from the system's own institutions list) — never a
    guessed one. Each college is one row: (id, name, inst, example)."""
    host = "csprd.ctclink.us"; site = "csprd"; node = "EMPLOYEE"; term = "2267"  # Fall 2026

    def __init__(self, id, name, inst, example):
        self.id = id; self.name = name; self.inst = inst; self.example = example

_CTCLINK = [
    ("wa-peninsula", "Peninsula College", "WA010", "CS 100"),
    ("wa-grays-harbor", "Grays Harbor College", "WA020", "CS 141"),
    ("wa-olympic", "Olympic College", "WA030", "CS 110"),
    ("wa-skagit-valley", "Skagit Valley College", "WA040", "CS 101"),
    ("wa-everett-cc", "Everett Community College", "WA050", "CS 110"),
    ("wa-seattle-central", "Seattle Central College", "WA062", "CSC 110"),
    ("wa-north-seattle", "North Seattle College", "WA063", "CSC 110"),
    ("wa-south-seattle", "South Seattle College", "WA064", "CSC 110"),
    ("wa-shoreline-cc", "Shoreline Community College", "WA070", "CS 110"),
    ("wa-bellevue", "Bellevue College", "WA080", "CS 210"),
    ("wa-highline", "Highline College", "WA090", "CIS 150"),
    ("wa-green-river", "Green River College", "WA100", "CS 121"),
    ("wa-pierce", "Pierce College (WA)", "WA110", "CS 202"),
    ("wa-centralia", "Centralia College", "WA120", "CS& 131"),
    ("wa-lower-columbia", "Lower Columbia College", "WA130", "CS 110"),
    ("wa-clark", "Clark College", "WA140", "MATH 111"),
    ("wa-wenatchee-valley", "Wenatchee Valley College", "WA150", "CSC 151"),
    ("wa-yakima-valley", "Yakima Valley College", "WA160", "CS& 141"),
    ("wa-spokane-falls-cc", "Spokane Falls Community College", "WA172", "CS 211"),
    ("wa-big-bend-cc", "Big Bend Community College", "WA180", "CS 103"),
    ("wa-columbia-basin", "Columbia Basin College", "WA190", "CS 101"),
    ("wa-walla-walla-cc", "Walla Walla Community College", "WA200", "CS 110"),
    ("wa-whatcom-cc", "Whatcom Community College", "WA210", "CS 101"),
    ("wa-tacoma-cc", "Tacoma Community College", "WA220", "CS 142"),
    ("wa-edmonds", "Edmonds College", "WA230", "CS 115"),
    ("wa-south-puget-sound-cc", "South Puget Sound Community College", "WA240", "CS 142"),
    ("wa-bellingham-tech", "Bellingham Technical College", "WA250", "IT 101"),
    ("wa-lake-washington-tech", "Lake Washington Institute of Technology", "WA260", "CS 143"),
    ("wa-renton-tech", "Renton Technical College", "WA270", "CS 142"),
    ("wa-bates-tech", "Bates Technical College", "WA280", "MATH 172"),
    ("wa-cascadia", "Cascadia College", "WA300", "MATH 95"),
    # Last 2 of 33 addressable ctcLink institutions (per SBCTC's own "College Codes
    # (Numeric Order)" doc, rev. 2023-07-31) — confirmed live in ctcLink's own
    # per-term institutions[] list alongside every school above (Fall 2026 = "2267").
    ("wa-spokane-cc", "Spokane Community College", "WA171", "ENGL& 101"),
    ("wa-clover-park-tech", "Clover Park Technical College", "WA290", "ENGL& 101"),
]


# ===========================================================================
class MinnState:
    """Minnesota State eServices (eservices.minnstate.edu) — ONE public course search
    serving all 33 Minnesota State colleges & universities (ISRS — not Banner/PeopleSoft).
    One GET per course; every section row carries an explicit status badge in the HTML
    (status-open / status-closed / status-cancelled). Open ONLY on status-open — 'Full'
    and 'Cancelled' NEVER alert. The list page shows status but not counts, so
    seats=None (same convention as CUNY). A bounced/validation-error response re-renders
    the search FORM (no searchResultsContainer marker) — treated as failure and never
    parsed, so a format change goes silent instead of false-alerting.

    yrtr term codes are SYSTEMWIDE (20273 = Fall 2026 = AY2027 term 3), so one
    class-level term serves every campus; it auto-rolls from the form's own yrtr
    <select> and is verified against live data before adoption.

    Each campus is one row: (id, name, campusid, rcid, example). campusid is the
    college's BRANDED page id and is NOT always the rcid tail — multi-campus colleges
    differ (Anoka-Ramsey rcid 0152 -> campusid 141, Southeast 0213 -> 260, South
    Central 0309 -> 270), and a WRONG campusid silently renders a generic no-subject
    page, so every row below was verified live (campus-branded page + exact-course
    search parsed) before shipping."""
    base = "https://eservices.minnstate.edu/registration/search/"
    term = "20273"                       # Fall 2026 (systemwide); auto-rolls via refresh_term
    _active_term = None                  # class-level — one term for the whole system
    # subjects are usually pure letters (ENG, ENGL) but a few campuses carry
    # digit-bearing codes (3DMA, D2LO) — those need a space before the course number
    _SUBJ_RE = re.compile(r"^([A-Za-z]{2,6})\s*(\d{2,4}[A-Za-z]?)$")
    _SUBJ_RE2 = re.compile(r"^([A-Za-z0-9]{2,6})\s+(\d{2,4}[A-Za-z]?)$")

    def __init__(self, id, name, campusid, rcid, example):
        self.id = id; self.name = name
        self.campusid = campusid; self.rcid = rcid; self.example = example

    def _norm(self, course):
        c = course.strip()
        m = self._SUBJ_RE.match(c) or self._SUBJ_RE2.match(c)
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def cur_term(self):
        return MinnState._active_term or self.term

    def reg_url(self, course):
        return self.base + "basic.html?campusid=" + self.campusid

    def _search_url(self, subj, num):
        return self.base + "advancedSubmit.html?" + urllib.parse.urlencode(
            {"campusid": self.campusid, "searchrcid": self.rcid,
             "searchcampusid": self.campusid, "yrtr": self.cur_term(),
             "subject": subj, "courseNumber": num, "openValue": "ALL",
             "delivery": "ALL", "resultNumber": "250", "showAdvanced": ""})

    def resolve_term(self):
        """Nearest upcoming main term's yrtr from the campus form's own <select>;
        None on failure. Anchored on the human 'Fall 2026 (Aug - Dec)' description —
        the code format is uniform systemwide but we never assume it."""
        try:
            page = _http(self.base + "basic.html?campusid=" + self.campusid)
            i = page.find('name="yrtr"')
            if i < 0:
                return None
            today = datetime.date.today()
            best, best_delta = None, None
            for m in re.finditer(r'<option value="(20\d{3})"(.*?)</option>', page[i:i + 8000], re.S):
                code, desc = m.group(1), re.sub(r"^[^>]*>", "", m.group(2), flags=re.S)
                sm = re.search(r"(spring|summer|fall|winter)\D{0,6}(20\d\d)", desc, re.I)
                if not sm:
                    continue
                season, year = sm.group(1).lower(), int(sm.group(2))
                delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
                if not _auto_season(season) or delta < -1:                       # skip clearly-past terms
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta, best = delta, code
            return best
        except Exception:
            return None

    def refresh_term(self, log=None):
        """Adopt a newly-detected term ONLY after the example course returns REAL
        sections under it (the 'none' sentinel is not proof); else keep last-known-good."""
        new = self.resolve_term()
        if not new or new == self.cur_term():
            return
        prev = MinnState._active_term
        MinnState._active_term = new
        secs = self.fetch({self.example}).get(self.example) or {}
        if not secs or "none" in secs:
            MinnState._active_term = prev
            if log:
                log(f"[term] {self.id}: detected {new} but no live data yet — keeping {self.cur_term()}")
            return
        if log:
            log(f"[term] {self.id}: term auto-updated {prev or self.term} -> {new}")

    def fetch(self, courses):
        """One search per course. Row layout: ... | ID#(6 digits) | Subj | # | Sec | ...
        with the status badge class in the same <tr>. Exact subject+number match only;
        duplicate section ids -> skip the course (accuracy over coverage)."""
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                page = _http(self._search_url(subj, num))
            except Exception:
                continue
            if "searchResultsContainer" not in page:     # bounced form / error — never parse
                continue
            secs, dup = {}, False
            for row in re.finditer(r"<tr[^>]*>(.*?)</tr>", page, re.S):
                r = row.group(1)
                st = re.search(r"status-(open|closed|cancelled)", r)
                if not st:
                    continue
                cells = [re.sub(r"(?:&nbsp;|\s)+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                         for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
                idx = next((i for i, c in enumerate(cells) if re.fullmatch(r"\d{6}", c)), None)
                if idx is None or len(cells) < idx + 4:
                    continue
                if cells[idx + 1].upper() != subj or cells[idx + 2].upper() != num:
                    continue
                sec = cells[idx + 3]
                if sec in secs:
                    dup = True
                    break
                secs[sec] = {"open": st.group(1) == "open", "seats": None}
            if dup:
                continue
            out[course] = secs if secs else {"none": {"open": False, "seats": None}}
        return out

_MINNSTATE = [
    # (id, name, campusid, rcid, example) — every row verified LIVE (branded page +
    # exact-course search parsed with unique sections) before shipping.
    ("mn-alexandria", "Alexandria Technical and Community College", "203", "0203", "ENGL 1410"),
    ("mn-anoka-tech", "Anoka Technical College", "202", "0202", "ENGL 1107"),
    ("mn-anoka-ramsey", "Anoka-Ramsey Community College", "141", "0152", "ENGL 1121"),
    ("mn-bemidji-state", "Bemidji State University", "070", "0070", "ENGL 1151"),
    ("mn-central-lakes", "Central Lakes College", "301", "0301", "ENGL 1410"),
    ("mn-century", "Century College", "304", "0304", "ENGL 1021"),
    ("mn-dakota-county-tech", "Dakota County Technical College", "211", "0211", "ENGL 1150"),
    ("mn-fond-du-lac", "Fond du Lac Tribal and Community College", "163", "0163", "ENGL 1101"),
    ("mn-hennepin-tech", "Hennepin Technical College", "204", "0204", "ENGL 1100"),
    ("mn-inver-hills", "Inver Hills Community College", "157", "0157", "ENG 1108"),
    ("mn-lake-superior", "Lake Superior College", "302", "0302", "ENGL 1106"),
    ("mn-metro-state", "Metro State University", "076", "0076", "MATH 115"),
    ("mn-minneapolis", "Minneapolis Community and Technical College", "305", "0305", "ENGL 1110"),
    ("mn-north", "Minnesota North College", "320", "0320", "ENGL 1231"),
    ("mn-southeast", "Minnesota State College Southeast", "260", "0213", "ENGL 1215"),
    ("mn-mstate", "Minnesota State Community and Technical College", "142", "0142", "ENGL 1101"),
    ("mn-moorhead", "Minnesota State University Moorhead", "072", "0072", "ENGL 101"),
    ("mn-mankato", "Minnesota State University, Mankato", "071", "0071", "ENG 101"),
    ("mn-west", "Minnesota West Community and Technical College", "209", "0209", "ENGL 1101"),
    ("mn-normandale", "Normandale Community College", "156", "0156", "ENGL 2150"),
    ("mn-north-hennepin", "North Hennepin Community College", "153", "0153", "ENGL 1201"),
    ("mn-northland", "Northland Community and Technical College", "303", "0303", "ENGL 1111"),
    ("mn-northwest-tech", "Northwest Technical College", "263", "0263", "ENGL 1111"),
    ("mn-pine-tech", "Pine Technical and Community College", "205", "0205", "ENGL 1276"),
    ("mn-ridgewater", "Ridgewater College", "308", "0308", "ENGL 1210"),
    ("mn-riverland", "Riverland Community College", "307", "0307", "ENGL 1101"),
    ("mn-rochester", "Rochester Community and Technical College", "306", "0306", "ENGL 1117"),
    ("mn-saint-paul", "Saint Paul College", "206", "0206", "ENGL 1711"),
    ("mn-south-central", "South Central College", "270", "0309", "ENGL 100"),
    ("mn-southwest-state", "Southwest Minnesota State University", "075", "0075", "ENG 151"),
    ("mn-st-cloud-state", "St. Cloud State University", "073", "0073", "ENGL 191"),
    ("mn-st-cloud-tech", "St. Cloud Technical & Community College", "208", "0208", "ENGL 1312"),
    ("mn-winona-state", "Winona State University", "074", "0074", "ENG 111"),
]


# ===========================================================================
class Colleague:
    """Ellucian Colleague Self-Service — Ellucian's OTHER SIS (many schools run it
    instead of Banner). PUBLIC course-catalog JSON API (no login): GET /Student/Courses
    for an antiforgery token, POST /PostSearchCriteria (keyword) for the course + its
    MatchingSectionIds, POST /Sections for section availability. We read the authoritative
    `AvailabilityStatus` ('Open' ONLY) + true `Available` count, and ONLY when
    `AreSeatCountsAvailable` is set — Waitlisted/Closed/unknown are never 'open', so we
    never false-alert. {} on any failure. Self-maintaining term (nearest upcoming Fall/
    Spring from ActivePlanTerms). Subclass sets: id, name, example, host.

    SHARED MULTI-COLLEGE HOSTS (Rancho Santiago: Santa Ana + Santiago Canyon on one
    host) return ONE CourseFullModel PER COLLEGE for the same course, each tagged with
    LocationCodes (['SAC'] / ['SCC']). Taking the first match would silently serve one
    college's sections and make the other INVISIBLE. Such schools set `campus` to their
    LocationCode: we then pick the model tagged for THAT college and also keep only its
    section rows (LocationCode). campus = "" (the default) = single-college host, first
    match, behaviour unchanged for every other Colleague school."""
    campus = ""          # LocationCode on a shared district host; "" = single-college
    _SUBJ_RE = re.compile(r"^([A-Za-z]{2,5})[ \-]?([A-Za-z]?\d{2,4}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._SUBJ_RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return f"https://{self.host}/Student/Courses"

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        body = op.open(f"https://{self.host}/Student/Courses", timeout=20).read().decode("utf-8", "replace")
        m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', body)
        return op, (m.group(1) if m else None)

    def _post(self, op, tok, path, payload):
        req = urllib.request.Request(f"https://{self.host}{path}", data=json.dumps(payload).encode())
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        if tok:
            req.add_header("__RequestVerificationToken", tok)
        return json.loads(op.open(req, timeout=25).read().decode("utf-8", "replace"))

    # secondary/sub-population term qualifiers — a term carrying one of these is NOT the
    # primary full-semester UNDERGRADUATE term most seat-watchers want. \bgraduate\b does
    # NOT match inside 'undergraduate' (no word boundary), so undergrad stays un-penalized.
    _SUBTERM_RE = re.compile(
        r"\bgraduate\b|\bgrad\b|continuing|cont\.? ?ed|weekend|evening|\bonline\b|"
        r"\d+\s*week|8wk|session|part of term|part-of-term|esperanza|express|dynamic|"
        r"late start|accelerated|\bii+\b|module|flex|doctoral|law\b|\bce\b|noncredit|non-credit|"
        r"\bmini\b|clinical",
        re.I)

    def _pick_term(self, terms):
        """Nearest upcoming PRIMARY term (e.g. 'Fall 2026', 'Fall 2026 Undergraduate') from
        ActivePlanTerms. Ranking: (1) nearest upcoming date, then (2) FEWEST secondary
        qualifiers — a plain full-semester undergraduate term beats 'Graduate', '8 Week',
        'Continuing Ed', a branch campus, etc. (matters: 'Fall 2026 Graduate' is SHORTER than
        'Fall 2026 Undergraduate', so length alone would wrongly pick Graduate), then
        (3) shortest description as a final tiebreak. Prevents covering only a sub-population."""
        today = datetime.date.today()
        seasons = ("spring", "summer", "fall", "autumn", "winter")
        best, best_key = None, None
        for t in terms:
            desc = (t.get("Description") or "")
            # handle BOTH 'Fall 2026' and '2026 Fall', and longer gaps ('Fall Semester 2026')
            m = (re.search(r"(spring|summer|fall|autumn|winter)\D{0,12}(20\d\d)", desc, re.I) or
                 re.search(r"(20\d\d)\D{0,12}(spring|summer|fall|autumn|winter)", desc, re.I))
            if not m:
                continue
            g = m.groups()
            if g[0].lower() in seasons:
                season, year = g[0].lower(), int(g[1])
            else:
                season, year = g[1].lower(), int(g[0])
            mon = _SEASON.get(season if season != "autumn" else "fall", 8)
            delta = (year - today.year) * 12 + (mon - today.month)
            if not _auto_season(season) or delta < -1:
                continue
            subpenalty = 1 if self._SUBTERM_RE.search(desc) else 0
            key = (delta, subpenalty, len(desc))   # nearest; then primary/undergrad; then plainest
            if best_key is None or key < best_key:
                best_key, best = key, desc
        return best

    def fetch(self, courses):
        try:
            op, tok = self._session()
        except Exception:
            return {}
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                d = self._post(op, tok, "/Student/Courses/PostSearchCriteria", {"Keyword": f"{subj} {num}"})
                term = self._pick_term(d.get("ActivePlanTerms") or [])
                if not term:
                    continue
                match = None
                for c in d.get("CourseFullModels") or []:
                    if (c.get("SubjectCode") or "").upper() != subj or (c.get("Number") or "").upper() != num:
                        continue
                    if self.campus and self.campus not in (c.get("LocationCodes") or []):
                        continue      # shared district host: that model is a sibling college's
                    match = c
                    break
                if not match or not match.get("MatchingSectionIds"):
                    continue
                sd = self._post(op, tok, "/Student/Courses/Sections",
                                {"sectionIds": match["MatchingSectionIds"], "courseId": match["Id"]})
                secs = {}
                for tm in (sd.get("SectionsRetrieved") or {}).get("TermsAndSections") or []:
                    if term.lower() not in ((tm.get("Term") or {}).get("Description") or "").lower():
                        continue
                    for wrap in tm.get("Sections") or []:
                        s = wrap.get("Section") or wrap
                        if self.campus and (s.get("LocationCode") or "") != self.campus:
                            continue  # belt: keep only THIS college's section rows
                        if not s.get("AreSeatCountsAvailable"):      # counts not published -> skip
                            continue
                        try:
                            av = int(s.get("Available"))            # true count; no count -> skip
                        except (TypeError, ValueError):
                            continue
                        key = str(s.get("Number") or s.get("SectionNameDisplay"))
                        if key in secs:                             # collapse guard
                            continue
                        # open ONLY when Colleague says 'Open'; Waitlisted/Closed => not open
                        secs[key] = {"open": s.get("AvailabilityStatus") == "Open", "seats": max(av, 0)}
                if secs:
                    out[course] = secs
            except Exception:
                continue
        return out


class LoyolaNO(Colleague):
    id = "loyno"; name = "Loyola University New Orleans"
    example = "COSC A211"; host = "loyno-ss.colleague.elluciancloud.com"

class WestTexasAM(Colleague):
    id = "wtamu"; name = "West Texas A&M University"      # != TAMU / TAMU-CC / TAMUC
    example = "MATH 1314"; host = "sss.wtamu.edu"         # single college, campus=""

class CoastalCarolina(Colleague):
    id = "ccu"; name = "Coastal Carolina University"
    example = "ENGL 101"; host = "sservice.coastal.edu"   # single college, campus=""

class Valparaiso(Colleague):
    # textual Colleague variant (base Colleague, NOT NewColleague). Small private (~2.5k).
    id = "valpo"; name = "Valparaiso University"
    example = "MATH 131"; host = "datavu1.valpo.edu"

class Troy(Colleague):
    # textual Colleague guest catalog at sss.troy.edu (the registration side is ADFS-walled,
    # but this catalog is open). Multi-campus shares one catalog, all Troy, no leak.
    id = "troy"; name = "Troy University"
    example = "ENG 1101"; host = "sss.troy.edu"

class UnionNY(Colleague):
    id = "union-ny"; name = "Union College (NY)"
    example = "CEE 301"; host = "selfservice.union.edu"

class ManchesterU(Colleague):
    id = "manchester"; name = "Manchester University"
    example = "INTD 130"; host = "mu-ss.colleague.elluciancloud.com"

class Whitman(Colleague):
    id = "whitman"; name = "Whitman College"
    example = "BIOL 250"; host = "selfservice.whitman.edu"

class Linfield(Colleague):
    id = "linfield"; name = "Linfield University"
    example = "COMP 262L"; host = "selfservice.linfield.edu"

class FranklinU(Colleague):
    id = "franklin-oh"; name = "Franklin University"
    example = "COMP 294"; host = "selfservice.franklin.edu"

class Ursinus(Colleague):
    id = "ursinus"; name = "Ursinus College"
    example = "GER 201"; host = "selfservice.ursinus.edu"

class SalveRegina(Colleague):
    id = "salve"; name = "Salve Regina University"
    example = "ENG 329"; host = "selfservice.salve.edu"

class Cornerstone(Colleague):
    id = "cornerstone"; name = "Cornerstone University"
    example = "EGR 226"; host = "selfservice.cornerstone.edu"

class NorthPark(Colleague):
    id = "northpark"; name = "North Park University"
    example = "MATH 1150"; host = "selfservice.northpark.edu"

class Gannon(Colleague):
    id = "gannon"; name = "Gannon University"
    example = "MATH 115"; host = "selfservice.gannon.edu"

class Mercyhurst(Colleague):
    id = "mercyhurst"; name = "Mercyhurst University"
    example = "COMP 120"; host = "selfservice.mercyhurst.edu"

class SaintVincent(Colleague):
    id = "stvincent"; name = "Saint Vincent College"
    example = "CS 312"; host = "selfservice.stvincent.edu"

class Maryville(Colleague):
    id = "maryville-mo"; name = "Maryville University"
    example = "COMP 101"; host = "selfservice.maryville.edu"

class AshevilleBuncombe(Colleague):
    id = "abtech"; name = "Asheville-Buncombe Technical Community College"
    example = "CSC 113"; host = "selfservice.abtech.edu"

class DurhamTech(Colleague):
    id = "durhamtech"; name = "Durham Technical Community College"
    example = "CSC 121"; host = "selfservice.durhamtech.edu"

class CravenCC(Colleague):
    id = "cravencc"; name = "Craven Community College"
    example = "CSC 113"; host = "selfservice.cravencc.edu"

class KirkwoodCC(Colleague):
    id = "kirkwood"; name = "Kirkwood Community College"
    example = "ENG 108"; host = "selfservice.kirkwood.edu"

class SoutheasternIA(Colleague):
    id = "scc-iowa"; name = "Southeastern Community College (Iowa)"
    example = "ENG 067"; host = "selfservice.scciowa.edu"

class EasternU(Colleague):
    id = "eastern-pa"; name = "Eastern University"
    example = "CSCI 110"; host = "selfservice.eastern.edu"

class Nichols(Colleague):
    id = "nichols"; name = "Nichols College"
    example = "MATH 150"; host = "selfservice.nichols.edu"

class Elms(Colleague):
    id = "elms"; name = "Elms College"
    example = "SPA 2206"; host = "selfservice.elms.edu"

class BladenCC(Colleague):
    id = "bladencc"; name = "Bladen Community College"
    example = "CSC 118"; host = "selfservice.bladencc.edu"

class TarrantCounty(Colleague):
    id = "tccd"; name = "Tarrant County College"
    example = "MATH 0190"; host = "selfservice.tccd.edu"

class Allegheny(Colleague):
    id = "ccac"; name = "Community College of Allegheny County"
    example = "MAT 106"; host = "selfservice.ccac.edu"

class Macomb(Colleague):
    id = "macomb"; name = "Macomb Community College"
    example = "MATH 1050"; host = "selfservice.macomb.edu"

class MidMichigan(Colleague):
    id = "midmich"; name = "Mid Michigan College"
    example = "MAT 104"; host = "selfservice.midmich.edu"

class GuilfordTech(Colleague):
    id = "gtcc"; name = "Guilford Technical Community College"
    example = "BUS 121"; host = "selfservice.gtcc.edu"

class StanlyCC(Colleague):
    id = "stanly"; name = "Stanly Community College"
    example = "MAT 045P"; host = "selfservice.stanly.edu"

class HaywoodCC(Colleague):
    id = "haywood"; name = "Haywood Community College"
    example = "MAT 025"; host = "selfservice.haywood.edu"

class Cedarville(Colleague):
    id = "cedarville"; name = "Cedarville University"
    example = "MATH 2740"; host = "selfservice.cedarville.edu"

class EasternIowaCC(Colleague):
    id = "eicc"; name = "Eastern Iowa Community Colleges"
    example = "HSC 137"; host = "selfservice.eicc.edu"

class McLennan(Colleague):
    id = "mclennan"; name = "McLennan Community College"
    example = "MATH 0308"; host = "selfservice.mclennan.edu"

class Roanoke(Colleague):
    id = "roanoke"; name = "Roanoke College"
    example = "MATH 111"; host = "selfservice.roanoke.edu"

class HardinSimmons(Colleague):
    id = "hsutx"; name = "Hardin-Simmons University"
    example = "CSCI 1320"; host = "selfservice.hsutx.edu"

class Elmhurst(Colleague):
    id = "elmhurst"; name = "Elmhurst University"
    example = "CS 420"; host = "selfservice.elmhurst.edu"

class Bellarmine(Colleague):
    id = "bellarmine"; name = "Bellarmine University"
    example = "CS 310"; host = "selfservice.bellarmine.edu"

class Wittenberg(Colleague):
    id = "wittenberg"; name = "Wittenberg University"
    example = "COMP 305"; host = "selfservice.wittenberg.edu"

class Quinnipiac(Colleague):
    id = "quinnipiac"; name = "Quinnipiac University"
    example = "CIS 245"; host = "selfservice.quinnipiac.edu"

class Juniata(Colleague):
    id = "juniata"; name = "Juniata College"
    example = "CS 485"; host = "selfservice.juniata.edu"

class SWOklahomaState(Colleague):
    id = "swosu"; name = "Southwestern Oklahoma State University"
    example = "COMSC 4943"; host = "selfservice.swosu.edu"

class LuzerneCC(Colleague):
    id = "luzerne"; name = "Luzerne County Community College"
    example = "ENG 102"; host = "selfservice.luzerne.edu"

class EastCentralOK(Colleague):
    id = "ecok"; name = "East Central University"
    example = "ENG 0211"; host = "selfservice.ecok.edu"

class USAOklahoma(Colleague):
    id = "usao"; name = "University of Science & Arts of Oklahoma"
    example = "CSCI 3003"; host = "selfservice.usao.edu"

class Hartwick(Colleague):
    id = "hartwick"; name = "Hartwick College"
    example = "MATH 108"; host = "selfservice.hartwick.edu"

class CaldwellCC(Colleague):
    id = "cccti"; name = "Caldwell Community College & Technical Institute"
    example = "MEC 231"; host = "selfservice.cccti.edu"

class RoanokeChowan(Colleague):
    id = "roanokechowan"; name = "Roanoke-Chowan Community College"
    example = "CIS 110"; host = "selfservice.roanokechowan.edu"

class NorthArkansas(Colleague):
    id = "northark"; name = "North Arkansas College"
    example = "HVAC 1112"; host = "selfservice.northark.edu"

class Aquinas(Colleague):
    id = "aquinas"; name = "Aquinas College"
    example = "CIS 111"; host = "selfservice.aquinas.edu"

class Alma(Colleague):
    id = "alma"; name = "Alma College"
    example = "CSC 240"; host = "selfservice.alma.edu"

class GrandView(Colleague):
    id = "grandview"; name = "Grand View University"
    example = "MATH 340"; host = "selfservice.grandview.edu"

class ElCamino(Colleague):
    id = "elcamino"; name = "El Camino College"
    example = "CSCI 14"; host = "selfservice.elcamino.edu"

class Triton(Colleague):
    id = "triton"; name = "Triton College"
    example = "RHT 101"; host = "selfservice.triton.edu"

class Canyons(Colleague):
    id = "canyons"; name = "College of the Canyons"
    example = "POLS 250"; host = "selfservice.canyons.edu"

class Grossmont(Colleague):
    id = "gcccd"; name = "Grossmont & Cuyamaca Colleges"
    example = "CS 119L"; host = "selfservice.gcccd.edu"

class PrinceGeorges(Colleague):
    id = "pgcc"; name = "Prince George's Community College"
    example = "INT 1540"; host = "selfservice.pgcc.edu"

class GovernorsState(Colleague):
    id = "govst"; name = "Governors State University"
    example = "CPSC 5000"; host = "selfservice.govst.edu"

class CarrollCCMD(Colleague):
    id = "carrollcc"; name = "Carroll Community College"
    example = "CIS 101"; host = "selfservice.carrollcc.edu"

class BergenCC(Colleague):
    id = "bergen"; name = "Bergen Community College"
    example = "CIS 288"; host = "selfservice.bergen.edu"

class CincinnatiState(Colleague):
    id = "cincystate"; name = "Cincinnati State Technical & Community College"
    example = "AMT 100"; host = "selfservice.cincinnatistate.edu"

class JolietJC(Colleague):
    id = "joliet"; name = "Joliet Junior College"
    example = "CIS 122"; host = "selfservice.jjc.edu"

class LewisClarkCC(Colleague):
    id = "lewisclark"; name = "Lewis & Clark Community College"
    example = "ADCG 144"; host = "selfservice.lc.edu"

class MortonCollege(Colleague):
    id = "morton"; name = "Morton College"
    example = "MUS 023"; host = "selfservice.morton.edu"

class McHenry(Colleague):
    id = "mchenry"; name = "McHenry County College"
    example = "MGT 220"; host = "selfservice.mchenry.edu"

class WesternIdaho(Colleague):
    id = "cwi"; name = "College of Western Idaho"
    example = "MATH 118"; host = "selfservice.cwi.edu"

class FingerLakesCC(Colleague):
    id = "flcc"; name = "Finger Lakes Community College"
    example = "CSC 248"; host = "selfservice.flcc.edu"

class HockingCollege(Colleague):
    id = "hocking"; name = "Hocking College"
    example = "MATH 1113"; host = "selfservice.hocking.edu"

class OklahomaChristian(Colleague):
    id = "oc"; name = "Oklahoma Christian University"
    example = "CMSC 2011"; host = "selfservice.oc.edu"

class LincolnLandCC(Colleague):
    id = "llcc"; name = "Lincoln Land Community College"
    example = "CSC 170"; host = "selfservice.llcc.edu"

class Regent(Banner):
    id = "regent"; name = "Regent University"
    example = "CSCI 233"; host = "banssb.regent.edu"; term = "202710"

class ButteCollege(Colleague):
    id = "butte"; name = "Butte College"
    example = "CSCI 21"; host = "selfservice.butte.edu"

class EssexCC(Banner):
    id = "essexcc"; name = "Essex County College"
    example = "CSC 104"; host = "bannerprod.essex.edu"; term = "202702"

class DelawareTech(Banner):
    id = "dtcc"; name = "Delaware Technical Community College"
    example = "CSC 114"; host = "banner.dtcc.edu"; term = "202751"

class WesternNewEngland(Colleague):
    id = "wne"; name = "Western New England University"
    example = "CS 490"; host = "selfservice.wne.edu"

class SaintMichaels(Colleague):
    id = "smcvt"; name = "Saint Michael's College"
    example = "CS 407"; host = "selfservice.smcvt.edu"

class Evansville(Colleague):
    id = "evansville"; name = "University of Evansville"
    example = "CS 350"; host = "selfservice.evansville.edu"

class DenmarkTech(Colleague):
    id = "denmarktech"; name = "Denmark Technical College"
    example = "ENG 102"; host = "selfservice.denmarktech.edu"

class Tulsa(Colleague):
    id = "utulsa"; name = "University of Tulsa"
    example = "CS 4863"; host = "selfservice.utulsa.edu"

class CarlAlbert(Colleague):
    id = "carlalbert"; name = "Carl Albert State College"
    example = "CS 1103"; host = "selfservice.carlalbert.edu"

class RedlandsCC(Colleague):
    id = "redlandscc"; name = "Redlands Community College"
    example = "MATH 2193"; host = "selfservice.redlandscc.edu"

class SoutheastCCNE(Colleague):
    id = "southeastccne"; name = "Southeast Community College (Nebraska)"
    example = "CSCI 1010"; host = "selfservice.southeast.edu"

class Coconino(Banner):
    id = "coconino"; name = "Coconino Community College"
    example = "CIS 120"; host = "registration.coconino.edu"; term = "202680"

class EasternWyoming(Colleague):
    id = "ewc"; name = "Eastern Wyoming College"
    example = "COMP 2000"; host = "selfservice.ewc.wy.edu"

class MissouriValley(Colleague):
    id = "moval"; name = "Missouri Valley College"
    example = "ENGL 130"; host = "selfservice.moval.edu"

class UAHuntsville(Banner):
    id = "uah"; name = "University of Alabama in Huntsville"
    example = "CS 104"; host = "registration.uah.edu"; term = "202609"

class Whittier(Banner):
    id = "whittier"; name = "Whittier College"
    example = "COSC 120"; host = "registration.whittier.edu"; term = "202609"

class SimpsonU(Colleague):
    id = "simpsonu"; name = "Simpson University"
    example = "BUSS 1830"; host = "selfservice.simpsonu.edu"

class WestAlabama(Colleague):
    id = "uwa"; name = "University of West Alabama"
    example = "SAL 305"; host = "selfservice.uwa.edu"

class StFrancisIL(Banner):
    id = "stfrancisil"; name = "University of St. Francis (Illinois)"
    example = "COMP 440"; host = "bannerxe.stfrancis.edu"; term = "202710"

class ColumbiaGreene(Banner):
    id = "sunycgcc"; name = "SUNY Columbia-Greene Community College"
    example = "CS 126"; host = "banner.sunycgcc.edu"; term = "202680"

class FDU(Colleague):
    id = "fdu"; name = "Fairleigh Dickinson University"
    example = "CSCI 7789"; host = "selfservice.fdu.edu"

class CentenaryNJ(Colleague):
    id = "centenarynj"; name = "Centenary University (New Jersey)"
    example = "EDU 3073"; host = "selfservice.centenaryuniversity.edu"

class StFrancisBK(Colleague):
    id = "sfcbk"; name = "St. Francis College (Brooklyn)"
    example = "CS 6001"; host = "selfservice.sfc.edu"

class LakeMichigan(Banner):
    id = "lakemichigan"; name = "Lake Michigan College"
    example = "CIS 100"; host = "ssbprod.lakemichigancollege.edu"; term = "202720"

class MVNU(Colleague):
    id = "mvnu"; name = "Mount Vernon Nazarene University"
    example = "CSC 1020"; host = "selfservice.mvnu.edu"

class WashingtonStateOH(Colleague):
    id = "wscc"; name = "Washington State College of Ohio"
    example = "ENGL 1520"; host = "selfservice.wscc.edu"

class ConnecticutCollege(Banner):
    id = "conncoll"; name = "Connecticut College"
    example = "MAT 112"; host = "reg-prod.ec.conncoll.edu"; term = "202690"

class BunkerHill(Colleague):
    id = "bhcc"; name = "Bunker Hill Community College"
    example = "CSC 242"; host = "selfservice.bhcc.edu"

class Denison(Banner):
    id = "denison"; name = "Denison University"
    example = "CS 451"; host = "banner.denison.edu"; term = "202640"

class KentuckyState(Banner):
    id = "kysu"; name = "Kentucky State University"
    example = "MAT 115"; host = "reg-prod.ec.kysu.edu"; term = "202710"

class TCLowcountry(Colleague):
    id = "tcl"; name = "Technical College of the Lowcountry"
    example = "ENG 101"; host = "selfservice.tcl.edu"

class MarsHill(Colleague):
    id = "mhu"; name = "Mars Hill University"
    example = "CS 220"; host = "selfservice.mhu.edu"

class WesternPiedmont(Colleague):
    id = "wpcc"; name = "Western Piedmont Community College"
    example = "CTI 110"; host = "selfservice.wpcc.edu"

class MitchellCC(Colleague):
    id = "mitchellcc"; name = "Mitchell Community College"
    example = "CSC 151"; host = "selfservice.mitchellcc.edu"

class SUNYPurchase(Banner):
    id = "purchase"; name = "SUNY Purchase"
    example = "MAT 1060"; host = "ssb.purchase.edu"; term = "202640"

class SUNYESF(Banner):
    id = "esf"; name = "SUNY College of Environmental Science and Forestry"
    example = "APM 105"; host = "banner.esf.edu"; term = "202720"

class NorthGATech(Banner):
    id = "northgatech"; name = "North Georgia Technical College"
    example = "ENGL 1101"; host = "banner.northgatech.edu"; term = "202712"

class Colgate(Banner):
    # Fall term is published "(View Only)" until registration opens — same live Banner
    # data underneath. Auto-term can't parse the tag, so the term is pinned here and
    # needs a manual bump each semester (like the VT-style customs).
    id = "colgate"; name = "Colgate University"
    example = "COSC 482"; host = "banner.colgate.edu"; term = "202601"

class UIndy(Banner):
    # UIndy names terms "Semester I 2026-2027" (no season word), which the auto-term
    # parser can't read — term pinned, manual bump each semester.
    id = "uindy"; name = "University of Indianapolis"
    example = "CSCI 155"; host = "banner.uindy.edu"; term = "202610"

class Northwood(Colleague):
    id = "northwood"; name = "Northwood University"
    example = "CS 4000"; host = "selfservice.northwood.edu"

class Rowan(Banner):
    # Rowan numbers courses with 5 digits ("CS 01104") — only reachable after the
    # Banner._code parser was widened to accept 1-5 digit numbers.
    id = "rowan"; name = "Rowan University"
    example = "CS 01104"; host = "ssb.rowan.edu"; term = "202640"

class Roosevelt(Banner):
    id = "roosevelt"; name = "Roosevelt University"
    example = "CST 480"; host = "banner.roosevelt.edu"; term = "202710"

class NationalLouis(Banner):
    # Fall 2026 published "(View Only)" — same live Banner data; term pinned, needs a
    # manual bump each semester (auto-term can't parse the View Only tag).
    id = "nlu"; name = "National Louis University"
    example = "CIS 540"; host = "banner.nl.edu"; term = "202690"

class MercyUniversity(Banner):
    # Runs parallel Fall terms (Semester/Trimester/Quarter). 202630 = Fall Semester
    # (the main undergrad term). auto_term pinned so the refresher can't drift it onto
    # the Quarter/grad term, which the season-only picker can't distinguish.
    id = "mercyny"; name = "Mercy University (New York)"
    example = "CISC 120"; host = "reg-prod.ec.mercy.edu"; term = "202630"; auto_term = False

class Pasadena(Banner):
    id = "pasadena"; name = "Pasadena City College"
    example = "CS 002"; host = "reg-prod.ec.pasadena.edu"; term = "202670"

class SanJoseEvergreen(Colleague):
    id = "sjeccd"; name = "San Jose-Evergreen Community College District"
    example = "CGID 001"; host = "selfservice.sjeccd.edu"

# --- July 8 2026 IPEDS batch (each verified through the production fetcher: live
# sections, clean int seat counts, latency < 5s; examples discovered from each
# school's own search API). Excluded from the same handoff after failing the gate:
# Victor Valley, Colorado Mountain, Columbia College MO, Campbell (sections exist
# but term-filtered fetch returns none / counts unpublished), Loras (dotted subject
# codes the adapter can't parse), Southwestern TX (non-standard numbering),
# Washington Adventist (host unreachable).
class CollegeOfTheDesert(Colleague):
    id = "codesert"; name = "College of the Desert"
    example = "ENG 005B"; host = "ss.collegeofthedesert.edu"

class Guam(Colleague):
    id = "guam"; name = "University of Guam"
    example = "CEE 404"; host = "selfservice.uog.edu"

class SimpsonCollegeIA(Colleague):
    id = "simpsoncollege"; name = "Simpson College"
    example = "MATH 130"; host = "ss.simpson.edu"

class Kankakee(Colleague):
    id = "kankakee"; name = "Kankakee Community College"
    example = "ENGL 1613"; host = "selfservice.kcc.edu"

class Midway(Colleague):
    id = "midway"; name = "Midway University"
    example = "ENG 100"; host = "ss.midway.edu"

class WorWic(Colleague):
    id = "worwic"; name = "Wor-Wic Community College"
    example = "ENG 101"; host = "selfservice.worwic.edu"

class DeltaMI(Colleague):
    id = "deltami"; name = "Delta College"
    example = "ENG 111C"; host = "ss.delta.edu"

class WilliamJewell(Colleague):
    id = "jewell"; name = "William Jewell College"
    example = "BIO 380"; host = "ss.jewell.edu"

class JamesSprunt(Colleague):
    id = "jamessprunt"; name = "James Sprunt Community College"
    example = "ENG 111"; host = "ss.jamessprunt.edu"

class LeesMcRae(Colleague):
    id = "leesmcrae"; name = "Lees-McRae College"
    example = "ENG 499"; host = "selfservice.lmc.edu"

class LenoirCC(Colleague):
    id = "lenoircc"; name = "Lenoir Community College"
    example = "ENG 112"; host = "ss.lenoircc.edu"

class PiedmontNC(Colleague):
    id = "piedmontnc"; name = "Piedmont Community College (NC)"
    example = "ENG 111"; host = "ss.piedmontcc.edu"

class SampsonCC(Colleague):
    id = "sampsoncc"; name = "Sampson Community College"
    example = "ENG 111"; host = "ss.sampsoncc.edu"

class SouthwesternCCNC(Colleague):
    id = "southwesterncc"; name = "Southwestern Community College (NC)"
    example = "ENG 111"; host = "ss.southwesterncc.edu"

class Daemen(Colleague):
    id = "daemen"; name = "Daemen University"
    example = "LIT 147"; host = "selfservice.daemen.edu"

class EasternOKState(Colleague):
    id = "eosc"; name = "Eastern Oklahoma State College"
    example = "ENGL 1113"; host = "ss.eosc.edu"

class SoutheasternOKState(Colleague):
    id = "seosu"; name = "Southeastern Oklahoma State University"
    example = "ENG 4990"; host = "selfservice.se.edu"

class WesternOKState(Colleague):
    id = "wosc"; name = "Western Oklahoma State College"
    example = "ENGL 1213"; host = "selfservice.wosc.edu"

class HolyFamily(Colleague):
    id = "holyfamily"; name = "Holy Family University"
    example = "MATH 109"; host = "selfservice.holyfamily.edu"

class MontgomeryCountyCC(Colleague):
    id = "mc3"; name = "Montgomery County Community College"
    example = "ENG 101"; host = "selfservice.mc3.edu"

class WestminsterUT(Colleague):
    id = "westminsterut"; name = "Westminster University"
    example = "LMW 326"; host = "ss.westminstercollege.edu"

class WesternWyoming(Colleague):
    id = "westernwyoming"; name = "Western Wyoming Community College"
    example = "ENGL 1010"; host = "selfservice.westernwyoming.edu"

# --- July 8 batch 4 (4-year push). Each quirk is contained in its own tiny subclass;
# the base Colleague stays untouched. Cut from the same handoff: UNC Charlotte (already
# live as `uncc` — selfservice.charlotte.edu is the same school's rebranded domain),
# TESU (monthly rolling terms, no season semantics — poor seat-watch fit), Colorado
# Mountain (HOLD: picker correctly chooses '2026 Fall' but fall sections aren't loaded
# yet — revisit once they are).
class SacredHeart(Colleague):
    id = "sacredheart"; name = "Sacred Heart University"
    example = "MA 301"; host = "colleague.sacredheart.edu"

class WashingtonAdventist(Colleague):
    id = "wau"; name = "Washington Adventist University"
    example = "ENGL 314"; host = "ss.wau.edu"

class CollegeOfIdaho(Colleague):
    id = "collegeofidaho"; name = "The College of Idaho"
    example = "ENGL 2115"; host = "selfservice.collegeofidaho.edu"

class DigiPen(Colleague):
    id = "digipen"; name = "DigiPen Institute of Technology"
    example = "CS 100"; host = "selfservice.digipen.edu"


class AbbrevTermColleague(Colleague):
    """Campbell writes seasons as FA/SP/SU ('2026 FA Undergraduate') — the base picker
    can't parse those, so it was choosing '2027 Fall UG' (13 months out) over the
    CURRENT '2026 FA Undergraduate'. Expand the abbreviations (word-bounded) before
    the base picker parses, then return the REAL description string (fetch must match
    it verbatim against each section's term)."""
    def _pick_term(self, terms):
        fixed = []
        for t in terms:
            d = t.get("Description") or ""
            d2 = re.sub(r"\bFA\b", "Fall", d)
            d2 = re.sub(r"\bSP\b", "Spring", d2)
            d2 = re.sub(r"\bSU\b", "Summer", d2)
            fixed.append({"Description": d2, "_orig": d})
        pick = super()._pick_term(fixed)
        if pick is None:
            return None
        for f in fixed:
            if f["Description"] == pick:
                return f["_orig"]
        return None

class Campbell(AbbrevTermColleague):
    id = "campbell"; name = "Campbell University"
    example = "ENGL 419"; host = "ss.campbell.edu"


class DottedColleague(Colleague):
    """Loras prefixes every subject with a letter+dot ('L.ENG 135') — the base
    subject regex refuses dots and the school would silently return nothing."""
    _SUBJ_RE = re.compile(r"^([A-Za-z]\.[A-Za-z]{2,5}|[A-Za-z]{2,5})[ \-]?([A-Za-z]?\d{2,4}[A-Za-z]?)$")

class Loras(DottedColleague):
    id = "loras"; name = "Loras College"
    example = "L.ENG 135"; host = "selfservice.loras.edu"


class DigitTermColleague(Colleague):
    """Columbia MO terms embed digits between season and year ('Fall 16-Week,
    2026/2027') which the base season parser can't cross — it was picking 'Summer
    Semester, 2028/2029' (the only parseable option, 2 years out). Strip the week
    token before parsing; the sub-term penalty + shortest-description tiebreak then
    prefer the plain 16-week full semester over Early/Late 8-week variants."""
    def _pick_term(self, terms):
        fixed = []
        for t in terms:
            d = t.get("Description") or ""
            d2 = re.sub(r"\b\d+-?\s*Week,?\s*", "", d)
            fixed.append({"Description": d2, "_orig": d})
        pick = super()._pick_term(fixed)
        if pick is None:
            return None
        for f in fixed:
            if f["Description"] == pick:
                return f["_orig"]
        return None

class ColumbiaMO(DigitTermColleague):
    id = "columbiamo"; name = "Columbia College (MO)"
    example = "ENGL 267W"; host = "selfservice.ccis.edu"


class SynthTermColleague(Colleague):
    """NWOSU publishes an EMPTY ActivePlanTerms list even though its sections carry
    normal 'Fall 2026'-style term names — synthesize the nearest upcoming season in
    exactly that format when the list is empty. Gated live: the synthesized string
    matched real fall sections."""
    def _pick_term(self, terms):
        pick = super()._pick_term(terms)
        if pick:
            return pick
        today = datetime.date.today()
        best, bd = None, None
        for season, mon in (("Spring", 1), ("Summer", 5), ("Fall", 8)):
            for yr in (today.year, today.year + 1):
                delta = (yr - today.year) * 12 + (mon - today.month)
                if delta < -1:
                    continue
                if bd is None or delta < bd:
                    bd, best = delta, f"{season} {yr}"
        return best

class NWOSU(SynthTermColleague):
    id = "nwosu"; name = "Northwestern Oklahoma State University"
    example = "ENGL 1213"; host = "selfservice.nwosu.edu"


class AcadYearColleague(Colleague):
    """Term labels use the academic-year 'YY/YY' style ('Fall 26/27 Semester') that the
    base season parser can't read. Rewrite to a plain 'Season 20YY' — Fall takes the
    FIRST year (26->2026), Spring/Summer/Winter the SECOND (Spring 26/27 = 2027) — then
    delegate to the base picker (which keeps its sub-term penalty + shortest-desc
    tiebreak, so 'Fall 26/27 Semester' beats 'Fall 26/27 Late Term')."""
    def _pick_term(self, terms):
        fixed = []
        for t in terms:
            d = t.get("Description") or ""
            m = re.search(r"(Fall|Spring|Summer|Winter)\s+(\d\d)/(\d\d)", d, re.I)
            if m:
                season = m.group(1).capitalize()
                yr = m.group(2) if season == "Fall" else m.group(3)
                d = re.sub(r"\d\d/\d\d", f"20{yr}", d)
            fixed.append({"Description": d, "_orig": (t.get("Description") or "")})
        pick = super()._pick_term(fixed)
        return next((f["_orig"] for f in fixed if f["Description"] == pick), None) if pick else None

_QTR_MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

class QuarterColleague(Colleague):
    """Quarter school whose term labels give a month span, not a season word
    ('2026-2027 Quarter 1 Aug-Oct'). Pick the nearest UPCOMING term by its START month:
    Aug-Dec falls in the range's first year, Jan-Jul in the second. All four quarters
    (plus summer) are valid registration terms."""
    def _pick_term(self, terms):
        today = datetime.date.today()
        best, bd = None, None
        for t in terms:
            d = t.get("Description") or ""
            ym = re.search(r"(20\d\d)-(20\d\d)", d)
            mm = re.search(r"\b([A-Z][a-z]{2})-[A-Z][a-z]{2}", d)
            if not (ym and mm):
                continue
            mon = _QTR_MON.get(mm.group(1).lower())
            if not mon:
                continue
            year = int(ym.group(1)) if mon >= 8 else int(ym.group(2))
            delta = (year - today.year) * 12 + (mon - today.month)
            if delta < -1:
                continue
            if bd is None or delta < bd:
                bd, best = delta, d
        return best

class GeorgiaMilitary(QuarterColleague):
    id = "gmc"; name = "Georgia Military College"
    example = "ENG 101"; host = "selfservice.gmc.cc.ga.us"


class MainTermColleague(Colleague):
    """Schools with PROGRAM-prefixed parallel terms ('PA Fall 2026', 'Nutrition Fall
    2026', 'Health Sciences Fall 2026') alongside the main 'Fall 2026 Term'. The base
    picker's shortest-desc tiebreak wrongly favors a short program prefix (e.g. 'PA
    Fall 2026'), landing on a sub-population that lacks the watched course's sections.
    Fix: drop any term with words BEFORE the season word, so only main-population terms
    reach the base picker."""
    def _pick_term(self, terms):
        main = [t for t in terms
                if not (lambda m: m and (t.get("Description") or "")[:m.start()].strip())(
                    re.search(r"\b(spring|summer|fall|autumn|winter)\b", t.get("Description") or "", re.I))]
        return super()._pick_term(main if main else terms)

class Bridgeport(MainTermColleague):
    # Live host is the SaaS domain; selfservice.bridgeport.edu 301-redirects to it but a
    # POST doesn't follow the redirect, so point straight at the SaaS host.
    id = "bridgeport"; name = "University of Bridgeport"
    example = "ENGL 101"; host = "colss-prod.bridgeportsaas.elluciancloud.com"


class AlnumSubjectColleague(Colleague):
    """Southwestern TX subjects embed digits ('ENG10 134', 'CHE51 101') — space
    separator required so the digits stay unambiguous."""
    _SUBJ_RE = re.compile(r"^([A-Za-z]{2,5}\d{0,2})\s+([A-Za-z]?\d{2,4}[A-Za-z]?)$")

class SouthwesternTX(AlnumSubjectColleague):
    id = "southwesterntx"; name = "Southwestern University (TX)"
    example = "HIS16 034"; host = "selfservice.southwestern.edu"


class VSC(Colleague):
    """Vermont State Colleges: ONE Colleague host serves TWO institutions (VTSU 4-year
    + CCV community college) distinguished ONLY by term-name prefix. The picker sees
    ONLY own-prefix terms, and fetch's verbatim term-description match then structurally
    excludes the other institution's sections ('VTSU Fall 2026' can never match a
    section filed under 'CCV Fall 2026'). Isolation proven live: the same course code
    (ENG 1061) returns DIFFERENT section sets per prefix (31 vs 34)."""
    term_prefix = ""
    def _pick_term(self, terms):
        mine = [t for t in terms
                if (t.get("Description") or "").startswith(self.term_prefix + " ")]
        return super()._pick_term(mine)

class VTSU(VSC):
    id = "vtsu"; name = "Vermont State University"
    example = "ENG 1061"; host = "selfservice.vsc.edu"; term_prefix = "VTSU"

class CCV(VSC):
    id = "ccv"; name = "Community College of Vermont"
    example = "ENG 1061"; host = "selfservice.vsc.edu"; term_prefix = "CCV"

# --- July 8 batch 5: Ellucian-Cloud Colleague sweep ({school}-ss.colleague.
# elluciancloud.com pattern), 34 gated adds. Scrapped from the same handoff:
# McCormick Seminary + SEBTS (no sections in their picked terms — niche grad
# calendars), Aurora University + American Samoa CC (HOLD: fall sections not
# loaded yet, revisit), Southwestern Law (rolling terms, research-side cut).
class ExactTermColleague(Colleague):
    """Kean's Wenzhou (China) branch SUFFIXES the shared term names — 'Fall 2026
    Wenzhou' CONTAINS 'Fall 2026', so the base substring term match would leak
    branch-campus sections into US results. Require exact term equality."""
    def fetch(self, courses):
        try:
            op, tok = self._session()
        except Exception:
            return {}
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                d = self._post(op, tok, "/Student/Courses/PostSearchCriteria", {"Keyword": f"{subj} {num}"})
                term = self._pick_term(d.get("ActivePlanTerms") or [])
                if not term:
                    continue
                match = None
                for c in d.get("CourseFullModels") or []:
                    if (c.get("SubjectCode") or "").upper() == subj and (c.get("Number") or "").upper() == num:
                        match = c
                        break
                if not match or not match.get("MatchingSectionIds"):
                    continue
                sd = self._post(op, tok, "/Student/Courses/Sections",
                                {"sectionIds": match["MatchingSectionIds"], "courseId": match["Id"]})
                secs = {}
                for tm in (sd.get("SectionsRetrieved") or {}).get("TermsAndSections") or []:
                    if term.lower() != ((tm.get("Term") or {}).get("Description") or "").lower():
                        continue                       # EXACT match only — no Wenzhou leak
                    for wrap in tm.get("Sections") or []:
                        sec = wrap.get("Section") or wrap
                        if not sec.get("AreSeatCountsAvailable"):
                            continue
                        try:
                            av = int(sec.get("Available"))
                        except (TypeError, ValueError):
                            continue
                        key = str(sec.get("Number") or sec.get("SectionNameDisplay"))
                        if key in secs:
                            continue
                        secs[key] = {"open": sec.get("AvailabilityStatus") == "Open", "seats": max(av, 0)}
                if secs:
                    out[course] = secs
            except Exception:
                continue
        return out

class Kean(ExactTermColleague):
    id = "kean"; name = "Kean University"
    example = "ESL 0095"; host = "kean-ss.colleague.elluciancloud.com"


class ShortYearTermColleague(Colleague):
    """Lincoln MO terms: 'FA 26 Semester 16 Wk' — abbreviated seasons AND 2-digit
    years, both invisible to the base season parser (it was picking a 2029 term)."""
    def _pick_term(self, terms):
        fixed = []
        for t in terms:
            d = t.get("Description") or ""
            d2 = re.sub(r"\bFA\b", "Fall", d)
            d2 = re.sub(r"\bSP\b", "Spring", d2)
            d2 = re.sub(r"\bSU\b", "Summer", d2)
            d2 = re.sub(r"\b(2\d)\b", r"20\1", d2)
            fixed.append({"Description": d2, "_orig": d})
        pick = super()._pick_term(fixed)
        if pick is None:
            return None
        for f in fixed:
            if f["Description"] == pick:
                return f["_orig"]
        return None

class LincolnMO(ShortYearTermColleague):
    id = "lincolnmo"; name = "Lincoln University (Missouri)"
    example = "ENG 101"; host = "lincolnu-ss.colleague.elluciancloud.com"


# --- July 11 batch 21: SUNY Onondaga (Codex find, Fable relay). Official
# selfservice.sunyocc.edu 301s to the SaaS host; POSTs don't follow redirects,
# so point straight at the resolved host (Bridgeport lesson).
class Onondaga(Colleague):
    id = "suny-onondaga"; name = "SUNY Onondaga Community College"
    example = "BIO 121"; host = "colss-prod.ec.sunyocc.edu"


class NewColleague(Colleague):
    """Ellucian Colleague Self-Service — NEWER (Angular-era) API variant. Same guest
    /Student/Courses catalog + antiforgery token, but search is POST /SearchAsync with
    {"searchParameters": <JSON-STRING>}, sections POST /SectionsAsync, TermsAndSections
    sits at the TOP level (no SectionsRetrieved wrapper), and AvailabilityStatus is a
    NUMERIC enum instead of textual 'Open' (full-code varies by school: LVC 1, Augustana 2).
    ACCURACY: the enum is untrusted by design — 0 alone could be a fake-open default, so a
    section is open ONLY when status == 0 AND Available > 0, two independent live signals
    (Available == Capacity - Enrolled held on every row probed; full sections show
    status != 0 with Enrolled == Capacity, proving the field is real enrollment, not a
    default). Guest search indexes ONLY active plan terms (a filter on a finished term
    returns no courses), so the completed-term test is run per school on current-term
    FULL sections: enrolled==capacity rows must carry a non-0 status before shipping.
    {} on any failure. Subclass sets: id, name, example, host."""

    def fetch(self, courses):
        try:
            op, tok = self._session()
        except Exception:
            return {}
        out = {}
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                params = json.dumps({"keyword": f"{subj} {num}",
                                     "pageNumber": 1, "quantityPerPage": 30})
                d = self._post(op, tok, "/Student/Courses/SearchAsync",
                               {"searchParameters": params})
                term = self._pick_term(d.get("ActivePlanTerms") or [])
                if not term:
                    continue
                match = None
                for c in d.get("CourseFullModels") or []:
                    if (c.get("SubjectCode") or "").upper() == subj and (c.get("Number") or "").upper() == num:
                        match = c
                        break
                if not match or not match.get("MatchingSectionIds"):
                    continue
                sd = self._post(op, tok, "/Student/Courses/SectionsAsync",
                                {"courseId": match["Id"], "sectionIds": match["MatchingSectionIds"]})
                secs = {}
                for tm in sd.get("TermsAndSections") or []:
                    if term.lower() not in ((tm.get("Term") or {}).get("Description") or "").lower():
                        continue
                    for wrap in tm.get("Sections") or []:
                        s = wrap.get("Section") or wrap
                        if not s.get("AreSeatCountsAvailable"):      # counts not published -> skip
                            continue
                        try:
                            av = int(s.get("Available"))            # true count; no count -> skip
                            status = int(s.get("AvailabilityStatus"))
                        except (TypeError, ValueError):
                            continue
                        key = str(s.get("Number") or s.get("SectionNameDisplay"))
                        if key in secs:                             # collapse guard
                            continue
                        # numeric enum untrusted: open needs status==0 AND a real seat
                        secs[key] = {"open": status == 0 and av > 0, "seats": max(av, 0)}
                if secs:
                    out[course] = secs
            except Exception:
                continue
        return out


class YearSpanNewColleague(NewColleague):
    """Newer-API schools whose term labels lead with an academic-year SPAN
    ('2026-27 Fall Semester', Augustana IL style) — the digit run in '-27' sits between
    year and season, which the base season parser can't cross. Rewrite to 'Season 20YY'
    (Fall keeps the FIRST year; Spring/Summer/Winter take the SECOND — '2026-27 Spring'
    is spring of 2027) then delegate to the base picker, sub-term penalty intact."""
    def _pick_term(self, terms):
        fixed = []
        for t in terms:
            d = t.get("Description") or ""
            m = re.match(r"\s*(20\d\d)-(\d\d)\s+(Fall|Spring|Summer|Winter)\b(.*)", d, re.I)
            if m:
                season = m.group(3).capitalize()
                yr = m.group(1) if season == "Fall" else m.group(1)[:2] + m.group(2)
                d = f"{season} {yr}{m.group(4)}"
            fixed.append({"Description": d, "_orig": (t.get("Description") or "")})
        pick = super()._pick_term(fixed)
        return next((f["_orig"] for f in fixed if f["Description"] == pick), None) if pick else None

# --- Batch 22: newer-Colleague schools (numeric-status SearchAsync/SectionsAsync).
# Enum verified per school; conservative rule (status==0 AND Available>0) in NewColleague.
class AugustanaIL(YearSpanNewColleague):   # ≠ Augustana University; term '2026-27 Fall Semester'
    id = "augustana-il"; name = "Augustana College (IL)"
    example = "BIOL 130"; host = "selfservice.augustana.edu"

class CamdenCounty(NewColleague):
    id = "camdencc"; name = "Camden County College"
    example = "BIO 121"; host = "selfservice.camdencc.edu"

class WalshCollege(NewColleague):          # ≠ Walsh University (id 'walsh', already live)
    id = "walshcollege"; name = "Walsh College"
    example = "ACC 316"; host = "selfservice.walshcollege.edu"

class WorcesterState(NewColleague):        # ≠ Worcester Polytechnic; subject EN not ENGL
    id = "worcesterstate"; name = "Worcester State University"
    example = "EN 101"; host = "selfservice.worcester.edu"


class Mercer(Colleague):
    id = "mercer"; name = "Mercer University"
    example = "HOS 111"; host = "mercer-ss.colleague.elluciancloud.com"

class Ashland(Colleague):
    id = "ashland"; name = "Ashland University"
    example = "MATH 108"; host = "ashland-ss.colleague.elluciancloud.com"

class ColumbiaChicago(Colleague):
    id = "colum"; name = "Columbia College Chicago"
    example = "ENGL 111"; host = "colum-ss.colleague.elluciancloud.com"

class SaintXavier(Colleague):
    id = "sxu"; name = "Saint Xavier University"
    example = "ENGL 317"; host = "sxu-ss.colleague.elluciancloud.com"

class OlivetNazarene(Colleague):
    id = "olivet"; name = "Olivet Nazarene University"
    example = "ENGL 303"; host = "olivet-ss.colleague.elluciancloud.com"

class McKendree(Colleague):
    id = "mckendree"; name = "McKendree University"
    example = "SPE 691"; host = "mckendree-ss.colleague.elluciancloud.com"

class UMobile(Colleague):
    id = "umobile"; name = "University of Mobile"
    example = "TE 471"; host = "umobile-ss.colleague.elluciancloud.com"

class DominicanCA(Colleague):
    id = "dominicanca"; name = "Dominican University of California"
    example = "ENGL 4202"; host = "dominican-ss.colleague.elluciancloud.com"

class Chaminade(Colleague):
    id = "chaminade"; name = "Chaminade University of Honolulu"
    example = "ED 405"; host = "selfservice.chaminade.edu"

class StThomasFL(Colleague):
    id = "stthomasfl"; name = "St. Thomas University (FL)"
    example = "EDT 620"; host = "stu-ss.colleague.elluciancloud.com"

class Naropa(Colleague):
    id = "naropa"; name = "Naropa University"
    example = "REL 602"; host = "naropa-ss.colleague.elluciancloud.com"

class Goodwin(Colleague):
    id = "goodwin"; name = "Goodwin University"
    example = "ENG 102"; host = "goodwin-ss.colleague.elluciancloud.com"

class Felician(Colleague):
    id = "felician"; name = "Felician University"
    example = "ENG 102"; host = "ss.felician.edu"

class Neumann(Colleague):
    id = "neumann"; name = "Neumann University"
    example = "ENG 101"; host = "selfserviceprod.neumann.edu"

class WilsonCollege(Colleague):
    id = "wilson"; name = "Wilson College"
    example = "MAT 103"; host = "wilson-ss.colleague.elluciancloud.com"

class LeTourneau(Colleague):
    id = "letu"; name = "LeTourneau University"
    example = "ENGL 1013"; host = "letu-ss.colleague.elluciancloud.com"

class SWAU(Colleague):
    id = "swau"; name = "Southwestern Adventist University"
    example = "ENGL 121L"; host = "swau-ss.colleague.elluciancloud.com"

class Trevecca(Colleague):
    id = "trevecca"; name = "Trevecca Nazarene University"
    example = "ENG 1080"; host = "trevecca-ss.colleague.elluciancloud.com"

class StFrancisWayne(Colleague):
    id = "stfranciswayne"; name = "University of Saint Francis (Fort Wayne)"
    example = "ENGL 104"; host = "sf-ss.colleague.elluciancloud.com"

class PointU(Colleague):
    id = "pointu"; name = "Point University"
    example = "ENGL 102"; host = "point-ss.colleague.elluciancloud.com"

class SpartanburgMethodist(Colleague):
    id = "smcsc"; name = "Spartanburg Methodist College"
    example = "ENGL 101"; host = "smcsc-ss.colleague.elluciancloud.com"

class CIIS(Colleague):
    id = "ciis"; name = "California Institute of Integral Studies"
    example = "PSY 9999P"; host = "ciis-ss.colleague.elluciancloud.com"

class BridgesCC(Colleague):
    id = "bridges"; name = "Bridges Christian College"
    example = "ENG 116"; host = "bcc-ss.colleague.elluciancloud.com"

class MilesCollege(Colleague):
    id = "miles"; name = "Miles College"
    example = "BY 406"; host = "miles-ss.colleague.elluciancloud.com"

class EdwardWaters(Colleague):
    id = "edwardwaters"; name = "Edward Waters University"
    example = "MAC 1105"; host = "ew-ss.colleague.elluciancloud.com"

class Fisk(Colleague):
    id = "fisk"; name = "Fisk University"
    example = "BIOL 291"; host = "fisk-ss.colleague.elluciancloud.com"

class LeMoyneOwen(Colleague):
    id = "lemoyneowen"; name = "LeMoyne-Owen College"
    example = "ENGL 313"; host = "loc-ss.colleague.elluciancloud.com"

class HustonTillotson(Colleague):
    id = "htu"; name = "Huston-Tillotson University"
    example = "ENGL 3373"; host = "htu-ss.colleague.elluciancloud.com"

class LincolnPA(Colleague):
    id = "lincolnpa"; name = "Lincoln University (Pennsylvania)"
    example = "MAT 1006"; host = "lincoln-ss.colleague.elluciancloud.com"

class BrooklynLaw(Colleague):
    id = "brooklaw"; name = "Brooklyn Law School"
    example = "CPL 311"; host = "brooklaw-ss.colleague.elluciancloud.com"

class Weatherford(Colleague):
    id = "weatherford"; name = "Weatherford College"
    example = "ENGL 2341"; host = "wc-ss.colleague.elluciancloud.com"

class LacCourteOreilles(Colleague):
    id = "lco"; name = "Lac Courte Oreilles Ojibwe University"
    example = "MTH 146"; host = "lco-ss.colleague.elluciancloud.com"

# --- July 8 batch 6. Scrapped: Victor Valley — its course search serves ARCHIVE
# sections (Spring 2024) while advertising Fall 2026 terms; false-freshness trap,
# third failed gate, do not re-add. Deferred upstream: Columbus State OH, Pitt CC
# (no guest ActivePlanTerms), Aurora U + American Samoa CC (fall not loaded).
class Georgetown(Banner):
    id = "georgetown"; name = "Georgetown University"
    example = "ACCT 1101"; host = "reg-prod.georgetown.elluciancloud.com"; term = "202630"

class OleMiss(Banner):
    id = "olemiss"; name = "University of Mississippi"
    example = "ENGL 2220"; host = "reg-prod.olemiss.elluciancloud.com"; term = "202710"

class CentralOklahoma(Banner):
    id = "uco"; name = "University of Central Oklahoma"
    example = "ACM 1132"; host = "reg-prod.uco.elluciancloud.com"; term = "202710"

class EasternOregon(Banner):
    id = "eou"; name = "Eastern Oregon University"
    example = "ACCT 420"; host = "reg-prod.eou.elluciancloud.com"; term = "202701"

class HelenaCollege(Banner):
    id = "helena"; name = "Helena College (University of Montana)"
    example = "ACTG 101"; host = "reg-prod.helenacollege.elluciancloud.com"; term = "202670"

class MCCKC(Banner):
    id = "mcckc"; name = "Metropolitan Community College (Kansas City)"
    example = "ACCT 100"; host = "reg-prod.mcckc.elluciancloud.com"; term = "202660"


class CodedTermColleague(Colleague):
    """NC colleges code terms as '2026FA' — expand to 'Fall 2026' for the season
    parser, return the REAL description for fetch's verbatim term match."""
    def _pick_term(self, terms):
        fixed = []
        for t in terms:
            d = t.get("Description") or ""
            d2 = re.sub(r"\b(20\d\d)\s*FA\b", r"Fall \1", d)
            d2 = re.sub(r"\b(20\d\d)\s*SP\b", r"Spring \1", d2)
            d2 = re.sub(r"\b(20\d\d)\s*SU\b", r"Summer \1", d2)
            d2 = re.sub(r"\b(20\d\d)\s*WI\b", r"Winter \1", d2)
            fixed.append({"Description": d2, "_orig": d})
        pick = super()._pick_term(fixed)
        if pick is None:
            return None
        for f in fixed:
            if f["Description"] == pick:
                return f["_orig"]
        return None


class NumSubjColleague(Colleague):
    """WI technical colleges: purely numeric subject codes ('804 123' = math);
    space separator required (same class of quirk as the Banner WCTC/Blackhawk fix)."""
    _SUBJ_RE = re.compile(r"^([A-Za-z0-9]{2,6})\s+([A-Za-z]?\d{2,4}[A-Za-z]?)$")


class Cabrillo(Colleague):
    id = "cabrillo"; name = "Cabrillo College"
    example = "ENGL 115"; host = "cabrillo-ss.colleague.elluciancloud.com"

class Mohave(Colleague):
    id = "mohave"; name = "Mohave Community College"
    example = "TRM 091"; host = "mohave-ss.colleague.elluciancloud.com"

class StateCenterCCD(Colleague):
    id = "scccd"; name = "State Center Community College District"
    example = "ENGL 205"; host = "selfservice.scccd.edu"

class RendLake(Colleague):
    id = "rendlake"; name = "Rend Lake College"
    example = "ENGL 1411"; host = "rlc-ss.colleague.elluciancloud.com"

class IllinoisValley(Colleague):
    id = "ivcc"; name = "Illinois Valley Community College"
    example = "BUS 1230"; host = "ivcc-ss.colleague.elluciancloud.com"

class SouthSuburban(Colleague):
    id = "southsuburban"; name = "South Suburban College"
    example = "MTH 093"; host = "ssc-ss.colleague.elluciancloud.com"

class Parkland(Colleague):
    id = "parkland"; name = "Parkland College"
    example = "ENG 102"; host = "parkland-ss.colleague.elluciancloud.com"

class IowaWestern(Colleague):
    id = "iowawestern"; name = "Iowa Western Community College"
    example = "MAT 743"; host = "iwcc-ss.colleague.elluciancloud.com"

class Kaskaskia(Colleague):
    id = "kaskaskia"; name = "Kaskaskia College"
    example = "ENGL 101"; host = "kaskaskia-ss.colleague.elluciancloud.com"

class Muskegon(Colleague):
    id = "muskegon"; name = "Muskegon Community College"
    example = "ENG 101"; host = "muskegoncc-ss.colleague.elluciancloud.com"

class Kishwaukee(Colleague):
    id = "kishwaukee"; name = "Kishwaukee College"
    example = "MAT 045"; host = "kish-ss.colleague.elluciancloud.com"

class OaklandCC(Colleague):
    id = "oaklandcc"; name = "Oakland Community College"
    example = "MAT 1125"; host = "oaklandcc-ss.colleague.elluciancloud.com"

class KCKCC(Colleague):
    id = "kckcc"; name = "Kansas City Kansas Community College"
    example = "ENGL 0102"; host = "kckcc-ss.colleague.elluciancloud.com"

class Allegany(Colleague):
    id = "allegany"; name = "Allegany College of Maryland"
    example = "MATH 105"; host = "allegany-ss.colleague.elluciancloud.com"

class MiddlesexNJ(Colleague):
    id = "middlesexnj"; name = "Middlesex College (NJ)"
    example = "ENG 234"; host = "middlesexcollege-ss.colleague.elluciancloud.com"

class IndependenceCC(Colleague):
    id = "indycc"; name = "Independence Community College"
    example = "MAT 1123"; host = "indycc-ss.colleague.elluciancloud.com"

class UCNJ(Colleague):
    id = "ucnj"; name = "UCNJ Union College of Union County"
    example = "BIOL 101"; host = "ucc-ss.colleague.elluciancloud.com"

class Brookdale(Colleague):
    id = "brookdale"; name = "Brookdale Community College"
    example = "ENGL 122"; host = "brookdalecc-ss.colleague.elluciancloud.com"

class WesternTexas(Colleague):
    id = "westerntexas"; name = "Western Texas College"
    example = "ENGL 1302"; host = "wtc-ss.colleague.elluciancloud.com"

class MassArt(Colleague):
    # base Colleague (older /PostSearchCriteria + textual AvailabilityStatus), NOT the
    # numeric NewColleague/SearchAsync variant (that route 404s here). CDAN 300 = 2 sec
    # 1 open/1 full, CDAN 303 = full — real mix, textual 'Open' only.
    id = "massart"; name = "Massachusetts College of Art and Design"
    example = "CDAN 300"; host = "mca-ss.colleague.elluciancloud.com"

class WakeTech(Colleague):
    # ~72k, one of the largest CCs in the US. ENG 111 = 196 sec 54 open/142 waitlisted;
    # base textual-Open rule correctly withholds a waitlisted section that still has a seat.
    id = "waketech"; name = "Wake Technical Community College"
    example = "ENG 111"; host = "selfserve.waketech.edu"

class Schoolcraft(Colleague):
    id = "schoolcraft"; name = "Schoolcraft College"
    example = "ENG 101"; host = "self-service.schoolcraft.edu"

class CentralCarolinaCC(Colleague):
    id = "centralcarolinacc"; name = "Central Carolina Community College"
    example = "ENG 111"; host = "ss-prod.cloud.cccc.edu"

class BrunswickCC(Colleague):
    id = "brunswickcc"; name = "Brunswick Community College"
    example = "ENG 111"; host = "ss2-prod-cloud.brunswickcc.edu"

class CollegeOfDuPage(Colleague):
    id = "cod"; name = "College of DuPage"
    example = "ENGLI 1101"; host = "selfserv.cod.edu"

class SouthwesternCA(Colleague):
    id = "swccd"; name = "Southwestern College (CA)"
    example = "ENGL C1000"; host = "collselfserv.swccd.edu"

class VictorValley(Colleague):
    # salvaged onto the elluciancloud host (old IPEDS host fetched empty — excluded then).
    id = "victorvalley"; name = "Victor Valley College"
    example = "ENGL C1000"; host = "vvc-ss.colleague.elluciancloud.com"

class Elgin(Colleague):
    id = "elgin"; name = "Elgin Community College"
    example = "ENG 101"; host = "selfservice.elgin.edu:8173"   # non-standard port

class Kellogg(Colleague):
    id = "kellogg"; name = "Kellogg Community College"
    example = "ENGL 151"; host = "portal.kellogg.edu"

class Coalinga(Colleague):
    id = "coalinga"; name = "Coalinga College"
    example = "ENGL C1000"; host = "ellucianssui.whccd.edu"

class SantaAna(Colleague):
    # Rancho Santiago CCD shared host — SAC model + SAC section rows only.
    id = "santaana"; name = "Santa Ana College"
    example = "ENGL C1000"; host = "colss-prod.cloud.rsccd.edu"; campus = "SAC"

class SantiagoCanyon(Colleague):
    id = "santiagocanyon"; name = "Santiago Canyon College"
    example = "ENGL C1000"; host = "colss-prod.cloud.rsccd.edu"; campus = "SCC"

class IndianHills(ShortYearTermColleague):
    id = "indianhills"; name = "Indian Hills Community College"
    example = "HCM 261"; host = "ss.indianhills.edu"

class SouthPiedmont(CodedTermColleague):
    id = "spcc"; name = "South Piedmont Community College"
    example = "BUS 121"; host = "selfservice.spcc.edu"

class Robeson(CodedTermColleague):
    id = "robeson"; name = "Robeson Community College"
    example = "MAT 045P"; host = "selfservice.robeson.edu"

class FlorenceDarlington(ShortYearTermColleague):
    id = "fdtc"; name = "Florence-Darlington Technical College"
    example = "ENG 101"; host = "selfservice.fdtc.edu"

class WesternTC(NumSubjColleague):
    id = "westerntc"; name = "Western Technical College (WI)"
    example = "804 123"; host = "westerntc-ss.colleague.elluciancloud.com"

class Nicolet(NumSubjColleague):
    id = "nicolet"; name = "Nicolet Area Technical College"
    example = "316 115"; host = "nicoletcollege-ss.colleague.elluciancloud.com"

# July 8 batch 7 — the two clean Banner 4-years. The classic-PeopleSoft
# (COMMUNITY_ACCESS.CLASS_SEARCH.GBL) flagship segment (Penn State/UCF/Houston/UConn/
# NAU/...) was investigated and SCRAPPED: NAU's guest view shows every section 'Open'
# even in a COMPLETED term (121/121 English sections Open in Fall 2025) — the guest
# status icon is NOT real availability, so it would false-alert on everything. The
# component is also not uniform across schools (subject field suffix varies $0 vs $1,
# per-school node/inst/strm), so it isn't a single-adapter win. Do not build without
# first proving a school's guest status reflects reality (completed-term closed-section
# test). See research/README.md.
class Winthrop(Banner):
    id = "winthrop"; name = "Winthrop University"
    example = "ACAD 101"; host = "prod-ssb.winthrop.edu"; term = "202680"

class Guilford(Banner):
    id = "guilford"; name = "Guilford College"
    example = "ENGL 101"; host = "ssbp.guilford.edu"; term = "202630"

class UNCG(Banner):
    id = "uncg"; name = "University of North Carolina at Greensboro"
    example = "BIO 111"; host = "erp-registration.uncg.edu"; term = "202608"

class Otis(Banner):
    id = "otis"; name = "Otis College of Art and Design"
    example = "ENGL 108"; host = "ssb1.otis.edu"; term = "202630"

class SCF(Banner):
    # CT-log discovery: non-guessable host no pattern sweep could hit. Florida
    # English = ENC. Live gate: ENC 1101 = 82 sec with 58 Act==Cap FULL rows.
    id = "scf"; name = "State College of Florida, Manatee-Sarasota"
    example = "ENC 1101"; host = "banner.banprod.scf.edu"; term = "202710"


# NOTE: OhioState() is now LIVE (#13, ~61k students). The earlier "throttling" was a
# TESTING artifact from aggressive concurrent probing — under gentle production polling
# (1 call/watched-course/cycle) it's rock-stable: verified 10/10 identical section
# counts, and enrollmentStatus varies reliably (1081 Open / 319 Closed across popular
# courses). Status-only (seats=None), open = enrollmentStatus=="Open". Fixed the stale
# section-field name ('number' -> 'section') that had left it returning 0 sections.
# Loyola Marymount (bannerxe.lmu.edu) tested but CUT — host times out repeatedly.
# Drake (registrationssb.drake.edu) tested but CUT — every fetch takes ~137s (host
# throttles or cold-starts per session); would stall a poller worker each cycle.
# Drexel(): class works (base_path="registration"), but the only published 2026 term
# is the medicine/professional SEMESTER calendar — no undergrad quarter (CS) courses
# yet. PARKED until Drexel's quarter terms publish; re-add to the list to enable.
_CUNY_MAPS = {
    "BAR01": {"AAS":"ASAM", "ACC":"ACCT", "AMS":"AMST", "ANT":"ANTH", "ARB":"ARAB", "ART":"ARTX", "BIO":"BIOL", "BLS":"BLST", "BUS":"BUAD", "CHI":"CHIN", "CHM":"CHEM", "CIS":"CMIS", "CMP":"COLI", "COM":"COMM", "COOP":"COOP", "ECO":"ECON", "ENG":"ENGL", "ENT":"ENTR", "ENV":"EVSC", "FIN":"FINA", "FLM":"FILM", "FPA":"ARFP", "FRE":"FREN", "FYS":"FROR", "HIS":"HIST", "IBS":"BUIT", "IDC":"INTE", "INS":"INSU", "ITL":"ITAL", "JPN":"JAPA", "JRN":"JOUR", "JWS":"JWST", "LACS":"LACS", "LAW":"LAW", "LIB":"LISC", "LTS":"LAST", "MAM":"MAOM", "MGT":"MANA", "MKT":"MARK", "MSC":"MUSI", "MTH":"MATH", "NMA":"ARNM", "OPM":"OPMA", "OPR":"OPRE", "PAF":"PUAF", "PHI":"PHIL", "PHY":"PHYS", "POL":"POSC", "POR":"PORT", "PSY":"PSYC", "QNT":"QUME", "RES":"REES", "SOC":"SOCI", "SPA":"SPAN", "STA":"STAT", "TAX":"TAXA", "THE":"THEA", "TRA":"TROR", "WST":"WKST"},   # Baruch College
    "BMC01": {"ACC":"ACCT", "ACL":"ACLS", "AFL":"AFST", "AFN":"AFST", "ANI":"ANMG", "ANT":"ANTH", "ARB":"ARAB", "ART":"ARTX", "ASL":"ASLG", "ASN":"ASAM", "AST":"ASTR", "BIO":"BIOL", "BTE":"BIOT", "BUS":"BUSI", "CED":"EDCO", "CHE":"CHEM", "CHI":"CHIN", "CIS":"CMIS", "COM":"COMM", "CRJ":"CJST", "CRT":"CTTN", "CSC":"CMSC", "CYS":"EDCS", "ECE":"EDEC", "ECO":"ECON", "EDB":"EDBL", "EDS":"EDSE", "EDU":"EDUC", "EMC":"PARA", "ENG":"ENGL", "ESC":"ENSC", "ESL":"ENSL", "ETH":"ETHN", "FNB":"FINA", "FRN":"FREN", "FYE":"FROR", "GEO":"GEOG", "GIS":"GEIS", "GLS":"GLST", "GWS":"WGST", "HIS":"HIST", "HIT":"MDTC", "HSD":"HEST", "HTT":"TRTO", "HUM":"HUSE", "ITL":"ITAL", "LAT":"LAST", "LIN":"LING", "LPN":"NURS", "MAR":"MARK", "MAT":"MATH", "MEA":"MATC", "MES":"MATC", "MMA":"MMDE", "MMP":"MMDE", "MUS":"MUSI", "NUR":"NURS", "PAN":"PUNA", "PHI":"PHIL", "PHY":"PHYS", "POL":"POSC", "PRT":"PORT", "PSY":"PSYC", "RTT":"RETH", "SBE":"BUSE", "SCI":"SCIE", "SOC":"SOCI", "SPE":"SPEE", "SPN":"SPAN", "THE":"THEA", "TRS":"TRAS", "URB":"UBST", "VAT":"VATC", "WLI":"WOFL"},   # Borough of Manhattan CC
    "HTR01": {"ACC":"ACCT", "ACCP":"ACCT", "ACSK":"DESK", "ADSUP":"CUTE", "AFPRL":"APLS", "ANTH":"ANTH", "ANTHC":"ANTC", "ANTHP":"ANTP", "ARB":"ARAB", "ARTCR":"ARTC", "ARTED":"EDAR", "ARTH":"ARTH", "ARTLA":"ARTL", "ASIAN":"ASAM", "ASTRO":"ASTR", "BILED":"EDBL", "BIOCH":"BICH", "BIOL":"BISC", "BUS":"BUSI", "CEDC":"CUTE", "CEDF":"EDFO", "CHEM":"CHEM", "CHIN":"CHIN", "CHND":"EDCN", "CLA":"CCAR", "CLARC":"CCAR", "CLASS":"EDLE", "COCO":"COUN", "COMPL":"COLI", "COMSC":"COSC", "COUNM":"EDMH", "COUNR":"EDRC", "COUNS":"COUN", "CSCI":"CMSC", "DAN":"DANC", "DANED":"EDDA", "DYSLX":"EDSP", "ECC":"EDEC", "ECF":"EDFO", "ECO":"ECON", "EDABA":"EDAB", "EDDIL":"EDUC", "EDESL":"EDES", "EDF":"EDFO", "EDLIT":"EDLI", "EDPS":"EDFO", "EDUC":"CUTE", "ENGL":"ENGL", "FILM":"FILM", "FILMP":"FILM", "FILPL":"FILM", "FREN":"FREN", "FYS":"FROR", "GEOG":"GEOG", "GEOL":"GEOL", "GERMN":"GERM", "GRK":"GREK", "GSR":"GRSR", "GTECH":"GETE", "HEBR":"HEBR", "HED":"EDHP", "HIST":"HIST", "HMBIO":"HUBI", "HONS":"HONS", "HR":"HURI", "HUM":"HUMA", "IMA":"ARIM", "ITAL":"ITAL", "JPN":"JAPA", "JS":"JWST", "LACS":"LACS", "LAT":"LATI", "LATED":"EDLT", "LIBR":"LISC", "LING":"LING", "MATH":"MATH", "MEDIA":"MEST", "MEDP":"MEST", "MEDPL":"MEST", "MLS":"MELS", "MLSP":"MELS", "MUS":"MUSI", "MUSED":"MUSI", "MUSHL":"MUSI", "MUSIN":"MUSI", "MUSPF":"MUSI", "MUSTH":"MUSI", "NFS":"NUFS", "NURS":"NURS", "NUTR":"NUTR", "PERM":"PERM", "PGEOG":"GEGE", "PH":"PUHE", "PHILO":"PHIL", "PHYS":"PHYS", "POL":"POLI", "POLSC":"POSC", "PORT":"PORT", "PSYCH":"PSYC", "PT":"PHTH", "PUPOL":"PUPO", "QSTA":"CUTE", "QSTAP":"CUTE", "QSTB":"EDFO", "QSTP":"EDFO", "RAS":"RUAS", "REL":"RELI", "RUSS":"RUSS", "SEDC":"CUTE", "SEDCP":"EDUC", "SEDF":"EDFO", "SOC":"SOCI", "SPAN":"SPAN", "SPED":"EDSP", "SPEDE":"EDEC", "SSW":"SCSW", "STABD":"STAB", "STAT":"STAT", "SW":"SOWO", "THC":"THEA", "THEA":"THEA", "TRN":"TRAS", "TRNC":"CHIN", "TRNS":"SPAN", "UKR":"UKRA", "URBG":"UBAF", "URBP":"UBPL", "URBS":"UBST", "WGS":"WGST", "WGSA":"WGST", "WGSC":"WGST", "WGSI":"WGST", "WGSL":"WGST", "WGSP":"WGST", "WGSS":"WGST", "WGST":"WGST"},   # Hunter College
    "QNS01": {"ACCT":"ACCT", "AFST":"AFST", "ANTH":"ANTH", "ARAB":"ARAB", "ARTH":"ARTH", "ARTS":"ARTS", "ASTR":"ASTR", "BALA":"BULA", "BIOL":"BIOL", "BUS":"BUSI", "CHEM":"CHEM", "CHIN":"CHIN", "CLAS":"CLAS", "CMLIT":"COLI", "COOP":"EDCO", "CSCI":"CMSC", "DANCE":"DANC", "DATA":"DAAN", "DESN":"DESI", "DRAM":"DRAT", "EAST":"EAST", "ECON":"ECON", "ECPCE":"CUED", "ECPEL":"EDIL", "ECPSE":"SPED", "ECPSP":"SCPS", "EECE":"EECE", "ENGL":"ENGL", "ENSCI":"EVSC", "EURO":"EURO", "FASH":"FASH", "FNES":"FNES", "FREN":"FREN", "GEOL":"GEOL", "GERM":"GERM", "GRKMD":"GRKM", "GRKST":"BMGS", "HEBRW":"HEBR", "HIST":"HIST", "HMNS":"INTE", "HNRS":"INTE", "HSS":"INTE", "HTH":"INTE", "INFO":"LISC", "ITAL":"ITAL", "ITAST":"IAST", "JAZZ":"JAZZ", "JEWST":"JWST", "JOURN":"MEST", "JPNS":"JAPA", "KOR":"KORE", "LABST":"LBST", "LALS":"LAST", "LATIN":"LATI", "LCD":"LING", "LIBR":"LIBR", "MATH":"MATH", "MEDST":"MEST", "MES":"MEAS", "MUSIC":"MUSI", "PHIL":"PHIL", "PHOTO":"PHOT", "PHYS":"PHYS", "PORT":"PORT", "PSCI":"POSC", "PSYCH":"PSYC", "QNS":"FROR", "RLGST":"RELI", "RM":"ECON", "RUSS":"RUSS", "SEEK":"SEEK", "SEYS":"EDSE", "SOC":"SOCI", "SPAN":"SPAN", "SPST":"INTE", "URBST":"UBST", "WGS":"WGST"},   # Queens College
    "BCC01": {"ACC":"ACCT", "ACM":"ANCM", "ACS":"AUTE", "ANT":"ANTH", "ARB":"ARAB", "ART":"ARTX", "AST":"ASTR", "BIO":"BIOL", "BIS":"BUIS", "BUS":"BUSI", "CHM":"CHEM", "CLE":"EDCI", "COM":"BUCO", "COMM":"COMM", "CPR":"CPR", "CRJ":"CJST", "CSI":"CMSC", "CSN":"CYNE", "CWE":"EDCO", "DAT":"DAPR", "ECO":"ECON", "EDU":"EDUC", "EGR":"EGNG", "ELC":"ELTE", "ENG":"ENGL", "ENV":"EVSC", "ESE":"EASC", "ESL":"ENSL", "EXS":"EXSC", "FILM":"FILM", "FIN":"FINA", "FRN":"FREN", "FYS":"FROR", "GEO":"GEOG", "GIS":"EVSC", "HCM":"HECM", "HIS":"HIST", "HLT":"HLED", "HSC":"HUSE", "ITL":"ITAL", "JPN":"JAPA", "KEY":"OFTC", "LAW":"LAW", "MED":"MEOF", "MEDP":"METC", "MEST":"MEST", "MKT":"MARK", "MLT":"MDLT", "MTH":"MATH", "MUS":"MUSI", "NMT":"MDCN", "NUR":"NURS", "PEA":"PHED", "PHL":"PHIL", "PHM":"NURS", "PHY":"PHYS", "PLB":"PHLE", "POL":"POSC", "POR":"PORT", "PSY":"PSYC", "RAD":"RATE", "REC":"TPRE", "SEC":"MDTC", "SOC":"SOCI", "SPN":"SPAN", "THEA":"THEA"},   # Bronx Community College (CUNY)
    "CSI01": {"AAD":"AFST", "ACC":"ACCT", "AMS":"AMST", "ANT":"ANTH", "ARB":"ARAB", "ART":"ARTX", "ASD":"AUSD", "ASL":"ASLG", "AST":"ASTR", "BDA":"BUDA", "BIO":"BIOL", "BUS":"BUSI", "CHM":"CHEM", "CHN":"CHIN", "CIN":"CIST", "COM":"COMM", "COR":"CORE", "CSC":"CMSC", "DAN":"DANC", "DED":"COBL", "DRA":"ARDR", "ECO":"ECON", "EDA":"EDSU", "EDC":"EDEM", "EDD":"EDUC", "EDE":"EDEM", "EDL":"EDET", "EDP":"EDSP", "EDS":"EDSE", "ELE":"EGEL", "ENG":"ENGL", "ENGR":"ENGR", "ENH":"ENGL", "ENL":"ENGL", "ENS":"ENSC", "ESC":"EVSC", "EWR":"ENGL", "FNC":"FINA", "FRN":"FREN", "GEG":"GEOG", "GEO":"GEOL", "HON":"HONS", "HST":"HIST", "INT":"INST", "ISI":"INSI", "ITL":"ITAL", "LACL":"LACS", "LBS":"LIST", "LIB":"LIBT", "LING":"LING", "LNG":"LANG", "MAM":"MAOM", "MGT":"MANA", "MKT":"MARK", "MLS":"MELS", "MTH":"MATH", "MUS":"MUSI", "MUSP":"MUSP", "NRS":"NURS", "NSM":"NEUR", "PHL":"PHIL", "PHO":"PHOT", "PHT":"PHTH", "PHY":"PHYS", "POL":"POSC", "PSY":"PSYC", "SKO":"SEEK", "SLS":"SCIE", "SOC":"SOCI", "SPD":"STDV", "SPN":"SPAN", "SWK":"SOWO", "WGS":"GWSS"},   # College of Staten Island (CUNY)
    "CTY01": {"ANTH":"ANTH", "ARAB":"ARAB", "ARCH":"ARCH", "ART":"ARTX", "ASIA":"ASAM", "ASTR":"ASTR", "BIO":"BIOL", "BLST":"BLST", "BME":"EGBI", "CE":"EGCI", "CHE":"EGCH", "CHEM":"CHEM", "CHIN":"CHIN", "CL":"COLI", "CSC":"CMSC", "EAS":"EASC", "EASE":"EDEE", "ECO":"ECON", "EDCE":"EDCH", "EDLS":"EDLE", "EDSE":"EDSE", "EDUC":"EDUC", "EE":"EGEL", "ENGL":"ENGL", "ENGR":"EGNG", "ESL":"ENSL", "FIQWS":"FROR", "FREN":"FREN", "GAME":"GAME", "HEB":"HEBR", "HIST":"HIST", "HUM":"HUMA", "IAS":"INTE", "INTL":"INST", "ITAL":"ITAL", "JAP":"JAPA", "JWST":"JWST", "LAAR":"ARCL", "LALS":"LAST", "LAT":"LATI", "MAM":"MAOM", "MATH":"MATH", "MATHE":"EDMA", "MCA":"MEDI", "ME":"EGME", "MED":"EDBM", "MHC":"HONS", "MSCI":"MILI", "MUS":"MUSI", "NSS":"FROR", "PHIL":"PHIL", "PHYS":"PHYS", "PHYSE":"PHED", "PORT":"PORT", "PSC":"POSC", "PSY":"PSYC", "SCI":"SCIE", "SCIE":"EDSC", "SOC":"SOCI", "SPAN":"SPAN", "SPANE":"EDSA", "SPCH":"SPEE", "SPED":"EDSP", "SSC":"SOSC", "STABD":"STAB", "SUS":"SUST", "THTR":"THEA", "UD":"UBST", "URB":"UBST", "USSO":"HIST", "WHUM":"WOHU", "WS":"WOST"},   # City College (CUNY)
    "NCC01": {"ACCT":"ACCT", "AMST":"AMST", "ANTH":"ANTH", "ART":"ARTX", "BIOL":"BIOL", "BUSI":"BUSI", "CHEM":"CHEM", "COMM":"COMM", "CSM":"STRM", "ECON":"ECON", "EDUC":"EDUC", "ENGL":"ENGL", "FYS":"FRSE", "GOVT":"GOVT", "HIST":"HIST", "HITE":"HITE", "HONR":"HONR", "HSVC":"HUSE", "INFT":"CMIS", "LASC":"LIAS", "MATH":"MATH", "PHIL":"PHIL", "PHYS":"PHYS", "PSYC":"PSYC", "SOCI":"SOCI", "SOSC":"SOSC", "UBST":"UBST"},   # Guttman Community College (CUNY)
    "HOS01": {"ACC":"ACCT", "ANTH":"ANTH", "BIO":"BIOL", "BLS":"BLST", "BUS":"BUSI", "CAP":"CAPS", "CHE":"CHEM", "CIS":"CMIS", "CJ":"CJST", "COM":"COMM", "COOP":"COOP", "CSC":"CMSC", "CSE":"STRE", "DD":"DIDE", "DM":"MUDI", "ECO":"ECON", "EDU":"EDUC", "ENG":"ENGL", "ENGR":"EGNG", "ENV":"EVSC", "ESL":"ENSL", "FRE":"FREN", "FYS":"GEST", "GD":"GADE", "GERO":"GERO", "HIS":"HIST", "HLT":"EDHE", "HUM":"HUMA", "ITA":"ITAL", "JPN":"JAPA", "LAC":"LACS", "LAW":"LAW", "LEG":"PAST", "LIN":"LING", "MAT":"MATH", "MTS":"STRM", "MUS":"MUSI", "NUR":"NURS", "OT":"OFTC", "PED":"PHED", "PHY":"PHYS", "POL":"POSC", "PPA":"PUAD", "PSY":"PSYC", "SCI":"SCIE", "SOC":"SOCI", "SPA":"SPAN", "SW":"SOWO", "VPA":"ARVP", "WGS":"WGST", "XRA":"RATE"},   # Hostos Community College (CUNY)
    "KCC01": {"ACC":"ACCT", "ANT":"ANTH", "ARB":"ARAB", "ART":"ARTX", "BA":"BUAD", "BF":"BUFA", "BIO":"BIOL", "CA":"ARCU", "CHI":"CHIN", "CHM":"CHEM", "CIS":"CMIS", "COH":"COHE", "CP":"CMPR", "CRJ":"CJST", "CS":"CMSC", "ECO":"ECON", "EDC":"EDEC", "EGR":"ENSC", "EMS":"EMMS", "ENG":"ENGL", "EPS":"EASC", "ESL":"ENSL", "EXS":"EXSC", "FD":"FADE", "FR":"FREN", "HE":"EDHE", "HEB":"HEBR", "HIS":"HIST", "HPE":"EDHP", "HS":"HESC", "IT":"ITAL", "JRL":"JOUR", "MAT":"MATH", "MCB":"COMM", "MCF":"FILM", "MCM":"MEDI", "MH":"MEHE", "MT":"MATE", "MUS":"MUSI", "NUR":"NURS", "PEC":"PHED", "PEM":"PHED", "PEW":"PHED", "PHI":"PHIL", "PHY":"PHYS", "POL":"POSC", "PSG":"POTE", "PSY":"PSYC", "PTA":"PHTA", "RPE":"EDRP", "SAC":"COUN", "SCI":"SCIE", "SD":"STDV", "SOC":"SOCI", "SPA":"SPAN", "SPE":"SPEE", "ST":"SUTE", "TAH":"TOHO", "THA":"THEA"},   # Kingsborough Community College (CUNY)
    "JJC01": {"ACC":"ACCT", "AFR":"AFST", "ANT":"ANTH", "ARA":"ARAB", "ART":"ARTX", "AST":"ASAM", "BIO":"BIOL", "CHE":"CHEM", "CHI":"CHIN", "CHS":"COHS", "CJBA":"CJST", "CJBS":"CJST", "CJM":"CJMA", "COM":"COMM", "COR":"COAD", "CRJ":"CJST", "CSCI":"CMSC", "CSL":"COUN", "DRA":"DRAM", "ECO":"ECON", "EDU":"EDUC", "EJS":"EVJS", "ENG":"ENGL", "ESA":"EMSA", "FCM":"CMFO", "FIS":"FISC", "FOS":"FOSC", "FRE":"FREN", "GEN":"GNST", "GER":"GERM", "HIS":"HIST", "HJS":"HUJU", "HON":"HONS", "HR":"HURI", "HUM":"HUMA", "ICJ":"CRIN", "ISP":"INTE", "ITA":"ITAL", "JPN":"JAPA", "LAW":"LAW", "LIT":"LITE", "LLS":"LAST", "LWS":"LAWS", "MAT":"MATH", "MHC":"MAHC", "MUS":"MUSI", "PAD":"PUAD", "PED":"PHED", "PHI":"PHIL", "PHY":"PHYS", "PMT":"PRMA", "POL":"POSC", "PSC":"POLS", "PSY":"PSYC", "REL":"RELI", "SCI":"SCIE", "SEC":"SECU", "SEI":"SOEI", "SOC":"SOCI", "SPA":"SPAN", "SSC":"SOSR", "STA":"STAT", "TOX":"TOXI", "UGR":"UNST"},   # John Jay College (CUNY)
    "LAG01": {"BTA":"ACCT", "BTC":"CMSC", "BTF":"BUSI", "BTI":"BUIN", "BTM":"MAST", "BTO":"OFTC", "BTP":"PAST", "BTT":"TRTO", "CJF":"SOSC", "CMF":"COST", "CSE":"COMM", "CSF":"FRSE", "ECF":"MATH", "EDF":"EDLA", "EIS":"EDLA", "ELA":"ARAB", "ELC":"CHIN", "ELE":"EDUC", "ELF":"FREN", "ELI":"ITAL", "ELJ":"JAPA", "ELK":"KORE", "ELL":"EDLA", "ELM":"ASLG", "ELN":"UBST", "ELS":"SPAN", "ELZ":"PORT", "ENA":"ENGL", "ENF":"ENGL", "ENG":"ENGL", "ENN":"ENGL", "ESA":"ENSL", "ESL":"ENSL", "FAF":"ARTX", "FSG":"STDV", "HAF":"THEA", "HPF":"FROR", "HSF":"HESC", "HSS":"HUSE", "HTR":"RECR", "HUA":"ARTX", "HUC":"COST", "HUI":"INDT", "HUM":"MUSI", "HUN":"INTE", "HUP":"PHIL", "HUT":"THEA", "HUV":"FITV", "HUW":"NEME", "HUX":"MUSR", "HUZ":"PHOT", "IDF":"FROR", "LIB":"LIAR", "LIF":"FROR", "LIN":"HEHU", "LMF":"FROR", "LRC":"LISC", "MAC":"MATH", "MAE":"MATH", "MAT":"MATH", "MRF":"FROR", "NSF":"BUSI", "REG":"STHR", "SCB":"BIOL", "SCC":"CHEM", "SCD":"DIET", "SCE":"PARA", "SCG":"EVST", "SCH":"INTE", "SCL":"NURS", "SCN":"UBST", "SCO":"OCTH", "SCP":"SCIE", "SCR":"NURS", "SCT":"PHTH", "SCV":"VETE", "SCX":"RATE", "SGN":"UBST", "SSA":"SOSC", "SSE":"SOSC", "SSH":"SOSC", "SSI":"SOSC", "SSJ":"SOSC", "SSN":"SOSC", "SSP":"SOSC", "SSS":"SOCI", "SSY":"PSYC", "SYF":"SOSC"},   # LaGuardia Community College (CUNY)
    "MEC01": {"ACCT":"ACCT", "AGRO":"COUN", "ANTH":"ANTH", "ART":"ARTX", "BIO":"BIOL", "BIOL":"BIOL", "BUS":"BUSI", "CHM":"CHEM", "CHML":"CHEM", "CIS":"CMIS", "CS":"CMSC", "ECON":"ECON", "EDUC":"EDUC", "ENGL":"ENGL", "ENTE":"ENTR", "ENVS":"EVSC", "FIN":"FINA", "FREL":"FREN", "FREN":"FREN", "FS":"FROR", "GEOG":"GEOG", "HACR":"HACR", "HIST":"HIST", "HSC":"HESC", "LAW":"LAW", "LIB":"LISC", "MAN":"MANA", "MAR":"MARK", "MASS":"MACO", "MED":"MEDI", "MPA":"MEPA", "MTH":"MATH", "MUS":"MUSI", "NUR":"NURS", "NURC":"NURC", "NURL":"NURS", "NURS":"NURS", "PA":"PUAD", "PERM":"PERM", "PHIL":"PHIL", "PHS":"PHSC", "PHY":"PHYS", "PHYL":"PHYS", "PHYW":"PHYS", "POL":"POSC", "PSYC":"PSYC", "REL":"RELI", "SOC":"SOCI", "SPAL":"SPAN", "SPAN":"SPAN", "SPC":"SEEK", "SPCH":"SPEE", "SSC":"SOSC", "SW":"SOWO"},   # Medgar Evers College (CUNY)
    "LEH01": {"AAS":"AFST", "ACC":"ACCT", "ACU":"ANCU", "AMS":"AMST", "ANT":"ANTH", "ARB":"ARAB", "ARH":"ARTH", "ART":"ARTX", "AST":"ASTR", "BBA":"BUAD", "BIO":"BIOL", "CED":"ECON", "CGI":"CMGI", "CHE":"CHEM", "CHI":"CHIN", "CIS":"CMIS", "CMP":"CMSC", "DEC":"EDCH", "DFN":"DIET", "DNC":"DANC", "DST":"DISB", "EBS":"EDBL", "ECE":"EDEC", "ECO":"ECON", "EDC":"EDEC", "EDE":"EDEC", "EDG":"EDCU", "EDL":"EDLE", "EDR":"EDRE", "EDS":"EDSP", "ENG":"ENGL", "ENRT":"MAEN", "ENV":"EVSC", "ENW":"ENGL", "ESC":"EDMI", "EXS":"EXSC", "FRE":"FREN", "FTS":"FILM", "GEH":"GEOG", "GEO":"GEOL", "GEP":"GEOP", "HEA":"HESC", "HIA":"HISA", "HIE":"HISE", "HIN":"NURS", "HIS":"HIST", "HIU":"HISU", "HIW":"HISW", "HSA":"HESA", "HSD":"HESC", "HUM":"HUMA", "IBA":"IBAP", "IDW":"WOCL", "IRI":"IRIS", "ITA":"ITAL", "JAL":"LANG", "JRN":"JOUR", "LAC":"LACS", "LEH":"GEST", "LNG":"LING", "LSP":"LESP", "LTS":"LACS", "MAT":"MATH", "MCS":"MECO", "MES":"MEAS", "MHC":"MAHC", "MLS":"INTE", "MSB":"BUSI", "MSH":"MUSI", "MSP":"MUSI", "MST":"MUSI", "NSS":"NASS", "NUR":"NURS", "PHI":"PHIL", "PHY":"PHYS", "POL":"POSC", "PSY":"PSYC", "REC":"RECR", "REH":"REHA", "REL":"RELI", "SOC":"SOCI", "SPA":"SPAN", "SPE":"SPET", "SPS":"INTE", "SPV":"SPEV", "SWK":"SOWO", "THE":"THEA", "THR":"TPRE", "WFL":"WOFL", "WST":"WOST"},   # Lehman College (CUNY)
    "NYT01": {"AAA":"INCL", "ACC":"ACCT", "AFR":"AFAS", "ANTH":"ANTH", "ARB":"ARAB", "ARCH":"ARCT", "ARTH":"ARTH", "BIO":"BISC", "BUF":"BUTF", "BUS":"BUSI", "CET":"EGCT", "CHEM":"CHEM", "CHN":"CHIN", "CMCE":"COTE", "COM":"COMM", "COMD":"CODE", "CST":"CMST", "DEN":"DEHY", "ECON":"ECON", "EDU":"EDTC", "EET":"ELET", "ENG":"ENGL", "ENT":"ENTM", "ENVC":"EVCT", "ESCI":"EVSC", "ESOL":"ENSL", "FMGT":"FAMA", "FREN":"FREN", "GEOG":"GEOG", "GOV":"GOVT", "HEA":"HLED", "HIS":"HIST", "HMGT":"HOMA", "HSA":"HESA", "HSCI":"HESC", "HUS":"HUSE", "IND":"INDT", "LATS":"LAST", "LAW":"LAWP", "LNG":"LANG", "MAT":"MATH", "MECH":"EGMT", "MEDU":"MAED", "MKT":"MARK", "MM":"MAOM", "MTEC":"EMMT", "MUS":"MUSI", "NUR":"NURS", "PERF":"PERF", "PHIL":"PHIL", "PHYS":"PHYS", "PSY":"PSYC", "RAD":"RATE", "RESD":"REDE", "SBS":"SOBS", "SET":"SETE", "SOC":"SOCI", "SPA":"SPAN", "TCET":"TELE", "THE":"THEA", "VCT":"OPTH", "WKSHP":"WORK"},   # NYC College of Technology (CUNY)
    "QCC01": {"ANTH":"ANTH", "ARCH":"ARCH", "ARTH":"ARTH", "ARTS":"ARTS", "BE":"DESK", "BI":"BIOL", "BU":"BUSI", "CD":"CODI", "CH":"CHEM", "CIS":"CMIS", "CN":"CNOW", "CRIM":"CJST", "CS":"CMSC", "CST":"STRT", "DAN":"DANC", "ECON":"ECON", "EDUC":"EDUC", "EE":"EGEL", "ENGL":"ENGL", "ET":"EGEC", "FMP":"MEDI", "GE":"GEOL", "HA":"MSTH", "HE":"EDHE", "HIST":"HIST", "IS":"INTE", "LA":"ARAB", "LC":"CHIN", "LF":"FREN", "LI":"ITAL", "LS":"SPAN", "MA":"MATH", "MP":"MUSI", "MT":"EGMT", "MUS":"MUSI", "NU":"NURS", "PE":"PHED", "PH":"PHYS", "PHIL":"PHIL", "PLSC":"POSC", "PSYC":"PSYC", "RAD":"RASA", "SOCY":"SOCI", "SP":"SPEC", "ST":"STAF", "TECH":"TECH", "TH":"THEA", "UBST":"UBST"},   # Queensborough Community College (CUNY)
    "YRK01": {"AC":"DESK", "ACC":"ACCT", "ANTH":"ANTH", "ARAB":"ARAB", "ASTR":"ASTR", "AVIA":"AVMA", "BENG":"BENG", "BIO":"BIOL", "BLST":"BLST", "BTEC":"BIOT", "BUS":"BUAD", "CHEM":"CHEM", "CHIN":"CHIN", "CLDV":"CUDI", "CLS":"CLLS", "CRE":"CREO", "CS":"CMSC", "CT":"COMT", "CTM":"CLTM", "ECON":"ECON", "EDUC":"EDUC", "EHS":"EVHC", "ENG":"ENGL", "ESL":"ENSL", "FA":"ARFI", "FINC":"FINA", "FREN":"FREN", "GEOL":"GEOL", "GERO":"GESS", "HE":"HLED", "HIST":"HIST", "HPGC":"HPGC", "HPPA":"PHAS", "HS":"HESC", "HUM":"HUMA", "IS":"INTE", "ITAL":"ITAL", "JOUR":"JOUR", "MATH":"MATH", "MKT":"MARK", "MS":"MOSC", "MSCI":"MILI", "MUS":"MUSI", "NURS":"NURS", "OT":"OCTH", "PE":"PHED", "PH":"PUHE", "PHIL":"PHIL", "PHS":"PMSC", "PHYS":"PHYS", "POL":"POSC", "PRST":"PRST", "PSY":"PSYC", "SCWK":"SOWO", "SD":"STDV", "SKCS":"SEEK", "SOC":"SOCI", "SPAN":"SPAN", "SPCH":"SPEC", "TA":"THAR", "WLIT":"WOLI", "WRIT":"WRIT"},   # York College (CUNY)
    "SPS01": {"AMER":"AMST", "ANTH":"ANTH", "AST":"ASTR", "BIO":"BIOL", "BUS":"BUSI", "CHEM":"CHEM", "CIS":"CMLI", "CM":"COMM", "COM":"DILI", "DATA":"DANA", "DSAB":"DISB", "DSSV":"DISB", "ECE":"EDEC", "ECO":"ECON", "EDUC":"ECED", "ENG":"ENGL", "GAI":"GEAI", "GEOG":"GEOG", "HESA":"HESA", "HIM":"HEIM", "HIST":"HIST", "HRL":"HURE", "ILAW":"LAWI", "INT":"SOSC", "IS":"DANA", "LANG":"LNST", "LAS":"LAST", "LBL":"LIST", "MATH":"MATH", "MGMT":"MANA", "MST":"MSST", "NURS":"NURS", "ORGD":"MAST", "PHE":"PUHE", "PHIL":"PHIL", "PLA":"INTE", "PROM":"MANA", "PSY":"PSYC", "QUAN":"INTE", "RAC":"RESE", "RM":"RSMT", "SOC":"SOCI", "SPAN":"SPAN", "YS":"YOST"},   # CUNY School of Professional Studies
    "BKL01": {"ACCT":"ACCT", "AFST":"AFST", "AMST":"AMST", "ANTH":"ANTH", "ARAB":"ARAB", "ARTD":"ARTX", "AUDI":"AUDI", "BIOL":"BIOL", "BUSN":"BUMA", "CASD":"CASD", "CAST":"CAST", "CBSE":"CBSE", "CHEM":"CHEM", "CHIN":"CHIN", "CHST":"EDCS", "CISC":"CMIS", "CLAS":"CLAS", "CMLT":"COLI", "COMM":"COMM", "CREO":"CREO", "ECAE":"ECAE", "ECON":"ECON", "EESC":"EESC", "ENGL":"ENGL", "ESLR":"ENSL", "FGSC":"FILM", "FILM":"FILM", "FINC":"FINA", "FREN":"FREN", "GLLC":"MODL", "GRKC":"GRKA", "GSCI":"GSCI", "HEBR":"HEBR", "HIST":"HIST", "HNSC":"HENS", "INDS":"INTE", "JAPN":"JAPA", "JUST":"JUST", "KORE":"KORE", "LATN":"LATI", "LING":"LING", "MAM":"MAOM", "MATH":"MATH", "MCHC":"HONS", "MUSC":"MUSI", "MVMT":"MVMT", "NEUR":"NEUR", "PERM":"PERM", "PHIL":"PHIL", "PHYS":"PHYS", "PIMA":"PIMA", "POLS":"POSC", "PRLS":"PRLS", "PSYC":"PSYC", "RELG":"RELG", "RUSS":"RUSS", "SEED":"SCED", "SOCY":"SOCI", "SPAN":"SPAN", "SPCL":"SPCL", "SUST":"SUST", "THEA":"THEA", "TREM":"TREM", "WGST":"WGST"},   # Brooklyn College (CUNY)
}


# ===========================================================================
class VCCS:
    """Virginia Community College System: ONE shared PeopleSoft guest class search
    (ps-sis.vccs.edu, S92GUEST site, NO login) serves all 23 Virginia community
    colleges, isolated by institution code.

    Mechanics — the page is PeopleSoft Fluid, i.e. stateful: GET the public entry URL
    (hands out guest cookies + the ICSID token), then ICAJAX POSTs run the search and
    page through results (25 rows/page; the '<N> results' counter and the pager's
    row-action id are parsed from each response, never hardcoded).

    Accuracy model (each point live-verified before launch):
    - Isolation: institution codes come ONLY from the system's own 'VCCS Colleges and
      Codes' KB table. Same trap as ctcLink: an INVALID code silently returns ANOTHER
      college's data, so codes are never guessed, and each college's entry page
      (which displays its own name) was checked against its code.
    - Status is authoritative per section: ONLY an 'Open' badge counts as open.
      'Wait List', 'Closed', or anything unrecognized => not open — never a false
      alert. The list view shows no seat counts, so like the Fose/VT adapters we
      report status only (seats None).
    - Fail closed: missing badge, duplicate section id, pager missing while rows
      remain, or results containing a DIFFERENT course => skip the course entirely.
    - Term: the guest search serves exactly ONE term — the active registration term
      (verified via the single-value term facet) — so it self-maintains across
      semesters; there is no term code to adopt or get wrong.
    """
    _BASE = "https://ps-sis.vccs.edu/psc/S92GUEST/EMPLOYEE/SA/c/VX_CUSTOM_SR.VX_SSR_CLSRCH_FL.GBL"
    _CRS_RE = re.compile(r"^([A-Za-z]{2,4})\s*(\d{1,3}[A-Za-z]?)$")

    def __init__(self, id, name, inst, example):
        self.id = id; self.name = name; self.inst = inst; self.example = example

    def _norm(self, course):
        m = self._CRS_RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return f"https://m.sis.vccs.edu/app/catalog/classSearch?institution={self.inst}"

    def _session(self):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA)]
        page = Banner._retry(lambda: op.open(self.reg_url(""), timeout=30)
                             .read().decode("utf-8", "replace"))
        m = re.search(r"name='ICSID' id='ICSID' value='([^']+)'", page)
        if not m:
            raise RuntimeError("vccs: no ICSID (page shape changed)")
        return op, m.group(1)

    def _post(self, op, icsid, state, action, extra=None):
        form = {"ICAJAX": "1", "ICType": "Panel", "ICElementNum": "0",
                "ICStateNum": str(state), "ICAction": action, "ICSID": icsid,
                "ICModelCancel": "0"}
        if extra:
            form.update(extra)
        req = urllib.request.Request(self._BASE,
                                     data=urllib.parse.urlencode(form).encode())
        return Banner._retry(lambda: op.open(req, timeout=30)
                             .read().decode("utf-8", "replace"))

    @staticmethod
    def _next_state(page, cur):
        m = (re.search(r"id='ICStateNum'[^>]*>(?:<!\[CDATA\[)?(\d+)", page) or
             re.search(r"name='ICStateNum'[^>]*value='(\d+)'", page))
        return int(m.group(1)) if m else cur + 1

    @staticmethod
    def _rows(page):
        """(row_index, section_id) for each rendered result row."""
        return re.findall(r"id='win0divVX_RSLT_NAV_WK_HTMLAREA2\$(\d+)'"
                          r".{0,400}?<small>Section (\S+) / Class Nbr \d+",
                          page, re.S)

    @staticmethod
    def _badges(page):
        """row_index -> status text, from the per-row card-header element series."""
        out = {}
        for m in re.finditer(r"id='win0divVX_RSLT_NAV_WK_HTMLAREA1\$\d+\$\$(\d+)'"
                             r"(.{0,1500}?)<!-- End HTML Area", page, re.S):
            blob = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2))).strip()
            sm = re.search(r"(Open|Wait List|Closed)$", blob)
            if sm:
                out[m.group(1)] = sm.group(1)
        return out

    def fetch(self, courses):
        try:
            op, icsid = self._session()
        except Exception:
            return {}
        out, state = {}, 1
        for course in courses:
            subj, num = self._norm(course)
            if not subj:
                continue
            try:
                page = self._post(op, icsid, state, "VX_CLSRCH_WRK_SSR_PB_SEARCH",
                                  {"VX_CLSRCH_WRK2_SUBJECT": subj,
                                   "VX_CLSRCH_WRK2_CATALOG_NBR": num})
                state = self._next_state(page, state)
            except Exception:
                continue
            if "The search returns no results" in page:
                continue                        # course not offered this term
            mt = re.search(r">(\d+) results?<", page)
            total = int(mt.group(1)) if mt else None
            secs, ok = {}, True
            for _ in range(10):                 # hard page cap (25 rows/page)
                text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
                # results must be OUR course only — a foreign header means the
                # search matched something else; can't trust pairing => skip
                heads = set(re.findall(r"\b([A-Z]{2,4}) (\d{1,3}[A-Z]?):\s", text))
                if heads - {(subj, num)}:
                    ok = False
                    break
                rows, badges = self._rows(page), self._badges(page)
                if not rows:
                    ok = False
                    break
                for idx, sec in rows:
                    st = badges.get(idx)
                    if st is None or sec in secs:   # missing badge / dup section id
                        ok = False
                        break
                    secs[sec] = {"open": st == "Open", "seats": None}
                if not ok:
                    break
                if total is None or len(secs) >= total:
                    break
                pm = re.search(r"OnRowAction\(this,'(VX_RSLT_NAV_WK_SEARCH_"
                               r"CONDITION2\$\d+\$)'", page)
                if not pm:                      # more rows exist but no pager
                    ok = False
                    break
                try:
                    page = self._post(op, icsid, state, pm.group(1))
                    state = self._next_state(page, state)
                except Exception:
                    ok = False
                    break
            if ok and secs and (total is None or len(secs) == total):
                out[course] = secs
        return out


# Authoritative SIS IDs from the system's own 'VCCS Colleges and Codes' table
# (help.vccs.edu KB 156820); 7 of 23 independently cross-checked against the
# colleges' OWN published class-search links. NEVER add a guessed code — an
# invalid code silently serves another college's data.
_VCCS = [
    ("va-brightpoint", "Brightpoint Community College", "JT290", "ENG 111"),
    ("va-blue-ridge", "Blue Ridge Community College (VA)", "BR291", "ENG 111"),
    ("va-camp", "Camp Community College", "PC277", "ENG 111"),
    ("va-central-virginia", "Central Virginia Community College", "CV292", "ENG 111"),
    ("va-danville", "Danville Community College", "DC279", "ENG 111"),
    ("va-eastern-shore", "Eastern Shore Community College", "ES284", "ENG 111"),
    ("va-germanna", "Germanna Community College", "GC297", "ENG 111"),
    ("va-laurel-ridge", "Laurel Ridge Community College", "LF298", "ENG 111"),
    ("va-mountain-empire", "Mountain Empire Community College", "ME299", "ENG 111"),
    ("va-mountain-gateway", "Mountain Gateway Community College", "DL287", "ENG 111"),
    ("va-new-river", "New River Community College", "NR275", "ENG 111"),
    ("va-nova", "Northern Virginia Community College (NOVA)", "NV280", "ENG 111"),
    ("va-patrick-henry", "Patrick & Henry Community College", "PH285", "ENG 111"),
    ("va-piedmont", "Piedmont Virginia Community College", "PV282", "ENG 111"),
    ("va-rappahannock", "Rappahannock Community College", "RC278", "ENG 111"),
    # Reynolds: ENG 111 reuses section id 15OA across two sessions (collapse guard
    # correctly skips it) — example is a verified-clean course instead
    ("va-reynolds", "Reynolds Community College", "SR283", "BIO 101"),
    ("va-southside", "Southside Virginia Community College", "SV276", "ENG 111"),
    ("va-southwest", "Southwest Virginia Community College", "SW294", "ENG 111"),
    ("va-tidewater", "Tidewater Community College", "TC295", "ENG 111"),
    ("va-virginia-highlands", "Virginia Highlands Community College", "VH296", "ENG 111"),
    ("va-virginia-peninsula", "Virginia Peninsula Community College", "TN293", "ENG 111"),
    ("va-virginia-western", "Virginia Western Community College", "VW286", "ENG 111"),
    ("va-wytheville", "Wytheville Community College", "WC288", "ENG 111"),
]


# ===========================================================================
_CUNY_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16 Safari/605.1.15"

class CUNY:
    """CUNY Global Search (globalsearch.cuny.edu) — ONE public guest search serving all
    CUNY colleges. Stateful 3-request form flow per subject search: GET search.jsp (session
    cookie) -> POST institution+term -> POST subject (open_class=O). Results carry CUNY's OWN
    authoritative Open/Closed/WaitList status via status_*.gif images; NO seat numbers ->
    seats=None. We read OPEN only, so we can NEVER false-alert (worst case is a miss, caught
    by the health guard). CUNY DISPLAYS course codes differently from the codes you SEARCH
    with (student sees "ACC 10100" but the search subject is "ACCT"); each college has a
    validated, CONFLICT-FREE display->search map in _CUNY_MAPS, so a student's typed code
    always resolves to exactly one search. Course numbers are 3-5 digits. Subclass sets id,
    name, inst, example. Fail-safe: {} on any error / format change. term shared (Fall = 1269;
    bump manually each semester like the other custom adapters)."""
    base = "https://globalsearch.cuny.edu/CFGlobalSearchTool/"
    term = "1269"; term_name = "2026 Fall Term"
    example = "BIOL 10200"
    _RE = re.compile(r"^([A-Za-z]{2,6})\.?\s*(\d{2,5}[A-Za-z]?)$")  # tolerate "BIOL. 1001" (Brooklyn)

    def _norm(self, course):
        m = self._RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        subj, _ = self._norm(course)
        return bool(subj) and subj in _CUNY_MAPS.get(self.inst, {})

    def reg_url(self, course):
        return self.base + "search.jsp"

    def _search(self, search_subject):
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", _CUNY_UA)]
        op.open(self.base + "search.jsp", timeout=15).read()
        d2 = op.open(urllib.request.Request(self.base + "CFSearchToolController",
            data=urllib.parse.urlencode({"inst_selection": self.inst,
                "selectedTermName": self.term_name, "term_value": self.term,
                "next_btn": "Next"}).encode()), timeout=20).read().decode("latin-1")
        form = d2[d2.find('name="class_search_form"'):]
        if not form:
            return None
        fields = {}
        for m in re.finditer(r'<input[^>]*>', form):
            t = m.group(0)
            if re.search(r'type=["\']?(submit|button|reset|checkbox|radio)', t):
                continue
            nm = re.search(r'name=["\']?([\w\[\]]+)', t)
            if not nm:
                continue
            val = re.search(r'value=["\']?([^"\'>]*)', t)
            fields[nm.group(1)] = val.group(1) if val else ""
        for m in re.finditer(r'<select[^>]*name=["\']?(\w+)', form):
            fields.setdefault(m.group(1), "")
        fields.update({"subject_name": search_subject, "selectedSubjectName": search_subject,
                       "open_class": "O", "search_btn_search": "Search"})
        return op.open(urllib.request.Request(self.base + "CFSearchToolController",
            data=urllib.parse.urlencode(fields).encode()), timeout=25).read().decode("latin-1")

    def _parse(self, html, disp, num):
        html = re.sub(r'<script.*?</script>', ' ', html, flags=re.S)
        # some colleges suffix the subject with a period in the DISPLAY ("BIOL. 1001" at
        # Brooklyn) — tolerate an optional trailing "." after the code (safe for the rest).
        m = re.search(re.escape(disp) + r'\.?(?:&nbsp;|\s)+' + re.escape(num) + r'(?:&nbsp;|\s)+-', html)
        if not m:
            return {}
        start = m.end()
        nxt = re.search(r'[A-Z]{2,6}\.?(?:&nbsp;|\s)+\d{2,5}[A-Za-z]?(?:&nbsp;|\s)+-', html[start + 5:])
        block = html[start: start + 5 + nxt.start()] if nxt else html[start:]
        secs = {}
        for row in re.finditer(r'>(\d{4,6})</a>(.*?)status_(open|closed|waiting)\.gif', block, re.S):
            secs[row.group(1)] = {"open": row.group(3) == "open", "seats": None}
        return secs

    def fetch(self, courses):
        cmap = _CUNY_MAPS.get(self.inst, {})
        by_search = {}
        for c in courses:
            subj, num = self._norm(c)
            ss = cmap.get(subj) if subj else None
            if ss:
                by_search.setdefault(ss, []).append((c, subj, num))
        out = {}
        for ss, items in by_search.items():
            try:
                html = self._search(ss)
            except Exception:
                continue
            if not html or "class section(s) found" not in html:
                continue
            for c, disp, num in items:
                secs = self._parse(html, disp, num)
                out[c] = secs if secs else {"none": {"open": False, "seats": None}}
        return out


class Baruch(CUNY):
    id = "cuny-baruch"; name = "Baruch College (CUNY)"; inst = "BAR01"; example = "BIO 1012"
class BMCC(CUNY):
    id = "cuny-bmcc"; name = "Borough of Manhattan CC (CUNY)"; inst = "BMC01"; example = "BIO 108"
class HunterCUNY(CUNY):
    id = "cuny-hunter"; name = "Hunter College (CUNY)"; inst = "HTR01"; example = "BIOL 10200"
class QueensCUNY(CUNY):
    id = "cuny-queens"; name = "Queens College (CUNY)"; inst = "QNS01"; example = "BIOL 105"
class BronxCC(CUNY):
    id = "cuny-bronxcc"; name = "Bronx Community College (CUNY)"; inst = "BCC01"; example = "BIO 11"
class StatenIsland(CUNY):
    id = "cuny-statenisland"; name = "College of Staten Island (CUNY)"; inst = "CSI01"; example = "BIO 106"
class CityCollege(CUNY):
    id = "cuny-citycollege"; name = "City College (CUNY)"; inst = "CTY01"; example = "BIO 10004"


class GuttmanCC(CUNY):
    id = "cuny-guttmancc"; name = "Guttman Community College (CUNY)"; inst = "NCC01"; example = "BIOL 122"
class HostosCC(CUNY):
    id = "cuny-hostoscc"; name = "Hostos Community College (CUNY)"; inst = "HOS01"; example = "BIO 110"

class KingsboroughCC(CUNY):
    id = "cuny-kingsboroughcc"; name = "Kingsborough Community College (CUNY)"; inst = "KCC01"; example = "BIO 1100"
class JohnJayCUNY(CUNY):
    id = "cuny-johnjaycuny"; name = "John Jay College (CUNY)"; inst = "JJC01"; example = "BIO 101"
class LaGuardiaCC(CUNY):
    id = "cuny-laguardiacc"; name = "LaGuardia Community College (CUNY)"; inst = "LAG01"; example = "ENG 101"

class MedgarEvers(CUNY):
    id = "cuny-medgarevers"; name = "Medgar Evers College (CUNY)"; inst = "MEC01"; example = "BIO 101"
class LehmanCUNY(CUNY):
    id = "cuny-lehmancuny"; name = "Lehman College (CUNY)"; inst = "LEH01"; example = "BIO 166"
class CityTech(CUNY):
    id = "cuny-citytech"; name = "NYC College of Technology (CUNY)"; inst = "NYT01"; example = "BIO 1100"
class Queensborough(CUNY):
    id = "cuny-queensborough"; name = "Queensborough Community College (CUNY)"; inst = "QCC01"; example = "ENGL 101"

class YorkCUNY(CUNY):
    id = "cuny-yorkcuny"; name = "York College (CUNY)"; inst = "YRK01"; example = "BIO 110"
class CunySPS(CUNY):
    id = "cuny-cunysps"; name = "CUNY School of Professional Studies"; inst = "SPS01"; example = "BIO 200"

class BrooklynCUNY(CUNY):
    id = "cuny-brooklyncuny"; name = "Brooklyn College (CUNY)"; inst = "BKL01"; example = "BIOL 1001"

class VSB:
    """Visual Schedule Builder (VSB Software Inc.) — ONE engine, hosted per district at
    vsb.<district>.edu, so this adapter is REUSABLE: a subclass sets host/term/cams/campuses.
    Proven on Contra Costa CCD (3 colleges). Public guest access, no login.

    Two GET endpoints, both gated by a per-minute anti-scrape token (lifted from unity.js):
        t = floor(now_ms / 60000) % 1000  ;  e = t%3 + t%39 + t%42
    1. /api/courses/suggestions?...&course_add=<code> -> <rs>SUBJ NUM</rs>, the term's real
       course keys. A key carries a SPACE and its number may LEAD with a letter (POLS C1000)
       or TRAIL one (MATH 121L), so we never hand-split the user's text — we ask this
       endpoint (it resolves 'POLSC1000' -> 'POLS C1000' in one hop) and keep the key whose
       space-stripped form matches ours. The search is FUZZY (course_add=BIOL also returns
       ANTHR 141L, BIOSC 005), so it must be an exact match, NEVER "first result".
    2. /api/class-data?...&course_0_0=<KEY> -> XML sections.

    XML: <course><uselection><selection><block secNo= os= isFull= campus=/>. A section is
    keyed by secNo and carries TWO blocks — the metered primary plus a linked LAB1 whose
    os/me/ws are ALL -1 (it holds no seat data) -> dedup by secNo and skip os<0, or a lab
    sentinel gets read as a seat count.

    ⚠️ OPEN RULE = os>0 AND isFull==0 — never os alone. Sections exist with os>0 while
    isFull=1 because every remaining seat is RESERVED: live-verified os == nres EXACTLY on
    all such sections (LMC CHEM 006 sec3246 os=4 nres=4, sec3255 os=4 nres=4, CHEM 007
    sec1143 os=3 nres=3, sec1410 os=5 nres=5, POLS C1000 sec0302 os=3 nres=3). Trusting
    os>0 would false-open every one. nres is NOT the discriminator either — 26 genuinely
    open sections carry nres>0 alongside isFull=0. isFull is the authority.

    ⚠️ `cams` DOES NOT FILTER class-data: CCC / DVC / LMC / all-five return byte-identical
    payloads (live-verified). It IS required by /suggestions (omit it -> zero keys). Campus
    isolation is therefore CLIENT-SIDE on each block's campus= attribute, and `campuses` is
    a SET because a college owns its satellite sites — Diablo Valley = DVC + San Ramon
    (SRC), Los Medanos = LMC + Brentwood (BRT), confirmed on the colleges' own sites.
    Scoping to the bare code would silently drop every satellite section. Live-verified
    ZERO secNo collisions within a college across 168 sections.

    A course not offered in the requested term answers HTTP 500 -> no data, never a guess.
    The pinned `term` is the seed / last-known-good; refresh_term auto-rolls it (see there)."""
    host = ""                             # 'vsb.4cd.edu'        subclass sets
    term = ""                             # '202630' Fall 2026   subclass sets
    cams = ""                             # required by /suggestions only
    campuses = ()                         # campus codes this college owns
    _TTL = 60                             # seats must stay fresh; only dedupes sibling colleges
    _KEY_TTL = 3600                       # code -> VSB key is stable within a term
    _MENU_TTL = 21600                     # term menu barely changes
    _lock = threading.Lock()
    _data = {}                            # (host, term, key) -> (ts, {(campus, secNo): {...}})
    _keys = {}                            # (host, term, flat) -> (ts, key or None)
    _menus = {}                           # host -> (ts, [(code, name)]) in menu order
    _RE = re.compile(r"^[A-Za-z]{2,6}[\s\-]*[A-Za-z]?\d{1,4}[A-Za-z]{0,2}$")
    _TERM_RE = re.compile(r'"(\w+)":\{"name":"([^"]+)"')
    _NAME_RE = re.compile(r"(spring|summer|fall|autumn|winter)\s*(20\d\d)", re.I)
    # Last day we still consider a term "live". Deliberately generous: rolling LATE only
    # costs a manual bump, rolling EARLY silently serves the wrong term's seats.
    _SEASON_END = {"winter": (2, 15), "spring": (6, 15), "summer": (9, 1), "fall": (1, 15)}
    _active_term = None

    @staticmethod
    def _token():
        t = int(time.time() // 60) % 1000
        return t, t % 3 + t % 39 + t % 42

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body.decode("utf-8", "replace")

    def valid_course(self, course):
        return bool(self._RE.match(course.strip()))

    def cur_term(self):
        return self._active_term or self.term

    def reg_url(self, course):
        return f"https://{self.host}/"

    def _suggest(self, term, text):
        """Course keys matching `text` in `term`. Fuzzy — callers must match exactly."""
        t, e = self._token()
        url = (f"https://{self.host}/api/courses/suggestions?term={term}"
               f"&cams={self.cams}&course_add={urllib.parse.quote(text)}"
               f"&page_num=0&sco=0&sio=1&already=&t={t}&e={e}")
        out = []
        for n in ET.fromstring(self._get(url)).iter("rs"):
            v = (n.text or "").strip()
            if v and v != "_more_":
                out.append(v)
        return out

    def _resolve(self, course):
        """User text -> VSB's exact course key, or None. Cached per term."""
        flat = re.sub(r"[^A-Za-z0-9]", "", course).upper()
        if not flat:
            return None
        ck = (self.host, self.cur_term(), flat)
        with VSB._lock:
            c = VSB._keys.get(ck)
            if c and time.time() - c[0] < self._KEY_TTL:
                return c[1]
        try:
            cands = self._suggest(self.cur_term(), course.strip())
        except Exception:
            return None                   # transient: don't cache a failure as "no such course"
        key = next((c for c in cands
                    if re.sub(r"\s+", "", c).upper() == flat), None)   # exact, never first-hit
        with VSB._lock:
            VSB._keys[ck] = (time.time(), key)
        return key

    def _sections(self, key):
        """All sections for a course key, district-wide: {(campus, secNo): {open, seats}}.
        Cached so sibling colleges on one host share a single fetch."""
        ck = (self.host, self.cur_term(), key)
        with VSB._lock:
            c = VSB._data.get(ck)
            if c and time.time() - c[0] < self._TTL:
                return c[1]
        t, e = self._token()
        url = (f"https://{self.host}/api/class-data?term={self.cur_term()}"
               f"&course_0_0={urllib.parse.quote(key)}&cams={self.cams}"
               f"&t={t}&e={e}&nouser=1")
        try:
            root = ET.fromstring(self._get(url))
        except Exception:
            return c[1] if c else {}      # 500 (not offered this term) or transient -> silence
        secs = {}
        for b in root.iter("block"):
            cam, sec = b.get("campus"), b.get("secNo")
            if not cam or not sec:
                continue
            try:
                avail, full = int(b.get("os")), int(b.get("isFull"))
            except (TypeError, ValueError):
                continue                  # no count -> skip, never guess
            if avail < 0:
                continue                  # LAB1 sentinel: os/me/ws all -1, carries no seats
            openb = avail > 0 and full == 0            # reserved-seat trap: os>0 can be FULL
            prev = secs.get((cam, sec))
            secs[(cam, sec)] = ({"open": prev["open"] and openb,
                                 "seats": min(prev["seats"], avail)}    # 2 metered blocks:
                                if prev else {"open": openb, "seats": avail})  # both must be open
        with VSB._lock:
            VSB._data[ck] = (time.time(), secs)
        return secs

    def fetch(self, courses):
        out = {}
        for course in courses:
            key = self._resolve(course)
            if not key:
                continue
            mine = {sec: v for (cam, sec), v in self._sections(key).items()
                    if cam in self.campuses}
            if mine:
                out[course] = mine
        return out

    def _menu(self):
        """[(code, name)] in the site's own order, from the term map criteria.jsp hands
        to EE.initEntrance({"202630":{"name":"Fall 2026",...}})."""
        with VSB._lock:
            c = VSB._menus.get(self.host)
            if c and time.time() - c[0] < self._MENU_TTL:
                return c[1]
        try:
            body = self._get(f"https://{self.host}/criteria.jsp")
        except Exception:
            return c[1] if c else []
        menu = [(code, name) for code, name in self._TERM_RE.findall(body)
                if self._term_end(name)]        # keep only terms we can date
        if menu:
            with VSB._lock:
                VSB._menus[self.host] = (time.time(), menu)
        return menu or (c[1] if c else [])

    def _term_end(self, name):
        """Last day a term is still 'live', from its DISPLAY NAME ('Fall 2026'). The name
        is used rather than the code because codes come from each school's own SIS and vary
        per host, while VSB always renders a human season+year."""
        m = self._NAME_RE.search(name or "")
        if not m:
            return None
        season = m.group(1).lower().replace("autumn", "fall")
        year = int(m.group(2))
        mo, day = self._SEASON_END[season]
        return datetime.date(year + (1 if season == "fall" else 0), mo, day)

    def _probe(self, term):
        """Does THIS college have live sections in `term`? The verify half of
        verify-before-adopt — a term can sit in the menu for months before its schedule
        is loaded, and adopting an empty one would silently stop every alert."""
        subj = re.match(r"^[A-Za-z]+", (self.example or "").strip())
        if not subj:
            return False
        try:
            keys = self._suggest(term, subj.group(0))
        except Exception:
            return False
        for key in keys[:3]:
            try:
                if any(cam in self.campuses for cam, _ in self._sections(key)):
                    return True
            except Exception:
                continue
        return False

    def refresh_term(self, log=None, today=None):
        """Roll the pinned term forward ONLY once it has ENDED, never early.

        Rolling early is the dangerous direction: VSB loads future terms months ahead
        (Spring 2027 already returned sections in July 2026), so the usual 'newest term
        with live data' rule would have jumped every college a full term ahead and
        silently starved current watchers of alerts. Rolling late merely costs a manual
        bump. So: keep the pinned term until its own season is over, then take the next
        dateable term in the menu that is still live AND verifiably has this college's
        sections; otherwise keep last-known-good."""
        menu = self._menu()
        if not menu:
            return
        names = dict(menu)
        codes = [c for c, _ in menu]
        cur = self.cur_term()
        today = today or datetime.date.today()
        end = self._term_end(names.get(cur))
        if cur not in codes or end is None or today <= end:
            return                            # still current (or unknown) -> never roll
        for code in codes[codes.index(cur) + 1:]:          # forward only
            nend = self._term_end(names.get(code))
            if nend is None or nend < today:
                continue                      # already over too
            prev = self._active_term
            self._active_term = code
            if self._probe(code):
                if log:
                    log(f"[term] {self.id}: term auto-updated {cur} -> {code} "
                        f"({names.get(code)})")
                return
            self._active_term = prev
            if log:
                log(f"[term] {self.id}: {cur} ({names.get(cur)}) ended but {code} has no "
                    f"live data yet — keeping {cur}")
            return


class ContraCostaCollege(VSB):
    id = "contracostacollege"; name = "Contra Costa College"
    host = "vsb.4cd.edu"; term = "202630"          # Fall 2026; pinned
    cams = "CCC_BRT_SRC_DVC_LMC"; campuses = ("CCC",)
    example = "MATH 120"

class DiabloValley(VSB):
    id = "diablovalley"; name = "Diablo Valley College"
    host = "vsb.4cd.edu"; term = "202630"
    cams = "CCC_BRT_SRC_DVC_LMC"; campuses = ("DVC", "SRC")   # + San Ramon campus
    example = "BIOL 130"

class LosMedanos(VSB):
    id = "losmedanos"; name = "Los Medanos College"
    host = "vsb.4cd.edu"; term = "202630"
    cams = "CCC_BRT_SRC_DVC_LMC"; campuses = ("LMC", "BRT")   # + Brentwood Center
    example = "CHEM 006"


class KCTCS(VSB):
    """Kentucky Community & Technical College System — 16 colleges on ONE VSB host.
    Public guest access (their own page invites non-students to browse).

    Campus ownership comes from the host's OWN authority, not name patterns: mscams in
    /api/v2/multiselectdata.js lists exactly 36 public campuses, each tagged with its
    college. class-data's campus= attr uses precisely these campus-level ids
    (live-verified: 5,931 sections across 60 courses -> 36 distinct values, 35 in the
    map). Each subclass's `campuses` is its college's exact mscams set.

    ⚠️ The 36th value, KCTCSiMYCEC ('Maysville CT E KY Correctional'), is EXCLUDED on
    purpose: sections taught inside the Eastern Kentucky Correctional Complex, absent
    from KCTCS's own public campus picker. A general Maysville student cannot enroll in
    them, so alerting on their seats would be an eligibility false-open (Racer-Academy
    class). A prefix-match rule (match any campus starting with the college's stem) was
    considered and REJECTED: it would have swept MYCEC in, and stems cross college
    lines in the location data (Ashland's own location list carries Maysville-stem
    codes), so prefixes can mis-assign, not just over-include.

    Term menu is just Summer 2026 (4262) + Fall 2026 (4264) — no premature future term;
    auto-rolls via VSB.refresh_term. cams (needed by /suggestions only) = all 36."""
    host = "kctvsbprd.ps.kctcs.edu"; term = "4264"           # Fall 2026
    cams = ("KCTCSiACTC_KCTCSiBSC_KCTCSiBLC_KCTCSiECTC_KCTCSiECTCL_KCTCSiECTCS_"
            "KCTCSiGTW_KCTCSiHZC_KCTCSiHZCKN_KCTCSiHZCLE_KCTCSiHZCLC_KCTCSiHZCTC_"
            "KCTCSiHEC_KCTCSiHPC_KCTCSiHPCFC_KCTCSiJFC_KCTCSiJFCBC_KCTCSiJFCCA_"
            "KCTCSiJFCSC_KCTCSiJFCSW_KCTCSiJFCTC_KCTCSiMDC_KCTCSiMYC_KCTCSiMYCRC_"
            "KCTCSiMYCLV_KCTCSiMYCMC_KCTCSiOWC_KCTCSiSMC_KCTCSiSKY_KCTCSiSEC_"
            "KCTCSiSECHA_KCTCSiSECKC_KCTCSiSECMD_KCTCSiSECPV_KCTCSiSECWH_KCTCSiWKCTC")
    example = "ENG 101"

class AshlandCTC(KCTCS):
    id = "ashlandctc"; name = "Ashland Community & Technical College"
    campuses = ("KCTCSiACTC",)
class BigSandyCTC(KCTCS):
    id = "bigsandyctc"; name = "Big Sandy Community & Technical College"
    campuses = ("KCTCSiBSC",)
class BluegrassCTC(KCTCS):
    id = "bluegrassctc"; name = "Bluegrass Community & Technical College"
    campuses = ("KCTCSiBLC",)
class ElizabethtownCTC(KCTCS):
    id = "elizabethtownctc"; name = "Elizabethtown Community & Technical College"
    campuses = ("KCTCSiECTC", "KCTCSiECTCL", "KCTCSiECTCS")
class GatewayKY(KCTCS):
    id = "gatewayky"; name = "Gateway Community & Technical College"  # ≠ GateWay CC (AZ)
    campuses = ("KCTCSiGTW",)
class HazardCTC(KCTCS):
    id = "hazardctc"; name = "Hazard Community & Technical College"
    campuses = ("KCTCSiHZC", "KCTCSiHZCKN", "KCTCSiHZCLE", "KCTCSiHZCLC", "KCTCSiHZCTC")
class HendersonCC(KCTCS):
    id = "hendersoncc"; name = "Henderson Community College"
    campuses = ("KCTCSiHEC",)
class HopkinsvilleCC(KCTCS):
    id = "hopkinsvillecc"; name = "Hopkinsville Community College"
    campuses = ("KCTCSiHPC", "KCTCSiHPCFC")                  # + Fort Campbell
class JeffersonCTC(KCTCS):
    id = "jeffersonctc"; name = "Jefferson Community & Technical College"  # ≠ SUNY Jefferson
    campuses = ("KCTCSiJFC", "KCTCSiJFCBC", "KCTCSiJFCCA",
                "KCTCSiJFCSC", "KCTCSiJFCSW", "KCTCSiJFCTC")
class MadisonvilleCC(KCTCS):
    id = "madisonvillecc"; name = "Madisonville Community College"
    campuses = ("KCTCSiMDC",)
class MaysvilleCTC(KCTCS):
    # KCTCSiMYCEC deliberately absent — correctional-facility sections, see KCTCS docstring
    id = "maysvillectc"; name = "Maysville Community & Technical College"
    campuses = ("KCTCSiMYC", "KCTCSiMYCRC", "KCTCSiMYCLV", "KCTCSiMYCMC")
class OwensboroCTC(KCTCS):
    id = "owensboroctc"; name = "Owensboro Community & Technical College"
    campuses = ("KCTCSiOWC",)
class SomersetCC(KCTCS):
    id = "somersetcc"; name = "Somerset Community College"
    campuses = ("KCTCSiSMC",)
class SouthcentralKY(KCTCS):
    id = "southcentralky"; name = "Southcentral Kentucky Community & Technical College"
    campuses = ("KCTCSiSKY",)
class SoutheastKY(KCTCS):
    id = "southeastky"; name = "Southeast Kentucky Community & Technical College"
    campuses = ("KCTCSiSEC", "KCTCSiSECHA", "KCTCSiSECKC",
                "KCTCSiSECMD", "KCTCSiSECPV", "KCTCSiSECWH")
class WestKentuckyCTC(KCTCS):
    id = "westkentuckyctc"; name = "West Kentucky Community & Technical College"
    campuses = ("KCTCSiWKCTC",)


_ALL_SCHOOLS = ([UMD(), Rutgers(), Cornell(), Penn(), VirginiaTech(), OhioState(),
                             CUBoulder(), Brown(), Yale(), NotreDame(), Emory(), Dartmouth(),
                             Wisconsin(), Iowa(),
                             Tennessee(), FAU(), BallState(), Wyoming(), CNM(),
                             GeorgiaTech(), Northeastern(), EmpireState(), TexasState(),
                             Temple(), Villanova(), CofC(), SouthFlorida(), Oklahoma(),
                             GeorgiaState(), PortlandState(),
                             GeorgiaSouthern(), WestGeorgia(), Valdosta(), GeorgiaGwinnett(),
                             ColumbusState(), GeorgiaCollege(), MiddleGeorgia(), ClaytonState(),
                             GeorgiaSouthwestern(), FortValleyState(),
                             AugustaUniversity(),
                             VCU(), OldDominion(), ConnecticutState(), LouisianaLafayette(),
                             GrandValley(), Radford(), Fordham(),
                             SouthernUtah(), UtahState(), MiamiOhio(),
                             MississippiState(), Skidmore(), Montclair(), MaryWashington(),
                             UNCCharlotte(), WesternMichigan(), WichitaState(), TexasTech(),
                             UCRiverside(), UTSA(), UTEP(), Memphis(), BuffaloState(), CCSF(),
                             USD(), SDStateU(), BlackHillsState(), NorthernStateU(),
                             DakotaState(), SDMines(), Alabama(), Idaho(),
                             OklahomaState(), WeberState(), Montana(), Tarleton(),
                             UNCWilmington(), Longwood(), WestChester(), SUNYPlattsburgh(),
                             ULMonroe(), McNeese(), Grambling(), SUNYGeneseo(),
                             SUNYFarmingdale(), SUNYPoly(), SUNYMorrisville(),
                             SUNYAlfredState(), CentralCTState(), SouthernCTState(),
                             WesternCTState(), EasternCTState(), StJosephs(), Rider(),
                             Kennesaw(), WayneState(), Dayton(), Xavier(), MSUDenver(),
                             ColoradoMesa(), EasternWashington(),
                             SouthAlabama(), TennesseeState(), Stockton(),
                             AlbanyStateGA(), SIUE(),
                             SanJacinto(), DMACC(), PimaCC(), JohnsonCountyCC(), Vincennes(),
                             NortheasternStateOK(), YoungstownState(), USFSanFrancisco(),
                             IUP(), Bloomsburg(), CaliforniaPA(), Cheyney(), EastStroudsburg(),
                             Kutztown(), Millersville(), Shippensburg(), SlipperyRock(),
                             BatonRougeCC(), Delgado(), SouthLouisianaCC(), BossierParish(),
                             RiverParishes(), SOWELA(), Nunez(),
                             ChattahoocheeValley(), WallaceDothan(), GadsdenState(),
                             SheltonState(), CalhounCC(), SouthernUnion(), BishopState(),
                             CoastalAlabama(), ReidState(),
                             ArapahoeCC(), CCAurora(), CCDenver(), ColoradoNorthwestern(),
                             FrontRange(), LamarCC(), MorganCC(), NortheasternJC(),
                             OteroCollege(), PikesPeak(), PuebloCC(), RedRocks(),
                             TrinidadState(), ColoradoStateFC(),
                             ArkansasTech(), UtahTech(), MontanaTech(), NMHighlands(),
                             WesternNM(), WesternOregon(), OregonTech(),
                             NJIT(), Lehigh(), TexasSouthern(),
                             SUNYMaritime(), Providence(), Samford(), Belmont(),
                             DetroitMercy(), Kettering(), Andrews(), JohnCarroll(),
                             Otterbein(), StEdwards(), UPortland(),
                             AuburnMontgomery(), SUNYOswego(), SUNYBrockport(),
                             SUNYCobleskill(), SUNYCortland(), SUNYNewPaltz(),
                             MissouriWestern(), WestfieldState(), EasternIllinois(),
                             SUNYBroome(), DutchessCC(), JeffersonCC(), AdirondackCC(),
                             GeneseeCC(), UlsterCC(), CorningCC(), Concord(),
                             RaritanValley(), NassauCC(), MichiganFlint(), Harding(),
                             Spelman(), Ramapo(), Wentworth(), EasternFlorida(), Oakton(),
                             Washtenaw(), Pellissippi(), VolunteerState(), JacksonStateTN(),
                             ColumbiaState(), NortheastState(), PiedmontTech(),
                             NortheastMississippi(), Itawamba(), MississippiDelta(),
                             LindseyWilson(), BartonCC(), Centenary(), Catawba(),
                             Walsh(), ConcordiaWI(), Curry(),
                             IllinoisWesleyan(), Canisius(), IncarnateWord(),
                             Citrus(), Cochise(), AllanHancock(), LakeSumter(), NorthwestFlorida(), AntelopeValley(), Harford(), Gavilan(), JeffersonCollegeMO(), MeridianCC(),
                             ConcordiaTX(), TAMUSanAntonio(), TAMUCentralTexas(), UDallas(),
                             Immaculata(), RoseHulman(), Earlham(), EmporiaState(),
                             Towson(), UVA(), USM(), Palomar(), BostonUniversity(), Coppin(),
                             CSUChico(), IllinoisCentral(), CSUChannelIslands(),
                             LoyolaNO(), UnionNY(), ManchesterU(), Whitman(), Linfield(),
                             FranklinU(), Ursinus(), SalveRegina(), Cornerstone(), NorthPark(),
                             Gannon(), Mercyhurst(), SaintVincent(), Maryville(),
                             AshevilleBuncombe(), DurhamTech(), CravenCC(), KirkwoodCC(),
                             SoutheasternIA(), EasternU(), Nichols(), Elms(), BladenCC(),
                             TarrantCounty(), Allegheny(), Macomb(), MidMichigan(),
                             GuilfordTech(), StanlyCC(), HaywoodCC(), Cedarville(),
                             EasternIowaCC(), McLennan(), Roanoke(), HardinSimmons(), Elmhurst(), Bellarmine(), Wittenberg(), Quinnipiac(), Juniata(), SWOklahomaState(), LuzerneCC(), EastCentralOK(), USAOklahoma(), Hartwick(), CaldwellCC(), RoanokeChowan(), NorthArkansas(), Aquinas(), Alma(), GrandView(), ElCamino(), Triton(), Canyons(), Grossmont(), PrinceGeorges(), GovernorsState(), CarrollCCMD(), BergenCC(), CincinnatiState(), JolietJC(), LewisClarkCC(), MortonCollege(), McHenry(), WesternIdaho(),
                             FingerLakesCC(), HockingCollege(), OklahomaChristian(), LincolnLandCC(),
                             Regent(), ButteCollege(), EssexCC(),
                             DelawareTech(), WesternNewEngland(), SaintMichaels(), Evansville(),
                             DenmarkTech(), Tulsa(), CarlAlbert(), RedlandsCC(), SoutheastCCNE(),
                             Coconino(), EasternWyoming(), MissouriValley(),
                             UAHuntsville(), Whittier(), SimpsonU(), WestAlabama(),
                             StFrancisIL(), ColumbiaGreene(), FDU(), CentenaryNJ(), StFrancisBK(),
                             LakeMichigan(), MVNU(), WashingtonStateOH(),
                             ConnecticutCollege(), BunkerHill(), Denison(), KentuckyState(),
                             TCLowcountry(), MarsHill(), WesternPiedmont(), MitchellCC(),
                             SUNYPurchase(), SUNYESF(), NorthGATech(), Colgate(), UIndy(),
                             Northwood(), Rowan(), Roosevelt(), NationalLouis(), MercyUniversity(), Pasadena(), SanJoseEvergreen(),
                             Baruch(), BMCC(), HunterCUNY(), QueensCUNY(),
                             BronxCC(), StatenIsland(), CityCollege(), GuttmanCC(), HostosCC(), KingsboroughCC(), JohnJayCUNY(), LaGuardiaCC(), MedgarEvers(), LehmanCUNY(), CityTech(), Queensborough(), YorkCUNY(), CunySPS(), BrooklynCUNY()]
                            + [UIUC()]
                            + [SNHU(), DeVry(), ConcordiaMoorhead(), Touro(),
                               SouthernOregon(), Massasoit(), WCTC(), Blackhawk()]
                            + [JeffersonStateCC(), LawsonState(), LurleenBWallace(),
                               NorthwestShoals(), TrenholmState(), WallaceSelma(),
                               BevillState(), EnterpriseState(), SneadState(),
                               IngramState(), CentralAlabama(), DrakeState(),
                               MarionMilitary(), NortheastAlabama(), WallaceHanceville(),
                               EastGeorgiaState()]
                            + [SacredHeart(), WashingtonAdventist(), CollegeOfIdaho(),
                               DigiPen(), Campbell(), Loras(), ColumbiaMO(),
                               NWOSU(), SouthwesternTX(), VTSU(), CCV()]
                            + [Kean(), LincolnMO(), Mercer(), Ashland(),
                               ColumbiaChicago(), SaintXavier(), OlivetNazarene(),
                               McKendree(), UMobile(), DominicanCA(), Chaminade(),
                               StThomasFL(), Naropa(), Goodwin(), Felician(),
                               Neumann(), WilsonCollege(), LeTourneau(), SWAU(),
                               Trevecca(), StFrancisWayne(), PointU(),
                               SpartanburgMethodist(), CIIS(), BridgesCC(),
                               MilesCollege(), EdwardWaters(), Fisk(),
                               LeMoyneOwen(), HustonTillotson(), LincolnPA(),
                               BrooklynLaw(), Weatherford(), LacCourteOreilles()]
                            + [Georgetown(), OleMiss(), CentralOklahoma(),
                               EasternOregon(), HelenaCollege(), MCCKC(),
                               Cabrillo(), Mohave(), StateCenterCCD(), RendLake(),
                               IllinoisValley(), SouthSuburban(), Parkland(),
                               IowaWestern(), Kaskaskia(), Muskegon(), Kishwaukee(),
                               OaklandCC(), KCKCC(), Allegany(), MiddlesexNJ(),
                               IndependenceCC(), UCNJ(), Brookdale(), WesternTexas(),
                               IndianHills(), SouthPiedmont(), Robeson(),
                               FlorenceDarlington(), WesternTC(), Nicolet(),
                               Onondaga(), Winthrop(), Guilford()]
                            + [SCAD(), NWMissouri(), NortheastNE(), AlfredU(),
                               FITNYC(), Hofstra(), JamestownCC(), SUNYCanton(),
                               SUNYSchenectady(), UpstateMedical(), Presbyterian(),
                               Gonzaga(), PacificLutheran(),
                               CollegeOfTheSequoias(), UCMerced(), UOPacific(),
                               UDC(), MorehouseSOM(), BethelMN(), MohawkValley(),
                               RocklandCC(), NewSchool(),
                               ABAC(), AtlantaMetro(), CoastalGeorgia(),
                               GordonState(), SouthGeorgiaState(), DaltonState()]
                            + [UArk(), SLU(), SouthCarolina(), UConn(), OregonState(),
                               CollegeOfTheDesert(), Guam(), SimpsonCollegeIA(),
                               Kankakee(), Midway(), WorWic(), DeltaMI(),
                               WilliamJewell(), JamesSprunt(), LeesMcRae(),
                               LenoirCC(), PiedmontNC(), SampsonCC(),
                               SouthwesternCCNC(), Daemen(), EasternOKState(),
                               SoutheasternOKState(), WesternOKState(), HolyFamily(),
                               MontgomeryCountyCC(), WestminsterUT(), WesternWyoming(),
                               GeorgiaMilitary(), Bridgeport(),
                               OrangeCoast(), GoldenWest(), Coastline(),
                               Bakersfield(), CerroCoso(), Porterville()]
                            + [CtcLink(*t) for t in _CTCLINK]
                            + [MinnState(*t) for t in _MINNSTATE]
                            + [VCCS(*t) for t in _VCCS])


def _guard_registry(all_schools):
    """Refuse to build the registry if two schools collide — a duplicate school (added
    twice across sessions, e.g. a school on its own host AND on a shared-system host)
    would otherwise reach the live site, or silently overwrite the other in the id-keyed
    dict. Fails LOUDLY at import so tests catch it, never the user.

    - Duplicate id: the {s.id: s} dict would silently drop one school. Fatal.
    - Duplicate exact display name (case-insensitive): the SAME school listed twice, OR
      two genuinely different schools that need disambiguating suffixes so users can tell
      them apart in the picker. Either way the name must be made unique. Fatal.
    Near-collisions that are legitimately different (e.g. 'Northeastern University' vs
    'Northeastern State University') differ in their exact names and pass cleanly."""
    from collections import Counter
    id_counts = Counter(s.id for s in all_schools)
    dup_ids = {i: n for i, n in id_counts.items() if n > 1}
    if dup_ids:
        raise ValueError(f"Duplicate school id(s) — one would silently overwrite another: {dup_ids}")
    name_map = {}
    for s in all_schools:
        name_map.setdefault(s.name.strip().lower(), []).append(s.id)
    dup_names = {n: ids for n, ids in name_map.items() if len(ids) > 1}
    if dup_names:
        raise ValueError(
            "Duplicate school name(s) — same school added twice, or two schools needing "
            f"distinguishing suffixes: {dup_names}")
    # Duplicate CLASS object: two `class Foo:` blocks with the same name silently shadow
    # each other in Python (only the last survives), so a stale earlier copy can sit in
    # the file undetected — the id/name checks above miss it because only one instance is
    # ever registered. Flag any adapter class used by more than one registered school
    # UNLESS it's an intentional shared base (subclassed by many).
    cls_map = {}
    for s in all_schools:
        cls_map.setdefault(type(s).__name__, []).append(s.id)
    _SHARED_BASES = {"CtcLink", "MinnState", "VCCS", "CACCD", "CrnKeyedBanner",
                     "NumSubjColleague", "CodedTermColleague", "VSC"}
    dup_cls = {c: ids for c, ids in cls_map.items()
               if len(ids) > 1 and c not in _SHARED_BASES}
    if dup_cls:
        raise ValueError(
            "Adapter class used by multiple schools without being a known shared base — "
            f"likely a duplicate/shadowed class definition: {dup_cls}")
    return {s.id: s for s in all_schools}


SCHOOLS = _guard_registry(_ALL_SCHOOLS + [UCI(), UCSC(), UCSB(), UCLA(), SFSU(), SacState(), CSUN(), IowaState(), TAMU(), Purdue(), UtahU(),
    AugustanaIL(), CamdenCounty(), WalshCollege(),
    BristolCC(), Clovis(), UNCG(), NCCU(), UNCAsheville(), Otis(),
    MissouriState(), Toledo(), SFAustin(), AlabamaAM(), Utica(), Berkeley(), SCF(), WorcesterState(), WSSU(), MTSU(), Framingham(), UNM(), Chabot(), LasPositas(), CCRI(), NCAT(), HGTC(), SanDiegoCity(), SanDiegoMesa(), SanDiegoMiramar(), Fairfield(),
    IvyTech(), UTArlington(), UAlaska(), UOregon(),
    WrightState(), RPI(), Duquesne(), NMSU(), USC(), Rice(),
    PhoenixCollege(), GlendaleCC(), MesaCC(), ChandlerGilbert(), EstrellaMountain(),
    GateWayCC(), ParadiseValleyCC(), RioSalado(), ScottsdaleCC(), SouthMountainCC(),
    GeorgeMason(), NorthernMichigan(), Hartford(), UTChattanooga(), IUBloomington(),
    MorenoValley(), NorcoCollege(), RiversideCity(), WestValley(), MissionCollege(),
    MassArt(), PortlandCC(), Wabash(), MonroeCC(),
    Moorpark(), OxnardCollege(), VenturaCollege(), UVI(), Cayuga(),
    WakeTech(), Schoolcraft(), CentralCarolinaCC(), BrunswickCC(),
    CollegeOfDuPage(), SouthwesternCA(), VictorValley(), Elgin(), Kellogg(), Coalinga(),
    SantaAna(), SantiagoCanyon(), WabashValley(), OlneyCentral(), LincolnTrail(),
    SUNYDelhi(), GuamCC(), Washburn(), MurrayState(), NorthAlabama(), SIUCarbondale(),
    PascoHernando(), USI(),
    ContraCostaCollege(), DiabloValley(), LosMedanos(), AngeloState(), ECU(),
    SamHoustonState(), FerrisState(), Valparaiso(), Cameron(),
    MidwesternState(), UNCPembroke(), WesternCarolina(), Lamar(), Troy(),
    ClevelandState(), JacksonvilleState(), OaklandU(), ETSU(),
    TennesseeTech(), CentralArkansas(), UTRGV(), Nicholls(), CoastalCarolina(),
    IndianaState(), TAMUCorpusChristi(), WestTexasAM(), SEMO(),
    AshlandCTC(), BigSandyCTC(), BluegrassCTC(), ElizabethtownCTC(), GatewayKY(),
    HazardCTC(), HendersonCC(), HopkinsvilleCC(), JeffersonCTC(), MadisonvilleCC(),
    MaysvilleCTC(), OwensboroCTC(), SomersetCC(), SouthcentralKY(), SoutheastKY(),
    WestKentuckyCTC()])


def refresh_all_terms(log=None):
    """Self-maintenance: let every Banner AND PeopleSoft school auto-roll to the new
    semester's term. Safe — each school verifies live data before adopting, else keeps
    last-known-good. Call this periodically (e.g. daily) from the app."""
    for s in SCHOOLS.values():
        # auto_term = False opts a school OUT of auto-rolling entirely (parallel same-season
        # populations, or a quarter calendar the shared season model can't express). Checked
        # HERE so it binds every family, not just Banner, whose refresh_term also checks it.
        if not getattr(s, "auto_term", True):
            continue
        # duck-typed: any adapter exposing refresh_term participates (they all follow
        # verify-before-adopt), so new one-off adapters (Berkeley) self-maintain too.
        if callable(getattr(s, "refresh_term", None)):
            try:
                s.refresh_term(log)
            except Exception:
                pass
