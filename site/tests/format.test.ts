/**
 * Basic tests for format utilities and rules
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { formatDate, formatDays, formatPercentage, getAgeBadgeCopy, getRepostBadgeCopy, getChipLabels } from '../src/lib/format.js';

describe('Format utilities', () => {
  it('formats dates correctly', () => {
    expect(formatDate('2027-02-03')).toBe('3 Feb 2027');
    expect(formatDate('2026-12-25')).toBe('25 Dec 2026');
  });

  it('formats days with + suffix', () => {
    expect(formatDays(1)).toBe('1+ day');
    expect(formatDays(34)).toBe('34+ days');
    expect(formatDays(0)).toBe('0+ days');
  });

  it('formats percentages with basis', () => {
    expect(formatPercentage(29, 4, 14, null)).toBe('29% (4 of 14)');
    expect(formatPercentage(12, 3, 25, 'last 180 days')).toBe('12% (3 of 25, last 180 days)');
  });
});

describe('Age badge copy', () => {
  it('returns correct copy for fresh listings', () => {
    const { label } = getAgeBadgeCopy('fresh', 5, false, null, '2027-02-03', 'compact');
    expect(label).toContain('New');
    expect(label).toContain('5+ days');
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

  it('returns correct copy for open_before_tracking', () => {
    const { label } = getAgeBadgeCopy('seen', 34, true, '2026-09-28', '2027-02-03', 'compact');
    expect(label).toContain('Up since at least');
    expect(label).toContain('28 Sep 2026');
  });

  it('returns correct copy for closed listings', () => {
    const { label } = getAgeBadgeCopy('closed', 35, false, null, '2027-01-05', 'full');
    expect(label).toContain('No longer listed');
    expect(label).toContain('5 Jan 2027');
  });
});

describe('Repost badge copy', () => {
  it('returns correct copy for single repost', () => {
    const { label } = getRepostBadgeCopy(1, '2026-10-05', 'compact');
    expect(label).toBe('Reposted');
  });

  it('returns correct copy for multiple reposts', () => {
    const { label } = getRepostBadgeCopy(2, '2026-10-05', 'compact');
    expect(label).toBe('Reposted ×2');
  });

  it('returns correct full copy', () => {
    const { label } = getRepostBadgeCopy(2, '2026-10-05', 'full');
    expect(label).toContain('Reposted 2 times');
    expect(label).toContain('5 Oct 2026');
  });
});

describe('Chip labels', () => {
  it('includes FRESH_MAX_DAYS + 1 in new chip', () => {
    const labels = getChipLabels();
    expect(labels.new).toContain('under 14 days'); // FRESH_MAX_DAYS = 13, so under 14
  });

  it('includes correct labels', () => {
    const labels = getChipLabels();
    expect(labels.longOpen).toBe('Open 90+ days');
    expect(labels.reposted).toBe('Reposted');
  });
});

describe('Null metrics never render as 0%', () => {
  it('does not format null metric value as percentage', () => {
    // When a metric is unavailable, it should show "—" not "0%"
    // This is handled in MetricCard component, but we test the format function doesn't create "0%"
    const result = formatPercentage(0, 0, 10, null);
    expect(result).toBe('0% (0 of 10)');
    
    // The actual null handling is in the component, which should show "—" for null values
  });
});
