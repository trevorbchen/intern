"""Apply flow against a local mock application form: fill, gating, and the real submit path."""
import types
from internbot.apply import apply_to


def run(browser, url, profile, submit, tmp_path, llm_client=None):
    page = browser.new_page()
    try:
        return apply_to(page, url, profile, submit, shot_dir=str(tmp_path / "shots"), llm_client=llm_client)
    finally:
        page.close()


def fake_llm(answer):
    b = types.SimpleNamespace(type="text", text=answer)
    return types.SimpleNamespace(messages=types.SimpleNamespace(
        create=lambda **kw: types.SimpleNamespace(content=[b])))


def test_dry_run_fills_but_never_submits(browser, mock_site, profile, tmp_path):
    base, posts = mock_site
    posts.clear()
    status, note = run(browser, base + "/basic", profile, False, tmp_path)
    assert status == "filled" and not posts


def test_submit_path_submits_when_everything_filled(browser, mock_site, profile, tmp_path):
    base, posts = mock_site
    posts.clear()
    status, note = run(browser, base + "/basic", profile, True, tmp_path)
    assert status == "submitted", note
    assert posts == ["/submit"]


def test_unknown_required_question_blocks_submit(browser, mock_site, profile, tmp_path):
    base, posts = mock_site
    posts.clear()
    status, note = run(browser, base + "/unknown", profile, True, tmp_path)
    assert status == "needs_manual" and "obscure" in note and not posts


def test_captcha_blocks_submit(browser, mock_site, profile, tmp_path):
    base, posts = mock_site
    posts.clear()
    status, note = run(browser, base + "/captcha", profile, True, tmp_path)
    assert status == "needs_manual" and "captcha" in note and not posts


def test_llm_answers_need_review_before_submit(browser, mock_site, profile, tmp_path):
    base, posts = mock_site
    posts.clear()
    status, note = run(browser, base + "/essay", profile, True, tmp_path, fake_llm("Because I like your research."))
    assert status == "needs_review" and "Claude answered" in note and not posts


def test_llm_answers_submit_when_allowed(browser, mock_site, profile, tmp_path):
    base, posts = mock_site
    posts.clear()
    profile["apply"]["submit_llm_answers"] = True
    status, note = run(browser, base + "/essay", profile, True, tmp_path, fake_llm("Because I like your research."))
    assert status == "submitted", note
    assert posts == ["/submit"]


def test_llm_needs_human_leaves_blank(browser, mock_site, profile, tmp_path):
    base, posts = mock_site
    status, note = run(browser, base + "/essay", profile, True, tmp_path, fake_llm("NEEDS_HUMAN"))
    assert status == "needs_manual"


def test_question_bank_answers_used(browser, mock_site, profile, tmp_path, monkeypatch):
    from internbot import bank
    monkeypatch.chdir(tmp_path)
    bank.save([{"q": "what is your favourite obscure thing", "type": "text", "seen": 1, "answer": "Moss"}])
    base, posts = mock_site
    posts.clear()
    status, note = run(browser, base + "/unknown", profile, True, tmp_path)
    assert status == "submitted", note


def test_run_applications_skips_non_ats_urls(tmp_path, profile, monkeypatch):
    from internbot.db import DB
    from internbot.apply import run_applications
    from internbot.models import Posting
    db = DB(":memory:")
    run_applications([Posting("linkedin", "Research Intern", "Co", "https://linkedin.com/jobs/1")], profile, db)
    assert db.applications()[0][1] == "needs_manual"
