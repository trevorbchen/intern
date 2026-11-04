from internbot import harvest, bank


def test_extract_questions_from_form(browser, mock_site):
    base, _ = mock_site
    pg = browser.new_page()
    try:
        pg.goto(base + "/essay")
        pg.wait_for_selector("form")
        found = harvest.extract(pg, "MockCo")
    finally:
        pg.close()
    by = {f["q"]: f for f in found}
    assert "first name" not in by and "email" not in by and "resume" not in by      # identity fields skipped
    auth = by["are you legally authorized to work in the us"]
    assert auth["type"] == "select" and auth["options"] == ["Yes", "No"] and auth["required"]
    combo = by["have you ever worked at {company} before"]                          # company name templated
    assert combo["type"] == "dropdown" and combo["options"] == ["Yes", "No"]
    assert by["why do you want to join {company}"]["type"] == "essay"


def test_bank_merge_lookup_and_company_template(tmp_path):
    entries = bank.merge([], [dict(q="why do you want to join {company}", type="essay", options=[], required=True, company="A"),
                              dict(q="why do you want to join {company}", type="essay", options=[], required=True, company="B")])
    assert entries[0]["seen"] == 2 and entries[0]["companies"] == ["A", "B"]
    entries[0]["answer"] = "Because."
    assert bank.lookup(entries, "Why do you want to join Anthropic?*") == "Because."
    assert bank.lookup(entries, "Something unrelated") is None
    p = str(tmp_path / "a.yaml")
    bank.save(entries, p)
    assert bank.load(p)[0]["answer"] == "Because."
