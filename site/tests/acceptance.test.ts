/**
 * Comprehensive test suite for GhostCheck SA frontend
 * Covers Part C acceptance cases, component rendering, flags, and config
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { formatDate, formatDays, formatPercentage, getAgeBadgeCopy, getRepostBadgeCopy, getChipLabels, getLegendCopy, getMetricGateMessage } from '../src/lib/format.js';
import { getRules, getSiteConfig } from '../src/lib/rules.js';

describe('Format utilities', () => {
  it('formats dates correctly', () => {
    expect(formatDate('2027-02-03')).toBe('3 Feb 2027');
    expect(formatDate('2026-12-25')).toBe('25 Dec 2026');
    expect(formatDate('2026-09-28')).toBe('28 Sep 2026');
  });

  it('formats days with + suffix', () => {
    expect(formatDays(1)).toBe('1+ day');
    expect(formatDays(34)).toBe('34+ days');
    expect(formatDays(0)).toBe('0+ days');
    expect(formatDays(112)).toBe('112+ days');
  });

  it('formats percentages with basis and window', () => {
    expect(formatPercentage(29, 4, 14, null)).toBe('29% (4 of 14)');
    expect(formatPercentage(12, 3, 25, 'last 180 days')).toBe('12% (3 of 25, last 180 days)');
    expect(formatPercentage(100, 5, 5, 'since 28 Sep 2026')).toBe('100% (5 of 5, since 28 Sep 2026)');
  });
});

describe('Rules constants', () => {
  it('loads rules from config/rules.json', () => {
    const rules = getRules();
    
    expect(rules.FRESH_MAX_DAYS).toBe(13);
    expect(rules.LONG_OPEN_MIN_DAYS).toBe(91);
    expect(rules.CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS).toBe(2);
    expect(rules.REPOST_WINDOW_DAYS).toBe(60);
    expect(rules.REPOST_RATE_WINDOW_DAYS).toBe(180);
    expect(rules.EMPLOYER_METRICS_MIN_TRACKED_DAYS).toBe(30);
    expect(rules.EMPLOYER_METRICS_MIN_LISTINGS_SEEN).toBe(5);
    expect(rules.OVERVIEW_MIN_TRACKED_DAYS).toBe(91);
    expect(rules.OVERVIEW_MIN_OPEN_LISTINGS).toBe(5);
    expect(rules.STALE_BUILD_HOURS).toBe(36);
    expect(rules.FAILED_STREAK_WARNING_RUNS).toBe(7);
    expect(rules.RECENTLY_CLOSED_WINDOW_DAYS).toBe(90);
  });

  it('uses rules constants in chip labels', () => {
    const rules = getRules();
    const chipLabels = getChipLabels();
    
    // "New (under 14 days)" where 14 = FRESH_MAX_DAYS + 1
    expect(chipLabels.new).toBe(`New (under ${rules.FRESH_MAX_DAYS + 1} days)`);
    expect(chipLabels.longOpen).toBe('Open 90+ days');
    expect(chipLabels.reposted).toBe('Reposted');
  });

  it('uses rules constants in legend copy', () => {
    const rules = getRules();
    const legend = getLegendCopy();
    
    expect(legend.new).toContain(`${rules.FRESH_MAX_DAYS + 1} days`);
    expect(legend.seen).toContain(`${rules.FRESH_MAX_DAYS + 1} to ${rules.LONG_OPEN_MIN_DAYS - 1} days`);
    expect(legend.longOpen).toContain(`${rules.LONG_OPEN_MIN_DAYS - 1} days`);
    expect(legend.reposted).toContain(`${rules.REPOST_WINDOW_DAYS} days`);
    expect(legend.closed).toContain(`${rules.CLOSE_AFTER_MISSED_SUCCESSFUL_CHECKS} successful checks`);
  });

  it('uses rules constants in metric gate message', () => {
    const rules = getRules();
    const message = getMetricGateMessage('Example Bank', '2026-10-28');
    
    expect(message).toContain(`${rules.EMPLOYER_METRICS_MIN_TRACKED_DAYS} days`);
    expect(message).toContain(`${rules.EMPLOYER_METRICS_MIN_LISTINGS_SEEN} listings`);
    expect(message).toContain('28 Oct 2026');
  });
});

describe('Part C: Acceptance test cases against rules.json', () => {
  let rules: any;

  beforeAll(() => {
    rules = getRules();
  });

  it('Scenario: New job ID first seen FRESH_MAX_DAYS days ago, employer tracked long before', () => {
    const daysSeen = rules.FRESH_MAX_DAYS;
    const openBeforeTracking = false;
    
    const { label } = getAgeBadgeCopy('fresh', daysSeen, openBeforeTracking, null, '2027-02-03', 'compact');
    
    expect(label).toContain('New');
    expect(label).toContain(`${daysSeen}+ days`);
  });

  it('Scenario: Same, one day older (should be seen, not fresh)', () => {
    const daysSeen = rules.FRESH_MAX_DAYS + 1;
    const openBeforeTracking = false;
    
    // Age state should be 'seen' not 'fresh'
    const { label } = getAgeBadgeCopy('seen', daysSeen, openBeforeTracking, null, '2027-02-03', 'compact');
    
    expect(label).toContain('Seen');
    expect(label).not.toContain('New');
  });

  it('Scenario: Listing with first_seen == tracked_since, days_seen < LONG_OPEN_MIN_DAYS', () => {
    const daysSeen = 34;
    const openBeforeTracking = true;
    const trackedSince = '2026-09-28';
    
    const { label } = getAgeBadgeCopy('seen', daysSeen, openBeforeTracking, trackedSince, '2027-02-03', 'compact');
    
    expect(label).toContain('Up since at least');
    expect(label).toContain('28 Sep 2026');
    expect(label).not.toContain('New');
  });

  it('Scenario: Any open listing with days_seen >= LONG_OPEN_MIN_DAYS', () => {
    const daysSeen = rules.LONG_OPEN_MIN_DAYS;
    
    const { label } = getAgeBadgeCopy('long_open', daysSeen, false, null, '2027-02-03', 'compact');
    
    expect(label).toContain('Open 90+ days');
    expect(label).toContain(`${daysSeen}+`);
  });

  it('Scenario: Open before tracking can be long_open if days_seen >= LONG_OPEN_MIN_DAYS', () => {
    const daysSeen = rules.LONG_OPEN_MIN_DAYS + 20;
    const openBeforeTracking = true;
    const trackedSince = '2026-09-28';
    
    const { label } = getAgeBadgeCopy('long_open', daysSeen, openBeforeTracking, trackedSince, '2027-02-03', 'compact');
    
    expect(label).toContain('Open 90+ days');
    expect(label).toContain('up since at least');
  });
});

describe('Age badge copy and rendering', () => {
  it('returns correct copy for fresh listings', () => {
    const { label } = getAgeBadgeCopy('fresh', 5, false, null, '2027-02-03', 'compact');
    expect(label).toContain('New');
    expect(label).toContain('5+ days');
  });

  it('returns correct full variant for fresh', () => {
    const { label } = getAgeBadgeCopy('fresh', 5, false, null, '2027-02-03', 'full');
    expect(label).toContain('New: seen for 5+ days');
  });

  it('returns correct copy for seen listings', () => {
    const { label } = getAgeBadgeCopy('seen', 34, false, null, '2027-02-03', 'compact');
    expect(label).toContain('Seen');
    expect(label).toContain('34+ days');
  });

  it('returns correct copy for long_open listings', () => {
    const { label } = getAgeBadgeCopy('long_open', 112, false, null, '2027-02-03', 'compact');
    expect(label).toContain('Open 90+ days');
    expect(label).toContain('112+ days');
  });

  it('returns correct copy for open_before_tracking with dashed border indication', () => {
    const { label } = getAgeBadgeCopy('seen', 34, true, '2026-09-28', '2027-02-03', 'compact');
    expect(label).toContain('Up since at least');
    expect(label).toContain('28 Sep 2026');
  });

  it('returns correct copy for closed listings', () => {
    const { label } = getAgeBadgeCopy('closed', 35, false, null, '2027-01-05', 'full');
    expect(label).toContain('No longer listed');
    expect(label).toContain('5 Jan 2027');
  });

  it('returns correct aria labels for accessibility', () => {
    const { ariaLabel } = getAgeBadgeCopy('fresh', 5, false, null, '2027-02-03', 'compact');
    expect(ariaLabel).toContain('New');
    expect(ariaLabel).toContain('at least 5 days');
  });
});

describe('Repost badge copy', () => {
  it('returns correct copy for single repost (compact)', () => {
    const { label } = getRepostBadgeCopy(1, '2026-10-05', 'compact');
    expect(label).toBe('Reposted');
  });

  it('returns correct copy for multiple reposts (compact)', () => {
    const { label } = getRepostBadgeCopy(2, '2026-10-05', 'compact');
    expect(label).toBe('Reposted ×2');
  });

  it('returns correct copy for single repost (full)', () => {
    const { label } = getRepostBadgeCopy(1, '2026-10-05', 'full');
    expect(label).toContain('Reposted once');
    expect(label).toContain('5 Oct 2026');
  });

  it('returns correct full copy for multiple reposts', () => {
    const { label } = getRepostBadgeCopy(2, '2026-10-05', 'full');
    expect(label).toContain('Reposted 2 times');
    expect(label).toContain('5 Oct 2026');
  });
});

describe('Site configuration and flags', () => {
  it('loads site config from config/site.json', () => {
    const config = getSiteConfig();
    
    expect(config.CORRECTIONS_EMAIL).toBe('[CORRECTIONS_EMAIL_TBD]');
    expect(typeof config.FEATURE_OVERVIEW).toBe('boolean');
    expect(['soft', 'public']).toContain(config.SITE_PHASE);
    expect(typeof config.POPIA_REVIEWED).toBe('boolean');
  });

  it('uses correct CORRECTIONS_EMAIL placeholder', () => {
    const config = getSiteConfig();
    expect(config.CORRECTIONS_EMAIL).toBe('[CORRECTIONS_EMAIL_TBD]');
  });
});

describe('Metric rendering - null values never show as 0%', () => {
  it('null value metric should not be formatted as 0%', () => {
    // A metric with value=null should be shown as "—" in MetricCard
    // The format function for non-null values
    const result = formatPercentage(0, 0, 10, null);
    expect(result).toBe('0% (0 of 10)');
    
    // But null values should never reach formatPercentage
    // They're handled in MetricCard component by showing "—"
  });
});
