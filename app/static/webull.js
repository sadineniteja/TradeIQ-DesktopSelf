// Webull UI logic

let webullState = {
    authenticated: false,
    selectedAccountId: null,
    accounts: [],
};

// Load configuration on page load
async function webullLoadConfig() {
    try {
        const res = await fetch('/api/webull/config');
        const data = await res.json();
        if (data.success) {
            const appKeyInput = document.getElementById('webull-app-key');
            const appSecretInput = document.getElementById('webull-app-secret');
            
            if (appKeyInput && data.app_key) {
                appKeyInput.value = data.app_key;
            }
            if (appSecretInput && data.app_secret) {
                appSecretInput.value = data.app_secret;
            }
            
            webullUpdateSavedStatus(data);
        }
    } catch (err) {
        console.error('Webull config load error', err);
    }
}

function webullUpdateSavedStatus(data) {
    const statusEl = document.getElementById('webull-config-status');
    if (statusEl) {
        const hasKeys = data.has_app_key && data.has_app_secret;
        statusEl.textContent = hasKeys ? '✅ Saved' : 'Not set';
        statusEl.style.color = hasKeys ? '#10b981' : '#6b7280';
    }
}

async function webullSaveConfig() {
    const appKey = document.getElementById('webull-app-key').value.trim();
    const appSecret = document.getElementById('webull-app-secret').value.trim();
    
    if (!appKey || !appSecret) {
        webullShowStatus('⚠️ Please enter both App Key and App Secret', 'error');
        return;
    }
    
    try {
        const res = await fetch('/api/webull/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                app_key: appKey,
                app_secret: appSecret,
            }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            webullShowStatus(data.error || 'Failed to save config', 'error');
            return;
        }
        webullShowStatus('✅ Configuration saved successfully', 'success');
        webullState.authenticated = true;
        webullUpdateSavedStatus(data);
        
        // Auto-load accounts after saving
        setTimeout(() => webullLoadAccounts(), 500);
    } catch (err) {
        webullShowStatus(`Config save error: ${err}`, 'error');
    }
}

function webullShowStatus(message, type = 'info') {
    const statusEl = document.getElementById('webull-status');
    if (statusEl) {
        statusEl.innerHTML = `<div class="status-box ${type}">${message}</div>`;
        setTimeout(() => {
            if (statusEl.innerHTML.includes(message)) {
                statusEl.innerHTML = '';
            }
        }, 5000);
    }
}

async function webullLoadAccounts() {
    try {
        const res = await fetch('/api/webull/accounts');
        const data = await res.json();
        
        if (!res.ok || !data.success) {
            webullShowStatus(data.error || 'Failed to load accounts', 'error');
            return;
        }
        
        webullState.accounts = data.accounts || [];
        
        const accountsListEl = document.getElementById('webull-accounts-list');
        if (accountsListEl) {
            if (webullState.accounts.length === 0) {
                accountsListEl.innerHTML = '<p class="help-text">No accounts found</p>';
                return;
            }
            
            let html = '<div class="form-group">';
            html += '<label>Select Account <span style="color: red;">*</span></label>';
            html += '<select id="webull-account-select" onchange="webullSelectAccount()" style="width: 100%;">';
            html += '<option value="">-- Select Account --</option>';
            
            webullState.accounts.forEach(account => {
                const accountId = account.account_id || account.accountId;
                const accountName = account.account_name || account.accountName || accountId;
                const accountType = account.account_type || account.accountType || 'Unknown';
                html += `<option value="${accountId}">${accountName} (${accountType})</option>`;
            });
            
            html += '</select>';
            html += '</div>';
            
            // Auto-select first account if none selected
            if (!webullState.selectedAccountId && webullState.accounts.length > 0) {
                const firstAccountId = webullState.accounts[0].account_id || webullState.accounts[0].accountId;
                webullState.selectedAccountId = firstAccountId;
                setTimeout(() => {
                    const selectEl = document.getElementById('webull-account-select');
                    if (selectEl) selectEl.value = firstAccountId;
                }, 100);
            }
            
            accountsListEl.innerHTML = html;
            
            // Populate account dropdowns in order forms
            webullPopulateAccountDropdowns();
            
            // Show trading sections
            document.getElementById('webull-options-section').style.display = 'block';
            document.getElementById('webull-equity-section').style.display = 'block';
        }
        
        webullShowStatus(`✅ Loaded ${webullState.accounts.length} account(s)`, 'success');
    } catch (err) {
        webullShowStatus(`Error loading accounts: ${err}`, 'error');
    }
}

