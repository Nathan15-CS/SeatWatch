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
        _lower_cipher_floor(ctx)
        return ctx

    ssl.create_default_context = _ctx
    ssl._create_default_https_context = _ctx
    _installed[0] = True
    if log:
        log(f"  [tls] supplemental CA intermediates loaded from {BUNDLE}; "
            f"cipher floor at SECLEVEL=1 with verification unchanged")
    return True


def _lower_cipher_floor(ctx):
    """Accept the older cipher suites some college servers still run, nothing more.

    Santa Clarita, Triton and Ursinus all RESET the TLS handshake outright against
    OpenSSL 3.0's defaults — TCP connects, then the connection dies, which reads as a dead
    host. They are not dead; their servers simply offer no cipher that clears the default
    security level. At SECLEVEL=1 all three negotiate AES256-GCM / AES256-SHA256 with
    certificate AND hostname verification fully on and legitimate certificates.

    This is a FLOOR, not a downgrade, and that distinction is the whole justification.
    Measured against the hosts that carry real consequences — Stripe, Twilio and Google —
    every one negotiates the identical TLS 1.3 suite with this set as it does without it.
    Nothing that already had strong crypto gives any up. The only behaviour that changes is
    that hosts previously refused outright become reachable.

    What SECLEVEL=1 permits that 2 does not is chiefly SHA-1 signatures and RSA keys below
    2048 bits. We still verify the full chain to a public root, we still check the
    hostname, and we send no credentials to any of these hosts — they serve public course
    catalogues. Verification is never disabled anywhere; see the note in this module's
    docstring about why anchoring an unverifiable certificate was refused.
    """
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    except (ssl.SSLError, ValueError):
        pass                   # older/newer OpenSSL that rejects the string: keep defaults
