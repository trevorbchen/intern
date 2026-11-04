"""Claude answers application questions that the profile `answers` patterns don't cover.

Needs ANTHROPIC_API_KEY in .env. Model defaults to claude-opus-5-5; set ANTHROPIC_MODEL in .env to
use something cheaper (e.g. claude-sonnet-5-5 or claude-haiku-5-5).
The model may ONLY use facts from your profile/resume. If it can't answer truthfully it returns
NEEDS_HUMAN and the field is left blank (application flagged for you).
"""
import os

NEEDS_HUMAN = "NEEDS_HUMAN"

SYSTEM = f"""You fill in job-application questions on behalf of a candidate applying to AI-research
internships at startups. Rules:
- Use ONLY facts in the candidate profile / resume provided. Never invent experience, projects,
  grades, dates, publications, or skills.
- If the question can't be answered truthfully from those facts, or is about demographics/EEO,
  disability, veteran status, criminal history, salary expectations, legal attestations, signatures,
  or anything sensitive, reply exactly {NEEDS_HUMAN}.
- If options are given, reply with exactly one option copied verbatim, nothing else.
- Otherwise write the answer only (no preamble, no quotes, no markdown). Short fields: a few words.
  Essays: 3-5 sentences, specific to the company/role, genuine and plain, no hype or clichés."""

_client = None


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def resume_text(path: str) -> str:
    path = os.path.expanduser(path or "")
    if not path.lower().endswith(".pdf") or not os.path.exists(path):
        return ""
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)[:12000]
    except Exception:
        return ""


def answer(question: str, options, profile: dict, job_text: str, resume: str = "", client=None):
    """Returns an answer string, or None if it needs a human."""
    facts = {k: v for k, v in profile.items() if k not in ("answers", "apply", "resume")}
    prompt = (f"CANDIDATE PROFILE:\n{facts}\n\nRESUME:\n{resume or '(none)'}\n\n"
              f"JOB POSTING (page text):\n{job_text[:6000]}\n\nQUESTION: {question}\n")
    if options:
        prompt += "OPTIONS:\n" + "\n".join(f"- {o}" for o in options)
    resp = (client or _get()).messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5"),
        max_tokens=1000, system=SYSTEM,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}])
    text = next((b.text for b in resp.content if b.type == "text"), "").strip()
    if not text or NEEDS_HUMAN in text:
        return None
    if options:
        match = next((o for o in options if o.strip().lower() == text.lower()), None)
        return match  # must be a real option
    return text


OUTREACH_SYSTEM = """You write short cold outreach (email or DM) from a student to someone at a top AI startup
about a research internship. Rules: 80-120 words, plain and specific, no flattery or clichés, no 'I hope this
finds you well'. Lead with one concrete, TRUE connection between the candidate's background and the role/team
(use ONLY facts from the profile/resume - never invent). One clear ask (a short chat or being considered).
If the recipient name is unknown, address it to 'the team' -- never make up a name.
Output format exactly:
SUBJECT: <short subject>
<body>"""


def draft_outreach(posting, profile: dict, resume: str = "", recipient: str = "", client=None) -> str:
    facts = {k: v for k, v in profile.items() if k not in ("answers", "apply", "resume")}
    prompt = (f"CANDIDATE PROFILE:\n{facts}\n\nRESUME:\n{resume or '(none)'}\n\n"
              f"ROLE: {posting.title} at {posting.company} ({posting.location})\nPOSTING / POST TEXT:\n"
              f"{(posting.description or posting.title)[:5000]}\n\nRECIPIENT: {recipient or 'unknown (hiring team)'}\n"
              f"SOURCE: {posting.source}  LINK: {posting.url}")
    resp = (client or _get()).messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5"), max_tokens=700,
        system=OUTREACH_SYSTEM, output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}])
    return next((b.text for b in resp.content if b.type == "text"), "").strip()


SCORE_SYSTEM = """You rate how well a research-internship posting fits a candidate who wants a research role at a
top AI startup. Consider: research (not product/sales/ops) focus, seniority fit for an intern, relevance to the
candidate's background and interests, location/eligibility, and how strong the team/company is.
Reply in exactly one line: SCORE: <0-100> | <one short reason>. 80+ = apply now, 60-79 = decent, below 60 = skip."""


def score_posting(posting, profile: dict, resume: str = "", client=None):
    """Returns (score:int, reason:str); (-1, "") on failure."""
    import re
    facts = {k: v for k, v in profile.items() if k in ("background", "school", "location", "interests", "graduation")}
    prompt = (f"CANDIDATE:\n{facts}\n{resume[:3000]}\n\nPOSTING: {posting.title} at {posting.company} "
              f"({posting.location})\n{(posting.description or '')[:3500]}")
    try:
        resp = (client or _get()).messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5"), max_tokens=200,
            system=SCORE_SYSTEM, output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}])
        text = next((b.text for b in resp.content if b.type == "text"), "")
        m = re.search(r"SCORE:\s*(\d{1,3})\s*\|?\s*(.*)", text)
        return (min(int(m.group(1)), 100), m.group(2).strip()) if m else (-1, "")
    except Exception:
        return -1, ""
