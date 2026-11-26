/**
 * Data loading module - single source for all contract data
 * Reads from /data or falls back to /data/_samples
 */

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

// Type definitions matching the contract

export interface SiteData {
  schema_version: number;
  build_time: string;
  data_date: string | null;
  last_successful_run_at: string | null;
  tracking_started_on: string | null;
  stale: {
    stale_after: string | null;
    stale_at_build: boolean;
    last_run_date: string | null;
    last_run_employers_ok: number;
    last_run_employers_failed: number;
  };
  counts: {
    open_listings: number;
    employers_tracked: number;
    employers_with_data: number;
    fresh: number;
    seen: number;
    long_open: number;
    reposted_open: number;
    open_before_tracking_open: number;
    closed_listings: number;
    listings_total: number;
  };
  earliest_long_open_possible_on: string | null;
}

export interface Metric {
  value: number | null;
  unit: string;
  numerator: number | null;
  denominator: number | null;
  window_label: string | null;
  window_start: string | null;
  available: boolean;
  unavailable_reason: string | null;
  available_from: string | null;
}

export interface ListingSummary {
  listing_id: string;
  employer_slug: string;
  employer_name: string;
  title: string;
  location: string | null;
  first_seen: string;
  last_seen: string;
  days_seen: number;
  status: 'open' | 'closed';
  closed_on: string | null;
  age_state: 'fresh' | 'seen' | 'long_open' | 'closed';
  open_before_tracking: boolean;
  reposted: boolean;
  repost_count: number;
  chain_first_seen: string | null;
}

export interface EmployerData {
  schema_version: number;
  id: string;
  slug: string;
  name: string;
  sector: string;
  ats_type: string;
  source_url: string;
  active: boolean;
  tracked_since: string | null;
  tracked_days: number | null;
  has_data: boolean;
  last_run: {
    date: string;
    time: string;
    status: 'ok' | 'blocked' | 'error';
  } | null;
  last_successful_check_at: string | null;
  consecutive_failed_runs: number;
  check_status: 'ok' | 'failed_recent' | 'failed_streak' | 'never_succeeded';
  total_listings_seen: number;
  metrics: {
    open_count: Metric;
    median_days_seen: Metric;
    share_open_90: Metric;
    repost_rate: Metric;
    long_open_possible_from: string | null;
  };
  overview: {
    eligible: boolean;
    eligible_from: string | null;
    reason: string | null;
  };
  listings: {
    open: ListingSummary[];
    recently_closed: ListingSummary[];
  };
}

export interface RepostLink {
  listing_id: string;
  match_basis: string;
  gap_days: number;
}

export interface ChainListing {
  listing_id: string;
  title: string;
  location: string | null;
  first_seen: string;
  last_seen: string;
  days_seen: number;
  status: 'open' | 'closed';
  closed_on: string | null;
  match_basis: string;
  gap_days: number;
}

export interface LaterRepost {
  listing_id: string;
  first_seen: string;
  status: 'open' | 'closed';
}

export interface ListingDetail {
  schema_version: number;
  listing_id: string;
  employer_id: string;
  employer_slug: string;
  employer_name: string;
  ats_job_id: string;
  title: string;
  normalised_title: string;
  location: string | null;
  normalised_location: string | null;
  fingerprint: string;
  url: string;
  apply_domain: string;
  first_seen: string;
  last_seen: string;
  days_seen: number;
  status: 'open' | 'closed';
  closed_on: string | null;
  gaps: Array<{
    closed_on: string;
    reopened_on: string;
  }>;
  age_state: 'fresh' | 'seen' | 'long_open' | 'closed';
  open_before_tracking: boolean;
  reposted: boolean;
  repost_count: number;
  chain_first_seen: string | null;
  repost_of: RepostLink | null;
  chain: ChainListing[];
  later_reposts: LaterRepost[];
  correction_ids: string[];
  employer: {
    tracked_since: string | null;
    active: boolean;
    last_run: {
      date: string;
      time: string;
      status: 'ok' | 'blocked' | 'error';
    } | null;
    last_successful_check_at: string | null;
    consecutive_failed_runs: number;
    check_status: string;
    open_count: number;
  };
  more_at_employer: ListingSummary[];
}

