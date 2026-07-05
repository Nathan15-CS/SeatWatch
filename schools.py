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
        WITHOUT ever risking accuracy."""
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
        # Handles contiguous ("CSCI 220") AND spaced ("C S 2334") subject codes.
        m = re.match(r"^([A-Za-z][A-Za-z ]*?)\s*(\d{3,4}[A-Za-z]?)$", course.strip())
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

class IllinoisWesleyan(Banner):
    id = "iwu"; name = "Illinois Wesleyan University"
    example = "CS 170"; host = "reg-prod.ec.iwu.edu"; term = "202610"

class Canisius(Banner):
    id = "canisius"; name = "Canisius University"
    example = "CSC 511"; host = "banner.canisius.edu"; term = "202630"

class IncarnateWord(Banner):
    id = "uiw"; name = "University of the Incarnate Word"
    example = "CIS 1100"; host = "reg-prod.ec.uiw.edu"; term = "202740"


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
SCHOOLS = {s.id: s for s in [UMD(), Rutgers(), Cornell(), Penn(), VirginiaTech(), OhioState(),
                             CUBoulder(), Brown(), Yale(), NotreDame(), Emory(),
                             Wisconsin(), Iowa(),
                             Tennessee(), FAU(), BallState(), Wyoming(), CNM(),
                             GeorgiaTech(), Northeastern(), EmpireState(), TexasState(),
                             Temple(), Villanova(), CofC(), SouthFlorida(), Oklahoma(),
                             GeorgiaState(), PortlandState(),
                             GeorgiaSouthern(), WestGeorgia(), Valdosta(), GeorgiaGwinnett(),
                             ColumbusState(), GeorgiaCollege(), MiddleGeorgia(), ClaytonState(),
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
                             RaritanValley(), NassauCC(), IllinoisWesleyan(),
                             Canisius(), IncarnateWord()]}


def refresh_all_terms(log=None):
    """Self-maintenance: let every Banner school auto-roll to the new semester's term.
    Safe — each school verifies live data before adopting, else keeps last-known-good.
    Call this periodically (e.g. daily) from the app."""
    for s in SCHOOLS.values():
        if isinstance(s, Banner):
            try:
                s.refresh_term(log)
            except Exception:
                pass
