// Smart Search - Renderer Script
// Handles search input, keyboard navigation, and results display

// State
let results = [];
let selectedIndex = -1;
let isLoading = false;

// DOM Elements
const searchInput = document.getElementById('search-input');
const resultsContainer = document.getElementById('results');
const statusText = document.getElementById('status-text');
const settingsBtn = document.getElementById('settings-btn');
const settingsPopup = document.getElementById('settings-popup');
const autoStartCheckbox = document.getElementById('auto-start-checkbox');

// File type icons mapping
const fileIcons = {
  '.py': { icon: '🐍', class: 'icon-python' },
  '.js': { icon: '📜', class: 'icon-js' },
  '.ts': { icon: '📜', class: 'icon-js' },
  '.txt': { icon: '📄', class: 'icon-text' },
  '.md': { icon: '📝', class: 'icon-text' },
  '.pdf': { icon: '📕', class: 'icon-pdf' },
  '.doc': { icon: '📘', class: 'icon-doc' },
  '.docx': { icon: '📘', class: 'icon-doc' },
  '.xlsx': { icon: '📗', class: 'icon-doc' },
  '.png': { icon: '🖼️', class: 'icon-image' },
  '.jpg': { icon: '🖼️', class: 'icon-image' },
  '.jpeg': { icon: '🖼️', class: 'icon-image' },
  '.gif': { icon: '🖼️', class: 'icon-image' },
  '.html': { icon: '🌐', class: 'icon-js' },
  '.css': { icon: '🎨', class: 'icon-js' },
  '.json': { icon: '{ }', class: 'icon-js' },
};

// Get icon for file type
function getFileIcon(fileType) {
  return fileIcons[fileType] || { icon: '📄', class: 'icon-default' };
}

// Debounce helper
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Perform search
async function performSearch(query) {
  if (!query || query.trim().length === 0) {
    results = [];
    renderResults();
    return;
  }

  isLoading = true;
  showLoading();

  try {
    const response = await window.api.search(query);
    
    if (response.error) {
      console.error('Search error:', response.error);
      showError(response.error);
    } else {
      results = response.results || [];
      selectedIndex = results.length > 0 ? 0 : -1;
      renderResults();
      updateStatus(`${results.length} results`);
    }
  } catch (error) {
    console.error('Search failed:', error);
    showError('Search failed');
  }

  isLoading = false;
}

// Render results
function renderResults() {
  if (results.length === 0) {
    resultsContainer.innerHTML = `
      <div class="empty-state">
        <p>${searchInput.value ? 'No results found' : 'Press <strong>Ctrl+Space</strong> to search'}</p>
      </div>
    `;
    return;
  }

  const html = results.map((result, index) => {
    const iconInfo = getFileIcon(result.file_type);
    const isSelected = index === selectedIndex;
    
    return `
      <div class="result-item ${isSelected ? 'selected' : ''}" data-index="${index}">
        <div class="file-icon ${iconInfo.class}">${iconInfo.icon}</div>
        <div class="result-info">
          <div class="result-name">${escapeHtml(result.file_name)}</div>
          <div class="result-snippet">${escapeHtml(result.snippet)}</div>
        </div>
        <div class="result-score">${(result.final_score * 100).toFixed(0)}%</div>
      </div>
    `;
  }).join('');

  resultsContainer.innerHTML = html;

  // Add click handlers
  document.querySelectorAll('.result-item').forEach(item => {
    item.addEventListener('click', () => {
      const index = parseInt(item.dataset.index);
      openResult(index);
    });
  });
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Show loading state
function showLoading() {
  resultsContainer.innerHTML = '<div class="loading">Searching...</div>';
  updateStatus('Searching...');
}

// Show error message
function showError(message) {
  resultsContainer.innerHTML = `<div class="empty-state"><p>Error: ${escapeHtml(message)}</p></div>`;
  updateStatus('Error');
}

// Update status text
function updateStatus(text) {
  statusText.textContent = text;
}

// Open selected result
async function openResult(index) {
  if (index < 0 || index >= results.length) return;
  
  const result = results[index];
  
  try {
    await window.api.openFile(result.path);
    await window.api.hideWindow();
  } catch (error) {
    console.error('Failed to open file:', error);
  }
}

// Show file in folder
async function showInFolder(index) {
  if (index < 0 || index >= results.length) return;
  
  const result = results[index];
  
  try {
    await window.api.showInFolder(result.path);
  } catch (error) {
    console.error('Failed to show in folder:', error);
  }
}

// Move selection
function moveSelection(direction) {
  if (results.length === 0) return;
  
  selectedIndex += direction;
  
  // Clamp to valid range
  if (selectedIndex < 0) selectedIndex = results.length - 1;
  if (selectedIndex >= results.length) selectedIndex = 0;
  
  // Re-render to update selection
  renderResults();
  
  // Scroll selected item into view
  const selectedItem = document.querySelector('.result-item.selected');
  if (selectedItem) {
    selectedItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
}

// ==============================================================================
// Event Listeners
// ==============================================================================

// Search input handler with debounce
searchInput.addEventListener('input', debounce((e) => {
  performSearch(e.target.value);
}, 200));

// Keyboard navigation
searchInput.addEventListener('keydown', (e) => {
  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault();
      moveSelection(1);
      break;
      
    case 'ArrowUp':
      e.preventDefault();
      moveSelection(-1);
      break;
      
    case 'Enter':
      e.preventDefault();
      openResult(selectedIndex);
      break;
      
    case 'Escape':
      e.preventDefault();
      window.api.hideWindow();
      break;
  }
});

// Listen for focus search from main process (Ctrl+Space)
window.api.onFocusSearch(() => {
  searchInput.value = '';
  searchInput.focus();
  results = [];
  selectedIndex = -1;
  renderResults();
});

// Initialize
updateStatus('Ready');

// Toggle settings popup
settingsBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  settingsPopup.classList.toggle('hidden');
});

// Close settings when clicking elsewhere
document.addEventListener('click', (e) => {
  if (!settingsPopup.contains(e.target) && e.target !== settingsBtn) {
    settingsPopup.classList.add('hidden');
  }
});

// Handle auto-start toggle
autoStartCheckbox.addEventListener('change', async (e) => {
  try {
    await window.api.setAutoLaunch(e.target.checked);
    updateStatus(e.target.checked ? 'Will start with Windows' : 'Removed from startup');
  } catch (error) {
    console.error('Failed to set auto-launch:', error);
    e.target.checked = !e.target.checked;
  }
});
