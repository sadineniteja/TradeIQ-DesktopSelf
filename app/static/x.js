// X (Twitter) Integration UI Logic with Signal Analysis

// Global state
let xSignalsData = [];
let xSignalsAutoRefreshInterval = null;
let xSignalsAutoRefreshWasEnabled = false; // Track if auto-refresh was enabled before pausing
let xSignalsLastId = null;
let xExpandedSignals = new Set();
let xModifyOpenSignals = new Set(); // Track which signals have modify section open
let xModifyInputValues = {}; // Store modify input values to preserve across re-renders
let xAnalysisCache = {};
let xReadSignals = new Set(); // Track which high-engagement signals have been read

console.log('[X Module] Script loaded, global state initialized');

// ==================== Configuration Management ====================

async function xLoadConfig() {
    try {
        const response = await fetch('/api/x/config');
        const data = await response.json();
        
        if (data.success && data.config) {
            document.getElementById('x-api-key').value = data.config.api_key || '';
            document.getElementById('x-api-secret').value = data.config.api_secret || '';
            document.getElementById('x-access-token').value = data.config.access_token || '';
            document.getElementById('x-access-token-secret').value = data.config.access_token_secret || '';
            document.getElementById('x-bearer-token').value = data.config.bearer_token || '';
        }
        
        // Load enabled state
        const enabledResponse = await fetch('/api/x/enabled');
        const enabledData = await enabledResponse.json();
        if (enabledData.success) {
            const enabled = enabledData.enabled !== false;
            document.getElementById('x-enabled').checked = enabled;
            updateXStatus(enabled);
        }
    } catch (error) {
        console.error('Error loading X config:', error);
        xShowMessage('Error loading configuration', 'error');
    }
}

