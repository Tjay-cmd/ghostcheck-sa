/**
 * Formatting utilities for dates, numbers, and badge copy
 */

import { getRules } from './rules';

/**
 * Format a SAST date as "26 Sep 2026"
 */
export function formatDate(dateStr: string): string {
  // Parse YYYY-MM-DD as local date, not UTC
  const [year, month, day] = dateStr.split('-').map(Number);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${day} ${months[month - 1]} ${year}`;
}

/**
 * Format a datetime as "26 Sep 2026, 06:12"
 */
export function formatDateTime(datetimeStr: string): string {
  const date = new Date(datetimeStr);
  const day = date.getDate();
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = months[date.getMonth()];
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${day} ${month} ${year}, ${hours}:${minutes}`;
}

/**
 * Format just the time as "06:12"
 */
export function formatTime(datetimeStr: string): string {
  const date = new Date(datetimeStr);
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

/**
 * Format days count as "34+ days"
 */
export function formatDays(days: number): string {
  return `${days}+ day${days === 1 ? '' : 's'}`;
}

/**
 * Format a percentage with its basis: "29% (4 of 14, last 180 days)"
 */
export function formatPercentage(
  value: number,
  numerator: number,
  denominator: number,
  windowLabel: string | null
): string {
  const basis = `${numerator} of ${denominator}`;
  const window = windowLabel ? `, ${windowLabel}` : '';
  return `${value}% (${basis}${window})`;
}

/**
 * Get age badge copy strings
 */
export function getAgeBadgeCopy(
  ageState: 'fresh' | 'seen' | 'long_open' | 'closed',
  daysSeen: number,
  openBeforeTracking: boolean,
  trackedSince: string | null,
  lastSeen: string | null,
  variant: 'compact' | 'full'
): { label: string; ariaLabel: string } {
  if (ageState === 'closed') {
    const label = variant === 'compact' 
      ? 'No longer listed'
      : `No longer listed: last seen ${lastSeen ? formatDate(lastSeen) : 'unknown'}`;
    return { label, ariaLabel: 'No longer listed' };
  }

  if (ageState === 'fresh') {
    const daysText = formatDays(daysSeen);
    const label = variant === 'compact' ? `New · ${daysText}` : `New: seen for ${daysText}`;
    return {
      label,
      ariaLabel: `New. Seen for at least ${daysSeen} days by our daily check.`
    };
  }

  if (openBeforeTracking && trackedSince) {
    const dateText = formatDate(trackedSince);
    const label = variant === 'compact' 
      ? `Up since at least ${dateText}`
      : `Up since at least ${dateText}${variant === 'full' ? ' (already listed when we started tracking)' : ''}`;
    return {
      label,
      ariaLabel: `Up since at least ${dateText}. Already listed when we started tracking this employer.`
    };
  }

  if (ageState === 'long_open') {
    const daysText = formatDays(daysSeen);
    const label = variant === 'compact' 
      ? `Open 90+ days · ${daysText}`
      : `Open 90+ days: seen for ${daysText}`;
    return {
      label,
      ariaLabel: `Open 90 plus days. Seen for at least ${daysSeen} days by our daily check.`
    };
  }

  // seen
  const daysText = formatDays(daysSeen);
  const label = variant === 'compact' ? `Seen ${daysText}` : `Seen for ${daysText}`;
  return {
    label,
    ariaLabel: `Seen for at least ${daysSeen} days by our daily check.`
  };
}

/**
 * Get repost badge copy
 */
export function getRepostBadgeCopy(
  repostCount: number,
  chainFirstSeen: string | null,
  variant: 'compact' | 'full'
): { label: string; ariaLabel: string } {
  if (variant === 'compact') {
    const label = repostCount === 1 ? 'Reposted' : `Reposted ×${repostCount}`;
    return {
      label,
      ariaLabel: `Reposted ${repostCount} ${repostCount === 1 ? 'time' : 'times'}`
    };
  }

  const times = repostCount === 1 ? 'once' : `${repostCount} times`;
  const firstSeenText = chainFirstSeen ? formatDate(chainFirstSeen) : 'unknown';
  return {
    label: `Reposted ${times}, first seen ${firstSeenText}`,
    ariaLabel: `Reposted ${times}, first seen ${firstSeenText}`
  };
}

/**
 * Get chip filter labels (from badge-system.md §7)
 */
export function getChipLabels() {
  const rules = getRules();
  return {
    new: `New (under ${rules.FRESH_MAX_DAYS + 1} days)`,
    longOpen: 'Open 90+ days',
    reposted: 'Reposted',
  };
}

/**
 * Get legend copy (from badge-system.md §7)
 */
export function getLegendCopy() {
  const rules = getRules();
  return {
    new: `New: first seen less than ${rules.FRESH_MAX_DAYS + 1} days ago, after we started tracking the employer.`,
    seen: `Seen: seen for ${rules.FRESH_MAX_DAYS + 1} to ${rules.LONG_OPEN_MIN_DAYS - 1} days, or already up when we started tracking (shown as 'Up since at least {date}').`,
    longOpen: `Open 90+ days: seen for more than ${rules.LONG_OPEN_MIN_DAYS - 1} days.`,
    reposted: `Reposted: a new listing with the same title and location appeared while an earlier one was still open, or within ${rules.REPOST_WINDOW_DAYS} days of it closing.`,
    closed: `No longer listed: our check didn't find it on ${rules.CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS} successful checks in a row.`,
  };
}

/**
 * Get metric gate message
 */
export function getMetricGateMessage(employerName: string, availableFrom: string | null) {
  const rules = getRules();
  const expected = availableFrom ? ` Expected from ${formatDate(availableFrom)}.` : '';
  return `Figures appear once we've tracked ${employerName} for ${rules.EMPLOYER_METRICS_MIN_TRACKED_DAYS} days and seen at least ${rules.EMPLOYER_METRICS_MIN_LISTINGS_SEEN} listings.${expected}`;
}

/**
 * Get long open early message
 */
export function getLongOpenEarlyMessage(date: string) {
  return `No listing can reach 90+ days by our count before ${formatDate(date)}.`;
}

/**
 * Get repost window label
 */
export function getRepostWindowLabel(windowLabel: string | null, windowStart: string | null) {
  const rules = getRules();
  if (windowLabel) return windowLabel;
  if (windowStart) return `since ${formatDate(windowStart)}`;
  return `last ${rules.REPOST_RATE_WINDOW_DAYS} days`;
}

/**
 * Get overview rule message
 */
export function getOverviewRuleMessage() {
  const rules = getRules();
  return `To keep comparisons fair, we include employers we've tracked for at least ${rules.OVERVIEW_MIN_TRACKED_DAYS} days that have at least ${rules.OVERVIEW_MIN_OPEN_LISTINGS} open listings.`;
}

/**
 * Get early long open message for home page
 */
export function getEarlyLongOpenMessage(earliestDate: string) {
  return `No listings have been open 90+ days by our count yet. The first can appear on ${formatDate(earliestDate)}.`;
}

/**
 * Get closure method copy
 */
export function getClosureMethodCopy() {
  const rules = getRules();
  return `If our check can't reach a careers page, we don't count that day, and we only mark a listing as gone after missing it on ${rules.CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS} successful checks in a row.`;
}
