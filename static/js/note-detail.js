(function() {
    function renderMarkdown(markdown) {
        const preview = document.getElementById('noteContent');
        if (!preview || !window.markdownRenderer) {
            return;
        }
        preview.innerHTML = window.markdownRenderer.render(markdown || '', true);
    }

    function updateRawView(markdown) {
        const rawView = document.getElementById('rawContentView');
        if (rawView) {
            rawView.textContent = markdown || '';
        }
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
        const toggleRawButton = document.getElementById('toggleRawButton');
        const rawView = document.getElementById('rawContentView');
        const editorPanel = document.getElementById('inlineEditorPanel');
        const editorToggle = document.getElementById('inlineEditorToggle');
        const editorClose = document.getElementById('inlineEditorClose');

        const initialContent = context.initialContent || (context.isLocked ? '' : context.content || '');
        if (contentField && context.noteType !== 'canvas' && !context.isLocked) {
            contentField.value = initialContent;
        }
        if (context.noteType !== 'canvas' && !context.isLocked) {
            renderMarkdown(initialContent);
            updateRawView(initialContent);
            initCheckboxHandler(initialContent);
        }

        if (toggleRawButton && rawView) {
            toggleRawButton.addEventListener('click', () => {
                const showing = rawView.style.display === 'block';
                rawView.style.display = showing ? 'none' : 'block';
                document.getElementById('noteContent').style.display = showing ? 'block' : 'none';
                toggleRawButton.textContent = showing ? 'Show Raw Markdown' : 'Show Rendered Markdown';
            });
        }

        if (contentField) {
            contentField.addEventListener('input', () => {
                if (context.noteType === 'canvas') return;
                const value = contentField.value;
                updateRawView(value);
                renderMarkdown(value);
                if (window.checkboxHandlerInstance) {
                    initCheckboxHandler(value);
                }
            });
        }

        if (editorPanel && editorToggle) {
            editorToggle.addEventListener('click', () => {
                editorPanel.classList.toggle('collapsed');
            });
        }
        if (editorPanel && editorClose) {
            editorClose.addEventListener('click', () => {
                editorPanel.classList.add('collapsed');
            });
        }

        window.applyDecryptedContent = function(markdown, password, salt) {
            if (contentField) {
                contentField.value = markdown;
            }
            context.isLocked = false;
            context.encryptionPassword = password;
            context.salt = salt;
            updateRawView(markdown);
            renderMarkdown(markdown);
            initCheckboxHandler(markdown);
        };

        window.updateRenderedMarkdown = renderMarkdown;
    });
})();
