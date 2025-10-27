/**
 * Canvas Note Editor
 * A reusable component for creating and editing canvas notes with draggable elements
 */

class CanvasEditor {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container with id "${containerId}" not found`);
            return;
        }

        this.options = {
            noteId: options.noteId || null,
            sharedNoteId: options.sharedNoteId || null,
            csrfToken: options.csrfToken || '',
            readonly: options.readonly || false,
            showGrid: options.showGrid !== undefined ? options.showGrid : true,
            gridSize: options.gridSize || 20,
            // Freehand drawing margin (px) to avoid clipping; can be overridden via options
            freehandMargin: options.freehandMargin || 12,
            onSave: options.onSave || (() => { }),
            onError: options.onError || ((error) => console.error(error)),
            // Optional: name of a global variable that holds the current theme (e.g. 'APP_THEME')
            themeVariableName: options.themeVariableName || '',
            // Optional: a function that returns the current theme value; overrides themeVariableName
            themeGetter: options.themeGetter || null,
            // If true, log theme-detection events to console (debug only)
            debugTheme: options.debugTheme || false,
        };

        // If CSRF token wasn't provided via options, try to read it from the DOM
        if (!this.options.csrfToken) {
            try {
                const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
                if (csrfInput) this.options.csrfToken = csrfInput.value;
            } catch (err) {
                // ignore
            }
        }

        this.elements = [];
        this.selectedElement = null;
        // History stacks for undo/redo
        this.undoStack = [];
        this.redoStack = [];
        this._suppressHistory = false;
        // Canvas zoom/scale (1 = 100%)
        this.scale = 1;
        // Guard to avoid re-registering document-level listeners
        this._staticListenersAttached = false;

        // Drawing mode state
        this.drawingMode = null;  // null, 'rectangle', 'circle', 'line', 'freehand'
        this.isDrawing = false;
        this.drawingStartX = 0;
        this.drawingStartY = 0;
        this.currentPath = [];  // For freehand drawing
        this.previewElement = null;  // For showing shape preview while drawing
        this.selectMode = false; // when true, pointer/select tool is active
        this.selectedElements = []; // array of element ids currently selected
        this.selectionRect = null; // marquee selection preview element
        this.selectionState = { isSelecting: false, startX: 0, startY: 0 };
        // Theme provider: function that returns the current theme value (string/bool)
        this.themeProvider = null;
        this._initThemeProvider(options);
        // Stroke settings
        this.currentStrokeWidth = options.strokeWidth || 2;
        this.currentStrokeColor = options.strokeColor || 'default'; // abstract color name

        this.dragState = {
            isDragging: false,
            element: null,
            startX: 0,
            startY: 0,
            elementStartX: 0,
            elementStartY: 0,
            deltaX: 0,
            deltaY: 0,
        };

        this.resizeState = {
            isResizing: false,
            element: null,
            handle: null,
            startX: 0,
            startY: 0,
            startWidth: 0,
            startHeight: 0,
        };

        this.init();
    }

    _pushHistory(action) {
        if (this._suppressHistory) return;
        try {
            this.undoStack.push(action);
            // cap history length
            if (this.undoStack.length > 200) this.undoStack.shift();
            // clear redo on new action
            this.redoStack = [];
            // Reflect changes in toolbar UI if available
            try { if (this.toolbar && typeof this._updatePickersUI === 'function') this._updatePickersUI(); } catch (e) { }
        } catch (err) { /* ignore */ }
    }

    async performUndo() {
        if (!this.undoStack.length) return;
        const action = this.undoStack.pop();
        this._suppressHistory = true;
        try {
            if (action.type === 'create') {
                // undo a creation by deleting the element
                await this._deleteElementById(action.element.id, { suppressHistory: true });
                this.redoStack.push(action);
            } else if (action.type === 'delete') {
                // Try to undo a deletion by calling undelete endpoint for each original id.
                // If undelete fails (element was permanently removed), fall back to recreating a new element.
                const recreated = [];
                let undeleteAllSucceeded = true;
                for (const snap of action.elements) {
                    try {
                        // Attempt to undelete (preserve original id)
                        const resp = await fetch(`/canvas/elements/${snap.id}/undelete/`, {
                            method: 'POST',
                            headers: { 'X-CSRFToken': this.options.csrfToken },
                        });
                        const json = await resp.json().catch(() => ({}));
                        if (json && json.success && json.element) {
                            // Add restored element to local list
                            this.elements.push(json.element);
                        } else {
                            // Undelete failed; mark and fallback to create
                            undeleteAllSucceeded = false;
                            const data = Object.assign({}, snap);
                            delete data.id;
                            const res = await this._createElementOnServer(data);
                            if (res && res.element) recreated.push(res.element);
                        }
                    } catch (err) {
                        undeleteAllSucceeded = false;
                        const data = Object.assign({}, snap);
                        delete data.id;
                        try {
                            const res = await this._createElementOnServer(data);
                            if (res && res.element) recreated.push(res.element);
                        } catch (e) {
                            // ignore
                        }
                    }
                }

                if (undeleteAllSucceeded) {
                    // Everything restored by undelete; redo can simply re-delete the original ids
                    this.redoStack.push({ type: 'delete', elements: action.elements });
                } else {
                    // Some elements had to be recreated (new ids); store recreated mapping so redo deletes the recreated ones
                    this.redoStack.push({ type: 'delete', elements: action.elements, recreated });
                }
            } else if (action.type === 'update') {
                // revert update by sending prev values
                await this.updateElement(action.id, action.prev, { suppressHistory: true });
                this.redoStack.push(action);
            }
        } catch (err) {
            console.error('Undo failed', err);
        } finally {
            this._suppressHistory = false;
            this.renderElements();
            try { if (this.toolbar && typeof this._updatePickersUI === 'function') this._updatePickersUI(); } catch (e) { }
            this.options.onSave();
        }
    }

    async performRedo() {
        if (!this.redoStack.length) return;
        const action = this.redoStack.pop();
        this._suppressHistory = true;
        try {
            if (action.type === 'create') {
                // redo a creation: try to undelete the original element (preserve ID).
                // If undelete isn't available (or fails), fall back to creating a new element
                const orig = action.element;
                let restored = false;
                try {
                    const resp = await fetch(`/canvas/elements/${orig.id}/undelete/`, {
                        method: 'POST',
                        headers: { 'X-CSRFToken': this.options.csrfToken },
                    });
                    const json = await resp.json().catch(() => ({}));
                    if (json && json.success && json.element) {
                        // ensure it's in local state
                        const exists = this.elements.find(e => String(e.id) === String(json.element.id));
                        if (!exists) this.elements.push(json.element);
                        restored = true;
                        // push original create action back to undo stack
                        this.undoStack.push(action);
                    }
                } catch (err) {
                    // ignore and fallback
                }

                if (!restored) {
                    // fallback: recreate element via create API and record new action
                    const data = Object.assign({}, orig);
                    delete data.id;
                    const res = await this._createElementOnServer(data);
                    if (res && res.element) {
                        this.elements.push(res.element);
                        // push a new create action representing this recreated element so undo will delete it
                        this.undoStack.push({ type: 'create', element: res.element });
                    } else {
                        console.error('Redo recreate failed', res && res.error);
                    }
                }
            } else if (action.type === 'delete') {
                // redo a deletion by deleting recreated elements if available, otherwise delete by id
                if (action.recreated && action.recreated.length) {
                    for (const el of action.recreated) {
                        await this._deleteElementById(el.id, { suppressHistory: true });
                    }
                } else {
                    for (const snap of action.elements) {
                        if (snap.id) await this._deleteElementById(snap.id, { suppressHistory: true });
                    }
                }
                this.undoStack.push(action);
            } else if (action.type === 'update') {
                await this.updateElement(action.id, action.next, { suppressHistory: true });
                this.undoStack.push(action);
            }
        } catch (err) {
            console.error('Redo failed', err);
        } finally {
            this._suppressHistory = false;
            this.renderElements();
            try { if (this.toolbar && typeof this._updatePickersUI === 'function') this._updatePickersUI(); } catch (e) { }
            this.options.onSave();
        }
    }

    // Wrapper to create element on server and return parsed result
    async _createElementOnServer(data) {
        try {
            const response = await fetch('/canvas/elements/create/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.options.csrfToken,
                },
                body: JSON.stringify(data),
            });
            return await response.json();
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    async _deleteElementById(id, opts = {}) {
        try {
            const res = await fetch(`/canvas/elements/${id}/delete/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': this.options.csrfToken },
            });
            const json = await res.json().catch(() => ({}));
            // Remove from local state regardless
            this.elements = this.elements.filter(el => String(el.id) !== String(id));
            this.renderElements();
            if (!opts.suppressHistory) {
                // we would have pushed history at caller
            }
            return json;
        } catch (err) {
            return { success: false, error: err.message };
        }
    }

    init() {
        this.createCanvas();
        this.loadElements();
        this.attachEventListeners();
        // Watch for theme changes so abstract colors re-render correctly
        this.setupThemeListeners();
    }

    _initThemeProvider(options) {
        // Priority: explicit themeGetter function > themeVariableName global var > DOM heuristics
        if (options && typeof options.themeGetter === 'function') {
            this.themeProvider = options.themeGetter;
            return;
        }

        if (options && typeof options.themeVariableName === 'string' && options.themeVariableName) {
            const varName = options.themeVariableName;
            this.themeProvider = () => {
                try {
                    return window[varName];
                } catch (err) {
                    return null;
                }
            };
            return;
        }

        // Default provider: check html/body data-theme or class, then matchMedia
        this.themeProvider = () => {
            try {
                const html = document.documentElement;
                const body = document.body;
                if (html && html.dataset && html.dataset.theme) return html.dataset.theme;
                if (body && body.dataset && body.dataset.theme) return body.dataset.theme;
                if (html && html.classList && [...html.classList].some(c => /dark/i.test(c))) return 'dark';
                if (body && body.classList && [...body.classList].some(c => /dark/i.test(c))) return 'dark';
                if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
                return 'light';
            } catch (err) {
                return null;
            }
        };
    }

    setupThemeListeners() {
        try {
            // Listen to OS theme changes
            if (window.matchMedia) {
                const mq = window.matchMedia('(prefers-color-scheme: dark)');
                // For older browsers that don't support addEventListener on MediaQueryList
                if (typeof mq.addEventListener === 'function') {
                    mq.addEventListener('change', () => this.renderElements());
                } else if (typeof mq.addListener === 'function') {
                    mq.addListener(() => this.renderElements());
                }
            }

            // Also observe body class changes (some apps toggle a .dark-mode class)
            if (window.MutationObserver) {
                // Disconnect previous observer if present
                if (this._themeObserver) this._themeObserver.disconnect();

                // Observe both <body> and <html> (documentElement) for class or data-theme changes.
                this._themeObserver = new MutationObserver((mutations) => {
                    for (const m of mutations) {
                        const attr = m.attributeName || '';
                        // React to class or theme-like attribute changes
                        if (attr === 'class' || attr.toLowerCase().includes('theme') || attr === 'data-theme') {
                            this.renderElements();
                            break;
                        }
                    }
                });

                try {
                    if (document.body) this._themeObserver.observe(document.body, { attributes: true, attributeFilter: ['class', 'data-theme'] });
                } catch (err) { /* ignore */ }

                try {
                    if (document.documentElement) this._themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
                } catch (err) { /* ignore */ }
            }
        } catch (err) {
            // If anything fails, silently ignore — rendering will still work on reload
            console.error('Failed to setup theme listeners', err);
        }
    }

    createCanvas() {
        this.container.innerHTML = `
            <div class="canvas-editor">
                <div class="canvas-toolbar">
                   ${(this.drawingMode || this.selectMode || (this.selectedElements && this.selectedElements.length)) ? `
                    <button type="button" class="btn-canvas btn-canvas-danger" data-action="clear-tools" title="Clear tools">
                        <span>✕</span>
                    </button>
                    ` : ''}
               
                    <button type="button" class="btn-canvas ${this.drawingMode === 'textbox' ? 'btn-canvas-active' : 'btn-canvas-secondary'}" data-action="add-textbox">
                        <span>📝</span> Text
                    </button>
                    <button type="button" class="btn-canvas ${this.drawingMode === 'image' ? 'btn-canvas-active' : 'btn-canvas-secondary'}" data-action="add-image">
                        <span>🖼️</span> Image
                    </button>
                    <!-- Shapes dropdown to reduce toolbar clutter -->
                    <div id="canvas-shapes-picker" style="display:inline-block;vertical-align:middle;margin-right:6px;"></div>
                    <button type="button" class="btn-canvas ${this.drawingMode === 'eraser' ? 'btn-canvas-active' : 'btn-canvas-secondary'}" data-action="eraser">
                        <span>🧽</span> Eraser
                    </button>
                    <button type="button" class="btn-canvas btn-canvas-secondary" data-action="undo">
                        <span>↶</span>
                    </button>
                    <button type="button" class="btn-canvas btn-canvas-secondary" data-action="redo">
                        <span>↷</span>
                    </button>
                    <button type="button" class="btn-canvas btn-canvas-secondary" data-action="zoom-in" title="Zoom In">
                        <span>🔍+</span>
                    </button>
                    <button type="button" class="btn-canvas btn-canvas-secondary" data-action="zoom-out" title="Zoom Out">
                        <span>🔍−</span>
                    </button>
                        <div class="canvas-controls" style="display:inline-flex;align-items:center;gap:8px;margin-left:8px;">
                            <label style="font-size:12px;">Stroke</label>
                                <div id="canvas-stroke-width-picker" style="display:flex;gap:6px;align-items:center;" aria-label="Stroke width picker"></div>
                                <label style="font-size:12px;">Color</label>
                                <div id="canvas-stroke-color-picker" style="display:flex;gap:6px;align-items:center;" aria-label="Stroke color picker"></div>
                        </div>
                    <button type="button" class="btn-canvas btn-canvas-secondary" data-action="toggle-grid">
                        <span>⊞</span> <span class="grid-toggle-text">${this.options.showGrid ? 'Hide' : 'Show'} Grid</span>
                    </button>
                    ${this.selectedElement ? `
                        <button type="button" class="btn-canvas btn-canvas-danger" data-action="delete-element">
                            <span>🗑️</span> Delete
                        </button>
                    ` : ''}
                </div>
             <div class="canvas-area ${this.options.showGrid ? 'show-grid' : ''} ${this.drawingMode ? 'drawing-mode' : ''}" 
                 style="--grid-size: ${this.options.gridSize}px;">
                    <div class="canvas-content" style="position:relative; transform-origin: 0 0;">
                        <!-- Elements will be rendered here -->
                    </div>
                </div>
                <input type="file" id="imageUploadInput" accept="image/*" style="display: none;">
            </div>
        `;

        this.toolbar = this.container.querySelector('.canvas-toolbar');
        this.canvasArea = this.container.querySelector('.canvas-area');
        this.canvasContent = this.container.querySelector('.canvas-content');
        // Ensure the grid is attached to the scaled content so it visually
        // scales with zoom. Store the logical grid size as a CSS variable on
        // the content element; the element is transformed (scaled) so the
        // background will appear larger/smaller automatically.
        try {
            const target = this.canvasContent || this.canvasArea;
            // remove any legacy class on canvasArea
            if (this.canvasArea && this.canvasArea.classList) this.canvasArea.classList.remove('show-grid');
            if (this.canvasContent && this.canvasContent.classList) {
                this.canvasContent.classList.toggle('show-grid', Boolean(this.options.showGrid));
                this.canvasContent.style.setProperty('--grid-size', `${this.options.gridSize}px`);
            } else if (this.canvasArea && this.canvasArea.classList) {
                // fallback for older markup
                this.canvasArea.classList.toggle('show-grid', Boolean(this.options.showGrid));
                this.canvasArea.style.setProperty('--grid-size', `${this.options.gridSize}px`);
            }
        } catch (err) {
            // Ignore failures here
        }
        this.imageInput = this.container.querySelector('#imageUploadInput');
        // Re-attach dynamic listeners for the newly created DOM nodes
        // (createCanvas can be called multiple times to refresh toolbar state)
        try {
            this.attachDynamicEventListeners();
        } catch (err) {
            // Defensive: log but don't crash the editor if listeners cannot be attached
            console.error('Failed to attach dynamic event listeners after createCanvas:', err);
        }
        // Apply current scale (in case editor was zoomed previously)
        try { this._applyScale(); } catch (e) { }
    }

    attachEventListeners() {
        if (this.options.readonly) return;
        // Attach document-level listeners only once per instance
        if (!this._staticListenersAttached) {
            this.attachStaticEventListeners();
            this._staticListenersAttached = true;
        }
    }

    attachDynamicEventListeners() {
        if (this.options.readonly) return;
        if (!this.toolbar || !this.canvasArea || !this.imageInput) return;

        // Toolbar buttons
        this.toolbar.addEventListener('click', (e) => {
            const button = e.target.closest('[data-action]');
            if (!button) return;
            const action = button.dataset.action;
            this.handleToolbarAction(action);
            // Remove focus from the clicked button so it doesn't keep the browser 'focused' styling
            try {
                // blur in next tick so any internal focus caused by the action finishes
                setTimeout(() => {
                    if (button && typeof button.blur === 'function') button.blur();
                }, 0);
            } catch (err) {
                // ignore
            }
        });

        // Build custom color and stroke width pickers (visual)
        this._buildColorPicker();
        this._buildStrokeWidthPicker();
        this._buildShapesPicker();
        // Update UI to reflect current settings
        this._updatePickersUI();

        // Canvas area events
        this.canvasArea.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvasArea.addEventListener('touchstart', (e) => this.handleTouchStart(e), { passive: false });

        // Image upload
        this.imageInput.addEventListener('change', (e) => this.handleImageUpload(e));

        // Prevent default drag behavior
        this.canvasArea.addEventListener('dragstart', (e) => e.preventDefault());
    }

    attachStaticEventListeners() {
        // Document-level listeners for move/end events
        document.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        document.addEventListener('touchmove', (e) => this.handleTouchMove(e), { passive: false });
        document.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        document.addEventListener('touchend', (e) => this.handleTouchEnd(e));
        // Keyboard shortcuts (Delete/Backspace for deleting selection)
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
    }

    handleKeyDown(e) {
        if (this.options.readonly) return;
        // Don't intercept typing in inputs/textareas or contentEditable
        const active = document.activeElement;
        if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)) return;

        if (e.key === 'Delete' || e.key === 'Backspace') {
            if (this.selectedElements && this.selectedElements.length) {
                e.preventDefault();
                this.deleteSelectedElement();
            }
        }
    }

    handleToolbarAction(action) {
        switch (action) {
            case 'select':
                // Toggle select mode: clicking again should exit to default
                if (this.selectMode) {
                    this.exitSelectMode();
                } else {
                    this.enterSelectMode();
                }
                break;
            case 'add-textbox':
                // Toggle textbox drawing mode instead of spawning immediately
                if (this.drawingMode === 'textbox') {
                    this.exitDrawingMode();
                } else {
                    this.enterDrawingMode('textbox');
                }
                break;
            case 'add-image':
                this.exitDrawingMode();
                this.imageInput.click();
                break;
            case 'draw-rectangle':
                // Toggle rectangle tool
                if (this.drawingMode === 'rectangle') {
                    this.exitDrawingMode();
                } else {
                    this.enterDrawingMode('rectangle');
                }
                break;
            case 'draw-circle':
                if (this.drawingMode === 'circle') {
                    this.exitDrawingMode();
                } else {
                    this.enterDrawingMode('circle');
                }
                break;
            case 'draw-line':
                if (this.drawingMode === 'line') {
                    this.exitDrawingMode();
                } else {
                    this.enterDrawingMode('line');
                }
                break;
            case 'draw-freehand':
                if (this.drawingMode === 'freehand') {
                    this.exitDrawingMode();
                } else {
                    this.enterDrawingMode('freehand');
                }
                break;
            case 'eraser':
                if (this.drawingMode === 'eraser') {
                    this.exitDrawingMode();
                } else {
                    this.enterDrawingMode('eraser');
                }
                break;
            case 'toggle-grid':
                this.toggleGrid();
                break;
            case 'clear-tools':
                // Clear any active tool or selection
                try {
                    this.exitDrawingMode();
                } catch (err) { /* ignore */ }
                try {
                    this.exitSelectMode();
                } catch (err) { /* ignore */ }
                try {
                    this.deselectElement();
                } catch (err) { /* ignore */ }
                // Rebuild toolbar/render to reflect cleared state
                try { this.createCanvas(); this.renderElements(); } catch (err) { /* ignore */ }
                break;
            case 'zoom-in':
                this.zoomIn();
                break;
            case 'zoom-out':
                this.zoomOut();
                break;
            case 'undo':
                this.performUndo();
                break;
            case 'redo':
                this.performRedo();
                break;
            case 'delete-element':
                this.deleteSelectedElement();
                break;
        }
    }

    // Build a visual color picker (swatches) according to current theme
    _buildColorPicker() {
        const container = this.toolbar.querySelector('#canvas-stroke-color-picker');
        if (!container) return;
        container.style.position = 'relative';
        container.innerHTML = '';

        // Toggle button (shows currently selected swatch)
        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'canvas-color-toggle';
        toggle.style.display = 'inline-flex';
        toggle.style.alignItems = 'center';
        toggle.style.gap = '6px';
        toggle.style.padding = '4px';
        toggle.style.border = '1px solid transparent';
        toggle.style.background = 'transparent';
        toggle.style.cursor = 'pointer';
        toggle.setAttribute('aria-haspopup', 'true');
        toggle.setAttribute('aria-expanded', 'false');

        const currentSwatch = document.createElement('span');
        currentSwatch.className = 'canvas-current-swatch';
        currentSwatch.style.display = 'inline-block';
        currentSwatch.style.width = '20px';
        currentSwatch.style.height = '20px';
        currentSwatch.style.borderRadius = '4px';
        currentSwatch.style.border = '1px solid rgba(0,0,0,0.12)';
        toggle.appendChild(currentSwatch);

        const caret = document.createElement('span');
        caret.innerHTML = '▾';
        caret.style.fontSize = '12px';
        caret.style.lineHeight = '12px';
        toggle.appendChild(caret);

        container.appendChild(toggle);

        // Panel
        const panel = document.createElement('div');
        panel.className = 'canvas-color-panel';
        Object.assign(panel.style, {
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: '0',
            display: 'none',
            padding: '8px',
            gap: '6px',
            background: this.isDarkMode() ? '#111' : '#fff',
            border: '1px solid rgba(0,0,0,0.12)',
            borderRadius: '6px',
            boxShadow: this.isDarkMode() ? '0 6px 18px rgba(0,0,0,0.6)' : '0 6px 18px rgba(0,0,0,0.08)',
            // panel will be toggled open/closed; use flex layout when shown
            flexWrap: 'wrap',
            width: 'max-content',
            zIndex: 9999,
        });

        const colors = ['default', 'red', 'green', 'blue', 'yellow', 'purple'];
        colors.forEach(name => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'canvas-color-swatch';
            btn.dataset.color = name;
            btn.title = name;
            btn.style.width = '28px';
            btn.style.height = '20px';
            btn.style.borderRadius = '4px';
            btn.style.border = '2px solid transparent';
            btn.style.padding = '0';
            btn.style.cursor = 'pointer';
            btn.style.boxSizing = 'border-box';
            btn.addEventListener('click', (ev) => {
                this.currentStrokeColor = name;
                this._updatePickersUI();
                panel.style.display = 'none';
                toggle.setAttribute('aria-expanded', 'false');
            });
            panel.appendChild(btn);
        });

        container.appendChild(panel);

        // Toggle open/close
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = panel.style.display === 'flex' || panel.style.display === 'block';
            panel.style.display = open ? 'none' : 'flex';
            toggle.setAttribute('aria-expanded', String(!open));
            // Update panel background to match theme
            panel.style.background = this.isDarkMode() ? '#111' : '#fff';
        });

        // Close on outside click (include shapes picker)
        if (!this._pickerGlobalClickListener) {
            this._pickerGlobalClickListener = (ev) => {
                const panels = this.toolbar.querySelectorAll('.canvas-color-panel, .canvas-stroke-panel, .canvas-shapes-panel');
                panels.forEach(p => { if (p && p.style) p.style.display = 'none'; });
                const toggles = this.toolbar.querySelectorAll('.canvas-color-toggle, .canvas-stroke-toggle, .canvas-shapes-toggle');
                toggles.forEach(t => t.setAttribute('aria-expanded', 'false'));
            };
            document.addEventListener('click', this._pickerGlobalClickListener);
        }
    }

    // Build shapes dropdown (rectangle, circle, line, freehand)
    _buildShapesPicker() {
        const container = this.toolbar.querySelector('#canvas-shapes-picker');
        if (!container) return;
        container.style.position = 'relative';
        container.innerHTML = '';

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'canvas-shapes-toggle btn-canvas-secondary';
        toggle.style.display = 'inline-flex';
        toggle.style.alignItems = 'center';
        toggle.style.gap = '6px';
        toggle.style.padding = '4px';
        toggle.style.cursor = 'pointer';
        toggle.innerHTML = '<span>▭</span> Shapes ▾';
        container.appendChild(toggle);

        const panel = document.createElement('div');
        panel.className = 'canvas-shapes-panel';
        Object.assign(panel.style, {
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: '0',
            display: 'none',
            padding: '6px',
            background: this.isDarkMode() ? '#111' : '#fff',
            border: '1px solid rgba(0,0,0,0.12)',
            borderRadius: '6px',
            boxShadow: this.isDarkMode() ? '0 6px 18px rgba(0,0,0,0.6)' : '0 6px 18px rgba(0,0,0,0.08)',
            zIndex: 9999,
            gap: '6px',
        });

        const shapes = [
            { name: 'rectangle', label: '▭ Rectangle' },
            { name: 'circle', label: '○ Circle' },
            { name: 'line', label: '╱ Line' },
            { name: 'freehand', label: '✏️ Draw' },
        ];

        shapes.forEach(s => {
            const b = document.createElement('button');
            b.type = 'button';
            b.className = 'btn-canvas btn-canvas-secondary';
            b.dataset.shape = s.name;
            b.style.padding = '6px 8px';
            b.textContent = s.label;
            // If this shape is currently active, mark it visually
            if (this.drawingMode === s.name) {
                b.classList.add('btn-canvas-active');
            }
            b.addEventListener('click', (e) => {
                e.stopPropagation();
                // clicking the same active shape toggles it off
                if (this.drawingMode === s.name) {
                    this.exitDrawingMode();
                } else {
                    this.enterDrawingMode(s.name);
                }
                panel.style.display = 'none';
            });
            panel.appendChild(b);
        });

        container.appendChild(panel);

        // Initialize toggle label to reflect current selected drawing mode (if it's a shape)
        const selectedShape = shapes.find(s => s.name === this.drawingMode);
        if (selectedShape) {
            toggle.innerHTML = `<span>${selectedShape.label.split(' ')[0]}</span> ${selectedShape.label.split(' ').slice(1).join(' ')} ▾`;
            toggle.setAttribute('aria-expanded', 'false');
            toggle.classList.add('btn-canvas-active');
        } else {
            toggle.innerHTML = '<span>▭</span> Shapes ▾';
            toggle.setAttribute('aria-expanded', 'false');
            toggle.classList.remove('btn-canvas-active');
        }

        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            // Always open/close the shapes panel when the toolbar toggle is clicked.
            // Do NOT unselect the current drawing mode here — unselect only happens
            // when clicking the specific dropdown item (so user can open the panel
            // without accidentally leaving draw mode).
            const open = panel.style.display === 'flex' || panel.style.display === 'block';
            panel.style.display = open ? 'none' : 'flex';
            toggle.setAttribute('aria-expanded', String(!open));
            panel.style.background = this.isDarkMode() ? '#111' : '#fff';
        });
    }

    // Build stroke width visual picker
    _buildStrokeWidthPicker() {
        const container = this.toolbar.querySelector('#canvas-stroke-width-picker');
        if (!container) return;
        container.style.position = 'relative';
        container.innerHTML = '';

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'canvas-stroke-toggle';
        toggle.style.display = 'inline-flex';
        toggle.style.alignItems = 'center';
        toggle.style.gap = '6px';
        toggle.style.padding = '4px';
        toggle.style.border = '1px solid transparent';
        toggle.style.background = 'transparent';
        toggle.style.cursor = 'pointer';
        toggle.setAttribute('aria-haspopup', 'true');
        toggle.setAttribute('aria-expanded', 'false');

        const currentSample = document.createElement('span');
        currentSample.className = 'canvas-current-strokesample';
        currentSample.style.display = 'inline-block';
        currentSample.style.width = '36px';
        currentSample.style.height = '24px';
        currentSample.style.padding = '2px';
        toggle.appendChild(currentSample);

        const caret = document.createElement('span');
        caret.innerHTML = '▾';
        caret.style.fontSize = '12px';
        caret.style.lineHeight = '12px';
        toggle.appendChild(caret);

        container.appendChild(toggle);

        const panel = document.createElement('div');
        panel.className = 'canvas-stroke-panel';
        Object.assign(panel.style, {
            position: 'absolute',
            top: 'calc(100% + 6px)',
            left: '0',
            display: 'none',
            padding: '8px',
            gap: '6px',
            background: this.isDarkMode() ? '#111' : '#fff',
            border: '1px solid rgba(0,0,0,0.12)',
            borderRadius: '6px',
            boxShadow: this.isDarkMode() ? '0 6px 18px rgba(0,0,0,0.6)' : '0 6px 18px rgba(0,0,0,0.08)',
            // panel will be toggled open/closed; use flex layout when shown
            flexWrap: 'wrap',
            width: 'max-content',
            zIndex: 9999,
        });

        const widths = [1, 2, 4, 6, 8];
        widths.forEach(w => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'canvas-stroke-sample';
            btn.dataset.width = String(w);
            btn.title = `${w}px`;
            btn.style.display = 'flex';
            btn.style.alignItems = 'center';
            btn.style.justifyContent = 'center';
            btn.style.width = '56px';
            btn.style.height = '30px';
            btn.style.padding = '6px';
            btn.style.border = '2px solid transparent';
            btn.style.cursor = 'pointer';
            btn.style.boxSizing = 'border-box';

            const svgNS = 'http://www.w3.org/2000/svg';
            const svg = document.createElementNS(svgNS, 'svg');
            svg.setAttribute('width', '48');
            svg.setAttribute('height', '16');
            svg.setAttribute('viewBox', '0 0 48 16');
            svg.style.display = 'block';
            svg.style.pointerEvents = 'none';

            const line = document.createElementNS(svgNS, 'line');
            line.setAttribute('x1', '4');
            line.setAttribute('y1', '8');
            line.setAttribute('x2', '44');
            line.setAttribute('y2', '8');
            line.setAttribute('stroke-linecap', 'round');
            line.setAttribute('stroke-width', String(w));
            line.setAttribute('stroke', this.getRenderColor(this.currentStrokeColor) || (this.isDarkMode() ? '#ffffff' : '#000000'));
            svg.appendChild(line);
            btn.appendChild(svg);

            btn.addEventListener('click', () => {
                this.currentStrokeWidth = w;
                this._updatePickersUI();
                panel.style.display = 'none';
                toggle.setAttribute('aria-expanded', 'false');
            });

            panel.appendChild(btn);
        });

        container.appendChild(panel);

        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = panel.style.display === 'flex' || panel.style.display === 'block';
            panel.style.display = open ? 'none' : 'flex';
            toggle.setAttribute('aria-expanded', String(!open));
            panel.style.background = this.isDarkMode() ? '#111' : '#fff';
        });
    }

    // Update pickers visuals (swatch colors and selection outlines)
    _updatePickersUI() {
        try {
            const colorBtns = Array.from(this.toolbar.querySelectorAll('.canvas-color-swatch'));
            colorBtns.forEach(btn => {
                const name = btn.dataset.color;
                const colorHex = this.getRenderColor(name) || (this.isDarkMode() ? '#ffffff' : '#000000');
                btn.style.background = colorHex;
                // If the color is too close to the background, add an outline
                btn.style.borderColor = (name === this.currentStrokeColor) ? (this.isDarkMode() ? '#ffffff' : '#000000') : 'transparent';
                // Add a subtle box-shadow in dark mode to make swatches pop
                btn.style.boxShadow = this.isDarkMode() ? '0 0 6px rgba(255,255,255,0.06)' : 'none';
            });

            const strokeBtns = Array.from(this.toolbar.querySelectorAll('.canvas-stroke-sample'));
            strokeBtns.forEach(btn => {
                const w = parseInt(btn.dataset.width, 10) || 2;
                const svg = btn.querySelector('svg');
                if (svg) {
                    const line = svg.querySelector('line');
                    if (line) {
                        line.setAttribute('stroke', this.getRenderColor(this.currentStrokeColor) || (this.isDarkMode() ? '#ffffff' : '#000000'));
                        line.setAttribute('stroke-width', String(w));
                    }
                }
                // Ensure sample background contrasts with stroke so white strokes are visible in dark mode
                btn.style.background = this.isDarkMode() ? '#111' : '#fff';
                btn.style.borderColor = (this.currentStrokeWidth === w) ? (this.isDarkMode() ? '#ffffff' : '#000000') : 'transparent';
                btn.style.boxShadow = this.isDarkMode() ? '0 4px 10px rgba(0,0,0,0.6)' : 'none';
            });
            // Update current swatch toggle
            try {
                const currentSwatch = this.toolbar.querySelector('.canvas-current-swatch');
                if (currentSwatch) {
                    const hex = this.getRenderColor(this.currentStrokeColor) || (this.isDarkMode() ? '#ffffff' : '#000000');
                    currentSwatch.style.background = hex;
                    currentSwatch.style.borderColor = this.isDarkMode() ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)';
                }
            } catch (err) { }
            // Update undo/redo button states
            try {
                const undoBtn = this.toolbar.querySelector('[data-action="undo"]');
                const redoBtn = this.toolbar.querySelector('[data-action="redo"]');
                if (undoBtn) {
                    if (this.undoStack && this.undoStack.length) {
                        undoBtn.removeAttribute('disabled');
                        undoBtn.classList.remove('btn-canvas-disabled');
                    } else {
                        undoBtn.setAttribute('disabled', 'disabled');
                        undoBtn.classList.add('btn-canvas-disabled');
                    }
                }
                if (redoBtn) {
                    if (this.redoStack && this.redoStack.length) {
                        redoBtn.removeAttribute('disabled');
                        redoBtn.classList.remove('btn-canvas-disabled');
                    } else {
                        redoBtn.setAttribute('disabled', 'disabled');
                        redoBtn.classList.add('btn-canvas-disabled');
                    }
                }
            } catch (err) { }
            // Update current stroke sample toggle
            try {
                const currentSample = this.toolbar.querySelector('.canvas-current-strokesample');
                if (currentSample) {
                    // render an inline svg showing the current stroke width and color
                    currentSample.innerHTML = '';
                    const svgNS = 'http://www.w3.org/2000/svg';
                    const svg = document.createElementNS(svgNS, 'svg');
                    svg.setAttribute('width', '48');
                    svg.setAttribute('height', '16');
                    svg.setAttribute('viewBox', '0 0 48 16');
                    svg.style.display = 'block';
                    const line = document.createElementNS(svgNS, 'line');
                    line.setAttribute('x1', '4');
                    line.setAttribute('y1', '8');
                    line.setAttribute('x2', '44');
                    line.setAttribute('y2', '8');
                    line.setAttribute('stroke-linecap', 'round');
                    line.setAttribute('stroke-width', String(this.currentStrokeWidth || 2));
                    line.setAttribute('stroke', this.getRenderColor(this.currentStrokeColor) || (this.isDarkMode() ? '#ffffff' : '#000000'));
                    svg.appendChild(line);
                    currentSample.appendChild(svg);
                    // Keep current sample background transparent so it doesn't obscure the stroke preview
                    currentSample.style.background = 'transparent';
                }
            } catch (err) { }
            // Update shapes toggle and dropdown highlighting to reflect current drawing mode
            try {
                const shapeToggle = this.toolbar.querySelector('.canvas-shapes-toggle');
                const shapePanel = this.toolbar.querySelector('.canvas-shapes-panel');
                const shapeList = ['rectangle', 'circle', 'line', 'freehand'];
                if (shapeToggle) {
                    if (shapeList.includes(this.drawingMode)) {
                        shapeToggle.classList.add('btn-canvas-active');
                    } else {
                        shapeToggle.classList.remove('btn-canvas-active');
                    }
                }
                if (shapePanel) {
                    const btns = Array.from(shapePanel.querySelectorAll('button'));
                    btns.forEach(b => {
                        if (b.dataset && b.dataset.shape === this.drawingMode) {
                            b.classList.add('btn-canvas-active');
                        } else {
                            b.classList.remove('btn-canvas-active');
                        }
                    });
                }
                // keep the toggle label in sync
                if (shapeToggle) {
                    const meta = {
                        rectangle: '▭ Rectangle',
                        circle: '○ Circle',
                        line: '╱ Line',
                        freehand: '✏️ Draw',
                    };
                    if (shapeList.includes(this.drawingMode)) {
                        const txt = meta[this.drawingMode] || 'Shape';
                        shapeToggle.innerHTML = `<span>${txt.split(' ')[0]}</span> ${txt.split(' ').slice(1).join(' ')} ▾`;
                    } else {
                        shapeToggle.innerHTML = '<span>▭</span> Shapes ▾';
                    }
                }
            } catch (err) { /* ignore shapes UI update errors */ }
        } catch (err) {
            // ignore UI update errors
            if (this.options.debugTheme) console.error('updatePickersUI error', err);
        }
    }

    enterDrawingMode(mode) {
        this.drawingMode = mode;
        this.selectMode = false;
        this.deselectElement();
        this.canvasArea.classList.add('drawing-mode');
        this.canvasArea.style.cursor = 'crosshair';
        this.createCanvas(); // Refresh toolbar to show active state
        this.renderElements();
    }

    enterSelectMode() {
        this.selectMode = true;
        this.drawingMode = null;
        this.canvasArea.classList.remove('drawing-mode');
        this.canvasArea.style.cursor = '';
        this.createCanvas();
        this.renderElements();
    }

    exitSelectMode() {
        this.selectMode = false;
        this.createCanvas();
        this.renderElements();
    }

    exitDrawingMode() {
        this.drawingMode = null;
        this.isDrawing = false;
        this.currentPath = [];
        if (this.previewElement) {
            this.previewElement.remove();
            this.previewElement = null;
        }
        this.canvasArea.classList.remove('drawing-mode');
        this.canvasArea.style.cursor = '';
        // Rebuild toolbar so button classes reflect the inactive state
        try {
            this.createCanvas();
            this.renderElements();
        } catch (err) {
            // ignore
        }
    }

    toggleGrid() {
        this.options.showGrid = !this.options.showGrid;
        const gridTarget = this.canvasContent || this.canvasArea;
        if (gridTarget && gridTarget.classList) gridTarget.classList.toggle('show-grid', this.options.showGrid);
        const gridToggleText = this.toolbar.querySelector('.grid-toggle-text');
        if (gridToggleText) {
            gridToggleText.textContent = this.options.showGrid ? 'Hide Grid' : 'Show Grid';
        }
        // Persist the user's choice locally so it applies globally on this machine
        try {
            localStorage.setItem('canvas.showGrid', String(this.options.showGrid));
        } catch (err) {
            // ignore storage errors (private browsing, etc.)
        }
    }

    async addTextbox() {
        // Enter textbox drawing mode so the user can draw where the textbox should be
        this.enterDrawingMode('textbox');
        return;
    }

    async handleImageUpload(e) {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('image', file);
        formData.append('x', '50');
        formData.append('y', '50');
        formData.append('width', '200');
        formData.append('height', '200');
        formData.append('z_index', this.elements.length.toString());

        if (this.options.noteId) {
            formData.append('note_id', this.options.noteId);
        } else if (this.options.sharedNoteId) {
            formData.append('shared_note_id', this.options.sharedNoteId);
        }

        try {
            const response = await fetch('/canvas/elements/upload-image/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.options.csrfToken,
                },
                body: formData,
            });

            const result = await response.json();
            if (result.success) {
                this.elements.push(result.element);
                // record creation for undo
                this._pushHistory({ type: 'create', element: result.element });
                this.renderElements();
                this.options.onSave();
            } else {
                this.options.onError(result.error || 'Failed to upload image');
            }
        } catch (error) {
            this.options.onError(error.message);
        }

        // Reset input
        this.imageInput.value = '';
    }

    async loadElements() {
        // Elements are loaded from the server via the note view
        // For now, we'll assume they're passed in or loaded separately
    }

    setElements(elements) {
        this.elements = elements || [];
        this.renderElements();
    }

    renderElements() {
        if (!this.canvasContent) return;
        this.canvasContent.innerHTML = '';

        // Sort by z-index
        const sortedElements = [...this.elements].sort((a, b) => a.z_index - b.z_index);

        sortedElements.forEach(element => {
            const elementDiv = this.createElementDiv(element);
            this.canvasContent.appendChild(elementDiv);
        });

        // Update pickers (colors/width preview) to reflect current theme/color
        try {
            if (this.toolbar) this._updatePickersUI();
        } catch (err) { /* ignore */ }
        // Ensure visual scale is applied after rendering
        try { this._applyScale(); } catch (e) { }
    }

    createElementDiv(element) {
        const div = document.createElement('div');
        div.className = 'canvas-element';
        div.dataset.elementId = element.id;
        div.style.left = `${element.x}px`;
        div.style.top = `${element.y}px`;
        div.style.width = `${element.width}px`;
        div.style.height = `${element.height}px`;
        div.style.zIndex = element.z_index;

        if (element.element_type === 'textbox') {
            div.classList.add('canvas-textbox');
            const textarea = document.createElement('textarea');
            textarea.className = 'canvas-textarea';
            textarea.value = element.text_content || '';
            textarea.readOnly = this.options.readonly;

            if (!this.options.readonly) {
                textarea.addEventListener('input', () => {
                    this.debounceUpdateElement(element.id, { text_content: textarea.value });
                });
            }

            div.appendChild(textarea);
        } else if (element.element_type === 'image' && element.image_url) {
            div.classList.add('canvas-image');
            const img = document.createElement('img');
            img.src = element.image_url;
            img.alt = 'Canvas image';
            img.draggable = false;
            // Prevent default browser selection/dragging for images so it doesn't conflict
            // with our custom canvas selection/drag logic.
            img.style.userSelect = 'none';
            img.style.webkitUserSelect = 'none';
            img.style.MozUserSelect = 'none';
            img.style.webkitUserDrag = 'none';
            img.addEventListener('mousedown', (ev) => ev.preventDefault());
            img.addEventListener('dragstart', (ev) => ev.preventDefault());
            div.appendChild(img);
        } else if (element.element_type === 'rectangle') {
            div.classList.add('canvas-shape', 'canvas-rectangle');
            div.style.border = `${element.stroke_width || 2}px solid ${this.getRenderColor(element.stroke_color) || '#000000'}`;
            div.style.backgroundColor = this.getRenderColor(element.fill_color) || 'transparent';
        } else if (element.element_type === 'circle') {
            div.classList.add('canvas-shape', 'canvas-circle');
            div.style.border = `${element.stroke_width || 2}px solid ${this.getRenderColor(element.stroke_color) || '#000000'}`;
            div.style.backgroundColor = this.getRenderColor(element.fill_color) || 'transparent';
            div.style.borderRadius = '50%';
        } else if (element.element_type === 'line') {
            div.classList.add('canvas-shape', 'canvas-line');
            // For lines, draw using a rotated div
            const length = Math.sqrt(element.width ** 2 + element.height ** 2);
            const angle = Math.atan2(element.height, element.width) * (180 / Math.PI);
            div.style.width = `${length}px`;
            div.style.height = `${element.stroke_width || 2}px`;
            div.style.backgroundColor = this.getRenderColor(element.stroke_color) || '#000000';
            div.style.transform = `rotate(${angle}deg)`;
            div.style.transformOrigin = '0 0';
            // allow pointer interactions so lines can be selected/moved/resized like other elements
        } else if (element.element_type === 'freehand') {
            div.classList.add('canvas-shape', 'canvas-freehand');
            // Create SVG for freehand drawing
            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.style.width = '100%';
            svg.style.height = '100%';
            svg.style.position = 'absolute';
            svg.style.pointerEvents = 'none';

            if (element.path_data) {
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', element.path_data);
                path.setAttribute('stroke', this.getRenderColor(element.stroke_color) || '#000000');
                path.setAttribute('stroke-width', element.stroke_width || 2);
                path.setAttribute('fill', 'none');
                path.setAttribute('stroke-linecap', 'round');
                path.setAttribute('stroke-linejoin', 'round');
                svg.appendChild(path);
            }
            div.appendChild(svg);
        }

        if (!this.options.readonly) {
            // Add resize handles for textbox, image and shape elements so they can be resized/moved like images
            const resizableTypes = ['textbox', 'image', 'rectangle', 'circle', 'line', 'freehand'];
            if (resizableTypes.includes(element.element_type)) {
                const handles = ['nw', 'ne', 'sw', 'se'];
                handles.forEach(position => {
                    const handle = document.createElement('div');
                    handle.className = `resize-handle resize-handle-${position}`;
                    handle.dataset.handle = position;
                    div.appendChild(handle);
                });
            }
        }

        // If currently in drawing mode, disable pointer interactions on existing elements
        if (this.drawingMode) {
            try { div.style.pointerEvents = 'none'; } catch (err) { /* ignore */ }
        }

        return div;
    }

    handleMouseDown(e) {
        if (this.options.readonly) return;

        const element = e.target.closest('.canvas-element');

        // If eraser mode, begin erasing
        if (this.drawingMode === 'eraser') {
            e.preventDefault();
            this.startEraser(e.clientX, e.clientY);
            return;
        }

        // If select mode, handle marquee or multi-select/drag
        if (this.selectMode) {
            if (!element) {
                // start marquee selection
                this.startSelection(e.clientX, e.clientY);
                return;
            } else {
                // clicked an element
                const clickedId = element.dataset.elementId;
                // if clicked element already part of selection, start multi-drag
                if (this.selectedElements.includes(String(clickedId))) {
                    this.startDragMulti(e.clientX, e.clientY);
                    return;
                }
                // otherwise select single and start dragging it
                this.selectSingleElement(element);
                this.startDrag(element, e.clientX, e.clientY);
                return;
            }
        }

        // If in drawing mode, start drawing
        if (this.drawingMode) {
            this.startDrawing(e.clientX, e.clientY);
            return;
        }

        if (!element) {
            this.deselectElement();
            return;
        }

        const handle = e.target.closest('.resize-handle');
        if (handle) {
            e.preventDefault();
            this.startResize(element, handle.dataset.handle, e.clientX, e.clientY);
        } else if (e.target.classList.contains('canvas-textarea')) {
            // Allow text editing
            this.selectElement(element);
        } else {
            e.preventDefault();
            this.startDrag(element, e.clientX, e.clientY);
        }
    }

    handleTouchStart(e) {
        if (this.options.readonly) return;
        const touch = e.touches[0];
        const element = touch.target.closest('.canvas-element');

        // If eraser mode, begin erasing (touch devices)
        if (this.drawingMode === 'eraser') {
            e.preventDefault();
            this.startEraser(touch.clientX, touch.clientY);
            return;
        }

        // If in drawing mode, start drawing immediately and do not allow selection/drag
        if (this.drawingMode) {
            this.startDrawing(touch.clientX, touch.clientY);
            return;
        }

        if (this.selectMode) {
            if (!element) {
                this.startSelection(touch.clientX, touch.clientY);
                return;
            } else {
                const clickedId = element.dataset.elementId;
                if (this.selectedElements.includes(String(clickedId))) {
                    this.startDragMulti(touch.clientX, touch.clientY);
                    return;
                }
                this.selectSingleElement(element);
                this.startDrag(element, touch.clientX, touch.clientY);
                return;
            }
        }

        const handle = touch.target.closest('.resize-handle');
        if (handle) {
            e.preventDefault();
            this.startResize(element, handle.dataset.handle, touch.clientX, touch.clientY);
        } else if (touch.target.classList.contains('canvas-textarea')) {
            // Allow text editing
            this.selectElement(element);
        } else {
            e.preventDefault();
            this.startDrag(element, touch.clientX, touch.clientY);
        }
    }

    startDrag(element, clientX, clientY) {
        this.selectElement(element);
        const p = this._clientToCanvas(clientX, clientY);
        this.dragState = {
            isDragging: true,
            element: element,
            elements: null, // used for multi-drag
            startX: p.x,
            startY: p.y,
            elementStartX: parseInt(element.style.left) || 0,
            elementStartY: parseInt(element.style.top) || 0,
            elementStartLeft: parseInt(element.style.left) || 0,
            elementStartTop: parseInt(element.style.top) || 0,
            deltaX: 0,
            deltaY: 0,
        };
    }

    startDragMulti(clientX, clientY) {
        // prepare drag state for multiple selected elements
        const items = [];
        this.selectedElements.forEach(id => {
            const el = (this.canvasContent || this.canvasArea).querySelector(`.canvas-element[data-element-id="${id}"]`);
            if (el) {
                items.push({
                    element: el,
                    startLeft: parseInt(el.style.left) || 0,
                    startTop: parseInt(el.style.top) || 0,
                    id: el.dataset.elementId,
                });
            }
        });

        const p = this._clientToCanvas(clientX, clientY);
        this.dragState = {
            isDragging: true,
            element: null,
            elements: items,
            startX: p.x,
            startY: p.y,
            deltaX: 0,
            deltaY: 0,
        };
    }

    startResize(element, handle, clientX, clientY) {
        this.selectElement(element);
        const p = this._clientToCanvas(clientX, clientY);
        this.resizeState = {
            isResizing: true,
            element: element,
            handle: handle,
            startX: p.x,
            startY: p.y,
            startWidth: parseInt(element.style.width) || 200,
            startHeight: parseInt(element.style.height) || 100,
            startLeft: parseInt(element.style.left) || 0,
            startTop: parseInt(element.style.top) || 0,
        };
    }

    handleMouseMove(e) {
        if (this.selectionState && this.selectionState.isSelecting) {
            e.preventDefault();
            this.updateSelection(e.clientX, e.clientY);
            return;
        }
        if (this.drawingMode === 'eraser' && this.isErasing) {
            e.preventDefault();
            this.eraseAtPoint(e.clientX, e.clientY);
            return;
        }
        if (this.isDrawing) {
            e.preventDefault();
            this.continueDrawing(e.clientX, e.clientY);
        } else if (this.dragState.isDragging) {
            e.preventDefault();
            this.performDrag(e.clientX, e.clientY);
        } else if (this.resizeState.isResizing) {
            e.preventDefault();
            this.performResize(e.clientX, e.clientY);
        }
    }

    handleTouchMove(e) {
        if (this.selectionState && this.selectionState.isSelecting) {
            e.preventDefault();
            const touch = e.touches[0];
            this.updateSelection(touch.clientX, touch.clientY);
            return;
        }
        if (this.drawingMode === 'eraser' && this.isErasing) {
            e.preventDefault();
            const touch = e.touches[0];
            this.eraseAtPoint(touch.clientX, touch.clientY);
            return;
        }
        if (this.isDrawing) {
            e.preventDefault();
            const touch = e.touches[0];
            this.continueDrawing(touch.clientX, touch.clientY);
        } else if (this.dragState.isDragging || this.resizeState.isResizing) {
            e.preventDefault();
            const touch = e.touches[0];
            if (this.dragState.isDragging) {
                this.performDrag(touch.clientX, touch.clientY);
            } else if (this.resizeState.isResizing) {
                this.performResize(touch.clientX, touch.clientY);
            }
        }
    }

    performDrag(clientX, clientY) {
        const p = this._clientToCanvas(clientX, clientY);
        const dx = p.x - this.dragState.startX;
        const dy = p.y - this.dragState.startY;

        // If multi-drag, apply transform to each element
        if (this.dragState.elements && this.dragState.elements.length) {
            this.dragState.deltaX = dx;
            this.dragState.deltaY = dy;
            this.dragState.elements.forEach(item => {
                // Snap to grid if enabled
                let tx = item.startLeft + dx;
                let ty = item.startTop + dy;
                if (this.options.showGrid) {
                    tx = Math.round(tx / this.options.gridSize) * this.options.gridSize;
                    ty = Math.round(ty / this.options.gridSize) * this.options.gridSize;
                }
                tx = Math.max(0, tx);
                ty = Math.max(0, ty);
                item.element.style.transform = `translate(${tx - item.startLeft}px, ${ty - item.startTop}px)`;
            });
            return;
        }

        let newX = this.dragState.elementStartX + dx;
        let newY = this.dragState.elementStartY + dy;

        // Snap to grid if enabled
        if (this.options.showGrid) {
            newX = Math.round(newX / this.options.gridSize) * this.options.gridSize;
            newY = Math.round(newY / this.options.gridSize) * this.options.gridSize;
        }

        // Keep within bounds
        newX = Math.max(0, newX);
        newY = Math.max(0, newY);

        // Use transform for smoother dragging, commit on finish
        const deltaX = newX - this.dragState.elementStartX;
        const deltaY = newY - this.dragState.elementStartY;
        this.dragState.deltaX = deltaX;
        this.dragState.deltaY = deltaY;
        this.dragState.element.style.transform = `translate(${deltaX}px, ${deltaY}px)`;
    }

    performResize(clientX, clientY) {
        const p = this._clientToCanvas(clientX, clientY);
        const dx = p.x - this.resizeState.startX;
        const dy = p.y - this.resizeState.startY;
        const handle = this.resizeState.handle;

        let newWidth = this.resizeState.startWidth;
        let newHeight = this.resizeState.startHeight;
        let newLeft = this.resizeState.startLeft;
        let newTop = this.resizeState.startTop;

        // Calculate new dimensions based on handle
        if (handle.includes('e')) {
            newWidth = Math.max(50, this.resizeState.startWidth + dx);
        }
        if (handle.includes('w')) {
            newWidth = Math.max(50, this.resizeState.startWidth - dx);
            newLeft = this.resizeState.startLeft + (this.resizeState.startWidth - newWidth);
        }
        if (handle.includes('s')) {
            newHeight = Math.max(50, this.resizeState.startHeight + dy);
        }
        if (handle.includes('n')) {
            newHeight = Math.max(50, this.resizeState.startHeight - dy);
            newTop = this.resizeState.startTop + (this.resizeState.startHeight - newHeight);
        }

        // Snap to grid if enabled
        if (this.options.showGrid) {
            newWidth = Math.round(newWidth / this.options.gridSize) * this.options.gridSize;
            newHeight = Math.round(newHeight / this.options.gridSize) * this.options.gridSize;
            newLeft = Math.round(newLeft / this.options.gridSize) * this.options.gridSize;
            newTop = Math.round(newTop / this.options.gridSize) * this.options.gridSize;
        }

        this.resizeState.element.style.width = `${newWidth}px`;
        this.resizeState.element.style.height = `${newHeight}px`;
        this.resizeState.element.style.left = `${newLeft}px`;
        this.resizeState.element.style.top = `${newTop}px`;
    }

    handleMouseUp(e) {
        if (this.selectionState && this.selectionState.isSelecting) {
            this.finishSelection();
            return;
        }
        if (this.drawingMode === 'eraser' && this.isErasing) {
            this.finishEraser();
            return;
        }
        if (this.isDrawing) {
            this.finishDrawing();
        } else if (this.dragState.isDragging) {
            this.finishDrag();
        } else if (this.resizeState.isResizing) {
            this.finishResize();
        }
    }

    handleTouchEnd(e) {
        if (this.selectionState && this.selectionState.isSelecting) {
            this.finishSelection();
            return;
        }
        if (this.drawingMode === 'eraser' && this.isErasing) {
            this.finishEraser();
            return;
        }
        if (this.isDrawing) {
            this.finishDrawing();
        } else if (this.dragState.isDragging) {
            this.finishDrag();
        } else if (this.resizeState.isResizing) {
            this.finishResize();
        }
    }

    finishDrag() {
        // If multi-drag, commit each element
        if (this.dragState.elements && this.dragState.elements.length) {
            const dx = this.dragState.deltaX || 0;
            const dy = this.dragState.deltaY || 0;
            // If nothing moved, skip server updates
            if (dx === 0 && dy === 0) {
                // Clear any transform applied during drag
                this.dragState.elements.forEach(item => { if (item.element) item.element.style.transform = ''; });
                this.dragState = { isDragging: false, element: null, elements: null, startX: 0, startY: 0, deltaX: 0, deltaY: 0 };
                return;
            }
            const promises = [];
            this.dragState.elements.forEach(item => {
                const finalX = item.startLeft + dx;
                const finalY = item.startTop + dy;
                item.element.style.left = `${finalX}px`;
                item.element.style.top = `${finalY}px`;
                item.element.style.transform = '';
                promises.push(this.updateElement(item.id, { x: finalX, y: finalY }));
            });
            // Wait for all updates (not awaited, but kept as array in case)
            Promise.allSettled(promises).then(() => { });
            this.dragState = { isDragging: false, element: null, elements: null, startX: 0, startY: 0, deltaX: 0, deltaY: 0 };
            return;
        }

        const element = this.dragState.element;
        const elementId = element.dataset.elementId;
        // Commit the transform into left/top and clear transform
        const finalX = this.dragState.elementStartX + (this.dragState.deltaX || 0);
        const finalY = this.dragState.elementStartY + (this.dragState.deltaY || 0);
        element.style.left = `${finalX}px`;
        element.style.top = `${finalY}px`;
        element.style.transform = '';

        // Only send update if position changed
        const elObj = this.elements.find(el => String(el.id) === String(elementId));
        const prevX = elObj ? (Number(elObj.x) || 0) : null;
        const prevY = elObj ? (Number(elObj.y) || 0) : null;
        if (prevX === null || prevY === null || prevX !== finalX || prevY !== finalY) {
            const updates = { x: finalX, y: finalY };
            this.updateElement(elementId, updates);
        }
        this.dragState = { isDragging: false, element: null, startX: 0, startY: 0, elementStartX: 0, elementStartY: 0, deltaX: 0, deltaY: 0 };
    }

    finishResize() {
        const element = this.resizeState.element;
        const elementId = element.dataset.elementId;

        const updates = {
            x: parseInt(element.style.left),
            y: parseInt(element.style.top),
            width: parseInt(element.style.width),
            height: parseInt(element.style.height),
        };

        // Only persist if something actually changed compared to local element state
        const elObj = this.elements.find(el => String(el.id) === String(elementId));
        let changed = true;
        if (elObj) {
            const prevX = Number(elObj.x) || 0;
            const prevY = Number(elObj.y) || 0;
            const prevW = Number(elObj.width) || 0;
            const prevH = Number(elObj.height) || 0;
            changed = (prevX !== updates.x) || (prevY !== updates.y) || (prevW !== updates.width) || (prevH !== updates.height);
        }

        if (changed) {
            this.updateElement(elementId, updates);
        }
        this.resizeState = { isResizing: false, element: null };
    }

    // Drawing methods
    startDrawing(clientX, clientY) {
        this.isDrawing = true;
        const p = this._clientToCanvas(clientX, clientY);
        this.drawingStartX = p.x;
        this.drawingStartY = p.y;
        this.drawingEndX = this.drawingStartX;
        this.drawingEndY = this.drawingStartY;

        if (this.drawingMode === 'freehand') {
            this.currentPath = [{ x: this.drawingStartX, y: this.drawingStartY }];
        }

        // Create preview element
        this.previewElement = document.createElement('div');
        this.previewElement.className = 'canvas-drawing-preview';
        this.previewElement.style.position = 'absolute';
        this.previewElement.style.pointerEvents = 'none';
        // append the preview to the scaled content so it zooms with the canvas
        if (this.canvasContent) this.canvasContent.appendChild(this.previewElement);
        // Ensure scale applied visually when previewing
        this._applyScale();
    }

    continueDrawing(clientX, clientY) {
        if (!this.isDrawing) return;
        const p = this._clientToCanvas(clientX, clientY);
        const currentX = p.x;
        const currentY = p.y;

        this.drawingEndX = currentX;
        this.drawingEndY = currentY;

        if (this.drawingMode === 'freehand') {
            this.currentPath.push({ x: currentX, y: currentY });
            this.updateFreehandPreview();
        } else {
            this.updateShapePreview(currentX, currentY);
        }
    }

    updateShapePreview(currentX, currentY) {
        const x = Math.min(this.drawingStartX, currentX);
        const y = Math.min(this.drawingStartY, currentY);
        const width = Math.abs(currentX - this.drawingStartX);
        const height = Math.abs(currentY - this.drawingStartY);

        const previewColor = this.getRenderColor(this.currentStrokeColor) || (this.isDarkMode() ? '#ffffff' : '#000000');

        this.previewElement.style.left = `${x}px`;
        this.previewElement.style.top = `${y}px`;
        this.previewElement.style.width = `${width}px`;
        this.previewElement.style.height = `${height}px`;
        this.previewElement.style.border = `2px dashed ${previewColor}`;

        if (this.drawingMode === 'circle') {
            this.previewElement.style.borderRadius = '50%';
        } else if (this.drawingMode === 'line') {
            const length = Math.sqrt(width ** 2 + height ** 2);
            const angle = Math.atan2(currentY - this.drawingStartY, currentX - this.drawingStartX) * (180 / Math.PI);
            this.previewElement.style.width = `${length}px`;
            this.previewElement.style.height = '2px';
            this.previewElement.style.left = `${this.drawingStartX}px`;
            this.previewElement.style.top = `${this.drawingStartY}px`;
            this.previewElement.style.transform = `rotate(${angle}deg)`;
            this.previewElement.style.transformOrigin = '0 0';
            this.previewElement.style.backgroundColor = previewColor;
            this.previewElement.style.border = 'none';
        }
    }

    updateFreehandPreview() {
        if (this.currentPath.length < 2) return;
        // Create SVG path for preview with a small margin so strokes don't appear clipped
        this.previewElement.innerHTML = '';
        const minX = Math.min(...this.currentPath.map(p => p.x));
        const minY = Math.min(...this.currentPath.map(p => p.y));
        const maxX = Math.max(...this.currentPath.map(p => p.x));
        const maxY = Math.max(...this.currentPath.map(p => p.y));

        const strokeWidth = 2;
        // Allow a configurable margin; default is provided by options.freehandMargin
        const margin = this.options.freehandMargin || Math.max(4, Math.ceil(strokeWidth / 2) + 2);

        const adjMinX = Math.max(0, minX - margin);
        const adjMinY = Math.max(0, minY - margin);
        const adjMaxX = maxX + margin;
        const adjMaxY = maxY + margin;

        this.previewElement.style.left = `${adjMinX}px`;
        this.previewElement.style.top = `${adjMinY}px`;
        this.previewElement.style.width = `${adjMaxX - adjMinX}px`;
        this.previewElement.style.height = `${adjMaxY - adjMinY}px`;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.style.width = '100%';
        svg.style.height = '100%';
        svg.style.position = 'absolute';

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        const pathData = this.currentPath.map((p, i) =>
            `${i === 0 ? 'M' : 'L'} ${p.x - adjMinX} ${p.y - adjMinY}`
        ).join(' ');

        path.setAttribute('d', pathData);
        path.setAttribute('stroke', this.getRenderColor(this.currentStrokeColor) || '#000000');
        path.setAttribute('stroke-width', String(strokeWidth));
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke-linecap', 'round');
        path.setAttribute('stroke-linejoin', 'round');

        svg.appendChild(path);
        this.previewElement.appendChild(svg);
    }

    // Eraser methods
    startEraser(clientX, clientY) {
        this.isErasing = true;
        this.eraserDeletedIds = new Set();
        this.eraserDeletedSnapshots = [];
        // perform immediate erase at start
        this.eraseAtPoint(clientX, clientY);
    }

    eraseAtPoint(clientX, clientY) {
        if (!this.isErasing) return;
        const p = this._clientToCanvas(clientX, clientY);
        const x = p.x;
        const y = p.y;
        // Eraser radius (virtual finger/tool size). Allow override via options.
        const eraserRadius = this.options.eraserRadius || 8;

        // Find elements that the eraser actually hits using shape-aware hit testing
        const candidates = [];
        for (const el of this.elements) {
            try {
                if (this._pointHitsElement(x, y, el, eraserRadius)) {
                    candidates.push(el);
                }
            } catch (err) {
                // If anything goes wrong with per-shape hit testing, fallback to bbox
                const left = Math.min(Number(el.x) || 0, Number(el.x + (el.width || 0)) || 0);
                const top = Math.min(Number(el.y) || 0, Number(el.y + (el.height || 0)) || 0);
                const right = Math.max(Number(el.x) || 0, Number(el.x + (el.width || 0)) || 0);
                const bottom = Math.max(Number(el.y) || 0, Number(el.y + (el.height || 0)) || 0);
                if (x >= left && x <= right && y >= top && y <= bottom) candidates.push(el);
            }
        }

        // Delete candidates that are not already deleted in this stroke
        candidates.forEach(async (el) => {
            const idStr = String(el.id);
            if (this.eraserDeletedIds.has(idStr)) return;
            // snapshot
            const snap = Object.assign({}, el);
            this.eraserDeletedSnapshots.push(snap);
            this.eraserDeletedIds.add(idStr);
            // delete from server (suppress history here)
            await this._deleteElementById(el.id, { suppressHistory: true });
        });
    }

    // Returns true if point (x,y) hits the element considering its geometry and stroke width.
    _pointHitsElement(x, y, element, eraserRadius = 8) {
        // default tolerance is half stroke width plus eraser radius
        const stroke = Number(element.stroke_width) || 2;
        const tol = (stroke / 2) + eraserRadius;

        if (!element || !element.element_type) return false;

        if (element.element_type === 'freehand' && element.path_data) {
            // path_data is expected as 'M x y L x y L x y ...'
            const coords = [];
            // extract numbers
            const nums = element.path_data.match(/-?\d*\.?\d+/g);
            if (!nums || nums.length < 4) return false;
            for (let i = 0; i < nums.length; i += 2) {
                const px = parseFloat(nums[i]);
                const py = parseFloat(nums[i + 1]);
                if (!isNaN(px) && !isNaN(py)) coords.push({ x: px + (Number(element.x) || 0), y: py + (Number(element.y) || 0) });
            }
            // check distance to each segment
            for (let i = 0; i < coords.length - 1; i++) {
                const p1 = coords[i];
                const p2 = coords[i + 1];
                const d = this._pointToSegmentDistance(x, y, p1.x, p1.y, p2.x, p2.y);
                if (d <= tol) return true;
            }
            return false;
        }

        if (element.element_type === 'line') {
            // line endpoints using stored width/height deltas
            const x1 = Number(element.x) || 0;
            const y1 = Number(element.y) || 0;
            const x2 = x1 + (Number(element.width) || 0);
            const y2 = y1 + (Number(element.height) || 0);
            const d = this._pointToSegmentDistance(x, y, x1, y1, x2, y2);
            return d <= tol;
        }

        // For rectangles, circles and images/textboxes, fall back to bbox intersection
        const left = Math.min(Number(element.x) || 0, Number(element.x + (element.width || 0)) || 0);
        const top = Math.min(Number(element.y) || 0, Number(element.y + (element.height || 0)) || 0);
        const right = Math.max(Number(element.x) || 0, Number(element.x + (element.width || 0)) || 0);
        const bottom = Math.max(Number(element.y) || 0, Number(element.y + (element.height || 0)) || 0);
        // Expand bbox a bit by tolerance to account for stroke and eraser area
        if (x >= left - tol && x <= right + tol && y >= top - tol && y <= bottom + tol) return true;
        return false;
    }

    // Distance from point to segment (x1,y1)-(x2,y2)
    _pointToSegmentDistance(px, py, x1, y1, x2, y2) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        if (dx === 0 && dy === 0) {
            // it's a point
            const vx = px - x1;
            const vy = py - y1;
            return Math.sqrt(vx * vx + vy * vy);
        }
        // Project point onto segment, computing parameterized position t
        const t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy);
        if (t < 0) {
            // nearest to x1,y1
            const vx = px - x1;
            const vy = py - y1;
            return Math.sqrt(vx * vx + vy * vy);
        } else if (t > 1) {
            // nearest to x2,y2
            const vx = px - x2;
            const vy = py - y2;
            return Math.sqrt(vx * vx + vy * vy);
        }
        // projection falls on segment
        const projx = x1 + t * dx;
        const projy = y1 + t * dy;
        const vx = px - projx;
        const vy = py - projy;
        return Math.sqrt(vx * vx + vy * vy);
    }

    finishEraser() {
        if (!this.isErasing) return;
        this.isErasing = false;
        const hadDeletions = this.eraserDeletedSnapshots && this.eraserDeletedSnapshots.length;
        if (hadDeletions) {
            this._pushHistory({ type: 'delete', elements: this.eraserDeletedSnapshots.slice() });
        }
        this.eraserDeletedSnapshots = [];
        this.eraserDeletedIds = new Set();
        this.renderElements();
        if (hadDeletions) this.options.onSave();
    }

    async finishDrawing() {
        if (!this.isDrawing) return;
        this.isDrawing = false;

        // Remove preview
        if (this.previewElement) {
            this.previewElement.remove();
            this.previewElement = null;
        }

        // Create the actual element
        if (this.drawingMode === 'freehand') {
            if (this.currentPath.length < 2) {
                this.currentPath = [];
                return;
            }
            await this.createFreehandElement();
        } else {
            const rect = this.canvasArea.getBoundingClientRect();
            await this.createShapeElement();
        }
    }

    async createShapeElement() {
        // For lines we preserve signed deltas so the angle reflects drag direction.
        let x, y, width, height;
        if (this.drawingMode === 'line') {
            x = Math.round(this.drawingStartX);
            y = Math.round(this.drawingStartY);
            width = Math.round(this.drawingEndX - this.drawingStartX); // signed
            height = Math.round(this.drawingEndY - this.drawingStartY); // signed
        } else {
            x = Math.min(this.drawingStartX, this.drawingEndX);
            y = Math.min(this.drawingStartY, this.drawingEndY);
            width = Math.abs(this.drawingEndX - this.drawingStartX);
            height = Math.abs(this.drawingEndY - this.drawingStartY);
        }

        // Don't create tiny shapes. For lines use length threshold so short diagonal
        // strokes are still captured even if one delta is small.
        if (this.drawingMode === 'line') {
            const length = Math.sqrt(width * width + height * height);
            if (length < 10) return;
        } else {
            if (width < 10 || height < 10) return;
        }

        const data = {
            element_type: this.drawingMode,
            x: Math.round(x),
            y: Math.round(y),
            width: Math.round(width),
            height: Math.round(height),
            stroke_color: this.currentStrokeColor || 'default',
            fill_color: '',
            stroke_width: this.currentStrokeWidth || 2,
            z_index: this.elements.length,
        };

        if (this.options.noteId) {
            data.note_id = this.options.noteId;
        } else if (this.options.sharedNoteId) {
            data.shared_note_id = this.options.sharedNoteId;
        }

        try {
            const response = await fetch('/canvas/elements/create/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.options.csrfToken,
                },
                body: JSON.stringify(data),
            });

            const result = await response.json();
            if (result.success) {
                this.elements.push(result.element);
                // Record creation for undo/redo
                try { this._pushHistory({ type: 'create', element: result.element }); } catch (e) { }
                this.renderElements();
                this.options.onSave();
                // If a textbox was just created via drawing, focus its textarea for immediate editing
                if (result.element && result.element.element_type === 'textbox') {
                    setTimeout(() => {
                        try {
                            const elDiv = (this.canvasContent || this.canvasArea).querySelector(`.canvas-element[data-element-id="${result.element.id}"]`);
                            if (elDiv) {
                                const ta = elDiv.querySelector('.canvas-textarea');
                                if (ta) {
                                    ta.focus();
                                    if (typeof ta.select === 'function') ta.select();
                                }
                            }
                        } catch (err) {
                            // ignore
                        }
                    }, 0);
                }
            } else {
                this.options.onError(result.error || 'Failed to create shape');
            }
        } catch (error) {
            this.options.onError(error.message);
        }
    }

    async createFreehandElement() {
        const minX = Math.min(...this.currentPath.map(p => p.x));
        const minY = Math.min(...this.currentPath.map(p => p.y));
        const maxX = Math.max(...this.currentPath.map(p => p.x));
        const maxY = Math.max(...this.currentPath.map(p => p.y));

        // Add a small buffer so the stroke doesn't get clipped at the edges.
        // Use a margin based on stroke width; keep at least 4px for breathing room.
        const strokeWidth = 2;
        // Use configurable margin when provided, otherwise default to the option or a small computed margin
        const margin = this.options.freehandMargin || Math.max(4, Math.ceil(strokeWidth / 2) + 2);

        const adjMinX = Math.max(0, minX - margin);
        const adjMinY = Math.max(0, minY - margin);
        const adjMaxX = maxX + margin;
        const adjMaxY = maxY + margin;

        // Convert path to relative coordinates and SVG path data using adjusted origin
        const pathData = this.currentPath.map((p, i) =>
            `${i === 0 ? 'M' : 'L'} ${p.x - adjMinX} ${p.y - adjMinY}`
        ).join(' ');

        const data = {
            element_type: 'freehand',
            x: Math.round(adjMinX),
            y: Math.round(adjMinY),
            width: Math.round(adjMaxX - adjMinX),
            height: Math.round(adjMaxY - adjMinY),
            stroke_color: this.currentStrokeColor || 'default',
            stroke_width: this.currentStrokeWidth || strokeWidth,
            path_data: pathData,
            z_index: this.elements.length,
        };

        if (this.options.noteId) {
            data.note_id = this.options.noteId;
        } else if (this.options.sharedNoteId) {
            data.shared_note_id = this.options.sharedNoteId;
        }

        try {
            const response = await fetch('/canvas/elements/create/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.options.csrfToken,
                },
                body: JSON.stringify(data),
            });

            const result = await response.json();
            if (result.success) {
                this.elements.push(result.element);
                // record creation for undo
                this._pushHistory({ type: 'create', element: result.element });
                this.renderElements();
                this.options.onSave();
                this.currentPath = [];
            } else {
                this.options.onError(result.error || 'Failed to create drawing');
            }
        } catch (error) {
            this.options.onError(error.message);
        }
    }

    selectElement(element) {
        // Remove previous selection
        (this.canvasContent || this.canvasArea).querySelectorAll('.canvas-element').forEach(el => {
            el.classList.remove('selected');
        });

        element.classList.add('selected');
        this.selectedElement = element;
        this.selectedElements = [String(element.dataset.elementId)];
        // Ensure delete button is present without rebuilding DOM
        this.ensureDeleteButton();
    }

    deselectElement() {
        (this.canvasContent || this.canvasArea).querySelectorAll('.canvas-element').forEach(el => {
            el.classList.remove('selected');
        });
        this.selectedElement = null;
        this.selectedElements = [];
        // Update toolbar
        this.removeDeleteButton();
    }

    selectSingleElement(element) {
        this.deselectElement();
        if (!element) return;
        element.classList.add('selected');
        this.selectedElement = element;
        this.selectedElements = [String(element.dataset.elementId)];
        this.ensureDeleteButton();
    }

    // Map abstract color names to theme-aware hex colors
    isDarkMode() {
        try {
            // First consult the configured themeProvider (app-level variable or getter)
            if (this.themeProvider) {
                const t = this.themeProvider();
                if (t !== undefined && t !== null) {
                    // Interpret booleans directly
                    if (typeof t === 'boolean') return t === true;
                    // Strings: allow 'dark'/'light', truthy 'true'/'1', or any value containing 'dark'
                    const s = String(t).toLowerCase().trim();
                    if (s === 'dark' || s === '1' || s === 'true') return true;
                    if (s === 'light' || s === '0' || s === 'false') return false;
                    if (s.indexOf('dark') !== -1) return true;
                    if (s.indexOf('light') !== -1) return false;
                }
            }

            // Fallback to media query and body class
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return true;
            return document.body && document.body.classList && document.body.classList.contains('dark-mode');
        } catch (err) {
            return false;
        }
    }

    // Public helper: re-render elements using current theme provider mapping
    refreshTheme() {
        if (this.options.debugTheme) console.debug('CanvasEditor.refreshTheme() called');
        try {
            this.renderElements();
        } catch (err) {
            if (this.options.debugTheme) console.error('refreshTheme error', err);
        }
    }

    // Convert client (screen) coordinates to canvas coordinates taking current scale into account
    _clientToCanvas(clientX, clientY) {
        const rect = this.canvasArea.getBoundingClientRect();
        const x = (clientX - rect.left + this.canvasArea.scrollLeft) / (this.scale || 1);
        const y = (clientY - rect.top + this.canvasArea.scrollTop) / (this.scale || 1);
        return { x, y };
    }

    // Apply current scale to canvas area (visual zoom)
    _applyScale() {
        try {
            if (this.canvasArea) {
                // Ensure the canvas area is sized so that when scaled it fills the visible container.
                // This prevents blank space appearing around the canvas when zooming out.
                try {
                    const containerRect = this.container.getBoundingClientRect();
                    const toolbarRect = this.toolbar ? this.toolbar.getBoundingClientRect() : { height: 0 };
                    // Available visual area for the canvas (width x height). If container height is 0
                    // (parent didn't provide explicit height), fallback to window innerHeight.
                    const availableWidth = Math.max(200, containerRect.width || window.innerWidth);
                    const availableHeight = Math.max(200, (containerRect.height || (window.innerHeight - (toolbarRect.height || 0))) - (toolbarRect.height || 0));

                    // Base logical size needed so that after scaling it covers available area
                    const baseLogicalWidth = Math.round(availableWidth / (this.scale || 1));
                    const baseLogicalHeight = Math.round(availableHeight / (this.scale || 1));

                    // Compute content extents from elements so the logical canvas always contains all elements
                    let maxContentW = 0;
                    let maxContentH = 0;
                    try {
                        if (Array.isArray(this.elements) && this.elements.length) {
                            for (const el of this.elements) {
                                const ex = Number(el.x) || 0;
                                const ey = Number(el.y) || 0;
                                const ew = Number(el.width) || 0;
                                const eh = Number(el.height) || 0;
                                maxContentW = Math.max(maxContentW, Math.ceil(ex + ew));
                                maxContentH = Math.max(maxContentH, Math.ceil(ey + eh));
                            }
                        }
                    } catch (e) {
                        maxContentW = 0; maxContentH = 0;
                    }

                    // Add a small padding so elements near the edge remain reachable
                    const padding = 120;

                    // Ensure logical size is at least large enough to cover available area after scaling
                    // and also large enough to contain content extents + padding.
                    const logicalWidth = Math.max(baseLogicalWidth, maxContentW + padding, 200);
                    const logicalHeight = Math.max(baseLogicalHeight, maxContentH + padding, 200);

                    // Guard against absurd sizes
                    const finalWidth = Math.min(100000, logicalWidth);
                    const finalHeight = Math.min(100000, logicalHeight);

                    // Apply logical dimensions to inner content (these are unscaled units).
                    // The outer canvasArea keeps a stable visual footprint; the inner canvasContent is scaled.
                    if (this.canvasContent) {
                        this.canvasContent.style.width = `${finalWidth}px`;
                        this.canvasContent.style.minWidth = `${finalWidth}px`;
                        this.canvasContent.style.height = `${finalHeight}px`;
                        this.canvasContent.style.minHeight = `${finalHeight}px`;

                        // Force reflow so scrollable area updates immediately
                        // eslint-disable-next-line no-unused-expressions
                        this.canvasContent.offsetHeight;

                        // If computed scrollable area is still smaller than the content extents (rare edge cases), expand height further
                        const requiredUnscaledHeight = maxContentH + padding;
                        if (this.canvasContent.scrollHeight < requiredUnscaledHeight) {
                            this.canvasContent.style.height = `${Math.min(100000, requiredUnscaledHeight)}px`;
                        }
                    }
                } catch (err) {
                    // If measurement fails, continue with transform-only behavior
                }

                // Apply CSS scale to visually zoom the inner content
                if (this.canvasContent) {
                    this.canvasContent.style.transform = `scale(${this.scale})`;
                } else {
                    // Fallback: if canvasContent isn't available, scale the outer area
                    this.canvasArea.style.transform = `scale(${this.scale})`;
                }
            }
        } catch (err) { /* ignore */ }
    }

    zoomIn() {
        this.scale = Math.min(4, (this.scale || 1) * 1.2);
        this._applyScale();
        // Rebuild toolbar UI (to update any UI reflecting scale)
        try { if (this.toolbar) this._updatePickersUI(); } catch (e) { }
    }

    zoomOut() {
        this.scale = Math.max(0.25, (this.scale || 1) / 1.2);
        this._applyScale();
        try { if (this.toolbar) this._updatePickersUI(); } catch (e) { }
    }

    getRenderColor(storedColor) {
        // If storedColor is a hex value, return as-is
        if (!storedColor) return null;
        storedColor = String(storedColor).trim();
        // normalize case for named colors
        const normalized = storedColor.toLowerCase();
        if (normalized.startsWith('#')) return normalized;

        // Define palettes for light and dark modes
        const palettes = {
            light: {
                default: '#000000',
                red: '#ef4444',
                green: '#10b981',
                blue: '#3b82f6',
                yellow: '#f59e0b',
                purple: '#8b5cf6',
            },
            // Neon/bright palette for dark mode to make colors pop
            dark: {
                default: '#ffffff',
                red: '#ff4d4d',
                green: '#2dd4bf',
                blue: '#60a5fa',
                yellow: '#ffd166',
                purple: '#c084fc',
            }
        };

        const theme = this.isDarkMode() ? 'dark' : 'light';
        if (palettes[theme] && palettes[theme][normalized]) return palettes[theme][normalized];

        // Fallback: if storedColor is a named CSS color, try that
        try {
            const s = new Option().style;
            s.color = normalized;
            if (s.color) return normalized;
        } catch (err) { }

        // Default fallback
        return palettes[theme].default;
    }

    startSelection(clientX, clientY) {
        const p = this._clientToCanvas(clientX, clientY);
        this.selectionState = { isSelecting: true, startX: p.x, startY: p.y };
        // Create a visual rectangle
        if (this.selectionRect) this.selectionRect.remove();
        this.selectionRect = document.createElement('div');
        this.selectionRect.className = 'selection-rect';
        Object.assign(this.selectionRect.style, {
            position: 'absolute',
            border: '1px dashed #000',
            backgroundColor: 'rgba(0, 120, 215, 0.12)',
            left: '0px',
            top: '0px',
            width: '0px',
            height: '0px',
            pointerEvents: 'none',
        });
        if (this.canvasContent) this.canvasContent.appendChild(this.selectionRect);
    }

    updateSelection(clientX, clientY) {
        if (!this.selectionState || !this.selectionState.isSelecting) return;
        const p = this._clientToCanvas(clientX, clientY);
        const startX = this.selectionState.startX;
        const startY = this.selectionState.startY;
        const currentX = p.x;
        const currentY = p.y;

        const x = Math.min(startX, currentX);
        const y = Math.min(startY, currentY);
        const w = Math.abs(currentX - startX);
        const h = Math.abs(currentY - startY);

        this.selectionRect.style.left = `${x}px`;
        this.selectionRect.style.top = `${y}px`;
        this.selectionRect.style.width = `${w}px`;
        this.selectionRect.style.height = `${h}px`;
    }

    finishSelection() {
        if (!this.selectionState || !this.selectionState.isSelecting) return;
        // Compute selected elements intersecting selectionRect
        const rectLeft = parseInt(this.selectionRect.style.left) || 0;
        const rectTop = parseInt(this.selectionRect.style.top) || 0;
        const rectW = parseInt(this.selectionRect.style.width) || 0;
        const rectH = parseInt(this.selectionRect.style.height) || 0;

        const selected = [];
        (this.canvasContent || this.canvasArea).querySelectorAll('.canvas-element').forEach(el => {
            const elLeft = parseInt(el.style.left) || 0;
            const elTop = parseInt(el.style.top) || 0;
            const elW = parseInt(el.style.width) || 0;
            const elH = parseInt(el.style.height) || 0;

            const intersects = !(elLeft > rectLeft + rectW || elLeft + elW < rectLeft || elTop > rectTop + rectH || elTop + elH < rectTop);
            if (intersects) {
                selected.push(el.dataset.elementId);
            }
        });

        // Apply selection
        this.deselectElement();
        selected.forEach(id => {
            const el = (this.canvasContent || this.canvasArea).querySelector(`.canvas-element[data-element-id="${id}"]`);
            if (el) el.classList.add('selected');
        });
        this.selectedElements = selected.map(String);
        this.selectedElement = selected.length ? (this.canvasContent || this.canvasArea).querySelector(`.canvas-element[data-element-id="${selected[0]}"]`) : null;
        this.removeSelectionRect();
        this.selectionState = { isSelecting: false, startX: 0, startY: 0 };
        this.ensureDeleteButton();
    }

    removeSelectionRect() {
        if (this.selectionRect) {
            this.selectionRect.remove();
            this.selectionRect = null;
        }
    }

    ensureDeleteButton() {
        if (!this.toolbar) return;
        let deleteBtn = this.toolbar.querySelector('[data-action="delete-element"]');
        if (!this.selectedElement) {
            if (deleteBtn) deleteBtn.remove();
            return;
        }
        if (!deleteBtn) {
            deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'btn-canvas btn-canvas-danger';
            deleteBtn.dataset.action = 'delete-element';
            deleteBtn.innerHTML = '<span>🗑️</span> Delete';
            // Place at end of toolbar
            this.toolbar.appendChild(deleteBtn);
            // Attach click handler
            deleteBtn.addEventListener('click', () => this.handleToolbarAction('delete-element'));
        }
    }

    removeDeleteButton() {
        if (!this.toolbar) return;
        const deleteBtn = this.toolbar.querySelector('[data-action="delete-element"]');
        if (deleteBtn) deleteBtn.remove();
    }

    async deleteSelectedElement() {
        // If multiple elements selected, delete all of them
        const toDelete = (this.selectedElements && this.selectedElements.length) ? [...this.selectedElements] : (this.selectedElement ? [String(this.selectedElement.dataset.elementId)] : []);
        if (!toDelete.length) return;
        // Capture snapshots for undo
        const snapshots = this.elements.filter(el => toDelete.includes(String(el.id))).map(el => Object.assign({}, el));

        try {
            // Delete each on server, suppress individual history (we'll push grouped action)
            const promises = toDelete.map(id => this._deleteElementById(id, { suppressHistory: true }));
            const results = await Promise.all(promises);
            const failed = results.filter(r => !r || r.success === false);
            if (failed.length) {
                const errMsg = (failed[0] && failed[0].error) ? failed[0].error : 'Failed to delete one or more elements';
                this.options.onError(errMsg);
            }

            // Push grouped delete action for undo
            if (snapshots.length) this._pushHistory({ type: 'delete', elements: snapshots });

            // Clear selection & refresh
            this.selectedElement = null;
            this.selectedElements = [];
            this.renderElements();
            this.removeDeleteButton();
            this.options.onSave();
        } catch (error) {
            this.options.onError(error.message);
        }
    }

    // Debounce text updates
    debounceUpdateElement(elementId, updates) {
        if (this.updateTimeout) {
            clearTimeout(this.updateTimeout);
        }

        this.updateTimeout = setTimeout(() => {
            this.updateElement(elementId, updates);
        }, 500);
    }

    async updateElement(elementId, updates, opts = {}) {
        try {
            const element = this.elements.find(el => el.id == elementId);
            let prev = null;
            if (element && !opts.suppressHistory && !this._suppressHistory) {
                prev = {};
                for (const k in updates) {
                    prev[k] = element[k];
                }
            }

            const response = await fetch(`/canvas/elements/${elementId}/update/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.options.csrfToken,
                },
                body: JSON.stringify(updates),
            });

            const result = await response.json();
            if (result.success) {
                // Update local element data
                const el = this.elements.find(el => el.id == elementId);
                if (el) {
                    Object.assign(el, updates);
                }
                // Push history after success
                if (prev) {
                    this._pushHistory({ type: 'update', id: elementId, prev: prev, next: updates });
                }
                this.options.onSave();
            } else {
                this.options.onError(result.error || 'Failed to update element');
            }
        } catch (error) {
            this.options.onError(error.message);
        }
    }
}

// Export for use in other scripts
window.CanvasEditor = CanvasEditor;
