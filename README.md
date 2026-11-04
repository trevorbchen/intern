# internbot — research internship scraper

**Scope: AI-research internships at startups only** (see `topics` and `exclude_companies` in `config.yaml`).

Collects research-internship postings from the web (Greenhouse, Lever, RSS), LinkedIn and Twitter/X,
filters by keywords, de-duplicates in SQLite, and reports only *new* postings (stdout, CSV, optional webhook).

```bash
pip install -r requirements.txt
python -m playwright install chromium  # once
export X_USERNAME=... X_PASSWORD=...   # bot logs in once, saves .x_session.json (gitignored)
# or, more reliable: export X_AUTH_TOKEN=... X_CT0=...  (cookies from a logged-in browser)
python -m internbot.cli --dry-run      # try it
python -m internbot.cli                # single run
python -m internbot.cli --watch        # constant: re-scrapes every interval_minutes (default 30)
pytest
```

Edit `config.yaml` for keywords, companies, and searches.

## Notes
- **Twitter/X**: crawled with a headless browser (no API). X blocks logged-out search, so supply your own
  session cookies (`X_AUTH_TOKEN`, `X_CT0`). This violates X's ToS and can get the account limited — use a throwaway.
- **LinkedIn**: reads the public logged-out search only (no login, rate-limited). LinkedIn's ToS
  prohibits scraping, so it may break or block you — disable under `sources.linkedin.enabled` if unsure.
- Web sources use public job-board JSON APIs and RSS.

## Applying, tracking, contacts
```bash
cp profile.example.yaml profile.yaml        # your details + resume path (gitignored)
python -m internbot.cli --apply             # fills Greenhouse/Lever forms, does NOT submit (screenshots in apply_shots/)
python -m internbot.cli --apply --submit    # actually submits (only when every required field is filled, no captcha)
python -m internbot.cli --applied           # running list of everything applied to, with dates
python -m internbot.cli --contacts          # Twitter handles + apply links found
```
Everything is also written to `out/applications.csv` and `out/contacts.csv`. Anything that can't be auto-filled
(custom questions, dropdowns, captchas, LinkedIn/other sites) is logged as `needs_manual` with the link.

## Quality controls
- `target_only` (config.yaml): only companies in `targets.yaml` (curated top-tier AI startups; refresh with `python tools/probe_targets.py`).
- Fit scoring: with `ANTHROPIC_API_KEY` + `profile.yaml`, Claude rates each new posting 0-100; below `min_score` is skipped, results are sorted best-first.
- `max_age_days` drops stale postings. LinkedIn duplicates (one per location) are collapsed.
- Outreach: `--outreach` drafts a cold email/DM per new posting into `out/outreach.md` (never sends).
- Track replies: `python -m internbot.cli --status Cohere interview` (replied | interview | rejected | offer), then `--applied`.
- Question bank: `--harvest` collects real application questions into `answers.yaml`; `--answer` fills them in interactively.
- `.github/workflows/scrape.yml` runs web + LinkedIn every 6 hours (secrets: `INTERNBOT_WEBHOOK`, `ANTHROPIC_API_KEY`); X crawling needs your own machine.

## Fellowships, researchers, dashboard
- Fellowships/residencies are tagged **PROGRAM** and never auto-applied: they land in the dashboard's "Apply by hand" tab.
  `programs.yaml` also watches MATS, Astra, SPAR, etc. (status open/closed, deadline, page-changed alerts). Add `deadline: YYYY-MM-DD` to put one on the calendar.
- `python -m internbot.cli --researchers [--draft]` finds researchers at target companies whose recent papers overlap your `interests`
  (OpenAlex, needs `OPENALEX_API_KEY`), and with `--draft` writes an email per researcher citing a specific paper. Nothing is sent.
- `python -m internbot.cli --ui` rebuilds `out/dashboard.html` (open it in a browser) and `out/deadlines.ics` (import into your calendar).
  Every normal run rebuilds both.

## The loop (everything, continuously) and what it costs
`python -m internbot.cli --watch` runs forever, each task on its own schedule (config.yaml -> `loop:`):
company boards (Greenhouse/Lever/Ashby) + careers pages + Hacker News + LinkedIn every 30 min; X every 2 h; fellowship pages
every 6 h; similar-researcher search daily; outreach drafts for every new posting; dashboard rebuilt each pass; alerts to your phone.
`--watch --once --force` runs every task one time and exits (handy for testing / cron).

| Piece | Cost |
|---|---|
| Job boards, careers pages, HN, fellowship pages, dashboard, calendar | free, no keys |
| LinkedIn (public guest pages), X (your own account via headless browser) | free, against their ToS (throwaway account) |
| Phone alerts | free: ntfy.sh (`NTFY_TOPIC`) |
| Similar researchers | free: OpenAlex. Keyless works in small daily batches; a free key (`OPENALEX_API_KEY`) scans everyone |
| Email / essay drafting | $0 with built-in templates; or Claude Haiku (default model, cents per month) with `ANTHROPIC_API_KEY` |
| Hosting | free: your own computer, or GitHub Actions (public repo = free minutes) |

Matching is strict on purpose: the *title* must be an intern / fellowship / residency / research-assistant type role and the
text must be AI-related, at a company in `targets.yaml`. Generic roles (e.g. plain "ML Intern") are skipped.
