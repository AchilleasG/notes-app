/**
 * Client-side Markdown Renderer
 * Handles all markdown rendering with custom checkbox support
 * Works for encrypted, decrypted, shared, and regular notes
 */

class MarkdownRenderer {
    constructor() {
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

        // Use marked.js to render markdown
        let html = marked.parse(markdown);

        // Post-process to replace checkboxes with custom HTML
        html = this.replaceCheckboxesWithCustomHTML(html, interactiveCheckboxes);

        return html;
    }

    /**
     * Replace all checkboxes with custom HTML elements
     * @param {string} html - The HTML to process
     * @param {boolean} interactive - Whether checkboxes should be clickable
     * @returns {string} - The processed HTML
     */
    replaceCheckboxesWithCustomHTML(html, interactive) {
        let checkboxCounter = 0;

        // Create a temporary div to parse HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        // Find all list items with checkboxes
        const listItems = tempDiv.querySelectorAll('li');

        listItems.forEach(li => {
            const checkbox = li.querySelector('input[type="checkbox"]');
            if (checkbox) {
                const isChecked = checkbox.checked || checkbox.hasAttribute('checked');
                const checkboxId = `checkbox-${checkboxCounter++}`;

                // Create custom checkbox HTML
                const customCheckbox = document.createElement('span');
                customCheckbox.className = interactive ? 'custom-checkbox interactive' : 'custom-checkbox';
                customCheckbox.setAttribute('data-checkbox-id', checkboxId);
                customCheckbox.setAttribute('data-checked', isChecked ? 'true' : 'false');
                customCheckbox.innerHTML = isChecked ? '☑' : '☐';

                if (!interactive) {
                    customCheckbox.style.cursor = 'default';
                    customCheckbox.style.pointerEvents = 'none';
                }

                // Add task-list-item class to li
                li.classList.add('task-list-item');

                // Add checked class to li if checked
                if (isChecked) {
                    li.classList.add('checked');
                }

                // Preserve list indentation styling
                // Check parent ul/ol elements and apply indentation
                let parent = li.parentElement;
                let depth = 0;
                while (parent && (parent.tagName === 'UL' || parent.tagName === 'OL')) {
                    depth++;
                    parent = parent.parentElement;
                    if (parent && parent.tagName === 'LI') {
                        parent = parent.parentElement;
                    }
                }

                // Replace the original checkbox with custom one
                checkbox.parentNode.replaceChild(customCheckbox, checkbox);
            }
        });

        return tempDiv.innerHTML;
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

        // Truncate by counting words while preserving structure
        let currentWordCount = 0;
        let truncatedMarkdown = '';
        const lines = markdown.split('\n');

        for (let line of lines) {
            const lineWords = line.trim().split(/\s+/).filter(w => w.length > 0);

            if (currentWordCount + lineWords.length <= wordCount) {
                truncatedMarkdown += line + '\n';
                currentWordCount += lineWords.length;
            } else {
                // Add partial line if we have room
                const remainingWords = wordCount - currentWordCount;
                if (remainingWords > 0) {
                    const partialLine = lineWords.slice(0, remainingWords).join(' ');
                    truncatedMarkdown += partialLine;
                }
                break;
            }
        }

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
            
            .custom-checkbox {
                display: inline-block;
                font-size: 20px;
                line-height: 1;
                margin-right: 8px;
                user-select: none;
                vertical-align: middle;
            }
            
            .custom-checkbox.interactive {
                cursor: pointer;
                transition: transform 0.1s ease;
            }
            
            .custom-checkbox.interactive:hover {
                transform: scale(1.1);
            }
            
            .custom-checkbox.interactive:active {
                transform: scale(0.95);
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
