# internbot — research internship scraper

Collects research-internship postings from the web (Greenhouse, Lever, RSS), LinkedIn and Twitter/X,
filters by keywords, de-duplicates in SQLite, and reports only *new* postings (stdout, CSV, optional webhook).

```bash
pip install -r requirements.txt
python -m playwright install chromium  # once
export X_AUTH_TOKEN=... X_CT0=...      # cookies from your own logged-in x.com session
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
