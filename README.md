# GhostCheck SA

**Job listing freshness monitoring for South Africa**

GhostCheck SA is a research project that tracks job postings on South African employer career sites to study how long positions stay open. It scrapes Workday and SuccessFactors career pages, logging which listings are visible each day and whether the site is reachable or blocked.

## Project Structure

```
.github/workflows/scrape.yml   Daily GitHub Actions workflow (04:17 UTC)
config/                        Configuration files
  employers.json                 Employer registry (10 SA employers)
  rules.json, site.json          Contract constants and site flags
  corrections.json               Manual data corrections
data/                          Contract sample outputs (for frontend development)
  site.json                      Site-level metadata
  employers/*.json               Per-employer summaries
  listings/*.json                Individual job listing details
  overview.json                  Employer overview page data
  search-index.json              Compact search index
  corrections-log.json           Public corrections log
history/                       M0 scraper raw outputs (internal, not for frontend)
  listings/*.json                Per-employer history files
  runlog.json                    Daily run log
scraper/                       Python scraper package
  ghostcheck/                    Core scraper modules
  tests/                         Pytest test suite
  requirements.txt               Production dependencies
  requirements-dev.txt           Development dependencies
contract/                      Data contract documentation and validation
  CONTRACT.md                    Complete field specification
  validate.py                    Schema and consistency validator
  schemas/*.schema.json          JSON Schema 2020-12 definitions
pipeline/                      M1 pipeline: history/ -> data/ (listing IDs, closures, reposts, metrics)
  ghostcheck_pipeline/           Pipeline package
  tests/                         Pytest test suite
site/                          Placeholder for Astro frontend (to be built)
```

## Milestone 0 (M0) Risk Spike

The M0 phase is a 3-day pilot that scrapes 10 South African employers (5 Workday, 5 SuccessFactors) once daily from GitHub Actions. It logs **ok/blocked/error** status plus listing counts, with no database or server infrastructure.

**Design goals:**
- **R0 cost:** Static JSON only, hosted on GitHub. No API calls, no database, no compute costs.
- **POPIA compliance:** Only stores job ID, title, location, URL, first_seen, and last_seen dates. Never collects recruiter names, contact details, full job descriptions, or salary information.
- **Block detection:** Classifies responses as ok (listings returned), blocked (403/Akamai challenge/CAPTCHA), or error (network/parsing failure).

The M0 scraper runs daily at 04:17 UTC (06:17 SAST) and commits results to the `history/` directory. This validates the technical approach before building the full pipeline and public site.

## Data Contract

The `contract/` directory defines the exact field names and structure for the future static site. Frontend developers build against these specifications:

- All dates are SAST calendar dates `YYYY-MM-DD`
- Listing IDs are stable 10-character hashes (Crockford base32) that never change
- Employer slugs are stable URL segments that never change
- Field names, types, and structure are locked (v1)

Validate the contract with:
```bash
cd contract
pip install -r requirements.txt
python validate.py
```

This checks that all sample data files match their JSON schemas and that cross-file consistency rules hold (listing counts, date arithmetic, metric gates, etc.).

## POPIA Field Policy

**Privacy by design:** Only the following per-listing fields are ever collected or stored:

- `ats_job_id` (internal ATS identifier)
- `title` (job title as shown on the career site)
- `location` (location string or null)
- `url` (direct link to the listing)
- `first_seen` (SAST date first observed)
- `last_seen` (SAST date last seen)

**Never collected:**
- Recruiter or hiring manager names
- Contact information (email addresses, phone numbers)
- Full job descriptions or requirements
- Salary or remuneration details
- Any personally identifiable information

The scraper enforces this through a hard whitelist in `scraper/ghostcheck/store.py`. Any field not in `ALLOWED_FIELDS` is dropped before writing to disk.

## Running the Scraper Locally

```bash
# Install dependencies
pip install -r scraper/requirements.txt

# Run scraper (writes to history/)
cd scraper
python -m ghostcheck.run

# Run tests
pip install -r requirements-dev.txt
pytest
```

The scraper reads `config/employers.json` and writes to `history/listings/` and `history/runlog.json` by default.

## Testing

The M0 scraper includes a comprehensive test suite:

```bash
cd scraper
pip install -r requirements-dev.txt
pytest -v
```

Tests cover:
- Workday and SuccessFactors parsers (pagination, edge cases)
- Block classification (403, Akamai, CAPTCHA, generic HTML)
- Storage layer (POPIA field whitelist, date handling, upsert logic)
- End-to-end run (multi-employer, error isolation, runlog)

## Milestone 1 (M1) Pipeline

`pipeline/` turns `history/` (M0's raw scrape output) into the `data/` contract:
listing ID generation, closure detection, repost-chain detection, employer
metrics and overview eligibility. See `pipeline/README.md` for how it works
and its known limitations.

```bash
pip install -r pipeline/requirements.txt
python -m ghostcheck_pipeline.build --repo-root .   # run from pipeline/
```

Validate the result:

```bash
cd contract && python validate.py ..
```

## Future Phases

After the M0 spike validates the approach:

1. ~~**M1:** Full pipeline with listing ID generation, closure detection, repost chains, employer metrics~~ — built, see `pipeline/`
2. **Static site:** Astro frontend in `site/` reading from `config/` and `data/`
3. **Public launch:** Search UI, employer pages, overview dashboard

## License

To be determined.

## Contributing

This is currently a research prototype. Contribution guidelines will be added in a future phase.
