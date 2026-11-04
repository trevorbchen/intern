from internbot.sources.twitter import parse_tweet

TWEET = """<article data-testid="tweet"><div data-testid="User-Name">Prof Smith @prof_smith</div>
<a href="https://x.com/prof_smith/status/123"><time datetime="2026-11-01T10:00:00Z">1h</time></a>
<div data-testid="tweetText">Hiring a research intern for summer! Apply: </div>
<a href="https://t.co/abc">lab.edu/apply-form</a><a href="https://t.co/zzz">…</a></article>"""

NO_LINK = """<article data-testid="tweet"><a href="https://x.com/someone/status/9"><time datetime="2026-11-02T10:00:00Z">2h</time></a>
<div data-testid="tweetText">DM me about our ML internship</div></article>"""

JUNK = """<article data-testid="tweet"><div>promoted, no status link</div></article>"""


def parse(browser, html):
    pg = browser.new_page()
    try:
        pg.set_content(html)
        return parse_tweet(pg.query_selector("article"))
    finally:
        pg.close()


def test_handle_and_apply_link(browser):
    post = parse(browser, TWEET)
    assert post.handle == "@prof_smith" and post.apply_url == "https://lab.edu/apply-form"
    assert post.url.endswith("/status/123") and post.posted == "2026-11-01T10:00:00Z"


def test_tweet_without_link_still_has_handle(browser):
    post = parse(browser, NO_LINK)
    assert post.handle == "@someone" and post.apply_url == ""


def test_junk_tweet_is_ignored(browser):
    assert parse(browser, JUNK) is None


def test_no_credentials_means_no_crash(monkeypatch, capsys):
    from internbot.sources import twitter
    for k in ("X_AUTH_TOKEN", "X_CT0", "X_USERNAME", "X_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(twitter, "STATE", "/nonexistent/state.json")
    monkeypatch.setitem(__import__("sys").modules, "playwright.sync_api", None)  # simulate playwright missing
    assert list(twitter.fetch({"queries": ["x"]})) == []
