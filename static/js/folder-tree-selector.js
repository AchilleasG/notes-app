/**
 * Folder Tree Selector - Reusable component for both personal and shared notes
 * Creates a tree-like folder selection interface
 */

class FolderTreeSelector {
    constructor(folders, currentFolderId = null) {
        this.folders = folders;
        this.currentFolderId = currentFolderId;
        this.selectedFolderId = currentFolderId;
        this.rootFolders = this.buildFolderTree(folders);
    }

    buildFolderTree(folders) {
        // Build a tree structure from flat folder array
        const folderMap = new Map();
        const rootFolders = [];

        // First pass: create folder objects
        folders.forEach(folder => {
            folderMap.set(folder.id, {
                ...folder,
                children: [],
                level: 0
            });
        });

        // Second pass: build parent-child relationships
        folders.forEach(folder => {
            const folderObj = folderMap.get(folder.id);
            if (folder.parent_id) {
                const parent = folderMap.get(folder.parent_id);
                if (parent) {
                    parent.children.push(folderObj);
                } else {
                    rootFolders.push(folderObj);
                }
            } else {
                rootFolders.push(folderObj);
            }
        });

        // Third pass: calculate levels correctly
        const calculateLevels = (folders, level = 0) => {
            folders.forEach(folder => {
                folder.level = level;
                if (folder.children.length > 0) {
                    calculateLevels(folder.children, level + 1);
                }
            });
        };
        
        calculateLevels(rootFolders);

        return rootFolders;
    }

    generateTreeHTML() {
        let html = `
            <div class="folder-tree-selector">
                <div class="folder-tree-item ${this.selectedFolderId === null || this.selectedFolderId === '' ? 'selected' : ''}" 
                     onclick="folderTreeSelector.selectFolder('')" 
                     data-folder-id="">
                    <span class="folder-icon">🏠</span>
                    <span class="folder-name">Home (No Folder)</span>
                </div>
        `;

        html += this.renderFolderTree(this.rootFolders);
        html += '</div>';

        return html;
    }

    renderFolderTree(folders, level = 0) {
        let html = '';
        
        folders.forEach(folder => {
            const isSelected = this.selectedFolderId === folder.id;
            const hasChildren = folder.children.length > 0;
            const indent = level * 20;

            html += `
                <div class="folder-tree-item ${isSelected ? 'selected' : ''}" 
                     onclick="folderTreeSelector.selectFolder(${folder.id})" 
                     data-folder-id="${folder.id}"
                     style="padding-left: ${indent + 12}px;">
                    ${hasChildren ? 
                        `<span class="folder-toggle" onclick="event.stopPropagation(); folderTreeSelector.toggleFolder(${folder.id})">▶</span>` : 
                        '<span class="folder-spacer"></span>'
                    }
                    <span class="folder-icon">📁</span>
                    <span class="folder-name">${folder.name}</span>
                </div>
            `;

            if (hasChildren) {
                html += `<div class="folder-children" data-parent="${folder.id}" style="display: none;">`;
                html += this.renderFolderTree(folder.children, level + 1);
                html += '</div>';
            }
        });

        return html;
    }

    selectFolder(folderId) {
        // Remove previous selection
        document.querySelectorAll('.folder-tree-item.selected').forEach(item => {
            item.classList.remove('selected');
        });

        // Add selection to current item
        const targetItem = document.querySelector(`[data-folder-id="${folderId || ''}"]`);
        if (targetItem) {
            targetItem.classList.add('selected');
        }

        this.selectedFolderId = folderId;
    }

    toggleFolder(folderId) {
        const toggle = document.querySelector(`[data-folder-id="${folderId}"] .folder-toggle`);
        const childrenContainer = document.querySelector(`[data-parent="${folderId}"]`);
        
        if (toggle && childrenContainer) {
            const isExpanded = childrenContainer.style.display !== 'none';
            
            if (isExpanded) {
                childrenContainer.style.display = 'none';
                toggle.textContent = '▶';
            } else {
                childrenContainer.style.display = 'block';
                toggle.textContent = '▼';
            }
        }
    }

    getSelectedFolderId() {
        return this.selectedFolderId === '' ? null : this.selectedFolderId;
    }

