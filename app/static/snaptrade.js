// SnapTrade Module - Connects to desktop proxy via ngrok

let snaptradeProxyUrl = '';

// Load proxy URL on page load
document.addEventListener('DOMContentLoaded', function() {
    snaptradeLoadProxyUrl();
});

async function snaptradeLoadProxyUrl() {
    try {
        const res = await fetch('/api/snaptrade/proxy-url');
        const data = await res.json();
        if (data.success && data.proxy_url) {
            snaptradeProxyUrl = data.proxy_url;
            document.getElementById('snaptrade-proxy-url').value = data.proxy_url;
            snaptradeCheckStatus();
        } else {
            document.getElementById('snaptrade-proxy-status').innerHTML = '<p style="color: #ef4444;">Not configured</p>';
        }
    } catch (error) {
        console.error('Failed to load proxy URL:', error);
    }
}

async function snaptradeSaveProxyUrl() {
    const url = document.getElementById('snaptrade-proxy-url').value.trim();
    if (!url) {
        alert('Please enter a proxy URL');
        return;
    }
    
    try {
        const res = await fetch('/api/snaptrade/proxy-url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ proxy_url: url })
        });
        const data = await res.json();
        if (data.success) {
            snaptradeProxyUrl = url;
            alert('✅ Proxy URL saved!');
            snaptradeCheckStatus();
        } else {
            alert('❌ Failed to save: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    }
}

async function snaptradeCheckStatus() {
    if (!snaptradeProxyUrl) {
        document.getElementById('snaptrade-proxy-status').innerHTML = '<p style="color: #ef4444;">Not configured</p>';
        return;
    }
    
    try {
        const res = await fetch('/api/snaptrade/status');
        const data = await res.json();
        if (data.success) {
            document.getElementById('snaptrade-proxy-status').innerHTML = '<p style="color: #10b981;">✅ Connected</p>';
            // Show other sections
            document.getElementById('snaptrade-accounts-section').style.display = 'block';
            document.getElementById('snaptrade-positions-section').style.display = 'block';
            document.getElementById('snaptrade-orders-section').style.display = 'block';
            document.getElementById('snaptrade-trade-section').style.display = 'block';
            document.getElementById('snaptrade-options-chain-section').style.display = 'block';
            snaptradeLoadAccounts();
        } else {
            document.getElementById('snaptrade-proxy-status').innerHTML = '<p style="color: #ef4444;">❌ Connection failed: ' + (data.error || 'Unknown error') + '</p>';
        }
    } catch (error) {
        document.getElementById('snaptrade-proxy-status').innerHTML = '<p style="color: #ef4444;">❌ Error: ' + error.message + '</p>';
    }
}

async function snaptradeLoadAccounts() {
    try {
        const res = await fetch('/api/snaptrade/accounts');
        const data = await res.json();
        if (data.success && data.accounts) {
            const accountsList = document.getElementById('snaptrade-accounts-list');
            const positionsSelect = document.getElementById('snaptrade-positions-account');
            const ordersSelect = document.getElementById('snaptrade-orders-account');
            const tradeSelect = document.getElementById('snaptrade-trade-account');
            const optionsChainSelect = document.getElementById('snaptrade-options-chain-account');
            
            // Clear existing options
            positionsSelect.innerHTML = '<option value="">Select Account</option>';
            ordersSelect.innerHTML = '<option value="">All Accounts</option>';
            tradeSelect.innerHTML = '<option value="">Use Last Account</option>';
            optionsChainSelect.innerHTML = '<option value="">Use Default Account</option>';
            
            if (data.accounts.length === 0) {
                accountsList.innerHTML = '<p>No accounts found</p>';
            } else {
                let html = '<div style="display: flex; flex-direction: column; gap: 10px;">';
                data.accounts.forEach(account => {
                    html += `<div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                        <strong>${account.name || account.account_id}</strong><br>
                        <small style="color: #666;">${account.account_id}</small>
                    </div>`;
                    
                    // Add to selects
                    const option = `<option value="${account.account_id}">${account.name || account.account_id}</option>`;
                    positionsSelect.innerHTML += option;
                    ordersSelect.innerHTML += option;
                    tradeSelect.innerHTML += option;
                    optionsChainSelect.innerHTML += option;
                });
                html += '</div>';
                accountsList.innerHTML = html;
            }
        } else {
            document.getElementById('snaptrade-accounts-list').innerHTML = '<p style="color: #ef4444;">Failed to load accounts: ' + (data.error || 'Unknown error') + '</p>';
        }
    } catch (error) {
        document.getElementById('snaptrade-accounts-list').innerHTML = '<p style="color: #ef4444;">Error: ' + error.message + '</p>';
    }
}

async function snaptradeLoadPositions() {
    const accountId = document.getElementById('snaptrade-positions-account').value;
    if (!accountId) {
        alert('Please select an account');
        return;
    }
    
    try {
        const res = await fetch(`/api/snaptrade/positions?account_id=${accountId}`);
        const data = await res.json();
        if (data.success) {
            const positionsList = document.getElementById('snaptrade-positions-list');
            positionsList.innerHTML = `<pre style="white-space: pre-wrap; background: #f5f5f5; padding: 10px; border-radius: 5px;">${data.positions || 'No positions'}</pre>`;
        } else {
            document.getElementById('snaptrade-positions-list').innerHTML = '<p style="color: #ef4444;">Failed: ' + (data.error || 'Unknown error') + '</p>';
        }
    } catch (error) {
        document.getElementById('snaptrade-positions-list').innerHTML = '<p style="color: #ef4444;">Error: ' + error.message + '</p>';
    }
}

async function snaptradeLoadOrders() {
    const accountId = document.getElementById('snaptrade-orders-account').value;
    
    try {
        const url = accountId ? `/api/snaptrade/orders?account_id=${accountId}` : '/api/snaptrade/orders';
        const res = await fetch(url);
        const data = await res.json();
        if (data.success) {
            const ordersList = document.getElementById('snaptrade-orders-list');
            ordersList.innerHTML = `<pre style="white-space: pre-wrap; background: #f5f5f5; padding: 10px; border-radius: 5px;">${data.orders || 'No orders'}</pre>`;
        } else {
            document.getElementById('snaptrade-orders-list').innerHTML = '<p style="color: #ef4444;">Failed: ' + (data.error || 'Unknown error') + '</p>';
        }
    } catch (error) {
        document.getElementById('snaptrade-orders-list').innerHTML = '<p style="color: #ef4444;">Error: ' + error.message + '</p>';
    }
}

function snaptradeToggleTradeType() {
    const tradeType = document.getElementById('snaptrade-trade-type').value;
    if (tradeType === 'equity') {
        document.getElementById('snaptrade-equity-trade-form').style.display = 'block';
        document.getElementById('snaptrade-option-trade-form').style.display = 'none';
    } else {
        document.getElementById('snaptrade-equity-trade-form').style.display = 'none';
        document.getElementById('snaptrade-option-trade-form').style.display = 'block';
    }
}

function snaptradeToggleEquityPrice() {
    const orderType = document.getElementById('snaptrade-equity-order-type').value;
    document.getElementById('snaptrade-equity-price-group').style.display = orderType === 'Limit' ? 'block' : 'none';
}

function snaptradeToggleOptionPrice() {
    const orderType = document.getElementById('snaptrade-option-order-type').value;
    document.getElementById('snaptrade-option-price-group').style.display = orderType === 'Limit' ? 'block' : 'none';
}

async function snaptradePlaceTrade() {
    const tradeType = document.getElementById('snaptrade-trade-type').value;
    const accountId = document.getElementById('snaptrade-trade-account').value;
    const resultDiv = document.getElementById('snaptrade-trade-result');
    
    resultDiv.innerHTML = '<p>Placing trade...</p>';
    
    let payload = {};
    if (accountId) {
        payload.account_id = accountId;
    }
    
    try {
        if (tradeType === 'equity') {
            payload.ticker = document.getElementById('snaptrade-equity-symbol').value.toUpperCase();
            payload.action = document.getElementById('snaptrade-equity-action').value;
            payload.quantity = parseInt(document.getElementById('snaptrade-equity-quantity').value);
            payload.orderType = document.getElementById('snaptrade-equity-order-type').value;
            payload.tif = document.getElementById('snaptrade-equity-time-in-force').value;
            if (payload.orderType === 'Limit') {
                payload.limitPrice = parseFloat(document.getElementById('snaptrade-equity-price').value);
            }
            
            const res = await fetch('/api/snaptrade/trade/equity', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (data.success) {
                resultDiv.innerHTML = `<div style="color: #10b981; padding: 10px; background: #d1fae5; border-radius: 5px;">
                    <strong>✅ Trade Placed Successfully!</strong><br>
                    <pre style="margin-top: 10px; white-space: pre-wrap;">${data.output || data.message || ''}</pre>
                </div>`;
            } else {
                // Check if this is a FOK cancellation (not a real error)
                const isFokCancellation = data.error && (
                    data.error.toLowerCase().includes('fok') && 
                    data.error.toLowerCase().includes('cancel')
                );
                
                if (isFokCancellation) {
                    // Yellow/orange color for FOK cancellation (expected behavior, not an error)
                    resultDiv.innerHTML = `<div style="color: #d97706; padding: 10px; background: #fef3c7; border-radius: 5px;">
                        <strong>⚠️ FOK: Order Not Filled - Cancelled</strong><br>
                        ${data.error || 'Order was placed but not filled within 3 seconds and was cancelled as expected.'}<br>
                        ${data.output ? '<pre style="margin-top: 10px; white-space: pre-wrap;">' + data.output + '</pre>' : ''}
                    </div>`;
                } else {
                    // Red color for actual errors
                    resultDiv.innerHTML = `<div style="color: #ef4444; padding: 10px; background: #fee2e2; border-radius: 5px;">
                        <strong>❌ Trade Failed</strong><br>
                        ${data.error || 'Unknown error'}<br>
                        ${data.output ? '<pre style="margin-top: 10px; white-space: pre-wrap;">' + data.output + '</pre>' : ''}
                    </div>`;
                }
            }
        } else {
            payload.ticker = document.getElementById('snaptrade-option-symbol').value.toUpperCase();
            payload.strike = parseFloat(document.getElementById('snaptrade-option-strike').value);
            payload.exp = document.getElementById('snaptrade-option-expiry').value;
            payload.optionType = document.getElementById('snaptrade-option-type').value;
            payload.action = document.getElementById('snaptrade-option-action').value;
            payload.contracts = parseInt(document.getElementById('snaptrade-option-contracts').value);
            payload.orderType = document.getElementById('snaptrade-option-order-type').value;
            payload.tif = document.getElementById('snaptrade-option-time-in-force').value;
            if (payload.orderType === 'Limit') {
                payload.limitPrice = parseFloat(document.getElementById('snaptrade-option-price').value);
            }
            
            const res = await fetch('/api/snaptrade/trade/option', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            
            if (data.success) {
                resultDiv.innerHTML = `<div style="color: #10b981; padding: 10px; background: #d1fae5; border-radius: 5px;">
                    <strong>✅ Trade Placed Successfully!</strong><br>
                    <pre style="margin-top: 10px; white-space: pre-wrap;">${data.output || data.message || ''}</pre>
                </div>`;
            } else {
                // Check if this is a FOK cancellation (not a real error)
                const isFokCancellation = data.error && (
                    data.error.toLowerCase().includes('fok') && 
                    data.error.toLowerCase().includes('cancel')
                );
                
                if (isFokCancellation) {
                    // Yellow/orange color for FOK cancellation (expected behavior, not an error)
                    resultDiv.innerHTML = `<div style="color: #d97706; padding: 10px; background: #fef3c7; border-radius: 5px;">
                        <strong>⚠️ FOK: Order Not Filled - Cancelled</strong><br>
                        ${data.error || 'Order was placed but not filled within 3 seconds and was cancelled as expected.'}<br>
                        ${data.output ? '<pre style="margin-top: 10px; white-space: pre-wrap;">' + data.output + '</pre>' : ''}
                    </div>`;
                } else {
                    // Red color for actual errors
                    resultDiv.innerHTML = `<div style="color: #ef4444; padding: 10px; background: #fee2e2; border-radius: 5px;">
                        <strong>❌ Trade Failed</strong><br>
                        ${data.error || 'Unknown error'}<br>
                        ${data.output ? '<pre style="margin-top: 10px; white-space: pre-wrap;">' + data.output + '</pre>' : ''}
                    </div>`;
                }
            }
        }
        
        // Refresh orders after placing trade
        setTimeout(() => snaptradeLoadOrders(), 2000);
    } catch (error) {
        resultDiv.innerHTML = `<div style="color: #ef4444; padding: 10px; background: #fee2e2; border-radius: 5px;">
            <strong>❌ Error</strong><br>
            ${error.message}
        </div>`;
    }
}

async function snaptradeLoadOptionsChain() {
    const symbol = document.getElementById('snaptrade-options-chain-symbol').value.trim().toUpperCase();
    const expiryDate = document.getElementById('snaptrade-options-chain-expiry').value;
    const accountId = document.getElementById('snaptrade-options-chain-account').value;
    const resultDiv = document.getElementById('snaptrade-options-chain-result');
    
    if (!symbol) {
        alert('Please enter a symbol');
        return;
    }
    
    resultDiv.innerHTML = '<p>⏳ Loading options chain...</p>';
    
    try {
        const params = new URLSearchParams({ symbol });
        if (expiryDate) {
            params.append('expiry_date', expiryDate);
        }
        if (accountId) {
            params.append('account_id', accountId);
        }
        
        const res = await fetch(`/api/snaptrade/options-chain?${params.toString()}`);
        const data = await res.json();
        
        if (data.success && data.chain) {
            const chains = data.chain;
            let html = `<div style="color: #10b981; padding: 10px; background: #d1fae5; border-radius: 5px; margin-bottom: 10px;">
                <strong>✅ Options Chain for ${symbol}</strong> (Source: ${data.source || 'yfinance'})`;
            if (data.filtered && chains.length > 0) {
                html += ` <span style="color: #059669;">- Filtered by date: ${chains[0].expiryDate}</span>`;
            } else if (data.available_dates) {
                html += ` <span style="color: #6b7280; font-size: 0.9em;">(${data.available_dates.length} expiration dates available)</span>`;
            }
            html += `</div>`;
            
            // Show available dates if not filtered
            if (!data.filtered && data.available_dates && data.available_dates.length > 0) {
                html += `<div style="padding: 10px; background: #f3f4f6; border-radius: 5px; margin-bottom: 10px; font-size: 0.9em;">
                    <strong>📅 Available Expiration Dates:</strong> ${data.available_dates.slice(0, 10).join(', ')}${data.available_dates.length > 10 ? '...' : ''}
                </div>`;
            }
            
            // Display the options chain data
            if (Array.isArray(chains) && chains.length > 0) {
                html += '<div style="overflow-x: auto;">';
                chains.forEach((chainItem, idx) => {
                    const expiryDate = chainItem.expiryDate || 'N/A';
                    html += `<div style="margin-bottom: 20px; padding: 15px; background: #f9fafb; border-radius: 5px; border: 1px solid #e5e7eb;">
                        <h3 style="margin-top: 0; color: #1f2937;">📅 Expiry: ${expiryDate}</h3>`;
                    
                    // Display Calls
                    if (chainItem.calls && Array.isArray(chainItem.calls) && chainItem.calls.length > 0) {
                        html += '<h4 style="color: #059669; margin-top: 15px;">📈 CALLS</h4>';
                        html += '<table style="width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 0.9em;">';
                        html += '<tr style="background: #d1fae5;"><th style="padding: 8px; text-align: left; border: 1px solid #e5e7eb;">Strike</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">Bid</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">Ask</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">Last</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">Vol</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">OI</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">IV</th><th style="padding: 8px; text-align: center; border: 1px solid #e5e7eb;">ITM</th></tr>';
                        chainItem.calls.forEach(call => {
                            const itm = call.inTheMoney ? '✅' : '❌';
                            html += `<tr style="${call.inTheMoney ? 'background: #f0fdf4;' : ''}">
                                <td style="padding: 8px; border: 1px solid #e5e7eb; font-weight: bold;">$${call.strike || 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">$${call.bid || 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">$${call.ask || 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">$${call.lastPrice || 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">${call.volume || '0'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">${call.openInterest || '0'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">${call.impliedVolatility ? (call.impliedVolatility * 100).toFixed(2) + '%' : 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: center;">${itm}</td>
                            </tr>`;
                        });
                        html += '</table>';
                    }
                    
                    // Display Puts
                    if (chainItem.puts && Array.isArray(chainItem.puts) && chainItem.puts.length > 0) {
                        html += '<h4 style="color: #dc2626; margin-top: 15px;">📉 PUTS</h4>';
                        html += '<table style="width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 0.9em;">';
                        html += '<tr style="background: #fee2e2;"><th style="padding: 8px; text-align: left; border: 1px solid #e5e7eb;">Strike</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">Bid</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">Ask</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">Last</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">Vol</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">OI</th><th style="padding: 8px; text-align: right; border: 1px solid #e5e7eb;">IV</th><th style="padding: 8px; text-align: center; border: 1px solid #e5e7eb;">ITM</th></tr>';
                        chainItem.puts.forEach(put => {
                            const itm = put.inTheMoney ? '✅' : '❌';
                            html += `<tr style="${put.inTheMoney ? 'background: #fef2f2;' : ''}">
                                <td style="padding: 8px; border: 1px solid #e5e7eb; font-weight: bold;">$${put.strike || 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">$${put.bid || 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">$${put.ask || 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">$${put.lastPrice || 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">${put.volume || '0'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">${put.openInterest || '0'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: right;">${put.impliedVolatility ? (put.impliedVolatility * 100).toFixed(2) + '%' : 'N/A'}</td>
                                <td style="padding: 8px; border: 1px solid #e5e7eb; text-align: center;">${itm}</td>
                            </tr>`;
                        });
                        html += '</table>';
                    }
                    
                    html += '</div>';
                });
                html += '</div>';
            } else {
                html += '<p>No options chain data available.</p>';
            }
            
            resultDiv.innerHTML = html;
        } else {
            resultDiv.innerHTML = `<div style="color: #ef4444; padding: 10px; background: #fee2e2; border-radius: 5px;">
                <strong>❌ Failed to Load Options Chain</strong><br>
                ${data.error || 'Unknown error'}
            </div>`;
        }
    } catch (error) {
        resultDiv.innerHTML = `<div style="color: #ef4444; padding: 10px; background: #fee2e2; border-radius: 5px;">
            <strong>❌ Error</strong><br>
            ${error.message}
        </div>`;
    }
}

