/**
 * HunterAI — Main Application Controller
 * Global state, routing, modals, initialization.
 */

const App = {
    currentProjectId: null,
    currentHuntId: null,
    currentMode: 'intermediate',
    firstRun: true,

    async init() {
        console.log('[HunterAI] Initializing...');

        // Initialize all modules
        HunterSocket.init();
        Terminal.init();
        Chat.init();
        Sidebar.init();
        await Models.init();

        // Check API status
        await this.checkStatus();

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'n') { e.preventDefault(); showNewHuntModal(); }
            if (e.ctrlKey && e.key === 'm') { e.preventDefault(); showModelModal(); }
            if (e.key === 'Escape') { this.closeAllModals(); }
        });

        console.log('[HunterAI] Ready.');
    },

    async checkStatus() {
        try {
            const resp = await fetch('/api/status');
            const data = await resp.json();
            this.firstRun = data.first_run;

            if (this.firstRun) {
                this.showFirstRunWelcome();
            }
        } catch (e) {
            console.error('Failed to check status:', e);
        }
    },

    showFirstRunWelcome() {
        // First run — the welcome screen already shows, user needs to set up a model
    },

    // Switch to a specific hunt
    async switchToHunt(huntId) {
        try {
            const resp = await fetch(`/api/hunts/${huntId}`);
            const data = await resp.json();
            if (!data.hunt) return;

            const hunt = data.hunt;
            this.currentHuntId = huntId;
            this.currentProjectId = hunt.project_id;

            // Update UI
            document.getElementById('current-hunt-title').textContent = hunt.name;
            document.getElementById('hunt-status-badge').textContent = hunt.status;
            document.getElementById('hunt-status-badge').classList.remove('hidden');
            document.getElementById('mode-selector').value = hunt.mode || 'intermediate';

            // Show chat, hide welcome
            document.getElementById('welcome-screen').classList.add('hidden');
            document.getElementById('chat-messages').classList.remove('hidden');

            // Load chat history
            Chat.setHunt(huntId);

            showToast(`Switched to: ${hunt.name}`, 'info');
        } catch (e) {
            showToast('Failed to load hunt', 'error');
        }
    },

    closeAllModals() {
        document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
    }
};

// ═══ GLOBAL FUNCTIONS (called from HTML onclick) ═══

function openModal(id) {
    document.getElementById(id)?.classList.remove('hidden');
}

function closeModal(id) {
    document.getElementById(id)?.classList.add('hidden');
}

function showNewHuntModal() {
    Sidebar.loadProjects(); // refresh project dropdown
    openModal('modal-new-hunt');
    document.getElementById('hunt-name')?.focus();
}

function showNewProjectModal() {
    openModal('modal-new-project');
    document.getElementById('project-name')?.focus();
}

function showSettingsModal() {
    openModal('modal-settings');
}

function showAssetsPanel() {
    showToast('Assets panel — coming soon', 'info');
}

function showToolsPanel() {
    openModal('modal-tools');
}

function changeMode(mode) {
    App.currentMode = mode;
}

// ─── Create Project ───
async function createProject() {
    const name = document.getElementById('project-name')?.value.trim();
    const desc = document.getElementById('project-description')?.value.trim();

    if (!name) {
        showToast('Project name is required', 'error');
        return;
    }

    try {
        const resp = await fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: desc })
        });
        const data = await resp.json();

        if (data.success) {
            showToast(`Project created: ${name}`, 'success');
            closeModal('modal-new-project');
            Sidebar.loadProjects();
        }
    } catch (e) {
        showToast('Failed to create project', 'error');
    }
}

