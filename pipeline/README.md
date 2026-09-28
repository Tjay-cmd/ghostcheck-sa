# GhostCheck SA — M1 pipeline

Turns the M0 scraper's raw output (`history/`) into the locked `data/` contract
(`../contract/CONTRACT.md`): listing IDs, closure detection, repost chains,
employer metrics, overview eligibility and the search index.

## Running

```bash
pip install -r requirements.txt      # stdlib only today
python -m ghostcheck_pipeline.build --repo-root ..
```

Writes `data/site.json`, `data/employers/*.json`, `data/listings/*.json`,
`data/overview.json`, `data/search-index.json` and `data/corrections-log.json`.
Re-running on unchanged input is idempotent (byte-identical output apart from
`build_time`/`generated_at`).

Validate the result against the contract:

```bash
cd ../contract && python validate.py ..
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## How it works

1. **Run stats** (`build.employer_run_stats`) — `tracked_since`, `last_run`,
   `consecutive_failed_runs` and `check_status` come straight out of
   `history/runlog.json`.
2. **Listing IDs** (`ids.Register`) — stable Crockford-base32 IDs
   (`sha256("{employer_id}:{ats_job_id}")`, top 50 bits), cached forever in
   `history/listing_id_register.json` so a hash collision (or hiding a
   listing) never reassigns or reuses an ID.
3. **Closure detection** (`build.compute_status`) — a listing is `closed`
   once it has been missing from `CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS`
   consecutive *successful* runs after its `last_seen`.
4. **Corrections** (`config/corrections.json`) — `fix_listing_field` patches
   are applied before normalisation; `hide_listing` (upheld, or
   `pending_review` + `personal_data_claim`) drops the listing from every
   published file while keeping its ID reserved; `suppress_repost_link`
   removes one specific chain hop.
5. **Repost chains** — listings are grouped by `fingerprint`
   (`employer_id|normalised_title|normalised_location`); consecutive
   same-fingerprint listings link up when the gap between the earlier one's
   `closed_on` and the later one's `first_seen` is within
   `REPOST_WINDOW_DAYS`. Chains are built transitively; `later_reposts` is
   the reverse index.
6. **Metrics** (`metrics.py`) — `open_count` is always available once an
   employer has data; `median_days_seen`/`share_open_90`/`repost_rate` are
   gated by `EMPLOYER_METRICS_MIN_TRACKED_DAYS` +
   `EMPLOYER_METRICS_MIN_LISTINGS_SEEN`, per the contract's Metric object.
7. **Site/overview/search-index roll-ups** are derived from the finished
   employer and listing docs, matching `contract/validate.py`'s
   cross-file consistency checks exactly (that script is the executable
   spec this pipeline was built against).

## Known limitation: `gaps` (reopen history) is not implemented

The pipeline always writes `gaps: []`. `history/listings/{employer}.json`
(the M0 store) keeps only one `first_seen`/`last_seen` pair per
`ats_job_id` — it doesn't retain the exact date a listing disappeared and
reappeared, so reopen detection needs to diff against the *previous*
build's own `data/listings/{id}.json` (if `status` flips `closed` → `open`
for the same `ats_job_id`, that's a reopen; `reopened_on` can only be
approximated from the successful-run dates in between). That diff isn't
wired up yet. With one day of real history so far no employer has hit this
path anyway — worth building once the scraper has run long enough to
produce a real reopen.

## Known gap: search-index size budget

`contract/validate.py` fails `data/search-index.json` over 100 KB **raw**.
With today's real registry (10 employers, 1,139 open listings) the raw file
is ~111 KB, but gzip is ~24 KB — well inside the ~80 KB gzip target
`CONTRACT.md` §10 actually documents. The raw-byte check was written against
a smaller synthetic sample and is stricter than the documented target; it's
not something this pipeline should paper over by truncating data. Worth a
decision: loosen `validate.py`'s check to gzip, or accept a larger raw
budget now that real employer data is bigger than the sample assumed.
