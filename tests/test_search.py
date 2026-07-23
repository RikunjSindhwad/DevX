"""Tests for web search: duckduckgo, bing, yahoo, multi-engine, fallback, rrf."""
from helpers import dx, run, _Resp, _engine_urlopen


def test_search_parses_duckduckgo_results(ws, capsys, monkeypatch):
    html = ('<div class="result results_links"><a class="result__a" href="//duckduckgo.com/l/?uddg='
            'https%3A%2F%2Fdocs.python.org%2F3%2F&rut=x">Python Docs</a>'
            '<a class="result__snippet">Docs snippet</a></div>')

    class Resp:
        def read(self): return html.encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(dx.urllib.request, "urlopen", lambda *a, **k: Resp())
    res, _ = run(capsys, "search", "python docs")
    assert res["ok"] and res["count"] >= 1 and "docs.python.org" in res["results"][0]["url"]


def test_rrf_fuses_and_dedupes():
    from lib.fetch.web_search import rrf
    fused = rrf([[{"url": "u1"}, {"url": "u2"}], [{"url": "u2"}, {"url": "u3"}]])
    urls = [r["url"] for r in fused]
    assert urls.count("u2") == 1 and urls[0] == "u2"             # deduped; ranked-high-in-both wins
    assert set(urls) == {"u1", "u2", "u3"}


def test_search_bing_parser(monkeypatch):
    from lib.fetch import web_search as wsm
    bing = '<li class="b_algo"><h2><a href="https://nodejs.org/api/">Node</a></h2></li>'
    monkeypatch.setattr(wsm.urllib.request, "urlopen", _engine_urlopen(bing=bing))
    res = wsm._bing("node", 5)
    assert res and res[0]["url"] == "https://nodejs.org/api/"


def test_search_yahoo_parser(monkeypatch):
    from lib.fetch import web_search as wsm
    yahoo = ('<div class="dd fst lst algo"><a href="https://r.search.yahoo.com/x/RU='
             'https%3A%2F%2Fvite.dev%2Fguide%2Fenv-and-mode/RK=2"><h3>Vite Env</h3></a>'
             '<div class="compText"><p>Snippet</p></div></div></li><li>')
    monkeypatch.setattr(wsm.urllib.request, "urlopen", _engine_urlopen(yahoo=yahoo))
    res = wsm._yahoo("vite", 5)
    assert res and res[0]["url"] == "https://vite.dev/guide/env-and-mode"


def test_search_multi_engine_rrf_dedupes(ws, capsys, monkeypatch):
    ddg = ('<div class="result results_links"><a class="result__a" '
           'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.python.org%2F3%2F&x=1">Py</a></div>')
    bing = '<li class="b_algo"><h2><a href="https://docs.python.org/3/">Py</a></h2></li>'
    monkeypatch.setattr(dx.urllib.request, "urlopen", _engine_urlopen(ddg=ddg, bing=bing))
    res, _ = run(capsys, "search", "python", "--engines", "duckduckgo,bing")
    assert res["ok"] and res["count"] == 1                       # same URL fused/deduped across engines
    assert set(res["engines"]) == {"duckduckgo", "bing"}


def test_search_default_uses_multi_engine_fallback(ws, capsys, monkeypatch):
    yahoo = '<div class="dd fst lst algo"><a href="https://crates.io/"><h3>Crate</h3></a></div></li><li>'
    monkeypatch.setattr(dx.urllib.request, "urlopen", _engine_urlopen(ddg="", bing="", yahoo=yahoo))
    res, _ = run(capsys, "search", "rust crate")                 # default queries ddg + bing + yahoo
    assert res["ok"] and res["count"] == 1 and "yahoo" in res["engines"]


def test_search_unknown_and_erroring_engines():
    from lib.fetch import web_search as wsm
    orig = dict(wsm.ENGINES)
    wsm.ENGINES["bad"] = lambda q, lim: (_ for _ in ()).throw(RuntimeError("down"))
    try:
        res = wsm.search("q", engines=["nope", "bad"])            # unknown + raising → no results
    finally:
        wsm.ENGINES.clear(); wsm.ENGINES.update(orig)
    assert res["ok"] is False and "errors" in res


def test_rrf_normalizes_urls_for_dedupe():
    from lib.fetch.web_search import rrf
    fused = rrf([[{"url": "https://docs.python.org/3/library/os.html"}],
                 [{"url": "https://docs.python.org/3/library/os.html?utm_source=bing"}],
                 [{"url": "https://DOCS.python.org/3/library/os.html/"}]])
    assert len(fused) == 1                                        # trailing-slash / tracking / case → one canonical
