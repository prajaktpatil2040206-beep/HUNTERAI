/**
 * HunterAI — Sidebar Navigation
 * Manages projects, hunts, and sidebar state.
 */

const Sidebar = {
    collapsed: false,

    init() {
        this.loadProjects();
        this.loadRecentHunts();
    },

    toggle() {
        const sidebar = document.getElementById('sidebar');
        this.collapsed = !this.collapsed;
        sidebar.classList.toggle('collapsed', this.collapsed);
    },

    async loadProjects() {
        try {
            const resp = await fetch('/api/projects');
            const data = await resp.json();
            this.renderProjects(data.projects || []);
        } catch (e) {
            console.error('Failed to load projects:', e);
        }
    },

    renderProjects(projects) {
        const container = document.getElementById('projects-list');
        if (projects.length === 0) {
            container.innerHTML = '<div class="empty-state">No projects yet</div>';
            return;
        }

        container.innerHTML = projects.map(p => `
            <div class="project-item" onclick="Sidebar.selectProject('${p._id}')" data-id="${p._id}">
                <span class="project-icon">📁</span>
                <span class="project-name">${this.escapeHtml(p.name)}</span>
                <span style="font-size:11px;color:var(--text-muted)">${p.hunt_count || 0}</span>
            </div>
        `).join('');

        // Also populate the hunt creation dropdown
        const select = document.getElementById('hunt-project');
        if (select) {
            select.innerHTML = '<option value="">— No Project —</option>' +
                projects.map(p => `<option value="${p._id}">${this.escapeHtml(p.name)}</option>`).join('');
        }
    },

    async loadRecentHunts() {
        try {
            const resp = await fetch('/api/recent-hunts');
            const data = await resp.json();
            this.renderRecentHunts(data.hunts || []);
        } catch (e) {
            console.error('Failed to load recent hunts:', e);
        }
    },

    renderRecentHunts(hunts) {
        const container = document.getElementById('recent-hunts-list');
        if (hunts.length === 0) {
            container.innerHTML = '<div class="empty-state">No hunts yet</div>';
            return;
        }

        container.innerHTML = hunts.map(h => `
            <div class="hunt-item ${App.currentHuntId === h._id ? 'active' : ''}" 
                 onclick="Sidebar.selectHunt('${h._id}')" data-id="${h._id}">
                <span class="hunt-status ${h.status || 'idle'}"></span>
                <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${this.escapeHtml(h.name)}</span>
            </div>
        `).join('');
    },

    selectProject(projectId) {
        // Highlight
        document.querySelectorAll('.project-item').forEach(el => el.classList.remove('active'));
        document.querySelector(`.project-item[data-id="${projectId}"]`)?.classList.add('active');
        // Could load project-specific hunts here
    },

    selectHunt(huntId) {
        App.switchToHunt(huntId);
        // Highlight
        document.querySelectorAll('.hunt-item').forEach(el => el.classList.remove('active'));
        document.querySelector(`.hunt-item[data-id="${huntId}"]`)?.classList.add('active');
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
};

// Global functions for HTML onclick
function toggleSidebar() {
    Sidebar.toggle();
}
