"""Free extra sources: careers-page watcher (companies with no public job API) and Hacker News 'Who is hiring'."""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from . import get
from ..models import Posting

KW = re.compile(r"intern|research|fellow|residen|scholar", re.I)


def careers_pages(pages):
    """pages: [{name, url}] -> Posting per link whose text looks like an intern/research role."""
    for pg in pages:
        try:
            soup = BeautifulSoup(get(pg["url"], headers={"User-Agent": "Mozilla/5.0"}).text, "html.parser")
        except Exception as e:
            print(f"[pages] {pg['name']} failed: {type(e).__name__}")
            continue
        seen = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            if 8 <= len(text) <= 140 and KW.search(text):
                url = urljoin(pg["url"], a["href"])
                if url not in seen:
                    seen.add(url)
                    yield Posting("careers-page", text, pg["name"], url, "", text)


def hn_hiring(months=2):
    """Latest 'Ask HN: Who is hiring?' threads (free Algolia API, no key). Company = text before first '|'."""
    q = get("https://hn.algolia.com/api/v1/search_by_date", params={
        "query": "Ask HN: Who is hiring?", "tags": "story,author_whoishiring", "hitsPerPage": months}).json()
    for story in q.get("hits", []):
        if "who is hiring" not in (story.get("title") or "").lower():
            continue
        item = get(f"https://hn.algolia.com/api/v1/items/{story['objectID']}").json()
        for c in item.get("children", []):
            html = c.get("text") or ""
            text = BeautifulSoup(html.replace("<p>", "\n"), "html.parser").get_text(" ", strip=True)
            first = text.split("|")[0].strip()
            if not text or len(first) > 60:
                continue
            title = " | ".join(x.strip() for x in text.split("|")[1:3]) or text[:100]
            yield Posting("hn", title[:140], first, f"https://news.ycombinator.com/item?id={c['id']}", "", text[:4000])
