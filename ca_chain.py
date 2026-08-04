"""Supply CA intermediates that colleges' own servers fail to send.

Nine schools looked dead and were not. Their registration servers present only their own
certificate and omit the intermediate that links it to a public root. A browser hides this
by fetching the missing link from the pointer inside the certificate ("AIA chasing");
Python does not, so verification failed against sites a student opens without complaint,
and the sweep filed the school as broken.

ops/edu-intermediates.pem holds those missing links. Every certificate in it was verified
against the system store on its own before inclusion, so this adds NO new trust — they are
links we already trust that the colleges neglected to send. One candidate chained to
nothing and was dropped: it arrived over plain HTTP, and anchoring it would have meant
trusting whatever it had ever signed.

load_verify_locations ADDS to the system store rather than replacing it, so nothing that
verified before can stop verifying. Certificate and hostname checking stay fully on.

Imported by both app.py (so the poller can reach these schools) and ops/sweep-schools.py
(so the sweep judges them under the same conditions the poller runs in — otherwise the
sweep would keep filing working schools as broken).
"""
import os
import ssl

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.environ.get("CA_EXTRA", os.path.join(HERE, "ops", "edu-intermediates.pem"))
_installed = [False]


def install(log=None):
    """Make the supplemental intermediates part of the default TLS trust. Idempotent.

    Returns True if applied. A missing bundle is not an error — it just means ordinary
    verification, which is exactly what happens on a machine that has not fetched it.
    """
    if _installed[0] or not os.path.exists(BUNDLE):
        return _installed[0]
    base = ssl.create_default_context

    def _ctx(*a, **k):
        ctx = base(*a, **k)
        try:
            ctx.load_verify_locations(cafile=BUNDLE)
        except Exception:
            pass               # a malformed bundle must never take the poller down
        return ctx

    ssl.create_default_context = _ctx
    ssl._create_default_https_context = _ctx
    _installed[0] = True
    if log:
        log(f"  [tls] loaded supplemental CA intermediates from {BUNDLE}")
    return True
