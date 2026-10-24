# GhostCheck SA Frontend

Static Astro site for [GhostCheck SA](https://ghostcheck.pages.dev) — tracks South African employer job listings and shows how long they've been up.

## Tech Stack

- **Astro 5** — static site generation
- **TypeScript** — type safety
- **Vitest** — unit testing
- **Plain CSS** — no framework, small bundle

## Prerequisites

- Node.js 22+ (or 20+)
- npm 10+

## Setup

```bash
cd site
npm install
```

## Development

```bash
npm run dev
```

Opens http://localhost:4321

The site reads from `../data/` (real pipeline output) or falls back to `../data/_samples/` (example data).

## Build

```bash
npm run build
```

Output goes to `dist/`. The build:
- Generates all static routes from the data files
- Respects feature flags from `../config/site.json` and env vars
- Content-hashes the search index
- Produces a budget report

## Test

```bash
npm test              # Run tests once
npm run test:watch    # Watch mode
```

Tests cover:
- Format utilities (dates, badges, copy strings)
- Badge logic against rules.json constants
- Null metrics never rendering as 0%
- Feature flags (FEATURE_OVERVIEW build exclusion)
- Budget checks

## Environment Variables & Flags

All flags default to values in `../config/site.json`. Env vars override:

| Variable | Type | Default | Description |
|---|---|---|---|
| `CORRECTIONS_EMAIL` | string | `[CORRECTIONS_EMAIL_TBD]` | Corrections contact email |
| `FEATURE_OVERVIEW` | boolean | `false` | Enable /overview/ route |
| `SITE_PHASE` | `soft`\|`public` | `soft` | Soft = test note in footer |
| `POPIA_REVIEWED` | boolean | `false` | Remove "Draft" label from POPIA |
| `PUBLIC_CF_WEB_ANALYTICS_TOKEN` | string | — | Cloudflare Web Analytics token (optional) |

**Soft launch (late Oct 2026):**
```bash
FEATURE_OVERVIEW=false SITE_PHASE=soft npm run build
```

**Public launch (early Feb 2027):**
```bash
FEATURE_OVERVIEW=true SITE_PHASE=public npm run build
```

## Deployment (Cloudflare Pages)

### Settings

- **Build command:** `npm run build`
- **Build output directory:** `dist`
- **Root directory:** `site`
- **Node version:** 22 (or latest)

### Environment Variables

Set these in the Cloudflare Pages dashboard:

| Variable | Production | Preview |
|---|---|---|
| `FEATURE_OVERVIEW` | `true` | `false` |
| `SITE_PHASE` | `public` | `soft` |
| `POPIA_REVIEWED` | `true` (once reviewed) | `false` |
| `PUBLIC_CF_WEB_ANALYTICS_TOKEN` | (token) | (optional) |

### Build Cache

Cache `node_modules` between builds for faster deploys.

### Preview Deployments

PRs get preview URLs automatically. They build with soft-launch flags by default.

## Budget Limits

Per-page budgets (F9 from handoff):

| Asset | Limit |
|---|---|
| HTML (gzip) | ≤ 25 KB |
| CSS (gzip) | ≤ 12 KB |
| JS (home) | ≤ 8 KB |
| JS (other) | ≤ 2 KB |
| Total first load | < 100 KB |

Run `npm run budget` after building to verify. The build fails if budgets are exceeded.

## Data Contract

The site reads from:
- `../config/rules.json` — rule constants (thresholds)
- `../config/site.json` — site flags
- `../data/site.json` — build metadata
- `../data/employers/*.json` — employer records
- `../data/listings/*.json` — listing detail
- `../data/overview.json` — overview data (if FEATURE_OVERVIEW)
- `../data/search-index.json` — compact search index
- `../data/corrections-log.json` — public corrections log

All data loading goes through `src/lib/data.ts`, so a contract field rename is a one-file change.

Schema validation: `cd ../contract && python validate.py`

## File Structure

```
site/
├── src/
│   ├── components/     AgeBadge, RepostBadge, ListingCard, MetricCard, etc.
│   ├── layouts/        BaseLayout, ProseLayout
│   ├── lib/            data.ts, rules.ts, format.ts
│   ├── pages/          All routes
│   ├── scripts/        Client JS (search, sort)
│   └── styles/         global.css
├── public/             _redirects, favicon.svg
├── dist/               Build output (gitignored)
└── tests/              Vitest tests
```

## Routes

All routes in `handoff.md` Part A, §A1:

- `/` — Home/search
- `/listings/new/`, `/listings/open-90-plus/`, `/listings/reposted/` — Static filters
- `/employers/` — A–Z index
- `/employers/{slug}/` — Employer detail
- `/employers/{slug}/{listing_id}/` — Listing detail (open + closed)
- `/overview/` — Employer listing overview (only if FEATURE_OVERVIEW)
- `/about/` — About & methodology
- `/404` — Not found

## Accessibility

- WCAG 2.1 AA contrast ratios (style-guide.md)
- 44px tap targets
- Visible 2px focus rings
- `<time datetime>` for all dates
- Badge state conveyed by icon + text + color + border, not color alone
- Works at 320px width
- Browsing works without JS (search requires JS)

## License

To be determined.

## Contract Questions for Backend

(To be filled in during implementation if any contract issues arise)

None so far.
