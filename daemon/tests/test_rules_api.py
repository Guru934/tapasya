import json
import threading
import urllib.request
import urllib.error

from tapasya import api, rules
from tapasya.tracker import decide

SITES = {
    "allow": ["docs.python.org", "github.com"],
    "block": ["instagram.com"],
    "mixed": ["youtube.com"],
    "study_keywords": ["tutorial", "lecture"],
}


def test_rules():
    c = lambda d, t="", s=False: rules.classify(d, t, s, SITES)[0]
    assert c("docs.python.org")
    assert c("gist.github.com")                 # subdomain of allowed
    assert not c("instagram.com")
    assert not c("www.instagram.com")
    assert not c("randomsite.com")              # unknown = not counted
    assert not c("")                            # internal page / no domain
    assert c("www.youtube.com", "Python Tutorial for beginners")
    assert not c("www.youtube.com", "funny cats")
    assert not c("www.youtube.com", "Python tutorial", s=True)   # shorts never count


def test_tab_staleness():
    st = api.TabState(stale_seconds=90)
    assert st.current(now=0) is None
    st.update("github.com", "x", False, now=100)
    assert st.current(now=150)["domain"] == "github.com"
    assert st.current(now=200) is None


def _cfg(require=True):
    return {"tracking": {"study_window_classes": ["brave-browser"], "browser_classes": ["brave-browser"],
                         "require_extension": require}, "study_sites": SITES}


def test_decide():
    tab = lambda d, t="": {"domain": d, "title": t, "shorts": False}
    # Default require_extension is now True (fail closed)
    assert decide("brave-browser", False, tab("github.com"), _cfg())[0] is True
    assert decide("brave-browser", False, tab("instagram.com"), _cfg())[0] is False
    assert decide("brave-browser", True, tab("github.com"), _cfg())[0] is False      # idle
    assert decide("discord", False, tab("github.com"), _cfg())[0] is False
    # Default require_extension is now True (fail closed) - None tab should not count
    assert decide("brave-browser", False, None, _cfg())[0] is False
    # Explicit false still allows fallback
    assert decide("brave-browser", False, None, _cfg(require=False))[0] is True
    assert decide("brave-browser", False, None, _cfg(require=True))[0] is False


def test_decide_require_extension_defaults_to_true():
    """Default config (no require_extension key) should fail closed."""
    cfg_no_require = {"tracking": {"study_window_classes": ["brave-browser"], "browser_classes": ["brave-browser"]},
                      "study_sites": SITES}
    assert decide("brave-browser", False, None, cfg_no_require)[0] is False
    # But valid tab should still count
    assert decide("brave-browser", False, {"domain": "github.com", "title": "x", "shorts": False}, cfg_no_require)[0] is True


def test_decide_stale_report_does_not_count():
    """Stale extension report (simulated by None tab) should not count when require_extension=true."""
    cfg = _cfg(require=True)
    assert decide("brave-browser", False, None, cfg)[0] is False


def test_decide_blocked_domain_never_counts():
    cfg = _cfg()
    tab = lambda d: {"domain": d, "title": "x", "shorts": False}
    assert decide("brave-browser", False, tab("instagram.com"), cfg)[0] is False
    assert decide("brave-browser", False, tab("www.instagram.com"), cfg)[0] is False


def test_decide_unknown_domain_never_counts():
    cfg = _cfg()
    tab = lambda d: {"domain": d, "title": "x", "shorts": False}
    assert decide("brave-browser", False, tab("randomsite.com"), cfg)[0] is False


def test_decide_empty_domain_never_counts():
    cfg = _cfg()
    assert decide("brave-browser", False, {"domain": "", "title": "x", "shorts": False}, cfg)[0] is False
    assert decide("brave-browser", False, {"domain": "   ", "title": "x", "shorts": False}, cfg)[0] is False


def test_decide_counts_an_audible_allowed_tab_while_idle():
    tab = {"domain": "github.com", "title": "lecture notes", "shorts": False, "audible": True}
    assert decide("brave-browser", True, tab, _cfg())[0] is True


def test_tab_state_ignores_empty_domain():
    """Empty domain reports should not overwrite valid state in TabState."""
    st = api.TabState(stale_seconds=90)
    st.update("github.com", "repo", False, False, now=100)
    assert st.current(now=150)["domain"] == "github.com"

    # Empty domain report (e.g., from focus loss) should be ignored
    st.update("", "x", False, False, now=150)
    assert st.current(now=180)["domain"] == "github.com"

    # Whitespace-only domain should also be ignored
    st.update("   ", "x", False, False, now=180)
    assert st.current(now=185)["domain"] == "github.com"

    # But a new valid domain should update the state
    st.update("docs.python.org", "docs", False, False, now=185)
    assert st.current(now=200)["domain"] == "docs.python.org"


def test_tab_state_staleness_still_works():
    """State should still become stale after the configured timeout."""
    st = api.TabState(stale_seconds=90)
    st.update("github.com", "x", False, now=100)
    assert st.current(now=150)["domain"] == "github.com"
    assert st.current(now=200) is None  # stale after 90 seconds


def test_tab_state_eligible_false_clears_state():
    """Explicit eligible=false should immediately clear the tab state."""
    st = api.TabState(stale_seconds=90)
    st.update("github.com", "repo", False, False, now=100)
    assert st.current(now=150)["domain"] == "github.com"

    # Explicit eligible=false should clear state immediately
    st.update("", "x", False, False, eligible=False, now=200)
    assert st.current(now=250) is None

    # After clearing, a new valid domain should work
    st.update("docs.python.org", "docs", False, False, eligible=True, now=300)
    assert st.current(now=350)["domain"] == "docs.python.org"


def test_tab_state_eligible_true_updates_state():
    """Explicit eligible=true with valid domain should update state."""
    st = api.TabState(stale_seconds=90)
    st.update("github.com", "repo", False, False, now=100)
    assert st.current(now=150)["domain"] == "github.com"

    # Explicit eligible=true with new domain should update
    st.update("docs.python.org", "docs", False, False, eligible=True, now=200)
    assert st.current(now=250)["domain"] == "docs.python.org"


def test_tab_state_backward_compat_empty_domain_ignored():
    """Empty domain without eligible flag should be ignored (backward compat)."""
    st = api.TabState(stale_seconds=90)
    st.update("github.com", "repo", False, False, now=100)
    assert st.current(now=110)["domain"] == "github.com"

    # Empty domain without eligible flag should be ignored (backward compat)
    st.update("", "x", False, False, eligible=None, now=120)
    assert st.current(now=130)["domain"] == "github.com"


def test_api_origin_and_update():
    st = api.TabState()
    server = api.make_server(st, "127.0.0.1", 0, lambda: {"ok": 1})
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/v1/tab"
    body = json.dumps({"domain": "github.com", "title": "repo", "shorts": False, "audible": True, "eligible": True}).encode()

    def post(origin):
        h = {"Content-Type": "application/json"}
        if origin:
            h["Origin"] = origin
        return urllib.request.Request(url, data=body, headers=h, method="POST")

    try:
        urllib.request.urlopen(post("https://evil.example"))
        assert False, "should be rejected"
    except urllib.error.HTTPError as e:
        assert e.code == 403
    assert urllib.request.urlopen(post("chrome-extension://abcdef")).status == 204
    assert st.current()["domain"] == "github.com"
    assert st.current()["audible"] is True
    assert json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/status")) == {"ok": 1}
    server.shutdown()
