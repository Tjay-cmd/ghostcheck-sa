# GhostCheck SA Frontend

This directory will contain the Astro static site for GhostCheck SA.

## Planned Structure

The frontend will:
- Read from `../config/` for employer registry, rules, and site flags
- Read from `../data/` for employer summaries, listings, and search index
- Generate static pages for search, employer profiles, and listing details
- Build to a deployable static site (e.g., Vercel, Netlify, GitHub Pages)

## Data Contract

The frontend builds against the data contract defined in `../contract/`:
- Field names and structure are locked (v1)
- All sample files validate against JSON Schema 2020-12
- Cross-file consistency rules are enforced by `../contract/validate.py`

## Development

To be implemented in a future phase after M0 validation.

Planned features:
- Search UI with filters (sector, location, age state)
- Employer profile pages with metrics and open listings
- Listing detail pages with history and repost chains
- Overview dashboard comparing employers
- Responsive design, dark mode, accessibility

## License

To be determined.
