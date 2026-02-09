// Search functionality using Lunr.js

let searchIndex;
let documents = [];

// Initialize search index
function initSearch(lectureData) {
    // Build documents array
    lectureData.sections.forEach((section, idx) => {
        documents.push({
            id: section.section_id,
            title: section.title,
            content: section.markdown_content,
            sectionNumber: idx + 1
        });
    });

    // Create Lunr index
    searchIndex = lunr(function () {
        this.ref('id');
        this.field('title', { boost: 10 });
        this.field('content');

        documents.forEach(doc => {
            this.add(doc);
        });
    });
}

// Search function
function performSearch(query) {
    if (!query || query.length < 2) {
        return [];
    }

    try {
        const results = searchIndex.search(query);
        return results.map(result => {
            const doc = documents.find(d => d.id === result.ref);
            return {
                ...doc,
                score: result.score
            };
        });
    } catch (e) {
        console.error('Search error:', e);
        return [];
    }
}

// Display search results
function displaySearchResults(results) {
    const resultsContainer = document.getElementById('searchResultsList');

    if (results.length === 0) {
        resultsContainer.innerHTML = '<p class="text-gray-500">검색 결과가 없습니다.</p>';
        return;
    }

    resultsContainer.innerHTML = results.map(result => `
        <div class="p-3 border border-gray-200 rounded hover:bg-gray-50 cursor-pointer"
             onclick="navigateToSection('${result.id}')">
            <h4 class="font-semibold text-blue-600">
                ${result.sectionNumber}. ${result.title}
            </h4>
            <p class="text-sm text-gray-600 mt-1">
                ${result.content.substring(0, 150)}...
            </p>
        </div>
    `).join('');
}

// Navigate to section
function navigateToSection(sectionId) {
    closeSearch();
    const element = document.getElementById(sectionId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Close search modal
function closeSearch() {
    document.getElementById('searchResults').classList.add('hidden');
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    const searchBox = document.getElementById('searchBox');

    // Initialize search with lecture data (will be injected by template)
    if (typeof LECTURE_DATA !== 'undefined') {
        initSearch(LECTURE_DATA);
    }

    // Search on input with debounce
    let searchTimeout;
    searchBox.addEventListener('input', function(e) {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            const query = e.target.value.trim();
            if (query.length >= 2) {
                const results = performSearch(query);
                displaySearchResults(results);
                document.getElementById('searchResults').classList.remove('hidden');
            } else {
                closeSearch();
            }
        }, 300);
    });

    // Close search on ESC key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeSearch();
        }
    });

    // Close search when clicking outside
    document.getElementById('searchResults').addEventListener('click', function(e) {
        if (e.target === this) {
            closeSearch();
        }
    });
});
