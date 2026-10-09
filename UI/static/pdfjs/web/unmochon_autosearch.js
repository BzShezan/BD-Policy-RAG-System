// Auto-trigger search from URL hash after PDF loads.
// Loaded as external file (not inline) to comply with PDF.js CSP.

console.log('[unmochon] autosearch script loaded');

window.addEventListener('load', function () {
  const hash = window.location.hash;
  const searchMatch = hash.match(/[#&]search=([^&]+)/);
  if (!searchMatch) {
    console.log('[unmochon] no search param in URL');
    return;
  }

  const searchTerm = decodeURIComponent(searchMatch[1]);
  console.log('[unmochon] searchTerm:', searchTerm);

  const tryFind = function (attempt) {
    if (attempt > 30) {
      console.log('[unmochon] gave up waiting for PDFViewerApplication');
      return;
    }
    if (window.PDFViewerApplication &&
        window.PDFViewerApplication.eventBus &&
        window.PDFViewerApplication.pdfDocument) {
      console.log('[unmochon] PDF ready, dispatching find event');
      window.PDFViewerApplication.eventBus.dispatch('find', {
        source: window,
        type: '',
        query: searchTerm,
        phraseSearch: false,
        caseSensitive: false,
        entireWord: false,
        highlightAll: true,
        findPrevious: false,
      });
    } else {
      setTimeout(function () { tryFind(attempt + 1); }, 500);
    }
  };
  tryFind(0);
});