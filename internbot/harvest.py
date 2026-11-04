"""Read-only crawl of public application forms (never submits) to collect the questions companies ask."""
import os, random, re, time
from . import bank
from .apply import _full_label, _required, _combo_options
from .sources import get


def job_urls(cfg, per_board=4):
    pri = re.compile(r"intern|research|scientist|machine learning|\bML\b|\bAI\b", re.I)
    out = []
    for t in cfg.get("greenhouse", []):
        try:
            jobs = get(f"https://boards-api.greenhouse.io/v1/boards/{t}/jobs").json()["jobs"]
        except Exception:
            continue
        jobs.sort(key=lambda j: (not pri.search(j["title"]), random.random()))
        out += [(t, f"https://job-boards.greenhouse.io/{t}/jobs/{j['id']}") for j in jobs[:per_board]]
    for c in cfg.get("lever", []):
        try:
            jobs = get(f"https://api.lever.co/v0/postings/{c}?mode=json").json()
        except Exception:
            continue
        jobs.sort(key=lambda j: (not pri.search(j["text"]), random.random()))
        out += [(c, j["hostedUrl"].rstrip("/") + "/apply") for j in jobs[:per_board]]
    return out


def extract(page, company_name):
    found = []
    seen_radio = set()
    for el in page.query_selector_all("form input:not([type=file]):not([type=hidden]):not([type=checkbox]), "
                                      "form textarea, form select"):
        try:
            if not el.is_visible():
                continue
            t = (el.get_attribute("type") or "").lower()
            label = _full_label(el)
            if t == "radio":
                name = el.get_attribute("name") or label
                if name in seen_radio:
                    continue
                seen_radio.add(name)
                label = el.evaluate("""e => { const g = e.closest('fieldset, [role=radiogroup], li, .application-question');
                    return g ? (g.querySelector('legend, .application-label, label') || g).innerText.split('\\n')[0] : ''; }""")
            q = bank.norm(label)
            if not q or bank.SKIP.search(q):
                continue
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            options = []
            if tag == "select":
                options = [o for o in el.evaluate("e => [...e.options].map(o => o.text.trim())")
                           if o and not o.lower().startswith("select")]
                typ = "select"
            elif el.get_attribute("role") == "combobox":
                _, options = _combo_options(page, el)
                page.keyboard.press("Escape")
                typ = "dropdown"
            elif t == "radio":
                options = el.evaluate("""e => [...document.querySelectorAll(`input[name="${e.name}"]`)]
                    .map(r => (r.closest('label') || {}).innerText || r.value)""")
                typ = "radio"
            else:
                typ = "essay" if tag == "textarea" else "text"
            if len(options) > 40:  # country/phone-code style lists: not a real question
                options = []
                if "country" in q:
                    continue
            if company_name:
                q = re.sub(re.escape(bank.norm(company_name)), "{company}", q)
            found.append(dict(q=q, type=typ, options=[o.strip() for o in options if o.strip()],
                              required=_required(el), company=company_name or ""))
        except Exception:
            continue
    return found


def harvest(cfg, per_board=4, delay=2.0):
    from playwright.sync_api import sync_playwright
    entries = bank.load()
    urls = job_urls(cfg, per_board)
    print(f"[harvest] {len(urls)} forms to read")
    exe = os.environ.get("CHROMIUM_PATH")
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        for i, (board, url) in enumerate(urls, 1):
            page = b.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                if not page.query_selector("form"):
                    btn = page.query_selector("a:has-text('Apply'), button:has-text('Apply')")
                    if btn:
                        btn.click()
                page.wait_for_selector("form", timeout=15000)
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                m = re.search(r" at (.+)$", page.title())
                company = (m.group(1).strip() if m else board)
                got = extract(page, company)
                entries = bank.merge(entries, got)
                bank.save(entries)
                print(f"[harvest] {i}/{len(urls)} {board}: {len(got)} questions (bank: {len(entries)})", flush=True)
            except Exception as e:
                print(f"[harvest] {i}/{len(urls)} {board}: skipped ({type(e).__name__})", flush=True)
            page.close()
            time.sleep(delay)
        b.close()
    print(f"[harvest] done: {len(entries)} distinct questions in {bank.PATH}")
    return entries


def prefill_from_profile(profile):
    """Fill blank bank answers from the regex `answers` in profile.yaml."""
    pats = [(re.compile(k, re.I), str(v)) for k, v in (profile.get("answers") or {}).items()]
    entries = bank.load()
    n = 0
    for e in entries:
        if not e.get("answer"):
            a = next((v for rx, v in pats if rx.search(e["q"])), None)
            if a and (not e.get("options") or a in e["options"]):
                e["answer"] = a
                n += 1
    bank.save(entries)
    return n


def interactive():
    entries = bank.load()
    todo = [e for e in sorted(entries, key=lambda e: -e.get("seen", 0)) if not e.get("answer")]
    print(f"{len(todo)} unanswered of {len(entries)}. Enter = skip, 'q' = save & quit.\n")
    for e in todo:
        print(f"[{e['seen']}x {e['type']}{' *' if e.get('required') else ''}] {e['q']}")
        opts = e.get("options") or []
        for i, o in enumerate(opts, 1):
            print(f"   {i}. {o}")
        a = input("> ").strip()
        if a.lower() == "q":
            break
        if a:
            e["answer"] = opts[int(a) - 1] if opts and a.isdigit() and 0 < int(a) <= len(opts) else a
            bank.save(entries)
    bank.save(entries)
    print("saved.")
