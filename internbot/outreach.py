"""Draft (never send) personalised outreach for each new posting -> out/outreach.md"""
import os, yaml
from datetime import date
from . import llm


def draft_all(postings, db=None, client=None, path="out/outreach.md"):
    if not (llm.enabled() or client):
        print("[outreach] ANTHROPIC_API_KEY not set - skipping drafts")
        return
    profile = yaml.safe_load(open("profile.yaml")) if os.path.exists("profile.yaml") else {}
    resume = llm.resume_text(profile.get("resume", ""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for p in postings:
            try:
                to = p.handle or ""  # twitter poster -> DM them; otherwise hiring team
                text = llm.draft_outreach(p, profile, resume, to, client)
            except Exception as e:
                print(f"[outreach] draft failed for {p.company}: {type(e).__name__}")
                continue
            kind = "DM" if p.handle else "Email"
            f.write(f"## {p.company} - {p.title}  ({date.today()})\n"
                    f"- {kind} to: {to or 'hiring team / recruiter / a researcher on the team'}\n- Link: {p.url}\n\n"
                    f"{text}\n\n---\n\n")
    print(f"[outreach] drafts appended to {path} - review and send yourself")
