/**
 * HunterAI — Chat Interface Logic (v2)
 * Autonomous/Feedback modes, Accept/Accept All/Reject buttons,
 * markdown rendering, file upload, voice input.
 */

const Chat = {
    currentHuntId: null,
    messages: [],
    isProcessing: false,
    voiceActive: false,
    recognition: null,
    execMode: 'feedback', // 'autonomous' or 'feedback'

    init() {
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                gfm: true,
                breaks: true,
                highlight: function(code, lang) {
                    if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                        return hljs.highlight(code, { language: lang }).value;
                    }
                    return code;
                }
            });
        }
        this.initVoice();
    },

    setHunt(huntId) {
        this.currentHuntId = huntId;
        this.messages = [];
        this.loadHistory(huntId);
    },

    async loadHistory(huntId) {
        try {
            const resp = await fetch(`/api/chat/history/${huntId}`);
            const data = await resp.json();
            this.messages = data.messages || [];
            this.renderAllMessages();

            // Show any pending actions
            if (data.pending_actions && data.pending_actions.length > 0) {
                this.renderPendingActions(data.pending_actions);
            }
        } catch (e) {
            console.error('Failed to load chat history:', e);
        }
    },

    renderAllMessages() {
        const container = document.getElementById('chat-messages');
        container.innerHTML = '';
        this.messages.forEach(msg => {
            container.appendChild(this.createMessageElement(msg));
        });
        this.scrollToBottom();
    },

    createMessageElement(msg) {
        const wrapper = document.createElement('div');
        wrapper.className = `message ${msg.role}`;
        wrapper.dataset.messageId = msg.id || '';

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';

        if (msg.role === 'user') {
            avatar.textContent = '👤';
        } else if (msg.role === 'assistant') {
            avatar.textContent = '🛡';
        } else {
            avatar.textContent = '⚡';
        }

        const content = document.createElement('div');
        content.className = 'message-content';

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        if (msg.role === 'assistant' && typeof marked !== 'undefined') {
            bubble.innerHTML = marked.parse(msg.content || '');
            this.addCommandButtons(bubble);
        } else if (msg.role === 'system' && typeof marked !== 'undefined') {
            bubble.innerHTML = marked.parse(msg.content || '');
        } else {
            bubble.textContent = msg.content || '';
        }

        content.appendChild(bubble);

        if (msg.timestamp) {
            const time = document.createElement('div');
            time.style.cssText = 'font-size:11px;color:var(--text-muted);margin-top:4px;padding:0 4px;';
            time.textContent = new Date(msg.timestamp).toLocaleTimeString();
            content.appendChild(time);
        }

        wrapper.appendChild(avatar);
        wrapper.appendChild(content);
        return wrapper;
    },

    addCommandButtons(bubble) {
        const pres = bubble.querySelectorAll('pre code');
        pres.forEach(code => {
            const pre = code.parentElement;
            const text = code.textContent.trim();
            if (text && text.length < 1000) {
                const btnBar = document.createElement('div');
                btnBar.className = 'code-action-bar';
                btnBar.innerHTML = `
                    <button class="cmd-btn" onclick="Chat.executeCommand(\`${text.replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`)">▶ Execute</button>
                    <button class="cmd-btn" style="opacity:0.6" onclick="navigator.clipboard.writeText(\`${text.replace(/`/g, '\\`').replace(/\$/g, '\\$')}\`);showToast('Copied!','success')">📋 Copy</button>
                `;
                pre.appendChild(btnBar);
            }
        });
    },

    async sendMessage(message) {
        if (!message.trim() || this.isProcessing) return;
        if (!this.currentHuntId) {
            showToast('Please start a hunt first.', 'error');
            return;
        }

        this.isProcessing = true;
        this.showTyping();
        this.updateSendButton(true);

        // Add user message
        const userMsg = {
            id: Date.now().toString(36),
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        };
        this.messages.push(userMsg);
        const container = document.getElementById('chat-messages');
        container.appendChild(this.createMessageElement(userMsg));
        this.scrollToBottom();

        const mode = document.getElementById('mode-selector')?.value || 'intermediate';

        try {
            const resp = await fetch('/api/chat/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    hunt_id: this.currentHuntId,
                    message: message,
                    mode: mode,
                    exec_mode: this.execMode
                })
            });
            const data = await resp.json();

            this.hideTyping();

            if (data.success && data.message) {
                this.messages.push(data.message);
                container.appendChild(this.createMessageElement(data.message));

                // Handle actions based on exec mode
                if (data.exec_mode === 'autonomous' && data.executed_actions?.length > 0) {
                    // Commands were auto-executed
                    this.showAutoExecutedNotice(data.executed_actions);
                } else if (data.pending_actions?.length > 0) {
                    // Feedback mode — show approval buttons
                    this.renderPendingActions(data.pending_actions);
                }
            } else if (data.error) {
                this.addSystemMessage(`⚠️ ${data.error}`);
            }
        } catch (e) {
            this.hideTyping();
            this.addSystemMessage(`⚠️ Network error: ${e.message}`);
        }

        this.isProcessing = false;
        this.updateSendButton(false);
        this.scrollToBottom();
    },

    // ─── ACTION APPROVAL SYSTEM (Like Antigravity) ──────────

    renderPendingActions(actions) {
        if (!actions || actions.length === 0) return;

        const container = document.getElementById('chat-messages');
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'message system';
        actionsDiv.id = 'pending-actions-container';

        let actionsHtml = actions.map((a, i) => `
            <div class="action-item" id="action-${a.action_id || a._id}">
                <div class="action-command">
                    <span class="action-number">${i + 1}</span>
                    <code>${this.escapeHtml(a.command)}</code>
                </div>
                <div class="action-buttons">
                    <button class="action-btn accept" onclick="Chat.acceptAction('${a.action_id || a._id}', this)" title="Execute this command">
                        ✓ Accept
                    </button>
                    <button class="action-btn reject" onclick="Chat.rejectAction('${a.action_id || a._id}', this)" title="Skip this command">
                        ✗ Reject
                    </button>
                </div>
            </div>
        `).join('');

        actionsDiv.innerHTML = `
            <div class="message-avatar">⚡</div>
            <div class="message-content">
                <div class="actions-container">
                    <div class="actions-header">
                        <span class="actions-title">🔐 ${actions.length} Command${actions.length > 1 ? 's' : ''} Awaiting Approval</span>
                        <div class="actions-header-buttons">
                            <button class="action-btn accept-all" onclick="Chat.acceptAllActions()">
                                ✓✓ Accept All
                            </button>
                            <button class="action-btn reject-all" onclick="Chat.rejectAllActions()">
                                ✗ Reject All
                            </button>
                        </div>
                    </div>
                    <div class="actions-list">
                        ${actionsHtml}
                    </div>
                </div>
            </div>
        `;

        container.appendChild(actionsDiv);
        this.scrollToBottom();
    },

    async acceptAction(actionId, btnEl) {
        try {
            const resp = await fetch('/api/chat/actions/accept', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action_id: actionId })
            });
            const data = await resp.json();
            if (data.success) {
                const item = document.getElementById(`action-${actionId}`);
                if (item) {
                    item.classList.add('accepted');
                    item.querySelector('.action-buttons').innerHTML = '<span class="action-status accepted">✓ Executing</span>';
                }
                showToast(`Executing command...`, 'success');
            }
        } catch (e) {
            showToast('Failed to execute', 'error');
        }
    },

    async rejectAction(actionId, btnEl) {
        try {
            await fetch('/api/chat/actions/reject', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action_id: actionId })
            });
            const item = document.getElementById(`action-${actionId}`);
            if (item) {
                item.classList.add('rejected');
                item.querySelector('.action-buttons').innerHTML = '<span class="action-status rejected">✗ Skipped</span>';
            }
        } catch (e) {
            showToast('Failed to reject', 'error');
        }
    },

    async acceptAllActions() {
        if (!this.currentHuntId) return;
        try {
            const resp = await fetch('/api/chat/actions/accept-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hunt_id: this.currentHuntId })
            });
            const data = await resp.json();
            if (data.success) {
                document.querySelectorAll('.action-item').forEach(item => {
                    if (!item.classList.contains('rejected')) {
                        item.classList.add('accepted');
                        const btns = item.querySelector('.action-buttons');
                        if (btns) btns.innerHTML = '<span class="action-status accepted">✓ Executing</span>';
                    }
                });
                showToast(`Executing ${data.executed_count} commands...`, 'success');
            }
        } catch (e) {
            showToast('Failed to accept all', 'error');
        }
    },

    async rejectAllActions() {
        if (!this.currentHuntId) return;
        try {
            await fetch('/api/chat/actions/reject-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hunt_id: this.currentHuntId })
            });
            document.querySelectorAll('.action-item').forEach(item => {
                item.classList.add('rejected');
                const btns = item.querySelector('.action-buttons');
                if (btns) btns.innerHTML = '<span class="action-status rejected">✗ Skipped</span>';
            });
            showToast('All commands rejected', 'info');
        } catch (e) {
            showToast('Failed to reject all', 'error');
        }
    },

    showAutoExecutedNotice(executedActions) {
        const count = executedActions.length;
        this.addSystemMessage(`🤖 **Autonomous Mode**: ${count} command${count > 1 ? 's' : ''} auto-executed. Watch the terminal panel below for output.`);
    },

    // ─── Direct command execution ───────────────────────────
    async executeCommand(command) {
        if (!this.currentHuntId) {
            showToast('No active hunt', 'error');
            return;
        }
        HunterSocket.execute(command, this.currentHuntId);
        this.addSystemMessage(`⚡ Executing: \`${command}\``);
        showToast(`Executing command...`, 'info');
    },

    // ─── AUTO-FIX SELF-HEALING LOOP ────────────────────────
    // When a command fails, automatically send error to AI,
    // get a corrected command, and execute it. Retry up to MAX times.

    autoFixRetries: {},       // { process_id: retry_count }
    MAX_AUTO_FIX_RETRIES: 5,

    /**
     * Called when terminal_complete fires with an error.
     * Triggers the auto-fix loop.
     */
    async handleCommandError(processId, command, huntId) {
        // Check retry count
        const key = command;  // Track retries by command intent
        if (!this.autoFixRetries[key]) this.autoFixRetries[key] = 0;
        this.autoFixRetries[key]++;

        if (this.autoFixRetries[key] > this.MAX_AUTO_FIX_RETRIES) {
            this.addSystemMessage(`🛑 Auto-fix gave up after ${this.MAX_AUTO_FIX_RETRIES} retries for: \`${command}\`. Try a different approach.`);
            delete this.autoFixRetries[key];
            return;
        }

        this.addSystemMessage(`🔧 Auto-fix attempt ${this.autoFixRetries[key]}/${this.MAX_AUTO_FIX_RETRIES} — Analyzing error...`);
        this.showTyping();

        try {
            const mode = document.getElementById('mode-selector')?.value || 'intermediate';
            const resp = await fetch('/api/chat/auto-fix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    hunt_id: huntId || this.currentHuntId,
                    process_id: processId,
                    mode: mode,
                    exec_mode: 'autonomous'  // Always auto-execute the fix
                })
            });
            const data = await resp.json();
            this.hideTyping();

            if (data.success && data.message) {
                // Show the AI's fix response
                this.messages.push(data.message);
                const container = document.getElementById('chat-messages');
                container.appendChild(this.createMessageElement(data.message));

                // If fix commands were auto-executed, show notice
                if (data.executed_actions?.length > 0) {
                    this.addSystemMessage(`⚡ Auto-fix executing: \`${data.executed_actions.map(a => a.command).join('; ')}\``);
                } else if (data.fix_commands?.length > 0) {
                    // Commands extracted but not yet executed — execute them now
                    for (const cmd of data.fix_commands) {
                        HunterSocket.execute(cmd, huntId || this.currentHuntId);
                        this.addSystemMessage(`⚡ Auto-fix executing: \`${cmd}\``);
                    }
                } else {
                    this.addSystemMessage(`ℹ️ AI analyzed the error but no executable fix was generated. Try rephrasing your request.`);
                    delete this.autoFixRetries[key];
                }
            } else {
                this.addSystemMessage(`⚠️ Auto-fix failed: ${data.error || 'Unknown error'}`);
                delete this.autoFixRetries[key];
            }
        } catch (e) {
            this.hideTyping();
            this.addSystemMessage(`⚠️ Auto-fix network error: ${e.message}`);
            delete this.autoFixRetries[key];
        }
        this.scrollToBottom();
    },

    // ─── Helpers ────────────────────────────────────────────

    addSystemMessage(content) {
        const container = document.getElementById('chat-messages');
        const msg = {
            id: Date.now().toString(36),
            role: 'system',
            content: content,
            timestamp: new Date().toISOString()
        };
        this.messages.push(msg);
        container.appendChild(this.createMessageElement(msg));
        this.scrollToBottom();
    },

    showTyping() {
        document.getElementById('typing-indicator')?.classList.remove('hidden');
        this.scrollToBottom();
    },

    hideTyping() {
        document.getElementById('typing-indicator')?.classList.add('hidden');
    },

    updateSendButton(loading) {
        const btn = document.getElementById('btn-send');
        if (btn) {
            btn.disabled = loading;
            btn.style.opacity = loading ? '0.4' : '1';
        }
    },

    scrollToBottom() {
        const chatArea = document.getElementById('chat-area');
        if (chatArea) {
            setTimeout(() => { chatArea.scrollTop = chatArea.scrollHeight; }, 50);
        }
    },

    setExecMode(mode) {
        this.execMode = mode;
        const label = document.getElementById('exec-mode-label');
        if (label) {
            label.textContent = mode === 'autonomous' ? '🤖 Autonomous' : '🔐 Feedback';
            label.className = `exec-mode-label ${mode}`;
        }
    },

    // ─── Voice Input ────────────────────────────────────────

    initVoice() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SR();
            this.recognition.continuous = false;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onresult = (event) => {
                const input = document.getElementById('chat-input');
                let transcript = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    transcript += event.results[i][0].transcript;
                }
                input.value = transcript;
                autoResizeInput(input);
            };

            this.recognition.onend = () => {
                this.voiceActive = false;
                document.getElementById('btn-voice')?.classList.remove('active');
                document.getElementById('input-status').textContent = '';
            };

            this.recognition.onerror = () => {
                this.voiceActive = false;
                document.getElementById('btn-voice')?.classList.remove('active');
                document.getElementById('input-status').textContent = '';
            };
        }
    },

    toggleVoice() {
        if (!this.recognition) {
            showToast('Voice not supported in this browser.', 'error');
            return;
        }
        if (this.voiceActive) {
            this.recognition.stop();
            this.voiceActive = false;
            document.getElementById('btn-voice')?.classList.remove('active');
            document.getElementById('input-status').textContent = '';
        } else {
            this.recognition.start();
            this.voiceActive = true;
            document.getElementById('btn-voice')?.classList.add('active');
            document.getElementById('input-status').textContent = '🎙 Listening...';
        }
    },

    // ─── File Upload ────────────────────────────────────────

    async uploadFile(file) {
        if (!this.currentHuntId) {
            showToast('Please start a hunt first.', 'error');
            return;
        }
        const formData = new FormData();
        formData.append('file', file);
        formData.append('hunt_id', this.currentHuntId);

        try {
            const resp = await fetch('/api/chat/upload', { method: 'POST', body: formData });
            const data = await resp.json();
            if (data.success) {
                showToast(`Uploaded: ${file.name}`, 'success');
                this.loadHistory(this.currentHuntId);
            }
        } catch (e) {
            showToast(`Upload failed: ${e.message}`, 'error');
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
};

// ─── Global handlers from HTML ──────────────────────────────

function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (message) {
        Chat.sendMessage(message);
        input.value = '';
        input.style.height = 'auto';
    }
}

function handleInputKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function autoResizeInput(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 150) + 'px';
}

function toggleVoiceInput() { Chat.toggleVoice(); }
function triggerFileUpload() { document.getElementById('file-input')?.click(); }
function handleFileUpload(input) {
    if (input.files) {
        Array.from(input.files).forEach(file => Chat.uploadFile(file));
        input.value = '';
    }
}

function toggleExecMode() {
    const newMode = Chat.execMode === 'autonomous' ? 'feedback' : 'autonomous';
    Chat.setExecMode(newMode);
    showToast(`Switched to ${newMode} mode`, 'info');
}
