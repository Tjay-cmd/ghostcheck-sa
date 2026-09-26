# GhostCheck SA: data contract v1

Status: **final field names** (v1, 26 Sep 2026). Source docs: `spec.md`, `ux/handoff.md` (Part B, §0.3 glossary, §0.4 constants, Part C), `ux/badge-system.md` (§2 = only source of rule values, §7 copy), `ux/ux-spec.md`.
The sample files in this folder are the exact contract. Frontend reads them as-is. Backend must produce byte-compatible shapes.
Validate with `pip install -r requirements.txt && python validate.py` (JSON Schema 2020-12 in `schemas/` plus cross-file consistency checks).

## 0. Global rules

| Rule | Requirement |
|---|---|
| Dates | SAST (Africa/Johannesburg) calendar dates `YYYY-MM-DD`. Datetimes ISO 8601 with offset `+02:00`. Times `HH:MM` SAST. |
| Glossary | Exactly handoff §0.3. `days_seen = last_seen − first_seen` (whole days, reopen gaps included). All ages are lower bounds; the UI adds "+". |
| Derived state is precomputed | `age_state`, `reposted`, `repost_count`, `open_before_tracking`, `days_seen`, `chain_first_seen`, every metric, `check_status`, overview eligibility and stale info are computed **once at build** by the pipeline. Frontend displays them and never re-derives them (F1). `config/rules.json` is used by the frontend only for display text (legend, chips, notes). |
| Rule values | Only in `config/rules.json`, equal to badge-system.md §2. `validate.py` checks that match. Code and tests refer to constant names, never literals. |
| **Listing ID stability** | `listing_id` is in public URLs (`/employers/{employer_slug}/{listing_id}/`), so it **never changes and is never reused**. Format: 10 chars, lowercase Crockford base32 (`^[0-9a-hjkmnp-tv-z]{10}$`) = the top 50 bits of `sha256("{employer_id}:{ats_job_id}")`. It's computed **once** when the record is created and then stored; it's never recomputed from mutable fields (title, location, URL, slug changes don't touch it). A reopen (same `ats_job_id`) keeps the same ID. On a hash collision with any ID ever issued (including hidden or deleted records), hash `"{employer_id}:{ats_job_id}:1"`, `:2`, … . The pipeline keeps a permanent issued-ID register, and IDs of hidden listings stay reserved forever. |
| Employer ID | `id` = `slug`, lowercase kebab-case, stable forever (the URL segment). Both keys exist because handoff B1 names both. `validate.py` enforces equality. A display-name change never changes the slug. |
| **POPIA** | Never stored anywhere in the repo, in config or data: recruiter/staff names or contacts (names, emails, phone numbers), full or partial job descriptions, salary/remuneration text. Per listing only `ats_job_id, title, location, url, first_seen, last_seen` are collected (M0 `store.py` whitelist). A title that contains a person's name is a personal-data case (hide via `config/corrections.json`). Correction records never contain requester names or emails, and they never quote the offending text (the repo is public). `validate.py` rejects field names matching salary/description/recruiter/contact/email/phone. |
| Neutral wording | No "ghost job", "fake", "worst", no rank numbers or `rank` fields. Overview order comes only from the chosen sort. |
| Hidden listings | A listing hidden by a correction is excluded from **every** published file and figure: no detail file (page = 404), not in search, employer lists, counts, metrics, `chain` or `later_reposts`. `repost_count` always equals `len(chain)`, so a badge never points to a 404. |
| Determinism | Fixed key order as in the samples. Arrays sorted as documented per field. Pretty-printed (2-space) except `search-index.json` (minified). That keeps daily commits small. |
| Versioning | Every `data/*` file has `schema_version: 1` (`v: 1` in the search index). A breaking change bumps it. |
| Empty/unknown | Fields are always present. Unknown values are `null`, never omitted and never `0` (a metric that isn't available has `value: null`, never "0%"). |

## 1. Repo layout

```
config/rules.json            constants (§0.4 keys only)
config/site.json             site flags + CORRECTIONS_EMAIL
config/employers.json        employer registry (hand-edited, superset of the M0 format)
config/corrections.json      manual overrides (hand-edited)
data/site.json               site-level build info (M1+)
data/employers/{slug}.json   one per employer in the registry (M1+)
data/listings/{listing_id}.json   one per published listing, open AND closed (M1+)
data/overview.json           employer listing overview (written every build; frontend uses it only if FEATURE_OVERVIEW) (M1+)
data/search-index.json       open listings, compact (frontend copies it to /data/search-index.{hash}.json, F8) (M1+)
data/corrections-log.json    public corrections log (M1+)
data/_samples/               fictional sample data for contract validation and frontend development
history/listings/{employer_id}.json   M0 raw per-employer scrape history (internal, not part of contract)
history/runlog.json          M0 daily run log (internal, not part of contract)
```

> **M0 → M1 path separation:** The M0 spike writes its raw per-employer history to `history/listings/{employer_id}.json` and the run log to `history/runlog.json`. These are internal files not read by the frontend. The contract's `data/` files will be generated by the M1 pipeline. Sample data for contract validation and frontend development is in `data/_samples/` until M1 produces real output.

## 2. `config/rules.json`

Exactly the 12 keys in handoff §0.4. All integers. Values = badge-system.md §2.

| Key | Type | Value | Used by |
|---|---|---|---|
| `FRESH_MAX_DAYS` | int | 13 | `age_state` = fresh when `days_seen ≤` this and not open-before-tracking |
| `LONG_OPEN_MIN_DAYS` | int | 91 | `age_state` = long_open when `days_seen ≥` this. Also `share_open_90`, `long_open_possible_from`, `earliest_long_open_possible_on` |
| `CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS` | int | 2 | `status`/`closed_on`: missing from this many consecutive **successful** checks |
| `REPOST_WINDOW_DAYS` | int | 60 | repost link when the earlier match is open or `closed_on ≥ first_seen − N` |
| `REPOST_RATE_WINDOW_DAYS` | int | 180 | `repost_rate` window |
| `EMPLOYER_METRICS_MIN_TRACKED_DAYS` | int | 30 | metric gate (days) |
| `EMPLOYER_METRICS_MIN_LISTINGS_SEEN` | int | 5 | metric gate (listings ever seen) |
| `OVERVIEW_MIN_TRACKED_DAYS` | int | 91 | overview eligibility (days) |
| `OVERVIEW_MIN_OPEN_LISTINGS` | int | 5 | overview eligibility (open listings) |
| `STALE_BUILD_HOURS` | int | 36 | `site.stale.stale_after` and the client-side banner |
| `FAILED_STREAK_WARNING_RUNS` | int | 7 | `check_status = failed_streak` |
| `RECENTLY_CLOSED_WINDOW_DAYS` | int | 90 | `employer.listings.recently_closed` |

## 3. `config/site.json` (site flags; **home of `CORRECTIONS_EMAIL`**)

`CORRECTIONS_EMAIL` lives here, not in `rules.json`, because rules.json must hold exactly the §0.4 keys and handoff A2 groups it with the site flags. When the email is decided, it's a one-line change.

| Field | Type | Null | Meaning |
|---|---|---|---|
| `CORRECTIONS_EMAIL` | string | no | Literal `[CORRECTIONS_EMAIL_TBD]` until decided (validate.py enforces it). Used in mailto, footer and About (F11). |
| `FEATURE_OVERVIEW` | bool | no | `false` = no `/overview/` route or links (F5). Soft launch `false`, public launch `true`. |
| `SITE_PHASE` | `"soft"`\|`"public"` | no | `soft` shows the footer "Test version" note. |
| `POPIA_REVIEWED` | bool | no | `false` = POPIA section shows "Draft, pending review" (F12). |

## 4. `config/employers.json` (registry, hand-edited)

`{defaults, employers[]}`. It's a superset of the M0 `config/employers.json`: the M0 fetchers keep working, and `slug`, `active` and `added_on` are new. Sorted by `id` is recommended but not required.

| Field | Type | Null | Meaning |
|---|---|---|---|
| `defaults.delay_seconds` / `max_pages` / `timeout_seconds` | number/int/number | no | scraper politeness defaults (M0) |
| `employers[].id` | slug | no | stable internal key, = `slug` |
| `employers[].slug` | slug | no | URL segment `/employers/{slug}/`, never changes |
| `employers[].name` | string | no | display name as the employer uses it |
| `employers[].sector` | enum | no | exactly one of the 9 sectors in handoff B1 |
| `employers[].ats_type` | `workday`\|`successfactors`\|`other` | no | selects the fetcher |
| `employers[].source_url` | https URL | no | public careers page ("Official careers site ↗") |
| `employers[].tenant`, `host`, `site` | string | required if workday | Workday tenant slug, host, site (CXS API) |
| `employers[].base_url` | https URL | required if successfactors | RMK career-site base |
| `employers[].sf_company` | string | optional | SuccessFactors company id when known |
| `employers[].overrides` | object | optional | per-employer scraper overrides (M0 `overrides`) |
| `employers[].note` | string | optional | internal note (never personal data) |
| `employers[].active` | bool | no | `false` = hidden from search/overview, and the employer page shows "no longer tracked" (B8.7) |
| `employers[].added_on` | date | no | date added to the registry (not `tracked_since`) |

A tenant/URL change (B8.5) edits `source_url`/tenant fields only. `id`, `slug` and `tracked_since` stay the same.

## 5. `config/corrections.json` (manual overrides, hand-edited)

`{corrections[]}`, sorted by `id`. This file is in `config/` (handoff B6 suggested `data/`) because it's human-authored input, not pipeline output.

| Field | Type | Null | Meaning |
|---|---|---|---|
| `id` | `corr-YYYY-NNNN` | no | stable correction id |
| `received_on` | date | no | date the request arrived |
| `type` | enum | no | `hide_listing` · `suppress_repost_link` · `fix_listing_field` · `note_only` |
| `reason` | enum | required for hide_listing | `personal_data_claim` · `employer_removal_approved` · `other` |
| `status` | enum | no | `pending_review` · `upheld` · `rejected` |
| `employer_id` | slug | no | employer concerned |
| `listing_id` | listing_id | required except note_only | target listing |
| `earlier_listing_id` | listing_id | required for suppress_repost_link | the earlier side of the link to drop |
| `field`, `value` | `title`\|`location`, string/null | required for fix_listing_field | corrected value (null = location unspecified) |
| `hides_listing` | bool | no | `true` only for `hide_listing` (schema-enforced) |
| `resolved_on` | date | null while pending | review decision date |
| `public_summary` | string ≤300 | null | text for the public log once upheld (neutral, no personal data) |
| `note` | string ≤300 | no | internal note. **No requester names/emails, and never quote personal data.** |

**When a correction takes effect (B8.6, D9):**

| Type + reason | pending_review | upheld | rejected |
|---|---|---|---|
| `hide_listing` + `personal_data_claim` | **hidden immediately** (next build; run the workflow manually) | hidden | shown again |
| `hide_listing` + other reasons | shown (stays up during review) | hidden | shown |
| `suppress_repost_link` | link kept | link removed; chain/counts recomputed | kept |
| `fix_listing_field` | old value | new value shown (and used for matching from then on, no retro-matching), id added to the listing's `correction_ids` | old value |
| `note_only` | no data effect | logged if `public_summary` is set | none |

A full employer removal (B8.7) = a human decision, then `active=false` in the registry and `hide_listing` (`employer_removal_approved`) for its listings. When a personal-data claim is upheld, the raw title in `history/` must also be scrubbed, because git history is public.

## 6. `data/site.json`

| Field | Type | Null | Meaning | Rule |
|---|---|---|---|---|
| `schema_version` | 1 | no | contract version | |
| `build_time` | datetime | no | when this JSON was built | footer build time |
| `data_date` | date | yes (no run yet) | SAST date of the data ("today" for this build). All `tracked_days` and windows are computed against it | |
| `last_successful_run_at` | datetime | yes | latest `ok` check time in the latest daily run where ≥1 employer succeeded | LastCheckedChip, stale banner |
| `tracking_started_on` | date | yes | earliest `tracked_since` of any employer | About DataStats |
| `stale.stale_after` | datetime | yes | `last_successful_run_at + STALE_BUILD_HOURS`. The client shows the banner when now > this | STALE_BUILD_HOURS |
| `stale.stale_at_build` | bool | no | already stale when built (the banner renders without JS) | STALE_BUILD_HOURS |
| `stale.last_run_date` | date | yes | date of the latest daily run (any status) | |
| `stale.last_run_employers_ok` | int | no | employers with `ok` in that run | |
| `stale.last_run_employers_failed` | int | no | employers with `blocked`/`error` in that run | |
| `counts.open_listings` | int | no | published open listings | "312 open listings" |
| `counts.employers_tracked` | int | no | active employers in the registry | "87 employers" |
| `counts.employers_with_data` | int | no | active employers with `tracked_since` | |
| `counts.fresh` / `seen` / `long_open` | int | no | open listings per `age_state` | empty states of static lists |
| `counts.reposted_open` | int | no | open listings with `reposted` | |
| `counts.open_before_tracking_open` | int | no | open listings with `open_before_tracking` | |
| `counts.closed_listings` | int | no | published closed listings | |
| `counts.listings_total` | int | no | all published listings | |
| `earliest_long_open_possible_on` | date | yes | earliest `tracked_since + LONG_OPEN_MIN_DAYS` | copy `home.early_long_open` |

## 7. `data/employers/{slug}.json`

One file per registry employer (including never-successful ones, B8.1, and inactive ones).

| Field | Type | Null | Meaning | Rule |
|---|---|---|---|---|
| `schema_version` | 1 | no | | |
| `id`, `slug`, `name`, `sector`, `ats_type`, `source_url`, `active` | as registry | no | copied from `config/employers.json` | B1 |
| `tracked_since` | date | yes | first successful check (M0 counts). `null` = never successful | glossary |
| `tracked_days` | int | yes | `data_date − tracked_since` | gates |
| `has_data` | bool | no | `tracked_since != null`. `false` = "We've added X but haven't completed a check yet" | B8.1 |
| `last_run` | `{date, time, status}` | yes | latest attempt. `status` ∈ `ok`/`blocked`/`error` | B1 |
| `last_successful_check_at` | datetime | yes | latest `ok` run ("Last checked …", "last successful check on …") | B1 |
| `consecutive_failed_runs` | int | no | failed runs since the last `ok` (0 if the last run was ok) | B1 |
| `check_status` | enum | no | `no_data` (never ok) · `failed_streak` (≥ `FAILED_STREAK_WARNING_RUNS`) · `last_run_failed` (≥1) · `ok`. Precedence in that order. Picks the banner | badge-system §6 |
| `total_listings_seen` | int | no | published listings ever seen (open + closed) | gate |
| `metrics.open_count` | Metric | no | open listings (always available unless `no_data`) | B4 |
| `metrics.median_days_seen` | Metric (`days`) | no | median `days_seen` of open listings (integer, floor of the median). `no_open` if 0 open | B4, gate |
| `metrics.share_open_90` | Metric (`percent`) | no | open with `days_seen ≥ LONG_OPEN_MIN_DAYS` ÷ open | B4, gate |
| `metrics.repost_rate` | Metric (`percent`) | no | listings first seen in the window that have a repost link ÷ listings first seen in the window | REPOST_RATE_WINDOW_DAYS, gate |
| `metrics.long_open_possible_from` | date | yes | `tracked_since + LONG_OPEN_MIN_DAYS` when it's after `data_date`, else null (copy `metric.long_open_early`) | B4 |
| `overview.eligible` | bool | no | active AND tracked ≥ `OVERVIEW_MIN_TRACKED_DAYS` AND open ≥ `OVERVIEW_MIN_OPEN_LISTINGS` | B4 |
| `overview.eligible_from` | date | yes | `tracked_since + OVERVIEW_MIN_TRACKED_DAYS`, only when the open-listings condition is met | badge-system §5 |
| `overview.reason` | enum | yes | null if eligible, else `tracked_days` · `open_listings` · `tracked_days_and_open_listings` · `no_data` · `inactive` | |
| `listings.open` | ListingSummary[] | no | **all** open listings, sorted `first_seen` desc, then `listing_id` desc | |
| `listings.recently_closed` | ListingSummary[] | no | closed with `closed_on ≥ data_date − RECENTLY_CLOSED_WINDOW_DAYS`, sorted `closed_on` desc | RECENTLY_CLOSED_WINDOW_DAYS |

**Metric object** (same keys for all four, handoff B4):

| Field | Type | Null | Meaning |
|---|---|---|---|
| `value` | int | yes | display value: count, whole days, or whole percent 0–100 (round half up). `null` when unavailable, **never 0 as a stand-in** |
| `unit` | `count`\|`days`\|`percent` | no | how to render |
| `numerator`, `denominator` | int | yes | set for percent metrics ("4 of 14"). Null otherwise |
| `window_label` | string | yes | repost_rate only: `"last {REPOST_RATE_WINDOW_DAYS} days"` or `"since {d Mon yyyy}"` (window starts at tracked_since when tracked < window) |
| `window_start` | date | yes | repost_rate only: first date of the window |
| `available` | bool | no | false = render gate/unavailable copy (F3) |
| `unavailable_reason` | `gate`\|`no_open`\|`no_data` | yes | why not available |
| `available_from` | date | yes | `tracked_since + EMPLOYER_METRICS_MIN_TRACKED_DAYS` when the day condition is the **only** outstanding gate condition (copy "Expected from {date}"), else null |

Gate = `tracked_days ≥ EMPLOYER_METRICS_MIN_TRACKED_DAYS` AND `total_listings_seen ≥ EMPLOYER_METRICS_MIN_LISTINGS_SEEN`. It applies to median, share and repost rate only.

**ListingSummary** (shared by employer lists, `more_at_employer` and home/static lists; a superset of handoff A3):

| Field | Type | Null | Meaning |
|---|---|---|---|
| `listing_id` | listing_id | no | |
| `employer_slug`, `employer_name` | string | no | |
| `title`, `location` | string | location null | as posted, whitespace-normalised (after corrections). Location may be `"Remote"` |
| `first_seen`, `last_seen` | date | no | glossary |
| `days_seen` | int | no | `last_seen − first_seen` |
| `status` | `open`\|`closed` | no | |
| `closed_on` | date | yes | null if open |
| `age_state` | `fresh`\|`seen`\|`long_open`\|`closed` | no | B3.7 |
| `open_before_tracking` | bool | no | `first_seen == employer.tracked_since` |
| `reposted` | bool | no | `repost_count ≥ 1` |
| `repost_count` | int | no | earlier listings in the chain (transitive) |
| `chain_first_seen` | date | yes | first_seen of the earliest listing in the chain |

## 8. `data/listings/{listing_id}.json` (listing detail, open and closed)

**Path decision:** flat `data/listings/{listing_id}.json`. Every published listing has one, open or closed (closed pages exist so repost history can link to them, `noindex`). The page URL is `/employers/{employer_slug}/{listing_id}/`. Home and static lists (`/listings/new/` etc.) can be prerendered by globbing these files (every ListingSummary field is at the top level) or from employer files.

| Field | Type | Null | Meaning | Rule |
|---|---|---|---|---|
| `schema_version` | 1 | no | | |
| `listing_id` | listing_id | no | stable forever, never reused (§0) | ID rule |
| `employer_id`, `employer_slug`, `employer_name` | string | no | owning employer | |
| `ats_job_id` | string ≤100 | no | the ATS's own job/requisition id | B2 |
| `title` | string ≤200 | no | as posted, whitespace-normalised. Updated in place when the ATS edits it (B8.4). Corrections are applied | B2 |
| `normalised_title` | string | no | casefold, every run of non-alphanumerics → one space, trimmed. Exact equality only | B2 |
| `location` | string | yes | as posted. null = unspecified | B2 |
| `normalised_location` | string | yes | same normalisation. `null` when location is null/empty or `"remote"`, so both unspecified/remote match each other | B3.5 |
| `fingerprint` | string | no | `{employer_id}\|{normalised_title}\|{normalised_location or "-"}` | spec |
| `url` | https URL | no | original posting (apply link, F7) | B2 |
| `apply_domain` | string | no | registrable domain of `url` (public-suffix aware: `jobs.nedbank.co.za` → `nedbank.co.za`) for "Opens the employer's own posting on {domain}" | ux §8 |
| `first_seen`, `last_seen` | date | no | glossary. `last_seen` only moves on successful checks | B3.2 |
| `days_seen` | int | no | `last_seen − first_seen` (gaps included) | B3.6 |
| `status` | `open`\|`closed` | no | closed after `CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS` consecutive successful misses | B3.3 |
| `closed_on` | date | yes | date of the last of those misses (current closure). null if open | B3.3 |
| `gaps` | `{closed_on, reopened_on}[]` | no (may be empty) | reopen history (same `ats_job_id` returned), oldest first. Not a repost | B3.4 |
| `age_state` | enum | no | `closed` if closed · `fresh` if `days_seen ≤ FRESH_MAX_DAYS` and not `open_before_tracking` · `long_open` if `days_seen ≥ LONG_OPEN_MIN_DAYS` · else `seen` | B3.7 |
| `open_before_tracking` | bool | no | `first_seen == employer.tracked_since` ("Up since at least {tracked_since}", never New) | glossary |
| `reposted` | bool | no | `repost_count ≥ 1` | badge §3 |
| `repost_count` | int | no | `len(chain)` | B3.8 |
| `chain_first_seen` | date | yes | first_seen of the oldest chain item | B3.8 |
| `repost_of` | `{listing_id, match_basis, gap_days}` | yes | the direct repost link (B3.5): the earlier listing, `"same_title_location"`, gap_days = 0 if the earlier one was open at this first_seen, else days from its `closed_on` to this `first_seen` (≤ `REPOST_WINDOW_DAYS`) | B3.5 |
| `chain[]` | ChainItem[] | no (may be empty) | **earlier** listings only (this listing excluded), newest → oldest, links followed transitively | B3.8 |
| `chain[].listing_id`, `title`, `location`, `first_seen`, `last_seen`, `days_seen`, `status`, `closed_on` | | | snapshot of that earlier listing | |
| `chain[].match_basis` | `"same_title_location"` | no | UI: "Same title and location, new job ID" | badge §4 |
| `chain[].gap_days` | int | no | gap between this item and the next-newer listing in the chain | B3.5 |
| `later_reposts[]` | `{listing_id, first_seen, status}` | no (may be empty) | listings whose chain contains this one (transitive), sorted `first_seen` asc. The first item drives "A similar listing was posted later on {date}" | B3.8 |
| `correction_ids` | string[] | no | upheld corrections applied to this listing (links to the log) | corrections |
| `employer.tracked_since`, `active`, `last_run`, `last_successful_check_at`, `consecutive_failed_runs`, `check_status`, `open_count` | as employer file | | context for the page header, banners and "See all N" | A3 |
| `more_at_employer` | ListingSummary[] ≤3 | no | other open listings at the employer, newest first_seen first | A3 |

## 9. `data/overview.json`

Written every build. The site uses it only when `FEATURE_OVERVIEW=true`. It contains no rank numbers.

| Field | Type | Null | Meaning | Rule |
|---|---|---|---|---|
| `schema_version` | 1 | no | | |
| `generated_at` | datetime | no | | |
| `data_date` | date | yes | "data to {date}" | |
| `default_sort` | `"share_open_90_desc"` | no | the array order of `employers` = % open 90+ high→low, ties by name A–Z (the no-JS default). Other sorts happen client-side | ux §9 |
| `employers[]` | row[] | no | **only** active employers with `overview.eligible` | OVERVIEW_MIN_TRACKED_DAYS, OVERVIEW_MIN_OPEN_LISTINGS |
| `employers[].slug`, `name`, `sector`, `tracked_since`, `open_count` | | no | | |
| `employers[].median_days_seen`, `share_open_90`, `repost_rate` | Metric | no | same objects as the employer file | B4 |
| `not_yet_eligible[]` | row[] | no | every other active employer, name A–Z | |
| `not_yet_eligible[].slug`, `name`, `sector` | string | no | | |
| `not_yet_eligible[].tracked_since` | date | yes | | |
| `not_yet_eligible[].open_count` | int | yes | null when no data | |
| `not_yet_eligible[].eligible_from` | date | yes | set only when the open-listings condition is already met | badge §5 |
| `not_yet_eligible[].reason` | enum | no | `tracked_days` · `open_listings` · `tracked_days_and_open_listings` · `no_data` | |
| `earliest_eligible_from` | date | yes | min `eligible_from`, for "Collecting data: first figures from {date}" | ux §9 |

## 10. `data/search-index.json` (compact)

Open listings of active employers only (not hidden). Minified. The frontend copies it to a content-hashed name (F8) and loads it lazily on first focus/typing, so it isn't part of the ≤100 KB first load. Size: a synthetic 3,000-row / 100-employer index is ~283 KB raw and **~71 KB gzip** (target ≤80 KB). `validate.py` fails any sample over 100 KB raw.

| Field | Type | Meaning |
|---|---|---|
| `v` | 1 | format version |
| `generated_at` | datetime | |
| `fields` | fixed string[] | row column names (documentation; order is fixed) |
| `employers` | `[slug, name][]` | employer lookup table, sorted by slug. Rows reference the index |
| `rows` | array[] | one per open listing, sorted `first_seen` desc then `listing_id` desc |

Row columns (positional): `0 listing_id` · `1 employer` (index into `employers`) · `2 title` · `3 location` (string\|null) · `4 first_seen` · `5 days_seen` · `6 age_state` (`fresh`\|`seen`\|`long_open`) · `7 open_before_tracking` (0/1) · `8 reposted` (0/1) · `9 repost_count`. Together these give the full A3 summary shape.

## 11. `data/corrections-log.json` (public)

| Field | Type | Null | Meaning |
|---|---|---|---|
| `schema_version` | 1 | no | |
| `entries[]` | array | no | newest first. Empty array = "No corrections yet." |
| `entries[].date` | date | no | date the fix was published (`resolved_on`) |
| `entries[].employer` | string | no | employer display name |
| `entries[].employer_slug` | slug | no | link target |
| `entries[].correction_id` | string | no | the upheld correction in `config/corrections.json` |
| `entries[].summary` | string ≤300 | no | = `public_summary`. Neutral, no personal data |

## 12. The sample data (fictional)

All employers are fictional ("Example …", reserved `.example` domains and a fake Workday tenant). Sample build: `data_date` 2027-02-03, built 06:31 SAST (public-launch era, so every state occurs). `config/site.json` holds the **real soft-launch defaults** (`FEATURE_OVERVIEW=false`, `SITE_PHASE=soft`), independent of the sample date.

| Employer | Case |
|---|---|
| `example-bank` (Workday) | tracked since 2026-09-28 (M0), 128 days, 10 listings. Metrics **available**, overview-eligible. Last run ok |
| `example-mining` (SuccessFactors) | tracked since 2027-01-15, 19 days. Metrics **available=false** (`gate`, expected from 2027-02-14). Last 2 runs blocked (`last_run_failed`), so last_seen stops at 2027-02-01. Not yet overview-eligible (from 2027-04-16) |
| `example-utility-soc` (other) | added, never successful: `tracked_since=null`, `no_data`, 9 failed runs, no listings |

| listing_id | Listing | Case |
|---|---|---|
| `zh52c8791m` | IT Intern, Centurion | open, `fresh`, 3 days |
| `8bncrtw7e6` | Graduate Programme 2027 | open, `long_open` + `open_before_tracking` (128 days) |
| `7md14shwt8` | Finance Intern 2027 | open, `long_open`, 106 days |
| `7vwnt8qsf8` / `jke8eh144t` / `zgtz0r4r7k` | Example Mining | open, `seen` + `open_before_tracking` (17 days, never New) |
| `2ga75cqsm0` | Credit Risk Analyst | `closed` 2027-01-14 (last seen 01-12, missed 01-13 and 01-14) |
| `pvwm3w62dv` | Actuarial Analyst | **reopened**: gap 2026-12-09 → 2026-12-21, same ID, `seen` 79 days, repost_count 0 |
| `znyevd73vn` → `bmqvzc53r8` → `ha7g2x9rad` | Data Analyst, Sandton | **repost chain**: A (closed) ← B (closed, gap 19) ← C (open, gap 13, "Reposted 2 times, first seen 2026-10-05"). A and B carry `later_reposts` |
| `1q5hkhev1v` | Branch Consultant | fresh, location fixed by upheld correction `corr-2027-0002` (in the public log) |
| `52mv7gd58g` | Cloud Engineer, Remote | `normalised_location=null` |

`config/corrections.json` also shows: a pending `suppress_repost_link` on the Data Analyst chain (the link stays visible during review), a rejected location fix, and a pending **personal-data** `hide_listing` for `wqrybqztf9`, which is therefore absent from every data file.