function webullPopulateAccountDropdowns() {
    // Populate options order account dropdown
    const optionAccountSelect = document.getElementById('webull-option-account');
    if (optionAccountSelect && webullState.accounts.length > 0) {
        optionAccountSelect.innerHTML = '<option value="">-- Select Account --</option>';
        webullState.accounts.forEach(account => {
            const accountId = account.account_id || account.accountId;
            const accountName = account.account_name || account.accountName || accountId;
            const accountType = account.account_type || account.accountType || 'Unknown';
            const option = document.createElement('option');
            option.value = accountId;
            option.textContent = `${accountName} (${accountType})`;
            optionAccountSelect.appendChild(option);
        });
        // Auto-select first account if available
        if (webullState.accounts.length > 0) {
            const firstAccountId = webullState.accounts[0].account_id || webullState.accounts[0].accountId;
            optionAccountSelect.value = firstAccountId;
        }
    }
    
    // Populate equity order account dropdown
    const equityAccountSelect = document.getElementById('webull-equity-account');
    if (equityAccountSelect && webullState.accounts.length > 0) {
        equityAccountSelect.innerHTML = '<option value="">-- Select Account --</option>';
        webullState.accounts.forEach(account => {
            const accountId = account.account_id || account.accountId;
            const accountName = account.account_name || account.accountName || accountId;
            const accountType = account.account_type || account.accountType || 'Unknown';
            const option = document.createElement('option');
            option.value = accountId;
            option.textContent = `${accountName} (${accountType})`;
            equityAccountSelect.appendChild(option);
        });
        // Auto-select first account if available
        if (webullState.accounts.length > 0) {
            const firstAccountId = webullState.accounts[0].account_id || webullState.accounts[0].accountId;
            equityAccountSelect.value = firstAccountId;
        }
    }
}

function webullSelectAccount() {
    const selectEl = document.getElementById('webull-account-select');
    if (selectEl) {
        webullState.selectedAccountId = selectEl.value;
        webullShowStatus(`✅ Account selected: ${webullState.selectedAccountId}`, 'success');
    }
}

async function webullPlaceOptionOrder() {
    const accountId = document.getElementById('webull-option-account').value;
    if (!accountId) {
        webullShowStatus('⚠️ Please select an account', 'error');
        return;
    }
    
    const symbol = document.getElementById('webull-option-symbol').value.trim().toUpperCase();
    const strike = document.getElementById('webull-option-strike').value.trim();
    const expiration = document.getElementById('webull-option-expiration').value.trim();
    const optionType = document.getElementById('webull-option-type').value;
    const side = document.getElementById('webull-option-side').value;
    const quantity = parseInt(document.getElementById('webull-option-quantity').value);
    const orderType = document.getElementById('webull-option-order-type').value;
    const limitPrice = document.getElementById('webull-option-limit-price').value.trim();
    const timeInForce = document.getElementById('webull-option-time-in-force').value;
    
    if (!symbol || !strike || !expiration || !quantity) {
        webullShowStatus('⚠️ Please fill in all required fields', 'error');
        return;
    }
    
    if (orderType === 'LIMIT' && !limitPrice) {
        webullShowStatus('⚠️ Limit price is required for LIMIT orders', 'error');
        return;
    }
    
    const resultEl = document.getElementById('webull-option-result');
    resultEl.innerHTML = '<p class="loading">Placing order...</p>';
    
    try {
        const res = await fetch(`/api/webull/accounts/${accountId}/place-option-order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol,
                strike_price: strike,
                init_exp_date: expiration,
                option_type: optionType,
                side,
                quantity,
                order_type: orderType,
                limit_price: limitPrice || null,
                time_in_force: timeInForce,
            }),
        });
        
        const data = await res.json();
        
        if (data.success) {
            resultEl.innerHTML = `
                <div class="status-box success">
                    <h4>✅ Order Placed Successfully!</h4>
                    <p><strong>Client Order ID:</strong> ${data.client_order_id}</p>
                    <p><strong>Order ID:</strong> ${data.order?.order_id || 'N/A'}</p>
                    ${data.preview ? `<p><strong>Estimated Cost:</strong> $${data.preview.estimated_cost || 'N/A'}</p>` : ''}
                </div>
            `;
        } else {
            const isTradingHours = data.order_valid;
            resultEl.innerHTML = `
                <div class="status-box ${isTradingHours ? 'warning' : 'error'}">
                    <h4>${isTradingHours ? '⚠️ Trading Hours Restriction' : '❌ Order Failed'}</h4>
                    <p>${data.error}</p>
                    ${isTradingHours ? '<p>✅ Order structure is valid - will be placed during market hours (9:30 AM - 4:00 PM ET)</p>' : ''}
                </div>
            `;
        }
    } catch (err) {
        resultEl.innerHTML = `<div class="status-box error">Error: ${err}</div>`;
    }
}

async function webullPlaceEquityOrder() {
    const accountId = document.getElementById('webull-equity-account').value;
    if (!accountId) {
        webullShowStatus('⚠️ Please select an account', 'error');
        return;
    }
    
    const symbol = document.getElementById('webull-equity-symbol').value.trim().toUpperCase();
    const side = document.getElementById('webull-equity-side').value;
    const quantity = parseInt(document.getElementById('webull-equity-quantity').value);
    const orderType = document.getElementById('webull-equity-order-type').value;
    const limitPrice = document.getElementById('webull-equity-limit-price').value.trim();
    const timeInForce = document.getElementById('webull-equity-time-in-force').value;
    const tradingSession = document.getElementById('webull-equity-trading-session').value;
    
    // Determine extended_hours_trading based on session
    const extendedHoursTrading = tradingSession === 'EXTENDED';
    
    if (!symbol || !quantity) {
        webullShowStatus('⚠️ Please fill in all required fields', 'error');
        return;
    }
    
    if (orderType === 'LIMIT' && !limitPrice) {
        webullShowStatus('⚠️ Limit price is required for LIMIT orders', 'error');
        return;
    }
    
    // Extended hours requires LIMIT orders
    if (extendedHoursTrading && orderType !== 'LIMIT') {
        webullShowStatus('⚠️ Extended hours trading only supports LIMIT orders', 'error');
        return;
    }
    
    const resultEl = document.getElementById('webull-equity-result');
    resultEl.innerHTML = '<p class="loading">Placing order...</p>';
    
    try {
        const res = await fetch(`/api/webull/accounts/${accountId}/place-equity-order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                symbol,
                side,
                quantity,
                order_type: orderType,
                limit_price: limitPrice || null,
                time_in_force: timeInForce,
                extended_hours_trading: extendedHoursTrading,
            }),
        });
        
        const data = await res.json();
        
        if (data.success) {
            resultEl.innerHTML = `
                <div class="status-box success">
                    <h4>✅ Order Placed Successfully!</h4>
                    <p><strong>Client Order ID:</strong> ${data.client_order_id}</p>
                    <p><strong>Order ID:</strong> ${data.order?.order_id || 'N/A'}</p>
                    <p><strong>Session:</strong> ${extendedHoursTrading ? 'Extended Hours' : 'Regular Hours'}</p>
                </div>
            `;
        } else {
            const isTradingHours = data.order_valid;
            resultEl.innerHTML = `
                <div class="status-box ${isTradingHours ? 'warning' : 'error'}">
                    <h4>${isTradingHours ? '⚠️ Trading Hours Restriction' : '❌ Order Failed'}</h4>
                    <p>${data.error}</p>
                    ${isTradingHours ? `<p>✅ Order structure is valid - try again during ${extendedHoursTrading ? 'extended hours (4 AM - 8 PM ET)' : 'regular hours (9:30 AM - 4:00 PM ET)'}</p>` : ''}
                </div>
            `;
        }
    } catch (err) {
        resultEl.innerHTML = `<div class="status-box error">Error: ${err}</div>`;
    }
}

