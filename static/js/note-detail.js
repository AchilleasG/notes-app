(function() {
    function renderMarkdown(markdown) {
        const preview = document.getElementById('noteContent');
        if (!preview || !window.markdownRenderer) {
            return;
        }
        preview.innerHTML = window.markdownRenderer.render(markdown || '', true);
    }

    function initCheckboxHandler(markdown) {
        if (typeof CheckboxHandler === 'undefined' || !window.noteContext) {
            return;
        }
        if (!window.checkboxHandlerInstance) {
            window.checkboxHandlerInstance = new CheckboxHandler();
        }
        window.checkboxHandlerInstance.init({
            content: markdown || '',
            noteId: window.noteContext.id,
            isEncrypted: window.noteContext.isLocked,
            encryptionPassword: window.noteContext.encryptionPassword,
            encryptionSalt: window.noteContext.salt,
            updateUrl: window.noteContext.checkboxUpdateUrl,
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        const context = window.noteContext || {};
        const contentField = document.getElementById('content');
        const inlineEditor = document.querySelector('[data-inline-editor="true"]');
        const viewToggleButtons = document.querySelectorAll('.view-toggle-btn');
        const actionsToggle = document.getElementById('noteActionsToggle');
        const actionsPanel = document.getElementById('noteActionsPanel');
        const sidebarContainer = document.querySelector('.sidebar-note-list[data-collapsible]');
        const sidebarToggle = sidebarContainer ? sidebarContainer.querySelector('.sidebar-toggle') : null;
        const sidebarPanel = document.getElementById('sidebarNotes');
        const inlineFormFields = document.getElementById('inlineFormFields');
        const metaToggle = document.getElementById('metaToggle');

        let currentViewMode = 'rendered';

        const initialContent = context.initialContent || (context.isLocked ? '' : context.content || '');
        if (contentField && context.noteType !== 'canvas' && !context.isLocked) {
            contentField.value = initialContent;
        }
        if (context.noteType !== 'canvas' && !context.isLocked) {
            renderMarkdown(initialContent);
            initCheckboxHandler(initialContent);
        }

        function setViewMode(mode) {
            if (!viewToggleButtons.length) {
                return;
            }
            currentViewMode = mode === 'markdown' ? 'markdown' : 'rendered';
            if (inlineEditor) {
                inlineEditor.setAttribute('data-mode', currentViewMode);
            }
            viewToggleButtons.forEach(btn => {
                const isActive = btn.dataset.mode === currentViewMode;
                btn.classList.toggle('active', isActive);
                btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            });
        }

        if (viewToggleButtons.length && inlineEditor) {
            setViewMode('rendered');
            viewToggleButtons.forEach(btn => {
                btn.addEventListener('click', () => {
                    setViewMode(btn.dataset.mode);
                });
            });
        }

        if (metaToggle && inlineFormFields) {
            metaToggle.addEventListener('click', () => {
                const isCollapsed = inlineFormFields.getAttribute('data-meta-collapsed') !== 'false';
                inlineFormFields.setAttribute('data-meta-collapsed', isCollapsed ? 'false' : 'true');
                metaToggle.setAttribute('aria-expanded', isCollapsed ? 'true' : 'false');
                metaToggle.textContent = isCollapsed ? 'Hide Options' : 'Show Options';
            });
        }

        if (actionsToggle && actionsPanel) {
            actionsToggle.addEventListener('click', () => {
                const isOpen = actionsPanel.classList.toggle('is-open');
                actionsToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            });
        }

        if (sidebarContainer && sidebarToggle && sidebarPanel) {
            const mq = window.matchMedia('(max-width: 768px)');
            const applySidebarState = () => {
                if (mq.matches) {
                    sidebarContainer.classList.add('is-collapsed');
                    sidebarToggle.setAttribute('aria-expanded', 'false');
                } else {
                    sidebarContainer.classList.remove('is-collapsed');
                    sidebarToggle.setAttribute('aria-expanded', 'true');
                }
            };
            applySidebarState();
            mq.addEventListener('change', applySidebarState);
            sidebarToggle.addEventListener('click', () => {
                const collapsed = sidebarContainer.classList.toggle('is-collapsed');
                sidebarToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            });
        }

        if (contentField) {
            contentField.addEventListener('input', () => {
                if (context.noteType === 'canvas') return;
                const value = contentField.value;
                renderMarkdown(value);
                if (window.checkboxHandlerInstance) {
                    initCheckboxHandler(value);
                }
            });
        }

        window.applyDecryptedContent = function(markdown, password, salt) {
            if (contentField) {
                contentField.value = markdown;
                contentField.dataset.notePassword = password;
                contentField.dataset.noteSalt = salt;
            }
            context.isLocked = false;
            context.encryptionPassword = password;
            context.salt = salt;
            context.initialContent = markdown;
            if (window.noteEncryption && context.id) {
                window.noteEncryption.cachePassword(context.id, password);
            }
            const placeholder = document.getElementById('encryptedPlaceholder');
            if (placeholder) {
                placeholder.remove();
            }
            renderMarkdown(markdown);
            initCheckboxHandler(markdown);
            if (inlineEditor) {
                inlineEditor.setAttribute('data-mode', 'rendered');
            }
        };

        window.updateRenderedMarkdown = renderMarkdown;
    });
})();
