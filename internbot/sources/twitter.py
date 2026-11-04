"""Tweets announcing research internships, found by crawling X's website with a headless browser.

No official API. X shows a login wall to logged-out visitors, so for reliable results export
cookies from YOUR OWN logged-in browser session:
    X_AUTH_TOKEN=<auth_token cookie>   X_CT0=<ct0 cookie>
Scraping X violates its ToS and can get the account rate-limited or suspended; use a throwaway
account, keep volume low. Without cookies we still try (usually yields nothing).
"""
import os, random, time
from urllib.parse import quote
from ..models import Posting

SEARCH = "https://x.com/search?q={q}&src=typed_query&f=live"


def _cookies():
    out = []
    for name, env in (("auth_token", "X_AUTH_TOKEN"), ("ct0", "X_CT0")):
        if os.environ.get(env):
            out.append({"name": name, "value": os.environ[env], "domain": ".x.com", "path": "/",
                        "secure": True, "httpOnly": name == "auth_token"})
    return out


def fetch(cfg):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[twitter] playwright not installed (pip install playwright)")
        return
    cookies = _cookies()
    if not cookies:
        print("[twitter] no X_AUTH_TOKEN/X_CT0 set; logged-out X usually blocks search")
    with sync_playwright() as pw:
        exe = os.environ.get("CHROMIUM_PATH")
        browser = pw.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        ctx = browser.new_context(viewport={"width": 1280, "height": 1800}, locale="en-US",
                                  user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        if cookies:
            ctx.add_cookies(cookies)
        page = ctx.new_page()
        for q in cfg.get("queries", []):
            try:
                page.goto(SEARCH.format(q=quote(q)), wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector("article[data-testid='tweet']", timeout=15000)
                for _ in range(cfg.get("scrolls", 3)):
                    page.mouse.wheel(0, 2500)
                    time.sleep(random.uniform(1.5, 3))
                tweets = page.query_selector_all("article[data-testid='tweet']")
            except Exception as e:
                print(f"[twitter] '{q[:40]}' no results ({type(e).__name__}) - login wall?")
                continue
            for t in tweets:
                try:
                    text = (t.query_selector("[data-testid='tweetText']") or t).inner_text()
                    link = t.query_selector("a[href*='/status/'] time")
                    status = link.evaluate("e => e.closest('a').href") if link else ""
                    posted = link.get_attribute("datetime") if link else ""
                    ext = [a.get_attribute("href") for a in t.query_selector_all("a[href^='https://t.co/']")]
                    url = status or (ext[0] if ext else "")
                    if url:
                        yield Posting("twitter", text.replace("\n", " ")[:120], "(tweet)", url,
                                      "", text, posted or "")
                except Exception:
                    continue
            time.sleep(random.uniform(4, 8))
        browser.close()
