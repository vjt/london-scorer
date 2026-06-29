from london_scorer import http

def test_get_json_caches_and_reuses(tmp_path, monkeypatch):
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    calls = {"n": 0}
    class R:
        def raise_for_status(self): pass
        def json(self): calls["n"] += 1; return {"ok": True}
    monkeypatch.setattr(http.requests, "get", lambda *a, **k: R())
    a = http.get_json("https://x/y", params={"q": 1})
    b = http.get_json("https://x/y", params={"q": 1})   # served from cache
    assert a == b == {"ok": True}
    assert calls["n"] == 1
