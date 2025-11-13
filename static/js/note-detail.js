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
        const noteContent = document.getElementById('noteContent');
        const editorDrawer = document.querySelector('.note-editor-drawer');
        const viewToggleButtons = document.querySelectorAll('.view-toggle-btn');
        const drawerToggleButtons = document.querySelectorAll('[data-toggle="editor-drawer"]');
        const actionsToggle = document.getElementById('noteActionsToggle');
        const actionsPanel = document.getElementById('noteActionsPanel');
        const sidebarContainer = document.querySelector('.sidebar-note-list[data-collapsible]');
        const sidebarToggle = sidebarContainer ? sidebarContainer.querySelector('.sidebar-toggle') : null;
        const sidebarPanel = document.getElementById('sidebarNotes');

        let manualDrawerOpen = false;
        let forcedMarkdownMode = false;

        const initialContent = context.initialContent || (context.isLocked ? '' : context.content || '');
        if (contentField && context.noteType !== 'canvas' && !context.isLocked) {
            contentField.value = initialContent;
        }
        if (context.noteType !== 'canvas' && !context.isLocked) {
            renderMarkdown(initialContent);
            initCheckboxHandler(initialContent);
        }

        function updateDrawerState() {
            if (!editorDrawer) return;
            const shouldOpen = forcedMarkdownMode || manualDrawerOpen;
            editorDrawer.classList.toggle('is-open', shouldOpen);
            editorDrawer.classList.toggle('is-expanded', forcedMarkdownMode);
            editorDrawer.setAttribute('aria-hidden', shouldOpen ? 'false' : 'true');
            drawerToggleButtons.forEach(btn => {
                btn.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
            });
        }

        function setViewMode(mode) {
            if (!noteContent || !viewToggleButtons.length) {
                return;
            }
            forcedMarkdownMode = mode === 'markdown';
            noteContent.classList.toggle('hidden', forcedMarkdownMode);
            viewToggleButtons.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === mode);
                btn.setAttribute('aria-pressed', btn.dataset.mode === mode ? 'true' : 'false');
            });
            updateDrawerState();
        }

        function toggleDrawer() {
            if (!editorDrawer) return;
            if (forcedMarkdownMode) {
                setViewMode('rendered');
                return;
            }
            manualDrawerOpen = !manualDrawerOpen;
            updateDrawerState();
        }

        if (drawerToggleButtons.length) {
            drawerToggleButtons.forEach(btn => btn.addEventListener('click', toggleDrawer));
        }

        if (viewToggleButtons.length && noteContent) {
            setViewMode('rendered');
            viewToggleButtons.forEach(btn => {
                btn.addEventListener('click', () => {
                    setViewMode(btn.dataset.mode);
                });
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
            renderMarkdown(markdown);
            initCheckboxHandler(markdown);
            manualDrawerOpen = true;
            setViewMode('rendered');
        };

        window.updateRenderedMarkdown = renderMarkdown;
    });
})();
