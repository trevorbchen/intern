import pytest
pw = pytest.importorskip("playwright.sync_api")
import os
from internbot.sources.twitter import parse_tweet

HTML = """<article data-testid="tweet"><div data-testid="User-Name">Prof Smith @prof_smith</div>
<a href="https://x.com/prof_smith/status/123"><time datetime="2026-11-01T10:00:00Z">1h</time></a>
<div data-testid="tweetText">Hiring a research intern for summer! Apply: </div>
<a href="https://t.co/abc">lab.edu/apply-form</a><a href="https://t.co/zzz">…</a></article>"""


def test_parse():
    with pw.sync_playwright() as p:
        exe = os.environ.get("CHROMIUM_PATH")
        b = p.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        pg = b.new_page(); pg.set_content(HTML)
        post = parse_tweet(pg.query_selector("article"))
        b.close()
    assert post.handle == "@prof_smith"
    assert post.apply_url == "https://lab.edu/apply-form"
    assert post.url.endswith("/status/123")
