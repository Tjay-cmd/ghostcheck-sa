/**
 * Build search index with content hashing
 * Generates search-index.{hash}.json in dist/data/
 */

import { writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { getAllListings, getEmployers } from '../src/lib/data.js';

const DIST_DIR = './dist';
const DATA_DIR = join(DIST_DIR, 'data');

function buildSearchIndex() {
  console.log('🔍 Building search index...');
  
  // Ensure data directory exists
  if (!existsSync(DATA_DIR)) {
    mkdirSync(DATA_DIR, { recursive: true });
  }
  
  const listings = getAllListings();
  const employers = getEmployers();
  
  // Create employer lookup
  const employerMap = new Map();
  employers.forEach(emp => {
    employerMap.set(emp.employer_slug, emp.employer_name);
  });
  
  // Build employer index (dedup)
  const employerIndex = new Map();
  let employerCounter = 0;
  
  listings.forEach(listing => {
    if (!employerIndex.has(listing.employer_slug)) {
      employerIndex.set(listing.employer_slug, {
        id: employerCounter++,
        slug: listing.employer_slug,
        name: employerMap.get(listing.employer_slug) || listing.employer_slug,
      });
    }
  });
  
  // Convert to array
  const employersArray = Array.from(employerIndex.values())
    .sort((a, b) => a.id - b.id)
    .map(e => [e.slug, e.name]);
  
  // Fields
  const fields = [
    'listing_id',
    'employer',       // index into employers array
    'title',
    'location',
    'first_seen',
    'days_seen',
    'age_state',
    'open_before_tracking',
    'reposted',
    'repost_count',
  ];
  
  // Build rows
  const rows = listings
    .filter(l => l.status === 'open') // Only open listings in search
    .map(listing => {
      const employerId = employerIndex.get(listing.employer_slug)!.id;
      
      return [
        listing.listing_id,
        employerId,
        listing.title,
        listing.location,
        listing.first_seen,
        listing.days_seen,
        listing.age_state,
        listing.open_before_tracking ? 1 : 0,
        listing.reposted ? 1 : 0,
        listing.repost_count || 0,
      ];
    });
  
  // Create index object
  const searchIndex = {
    v: 1,
    generated_at: new Date().toISOString(),
    fields,
    employers: employersArray,
    rows,
  };
  
  // Serialize
  const content = JSON.stringify(searchIndex);
  
  // Content hash
  const hash = createHash('sha256').update(content).digest('hex').slice(0, 8);
  const filename = `search-index.${hash}.json`;
  const filePath = join(DATA_DIR, filename);
  
  // Write file
  writeFileSync(filePath, content);
  
  const sizeKB = (content.length / 1024).toFixed(2);
  console.log(`✅ Search index: ${filename} (${sizeKB} KB, ${rows.length} listings)`);
  
  // Write meta file for client to find it
  const metaContent = JSON.stringify({ url: `/data/${filename}`, hash });
  writeFileSync(join(DATA_DIR, 'search-index-meta.json'), metaContent);
  
  return filename;
}

try {
  buildSearchIndex();
} catch (error) {
  console.error('❌ Failed to build search index:', error);
  process.exit(1);
}
