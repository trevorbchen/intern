"""Claude answers application questions that the profile `answers` patterns don't cover.

Needs ANTHROPIC_API_KEY in .env. Model defaults to the cheapest (claude-haiku-5-5); set ANTHROPIC_MODEL in .env
for something stronger (claude-sonnet-5-5 / claude-opus-5-5). With no key everything falls back to templates.
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


def model() -> str:
    """Cheapest current Claude by default (~cents/month at this volume). Override with ANTHROPIC_MODEL."""
    return os.environ.get("ANTHROPIC_MODEL") or "claude-haiku-5-5"


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
        model=model(),
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
        model=model(), max_tokens=700,
        system=OUTREACH_SYSTEM, output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}])
    return next((b.text for b in resp.content if b.type == "text"), "").strip()


RESEARCHER_SYSTEM = """You write a short cold email from a student to a researcher at an AI startup, asking about
research internship/collaboration opportunities. Rules: 90-130 words. Open with ONE specific, accurate point about
their named paper (only what the title/topics support - never invent results or details you can't know). Then ONE
true link to the candidate's own work (profile/resume facts only). Ask a small, concrete question or whether the
team takes research interns. Plain, warm, not flattering, no clichés. Don't invent names beyond the given one.
Output exactly:
SUBJECT: <short subject>
<body>"""


def draft_researcher_outreach(name, company, papers, profile, resume="", client=None):
    facts = {k: v for k, v in profile.items() if k not in ("answers", "apply", "resume")}
    plist = "\n".join(f"- {p['title']} ({p.get('year')})" for p in papers)
    prompt = (f"CANDIDATE PROFILE:\n{facts}\n\nRESUME:\n{resume[:4000] or '(none)'}\n\n"
              f"RESEARCHER: {name} at {company}\nTHEIR RECENT PAPERS (most relevant first):\n{plist}")
    resp = (client or _get()).messages.create(
        model=model(), max_tokens=600,
        system=RESEARCHER_SYSTEM, output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}])
    return next((b.text for b in resp.content if b.type == "text"), "").strip()


# ---- $0 fallbacks (no API key): plain templates using only your own profile facts ----
def template_researcher(name, company, papers, profile) -> str:
    paper = papers[0]["title"] if papers else "your recent work"
    me = (profile.get("background") or "").strip().split(".")[0] or "a student interested in research"
    return (f"SUBJECT: Question about your paper on {paper[:60]}\n"
            f"Hi {name.split()[0]},\n\nI read \"{paper}\" and found it really interesting. {me}. "
            f"I'm looking for a research internship and wanted to ask whether {company} takes interns on this kind of work, "
            f"or if there's a better person to contact.\n\nThanks for your time,\n{profile.get('first_name', '')}")


def template_posting(posting, profile) -> str:
    me = (profile.get("background") or "").strip().split(".")[0] or "a student interested in research"
    return (f"SUBJECT: {posting.title} - {profile.get('first_name', '')} {profile.get('last_name', '')}\n"
            f"Hi,\n\nI'm applying for the {posting.title} role at {posting.company}. {me}. "
            f"I'd love to chat briefly about the team's research and whether I could contribute.\n\n"
            f"Thanks,\n{profile.get('first_name', '')}")
