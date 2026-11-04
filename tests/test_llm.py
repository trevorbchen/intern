import types
from internbot import llm


def fake(text):
    b = types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(messages=types.SimpleNamespace(
        create=lambda **kw: types.SimpleNamespace(content=[b])))


def test_text_answer():
    assert llm.answer("Why us?", None, {}, "job", client=fake("Because research.")) == "Because research."


def test_needs_human_is_none():
    assert llm.answer("Gender?", None, {}, "job", client=fake("NEEDS_HUMAN")) is None


def test_option_must_be_real():
    assert llm.answer("Q", ["Yes", "No"], {}, "", client=fake("yes")) == "Yes"
    assert llm.answer("Q", ["Yes", "No"], {}, "", client=fake("Maybe")) is None


def test_outreach_draft(tmp_path, monkeypatch):
    from internbot import outreach
    from internbot.models import Posting
    monkeypatch.chdir(tmp_path)
    p = Posting("ashby", "Research Intern", "Cohere", "https://x/1", "Toronto", "LLM research")
    outreach.draft_all([p], None, client=fake("SUBJECT: Hi\nbody"), path="out/o.md")
    assert "Cohere" in (tmp_path / "out/o.md").read_text() and "SUBJECT: Hi" in (tmp_path / "out/o.md").read_text()
