"""Every source parser, with the network mocked out."""
import json, types
import pytest
from internbot.sources import web, linkedin, extra


class Resp:
    def __init__(self, data=None, text="", content=b""):
        self._d, self.text, self.content = data, text, content

    def json(self):
        return self._d


def patch_get(monkeypatch, mod, mapping):
    def fake(url, **kw):
        for k, v in mapping.items():
            if k in url:
                return v
        raise AssertionError("unexpected url " + url)
    monkeypatch.setattr(mod, "get", fake)


def test_greenhouse(monkeypatch):
    patch_get(monkeypatch, web, {"greenhouse": Resp({"jobs": [{"title": "ML Intern", "absolute_url": "https://g/1",
              "location": {"name": "NYC"}, "updated_at": "2026-10-01"}]})})
    p = list(web.greenhouse("tok"))[0]
    assert (p.source, p.title, p.location, p.url) == ("greenhouse", "ML Intern", "NYC", "https://g/1")


def test_lever(monkeypatch):
    patch_get(monkeypatch, web, {"lever": Resp([{"text": "Research Intern", "hostedUrl": "https://l/1",
              "categories": {"location": "SF"}, "descriptionPlain": "LLMs", "createdAt": 1760000000000}])})
    p = list(web.lever("co"))[0]
    assert p.title == "Research Intern" and p.description == "LLMs" and p.posted == "1760000000000"


def test_ashby(monkeypatch):
    patch_get(monkeypatch, web, {"ashbyhq": Resp({"jobs": [{"title": "AI Residency", "jobUrl": "https://a/1",
              "location": "SF", "descriptionPlain": "x", "publishedAt": "2026-10-01T00:00:00Z"}]})})
    p = list(web.ashby("tok", "Display Name"))[0]
    assert p.company == "Display Name" and p.source == "ashby"


def test_rss(monkeypatch):
    xml = b"""<rss version="2.0"><channel><title>Jobs</title><item><title>Research Intern</title>
    <link>https://r/1</link><description>&lt;p&gt;LLM team&lt;/p&gt;</description></item></channel></rss>"""
    patch_get(monkeypatch, web, {"feed": Resp(content=xml)})
    p = list(web.rss("https://feed.example/rss"))[0]
    assert p.title == "Research Intern" and "LLM team" in p.description and "<p>" not in p.description


def test_fetch_targets_sets_display_company_and_survives_failures(monkeypatch):
    def fake_ashby(tok, name=None):
        yield web.Posting("ashby", "AI Intern", tok, "https://a/2")
    monkeypatch.setattr(web, "ashby", fake_ashby)
    monkeypatch.setattr(web, "greenhouse", lambda t: (_ for _ in ()).throw(RuntimeError("boom")))
    out = list(web.fetch_targets([{"name": "Good Co", "ats": "ashby", "token": "g"},
                                  {"name": "Bad Co", "ats": "greenhouse", "token": "b"}]))
    assert [p.company for p in out] == ["Good Co"]


LI_HTML = """<ul><li><a class="base-card__full-link" href="https://linkedin.com/jobs/view/1?x=2"></a>
<h3 class="base-search-card__title"> Research Intern </h3><h4 class="base-search-card__subtitle">Scale</h4>
<span class="job-search-card__location">SF</span><time datetime="2026-10-20"></time></li>
<li><div>broken card</div></li></ul>"""


def test_linkedin_parse_and_pagination(monkeypatch):
    calls = []

    def fake(url, **kw):
        calls.append(url)
        return Resp(text=LI_HTML if "start=0" in url else "")
    monkeypatch.setattr(linkedin, "get", fake)
    monkeypatch.setattr(linkedin.time, "sleep", lambda s: None)
    out = list(linkedin.fetch({"searches": ["research intern"], "pages": 3, "location": "United States"}))
    assert len(out) == 1 and out[0].company == "Scale" and out[0].posted == "2026-10-20"
    assert len(calls) == 2 and "f_E=1" in calls[0]  # stops at the first empty page


def test_linkedin_http_error_is_contained(monkeypatch):
    monkeypatch.setattr(linkedin, "get", lambda u, **k: (_ for _ in ()).throw(RuntimeError("429")))
    monkeypatch.setattr(linkedin.time, "sleep", lambda s: None)
    assert list(linkedin.fetch({"searches": ["a", "b"], "pages": 2})) == []


def test_careers_pages(monkeypatch):
    html = ('<a href="/jobs/1">Research Intern, Vision</a><a href="/about">About us</a><a href="/x">Research</a>'
            '<a href="/jobs/1">Research Intern, Vision</a><a href="/jobs/2">AI Residency Program 2027</a>')
    monkeypatch.setattr(extra, "get", lambda u, **k: Resp(text=html))
    out = list(extra.careers_pages([{"name": "Acme", "url": "https://acme.com/careers"}]))
    assert [p.title for p in out] == ["Research Intern, Vision", "AI Residency Program 2027"]  # deduped, nav links skipped
    assert out[0].url == "https://acme.com/jobs/1" and out[0].company == "Acme"


def test_hn_hiring(monkeypatch):
    def fake(url, **kw):
        if "search_by_date" in url:
            return Resp({"hits": [{"objectID": "9", "title": "Ask HN: Who is hiring? (November 2026)"},
                                  {"objectID": "8", "title": "Something else"}]})
        return Resp({"children": [{"id": 5, "text": "Cohere | Research Intern | Toronto<p>LLM stuff"},
                                  {"id": 6, "text": "x" * 200}, {"id": 7, "text": ""}]})
    monkeypatch.setattr(extra, "get", fake)
    out = list(extra.hn_hiring())
    assert len(out) == 1 and out[0].company == "Cohere" and "Research Intern" in out[0].title
    assert out[0].url.endswith("id=5")
