/**
 * Note Preview Renderer
 * Shared functionality for rendering markdown previews in note lists
 * Works for both regular notes and shared notes
 */

(function () {
    'use strict';

    /**
     * Render all markdown previews on the page
     * Should be called after the DOM is loaded and marked.js is available
     */
    function renderNotePreviews() {
        const previews = document.querySelectorAll('.note-preview[data-markdown]');

        if (previews.length === 0) {
            return;
        }

        // Check if dependencies are available
        if (!window.markdownRenderer) {
            console.error('markdownRenderer not available');
            return;
        }

        if (typeof marked === 'undefined') {
            console.error('marked.js not loaded');
            return;
        }

        // Render each preview
        previews.forEach(preview => {
            let markdown = preview.getAttribute('data-markdown');
            const isPreview = preview.getAttribute('data-preview') === 'true';

            if (!markdown) {
                return;
            }

            try {
                // Unescape the content - Django's escapejs creates escaped strings
                // We need to properly decode escape sequences
                markdown = markdown
                    .replace(/\\u000D\\u000A/g, '\n')  // Windows line ending
                    .replace(/\\u000A/g, '\n')          // Unix line ending
                    .replace(/\\u000D/g, '\n')          // Mac line ending
                    .replace(/\\u0022/g, '"')           // Escaped double quote
                    .replace(/\\u0027/g, "'")           // Escaped single quote
                    .replace(/\\u002D/g, '-')           // Escaped dash/hyphen
                    .replace(/\\u005B/g, '[')           // Escaped left bracket
                    .replace(/\\u005D/g, ']')           // Escaped right bracket
                    .replace(/\\u003C/g, '<')           // Escaped less than
                    .replace(/\\u003E/g, '>')           // Escaped greater than
                    .replace(/\\u0026/g, '&')           // Escaped ampersand
                    .replace(/\\n/g, '\n')              // Escaped newline
                    .replace(/\\r/g, '\r')              // Escaped carriage return
                    .replace(/\\t/g, '\t')              // Escaped tab
                    .replace(/\\"/g, '"')               // Escaped quote
                    .replace(/\\'/g, "'")               // Escaped single quote
                    .replace(/\\\\/g, '\\');            // Escaped backslash

                let html;
                if (isPreview) {
                    // For list view - show truncated preview with non-interactive checkboxes
                    html = window.markdownRenderer.renderPreview(markdown, 30);
                } else {
                    // For full view - show complete content with interactive checkboxes
                    html = window.markdownRenderer.render(markdown, true);
                }

                preview.innerHTML = html;
            } catch (error) {
                console.error('Failed to render markdown preview:', error);
                // Fallback to plain text preview
                const plainText = markdown.replace(/[#*_\[\]()]/g, '').substring(0, 100);
                preview.textContent = plainText + (markdown.length > 100 ? '...' : '');
            }
        });
    }

    /**
     * Initialize the preview renderer
     * Waits for both DOM and marked.js to be ready
     */
    function initPreviewRenderer() {
        // Check if marked.js is already loaded
        if (typeof marked !== 'undefined' && window.markdownRenderer) {
            renderNotePreviews();
            return;
        }

        // Wait a bit for marked.js to load
        let attempts = 0;
        const maxAttempts = 20; // 2 seconds max

        const checkInterval = setInterval(function () {
            attempts++;

            if (typeof marked !== 'undefined' && window.markdownRenderer) {
                clearInterval(checkInterval);
                renderNotePreviews();
            } else if (attempts >= maxAttempts) {
                clearInterval(checkInterval);
                console.error('Timeout waiting for marked.js and markdownRenderer');
            }
        }, 100);
    }

    // Export to global scope
    window.renderNotePreviews = renderNotePreviews;
    window.initPreviewRenderer = initPreviewRenderer;

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPreviewRenderer);
    } else {
        // DOM already loaded, initialize immediately
        initPreviewRenderer();
    }
})();
