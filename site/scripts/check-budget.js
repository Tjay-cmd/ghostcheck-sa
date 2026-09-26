/**
 * Budget verification script
 * Checks that built files meet size requirements
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';

const DIST_DIR = './dist';

const BUDGETS = {
  html: 25 * 1024, // 25 KB gzip
  css: 12 * 1024, // 12 KB gzip
  jsHome: 8 * 1024, // 8 KB for home page
  jsOther: 2 * 1024, // 2 KB for other pages
  totalFirstLoad: 100 * 1024, // 100 KB uncompressed
};

function getGzipSize(filePath) {
  const content = readFileSync(filePath);
  const compressed = gzipSync(content);
  return compressed.length;
}

function getFileSize(filePath) {
  return statSync(filePath).size;
}

function findFiles(dir, ext) {
  const files = [];
  const items = readdirSync(dir, { withFileTypes: true });
  
  for (const item of items) {
    const fullPath = join(dir, item.name);
    if (item.isDirectory()) {
      files.push(...findFiles(fullPath, ext));
    } else if (item.name.endsWith(ext)) {
      files.push(fullPath);
    }
  }
  
  return files;
}

function checkBudgets() {
  console.log('🔍 Checking build budgets...\n');
  
  let failed = false;
  const results = [];
  
  // Check HTML files
  const htmlFiles = findFiles(DIST_DIR, '.html');
  console.log(`📄 HTML Files (${htmlFiles.length}):`);
  
  for (const file of htmlFiles) {
    const gzipSize = getGzipSize(file);
    const path = file.replace(DIST_DIR + '/', '');
    const status = gzipSize <= BUDGETS.html ? '✅' : '❌';
    const sizeKB = (gzipSize / 1024).toFixed(2);
    const budgetKB = (BUDGETS.html / 1024).toFixed(0);
    
    console.log(`  ${status} ${path}: ${sizeKB} KB gzip (budget: ${budgetKB} KB)`);
    
    if (gzipSize > BUDGETS.html) {
      failed = true;
    }
    
    results.push({ type: 'html', path, size: gzipSize, budget: BUDGETS.html });
  }
  
  // Check CSS files
  const cssFiles = findFiles(DIST_DIR, '.css');
  console.log(`\n🎨 CSS Files (${cssFiles.length}):`);
  
  for (const file of cssFiles) {
    const gzipSize = getGzipSize(file);
    const path = file.replace(DIST_DIR + '/', '');
    const status = gzipSize <= BUDGETS.css ? '✅' : '❌';
    const sizeKB = (gzipSize / 1024).toFixed(2);
    const budgetKB = (BUDGETS.css / 1024).toFixed(0);
    
    console.log(`  ${status} ${path}: ${sizeKB} KB gzip (budget: ${budgetKB} KB)`);
    
    if (gzipSize > BUDGETS.css) {
      failed = true;
    }
    
    results.push({ type: 'css', path, size: gzipSize, budget: BUDGETS.css });
  }
  
  // Check JS files
  const jsFiles = findFiles(DIST_DIR, '.js');
  console.log(`\n📦 JavaScript Files (${jsFiles.length}):`);
  
  for (const file of jsFiles) {
    const fileSize = getFileSize(file);
    const path = file.replace(DIST_DIR + '/', '');
    
    // Determine budget based on path
    const isHome = path.includes('index') || path.includes('_astro/hoisted');
    const budget = isHome ? BUDGETS.jsHome : BUDGETS.jsOther;
    const status = fileSize <= budget ? '✅' : '❌';
    const sizeKB = (fileSize / 1024).toFixed(2);
    const budgetKB = (budget / 1024).toFixed(0);
    
    console.log(`  ${status} ${path}: ${sizeKB} KB (budget: ${budgetKB} KB${isHome ? ' home' : ' other'})`);
    
    if (fileSize > budget) {
      failed = true;
    }
    
    results.push({ type: 'js', path, size: fileSize, budget });
  }
  
  // Summary
  console.log('\n' + '='.repeat(60));
  
  if (failed) {
    console.log('❌ Budget check FAILED');
    console.log('\nFiles exceeding budget:');
    
    for (const result of results) {
      if (result.size > result.budget) {
        const overage = ((result.size - result.budget) / 1024).toFixed(2);
        console.log(`  - ${result.path}: +${overage} KB over budget`);
      }
    }
    
    process.exit(1);
  } else {
    console.log('✅ All budgets passed!');
    process.exit(0);
  }
}

checkBudgets();
