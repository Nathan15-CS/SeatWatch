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
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request

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


def _pick_current_term(terms, today=None):
    """From a Banner getTerms list, pick the nearest MAIN term whose registration is the
    current target (starts >= ~1 month out). Anchored on the human-readable description —
    term CODES are not portable across schools, but 'Fall 2026' always is. Returns code
    or None. This was validated to reproduce all 43 hand-verified hardcoded terms."""
    if today is None:
        today = datetime.date.today()
    best, best_delta = None, None
    for t in terms:
        d = (t.get("description") or "").lower()
        if "view only" in d or any(s in d for s in _SUBTERM):
            continue
        m = (re.search(r"(spring|summer|fall|autumn|winter)\D{0,14}(20\d\d)", d) or
             re.search(r"(20\d\d)\D{0,14}(spring|summer|fall|autumn|winter)", d))
        if not m:
            continue
        g = m.groups()
        season = g[0] if g[0] in _SEASON else g[1]
        year = int(g[1] if g[0] in _SEASON else g[0])
        delta = (year - today.year) * 12 + (_SEASON[season] - today.month)
        if delta < 1:                      # skip in-progress / past terms
            continue
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
    Fail-safe: {} on any error, so a broken fetch is silent, never fabricated."""
    # subclass sets: id, name, example, api, srcdb

    @staticmethod
    def _norm(course):
        # 3-5 digit numbers: Emory "CS 170", CU/Brown/Yale 4-digit, Notre Dame "CSE 20110"
        m = re.match(r"^([A-Za-z]{2,5})[\s-]*(\d{3,5}[A-Za-z]?)$", course.strip())
        return f"{m.group(1).upper()} {m.group(2).upper()}" if m else None

    def valid_course(self, course):
        return self._norm(course) is not None

    def reg_url(self, course):
        return self.api.split("/api/")[0] + "/"

    def fetch(self, courses):
        out = {}
        for course in courses:
            code = self._norm(course)
            if not code:
                continue
            try:
                body = json.dumps({"other": {"srcdb": self.srcdb},
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
        """Auto-detect the current registration term; None on failure."""
        try:
            return _pick_current_term(self._get_terms())
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
                q = urllib.parse.urlencode({"txt_subject": subj, "txt_courseNumber": num,
                                            "txt_term": self.cur_term(), "pageOffset": 0,
                                            "pageMaxSize": 100})
                res = json.loads(self._retry(lambda: op.open(
                    base + "/searchResults/searchResults?" + q + self._mep(),
                    timeout=30).read().decode("utf-8", "replace")))
            except Exception:
                continue
            secs = {}
            for r in res.get("data") or []:
                if str(r.get("courseNumber")) != num:   # txt_courseNumber is prefix-match
                    continue
                if (r.get("subject") or "").upper() != subj:   # guard cross-subject collisions
                    continue
                if self.campus and (r.get("campusDescription") or "").split(" ")[0] != self.campus:
                    continue                            # shared-pool host: only OUR campus
                seq = r.get("sequenceNumber")
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

class BallState(Banner):
    id = "ballstate"; name = "Ball State University"
    example = "CS 120"; host = "banner.bsu.edu"; term = "202610"

class Wyoming(Banner):
    id = "uwyo"; name = "University of Wyoming"
    example = "COSC 1010"; host = "wyossb.uwyo.edu"; term = "202710"

class CNM(Banner):
    id = "cnm"; name = "Central New Mexico College"
    example = "CSCI 1220"; host = "banner.cnm.edu"; term = "202670"

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

class AlbanyState(Banner):
    id = "asurams"; name = "Albany State University"
    example = "CSCI 1301"; host = "asuramspc.gabest.usg.edu"; term = "202608"

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
    host = "reg-prod.ec.accs.edu"; term = "202710"

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
    _SUBJ_RE = re.compile(r"^([A-Za-z]{1,6}&?)\s*(\d{2,4}[A-Za-z]?)$")

    def _norm(self, course):
        m = self._SUBJ_RE.match(course.strip())
        return (m.group(1).upper(), m.group(2).upper()) if m else (None, None)

    def valid_course(self, course):
        return self._norm(course)[0] is not None

    def reg_url(self, course):
        return (f"https://{self.host}/psp/{self.site}/{self.node}/SA/s/"
                "WEBLIB_HCX_CM.H_BROWSE_CLASSES.FieldFormula.IScript_Main")

    def cur_term(self):
        return self._active_term or self.term

    def _cs(self):
        return (f"https://{self.host}/psc/{self.site}/{self.node}/SA/s/"
                "WEBLIB_HCX_CM.H_CLASS_SEARCH.FieldFormula")

    def _session(self):
        """Establish a guest session (no login) — the browse-classes page hands out the
        cookies the class-search IScript needs."""
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", UA), ("Accept", "application/json")]
        op.open(f"https://{self.host}/psp/{self.site}/{self.node}/SA/s/"
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
                if delta < -1:                          # skip clearly-past terms
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
                if delta < -1:                       # skip clearly-past terms
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
    Spring from ActivePlanTerms). Subclass sets: id, name, example, host."""
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
            if delta < -1:
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
                    if (c.get("SubjectCode") or "").upper() == subj and (c.get("Number") or "").upper() == num:
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

