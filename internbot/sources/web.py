"""Public job-board APIs (Greenhouse, Lever) and RSS feeds."""
import feedparser
from bs4 import BeautifulSoup
from . import get
from ..models import Posting


def _text(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def greenhouse(token):
    data = get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs").json()
    for j in data.get("jobs", []):
        yield Posting("greenhouse", j["title"], token, j["absolute_url"],
                      (j.get("location") or {}).get("name", ""), "", j.get("updated_at", ""))


def lever(company):
    for j in get(f"https://api.lever.co/v0/postings/{company}?mode=json").json():
        yield Posting("lever", j["text"], company, j["hostedUrl"],
                      (j.get("categories") or {}).get("location", "") or "",
                      j.get("descriptionPlain", ""), str(j.get("createdAt", "")))


def rss(url):
    feed = feedparser.parse(get(url).content)
    for e in feed.entries:
        yield Posting("rss", e.get("title", ""), feed.feed.get("title", url), e.get("link", ""),
                      "", _text(e.get("summary", "")), e.get("published", ""))


def fetch(cfg):
    for t in cfg.get("greenhouse", []):
        yield from _safe(greenhouse, t)
    for c in cfg.get("lever", []):
        yield from _safe(lever, c)
    for u in cfg.get("rss", []):
        yield from _safe(rss, u)


def _safe(fn, arg):
    try:
        yield from fn(arg)
    except Exception as e:
        print(f"[web] {fn.__name__}({arg}) failed: {e}")