// ─── Create Hunt ───
async function createHunt() {
    const name = document.getElementById('hunt-name')?.value.trim();
    const target = document.getElementById('hunt-target')?.value.trim();
    const type = document.getElementById('hunt-type')?.value;
    const desc = document.getElementById('hunt-description')?.value.trim();
    const projectId = document.getElementById('hunt-project')?.value;
    const mode = document.querySelector('input[name="hunt-mode"]:checked')?.value || 'intermediate';

    if (!name) {
        showToast('Hunt name is required', 'error');
        return;
    }

    try {
        const resp = await fetch('/api/hunts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                target_url: target,
                target_type: type,
                description: desc,
                project_id: projectId || null,
                mode
            })
        });
        const data = await resp.json();

        if (data.success) {
            showToast(`Hunt started: ${name}`, 'success');
            closeModal('modal-new-hunt');

            // Mark first run done
            if (App.firstRun) {
                fetch('/api/first-run-complete', { method: 'POST' });
                App.firstRun = false;
            }

            // Switch to the new hunt
            App.switchToHunt(data.hunt._id);
            Sidebar.loadRecentHunts();
        }
    } catch (e) {
        showToast('Failed to create hunt', 'error');
    }
}

// ─── Tool Scanning ───
async function scanTools() {
    const btn = document.getElementById('btn-scan-tools');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '🔍 Scanning...';
    }

    try {
        const resp = await fetch('/api/tools/scan', { method: 'POST' });
        const data = await resp.json();

        if (data.success) {
            showToast(`Scan complete: ${data.total_installed} tools found`, 'success');
            renderToolsGrid(data.categories, data.total_installed, data.total_known);
        }
    } catch (e) {
        showToast('Tool scan failed', 'error');
    }

    if (btn) {
        btn.disabled = false;
        btn.textContent = '🔍 Scan Tools';
    }
}

function renderToolsGrid(categories, installed, total) {
    const summary = document.getElementById('tools-summary');
    summary.innerHTML = `
        <div class="tools-stat">
            <div class="tools-stat-value">${installed}</div>
            <div class="tools-stat-label">Installed</div>
        </div>
        <div class="tools-stat">
            <div class="tools-stat-value">${total - installed}</div>
            <div class="tools-stat-label">Missing</div>
        </div>
        <div class="tools-stat">
            <div class="tools-stat-value">${total}</div>
            <div class="tools-stat-label">Total Known</div>
        </div>
    `;

    const grid = document.getElementById('tools-grid');
    grid.innerHTML = Object.entries(categories).map(([cat, data]) => `
        <div class="tool-category-card">
            <h4>${cat.replace(/_/g, ' ')}</h4>
            <div class="tool-count">${data.installed} / ${data.installed + data.missing} installed</div>
            <div class="tool-name-list">
                ${(data.installed || []).map(t => `<span class="tool-name-tag installed">${typeof t === 'string' ? t : t.name || t}</span>`).join('')}
                ${(data.missing || []).map(t => `<span class="tool-name-tag missing">${t}</span>`).join('')}
            </div>
        </div>
    `).join('');
}

// ─── Settings ───
async function saveSettings() {
    const scopeMode = document.getElementById('setting-scope-mode')?.value;
    const defaultMode = document.getElementById('setting-default-mode')?.value;
    const port = document.getElementById('setting-port')?.value;

    try {
        await fetch('/api/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                scope: { mode: scopeMode },
                ui: { default_mode: defaultMode },
                server: { port: parseInt(port) || 5000 }
            })
        });
        showToast('Settings saved!', 'success');
        closeModal('modal-settings');
    } catch (e) {
        showToast('Failed to save settings', 'error');
    }
}

async function checkApiStatus() {
    try {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        showToast(`Server status: ${data.status} | v${data.version}`, 'success');
    } catch (e) {
        showToast('Server unreachable', 'error');
    }
}

// ─── Legal ───
function acceptLegal() {
    const checkbox = document.getElementById('legal-checkbox');
    if (checkbox && checkbox.checked) {
        closeModal('modal-legal');
        showToast('Legal disclaimer accepted', 'info');
    }
}
document.getElementById('legal-checkbox')?.addEventListener('change', function() {
    document.getElementById('btn-accept-legal').disabled = !this.checked;
});

// ─── Toast Notifications ───
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 3500);
}

// ═══ INITIALIZE ON DOM READY ═══
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
