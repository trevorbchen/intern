# internbot — research internship scraper

Collects research-internship postings from the web (Greenhouse, Lever, RSS), LinkedIn and Twitter/X,
filters by keywords, de-duplicates in SQLite, and reports only *new* postings (stdout, CSV, optional webhook).

```bash
pip install -r requirements.txt
export TWITTER_BEARER_TOKEN=...        # optional, official X API v2
python -m internbot.cli --dry-run      # try it
python -m internbot.cli                # real run; schedule with cron / GitHub Actions
pytest
```

Edit `config.yaml` for keywords, companies, and searches.

## Notes
- **Twitter/X**: uses the official API (paid tier needed for search); no scraping.
- **LinkedIn**: reads the public logged-out search only (no login, rate-limited). LinkedIn's ToS
  prohibits scraping, so it may break or block you — disable under `sources.linkedin.enabled` if unsure.
- Web sources use public job-board JSON APIs and RSS.
