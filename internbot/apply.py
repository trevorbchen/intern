"""Auto-fill (and optionally submit) Greenhouse / Lever application forms.

Safe by default: fills the form and takes a screenshot but does NOT submit unless submit=True.
If any required field can't be filled from profile.yaml, or a captcha is present, nothing is
submitted and the posting is logged as `needs_manual` so you can finish it by hand.
LinkedIn Easy Apply is deliberately not automated (violates ToS, gets accounts banned).
"""
import os, re
from dataclasses import replace
from .models import Posting

HOSTS = ("greenhouse.io", "lever.co")

FIELDS = {  # profile key -> candidate selectors
    "first_name": ["#first_name", "input[name='first_name']"],
    "last_name": ["#last_name", "input[name='last_name']"],
    "full_name": ["input[name='name']"],
    "email": ["#email", "input[name='email']"],
    "phone": ["#phone", "input[name='phone']"],
    "linkedin": ["input[name='urls[LinkedIn]']", "input[autocomplete='custom-question-linkedin-profile']",
                 "input[aria-label*='LinkedIn' i]"],
    "github": ["input[name='urls[GitHub]']", "input[aria-label*='GitHub' i]"],
    "website": ["input[name='urls[Portfolio]']", "input[aria-label*='Website' i]"],
    "location": ["input[name='location']", "#job_application_location"],
    "school": ["input[name='org']", "input[aria-label*='School' i]"],
    "cover_note": ["textarea[name='comments']", "#cover_letter_text", "textarea[aria-label*='cover' i]"],
}


def can_apply(url: str) -> bool:
    return any(h in (url or "") for h in HOSTS)


def _label(page, el) -> str:
    try:
        return el.evaluate("""e => (e.labels && e.labels[0] ? e.labels[0].innerText :
            e.getAttribute('aria-label') || e.name || e.id || '')""").strip()[:60]
    except Exception:
        return "?"


def apply_to(page, url: str, profile: dict, submit: bool, shot_dir="apply_shots"):
    """Returns (status, note). status: submitted | filled | needs_manual | failed"""
    try:
        if "lever.co" in url and not url.rstrip("/").endswith("/apply"):
            url = url.rstrip("/") + "/apply"
        page.goto(url, wait_until="domcontentloaded", timeout=40000)
        if not page.query_selector("form"):  # some pages hide the form behind an Apply button
            btn = page.query_selector("a:has-text('Apply'), button:has-text('Apply')")
            if btn:
                btn.click()
        page.wait_for_selector("form", timeout=15000)
        try:  # React forms hydrate late and wipe anything typed before that
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(1500)
        data = dict(profile, full_name=f"{profile['first_name']} {profile['last_name']}")
        for key, sels in FIELDS.items():
            if not data.get(key):
                continue
            for sel in sels:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(str(data[key]))
                    break
        resume = os.path.expanduser(profile.get("resume", ""))
        fi = page.query_selector("input[type=file][name='resume'], input[type=file]#resume, input[type=file]")
        if fi and os.path.exists(resume):
            fi.set_input_files(resume)
        # anything required that's still empty?
        missing = []
        for el in page.query_selector_all("input[required], textarea[required], select[required], "
                                          "[aria-required='true']"):
            try:
                t = (el.get_attribute("type") or "").lower()
                if not el.is_visible() and t != "file":
                    continue
                if t in ("hidden", "checkbox", "radio"):
                    continue
                if t == "file":
                    if not el.evaluate("e => e.files && e.files.length"):
                        missing.append("resume")
                elif not (el.input_value() or "").strip():
                    missing.append(_label(page, el))
            except Exception:
                continue
        captcha = page.query_selector("iframe[src*='hcaptcha'], iframe[src*='recaptcha'], .h-captcha")
        os.makedirs(shot_dir, exist_ok=True)
        shot = os.path.join(shot_dir, re.sub(r"\W+", "_", url)[-80:] + ".png")
        page.screenshot(path=shot, full_page=True)
        if missing:
            return "needs_manual", f"unfilled required: {', '.join(sorted(set(missing)))[:200]} ({shot})"
        if captcha and submit:
            return "needs_manual", f"captcha present ({shot})"
        if not submit:
            return "filled", f"dry run, not submitted ({shot})"
        btn = page.query_selector("button[type=submit], input[type=submit], #submit_app")
        if not btn:
            return "needs_manual", "no submit button found"
        btn.click()
        page.wait_for_timeout(5000)
        body = page.inner_text("body").lower()
        if any(k in body for k in ("thank you", "application submitted", "has been received", "thanks for applying")):
            return "submitted", "confirmation text seen"
        return "needs_manual", f"clicked submit but no confirmation seen ({shot})"
    except Exception as e:
        return "failed", f"{type(e).__name__}: {str(e)[:150]}"


def run_applications(postings, profile, db, submit=False, limit=5):
    from playwright.sync_api import sync_playwright
    todo = []
    for p in postings:
        target = p.url if can_apply(p.url) else (p.apply_url if can_apply(p.apply_url) else "")
        if target:
            tp = replace(p, url=target)
            if not db.already_applied(tp.uid):
                todo.append(tp)
        else:
            db.record_application(p, "needs_manual", "no Greenhouse/Lever form; apply by hand")
    exe = os.environ.get("CHROMIUM_PATH")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        for p in todo[:limit]:
            page = browser.new_page()
            status, note = apply_to(page, p.url, profile, submit)
            page.close()
            db.record_application(p, status, note)
            print(f"[apply] {status}: {p.company} - {p.title}\n        {note}")
        browser.close()
