/**
 * HunterAI — Terminal Panel Controller
 * Renders real-time command output from WebSocket into the terminal panel.
 */

const Terminal = {
    outputEl: null,
    processCount: 0,
    autoScroll: true,
    collapsed: false,

    init() {
        this.outputEl = document.getElementById('terminal-output');
        this.processCountEl = document.getElementById('terminal-process-count');

        // Listen for terminal events from WebSocket
        HunterSocket.on('terminal_command', (data) => this.onCommand(data));
        HunterSocket.on('terminal_output', (data) => this.onOutput(data));
        HunterSocket.on('terminal_complete', (data) => this.onComplete(data));
        HunterSocket.on('terminal_error', (data) => this.onError(data));
        HunterSocket.on('terminal_started', (data) => this.onStarted(data));
    },

    onCommand(data) {
        const line = document.createElement('div');
        line.className = 'terminal-line terminal-command';
        line.dataset.processId = data.process_id;
        line.innerHTML = `<span class="terminal-prompt">$ </span><span>${this.escapeHtml(data.command)}</span>`;
        this.outputEl.appendChild(line);
        this.processCount++;
        this.updateProcessCount();
        this.scrollToBottom();

        // Ensure terminal is visible
        if (this.collapsed) {
            this.expand();
        }
    },

    onOutput(data) {
        const line = document.createElement('div');
        const type = data.type === 'stderr' ? 'terminal-stderr' : 'terminal-stdout';
        line.className = `terminal-line ${type}`;
        line.dataset.processId = data.process_id;
        line.innerHTML = `<span class="terminal-prompt">${data.type === 'stderr' ? '!' : '›'}</span><span>${this.escapeHtml(data.data)}</span>`;
        this.outputEl.appendChild(line);
        this.scrollToBottom();
    },

    onComplete(data) {
        const line = document.createElement('div');
        const isError = data.exit_code !== 0;
        line.className = `terminal-line terminal-exit ${isError ? 'error' : ''}`;
        line.dataset.processId = data.process_id;
        line.innerHTML = `<span class="terminal-prompt">${isError ? '✗' : '✓'}</span><span>Process exited with code ${data.exit_code} [${data.status}]</span>`;
        this.outputEl.appendChild(line);
        this.processCount = Math.max(0, this.processCount - 1);
        this.updateProcessCount();
        this.scrollToBottom();
    },

    onError(data) {
        const line = document.createElement('div');
        line.className = 'terminal-line terminal-stderr';
        line.innerHTML = `<span class="terminal-prompt">✗</span><span>Error: ${this.escapeHtml(data.error || 'Unknown error')}</span>`;
        this.outputEl.appendChild(line);
        this.scrollToBottom();
    },

    onStarted(data) {
        // We already handle this in onCommand — this is the WebSocket ack
    },

    scrollToBottom() {
        if (this.autoScroll && this.outputEl) {
            this.outputEl.scrollTop = this.outputEl.scrollHeight;
        }
    },

    updateProcessCount() {
        if (this.processCountEl) {
            this.processCountEl.textContent = `${this.processCount} process${this.processCount !== 1 ? 'es' : ''}`;
        }
    },

    addSystemLine(text) {
        const line = document.createElement('div');
        line.className = 'terminal-line terminal-system';
        line.innerHTML = `<span class="terminal-prompt">⚡</span><span>${this.escapeHtml(text)}</span>`;
        this.outputEl.appendChild(line);
        this.scrollToBottom();
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    expand() {
        const panel = document.getElementById('terminal-panel');
        panel.classList.remove('collapsed');
        panel.classList.add('expanded');
        this.collapsed = false;
    },

    collapse() {
        const panel = document.getElementById('terminal-panel');
        panel.classList.add('collapsed');
        panel.classList.remove('expanded');
        this.collapsed = true;
    },

    reset() {
        const panel = document.getElementById('terminal-panel');
        panel.classList.remove('collapsed', 'expanded');
        this.collapsed = false;
    }
};

// Global functions for HTML onclick
function clearTerminal() {
    const el = document.getElementById('terminal-output');
    el.innerHTML = '';
    Terminal.addSystemLine('Terminal cleared.');
}

function toggleTerminal() {
    const panel = document.getElementById('terminal-panel');
    if (panel.classList.contains('collapsed')) {
        Terminal.reset();
    } else if (panel.classList.contains('expanded')) {
        Terminal.reset();
    } else {
        Terminal.expand();
    }
}