export interface OverviewEmployer {
  slug: string;
  name: string;
  sector: string;
  tracked_since: string;
  tracked_days: number;
  open_count: number;
  median_days_seen: number | null;
  share_open_90: {
    value: number;
    numerator: number;
    denominator: number;
  };
  repost_rate: {
    value: number;
    numerator: number;
    denominator: number;
    window_label: string;
  };
}

export interface OverviewData {
  schema_version: number;
  generated_at: string;
  data_date: string;
  eligible_employers: OverviewEmployer[];
  not_yet_eligible: Array<{
    slug: string;
    name: string;
    eligible_from: string;
    reason: string;
  }>;
}

export interface SearchIndex {
  v: number;
  generated_at: string;
  fields: string[];
  employers: Array<[string, string]>;
  rows: Array<any[]>;
}

export interface CorrectionsLog {
  schema_version: number;
  generated_at: string;
  corrections: Array<{
    id: string;
    date: string;
    employer: string;
    summary: string;
  }>;
}

// Determine data directory
function getDataDir(): string {
  const dataPath = resolve(process.cwd(), '../data');
  const samplesPath = resolve(process.cwd(), '../data/_samples');
  
  // Check if real data exists by looking for site.json
  if (existsSync(join(dataPath, 'site.json'))) {
    return dataPath;
  }
  
  // Fall back to samples
  return samplesPath;
}

export function getSiteData(): SiteData {
  const dataDir = getDataDir();
  const content = readFileSync(join(dataDir, 'site.json'), 'utf-8');
  return JSON.parse(content);
}

export function getEmployerData(slug: string): EmployerData {
  const dataDir = getDataDir();
  const content = readFileSync(join(dataDir, 'employers', `${slug}.json`), 'utf-8');
  return JSON.parse(content);
}

export function getAllEmployers(): EmployerData[] {
  const dataDir = getDataDir();
  const employersDir = join(dataDir, 'employers');
  
  if (!existsSync(employersDir)) {
    return [];
  }
  
  const files = readdirSync(employersDir).filter((f: string) => f.endsWith('.json'));
  return files.map((file: string) => {
    const content = readFileSync(join(employersDir, file), 'utf-8');
    return JSON.parse(content) as EmployerData;
  }).sort((a: EmployerData, b: EmployerData) => a.name.localeCompare(b.name));
}

export function getListingDetail(listingId: string): ListingDetail {
  const dataDir = getDataDir();
  const content = readFileSync(join(dataDir, 'listings', `${listingId}.json`), 'utf-8');
  return JSON.parse(content);
}

export function getAllListings(): ListingSummary[] {
  const employers = getAllEmployers();
  const allListings: ListingSummary[] = [];
  
  for (const employer of employers) {
    allListings.push(...employer.listings.open);
  }
  
  return allListings;
}

export function getOverviewData(): OverviewData | null {
  const dataDir = getDataDir();
  const overviewPath = join(dataDir, 'overview.json');
  
  if (!existsSync(overviewPath)) {
    return null;
  }
  
  const content = readFileSync(overviewPath, 'utf-8');
  return JSON.parse(content);
}

export function getSearchIndex(): SearchIndex {
  const dataDir = getDataDir();
  const content = readFileSync(join(dataDir, 'search-index.json'), 'utf-8');
  return JSON.parse(content);
}

export function getCorrectionsLog(): CorrectionsLog {
  const dataDir = getDataDir();
  const correctionsPath = join(dataDir, 'corrections-log.json');
  
  if (!existsSync(correctionsPath)) {
    return {
      schema_version: 1,
      generated_at: new Date().toISOString(),
      corrections: [],
    };
  }
  
  const content = readFileSync(correctionsPath, 'utf-8');
  return JSON.parse(content);
}
