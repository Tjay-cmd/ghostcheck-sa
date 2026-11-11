/**
 * Client-side search for home page
 * Lazy-loads search index on first interaction, filters and sorts listings
 * Syncs state with URL query params
 */

interface SearchIndex {
  v: number;
  generated_at: string;
  fields: string[];
  employers: Array<[string, string]>;
  rows: Array<any[]>;
}

interface Listing {
  listing_id: string;
  employer_slug: string;
  employer_name: string;
  title: string;
  location: string | null;
  first_seen: string;
  days_seen: number;
  age_state: 'fresh' | 'seen' | 'long_open';
  open_before_tracking: boolean;
  reposted: boolean;
  repost_count: number;
}

let searchIndex: SearchIndex | null = null;
let isLoading = false;

// Find the hashed search index filename
async function findSearchIndexUrl(): Promise<string> {
  try {
    // Fetch the meta file that contains the hashed filename
    const metaResponse = await fetch('/data/search-index-meta.json');
    if (metaResponse.ok) {
      const meta = await metaResponse.json();
      return meta.url;
    }
  } catch (error) {
    // Fallback to non-hashed version (shouldn't happen in production)
    console.warn('Failed to load search index meta, using fallback');
  }
  
  return '/data/search-index.json';
}

// Load search index
async function loadSearchIndex(): Promise<SearchIndex> {
  if (searchIndex) return searchIndex;
  if (isLoading) {
    // Wait for existing load
    await new Promise(resolve => setTimeout(resolve, 100));
    return loadSearchIndex();
  }
  
  isLoading = true;
  
  try {
    const url = await findSearchIndexUrl();
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to load search index');
    
    searchIndex = await response.json();
    isLoading = false;
    return searchIndex!;
  } catch (error) {
    isLoading = false;
    throw error;
  }
}

// Parse rows into listing objects
function parseListings(index: SearchIndex): Listing[] {
  const fieldMap: Record<string, number> = {};
  index.fields.forEach((field, i) => {
    fieldMap[field] = i;
  });
  
  return index.rows.map(row => {
    const employerIdx = row[fieldMap['employer']] as number;
    const employer = index.employers[employerIdx];
    
    return {
      listing_id: row[fieldMap['listing_id']],
      employer_slug: employer[0],
      employer_name: employer[1],
      title: row[fieldMap['title']],
      location: row[fieldMap['location']],
      first_seen: row[fieldMap['first_seen']],
      days_seen: row[fieldMap['days_seen']],
      age_state: row[fieldMap['age_state']],
      open_before_tracking: Boolean(row[fieldMap['open_before_tracking']]),
      reposted: Boolean(row[fieldMap['reposted']]),
      repost_count: row[fieldMap['repost_count']] || 0,
    };
  });
}

// Filter listings
function filterListings(listings: Listing[], filters: {
  q: string;
  age: string;
  reposted: boolean;
}): Listing[] {
  return listings.filter(listing => {
    // Query filter
    if (filters.q) {
      const query = filters.q.toLowerCase();
      const matchesTitle = listing.title.toLowerCase().includes(query);
      const matchesEmployer = listing.employer_name.toLowerCase().includes(query);
      if (!matchesTitle && !matchesEmployer) return false;
    }
    
    // Age filter
    if (filters.age === 'new' && listing.age_state !== 'fresh') return false;
    if (filters.age === 'long_open' && listing.age_state !== 'long_open') return false;
    
    // Reposted filter
    if (filters.reposted && !listing.reposted) return false;
    
    return true;
  });
}

// Sort listings
function sortListings(listings: Listing[], sortBy: string): Listing[] {
  const sorted = [...listings];
  
  switch (sortBy) {
    case 'longest':
      sorted.sort((a, b) => b.days_seen - a.days_seen);
      break;
    case 'employer':
      sorted.sort((a, b) => a.employer_name.localeCompare(b.employer_name));
      break;
    case 'newest':
    default:
      sorted.sort((a, b) => {
        const dateA = new Date(a.first_seen).getTime();
        const dateB = new Date(b.first_seen).getTime();
        return dateB - dateA;
      });
  }
  
  return sorted;
}

// Get URL params
function getUrlParams(): URLSearchParams {
  return new URLSearchParams(window.location.search);
}

// Update URL params
function updateUrlParams(params: Record<string, string>) {
  const url = new URL(window.location.href);
  Object.entries(params).forEach(([key, value]) => {
    if (value) {
      url.searchParams.set(key, value);
    } else {
      url.searchParams.delete(key);
    }
  });
  window.history.replaceState({}, '', url);
}

