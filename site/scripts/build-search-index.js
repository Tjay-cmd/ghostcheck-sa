/**
 * Build search index with content hashing
 * Generates search-index.{hash}.json in dist/data/
 */

import { writeFileSync, mkdirSync, existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';

const DIST_DIR = './dist';
const DATA_DIR = join(DIST_DIR, 'data');
const SOURCE_DATA_DIR = existsSync('../data/listings') ? '../data' : '../data/_samples';

function buildSearchIndex() {
  console.log('🔍 Building search index...');
  
  // Ensure data directory exists
  if (!existsSync(DATA_DIR)) {
    mkdirSync(DATA_DIR, { recursive: true });
  }
  
  // Load listings
  const listingsDir = join(SOURCE_DATA_DIR, 'listings');
  const listingFiles = readdirSync(listingsDir).filter(f => f.endsWith('.json'));
  const listings = listingFiles.map(file => {
    const content = readFileSync(join(listingsDir, file), 'utf-8');
    return JSON.parse(content);
  });
  
  // Load employers for name lookup
  const employersDir = join(SOURCE_DATA_DIR, 'employers');
  const employerFiles = readdirSync(employersDir).filter(f => f.endsWith('.json'));
  const employers = employerFiles.map(file => {
    const content = readFileSync(join(employersDir, file), 'utf-8');
    return JSON.parse(content);
  });
  
  // Create employer lookup
  const employerMap = new Map();
  employers.forEach(emp => {
    employerMap.set(emp.slug, emp.name);
  });
  
  // Build employer index (dedup)
  const employerIndex = new Map();
  let employerCounter = 0;
  
  const openListings = listings.filter(l => l.status === 'open');
  
  openListings.forEach(listing => {
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
  const rows = openListings.map(listing => {
    const employerData = employerIndex.get(listing.employer_slug);
    if (!employerData) {
      throw new Error(`Employer not found: ${listing.employer_slug}`);
    }
    const employerId = employerData.id;
    
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
