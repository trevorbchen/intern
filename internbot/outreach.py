"""Draft (never send) personalised outreach for each new posting -> out/outreach.md"""
import os, yaml
from datetime import date
from . import llm


def draft_all(postings, db=None, client=None, path="out/outreach.md"):
    use_llm = llm.enabled() or client is not None
    if not os.path.exists("profile.yaml") and client is None:
        print("[outreach] no profile.yaml yet - skipping drafts (copy profile.example.yaml and fill it in)")
        return
    profile = yaml.safe_load(open("profile.yaml")) if os.path.exists("profile.yaml") else {}
    resume = llm.resume_text(profile.get("resume", ""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for p in postings:
            try:
                to = p.handle or ""  # twitter poster -> DM them; otherwise hiring team
                text = (llm.draft_outreach(p, profile, resume, to, client) if use_llm
                        else llm.template_posting(p, profile))
            except Exception as e:
                print(f"[outreach] draft failed for {p.company}: {type(e).__name__}")
                continue
            kind = "DM" if p.handle else "Email"
            f.write(f"## {p.company} - {p.title}  ({date.today()})\n"
                    f"- {kind} to: {to or 'hiring team / recruiter / a researcher on the team'}\n- Link: {p.url}\n\n"
                    f"{text}\n\n---\n\n")
    print(f"[outreach] drafts appended to {path} - review and send yourself")