// Initialize search UI
export async function initSearch() {
  const searchInput = document.getElementById('search-input') as HTMLInputElement;
  const resultsContainer = document.getElementById('search-results');
  const loadMoreBtn = document.getElementById('load-more-btn');
  const resultCount = document.getElementById('result-count');
  const ageFilters = document.querySelectorAll<HTMLInputElement>('[name="age"]');
  const repostedFilter = document.getElementById('reposted-filter') as HTMLInputElement;
  const sortSelect = document.getElementById('sort-select') as HTMLSelectElement;
  
  if (!searchInput || !resultsContainer) return;
  
  let currentListings: Listing[] = [];
  let filteredListings: Listing[] = [];
  let displayCount = 25;
  
  // Read initial state from URL
  const params = getUrlParams();
  const initialQ = params.get('q') || '';
  const initialAge = params.get('age') || '';
  const initialReposted = params.get('reposted') === '1';
  const initialSort = params.get('sort') || 'newest';
  
  if (initialQ) searchInput.value = initialQ;
  if (initialSort && sortSelect) sortSelect.value = initialSort;
  if (initialReposted && repostedFilter) repostedFilter.checked = true;
  
  ageFilters.forEach(radio => {
    if (radio.value === initialAge) radio.checked = true;
  });
  
  async function performSearch() {
    if (!resultsContainer) return;
    
    try {
      // Load index if not loaded
      if (!searchIndex) {
        const loading = document.createElement('div');
        loading.className = 'search-loading';
        loading.textContent = 'Loading listings...';
        resultsContainer.innerHTML = '';
        resultsContainer.appendChild(loading);
        
        const index = await loadSearchIndex();
        currentListings = parseListings(index);
      }
      
      // Get current filters
      const q = searchInput.value.trim();
      const checkedAge = document.querySelector<HTMLInputElement>('[name="age"]:checked');
      const age = checkedAge?.value || '';
      const reposted = repostedFilter?.checked || false;
      const sort = sortSelect?.value || 'newest';
      
      // Update URL
      updateUrlParams({
        q,
        age,
        reposted: reposted ? '1' : '',
        sort: sort !== 'newest' ? sort : '',
      });
      
      // Filter and sort
      filteredListings = filterListings(currentListings, { q, age, reposted });
      filteredListings = sortListings(filteredListings, sort);
      
      // Update count
      if (resultCount) {
        resultCount.textContent = `${filteredListings.length} listing${filteredListings.length === 1 ? '' : 's'}`;
      }
      
      // Render results
      displayCount = 25;
      renderResults();
      
    } catch (error) {
      resultsContainer.innerHTML = '<div class="search-error">Failed to load search. Please refresh the page.</div>';
    }
  }
  
  function renderResults() {
    if (!resultsContainer) return;
    
    const toShow = filteredListings.slice(0, displayCount);
    
    resultsContainer.innerHTML = '';
    
    if (toShow.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'search-empty';
      empty.innerHTML = '<p>No listings match your search.</p>';
      resultsContainer.appendChild(empty);
      if (loadMoreBtn) loadMoreBtn.style.display = 'none';
      return;
    }
    
    toShow.forEach(listing => {
      const card = createListingCard(listing);
      resultsContainer.appendChild(card);
    });
    
    // Show/hide load more
    if (loadMoreBtn) {
      loadMoreBtn.style.display = filteredListings.length > displayCount ? 'block' : 'none';
    }
  }
  
  function createListingCard(listing: Listing): HTMLElement {
    const card = document.createElement('a');
    card.className = 'listing-card';
    card.href = `/employers/${listing.employer_slug}/${listing.listing_id}/`;
    
    const badges = [];
    if (listing.age_state === 'fresh') {
      badges.push(`<span class="badge badge-new">🌱 New · ${listing.days_seen}+ days</span>`);
    } else if (listing.age_state === 'long_open') {
      badges.push(`<span class="badge badge-long">⏳ Open 90+ days · ${listing.days_seen}+</span>`);
    } else {
      badges.push(`<span class="badge badge-seen">🕐 Seen ${listing.days_seen}+ days</span>`);
    }
    
    if (listing.reposted && listing.repost_count > 0) {
      const label = listing.repost_count === 1 ? 'Reposted' : `Reposted ×${listing.repost_count}`;
      badges.push(`<span class="badge badge-repost">🔁 ${label}</span>`);
    }
    
    card.innerHTML = `
      <div class="listing-card-content">
        <h3 class="listing-title">${escapeHtml(listing.title)}</h3>
        <div class="listing-meta">
          <span class="listing-employer">${escapeHtml(listing.employer_name)}</span>
          ${listing.location ? `<span class="meta-separator">·</span><span class="listing-location">${escapeHtml(listing.location)}</span>` : ''}
        </div>
        <div class="listing-badges">${badges.join('')}</div>
      </div>
      <div class="listing-chevron">›</div>
    `;
    
    return card;
  }
  
  function escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
  
  // Event listeners
  searchInput.addEventListener('focus', () => {
    if (!searchIndex) performSearch();
  });
  
  searchInput.addEventListener('input', () => {
    performSearch();
  });
  
  ageFilters.forEach(radio => {
    radio.addEventListener('change', performSearch);
  });
  
  if (repostedFilter) {
    repostedFilter.addEventListener('change', performSearch);
  }
  
  if (sortSelect) {
    sortSelect.addEventListener('change', performSearch);
  }
  
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener('click', (e) => {
      e.preventDefault();
      displayCount += 25;
      renderResults();
    });
  }
  
  // Initial search if there are URL params
  if (initialQ || initialAge || initialReposted || initialSort !== 'newest') {
    performSearch();
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSearch);
} else {
  initSearch();
}
