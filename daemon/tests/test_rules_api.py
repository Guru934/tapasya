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


def _cfg(require=False):
    return {"tracking": {"study_window_classes": ["brave-browser"], "browser_classes": ["brave-browser"],
                         "require_extension": require}, "study_sites": SITES}


def test_decide():
    tab = lambda d, t="": {"domain": d, "title": t, "shorts": False}
    assert decide("brave-browser", False, tab("github.com"), _cfg())[0] is True
    assert decide("brave-browser", False, tab("instagram.com"), _cfg())[0] is False
    assert decide("brave-browser", True, tab("github.com"), _cfg())[0] is False      # idle
    assert decide("discord", False, tab("github.com"), _cfg())[0] is False
    assert decide("brave-browser", False, None, _cfg())[0] is True                   # fallback
    assert decide("brave-browser", False, None, _cfg(require=True))[0] is False


def test_decide_counts_an_audible_allowed_tab_while_idle():
    tab = {"domain": "github.com", "title": "lecture notes", "shorts": False, "audible": True}
    assert decide("brave-browser", True, tab, _cfg())[0] is True


def test_api_origin_and_update():
    st = api.TabState()
    server = api.make_server(st, "127.0.0.1", 0, lambda: {"ok": 1})
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/v1/tab"
    body = json.dumps({"domain": "github.com", "title": "repo", "shorts": False, "audible": True}).encode()

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
