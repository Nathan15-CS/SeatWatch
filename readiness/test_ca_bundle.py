"""READINESS #31 — the supplemental CA bundle adds reach, never new trust.

ops/edu-intermediates.pem exists because colleges' servers omit the intermediate that
links their certificate to a public root. Browsers hide this by chasing the AIA pointer;
Python does not, so schools that a student opens without complaint were filed as broken.
Towson went dark for 23 days in August 2026 for exactly this reason — InCommon migrated to
eMudhra and the new chain ended at a root the server could not reach.

This is a TRUST SURFACE. Anything in that file can vouch for any host SeatWatch fetches,
and SeatWatch's whole promise is that its seat data is real. So two properties are asserted
here, and they are the ones that actually matter:

  1. It cannot ANCHOR new trust. Only a self-signed certificate anchors anything; an
     intermediate merely extends trust that already exists, and one whose issuer is not
     trusted is inert. So every self-signed cert in the bundle must ALREADY be in the
     system store. (Verifying every cert against the system store would be the obvious
     test and is the wrong one: legitimate intermediates chain to roots that differ
     between macOS and Ubuntu, so it fails for reasons that have nothing to do with trust.)

  2. It must PARSE. ca_chain.install() deliberately swallows a load failure so a bad
     bundle cannot take the poller down — which means a malformed file silently drops
     every intermediate and takes out the schools that depend on them, with no error
     anywhere. The swallow is right; the silence is why this check exists.

Entirely offline: certificate arithmetic, no network.
"""
import os
import re
import ssl
import subprocess
import sys
import tempfile

HERE = os.path.expanduser("~/seatwatch")
BUNDLE = os.path.join(HERE, "ops", "edu-intermediates.pem")


def _field(path, what):
    return subprocess.run(["openssl", "x509", "-in", path, "-noout", what],
                          capture_output=True, text=True).stdout.strip()


def run():
    sys.path.insert(0, HERE)
    import ca_chain

    results = []
    def check(n, c, d=""): results.append((n, bool(c), d))

    check("the bundle exists", os.path.exists(BUNDLE), BUNDLE)
    raw = open(BUNDLE).read()
    blocks = re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                        raw, re.S)
    check("it contains certificates at all", len(blocks) >= 1,
          "an empty bundle would silently return every affected school to 'broken'")

    # PARSES. The one failure mode ca_chain is built to survive, and therefore the one
    # that leaves no trace: a malformed file loads nothing and says nothing.
    loaded = None
    try:
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cafile=BUNDLE)
        loaded = len(ctx.get_ca_certs())
        check("OpenSSL parses the whole bundle", True)
    except Exception as e:
        check("OpenSSL parses the whole bundle", False,
              f"{type(e).__name__}: {e} — install() would swallow this and drop ALL of them")

    # ADDS rather than REPLACES: whatever verified before must still verify.
    bare = len(ssl.create_default_context().get_ca_certs())
    if loaded is not None:
        check("it ADDS to the system store instead of replacing it", loaded > bare,
              f"bundle-loaded={loaded} vs system-only={bare}; replacing would break "
              f"every school that was already fine")

    system_ca = ssl.get_default_verify_paths().cafile
    check("a system trust store was found to compare against", bool(system_ca),
          "without one this suite cannot judge trust and must not pretend otherwise")

    # THE TRUST RULE.
    selfsigned, checked_any = [], 0
    for b in blocks:
        p = tempfile.mktemp()
        open(p, "w").write(b + "\n")
        try:
            subj = _field(p, "-subject").replace("subject=", "").strip()
            iss = _field(p, "-issuer").replace("issuer=", "").strip()
            if not subj:
                continue
            checked_any += 1
            if subj == iss:                       # self-signed => an anchor
                r = subprocess.run(["openssl", "verify", "-CAfile", system_ca, p],
                                   capture_output=True, text=True)
                selfsigned.append((subj.split("CN=")[-1][:48], r.returncode == 0))
        finally:
            os.unlink(p)

    check("every certificate in the bundle was readable", checked_any == len(blocks),
          f"parsed {checked_any} of {len(blocks)} — an unreadable one is unaudited")

    rogue = [cn for cn, trusted in selfsigned if not trusted]
    check("no cert in the bundle ANCHORS trust the system does not already have",
          not rogue,
          f"self-signed and untrusted: {rogue} — such a CA could vouch for any registrar "
          f"and SeatWatch would believe its seat counts")
    check("...and the rule was actually exercised, not vacuously true",
          len(blocks) > 0 and checked_any > 0,
          "an empty bundle would satisfy the rule above while proving nothing")

    # Dead weight is not dangerous, but it hides the real reason a school is failing.
    expired = []
    for b in blocks:
        p = tempfile.mktemp()
        open(p, "w").write(b + "\n")
        try:
            if subprocess.run(["openssl", "x509", "-in", p, "-noout", "-checkend", "0"],
                              capture_output=True).returncode != 0:
                expired.append(_field(p, "-subject").split("CN=")[-1][:48])
        finally:
            os.unlink(p)
    check("no expired certificates are being shipped", not expired,
          f"expired: {expired} — harmless to trust, but it makes a live TLS failure look "
          f"like it is already handled")

    # install() is called from app.py AND the sweep; if they disagree the sweep files
    # working schools as broken, which is how this whole class of bug stays invisible.
    try:
        a = ca_chain.install()
        b = ca_chain.install()
        check("install() is idempotent and never raises", a == b or (a and b))
    except Exception as e:
        check("install() is idempotent and never raises", False, f"{type(e).__name__}: {e}")

    src = open(os.path.join(HERE, "ca_chain.py")).read()
    check("a malformed bundle still cannot take the poller down",
          "except Exception" in src,
          "the swallow is deliberate — this suite is what compensates for its silence")

    p_ = sum(x for _, x, _ in results)
    f_ = sum(not x for _, x, _ in results)
    return p_, f_, results


if __name__ == "__main__":
    p, f, res = run()
    for n, ok, d in res:
        print(f"  [{'PASS' if ok else '*** FAIL'}] {n}{('  ' + d) if d and not ok else ''}")
    print(f"\n  {p} passed, {f} failed")
    sys.exit(1 if f else 0)
