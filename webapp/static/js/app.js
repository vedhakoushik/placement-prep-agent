// Global utilities used across pages

// Safe markdown renderer — strips any raw HTML from AI output before rendering
function safeMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text || ''));
}

// Highlight active nav link based on current path
document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    if (link.getAttribute('href') === path) {
      link.classList.add('active');
    }
  });
});
