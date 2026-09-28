/**
 * Rules and configuration loader
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export interface Rules {
  FRESH_MAX_DAYS: number;
  LONG_OPEN_MIN_DAYS: number;
  CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS: number;
  REPOST_WINDOW_DAYS: number;
  REPOST_RATE_WINDOW_DAYS: number;
  EMPLOYER_METRICS_MIN_TRACKED_DAYS: number;
  EMPLOYER_METRICS_MIN_LISTINGS_SEEN: number;
  OVERVIEW_MIN_TRACKED_DAYS: number;
  OVERVIEW_MIN_OPEN_LISTINGS: number;
  STALE_BUILD_HOURS: number;
  FAILED_STREAK_WARNING_RUNS: number;
  RECENTLY_CLOSED_WINDOW_DAYS: number;
}

export interface SiteConfig {
  CORRECTIONS_EMAIL: string;
  FEATURE_OVERVIEW: boolean;
  SITE_PHASE: 'soft' | 'public';
  POPIA_REVIEWED: boolean;
}

let rulesCache: Rules | null = null;
let siteConfigCache: SiteConfig | null = null;

export function getRules(): Rules {
  if (rulesCache) return rulesCache;
  
  const configPath = resolve(process.cwd(), '../config/rules.json');
  const content = readFileSync(configPath, 'utf-8');
  rulesCache = JSON.parse(content);
  return rulesCache as Rules;
}

export function getSiteConfig(): SiteConfig {
  if (siteConfigCache) return siteConfigCache;
  
  const configPath = resolve(process.cwd(), '../config/site.json');
  const content = readFileSync(configPath, 'utf-8');
  const parsed = JSON.parse(content);
  
  // Allow env var overrides
  siteConfigCache = {
    CORRECTIONS_EMAIL: process.env.CORRECTIONS_EMAIL || parsed.CORRECTIONS_EMAIL,
    FEATURE_OVERVIEW: process.env.FEATURE_OVERVIEW === 'true' ? true : 
                     process.env.FEATURE_OVERVIEW === 'false' ? false : 
                     parsed.FEATURE_OVERVIEW,
    SITE_PHASE: (process.env.SITE_PHASE as 'soft' | 'public') || parsed.SITE_PHASE,
    POPIA_REVIEWED: process.env.POPIA_REVIEWED === 'true' ? true :
                   process.env.POPIA_REVIEWED === 'false' ? false :
                   parsed.POPIA_REVIEWED,
  };
  
  return siteConfigCache;
}
