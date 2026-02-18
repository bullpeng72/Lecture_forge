// Search functionality - Korean/English compatible substring search
//
// Why not Lunr.js for full-text indexing?
// - Lunr's trimmer uses /^\W+/ and /\W+$/ which are ASCII-only (\W = [^A-Za-z0-9_]).
//   Korean-only tokens (e.g. "인공지능") are entirely \W, so the trimmer reduces
//   them to "" and they never enter the index.
// - Removing the trimmer fixes Korean indexing but breaks English: tokens like
//   "AI는" (English + Korean particle) were previously trimmed to "ai"; without
//   the trimmer they stay as "ai는" and no longer match an "ai" query.
// - Fixing this properly requires a full Korean morphological analyzer.
//
// Simple substring search handles both languages correctly with zero extra deps.

let documents = [];

// Populate the documents array from lecture section data
function initSearch(lectureData) {
    documents = lectureData.sections.map(function (section, idx) {
        return {
            id: section.section_id,
            title: section.title,
            content: section.markdown_content,
            sectionNumber: idx + 1
        };
    });
}

// Search function: case-insensitive substring match for Korean and English
function performSearch(query) {
    if (!query || query.length < 2 || !documents.length) {
        return [];
    }

    var q = query.toLowerCase();

    return documents
        .map(function (doc) {
            var titleHit   = doc.title.toLowerCase().includes(q);
            var contentHit = doc.content.toLowerCase().includes(q);
            // Title matches are weighted higher (10×) than body matches
            var score = (titleHit ? 10 : 0) + (contentHit ? 1 : 0);
            return score > 0 ? Object.assign({}, doc, { score: score }) : null;
        })
        .filter(Boolean)
        .sort(function (a, b) { return b.score - a.score; });
}

// Display search results
function displaySearchResults(results) {
    var resultsContainer = document.getElementById('searchResultsList');

    if (results.length === 0) {
        resultsContainer.innerHTML = '<p class="text-gray-500">검색 결과가 없습니다.</p>';
        return;
    }

    resultsContainer.innerHTML = results.map(function (result) {
        return (
            '<div class="p-3 border border-gray-200 rounded hover:bg-gray-50 cursor-pointer"' +
            '     onclick="navigateToSection(\'' + result.id + '\')">' +
            '    <h4 class="font-semibold text-blue-600">' +
            '        ' + result.sectionNumber + '. ' + result.title +
            '    </h4>' +
            '    <p class="text-sm text-gray-600 mt-1">' +
            '        ' + result.content.substring(0, 150) + '...' +
            '    </p>' +
            '</div>'
        );
    }).join('');
}

// Navigate to section
function navigateToSection(sectionId) {
    closeSearch();
    var element = document.getElementById(sectionId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Close search modal
function closeSearch() {
    document.getElementById('searchResults').classList.add('hidden');
}

// Event listeners
document.addEventListener('DOMContentLoaded', function () {
    var searchBox = document.getElementById('searchBox');

    // Populate documents from lecture data injected by the template
    if (typeof LECTURE_DATA !== 'undefined') {
        initSearch(LECTURE_DATA);
    }

    // Search on input with debounce
    var searchTimeout;
    searchBox.addEventListener('input', function (e) {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(function () {
            var query = e.target.value.trim();
            if (query.length >= 2) {
                var results = performSearch(query);
                displaySearchResults(results);
                document.getElementById('searchResults').classList.remove('hidden');
            } else {
                closeSearch();
            }
        }, 300);
    });

    // Close search on ESC key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeSearch();
        }
    });

    // Close search when clicking outside the modal
    document.getElementById('searchResults').addEventListener('click', function (e) {
        if (e.target === this) {
            closeSearch();
        }
    });
});
