/**
 * HunterAI — WebSocket Connection Manager
 * Handles Socket.IO connection for real-time terminal + chat streaming.
 */

const HunterSocket = {
    socket: null,
    connected: false,
    callbacks: {},

    init() {
        this.socket = io('/terminal', {
            transports: ['websocket', 'polling'],
            reconnectionAttempts: 10,
            reconnectionDelay: 2000
        });

        this.socket.on('connect', () => {
            this.connected = true;
            this.updateStatus(true);
            console.log('[HunterAI] WebSocket connected');
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            this.updateStatus(false);
            console.log('[HunterAI] WebSocket disconnected');
        });

        this.socket.on('connect_error', (err) => {
            this.connected = false;
            this.updateStatus(false);
            console.warn('[HunterAI] WebSocket error:', err.message);
        });

        // Terminal events
        this.socket.on('terminal_status', (data) => {
            this.emit('terminal_status', data);
        });

        this.socket.on('terminal_command', (data) => {
            this.emit('terminal_command', data);
        });

        this.socket.on('terminal_output', (data) => {
            this.emit('terminal_output', data);
        });

        this.socket.on('terminal_complete', (data) => {
            this.emit('terminal_complete', data);
        });

        this.socket.on('terminal_error', (data) => {
            this.emit('terminal_error', data);
        });

        this.socket.on('terminal_killed', (data) => {
            this.emit('terminal_killed', data);
        });

        this.socket.on('terminal_started', (data) => {
            this.emit('terminal_started', data);
        });
    },

    updateStatus(connected) {
        const el = document.getElementById('connection-status');
        if (el) {
            el.classList.toggle('connected', connected);
        }
    },

    // Execute command via WebSocket
    execute(command, huntId, cwd) {
        if (this.socket) {
            this.socket.emit('execute', { command, hunt_id: huntId, cwd });
        }
    },

    // Kill a process
    kill(processId) {
        if (this.socket) {
            this.socket.emit('kill', { process_id: processId });
        }
    },

    // Event subscription
    on(event, callback) {
        if (!this.callbacks[event]) {
            this.callbacks[event] = [];
        }
        this.callbacks[event].push(callback);
    },

    emit(event, data) {
        const cbs = this.callbacks[event] || [];
        cbs.forEach(cb => cb(data));
    },

    off(event) {
        delete this.callbacks[event];
    }
};