    getCSS() {
        return `
            <style>
                .folder-tree-selector {
                    max-height: 300px;
                    overflow-y: auto;
                    border: 1px solid var(--border-primary);
                    border-radius: 8px;
                    background: var(--bg-primary);
                    margin-bottom: 16px;
                }

                .folder-tree-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 10px 12px;
                    cursor: pointer;
                    transition: background 0.2s;
                    border-bottom: 1px solid var(--border-secondary);
                }

                .folder-tree-item:last-child {
                    border-bottom: none;
                }

                .folder-tree-item:hover {
                    background: var(--bg-tertiary);
                }

                .folder-tree-item.selected {
                    background: var(--accent-light);
                    color: var(--accent-primary);
                    font-weight: 500;
                }

                .folder-toggle {
                    width: 16px;
                    height: 16px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 12px;
                    cursor: pointer;
                    color: var(--text-secondary);
                    transition: transform 0.2s;
                }

                .folder-spacer {
                    width: 16px;
                    height: 16px;
                }

                .folder-icon {
                    font-size: 16px;
                    flex-shrink: 0;
                }

                .folder-name {
                    flex: 1;
                    color: var(--text-primary);
                    font-size: 14px;
                }

                .folder-tree-item.selected .folder-name {
                    color: var(--accent-primary);
                }

                .folder-children {
                    border-left: 2px solid var(--border-secondary);
                    margin-left: 20px;
                }
            </style>
        `;
    }
}

// Global functions for easy access
function createFolderTreeDialog(title, folders, currentFolderId, onMove) {
    // Create the tree selector
    window.folderTreeSelector = new FolderTreeSelector(folders, currentFolderId);
    
    const dialog = document.createElement('div');
    dialog.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 10000;';
    
    dialog.innerHTML = `
        ${window.folderTreeSelector.getCSS()}
        <div style="background: var(--bg-secondary); padding: 24px; border-radius: 12px; max-width: 500px; width: 90%; max-height: 80vh; overflow: hidden; display: flex; flex-direction: column;">
            <h3 style="margin: 0 0 16px 0; color: var(--text-primary);">${title}</h3>
            <div style="flex: 1; overflow: hidden;">
                ${window.folderTreeSelector.generateTreeHTML()}
            </div>
            <div style="display: flex; gap: 12px; margin-top: 16px;">
                <button id="move-confirm-btn" style="flex: 1; padding: 10px; background: var(--accent-primary); color: white; border: none; border-radius: 8px; cursor: pointer;">Move</button>
                <button id="move-cancel-btn" style="flex: 1; padding: 10px; background: var(--bg-tertiary); color: var(--text-primary); border: 1px solid var(--border-primary); border-radius: 8px; cursor: pointer;">Cancel</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(dialog);
    
    // Add event listeners
    dialog.querySelector('#move-confirm-btn').addEventListener('click', () => {
        const selectedFolderId = window.folderTreeSelector.getSelectedFolderId();
        onMove(selectedFolderId);
        document.body.removeChild(dialog);
    });
    
    dialog.querySelector('#move-cancel-btn').addEventListener('click', () => {
        document.body.removeChild(dialog);
    });
    
    // Close on backdrop click
    dialog.addEventListener('click', (e) => {
        if (e.target === dialog) {
            document.body.removeChild(dialog);
        }
    });
    
    // Auto-expand folders to show currently selected folder
    if (currentFolderId) {
        setTimeout(() => {
            expandToFolder(currentFolderId, folders);
        }, 100);
    }
}

function expandToFolder(targetFolderId, folders) {
    // Find the path to the target folder
    const findParentPath = (folderId, path = []) => {
        const folder = folders.find(f => f.id === folderId);
        if (!folder) return null;
        
        path.unshift(folder.id);
        
        if (folder.parent_id) {
            return findParentPath(folder.parent_id, path);
        }
        
        return path;
    };
    
    const path = findParentPath(targetFolderId);
    if (path) {
        // Expand all folders in the path
        path.slice(0, -1).forEach(folderId => {
            window.folderTreeSelector.toggleFolder(folderId);
        });
    }
}

// Export for module systems if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { FolderTreeSelector, createFolderTreeDialog };
}