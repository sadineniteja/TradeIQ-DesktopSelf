// TradingView Executor JavaScript

// Helper function for HTML escaping
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load configuration
async function tradingviewExecutorLoadConfig() {
    try {
        const response = await fetch('/api/tradingview-executor/config');
        const data = await response.json();
        
        if (data.success && data.config) {
            document.getElementById('tradingview-platform').value = data.config.platform || 'etrade';
            document.getElementById('tradingview-position-size').value = data.config.position_size || 1.0;
            document.getElementById('tradingview-bid-delta').value = data.config.bid_delta || 0.01;
            document.getElementById('tradingview-ask-delta').value = data.config.ask_delta || 0.01;
            document.getElementById('tradingview-increments').value = data.config.increments || 0.01;
            
            // Load enabled state
            const enabled = data.config.enabled !== false; // Default to true if not set
            document.getElementById('tradingview-executor-enabled').checked = enabled;
            updateTradingViewExecutorStatus(enabled);
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Toggle enabled state
async function tradingviewExecutorToggleEnabled() {
    const enabled = document.getElementById('tradingview-executor-enabled').checked;
    
    try {
        const response = await fetch('/api/tradingview-executor/enabled', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateTradingViewExecutorStatus(enabled);
            showTradingViewMessage(
                enabled ? '✅ TradingView Executor enabled' : '⚠️ TradingView Executor disabled',
                enabled ? 'success' : 'warning'
            );
        } else {
            // Revert checkbox on error
            document.getElementById('tradingview-executor-enabled').checked = !enabled;
            showTradingViewMessage('Failed to update enabled state: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        // Revert checkbox on error
        document.getElementById('tradingview-executor-enabled').checked = !enabled;
        showTradingViewMessage('Error updating enabled state: ' + error.message, 'error');
    }
}

// Update status display
function updateTradingViewExecutorStatus(enabled) {
    const statusEl = document.getElementById('tradingview-executor-status');
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

// Save configuration
async function tradingviewExecutorSaveConfig() {
    const config = {
        platform: document.getElementById('tradingview-platform').value,
        position_size: parseFloat(document.getElementById('tradingview-position-size').value),
        bid_delta: parseFloat(document.getElementById('tradingview-bid-delta').value),
        ask_delta: parseFloat(document.getElementById('tradingview-ask-delta').value),
        increments: parseFloat(document.getElementById('tradingview-increments').value),
    };
    
    // Validate ranges
    if (config.position_size < 0.001 || config.position_size > 100.0) {
        showTradingViewMessage('Position size must be between 0.001 and 100.000', 'error');
        return;
    }
    if (config.bid_delta < 0.001 || config.bid_delta > 100.0) {
        showTradingViewMessage('Bid Delta must be between 0.001 and 100.000', 'error');
        return;
    }
    if (config.ask_delta < 0.001 || config.ask_delta > 100.0) {
        showTradingViewMessage('Ask Delta must be between 0.001 and 100.000', 'error');
        return;
    }
    if (config.increments < 0.001 || config.increments > 100.0) {
        showTradingViewMessage('Increments must be between 0.001 and 100.000', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/tradingview-executor/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        if (data.success) {
            showTradingViewMessage('Configuration saved successfully!', 'success');
        } else {
            showTradingViewMessage('Failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error saving config:', error);
        showTradingViewMessage('Error: ' + error.message, 'error');
    }
}

// Execute trade (manual execution)
async function tradingviewExecutorExecute() {
    const symbol = document.getElementById('tradingview-exec-symbol').value.trim().toUpperCase();
    const action = document.getElementById('tradingview-exec-action').value;
    const price = parseFloat(document.getElementById('tradingview-exec-price').value);
    
    if (!symbol || !price || isNaN(price)) {
        showTradingViewMessage('Please provide symbol and price', 'error');
        return;
    }
    
    const resultDiv = document.getElementById('tradingview-executor-result');
    
    // Show processing
    let html = '<div class="test-result info show">';
    html += '<h3 style="margin-top: 0;">🔄 Executing Trade...</h3>';
    html += '<div style="background: #f0f9ff; padding: 16px; border-radius: 8px; margin: 16px 0; border: 2px solid #0ea5e9;">';
    html += '<h4 style="margin: 0 0 12px 0;">📋 Input Summary</h4>';
    html += '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 0.9rem;">';
    html += '<div><strong>Symbol:</strong> ' + symbol + '</div>';
    html += '<div><strong>Action:</strong> ' + action + '</div>';
    html += '<div><strong>Signal Price:</strong> $' + price.toFixed(2) + '</div>';
    html += '</div></div>';
    html += '<p style="text-align: center; color: #0ea5e9;">⏳ Processing...</p>';
    html += '</div>';
    resultDiv.innerHTML = html;
    
    try {
        const response = await fetch('/api/tradingview-executor/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol, action, price })
        });
        
        const data = await response.json();
        
        html = '<div class="test-result ' + (data.success ? 'success' : 'error') + ' show">';
        
        if (data.success) {
            html += '<h2 style="margin-top: 0; color: #059669;">✅ Trade Executed Successfully</h2>';
            html += '<div style="background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); padding: 20px; border-radius: 8px; margin: 16px 0; border: 2px solid #059669;">';
            html += '<h3 style="margin: 0 0 16px 0; color: #065f46;">📊 Execution Results</h3>';
            html += '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">';
            html += '<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Order ID:</strong><br>' + (data.order_id || 'N/A') + '</div>';
            html += '<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Filled Price:</strong><br><span style="color: #059669; font-weight: bold; font-size: 1.2rem;">$' + (data.filled_price ? data.filled_price.toFixed(2) : 'N/A') + '</span></div>';
            html += '<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Quantity:</strong><br>' + (data.quantity || 'N/A') + '</div>';
            html += '<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Attempts:</strong><br>' + (data.attempts || 'N/A') + '</div>';
            html += '</div></div>';
        } else {
            html += '<h2 style="margin-top: 0; color: #dc2626;">❌ Trade Execution Failed</h2>';
            html += '<div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); padding: 20px; border-radius: 8px; margin: 16px 0; border: 2px solid #dc2626;">';
            html += '<h3 style="margin: 0 0 12px 0; color: #991b1b;">⚠️ Failure Information</h3>';
            html += '<div style="background: white; padding: 16px; border-radius: 6px;">';
            html += '<p style="margin: 0;"><strong>Error:</strong></p>';
            html += '<p style="margin: 8px 0 0 0; color: #991b1b; font-size: 0.95rem;">' + (data.error || 'Unknown error') + '</p>';
            html += '</div>';
            if (data.attempts) {
                html += '<div style="background: white; padding: 16px; border-radius: 6px; margin-top: 12px;">';
                html += '<p style="margin: 0;"><strong>Attempts:</strong> ' + data.attempts + '</p>';
                html += '</div>';
            }
            html += '</div>';
        }
        
        // Add log section
        if (data.log && data.log.length > 0) {
            html += '<div style="margin: 24px 0;">';
            html += '<h3 style="margin: 0 0 16px 0;">📋 Execution Log</h3>';
            html += '<div style="background: #1e293b; color: #e2e8f0; padding: 20px; border-radius: 8px; max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 0.85rem; line-height: 1.7;">';
            data.log.forEach(line => {
                let color = '#e2e8f0';
                if (line.includes('✅')) color = '#4ade80';
                else if (line.includes('❌')) color = '#f87171';
                else if (line.includes('⚠️')) color = '#fbbf24';
                else if (line.includes('===') || line.includes('EXECUTION')) color = '#60a5fa';
                else if (line.includes('🔄')) color = '#a78bfa';
                html += '<div style="color: ' + color + '; margin: 2px 0;">' + escapeHtml(line) + '</div>';
            });
            html += '</div></div>';
        }
        
        html += '</div>';
        resultDiv.innerHTML = html;
        
        // Refresh history after execution
        setTimeout(() => tradingviewExecutorLoadHistory(), 500);
    } catch (error) {
        console.error('Error executing:', error);
        resultDiv.innerHTML = '<div class="test-result error show"><h2>❌ Error</h2><p>' + error.message + '</p></div>';
    }
}

// Show message
function showTradingViewMessage(message, type) {
    const messageDiv = document.getElementById('tradingview-executor-message');
    if (messageDiv) {
        messageDiv.className = 'result-box ' + (type === 'success' ? 'success' : 'error');
        messageDiv.textContent = message;
        messageDiv.style.display = 'block';
        setTimeout(() => { messageDiv.style.display = 'none'; }, 5000);
    }
}

// Load execution history
async function tradingviewExecutorLoadHistory() {
    const historyDiv = document.getElementById('tradingview-executor-history');
    if (!historyDiv) return;
    
    historyDiv.innerHTML = '<p class="loading">Loading history...</p>';
    
    try {
        const response = await fetch('/api/tradingview-executor/history?limit=20');
        const data = await response.json();
        
        if (!data.success || !data.history || data.history.length === 0) {
            historyDiv.innerHTML = '<p style="color: #999; padding: 20px; text-align: center;">No execution history found</p>';
            return;
        }
        
        let html = '';
        data.history.forEach(exec => {
            const statusClass = exec.status === 'success' ? 'success' : 'error';
            const statusIcon = exec.status === 'success' ? '✅' : '❌';
            
            html += '<div class="result-box ' + statusClass + '" style="margin-bottom: 15px;">';
            html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">';
            html += '<h4 style="margin: 0;">' + statusIcon + ' ' + exec.action + ' ' + exec.symbol + ' @ $' + (exec.signal_price || 0).toFixed(2) + '</h4>';
            html += '<span style="font-size: 0.9rem; color: #666;">' + new Date(exec.created_at).toLocaleString() + '</span>';
            html += '</div>';
            
            html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 10px;">';
            html += '<div><strong>Platform:</strong> ' + (exec.platform || 'N/A').toUpperCase() + '</div>';
            html += '<div><strong>Position:</strong> ' + (exec.position_size || 0) + '</div>';
            html += '<div><strong>Attempts:</strong> ' + (exec.attempts || 0) + '</div>';
            
            if (exec.status === 'success') {
                html += '<div><strong>Order ID:</strong> ' + (exec.order_id || 'N/A') + '</div>';
                html += '<div><strong>Filled Price:</strong> $' + (exec.filled_price || 0).toFixed(2) + '</div>';
                html += '<div><strong>Quantity:</strong> ' + (exec.quantity || 0) + '</div>';
                if (exec.preview_id) {
                    html += '<div style="grid-column: 1 / -1;"><strong>Preview ID:</strong> <span style="font-family: monospace; font-size: 0.9rem;">' + exec.preview_id + '</span></div>';
                }
            } else {
                html += '<div style="grid-column: 1 / -1;"><strong>Error:</strong> ' + (exec.error_message || 'Unknown error') + '</div>';
                if (exec.preview_id) {
                    html += '<div style="grid-column: 1 / -1;"><strong>Preview ID (before failure):</strong> <span style="font-family: monospace; font-size: 0.9rem;">' + exec.preview_id + '</span></div>';
                }
            }
            html += '</div>';
            
            if (exec.execution_log) {
                html += '<details style="margin-top: 10px;"><summary style="cursor: pointer; font-weight: bold;">📋 View Log</summary>';
                html += '<pre style="background: #1e293b; color: #e2e8f0; padding: 15px; border-radius: 4px; font-size: 12px; max-height: 300px; overflow-y: auto; margin-top: 10px; font-family: monospace; line-height: 1.7;">';
                const logLines = exec.execution_log.split('\n');
                logLines.forEach(line => {
                    let color = '#e2e8f0';
                    if (line.includes('✅')) color = '#4ade80';
                    else if (line.includes('❌')) color = '#f87171';
                    else if (line.includes('⚠️')) color = '#fbbf24';
                    else if (line.includes('===') || line.includes('EXECUTION')) color = '#60a5fa';
                    else if (line.includes('🔄')) color = '#a78bfa';
                    html += '<span style="color: ' + color + ';">' + escapeHtml(line) + '</span>\n';
                });
                html += '</pre></details>';
            }
            
            html += '</div>';
        });
        
        historyDiv.innerHTML = html;
    } catch (error) {
        console.error('Error loading history:', error);
        historyDiv.innerHTML = '<div class="result-box error">Error loading history: ' + error.message + '</div>';
    }
}

// Clear execution history
async function tradingviewExecutorClearHistory() {
    if (!confirm('Are you sure you want to clear all TradingView execution history?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/tradingview-executor/history/clear', {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (data.success) {
            showTradingViewMessage('History cleared successfully', 'success');
            tradingviewExecutorLoadHistory();
        } else {
            showTradingViewMessage('Failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error clearing history:', error);
        showTradingViewMessage('Error: ' + error.message, 'error');
    }
}

// Execute trade (manual execution)
async function tradingviewExecutorExecute() {
    const symbol = document.getElementById('tradingview-exec-symbol').value.trim().toUpperCase();
    const action = document.getElementById('tradingview-exec-action').value;
    const price = parseFloat(document.getElementById('tradingview-exec-price').value);
    
    if (!symbol || !price || isNaN(price)) {
        showTradingViewMessage('Please provide symbol, action, and price', 'error');
        return;
    }
    
    const resultDiv = document.getElementById('tradingview-executor-result');
    
    // Show processing
    let html = '<div class="test-result info show">';
    html += '<h3 style="margin-top: 0;">🔄 Executing Trade...</h3>';
    html += '<div style="background: #f0f9ff; padding: 16px; border-radius: 8px; margin: 16px 0; border: 2px solid #0ea5e9;">';
    html += '<h4 style="margin: 0 0 12px 0;">📋 Input Summary</h4>';
    html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 0.9rem;">';
    html += '<div><strong>Symbol:</strong> ' + symbol + '</div>';
    html += '<div><strong>Action:</strong> ' + action + '</div>';
    html += '<div><strong>Signal Price:</strong> $' + price.toFixed(2) + '</div>';
    html += '</div></div>';
    html += '<p style="text-align: center; color: #0ea5e9;">⏳ Processing...</p>';
    html += '</div>';
    resultDiv.innerHTML = html;
    
    try {
        const response = await fetch('/api/tradingview-executor/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol, action, price })
        });
        
        const data = await response.json();
        
        html = '<div class="test-result ' + (data.success ? 'success' : 'error') + ' show">';
        
        if (data.success) {
            html += '<h2 style="margin-top: 0; color: #059669;">✅ Trade Executed Successfully</h2>';
            html += '<div style="background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); padding: 20px; border-radius: 8px; margin: 16px 0; border: 2px solid #059669;">';
            html += '<h3 style="margin: 0 0 16px 0; color: #065f46;">📊 Execution Results</h3>';
            html += '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">';
            html += '<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Order ID:</strong><br>' + (data.order_id || 'N/A') + '</div>';
            html += '<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Filled Price:</strong><br><span style="color: #059669; font-weight: bold; font-size: 1.2rem;">$' + (data.filled_price ? data.filled_price.toFixed(2) : 'N/A') + '</span></div>';
            html += '<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Quantity:</strong><br>' + (data.quantity || 'N/A') + '</div>';
            html += '<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Attempts:</strong><br>' + (data.attempts || 'N/A') + '</div>';
            html += '</div></div>';
        } else {
            html += '<h2 style="margin-top: 0; color: #dc2626;">❌ Trade Execution Failed</h2>';
            html += '<div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); padding: 20px; border-radius: 8px; margin: 16px 0; border: 2px solid #dc2626;">';
            html += '<h3 style="margin: 0 0 12px 0; color: #991b1b;">⚠️ Failure Information</h3>';
            html += '<div style="background: white; padding: 16px; border-radius: 6px;">';
            html += '<p style="margin: 0;"><strong>Error:</strong></p>';
            html += '<p style="margin: 8px 0 0 0; color: #991b1b; font-size: 0.95rem;">' + (data.error || 'Unknown error') + '</p>';
            html += '</div>';
            if (data.attempts) {
                html += '<div style="background: white; padding: 16px; border-radius: 6px; margin-top: 12px;">';
                html += '<p style="margin: 0;"><strong>Attempts:</strong> ' + data.attempts + '</p>';
                html += '</div>';
            }
            html += '</div>';
        }
        
        // Add log section
        if (data.log && data.log.length > 0) {
            html += '<div style="margin: 24px 0;">';
            html += '<h3 style="margin: 0 0 16px 0;">📋 Execution Log</h3>';
            html += '<div style="background: #1e293b; color: #e2e8f0; padding: 20px; border-radius: 8px; max-height: 400px; overflow-y: auto; font-family: monospace; font-size: 0.85rem; line-height: 1.7;">';
            data.log.forEach(line => {
                let color = '#e2e8f0';
                if (line.includes('✅')) color = '#4ade80';
                else if (line.includes('❌')) color = '#f87171';
                else if (line.includes('⚠️')) color = '#fbbf24';
                else if (line.includes('===') || line.includes('EXECUTION')) color = '#60a5fa';
                else if (line.includes('🔄')) color = '#a78bfa';
                html += '<div style="color: ' + color + '; margin: 2px 0;">' + escapeHtml(line) + '</div>';
            });
            html += '</div></div>';
        }
        
        html += '</div>';
        resultDiv.innerHTML = html;
        
        // Refresh history after execution
        setTimeout(() => tradingviewExecutorLoadHistory(), 500);
    } catch (error) {
        console.error('Error executing:', error);
        resultDiv.innerHTML = '<div class="test-result error show"><h2>❌ Error</h2><p>' + error.message + '</p></div>';
    }
}

// Show message
function showTradingViewMessage(message, type) {
    const messageDiv = document.getElementById('tradingview-executor-message');
    if (messageDiv) {
        messageDiv.className = 'result-box ' + (type === 'success' ? 'success' : 'error');
        messageDiv.textContent = message;
        messageDiv.style.display = 'block';
        setTimeout(() => { messageDiv.style.display = 'none'; }, 5000);
    }
}