async function xSaveConfig() {
    const apiKey = document.getElementById('x-api-key').value.trim();
    const apiSecret = document.getElementById('x-api-secret').value.trim();
    const accessToken = document.getElementById('x-access-token').value.trim();
    const accessTokenSecret = document.getElementById('x-access-token-secret').value.trim();
    const bearerToken = document.getElementById('x-bearer-token').value.trim();
    
    if (!apiKey || !apiSecret || !accessToken || !accessTokenSecret) {
        xShowMessage('Please enter API Key, API Secret, Access Token, and Access Token Secret', 'error');
        return;
    }
    
    try {
        const configData = {
            api_key: apiKey,
            api_secret: apiSecret,
            access_token: accessToken,
            access_token_secret: accessTokenSecret
        };
        
        if (bearerToken) {
            configData.bearer_token = bearerToken;
        }
        
        const response = await fetch('/api/x/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(configData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            xShowMessage('✅ Configuration saved successfully!', 'success');
        } else {
            xShowMessage('❌ Failed to save configuration: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error saving X config:', error);
        xShowMessage('Error saving configuration: ' + error.message, 'error');
    }
}

async function xToggleEnabled() {
    const enabled = document.getElementById('x-enabled').checked;
    
    try {
        const response = await fetch('/api/x/enabled', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateXStatus(enabled);
            xShowMessage(
                enabled ? '✅ X integration enabled' : '⚠️ X integration disabled',
                enabled ? 'success' : 'warning'
            );
        } else {
            document.getElementById('x-enabled').checked = !enabled;
            xShowMessage('Failed to update enabled state: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        document.getElementById('x-enabled').checked = !enabled;
        xShowMessage('Error updating enabled state: ' + error.message, 'error');
    }
}

function updateXStatus(enabled) {
    const statusEl = document.getElementById('x-status');
    if (enabled) {
        statusEl.textContent = '✅ Enabled';
        statusEl.style.background = '#d1fae5';
        statusEl.style.color = '#065f46';
    } else {
        statusEl.textContent = '❌ Disabled';
        statusEl.style.background = '#fee2e2';
        statusEl.style.color = '#991b1b';
    }
}

function xShowMessage(message, type = 'info') {
    const messageDiv = document.getElementById('x-message');
    if (!messageDiv) return;
    
    messageDiv.style.display = 'block';
    messageDiv.className = `result-box ${type} show`;
    messageDiv.textContent = message;
    
    if (type === 'success') {
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 5000);
    }
}

// ==================== Grok API Management ====================

async function grokLoadConfig() {
    try {
        const response = await fetch('/api/grok/config');
        const data = await response.json();
        
        if (data.success && data.config) {
            document.getElementById('grok-api-key').value = data.config.api_key || '';
            
            if (data.config.model) {
                const modelSelect = document.getElementById('grok-model-select');
                const customModelInput = document.getElementById('grok-custom-model');
                
                // Check if model is in the dropdown
                const options = Array.from(modelSelect.options).map(opt => opt.value);
                if (options.includes(data.config.model)) {
                    modelSelect.value = data.config.model;
                } else {
                    // Custom model
                    modelSelect.value = 'custom';
                    customModelInput.value = data.config.model;
                    document.getElementById('grok-custom-model-container').style.display = 'block';
                }
            }
        }
        
        const enabledResponse = await fetch('/api/grok/enabled');
        const enabledData = await enabledResponse.json();
        if (enabledData.success) {
            const enabled = enabledData.enabled !== false;
            document.getElementById('grok-enabled').checked = enabled;
            updateGrokStatus(enabled);
        }
    } catch (error) {
        console.error('Error loading Grok config:', error);
    }
}

function grokModelSelectChanged() {
    const select = document.getElementById('grok-model-select');
    const customContainer = document.getElementById('grok-custom-model-container');
    
    if (select.value === 'custom') {
        customContainer.style.display = 'block';
    } else {
        customContainer.style.display = 'none';
    }
}

async function grokSaveConfig() {
    const apiKey = document.getElementById('grok-api-key').value.trim();
    const modelSelect = document.getElementById('grok-model-select').value;
    
    let model;
    if (modelSelect === 'custom') {
        model = document.getElementById('grok-custom-model').value.trim();
        if (!model) {
            grokShowMessage('Please enter a custom model name', 'error');
            return;
        }
    } else {
        model = modelSelect;
    }
    
    if (!apiKey) {
        grokShowMessage('Please enter your Grok API Key', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/grok/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                api_key: apiKey,
                model: model
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            grokShowMessage(`✅ Grok configuration saved! (${model})`, 'success');
        } else {
            grokShowMessage('❌ Failed to save: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        grokShowMessage('Error: ' + error.message, 'error');
    }
}

async function grokTestConnection() {
    const resultDiv = document.getElementById('grok-test-result');
    resultDiv.innerHTML = '<div class="test-result info show">🧪 Testing Grok API connection...</div>';
    
    try {
        const response = await fetch('/api/grok/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            resultDiv.innerHTML = `
                <div class="test-result success show">
                    <h3 style="margin-top: 0; color: #059669;">✅ Grok API Connected Successfully!</h3>
                    <div style="background: #d1fae5; padding: 12px; border-radius: 6px; margin-top: 10px;">
                        <p style="margin: 0;"><strong>Model:</strong> ${data.model || 'grok-beta'}</p>
                        <p style="margin: 5px 0 0 0;"><strong>Response:</strong> ${escapeHtml(data.response || 'OK')}</p>
                    </div>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="test-result error show">
                    <h3 style="margin-top: 0; color: #dc2626;">❌ Connection Failed</h3>
                    <p>${escapeHtml(data.error || 'Unknown error')}</p>
                </div>
            `;
        }
    } catch (error) {
        resultDiv.innerHTML = `
            <div class="test-result error show">
                <h3 style="margin-top: 0; color: #dc2626;">❌ Error</h3>
                <p>${escapeHtml(error.message)}</p>
            </div>
        `;
    }
}

async function grokToggleEnabled() {
    const enabled = document.getElementById('grok-enabled').checked;
    
    try {
        const response = await fetch('/api/grok/enabled', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateGrokStatus(enabled);
            grokShowMessage(
                enabled ? '✅ Grok AI enabled' : '⚠️ Grok AI disabled',
                enabled ? 'success' : 'warning'
            );
        } else {
            document.getElementById('grok-enabled').checked = !enabled;
            grokShowMessage('Failed to update: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        document.getElementById('grok-enabled').checked = !enabled;
        grokShowMessage('Error: ' + error.message, 'error');
    }
}

function updateGrokStatus(enabled) {
    const statusEl = document.getElementById('grok-status');
    if (enabled) {
        statusEl.textContent = '✅ Enabled';
        statusEl.style.background = '#d1fae5';
        statusEl.style.color = '#065f46';
    } else {
        statusEl.textContent = '❌ Disabled';
        statusEl.style.background = '#fee2e2';
        statusEl.style.color = '#991b1b';
    }
}

function grokShowMessage(message, type = 'info') {
    const messageDiv = document.getElementById('grok-message');
    if (!messageDiv) return;
    
    messageDiv.style.display = 'block';
    messageDiv.className = `result-box ${type} show`;
    messageDiv.textContent = message;
    
    if (type === 'success') {
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 5000);
    }
}

// ==================== Signal Loading & Display ====================

async function xLoadSignals() {
    console.log('[X Module] ===== xLoadSignals CALLED =====');
    console.log('[X Module] Current xSignalsData length:', xSignalsData.length);
    console.log('[X Module] Current xSignalsLastId:', xSignalsLastId);
    
    try {
        const url = xSignalsLastId 
            ? `/api/signals/x-channel?limit=50&since_id=${xSignalsLastId}`
            : '/api/signals/x-channel?limit=50';
        
        console.log('[X Module] Fetching signals from:', url);
        const response = await fetch(url);
        
        if (!response.ok) {
            console.error('[X Module] API response not OK:', response.status, response.statusText);
            return;
        }
        
        const data = await response.json();
        console.log('[X Module] Received data:', data);
        
        if (data.success && data.signals) {
            console.log('[X Module] Processing', data.signals.length, 'signals');
            // Update last ID
            if (data.signals.length > 0) {
                const maxId = Math.max(...data.signals.map(s => s.id));
                if (!xSignalsLastId || maxId > xSignalsLastId) {
                    xSignalsLastId = maxId;
                }
                
                // Add new signals to our data array
                const newSignals = [];
                data.signals.forEach(signal => {
                    if (!xSignalsData.find(s => s.id === signal.id)) {
                        xSignalsData.push(signal);
                        newSignals.push(signal);
                    }
                });
                
                // Sort xSignalsData to keep newest first (by ID descending, or by received_at if available)
                xSignalsData.sort((a, b) => {
                    // First try to sort by received_at timestamp (newest first)
                    if (a.received_at && b.received_at) {
                        return new Date(b.received_at) - new Date(a.received_at);
                    }
                    // Fallback to ID (higher ID = newer signal)
                    return (b.id || 0) - (a.id || 0);
                });
                
                // Automatically load analysis for new signals (they may have been auto-analyzed)
                if (newSignals.length > 0) {
                    // Load analysis for all new signals in parallel
                    const analysisPromises = newSignals.map(signal => 
                        fetch(`/api/x/signals/${signal.id}/analysis`)
                            .then(res => res.json())
                            .then(data => {
                                if (data.success && data.analysis) {
                                    xAnalysisCache[signal.id] = data.analysis;
                                }
                            })
                            .catch(err => {
                                // Signal may not have analysis yet, that's OK
                                console.debug(`No analysis yet for signal ${signal.id}`);
                            })
                    );
                    
                    // Wait for all analysis loads to complete (or fail silently)
                    await Promise.allSettled(analysisPromises);
                }
            }
            
            // Check analysis status for existing signals that don't have analysis yet
            // This ensures we update the UI when analysis completes in the background
            const signalsWithoutAnalysis = xSignalsData.filter(s => !xAnalysisCache[s.id]);
            if (signalsWithoutAnalysis.length > 0) {
                console.log(`[X Module] Checking analysis for ${signalsWithoutAnalysis.length} existing signals without analysis`);
                
                // Check analysis for signals without analysis (limit to 10 at a time to avoid overload)
                const signalsToCheck = signalsWithoutAnalysis.slice(0, 10);
                const analysisCheckPromises = signalsToCheck.map(signal => 
                    fetch(`/api/x/signals/${signal.id}/analysis`)
                        .then(res => res.json())
                        .then(data => {
                            if (data.success && data.analysis) {
                                // Analysis found! Update cache
                                xAnalysisCache[signal.id] = data.analysis;
                                console.log(`[X Module] Analysis found for signal ${signal.id}`);
                                return true; // Indicate we found analysis
                            }
                            return false;
                        })
                        .catch(err => {
                            // Signal may not have analysis yet, that's OK
                            return false;
                        })
                );
                
                // Wait for all checks to complete
                const results = await Promise.allSettled(analysisCheckPromises);
                const foundAny = results.some(r => r.status === 'fulfilled' && r.value === true);
                
                // Update badge count if any new analyses were found
                if (foundAny) {
                    xUpdateMobileBadge();
                }
                
                if (foundAny) {
                    console.log('[X Module] Found new analysis, updating UI');
                }
            }
            
            // Apply filters and render (this will update the UI with any new analysis)
            xApplyFilters();
            
            // Update analytics
            xUpdateAnalytics();
            
            // Update badge count after loading signals
            xUpdateMobileBadge();
        }
    } catch (error) {
        console.error('Error loading signals:', error);
    }
}

// ==================== Mobile Badge Count ====================

async function xCountUnreadHighEngagementSignals() {
    try {
        const response = await fetch('/api/x/unread-count');
        const data = await response.json();
        return data.count || 0;
    } catch (error) {
        console.error('[X Module] Error fetching unread count:', error);
        return 0;
    }
}

async function xUpdateMobileBadge() {
    try {
        const count = await xCountUnreadHighEngagementSignals();
        
        // Update mobile nav badge
        const mobileButton = document.querySelector('.mobile-tab-btn[onclick*="switchTab(\'x\'"]');
        xUpdateButtonBadge(mobileButton, count);
        
        // Update desktop nav badge
        const desktopButton = document.querySelector('.tabs > .tab-btn[onclick*="switchTab(\'x\'"]');
        xUpdateButtonBadge(desktopButton, count);
        
        // Update app icon badge
        if (typeof updateAppIconBadge === 'function') {
            updateAppIconBadge();
        }
    } catch (error) {
        console.error('[X Module] Error updating badge:', error);
    }
}

// Helper function to update badge on a button
function xUpdateButtonBadge(button, count) {
    if (!button) return;
    
    let badge = button.querySelector('.x-badge');
            
            if (count > 0) {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'x-badge';
                    badge.style.cssText = 'position: absolute; top: 2px; right: 2px; background: #ef4444; color: white; border-radius: 10px; min-width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold; padding: 0 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);';
            button.style.position = 'relative';
            button.appendChild(badge);
                }
                badge.textContent = count > 99 ? '99+' : count.toString();
                badge.style.display = 'flex';
            } else {
                if (badge) {
                    badge.style.display = 'none';
                }
            }
        }
        
function xMarkSignalsAsRead() {
    // Auto-mark signals as read when X tab is opened:
    // 1. LOW engagement (score < 0.5) - these shouldn't show as unread
    // 2. OLD signals (> 1 hour) - these expire automatically
    // Only HIGH engagement (>= 0.5) signals within 1 hour should stay unread
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000); // 1 hour in milliseconds
    
    xSignalsData.forEach(signal => {
        if (xReadSignals.has(signal.id)) return; // Already read
        
        const analysis = xAnalysisCache[signal.id];
        const engagementScore = analysis ? analysis.score : 0;
        
        // Check if signal is older than 1 hour
        let isOld = false;
        if (signal.received_at) {
            const signalTime = new Date(signal.received_at);
            isOld = signalTime < oneHourAgo;
        }
        
        // Mark as read if: old OR low engagement score
        if (isOld || engagementScore < 0.5) {
            xReadSignals.add(signal.id);
            // Also mark in database if not already marked
            if (!signal.x_read) {
                markSignalAsReadInX(signal.id);
    }
        }
    });
    
    // Update badge
    xUpdateMobileBadge();
}

function xAutoMarkOldSignalsAsRead() {
    // Automatically mark signals as read if:
    // 1. Signal is older than 1 hour, OR
    // 2. Signal has engagement score < 0.5 (low engagement)
    // Only high-engagement signals (score >= 0.5) within the last hour should be unread
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000); // 1 hour in milliseconds
    
    xSignalsData.forEach(signal => {
        if (xReadSignals.has(signal.id)) return; // Already read
        
        const analysis = xAnalysisCache[signal.id];
        const engagementScore = analysis ? analysis.score : 0;
        
        // Check if signal is older than 1 hour
        let isOld = false;
        if (signal.received_at) {
            const signalTime = new Date(signal.received_at);
            isOld = signalTime < oneHourAgo;
        }
        
        // Mark as read if: old OR low engagement score
        if (isOld || engagementScore < 0.5) {
            xReadSignals.add(signal.id);
            // Also mark in database if not already marked
            if (!signal.x_read) {
                markSignalAsReadInX(signal.id);
            }
        }
    });
}

async function markSignalAsReadInX(signalId) {
    try {
        const response = await fetch(`/api/signals/${signalId}/mark-x-read`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Update the signal object in xSignalsData
            const signal = xSignalsData.find(s => s.id === signalId);
            if (signal) {
                signal.x_read = true;
            }
            
            // Remove highlight from signal card
            const signalCard = document.querySelector(`.x-signal-card[data-signal-id="${signalId}"]`);
            if (signalCard) {
                signalCard.classList.remove('signal-unread-x');
            }
            
            // Update badge count
            xUpdateMobileBadge();
            
            return { success: true };
        } else {
            throw new Error(data.error || 'Failed to mark signal as read');
        }
    } catch (error) {
        console.error('[X Module] Error marking signal as read:', error);
        throw error;
    }
}

function xApplyFilters() {
    console.log('[X Module] ===== xApplyFilters CALLED =====');
    console.log('[X Module] xSignalsData length:', xSignalsData.length);
    console.log('[X Module] xSignalsData:', xSignalsData);
    
    const scoreFilter = document.getElementById('x-filter-score')?.value || 'all';
    const botFilter = document.getElementById('x-filter-bot')?.value || 'all';
    const statusFilter = document.getElementById('x-filter-status')?.value || 'all';
    const tickerFilter = document.getElementById('x-filter-ticker')?.value?.toUpperCase() || '';
    
    console.log('[X Module] Filters:', { scoreFilter, botFilter, statusFilter, tickerFilter });
    
    let filtered = [...xSignalsData];
    console.log('[X Module] Starting with', filtered.length, 'signals before filtering');
    
    // Filter by score (only filter signals that have been analyzed)
    if (scoreFilter !== 'all') {
        const minScore = parseFloat(scoreFilter);
        filtered = filtered.filter(s => {
            const analysis = xAnalysisCache[s.id];
            // Show signal if: it has analysis AND meets score threshold, OR it hasn't been analyzed yet
            return !analysis || (analysis && analysis.score >= minScore);
        });
    }
    
    // Filter by bot type (check title)
    if (botFilter !== 'all') {
        filtered = filtered.filter(s => s.title && s.title.toLowerCase().includes(botFilter.toLowerCase()));
    }
    
    // Filter by status
    if (statusFilter !== 'all') {
        if (statusFilter === 'pending') {
            filtered = filtered.filter(s => !xAnalysisCache[s.id]);
        } else if (statusFilter === 'analyzed') {
            filtered = filtered.filter(s => xAnalysisCache[s.id]);
        } else if (statusFilter === 'posted') {
            // TODO: Check if signal has been posted
            filtered = filtered.filter(s => false); // For now, no signals shown as posted
        }
    }
    
    // Filter by ticker
    if (tickerFilter) {
        filtered = filtered.filter(s => {
            const content = ((s.title || '') + ' ' + (s.message || '')).toUpperCase();
            return content.includes(tickerFilter) || content.includes('$' + tickerFilter);
        });
    }
    
    // Sort signals: newest first (by ID descending, or by received_at timestamp if available)
    filtered.sort((a, b) => {
        // First try to sort by received_at timestamp (newest first)
        if (a.received_at && b.received_at) {
            return new Date(b.received_at) - new Date(a.received_at);
        }
        // Fallback to ID (higher ID = newer signal)
        return (b.id || 0) - (a.id || 0);
    });
    
    // Render filtered signals
    console.log('[X Module] After all filters, rendering', filtered.length, 'signals (newest first)');
    xRenderSignals(filtered);
}

function xRenderSignals(signals) {
    const container = document.getElementById('x-signals-list');
    
    console.log('[X Module] xRenderSignals called with', signals.length, 'signals');
    console.log('[X Module] Container element:', container);
    
    // Auto-mark signals older than 1 hour as read
    xAutoMarkOldSignalsAsRead();
    
    if (!container) {
        console.error('[X Module] ERROR: x-signals-list container not found!');
        return;
    }
    
    if (signals.length === 0) {
        console.log('[X Module] No signals to display, showing empty message');
        container.innerHTML = '<p style="color: #666; text-align: center; padding: 40px;">No signals match your filters. Try changing filters or analyzing signals first.</p>';
        return;
    }
    
    console.log('[X Module] Rendering', signals.length, 'signal cards');
    container.innerHTML = '';
    
    console.log('[X Module] Creating', signals.length, 'cards...');
    let successCount = 0;
    let errorCount = 0;
    
    signals.forEach((signal, index) => {
        try {
            console.log(`[X Module] Creating card ${index + 1}/${signals.length} for signal ID ${signal.id}`);
            const signalCard = xCreateSignalCard(signal);
            if (!signalCard) {
                console.error(`[X Module] xCreateSignalCard returned null/undefined for signal ${signal.id}`);
                errorCount++;
                return;
            }
            container.appendChild(signalCard);
            successCount++;
        } catch (error) {
            console.error(`[X Module] ERROR creating card for signal ${signal.id}:`, error);
            console.error('[X Module] Signal data:', signal);
            errorCount++;
        }
    });
    
    console.log(`[X Module] Card creation complete: ${successCount} success, ${errorCount} errors`);
}

function xCreateSignalCard(signal) {
    console.log('[X Module] xCreateSignalCard called for signal:', signal.id);
    
    try {
        const card = document.createElement('div');
        card.className = 'x-signal-card';
        card.setAttribute('data-signal-id', signal.id);
        
        // Check if signal is unread for X module
        const isUnreadX = !signal.x_read;
        if (isUnreadX) {
            card.classList.add('signal-unread-x');
        }
    card.style.cssText = `
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: all 0.2s ease;
        cursor: pointer;
        touch-action: manipulation;
    `;
    
    // Make card clickable to mark as read if unread (but not if clicking buttons)
    if (isUnreadX) {
        card.addEventListener('click', (e) => {
            // Don't mark as read if clicking on buttons or interactive elements
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                return;
            }
            // Mark as read when card is clicked
            markSignalAsReadInX(signal.id).then(() => {
                xApplyFilters();
            }).catch(err => {
                console.error('[X Module] Error marking signal as read on card click:', err);
            });
        });
        card.addEventListener('touchend', (e) => {
            // Don't mark as read if clicking on buttons or interactive elements
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) {
                return;
            }
            e.preventDefault();
            // Mark as read when card is touched
            markSignalAsReadInX(signal.id).then(() => {
                xApplyFilters();
            }).catch(err => {
                console.error('[X Module] Error marking signal as read on card touch:', err);
            });
        });
    }
    
    const analysis = xAnalysisCache[signal.id];
    const isExpanded = xExpandedSignals.has(signal.id);
    
    // Header
    const header = document.createElement('div');
    header.style.cssText = 'display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;';
    
    const headerLeft = document.createElement('div');
    headerLeft.style.flex = '1';
    
    const statusBadge = xGetStatusBadge(signal, analysis);
    const botType = xGetBotType(signal.title);
    const timeAgo = xGetTimeAgo(signal.received_at);
    
    headerLeft.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            ${statusBadge}
            <span style="font-weight: 600; color: #1d4ed8;">🐦 ${botType}</span>
            <span style="font-size: 0.85em; color: #666;">ID: ${signal.id}</span>
            <span style="font-size: 0.85em; color: #666;">•</span>
            <span style="font-size: 0.85em; color: #666;">${timeAgo}</span>
        </div>
    `;
    
    if (analysis) {
        const scoreDiv = document.createElement('div');
        scoreDiv.style.cssText = 'display: flex; align-items: center; gap: 8px;';
        scoreDiv.innerHTML = `
            <span style="font-size: 1.2em; font-weight: bold; color: #059669;">${analysis.score.toFixed(2)}</span>
            <span style="font-size: 1.1em;">${analysis.star_rating}</span>
        `;
        headerLeft.appendChild(scoreDiv);
    }
    
    const expandBtn = document.createElement('button');
    expandBtn.textContent = isExpanded ? '▲ Collapse' : '▼ Expand';
    expandBtn.style.cssText = 'padding: 6px 12px; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 4px; cursor: pointer; font-size: 0.9em;';
    expandBtn.onclick = (e) => {
        e.stopPropagation();
        xToggleSignalExpand(signal.id);
    };
    
    header.appendChild(headerLeft);
    header.appendChild(expandBtn);
    
    // Content Preview
    const preview = document.createElement('div');
    preview.style.cssText = 'margin: 10px 0; padding: 10px; background: #f9fafb; border-radius: 4px;';
    
    // Determine what to show: tweet if ready, otherwise raw signal
    let displayText = '';
    let isTweet = false;
    
    if (analysis && analysis.variants && analysis.variants.length > 0 && analysis.variants[0].text) {
        // Show the ready-to-post tweet
        displayText = analysis.variants[0].text;
        isTweet = true;
        preview.style.cssText = 'margin: 10px 0; padding: 10px; background: #ecfdf5; border-radius: 4px; border-left: 4px solid #10b981;';
    } else {
        // Show raw original signal
        displayText = signal.message || signal.raw_content || '';
        isTweet = false;
    }
    
    if (signal.title && !isTweet) {
        preview.innerHTML += `<div style="font-weight: 600; margin-bottom: 6px;">${escapeHtml(signal.title)}</div>`;
    }
    
    if (isTweet) {
        preview.innerHTML += `<div style="margin-bottom: 6px; font-size: 0.75em; color: #059669; font-weight: 600;">✍️ Ready-to-Post Tweet:</div>`;
    }
    
    const previewLength = 300;
    preview.innerHTML += `<div style="color: #6b7280; font-size: 0.9em; white-space: pre-wrap; word-wrap: break-word;">${escapeHtml(displayText.substring(0, previewLength))}${displayText.length > previewLength ? '...' : ''}</div>`;
    if (displayText.length > previewLength) {
        preview.innerHTML += `<div style="margin-top: 5px; font-size: 0.8em; color: #9ca3af; font-style: italic;">(${displayText.length} total characters - expand to see full ${isTweet ? 'tweet' : 'message'})</div>`;
    }
    
    // Quick Actions
    const actions = document.createElement('div');
    actions.style.cssText = 'display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap;';
    
    // Read button - only show if signal is unread
    if (!signal.x_read) {
        const readBtn = document.createElement('button');
        readBtn.className = 'btn btn-secondary';
        readBtn.textContent = '✓ Read';
        readBtn.style.fontSize = '0.9em';
        readBtn.style.cursor = 'pointer';
        readBtn.style.touchAction = 'manipulation'; // Improve touch responsiveness
        const handleMarkRead = async (e) => {
            e.preventDefault();
            e.stopPropagation();
            try {
                await markSignalAsReadInX(signal.id);
                // Re-render to remove unread styling and hide Read button
                xApplyFilters();
            } catch (err) {
                console.error('[X Module] Error marking signal as read:', err);
                alert('Failed to mark signal as read. Please try again.');
            }
        };
        readBtn.addEventListener('click', handleMarkRead);
        readBtn.addEventListener('touchend', handleMarkRead);
        actions.appendChild(readBtn);
    }
    
    const analyzeBtn = document.createElement('button');
    analyzeBtn.className = 'btn btn-primary';
    analyzeBtn.textContent = analysis ? '🔄 Re-analyze' : '🧠 Analyze';
    analyzeBtn.style.fontSize = '0.9em';
    analyzeBtn.onclick = (e) => {
        e.stopPropagation();
        xAnalyzeSignal(signal.id);
    };
    
    actions.appendChild(analyzeBtn);
    
    if (analysis && analysis.variants && analysis.variants.length > 0) {
        const modifyBtn = document.createElement('button');
        modifyBtn.className = 'btn btn-secondary';
        modifyBtn.textContent = '✏️ Modify';
        modifyBtn.style.fontSize = '0.9em';
        modifyBtn.onclick = (e) => {
            e.stopPropagation();
            xToggleModifyField(signal.id);
        };
        actions.appendChild(modifyBtn);
        
        const postBtn = document.createElement('button');
        postBtn.className = 'btn btn-success';
        postBtn.textContent = '📤 Post';
        postBtn.style.fontSize = '0.9em';
        postBtn.onclick = (e) => {
            e.stopPropagation();
            xPostTweet(signal.id, analysis.variants[0].id);
        };
        actions.appendChild(postBtn);
    }
    
    card.appendChild(header);
    card.appendChild(preview);
    card.appendChild(actions);
    
    // Add modify field container (hidden by default, or shown if previously open)
    const modifyContainer = document.createElement('div');
    modifyContainer.id = `modify-container-${signal.id}`;
    const isModifyOpen = xModifyOpenSignals.has(signal.id);
    const savedInputValue = xModifyInputValues[signal.id] || ''; // Restore saved input value
    modifyContainer.style.cssText = `display: ${isModifyOpen ? 'block' : 'none'}; margin-top: 15px; padding: 15px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb;`;
    modifyContainer.innerHTML = `
        <div style="margin-bottom: 10px;">
            <label style="display: block; font-weight: 600; margin-bottom: 5px; font-size: 0.9em;">Modification Instructions:</label>
            <textarea id="modify-input-${signal.id}" rows="3" placeholder="e.g., Make it more concise, Add emoji, Change tone to be more professional..." style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.9em; resize: vertical;" inputmode="text" autocomplete="off" autocapitalize="sentences" autocorrect="on" spellcheck="true">${savedInputValue}</textarea>
        </div>
        <div style="display: flex; gap: 10px;">
            <button onclick="xModifyTweet(${signal.id})" class="btn btn-primary" style="font-size: 0.9em;">✨ Apply Modifications</button>
            <button onclick="xToggleModifyField(${signal.id})" class="btn btn-secondary" style="font-size: 0.9em;">❌ Cancel</button>
        </div>
        <div id="modify-result-${signal.id}" style="margin-top: 10px; display: none;"></div>
    `;
    card.appendChild(modifyContainer);
    
    // Add event listener to save textarea value as user types (preserve across re-renders)
    if (isModifyOpen) {
        // Use setTimeout to ensure the textarea exists in the DOM
        setTimeout(() => {
            const textarea = document.getElementById(`modify-input-${signal.id}`);
            if (textarea) {
                textarea.addEventListener('input', () => {
                    xModifyInputValues[signal.id] = textarea.value;
                });
            }
        }, 0);
    }
    
    // Expanded Content - only show if analysis is complete with all required fields
    if (isExpanded && analysis && analysis.score_breakdown) {
        const expanded = xCreateExpandedContent(signal, analysis);
        card.appendChild(expanded);
    } else if (isExpanded && !analysis) {
        // Show "analyzing..." message if expanded but no analysis yet
        const analyzing = document.createElement('div');
        analyzing.style.cssText = 'margin-top: 15px; padding: 20px; background: #fef3c7; border-left: 3px solid #f59e0b; border-radius: 4px;';
        analyzing.innerHTML = '<p style="margin: 0; color: #92400e; text-align: center;">⏳ Click "Analyze" to generate tweet variants and engagement predictions...</p>';
        card.appendChild(analyzing);
    } else if (isExpanded && analysis && !analysis.score_breakdown) {
        // Analysis exists but incomplete
        const incomplete = document.createElement('div');
        incomplete.style.cssText = 'margin-top: 15px; padding: 20px; background: #fef3c7; border-left: 3px solid #f59e0b; border-radius: 4px;';
        incomplete.innerHTML = '<p style="margin: 0; color: #92400e; text-align: center;">⚠️ Analysis incomplete. Click "Re-analyze" to generate full analysis.</p>';
        card.appendChild(incomplete);
    }
    
    // Click to expand
    card.onclick = () => {
        if (!isExpanded && !analysis) {
            xAnalyzeSignal(signal.id);
        }
        xToggleSignalExpand(signal.id);
    };
    
    console.log('[X Module] Successfully created card for signal:', signal.id);
    return card;
    
    } catch (error) {
        console.error('[X Module] FATAL ERROR in xCreateSignalCard for signal', signal.id, ':', error);
        console.error('[X Module] Stack trace:', error.stack);
        throw error; // Re-throw so outer catch can handle it
    }
}

function xCreateExpandedContent(signal, analysis) {
    const expanded = document.createElement('div');
    expanded.className = 'x-signal-expanded';
    expanded.style.cssText = 'margin-top: 20px; padding-top: 20px; border-top: 2px solid #e5e7eb;';
    
    // Raw Original Signal (Full Message)
    const fullMessage = signal.message || signal.raw_content || '';
    expanded.innerHTML += `
        <div style="margin-bottom: 20px;">
            <h4 style="margin: 0 0 10px 0;">📄 Raw Original Signal</h4>
            <div style="background: #f9fafb; padding: 15px; border-radius: 6px; border: 1px solid #e5e7eb;">
                <div style="margin-bottom: 8px;">
                    <strong>Title:</strong> ${escapeHtml(signal.title || 'N/A')}
                </div>
                <div style="white-space: pre-wrap; word-wrap: break-word; font-family: monospace; font-size: 0.9em; color: #374151; line-height: 1.6;">
                    ${escapeHtml(fullMessage)}
                </div>
                <div style="margin-top: 10px; font-size: 0.85em; color: #6b7280;">
                    <strong>Length:</strong> ${fullMessage.length} characters
                </div>
            </div>
        </div>
    `;
    
    // Score Breakdown
    expanded.innerHTML += `
        <div style="margin-bottom: 20px;">
            <h4 style="margin: 0 0 10px 0;">🧠 Engagement Score Breakdown</h4>
            <div style="background: #f9fafb; padding: 15px; border-radius: 6px;">
                ${xRenderScoreBreakdown(analysis.score_breakdown)}
            </div>
        </div>
    `;
    
    // Entities
    if (analysis.entities) {
        expanded.innerHTML += `
            <div style="margin-bottom: 20px;">
                <h4 style="margin: 0 0 10px 0;">🏷️ Extracted Entities</h4>
                <div style="background: #f9fafb; padding: 15px; border-radius: 6px;">
                    ${xRenderEntities(analysis.entities)}
                </div>
            </div>
        `;
    }
    
    // Tweet Variants
    if (analysis.variants && analysis.variants.length > 0) {
        expanded.innerHTML += `
            <div style="margin-bottom: 20px;">
                <h4 style="margin: 0 0 10px 0;">✍️ Generated Tweet Variants</h4>
                ${xRenderVariants(signal.id, analysis.variants)}
            </div>
        `;
    }
    
    return expanded;
}

function xRenderScoreBreakdown(breakdown) {
    if (!breakdown) return '<p>No breakdown available</p>';
    
    let html = '<table style="width: 100%; font-size: 0.9em;">';
    html += '<tr style="border-bottom: 1px solid #e5e7eb; font-weight: 600;"><td>Factor</td><td>Weight</td><td>Score</td><td>Contribution</td></tr>';
    
    for (const [key, data] of Object.entries(breakdown)) {
        if (key === 'penalty') continue;
        // Calculate contribution if not provided (score * weight)
        const contribution = data.contribution !== undefined ? data.contribution : (data.score * data.weight);
        html += `
            <tr style="border-bottom: 1px solid #f3f4f6;">
                <td style="padding: 8px 0;">${key.replace(/_/g, ' ')}</td>
                <td>${(data.weight * 100).toFixed(0)}%</td>
                <td>${data.score.toFixed(2)}</td>
                <td><strong>${contribution.toFixed(2)}</strong></td>
            </tr>
        `;
    }
    
    html += '</table>';
    return html;
}

function xRenderEntities(entities) {
    let html = '';
    
    if (entities.tickers && entities.tickers.length > 0) {
        html += `<div style="margin-bottom: 10px;"><strong>Tickers:</strong> ${entities.tickers.map(t => `<span style="background: #dbeafe; padding: 4px 8px; border-radius: 4px; margin: 0 4px; font-family: monospace;">$${t}</span>`).join('')}</div>`;
    }
    
    if (entities.keywords && entities.keywords.length > 0) {
        html += `<div style="margin-bottom: 10px;"><strong>Keywords:</strong> ${entities.keywords.map(k => `<span style="background: #e0e7ff; padding: 4px 8px; border-radius: 4px; margin: 0 4px;">${k}</span>`).join('')}</div>`;
    }
    
    if (entities.financial_numbers && entities.financial_numbers.length > 0) {
        html += `<div><strong>Numbers:</strong> ${entities.financial_numbers.join(', ')}</div>`;
    }
    
    return html || '<p>No entities extracted</p>';
}

function xRenderVariants(signalId, variants) {
    if (!variants || variants.length === 0) {
        return '<p style="color: #999;">No tweet generated</p>';
    }
    
    let html = '';
    
    // Render the single professional variant
    const variant = variants[0];
    const isRecommended = variant.recommended;
    const charCount = variant.text.length;
    
    html += `
        <div style="background: white; border: 2px solid ${isRecommended ? '#10b981' : '#e5e7eb'}; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
            ${isRecommended ? '<div style="background: #10b981; color: white; padding: 6px 12px; border-radius: 4px; display: inline-block; margin-bottom: 10px; font-weight: 600;">✅ READY TO POST</div>' : ''}
            
            <div style="margin-bottom: 12px;">
                <span style="background: #dbeafe; color: #1e40af; padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 600;">
                    ${variant.type.toUpperCase()}
                </span>
            </div>
            
            <div style="background: #f9fafb; padding: 15px; border-radius: 6px; margin-bottom: 12px; border-left: 4px solid #3b82f6;">
                <div style="font-size: 1em; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word;">
                    ${escapeHtml(variant.text)}
                </div>
            </div>
            
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding: 10px; background: #f0f9ff; border-radius: 4px;">
                <div style="font-size: 0.9em; color: #1e40af;">
                    <strong>📊 Predicted:</strong> ${variant.predicted_engagement || 0} engagements
                </div>
                <div style="font-size: 0.9em; color: ${charCount > 280 ? '#dc2626' : '#059669'};">
                    <strong>📏</strong> ${charCount}/280 chars
                </div>
            </div>
            
            ${variant.context_used ? `
                <div style="margin-bottom: 12px; padding: 10px; background: #fef3c7; border-radius: 4px; border-left: 3px solid #f59e0b;">
                    <div style="font-size: 0.85em; color: #92400e;">
                        <strong>🔍 Context Used:</strong> ${escapeHtml(variant.context_used)}
                    </div>
                </div>
            ` : ''}
            
            ${variant.relevant_facts && variant.relevant_facts.length > 0 ? `
                <div style="margin-bottom: 12px; padding: 10px; background: #ecfdf5; border-radius: 4px;">
                    <div style="font-size: 0.85em; color: #065f46; margin-bottom: 6px;">
                        <strong>📋 Relevant Facts Incorporated:</strong>
                    </div>
                    <ul style="margin: 0; padding-left: 20px; font-size: 0.85em; color: #047857;">
                        ${variant.relevant_facts.map(fact => `<li>${escapeHtml(fact)}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}
            
            <div style="margin-bottom: 10px; padding: 8px; background: #f3f4f6; border-radius: 4px;">
                <div style="font-size: 0.85em; color: #6b7280;">
                    <strong>Style:</strong> ${variant.style || 'Professional, factual, engaging'}
                </div>
            </div>
            
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <button onclick="xPostTweet(${signalId}, ${variant.id})" class="btn btn-success" style="flex: 1; min-width: 120px;">
                    📤 Post This Tweet
                </button>
                <button onclick="xCopyVariant('${escapeHtml(variant.text).replace(/'/g, "\\'")}');" class="btn btn-secondary" style="flex: 1; min-width: 100px;">
                    📋 Copy
                </button>
            </div>
        </div>
    `;
    
    return html;
}

// ==================== Signal Actions ====================

async function xAnalyzeSignal(signalId) {
    try {
        // Show loading state
        const card = document.querySelector(`[data-signal-id="${signalId}"]`);
        if (card) {
            card.style.opacity = '0.6';
        }
        
        const response = await fetch(`/api/x/signals/analyze/${signalId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Store analysis in cache
            xAnalysisCache[signalId] = data.analysis;
            
            // Update badge count if this is a high-engagement signal
            if (data.analysis && data.analysis.score >= 0.5) {
                xUpdateMobileBadge();
            }
            
            // Re-render the signal
            xApplyFilters();
            
            // Expand the signal
            xExpandedSignals.add(signalId);
            xApplyFilters();
        } else {
            alert('Analysis failed: ' + data.error);
        }
        
        if (card) {
            card.style.opacity = '1';
        }
    } catch (error) {
        console.error('Error analyzing signal:', error);
        alert('Error: ' + error.message);
    }
}

// Make functions globally accessible for onclick handlers
window.xToggleModifyField = function(signalId) {
    const container = document.getElementById(`modify-container-${signalId}`);
    if (container) {
        if (container.style.display === 'none') {
            // Opening modify section - pause auto-refresh
            const checkbox = document.getElementById('x-signals-autorefresh');
            if (checkbox && checkbox.checked) {
                xSignalsAutoRefreshWasEnabled = true;
                xStopAutoRefresh();
                console.log('[X Module] Auto-refresh paused because modify section is open');
            }
            
            container.style.display = 'block';
            xModifyOpenSignals.add(signalId); // Track that this modify section is open
            const textarea = document.getElementById(`modify-input-${signalId}`);
            if (textarea) {
                textarea.focus();
                // Save input value as user types to preserve across re-renders
                textarea.addEventListener('input', () => {
                    xModifyInputValues[signalId] = textarea.value;
                });
            }
        } else {
            // Closing modify section - resume auto-refresh if it was enabled
            container.style.display = 'none';
            xModifyOpenSignals.delete(signalId); // Remove from tracking when closed
            
            // If no modify sections are open, resume auto-refresh
            if (xModifyOpenSignals.size === 0 && xSignalsAutoRefreshWasEnabled) {
                const checkbox = document.getElementById('x-signals-autorefresh');
                if (checkbox) {
                    checkbox.checked = true; // Ensure checkbox is checked
                    xStartAutoRefresh();
                    console.log('[X Module] Auto-refresh resumed after modify section closed');
                }
                xSignalsAutoRefreshWasEnabled = false;
            }
            
            // Clear the input and saved value
            const textarea = document.getElementById(`modify-input-${signalId}`);
            if (textarea) {
                textarea.value = '';
            }
            delete xModifyInputValues[signalId]; // Clear saved value
            const resultDiv = document.getElementById(`modify-result-${signalId}`);
            if (resultDiv) {
                resultDiv.style.display = 'none';
                resultDiv.innerHTML = '';
            }
        }
    }
};

window.xModifyTweet = async function(signalId) {
    const modifyInput = document.getElementById(`modify-input-${signalId}`);
    const resultDiv = document.getElementById(`modify-result-${signalId}`);
    
    if (!modifyInput) {
        alert('Modify input field not found');
        return;
    }
    
    const modificationText = modifyInput.value.trim();
    if (!modificationText) {
        alert('Please enter modification instructions');
        return;
    }
    
    // Show loading state
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = 'result-box info show';
        resultDiv.innerHTML = '<p style="margin: 0;">⏳ Modifying tweet...</p>';
    }
    
    try {
        const response = await fetch(`/api/x/signals/${signalId}/modify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                modifications: modificationText 
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.modified_tweet) {
            // Update the analysis cache with the modified tweet
            if (xAnalysisCache[signalId] && xAnalysisCache[signalId].variants && xAnalysisCache[signalId].variants.length > 0) {
                // Create a new variant with the modified tweet
                const modifiedVariant = {
                    id: `modified-${Date.now()}`,
                    text: data.modified_tweet,
                    score: xAnalysisCache[signalId].variants[0].score || 0,
                    engagement_prediction: xAnalysisCache[signalId].variants[0].engagement_prediction || 0
                };
                // Replace the first variant with the modified one
                xAnalysisCache[signalId].variants[0] = modifiedVariant;
            }
            
            // Show success message
            if (resultDiv) {
                resultDiv.className = 'result-box success show';
                resultDiv.innerHTML = '<p style="margin: 0;">✅ Tweet modified successfully! The updated tweet is now displayed above.</p>';
            }
            
            // Re-render the signal card to show the modified tweet
            xApplyFilters();
            
            // Hide the modify field after a short delay
            setTimeout(() => {
                xToggleModifyField(signalId);
                // Note: xToggleModifyField will remove from xModifyOpenSignals when closing
            }, 2000);
        } else {
            if (resultDiv) {
                resultDiv.className = 'result-box error show';
                resultDiv.innerHTML = `<p style="margin: 0;">❌ Error: ${data.error || 'Failed to modify tweet'}</p>`;
            }
        }
    } catch (error) {
        console.error('Error modifying tweet:', error);
        if (resultDiv) {
            resultDiv.className = 'result-box error show';
            resultDiv.innerHTML = `<p style="margin: 0;">❌ Error: ${error.message}</p>`;
        }
    }
};

async function xPostTweet(signalId, variantId) {
    if (!confirm('Post this tweet to X?')) return;
    
    try {
        const response = await fetch(`/api/x/signals/${signalId}/post`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ variant_id: variantId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ Tweet posted successfully!\nTweet ID: ' + data.result.tweet_id);
            xApplyFilters();
        } else {
            alert('❌ Failed to post tweet: ' + data.error);
        }
    } catch (error) {
        console.error('Error posting tweet:', error);
        alert('Error: ' + error.message);
    }
}

function xCopyVariant(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('✅ Tweet copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

function xToggleSignalExpand(signalId) {
    const wasExpanded = xExpandedSignals.has(signalId);
    
    if (wasExpanded) {
        xExpandedSignals.delete(signalId);
    } else {
        xExpandedSignals.add(signalId);
        
        // Mark signal as read when expanded for the first time
        const signal = xSignalsData.find(s => s.id === signalId);
        if (signal && !signal.x_read) {
            // Mark as read in database (async, don't wait)
            markSignalAsReadInX(signalId).then(() => {
                // Re-render to remove unread styling
                xApplyFilters();
            }).catch(err => {
                console.error('[X Module] Error marking signal as read on expand:', err);
            });
        }
    }
    xApplyFilters();
}

async function xClearSignals() {
    if (!confirm('Clear all displayed signals? This will permanently delete them from the database.')) return;
    
    try {
        // Call backend API to delete signals from database
        const response = await fetch('/api/signals/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ channel_name: 'x' })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Clear frontend state
            xSignalsData = [];
            xAnalysisCache = {};
            xExpandedSignals.clear();
            xSignalsLastId = null;
            
            // Re-render (will show empty state)
            xApplyFilters();
            
            // Show success message
            xShowMessage(`✅ Cleared ${data.signals_deleted || 0} signal(s) from database`, 'success');
        } else {
            xShowMessage('❌ Failed to clear signals: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error clearing signals:', error);
        xShowMessage('Error clearing signals: ' + error.message, 'error');
    }
}

// ==================== Analytics ====================

async function xUpdateAnalytics() {
    try {
        // Fetch real analytics from backend
        const response = await fetch('/api/x/analytics');
        const data = await response.json();
        
        if (data.success) {
            // Update Today's Signals
            const signalsEl = document.getElementById('x-analytics-signals');
            const signalsTrendEl = document.getElementById('x-analytics-signals-trend');
            if (signalsEl) {
                signalsEl.textContent = data.today_signals || 0;
            }
            if (signalsTrendEl) {
                const analyzed = data.analyzed_signals || 0;
                const total = data.today_signals || 0;
                if (total > 0) {
                    const analyzedPct = ((analyzed / total) * 100).toFixed(0);
                    signalsTrendEl.textContent = `${analyzedPct}% analyzed`;
                } else {
                    signalsTrendEl.textContent = 'No signals today';
                }
            }
            
            // Update Posted Tweets
            const postedEl = document.getElementById('x-analytics-posted');
            const postedTrendEl = document.getElementById('x-analytics-posted-trend');
            if (postedEl) {
                postedEl.textContent = data.posted_tweets || 0;
            }
            if (postedTrendEl) {
                const total = data.today_signals || 0;
                const posted = data.posted_tweets || 0;
                if (total > 0) {
                    const rate = ((posted / total) * 100).toFixed(1);
                    postedTrendEl.textContent = `${rate}% conversion`;
                } else {
                    postedTrendEl.textContent = '0% conversion';
                }
            }
            
        } else {
            // Fallback to local data if API fails
            xUpdateAnalyticsFallback();
        }
    } catch (error) {
        console.error('Error fetching analytics:', error);
        // Fallback to local data
        xUpdateAnalyticsFallback();
    }
}

function xUpdateAnalyticsFallback() {
    // Fallback: Use local data
    const signalsEl = document.getElementById('x-analytics-signals');
    const signalsTrendEl = document.getElementById('x-analytics-signals-trend');
    if (signalsEl) {
        signalsEl.textContent = xSignalsData.length;
    }
    if (signalsTrendEl) {
        const analyzedCount = Object.keys(xAnalysisCache).length;
        if (xSignalsData.length > 0) {
            const analyzedPct = ((analyzedCount / xSignalsData.length) * 100).toFixed(0);
            signalsTrendEl.textContent = `${analyzedPct}% analyzed`;
        } else {
            signalsTrendEl.textContent = 'No signals loaded';
        }
    }
}

// ==================== Helpers ====================

function xGetStatusBadge(signal, analysis) {
    if (!analysis) {
        return '<span style="background: #fbbf24; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600;">⏳ PENDING</span>';
    }
    
    if (analysis.recommendation === 'POST_IMMEDIATELY') {
        return '<span style="background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600;">✅ POST NOW</span>';
    }
    
    return '<span style="background: #3b82f6; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600;">📊 ANALYZED</span>';
}

function xGetBotType(title) {
    if (!title) return 'Unknown';
    const lowerTitle = title.toLowerCase();
    if (lowerTitle.includes('uwhale') || lowerTitle.includes('uw economic')) return 'UWhale News';
    if (lowerTitle.includes('fsmn') || lowerTitle.includes('elite news')) return 'X News';
    if (lowerTitle.includes('flow') || lowerTitle.includes('contract')) return 'Flow Bot';
    return 'Unknown';
}

function xGetTimeAgo(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    return date.toLocaleDateString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== Auto-Refresh ====================

function xStartAutoRefresh() {
    console.log('[X Module] Starting auto-refresh');
    if (xSignalsAutoRefreshInterval) {
        clearInterval(xSignalsAutoRefreshInterval);
    }
    
    xSignalsAutoRefreshInterval = setInterval(() => {
        const checkbox = document.getElementById('x-signals-autorefresh');
        if (checkbox && checkbox.checked) {
            console.log('[X Module] Auto-refresh triggered');
            xLoadSignals();
        }
    }, 3000);
    
    console.log('[X Module] Loading initial signals');
    xLoadSignals();
}

function xStopAutoRefresh() {
    if (xSignalsAutoRefreshInterval) {
        clearInterval(xSignalsAutoRefreshInterval);
        xSignalsAutoRefreshInterval = null;
    }
}

// ==================== Signal Navigation ====================

function xNavigateToSignal(signalId) {
    console.log('[X Module] Navigating to signal:', signalId);
    
    // Switch to X tab if not already there
    const xTab = document.getElementById('x-tab');
    if (xTab && !xTab.classList.contains('active')) {
        // Try to use switchTab function if available
        if (typeof switchTab === 'function') {
            switchTab('x');
        } else {
            // Fallback: find the X tab button and click it
            const xTabButton = Array.from(document.querySelectorAll('.tab-btn')).find(btn => {
                const onclick = btn.getAttribute('onclick') || '';
                return onclick.includes("'x'") || onclick.includes('"x"') || btn.textContent.includes('X');
            });
            if (xTabButton) {
                xTabButton.click();
            }
        }
    }
    
    // Wait a bit for tab to switch, then scroll to signal
    setTimeout(() => {
        const signalCard = document.querySelector(`[data-signal-id="${signalId}"]`);
        if (signalCard) {
            // Scroll to signal card
            signalCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Highlight the signal card temporarily
            signalCard.style.transition = 'box-shadow 0.3s ease';
            signalCard.style.boxShadow = '0 0 20px rgba(59, 130, 246, 0.6)';
            signalCard.style.border = '2px solid #3b82f6';
            
            // Remove highlight after 3 seconds
            setTimeout(() => {
                signalCard.style.boxShadow = '';
                signalCard.style.border = '';
            }, 3000);
            
            // Expand the signal if not already expanded
            if (!xExpandedSignals.has(signalId)) {
                xExpandedSignals.add(signalId);
                xApplyFilters(); // Re-render to show expanded content
                
                // Scroll again after expansion
                setTimeout(() => {
                    signalCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 300);
            }
        } else {
            console.warn('[X Module] Signal card not found:', signalId);
            // Signal might not be loaded yet, try loading signals first
            xLoadSignals().then(() => {
                setTimeout(() => {
                    xNavigateToSignal(signalId);
                }, 500);
            });
        }
    }, 300);
}

// Listen for messages from service worker
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
        console.log('[X Module] Message from service worker:', event.data);
        if (event.data && event.data.type === 'navigate_to_signal') {
            const signalId = event.data.signal_id;
            const tab = event.data.tab;
            
            if (tab === 'x' && signalId) {
                xNavigateToSignal(signalId);
            }
        }
    });
}

// ==================== Initialization ====================

document.addEventListener('DOMContentLoaded', function() {
    const checkbox = document.getElementById('x-signals-autorefresh');
    if (checkbox) {
        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                xStartAutoRefresh();
            } else {
                xStopAutoRefresh();
            }
        });
    }
    
    // Check for signal ID in URL hash (for deep linking from notifications)
    const hash = window.location.hash;
    if (hash && hash.startsWith('#signal-')) {
        const signalId = parseInt(hash.replace('#signal-', ''));
        if (signalId) {
            // Wait for signals to load, then navigate
            setTimeout(() => {
                xNavigateToSignal(signalId);
            }, 1000);
        }
    }
    
    // Update badge count on initial load (wait for signals to load)
    setTimeout(() => {
        xUpdateMobileBadge();
    }, 2000);
});
