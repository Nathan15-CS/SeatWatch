"""Parser fake-open lock-in tests — the highest-value tests in the suite.

They pin the open/full rule for every adapter FAMILY against a sanitized fixture, driven
through the REAL adapter parse (HTTP injected — no rule is re-implemented in the test), so
a future refactor can never silently turn a FULL section into a fake "open" (the #1
reputation killer: texting a student a seat that isn't there).
"""
import sys, json, re, os
sys.path.insert(0, os.path.expanduser("~/seatwatch"))
import schools

_RESULTS = []
def ck(name, cond):
    _RESULTS.append((name, bool(cond), ""))


def run():
    """Aggregator entry point — the module body already executed the checks on import."""
    p = sum(ok for _, ok, _ in _RESULTS); f = sum(not ok for _, ok, _ in _RESULTS)
    return p, f, list(_RESULTS)

class _Resp:
    def __init__(self, body): self._b = body if isinstance(body, bytes) else body.encode()
    def read(self, *a): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False
    class _H:
        def get(self, k, d=None): return d
    headers = _H(); status = 200

def _url(req): return req.full_url if hasattr(req, "full_url") else str(req)


# ============================================================= Banner 9
print("=== Banner 9 — seatsAvailable authoritative; openSection LIES read FULL (ECU/UNCP) ===")
class _BOpener:
    def __init__(self, fx): self.fx = fx
    def open(self, req, timeout=None):
        return _Resp(json.dumps(self.fx)) if "searchResults" in _url(req) else _Resp(b"")
def _banner(rows):
    class T(schools.Banner):
        id = "t"; name = "T"; example = "CS 101"; host = "x"; term = "202608"
    a = T(); a._session = lambda: (_BOpener({"data": rows, "totalCount": len(rows)}), "https://x")
    return a
rows = [
    {"subject": "CS", "courseNumber": "101", "sequenceNumber": "001", "seatsAvailable": 5,  "openSection": True},
    {"subject": "CS", "courseNumber": "101", "sequenceNumber": "002", "seatsAvailable": 0,  "openSection": True},   # LIE
    {"subject": "CS", "courseNumber": "101", "sequenceNumber": "003", "seatsAvailable": -4, "openSection": True},   # LIE
    {"subject": "CS", "courseNumber": "101", "sequenceNumber": "004", "seatsAvailable": 3,  "openSection": False},
    {"subject": "CS", "courseNumber": "101", "sequenceNumber": "005", "seatsAvailable": 0,  "openSection": False},
]
r = _banner(rows).fetch(["CS 101"]).get("CS 101", {})
ck("5 seats -> open", r.get("001", {}).get("open") is True)
ck("openSection=True + 0 seats -> FULL", r.get("002", {}).get("open") is False)
ck("openSection=True + -4 seats -> FULL", r.get("003", {}).get("open") is False)
ck("openSection=False + 3 seats -> open (seats win)", r.get("004", {}).get("open") is True)
ck("0 seats -> FULL", r.get("005", {}).get("open") is False)
ck("negative seats never surface", r.get("003", {}).get("seats") == 0)


# ============================================================= Colleague (real adapter)
print("\n=== Colleague — AvailabilityStatus=='Open' only, gated on AreSeatCountsAvailable ===")
def _colleague(section_rows):
    class T(schools.Colleague):
        id = "t"; name = "T"; example = "CS 101"; host = "x"
    a = T()
    a._session = lambda: (object(), "tok")
    def fake_post(op, tok, path, payload):
        if "PostSearchCriteria" in path:
            return {"ActivePlanTerms": [{"Description": "Fall 2026"}],
                    "CourseFullModels": [{"SubjectCode": "CS", "Number": "101",
                                          "MatchingSectionIds": ["s1"], "Id": "c1", "LocationCodes": []}]}
        return {"SectionsRetrieved": {"TermsAndSections": [
            {"Term": {"Description": "Fall 2026"}, "Sections": [{"Section": s} for s in section_rows]}]}}
    a._post = fake_post
    return a
secs = [
    {"Number": "01", "AvailabilityStatus": "Open",       "Available": 3, "AreSeatCountsAvailable": True},
    {"Number": "02", "AvailabilityStatus": "Waitlisted", "Available": 0, "AreSeatCountsAvailable": True},
    {"Number": "03", "AvailabilityStatus": "Closed",     "Available": 0, "AreSeatCountsAvailable": True},
    {"Number": "04", "AvailabilityStatus": "Open",       "Available": 5, "AreSeatCountsAvailable": False},  # skip
]
cr = _colleague(secs).fetch(["CS 101"]).get("CS 101", {})
ck("Open + counts -> open", cr.get("01", {}).get("open") is True)
ck("Waitlisted -> FULL", cr.get("02", {}).get("open") is False)
ck("Closed -> FULL", cr.get("03", {}).get("open") is False)
ck("counts unavailable -> section dropped entirely", "04" not in cr)


# ============================================================= Banner 8 (real _build)
print("\n=== Banner 8 / ListcrseBanner8 — Seats row (not Waitlist); 'none' for bad course ===")
def _listcrse(listing, details):
    class T(schools.ListcrseBanner8):
        id = "t"; name = "T"; example = "EN 101"; term = "202608"; base = "https://x/pls/prod"
    a = T()
    class LOp:
        def open(self, req, timeout=None):
            u = _url(req)
            if "p_disp_listcrse" in u: return _Resp(listing)
            m = re.search(r"crn_in=(\d+)", u)
            return _Resp(details.get(m.group(1), "") if m else "")
    a._session = lambda: LOp()
    return a
listing = ("<a href='bwckschd.p_disp_detail_sched?term_in=202608&crn_in=10001'>Eng - 10001 - EN 101 - 001</a>"
           "<a href='bwckschd.p_disp_detail_sched?term_in=202608&crn_in=10002'>Eng - 10002 - EN 101 - 002</a>")
details = {
    # FULL section: Seats rem=0, but Waitlist has 8 open — must be IGNORED
    "10001": '<th><SPAN class="fieldlabeltext">Seats</SPAN></th><td>30</td><td>30</td><td>0</td>'
             '<th><SPAN class="fieldlabeltext">Waitlist Seats</SPAN></th><td>10</td><td>2</td><td>8</td>',
    # OPEN section: Seats rem=7
    "10002": '<th><SPAN class="fieldlabeltext">Seats</SPAN></th><td>25</td><td>18</td><td>7</td>',
}
b8 = _listcrse(listing, details)._build("202608", "EN", "101")
ck("full section (Seats rem=0) -> FULL, Waitlist's 8 ignored", b8.get("10001", {}).get("open") is False)
ck("open section (Seats rem=7) -> open", b8.get("10002", {}).get("open") is True)
ck("open section seats = Remaining (7)", b8.get("10002", {}).get("seats") == 7)
# nonexistent course -> the 'none' sentinel, which must never read as open
empty = _listcrse("no matching course text here", {})._build("202608", "ZZ", "999")
ck("bad course -> no real section (empty or 'none' only)", all(k == "none" for k in empty) or not empty)
for k, v in empty.items():
    ck("any 'none' sentinel is open=False", v.get("open") is False)

if __name__ == "__main__":
    _p, _f, _res = run()
    for _n, _ok, _ in _res:
        print(f"  [{'PASS' if _ok else '*** FAIL'}] {_n}")
    print(f"\n  {_p} passed, {_f} failed")
    sys.exit(1 if _f else 0)