// Toggle limit price field visibility based on order type
function webullToggleLimitPrice(type) {
    const orderType = document.getElementById(`webull-${type}-order-type`).value;
    const limitPriceGroup = document.getElementById(`webull-${type}-limit-price-group`);
    if (limitPriceGroup) {
        limitPriceGroup.style.display = orderType === 'LIMIT' ? 'block' : 'none';
    }
}

// Handle trading session change for equity orders
function webullHandleTradingSession() {
    const sessionSelect = document.getElementById('webull-equity-trading-session');
    const orderTypeSelect = document.getElementById('webull-equity-order-type');
    const sessionInfoEl = document.getElementById('webull-equity-session-info');
    
    if (!sessionSelect) return;
    
    const session = sessionSelect.value;
    
    if (session === 'EXTENDED') {
        // Extended hours: Only LIMIT orders allowed
        orderTypeSelect.value = 'LIMIT';
        orderTypeSelect.disabled = true;
        
        // Show limit price field
        webullToggleLimitPrice('equity');
        
        // Update info text
        if (sessionInfoEl) {
            sessionInfoEl.innerHTML = `
                ⚠️ <strong>Extended Hours:</strong> Pre-market (4:00 AM - 9:30 AM ET) & After-hours (4:00 PM - 8:00 PM ET).<br>
                <span style="color: #dc2626;">Only LIMIT orders are allowed during extended hours.</span>
            `;
            sessionInfoEl.style.color = '#b45309';
        }
    } else {
        // Regular hours: All order types allowed
        orderTypeSelect.disabled = false;
        
        // Update info text
        if (sessionInfoEl) {
            sessionInfoEl.innerHTML = `
                ℹ️ <strong>Regular Hours:</strong> Submit during 9:30 AM - 4:00 PM ET. Market & Limit orders allowed.
            `;
            sessionInfoEl.style.color = '#666';
        }
    }
}

// Load config when tab is shown
function webullInit() {
    webullLoadConfig();
    webullLoadAccounts();
}

