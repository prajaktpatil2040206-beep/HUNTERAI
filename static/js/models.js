/**
 * HunterAI — Model Management Modal
 * Provider selection, API key input/test, model switching.
 */

const Models = {
    providers: {},
    selectedProvider: null,
    models: [],

    async init() {
        await this.loadProviders();
        await this.loadModels();
    },

    async loadProviders() {
        try {
            const resp = await fetch('/api/models/providers');
            const data = await resp.json();
            this.providers = {};
            (data.providers || []).forEach(p => { this.providers[p.id] = p; });
        } catch (e) {
            console.error('Failed to load providers:', e);
        }
    },

    async loadModels() {
        try {
            const resp = await fetch('/api/models');
            const data = await resp.json();
            this.models = data.models || [];
            this.renderModels();
            this.updateActiveModelDisplay();
        } catch (e) {
            console.error('Failed to load models:', e);
        }
    },

    renderModels() {
        const container = document.getElementById('models-list');
        if (this.models.length === 0) {
            container.innerHTML = '<div class="empty-state">No models configured yet. Click a provider above to add one.</div>';
            return;
        }

        container.innerHTML = this.models.map(m => `
            <div class="model-item ${m.is_active ? 'active' : ''}" data-id="${m._id}">
                <div class="model-item-info">
                    <div class="model-item-name">${this.escapeHtml(m.display_name || m.model_name)}</div>
                    <div class="model-item-provider">${this.escapeHtml(m.provider_name || m.provider)} · ${m.api_key_masked || '••••'}</div>
                </div>
                <div class="model-item-actions">
                    ${m.is_active
                        ? '<span class="btn-sm active">Active</span>'
                        : `<button class="btn-sm" onclick="Models.setActive('${m._id}')">Use</button>`
                    }
                    <button class="btn-sm danger" onclick="Models.deleteModel('${m._id}')">✕</button>
                </div>
            </div>
        `).join('');
    },

    updateActiveModelDisplay() {
        const active = this.models.find(m => m.is_active);
        const el = document.getElementById('active-model-name');
        if (el) {
            el.textContent = active ? (active.display_name || active.model_name) : 'No Model';
        }
    },

    selectProvider(providerId) {
        this.selectedProvider = providerId;
        const provider = this.providers[providerId];
        if (!provider) return;

        // Show add form, hide provider grid
        document.getElementById('provider-grid').classList.add('hidden');
        document.getElementById('add-model-form').classList.remove('hidden');
        document.getElementById('add-model-provider-name').textContent = `Add ${provider.name} Model`;

        // Populate model dropdown
        const select = document.getElementById('add-model-name');
        select.innerHTML = provider.models.map(m => `<option value="${m}">${m}</option>`).join('');

        // Show custom URL field for custom/ollama
        const customUrlGroup = document.getElementById('custom-url-group');
        customUrlGroup.style.display = (providerId === 'custom' || providerId === 'ollama') ? 'block' : 'none';

        // Clear previous inputs
        document.getElementById('add-model-key').value = '';
        document.getElementById('add-model-display').value = '';
        document.getElementById('add-model-url').value = provider.base_url || '';
        document.getElementById('model-test-result').classList.add('hidden');
    },

    cancelAddModel() {
        document.getElementById('provider-grid').classList.remove('hidden');
        document.getElementById('add-model-form').classList.add('hidden');
        this.selectedProvider = null;
    },

    async testAndAdd() {
        const provider = this.selectedProvider;
        const modelName = document.getElementById('add-model-name').value;
        const apiKey = document.getElementById('add-model-key').value;
        const displayName = document.getElementById('add-model-display').value;
        const customUrl = document.getElementById('add-model-url').value;

        const resultEl = document.getElementById('model-test-result');
        const btn = document.getElementById('btn-test-model');

        if (!apiKey && provider !== 'ollama') {
            resultEl.className = 'model-test-result error';
            resultEl.textContent = 'API key is required.';
            resultEl.classList.remove('hidden');
            return;
        }

        btn.disabled = true;
        document.getElementById('test-model-text').textContent = 'Testing...';

        try {
            // Test first
            const testResp = await fetch('/api/models/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider, api_key: apiKey, model_name: modelName, custom_url: customUrl || undefined })
            });
            const testData = await testResp.json();

            if (testData.success) {
                // Add the model
                const addResp = await fetch('/api/models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider,
                        api_key: apiKey,
                        model_name: modelName,
                        display_name: displayName || `${this.providers[provider]?.name} - ${modelName}`,
                        custom_url: customUrl || undefined
                    })
                });
                const addData = await addResp.json();

                if (addData.success) {
                    resultEl.className = 'model-test-result success';
                    resultEl.textContent = '✓ Connected and added successfully!';
                    resultEl.classList.remove('hidden');
                    showToast('Model added successfully!', 'success');
                    await this.loadModels();
                    setTimeout(() => this.cancelAddModel(), 1500);
                }
            } else {
                resultEl.className = 'model-test-result error';
                resultEl.textContent = `✗ Test failed: ${testData.message}`;
                resultEl.classList.remove('hidden');
            }
        } catch (e) {
            resultEl.className = 'model-test-result error';
            resultEl.textContent = `✗ Error: ${e.message}`;
            resultEl.classList.remove('hidden');
        }

        btn.disabled = false;
        document.getElementById('test-model-text').textContent = 'Test & Add';
    },

    async setActive(modelId) {
        try {
            await fetch(`/api/models/${modelId}/active`, { method: 'PUT' });
            await this.loadModels();
            showToast('Model switched!', 'success');
        } catch (e) {
            showToast('Failed to switch model', 'error');
        }
    },

    async deleteModel(modelId) {
        if (!confirm('Delete this model configuration?')) return;
        try {
            await fetch(`/api/models/${modelId}`, { method: 'DELETE' });
            await this.loadModels();
            showToast('Model removed', 'info');
        } catch (e) {
            showToast('Failed to delete model', 'error');
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
};

// Global functions for HTML onclick
function showModelModal() {
    Models.loadModels();
    openModal('modal-models');
}

function selectProvider(providerId) {
    Models.selectProvider(providerId);
}

function cancelAddModel() {
    Models.cancelAddModel();
}

function testAndAddModel() {
    Models.testAndAdd();
}
