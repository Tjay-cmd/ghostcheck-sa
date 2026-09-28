# GhostCheck SA: static site

Astro site built from the data contract (`../contract/CONTRACT.md`). It reads
`../data/` and `../config/` at build time and displays precomputed state only:
it never re-derives ages, closures or metrics (F1).

```bash
npm install
npm run build                                 # real data from ../data  -> dist/
GHOSTCHECK_DATA=data/_samples npm run build   # fictional samples: every state (reposts, closed, gated metrics, failed checks)
npm run preview
```

## Pages

| Route | Source |
|---|---|
| `/` | `data/site.json`, employer files |
| `/search/` | `data/search-index.json`, published as `/data/search-index.{hash}.json` (F8) |
| `/employers/` and `/employers/{slug}/` | `data/employers/*.json` |
| `/employers/{slug}/{listing_id}/` | `data/listings/*.json` (closed listings get `noindex`) |
| `/overview/` | `data/overview.json`, only built when `FEATURE_OVERVIEW` is true (F5) |
| `/method/`, `/corrections/` | `config/rules.json`, `config/site.json`, `data/corrections-log.json` |

## Design

An editorial "data desk" look: warm newsprint with a night edition, Newsreader
(serif, self-hosted) for text and Martian Mono for figures. The signature
element is the **days-seen ruler** on every listing: a 0–130 day scale with the
new window (`FRESH_MAX_DAYS`) and long-open zone (`LONG_OPEN_MIN_DAYS`) shaded,
a needle at `days_seen`, and a `‹` when the listing was up before tracking began.
All threshold values come from `config/rules.json`.

Works at phone width, in light and dark mode, and respects
`prefers-reduced-motion`.
