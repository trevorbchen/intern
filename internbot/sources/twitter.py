"""Tweets announcing research internships via the official X API v2 (recent search)."""
import os
from . import get
from ..models import Posting


def fetch(cfg):
    token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not token:
        print("[twitter] TWITTER_BEARER_TOKEN not set, skipping")
        return
    for q in cfg.get("queries", []):
        try:
            data = get("https://api.twitter.com/2/tweets/search/recent",
                       headers={"Authorization": f"Bearer {token}"},
                       params={"query": q, "max_results": max(10, min(cfg.get("max_results", 50), 100)),
                               "tweet.fields": "created_at,entities,author_id"}).json()
        except Exception as e:
            print(f"[twitter] query failed: {e}")
            continue
        for t in data.get("data", []):
            urls = [u.get("expanded_url") for u in t.get("entities", {}).get("urls", [])
                    if u.get("expanded_url") and "twitter.com" not in u["expanded_url"]
                    and "x.com" not in u["expanded_url"]]
            link = urls[0] if urls else f"https://x.com/i/web/status/{t['id']}"
            yield Posting("twitter", t["text"].replace("\n", " ")[:120], "(tweet)", link,
                          "", t["text"], t.get("created_at", ""))
