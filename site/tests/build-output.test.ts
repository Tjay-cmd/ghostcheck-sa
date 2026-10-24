/**
 * Build output and flag tests
 * Tests that feature flags work correctly and build outputs are as expected
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { getSiteConfig } from '../src/lib/rules.js';

const DIST_DIR = join(process.cwd(), 'dist');

describe('Feature flags - FEATURE_OVERVIEW', () => {
  it('overview page should be generated when FEATURE_OVERVIEW is true', () => {
    // This test runs against the current build
    // In a flag-off build, we'd check that overview doesn't exist
    const config = getSiteConfig();
    
    if (config.FEATURE_OVERVIEW) {
      const overviewPath = join(DIST_DIR, 'overview', 'index.html');
      if (existsSync(DIST_DIR)) {
        expect(existsSync(overviewPath)).toBe(true);
      }
    }
  });

  it('should not link to overview when FEATURE_OVERVIEW is false', () => {
    const config = getSiteConfig();
    
    if (!config.FEATURE_OVERVIEW && existsSync(DIST_DIR)) {
      // Check that no HTML files contain links to /overview/
      const htmlFiles = findHtmlFiles(DIST_DIR);
      
      for (const file of htmlFiles) {
        const content = readFileSync(file, 'utf-8');
        
        // Should not have href="/overview/" or href="/overview"
        expect(content).not.toMatch(/href="\/overview\/"/);
        expect(content).not.toMatch(/href="\/overview"/);
      }
    }
  });
});

describe('Feature flags - SITE_PHASE', () => {
  it('shows test version note in footer when SITE_PHASE=soft', () => {
    const config = getSiteConfig();
    
    if (config.SITE_PHASE === 'soft' && existsSync(DIST_DIR)) {
      const homePath = join(DIST_DIR, 'index.html');
      if (existsSync(homePath)) {
        const content = readFileSync(homePath, 'utf-8');
        expect(content).toContain('Test version');
      }
    }
  });

  it('does not show test version note when SITE_PHASE=public', () => {
    const config = getSiteConfig();
    
    if (config.SITE_PHASE === 'public' && existsSync(DIST_DIR)) {
      const homePath = join(DIST_DIR, 'index.html');
      if (existsSync(homePath)) {
        const content = readFileSync(homePath, 'utf-8');
        expect(content).not.toContain('Test version');
      }
    }
  });
});

describe('Feature flags - POPIA_REVIEWED', () => {
  it('shows "Draft, pending review" label when POPIA_REVIEWED=false', () => {
    const config = getSiteConfig();
    
    if (!config.POPIA_REVIEWED && existsSync(DIST_DIR)) {
      const aboutPath = join(DIST_DIR, 'about', 'index.html');
      if (existsSync(aboutPath)) {
        const content = readFileSync(aboutPath, 'utf-8');
        expect(content).toContain('Draft, pending review');
      }
    }
  });

  it('does not show draft label when POPIA_REVIEWED=true', () => {
    const config = getSiteConfig();
    
    if (config.POPIA_REVIEWED && existsSync(DIST_DIR)) {
      const aboutPath = join(DIST_DIR, 'about', 'index.html');
      if (existsSync(aboutPath)) {
        const content = readFileSync(aboutPath, 'utf-8');
        expect(content).not.toContain('Draft, pending review');
      }
    }
  });
});

describe('Configuration - CORRECTIONS_EMAIL', () => {
  it('uses CORRECTIONS_EMAIL placeholder in all pages', () => {
    const config = getSiteConfig();
    
    if (existsSync(DIST_DIR)) {
      const aboutPath = join(DIST_DIR, 'about', 'index.html');
      if (existsSync(aboutPath)) {
        const content = readFileSync(aboutPath, 'utf-8');
        expect(content).toContain(config.CORRECTIONS_EMAIL);
      }
    }
  });
});

describe('Apply links use correct attributes', () => {
  it('apply links use target="_blank" rel="noopener nofollow"', () => {
    if (!existsSync(DIST_DIR)) return;
    
    // Check listing detail pages
    const listingsDir = join(DIST_DIR, 'employers');
    if (!existsSync(listingsDir)) return;
    
    const employerDirs = readdirSync(listingsDir, { withFileTypes: true })
      .filter(d => d.isDirectory());
    
    for (const employerDir of employerDirs.slice(0, 2)) {
      const employerPath = join(listingsDir, employerDir.name);
      const listingDirs = readdirSync(employerPath, { withFileTypes: true })
        .filter(d => d.isDirectory());
      
      for (const listingDir of listingDirs.slice(0, 1)) {
        const listingPath = join(employerPath, listingDir.name, 'index.html');
        if (existsSync(listingPath)) {
          const content = readFileSync(listingPath, 'utf-8');
          
          // Find apply button/link
          if (content.includes('Apply on')) {
            // Should have target="_blank" and rel="noopener nofollow"
            const applyLinkMatch = content.match(/<a[^>]*Apply on[^>]*>/);
            if (applyLinkMatch) {
              const link = applyLinkMatch[0];
              expect(link).toContain('target="_blank"');
              expect(link).toContain('rel="noopener nofollow"');
            }
          }
        }
      }
    }
  });
});

describe('External origin restrictions', () => {
  it('no page references external origins except Cloudflare beacon', () => {
    if (!existsSync(DIST_DIR)) return;
    
    const htmlFiles = findHtmlFiles(DIST_DIR).slice(0, 10);
    const allowedOrigins = [
      'static.cloudflareinsights.com', // Cloudflare Web Analytics
    ];
    
    for (const file of htmlFiles) {
      const content = readFileSync(file, 'utf-8');
      
      // Find all external URLs (http:// or https://), excluding SVG namespaces
      const externalUrls = (content.match(/https?:\/\/[^"'\s]+/g) || [])
        .filter(url => !url.includes('w3.org'));
      
      for (const url of externalUrls) {
        const isAllowed = allowedOrigins.some(origin => url.includes(origin));
        
        // Allow data URLs from employer career sites
        const isEmployerUrl = url.includes('myworkdayjobs.com') || url.includes('example');
        
        if (!isAllowed && !isEmployerUrl) {
          console.log(`Unexpected external URL: ${url} in ${file}`);
        }
        expect(isAllowed || isEmployerUrl).toBe(true);
      }
    }
  });
});

describe('Search index content hashing', () => {
  it('search index should be content-hashed', () => {
    if (!existsSync(DIST_DIR)) return;
    
    const dataDir = join(DIST_DIR, 'data');
    if (!existsSync(dataDir)) return;
    
    const files = readdirSync(dataDir);
    const searchIndexFiles = files.filter(f => f.startsWith('search-index') && f.endsWith('.json'));
    
    if (searchIndexFiles.length > 0) {
      // Should have hash in filename
      const hashedFile = searchIndexFiles.find(f => f.match(/search-index\.[a-z0-9]+\.json/));
      expect(hashedFile).toBeDefined();
    }
  });
});

// Helper functions
function findHtmlFiles(dir: string): string[] {
  const files: string[] = [];
  
  if (!existsSync(dir)) return files;
  
  const items = readdirSync(dir, { withFileTypes: true });
  
  for (const item of items) {
    const fullPath = join(dir, item.name);
    if (item.isDirectory()) {
      files.push(...findHtmlFiles(fullPath));
    } else if (item.name.endsWith('.html')) {
      files.push(fullPath);
    }
  }
  
  return files;
}
