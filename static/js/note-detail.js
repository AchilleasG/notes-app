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
        const inlineContentGroup = document.querySelector('.inline-detail-content-group');
        const viewToggleButtons = document.querySelectorAll('.view-toggle-btn');

        const initialContent = context.initialContent || (context.isLocked ? '' : context.content || '');
        if (contentField && context.noteType !== 'canvas' && !context.isLocked) {
            contentField.value = initialContent;
        }
        if (context.noteType !== 'canvas' && !context.isLocked) {
            renderMarkdown(initialContent);
            initCheckboxHandler(initialContent);
        }

        function setViewMode(mode) {
            if (!inlineContentGroup || !noteContent || !viewToggleButtons.length) {
                return;
            }
            const showEditor = mode === 'markdown';
            inlineContentGroup.classList.toggle('is-visible', showEditor);
            noteContent.classList.toggle('hidden', showEditor);
            viewToggleButtons.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.mode === mode);
                btn.setAttribute('aria-pressed', btn.dataset.mode === mode ? 'true' : 'false');
            });
        }

        if (viewToggleButtons.length && inlineContentGroup && noteContent) {
            setViewMode('rendered');
            viewToggleButtons.forEach(btn => {
                btn.addEventListener('click', () => {
                    setViewMode(btn.dataset.mode);
                });
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
            }
            context.isLocked = false;
            context.encryptionPassword = password;
            context.salt = salt;
            renderMarkdown(markdown);
            initCheckboxHandler(markdown);
            if (viewToggleButtons.length && inlineContentGroup && noteContent) {
                setViewMode('rendered');
            }
        };

        window.updateRenderedMarkdown = renderMarkdown;
    });
})();
