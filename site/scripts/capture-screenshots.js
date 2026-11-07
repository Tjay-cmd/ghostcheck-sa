/**
 * Screenshot capture script using Playwright
 * Captures all pages at 360px and 1280px widths
 */

import { chromium } from 'playwright';
import { mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const SCREENSHOTS_DIR = join(__dirname, '../docs/screenshots');
const BASE_URL = 'http://localhost:4321';

const PAGES = [
  { name: 'home', path: '/', widths: [360, 1280] },
  { name: 'home-not-enough-data', path: '/', widths: [360, 1280], note: 'collecting data state' },
  { name: 'employers-index', path: '/employers/', widths: [360, 1280] },
  { name: 'employer-detail', path: '/employers/example-bank/', widths: [360, 1280] },
  { name: 'listing-detail', path: '/employers/example-bank/bmqvzc53r8/', widths: [360, 1280] },
  { name: 'listings-new', path: '/listings/new/', widths: [360, 1280] },
  { name: 'listings-open-90-plus', path: '/listings/open-90-plus/', widths: [360, 1280] },
  { name: 'listings-reposted', path: '/listings/reposted/', widths: [360, 1280] },
  { name: 'overview', path: '/overview/', widths: [360, 1280] },
  { name: 'about', path: '/about/', widths: [360, 1280] },
];

async function captureScreenshots() {
  // Create screenshots directory
  mkdirSync(SCREENSHOTS_DIR, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('📸 Capturing screenshots...\n');

  for (const pageInfo of PAGES) {
    const { name, path, widths } = pageInfo;
    
    for (const width of widths) {
      const filename = `${name}-${width}px.png`;
      const filepath = join(SCREENSHOTS_DIR, filename);
      
      try {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(`${BASE_URL}${path}`, { waitUntil: 'networkidle' });
        
        // Wait a bit for fonts to load
        await page.waitForTimeout(500);
        
        await page.screenshot({ path: filepath, fullPage: true });
        console.log(`✅ ${filename}`);
      } catch (error) {
        console.log(`❌ ${filename}: ${error.message}`);
      }
    }
  }

  await browser.close();
  console.log(`\n✅ Screenshots saved to ${SCREENSHOTS_DIR}`);
}

captureScreenshots().catch(console.error);
