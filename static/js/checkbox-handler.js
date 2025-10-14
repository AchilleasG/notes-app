/**
 * Checkbox Handler for Interactive Task Lists
 * Handles checkbox clicks and updates note content
 */

class CheckboxHandler {
    constructor() {
        this.currentContent = '';
        this.noteId = null;
        this.noteType = 'regular'; // 'regular' or 'shared'
        this.isEncrypted = false;
        this.encryptionPassword = null;
        this.encryptionSalt = null;
        this.updateUrl = null;
        this.csrfToken = null;
        this.onContentUpdate = null; // Callback after content update
    }

    /**
     * Initialize the checkbox handler
     * @param {Object} config - Configuration object
     */
    init(config) {
        this.currentContent = config.content || '';
        this.noteId = config.noteId;
        this.noteType = config.noteType || 'regular';
        this.isEncrypted = config.isEncrypted || false;
        this.encryptionPassword = config.encryptionPassword || null;
        this.encryptionSalt = config.encryptionSalt || null;
        this.updateUrl = config.updateUrl;
        this.csrfToken = config.csrfToken || this.getCSRFToken();
        this.onContentUpdate = config.onContentUpdate || null;
        
        // Attach event listeners
        this.attachCheckboxListeners();
    }

    /**
     * Get CSRF token from page
     */
    getCSRFToken() {
        const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
        if (tokenElement) {
            return tokenElement.value;
        }
        
        // Try to get from cookie
        const name = 'csrftoken';
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                return cookie.substring(name.length + 1);
            }
        }
        
        return null;
    }

    /**
     * Attach click listeners to all interactive checkboxes
     */
    attachCheckboxListeners() {
        // Use event delegation on the document
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('task-checkbox') && 
                e.target.classList.contains('interactive') &&
                !e.target.disabled) {
                this.handleCheckboxClick(e.target);
            }
        });
    }

    /**
     * Handle checkbox click
     * @param {HTMLInputElement} checkbox - The clicked checkbox
     */
    async handleCheckboxClick(checkbox) {
        // Prevent default to handle it ourselves
        const newCheckedState = checkbox.checked;
        
        // Find the position of this checkbox in the markdown
        const checkboxIndex = this.findCheckboxIndex(checkbox);
        
        if (checkboxIndex === -1) {
            console.error('Could not find checkbox in markdown');
            return;
        }
        
        // Update the markdown content
        const updatedContent = this.updateCheckboxInMarkdown(this.currentContent, checkboxIndex, newCheckedState);
        
        // Save the updated content
        try {
            await this.saveNoteContent(updatedContent);
            this.currentContent = updatedContent;
            console.log('Checkbox state saved successfully');
            
            // Call the callback if provided
            if (this.onContentUpdate) {
                this.onContentUpdate(updatedContent);
            }
        } catch (error) {
            console.error('Failed to save checkbox state:', error);
            // Revert the checkbox state
            checkbox.checked = !newCheckedState;
            alert('Failed to save checkbox state. Please try again.');
        }
    }

    /**
     * Find the index of a checkbox in the markdown
     * @param {HTMLInputElement} checkbox - The checkbox element
     * @returns {number} - The index of the checkbox (0-based)
     */
    findCheckboxIndex(checkbox) {
        // Find all checkboxes in the document
        const allCheckboxes = document.querySelectorAll('.task-checkbox.interactive');
        
        for (let i = 0; i < allCheckboxes.length; i++) {
            if (allCheckboxes[i] === checkbox) {
                return i;
            }
        }
        
        return -1;
    }

    /**
     * Update a checkbox state in the markdown content
     * @param {string} markdown - The markdown content
     * @param {number} checkboxIndex - The index of the checkbox to update
     * @param {boolean} checked - The new checked state
     * @returns {string} - The updated markdown
     */
    updateCheckboxInMarkdown(markdown, checkboxIndex, checked) {
        // Find all checkbox patterns in the markdown
        const checkboxPattern = /-\s*\[([ xX])\]/g;
        const matches = [];
        let match;
        
        while ((match = checkboxPattern.exec(markdown)) !== null) {
            matches.push({
                index: match.index,
                checked: match[1].toLowerCase() === 'x',
                fullMatch: match[0]
            });
        }
        
        if (checkboxIndex >= matches.length) {
            console.error('Checkbox index out of range');
            return markdown;
        }
        
        // Update the specific checkbox
        const targetMatch = matches[checkboxIndex];
        const newCheckbox = checked ? '- [x]' : '- [ ]';
        
        const before = markdown.substring(0, targetMatch.index);
        const after = markdown.substring(targetMatch.index + targetMatch.fullMatch.length);
        
        return before + newCheckbox + after;
    }

    /**
     * Save the updated note content
     * @param {string} content - The updated content
     */
    async saveNoteContent(content) {
        if (!this.updateUrl) {
            throw new Error('Update URL not configured');
        }
        
        let finalContent = content;
        let encryptedContent = '';
        let salt = this.encryptionSalt;
        
        // Encrypt if needed
        if (this.isEncrypted && this.encryptionPassword) {
            if (typeof window.noteEncryption === 'undefined') {
                throw new Error('Encryption module not available');
            }
            
            const result = await window.noteEncryption.encrypt(
                content,
                this.encryptionPassword,
                this.encryptionSalt
            );
            
            encryptedContent = result.encrypted;
            salt = result.salt;
            finalContent = ''; // Clear plaintext
        }
        
        // Prepare form data
        const formData = new URLSearchParams();
        formData.append('content', finalContent);
        if (encryptedContent) {
            formData.append('encrypted_content', encryptedContent);
            formData.append('salt', salt);
            formData.append('is_locked', 'on');
        }
        formData.append('ajax_update', 'true');
        
        // Send update request
        const response = await fetch(this.updateUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': this.csrfToken,
            },
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Update failed: ${response.statusText}`);
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error('Update failed');
        }
    }

    /**
     * Update the current content (e.g., after decryption)
     * @param {string} content - The new content
     */
    updateContent(content) {
        this.currentContent = content;
    }
}

// Create global instance
window.checkboxHandler = new CheckboxHandler();
