"""LinkedIn public (logged-out) job search pages.

NOTE: LinkedIn's ToS restricts automated scraping. This only reads the public guest
listing, with delays and low volume, no login. LinkedIn may block or change it at any time.
Use at your own risk / for personal use.
"""
import time
from urllib.parse import quote
from bs4 import BeautifulSoup
from . import get
from ..models import Posting

BASE = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


def fetch(cfg):
    delay = cfg.get("delay_seconds", 3)
    for q in cfg.get("searches", []):
        for page in range(cfg.get("pages", 1)):
            url = (f"{BASE}?keywords={quote(q)}&location={quote(cfg.get('location', ''))}"
                   f"&f_E=1&start={page * 25}")  # f_E=1 -> Internship experience level
            try:
                html = get(url).text
            except Exception as e:
                print(f"[linkedin] '{q}' page {page} failed: {e}")
                break
            cards = BeautifulSoup(html, "html.parser").select("li")
            if not cards:
                break
            for li in cards:
                a = li.select_one("a.base-card__full-link")
                t = li.select_one(".base-search-card__title")
                if not (a and t):
                    continue
                co = li.select_one(".base-search-card__subtitle")
                loc = li.select_one(".job-search-card__location")
                dt = li.select_one("time")
                yield Posting("linkedin", t.get_text(strip=True),
                              co.get_text(strip=True) if co else "", a["href"],
                              loc.get_text(strip=True) if loc else "", "",
                              dt.get("datetime", "") if dt else "")
            time.sleep(delay)
