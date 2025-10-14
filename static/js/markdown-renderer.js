/**
 * Client-side Markdown Renderer
 * Handles all markdown rendering with custom checkbox support
 * Works for encrypted, decrypted, shared, and regular notes
 */

class MarkdownRenderer {
    constructor() {
        this.checkboxIdCounter = 0;
        this.markedConfigured = false;
    }

    /**
     * Render markdown to HTML
     * @param {string} markdown - The markdown content to render
     * @param {boolean} interactiveCheckboxes - Whether checkboxes should be clickable (true for detail view, false for list view)
     * @returns {string} - The rendered HTML
     */
    render(markdown, interactiveCheckboxes = true) {
        if (!markdown) return '';
        
        // Ensure marked.js is available
        if (typeof marked === 'undefined') {
            console.error('marked.js not loaded yet');
            return '<p>Loading markdown renderer...</p>';
        }
        
        // Configure marked.js if not already configured
        if (!this.markedConfigured) {
            marked.setOptions({
                breaks: true,
                gfm: true,
                tables: true,
                sanitize: false,
                smartLists: true,
                smartypants: false
            });
            this.markedConfigured = true;
        }
        
        // Reset checkbox counter for each render to avoid ID conflicts
        this.checkboxIdCounter = 0;
        
        // Use marked.js to render markdown
        let html = marked.parse(markdown);
        
        // Post-process to add custom checkbox styling
        html = this.processCheckboxes(html, interactiveCheckboxes);
        
        return html;
    }

    /**
     * Process checkboxes to add custom styling and behavior
     * @param {string} html - The HTML to process
     * @param {boolean} interactive - Whether checkboxes should be clickable
     * @returns {string} - The processed HTML
     */
    processCheckboxes(html, interactive) {
        // Replace task list checkboxes with custom styled ones
        // Process checked checkboxes FIRST (more specific pattern)
        html = html.replace(
            /<li>\s*<input([^>]*)type="checkbox"([^>]*)checked([^>]*)>\s*/gi,
            (match, before, middle, after) => {
                const checkboxId = `checkbox-${this.checkboxIdCounter++}`;
                const disabledAttr = interactive ? '' : ' disabled';
                const className = interactive ? 'task-checkbox interactive' : 'task-checkbox';
                return `<li class="task-list-item"><input type="checkbox" class="${className}" id="${checkboxId}" data-checked="true" checked${disabledAttr}><label for="${checkboxId}"></label>`;
            }
        );
        
        // Then process unchecked checkboxes (will not match already processed checked ones)
        html = html.replace(
            /<li>\s*<input([^>]*)type="checkbox"([^>]*)>\s*/gi,
            (match, before, after) => {
                // Skip if this is already a processed checkbox
                if (match.includes('task-checkbox')) {
                    return match;
                }
                const checkboxId = `checkbox-${this.checkboxIdCounter++}`;
                const disabledAttr = interactive ? '' : ' disabled';
                const className = interactive ? 'task-checkbox interactive' : 'task-checkbox';
                return `<li class="task-list-item"><input type="checkbox" class="${className}" id="${checkboxId}" data-checked="false"${disabledAttr}><label for="${checkboxId}"></label>`;
            }
        );
        
        return html;
    }

    /**
     * Render markdown preview (truncated)
     * @param {string} markdown - The markdown content
     * @param {number} wordCount - Number of words to show
     * @returns {string} - The rendered preview HTML
     */
    renderPreview(markdown, wordCount = 30) {
        if (!markdown) return '';
        
        // Ensure marked.js is available
        if (typeof marked === 'undefined') {
            console.error('marked.js not loaded yet for preview');
            return '<p>Loading...</p>';
        }
        
        // First render the full markdown
        let html = this.render(markdown, false); // Non-interactive for previews
        
        // Strip HTML tags to count words
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        const text = tempDiv.textContent || tempDiv.innerText || '';
        
        // Split into words
        const words = text.trim().split(/\s+/);
        
        if (words.length <= wordCount) {
            return html;
        }
        
        // Truncate the original markdown and re-render
        const markdownWords = markdown.trim().split(/\s+/);
        const truncatedMarkdown = markdownWords.slice(0, wordCount).join(' ');
        
        return this.render(truncatedMarkdown, false) + '...';
    }

    /**
     * Get custom CSS for checkboxes
     * @returns {string} - CSS styles as a string
     */
    static getCheckboxStyles() {
        return `
            /* Custom checkbox styles */
            .task-list-item {
                list-style: none;
                position: relative;
                padding-left: 0;
            }
            
            .task-checkbox {
                appearance: none;
                -webkit-appearance: none;
                width: 20px;
                height: 20px;
                border: 2px solid var(--border-primary);
                border-radius: 4px;
                background: var(--bg-primary);
                cursor: pointer;
                position: relative;
                vertical-align: middle;
                margin-right: 10px;
                transition: all 0.2s ease;
            }
            
            .task-checkbox:hover:not(:disabled) {
                border-color: var(--accent-primary);
                background: var(--accent-light);
            }
            
            .task-checkbox:checked {
                background: var(--accent-primary);
                border-color: var(--accent-primary);
            }
            
            .task-checkbox:checked::after {
                content: '✓';
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            
            .task-checkbox:disabled {
                cursor: default;
                opacity: 0.6;
            }
            
            .task-checkbox:disabled:hover {
                border-color: var(--border-primary);
                background: var(--bg-primary);
            }
            
            .task-checkbox:disabled:checked {
                background: var(--accent-primary);
                opacity: 0.6;
            }
            
            /* Hide the default label (we use the checkbox itself) */
            .task-checkbox + label {
                display: none;
            }
        `;
    }
}

// Create global instance
window.markdownRenderer = new MarkdownRenderer();

// Function to inject checkbox styles into the page
function injectCheckboxStyles() {
    const styleId = 'markdown-checkbox-styles';
    
    // Check if styles already injected
    if (document.getElementById(styleId)) {
        return;
    }
    
    const styleElement = document.createElement('style');
    styleElement.id = styleId;
    styleElement.textContent = MarkdownRenderer.getCheckboxStyles();
    document.head.appendChild(styleElement);
}

// Inject styles when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectCheckboxStyles);
} else {
    injectCheckboxStyles();
}
