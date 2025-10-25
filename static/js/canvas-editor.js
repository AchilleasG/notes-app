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
            onSave: options.onSave || (() => { }),
            onError: options.onError || ((error) => console.error(error)),
        };

        this.elements = [];
        this.selectedElement = null;
        // Guard to avoid re-registering document-level listeners
        this._staticListenersAttached = false;
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

    init() {
        this.createCanvas();
        this.loadElements();
        this.attachEventListeners();
    }

    createCanvas() {
        this.container.innerHTML = `
            <div class="canvas-editor">
                <div class="canvas-toolbar">
                    <button type="button" class="btn-canvas btn-canvas-primary" data-action="add-textbox">
                        <span>📝</span> Add Text
                    </button>
                    <button type="button" class="btn-canvas btn-canvas-primary" data-action="add-image">
                        <span>🖼️</span> Add Image
                    </button>
                    <button type="button" class="btn-canvas btn-canvas-secondary" data-action="toggle-grid">
                        <span>⊞</span> <span class="grid-toggle-text">${this.options.showGrid ? 'Hide' : 'Show'} Grid</span>
                    </button>
                    ${this.selectedElement ? `
                        <button type="button" class="btn-canvas btn-canvas-danger" data-action="delete-element">
                            <span>🗑️</span> Delete
                        </button>
                    ` : ''}
                </div>
                <div class="canvas-area ${this.options.showGrid ? 'show-grid' : ''}" 
                     style="--grid-size: ${this.options.gridSize}px;">
                    <!-- Elements will be rendered here -->
                </div>
                <input type="file" id="imageUploadInput" accept="image/*" style="display: none;">
            </div>
        `;

        this.toolbar = this.container.querySelector('.canvas-toolbar');
        this.canvasArea = this.container.querySelector('.canvas-area');
        this.imageInput = this.container.querySelector('#imageUploadInput');
    }

    attachEventListeners() {
        if (this.options.readonly) return;
        // Attach listeners tied to current DOM elements (safe to call after re-render)
        this.attachDynamicEventListeners();
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
        });

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
    }

    handleToolbarAction(action) {
        switch (action) {
            case 'add-textbox':
                this.addTextbox();
                break;
            case 'add-image':
                this.imageInput.click();
                break;
            case 'toggle-grid':
                this.toggleGrid();
                break;
            case 'delete-element':
                this.deleteSelectedElement();
                break;
        }
    }

    toggleGrid() {
        this.options.showGrid = !this.options.showGrid;
        this.canvasArea.classList.toggle('show-grid', this.options.showGrid);
        const gridToggleText = this.toolbar.querySelector('.grid-toggle-text');
        if (gridToggleText) {
            gridToggleText.textContent = this.options.showGrid ? 'Hide Grid' : 'Show Grid';
        }
    }

    async addTextbox() {
        const data = {
            element_type: 'textbox',
            x: 50,
            y: 50,
            width: 200,
            height: 100,
            text_content: 'New text box',
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
                this.renderElements();
                this.options.onSave();
            } else {
                this.options.onError(result.error || 'Failed to create element');
            }
        } catch (error) {
            this.options.onError(error.message);
        }
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
        this.canvasArea.innerHTML = '';

        // Sort by z-index
        const sortedElements = [...this.elements].sort((a, b) => a.z_index - b.z_index);

        sortedElements.forEach(element => {
            const elementDiv = this.createElementDiv(element);
            this.canvasArea.appendChild(elementDiv);
        });
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
            div.appendChild(img);
        }

        if (!this.options.readonly) {
            // Add resize handles
            const handles = ['nw', 'ne', 'sw', 'se'];
            handles.forEach(position => {
                const handle = document.createElement('div');
                handle.className = `resize-handle resize-handle-${position}`;
                handle.dataset.handle = position;
                div.appendChild(handle);
            });
        }

        return div;
    }

    handleMouseDown(e) {
        if (this.options.readonly) return;

        const element = e.target.closest('.canvas-element');
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
        if (!element) {
            this.deselectElement();
            return;
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

        this.dragState = {
            isDragging: true,
            element: element,
            startX: clientX,
            startY: clientY,
            elementStartX: parseInt(element.style.left) || 0,
            elementStartY: parseInt(element.style.top) || 0,
            deltaX: 0,
            deltaY: 0,
        };
    }

    startResize(element, handle, clientX, clientY) {
        this.selectElement(element);

        this.resizeState = {
            isResizing: true,
            element: element,
            handle: handle,
            startX: clientX,
            startY: clientY,
            startWidth: parseInt(element.style.width) || 200,
            startHeight: parseInt(element.style.height) || 100,
            startLeft: parseInt(element.style.left) || 0,
            startTop: parseInt(element.style.top) || 0,
        };
    }

    handleMouseMove(e) {
        if (this.dragState.isDragging) {
            e.preventDefault();
            this.performDrag(e.clientX, e.clientY);
        } else if (this.resizeState.isResizing) {
            e.preventDefault();
            this.performResize(e.clientX, e.clientY);
        }
    }

    handleTouchMove(e) {
        if (this.dragState.isDragging || this.resizeState.isResizing) {
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
        const dx = clientX - this.dragState.startX;
        const dy = clientY - this.dragState.startY;

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
        const dx = clientX - this.resizeState.startX;
        const dy = clientY - this.resizeState.startY;
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
        if (this.dragState.isDragging) {
            this.finishDrag();
        } else if (this.resizeState.isResizing) {
            this.finishResize();
        }
    }

    handleTouchEnd(e) {
        if (this.dragState.isDragging) {
            this.finishDrag();
        } else if (this.resizeState.isResizing) {
            this.finishResize();
        }
    }

    finishDrag() {
        const element = this.dragState.element;
        const elementId = element.dataset.elementId;
        // Commit the transform into left/top and clear transform
        const finalX = this.dragState.elementStartX + (this.dragState.deltaX || 0);
        const finalY = this.dragState.elementStartY + (this.dragState.deltaY || 0);
        element.style.left = `${finalX}px`;
        element.style.top = `${finalY}px`;
        element.style.transform = '';

        const updates = { x: finalX, y: finalY };

        this.updateElement(elementId, updates);
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

        this.updateElement(elementId, updates);
        this.resizeState = { isResizing: false, element: null };
    }

    selectElement(element) {
        // Remove previous selection
        this.canvasArea.querySelectorAll('.canvas-element').forEach(el => {
            el.classList.remove('selected');
        });

        element.classList.add('selected');
        this.selectedElement = element;
        // Ensure delete button is present without rebuilding DOM
        this.ensureDeleteButton();
    }

    deselectElement() {
        this.canvasArea.querySelectorAll('.canvas-element').forEach(el => {
            el.classList.remove('selected');
        });
        this.selectedElement = null;
        // Update toolbar
        this.removeDeleteButton();
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
        if (!this.selectedElement) return;

        const elementId = this.selectedElement.dataset.elementId;

        try {
            const response = await fetch(`/canvas/elements/${elementId}/delete/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.options.csrfToken,
                },
            });

            const result = await response.json();
            if (result.success) {
                this.elements = this.elements.filter(el => el.id != elementId);
                this.selectedElement = null;
                this.renderElements();
                // Refresh toolbar state
                this.removeDeleteButton();
                this.options.onSave();
            } else {
                this.options.onError(result.error || 'Failed to delete element');
            }
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

    async updateElement(elementId, updates) {
        try {
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
                const element = this.elements.find(el => el.id == elementId);
                if (element) {
                    Object.assign(element, updates);
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