class RhodesState(Banner):
    id = "rhodesstate"; name = "Rhodes State College"
    example = "MTH 1260"; host = "banner-prod.rhodesstate.edu"; term = "202620"

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

SCHOOLS = {s.id: s for s in [UMD(), Rutgers(), Cornell(), Penn(), VirginiaTech(), OhioState(),
                             CUBoulder(), Brown(), Yale(), NotreDame(), Emory(), Dartmouth(),
                             Wisconsin(), Iowa(),
                             Tennessee(), FAU(), BallState(), Wyoming(), CNM(),
                             GeorgiaTech(), Northeastern(), EmpireState(), TexasState(),
                             Temple(), Villanova(), CofC(), SouthFlorida(), Oklahoma(),
                             GeorgiaState(), PortlandState(),
                             GeorgiaSouthern(), WestGeorgia(), Valdosta(), GeorgiaGwinnett(),
                             ColumbusState(), GeorgiaCollege(), MiddleGeorgia(), ClaytonState(),
                             GeorgiaSouthwestern(), FortValleyState(), AlbanyState(),
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
                             CoastalAlabama(), ReidState(), ColoradoStateFC(),
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
                             Towson(), UVA(), USM(), Palomar(),
                             LoyolaNO(), UnionNY(), ManchesterU(), Whitman(), Linfield(),
                             FranklinU(), Ursinus(), SalveRegina(), Cornerstone(), NorthPark(),
                             Gannon(), Mercyhurst(), SaintVincent(), Maryville(),
                             AshevilleBuncombe(), DurhamTech(), CravenCC(), KirkwoodCC(),
                             SoutheasternIA(), EasternU(), Nichols(), Elms(), BladenCC(),
                             TarrantCounty(), Allegheny(), Macomb(), MidMichigan(),
                             GuilfordTech(), StanlyCC(), HaywoodCC(), Cedarville(),
                             EasternIowaCC(), McLennan(), Roanoke(), HardinSimmons(), Elmhurst(), Bellarmine(), Wittenberg(), Quinnipiac(), Juniata(), SWOklahomaState(), LuzerneCC(), EastCentralOK(), USAOklahoma(), Hartwick(), CaldwellCC(), RoanokeChowan(), NorthArkansas(), Aquinas(), Alma(), GrandView(), ElCamino(), Triton(), Canyons(), Grossmont(), PrinceGeorges(), GovernorsState(), CarrollCCMD(), BergenCC(), CincinnatiState(), JolietJC(), LewisClarkCC(), MortonCollege(), McHenry(), WesternIdaho(),
                             FingerLakesCC(), HockingCollege(), OklahomaChristian(), LincolnLandCC(),
                             RhodesState(), Regent(), ButteCollege(), EssexCC(),
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
                            + [CtcLink(*t) for t in _CTCLINK]
                            + [MinnState(*t) for t in _MINNSTATE]
                            + [VCCS(*t) for t in _VCCS]}


def refresh_all_terms(log=None):
    """Self-maintenance: let every Banner AND PeopleSoft school auto-roll to the new
    semester's term. Safe — each school verifies live data before adopting, else keeps
    last-known-good. Call this periodically (e.g. daily) from the app."""
    for s in SCHOOLS.values():
        if isinstance(s, (Banner, PeopleSoft, MinnState)):
            try:
                s.refresh_term(log)
            except Exception:
                pass
