// Smart Trade Executor UI Logic

// Load enabled state on page load
async function smartExecutorLoadEnabled() {
    try {
        const response = await fetch('/api/smart-executor/enabled');
        const data = await response.json();
        
        if (data.success) {
            const enabled = data.enabled !== false; // Default to true if not set
            document.getElementById('smart-executor-enabled').checked = enabled;
            updateSmartExecutorStatus(enabled);
        }
    } catch (error) {
        console.error('Error loading enabled state:', error);
    }
}

// Toggle enabled state
async function smartExecutorToggleEnabled() {
    const enabled = document.getElementById('smart-executor-enabled').checked;
    
    try {
        const response = await fetch('/api/smart-executor/enabled', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateSmartExecutorStatus(enabled);
            const resultDiv = document.getElementById('executor-result');
            const message = enabled ? '✅ Smart Executor enabled' : '⚠️ Smart Executor disabled';
            const className = enabled ? 'success' : 'warning';
            resultDiv.innerHTML = `<div class="test-result ${className} show">${message}</div>`;
        } else {
            // Revert checkbox on error
            document.getElementById('smart-executor-enabled').checked = !enabled;
            const resultDiv = document.getElementById('executor-result');
            resultDiv.innerHTML = `<div class="test-result error show">Failed to update enabled state: ${data.error || 'Unknown error'}</div>`;
        }
    } catch (error) {
        // Revert checkbox on error
        document.getElementById('smart-executor-enabled').checked = !enabled;
        const resultDiv = document.getElementById('executor-result');
        resultDiv.innerHTML = `<div class="test-result error show">Error updating enabled state: ${error.message}</div>`;
    }
}

// Update status display
function updateSmartExecutorStatus(enabled) {
    const statusEl = document.getElementById('smart-executor-status');
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

// Execution history pagination
// Use globals (var) and guard against missing definitions to avoid "not defined" errors
if (typeof window !== "undefined") {
    window.allExecutionsData = window.allExecutionsData || [];
    window.visibleExecutionsCount = window.visibleExecutionsCount || 2;
    window.INITIAL_EXECUTIONS_LIMIT = window.INITIAL_EXECUTIONS_LIMIT || 2;
    window.EXECUTIONS_INCREMENT = window.EXECUTIONS_INCREMENT || 2;
}
var allExecutionsData = window.allExecutionsData; // Store all executions
var visibleExecutionsCount = window.visibleExecutionsCount; // Track how many executions are currently visible
var INITIAL_EXECUTIONS_LIMIT = window.INITIAL_EXECUTIONS_LIMIT; // Show only 2 most recent by default
var EXECUTIONS_INCREMENT = window.EXECUTIONS_INCREMENT; // Show 2 more executions each time "Show More" is clicked

// Style Clear History button with orangish-yellow color
function styleClearHistoryButton() {
    const buttons = document.querySelectorAll('button');
    buttons.forEach(button => {
        const text = button.textContent || button.innerText || '';
        const onclick = button.getAttribute('onclick') || '';
        // Match by text or onclick handler
        if ((text.toLowerCase().includes('clear') && text.toLowerCase().includes('history')) ||
            onclick.includes('executorClearHistory')) {
            button.style.background = '#fbbf24';
            button.style.color = '#92400e';
            button.style.border = 'none';
        }
    });
}

// Style buttons on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            styleClearHistoryButton();
        }, 500);
    });
} else {
    setTimeout(() => {
        styleClearHistoryButton();
    }, 500);
}

async function executorExecuteTrade() {
    const platform = document.getElementById('executor-platform').value;
    const signalTitle = document.getElementById('executor-signal-title')?.value?.trim() || '';
    const ticker = document.getElementById('executor-ticker').value.trim().toUpperCase();
    const direction = document.getElementById('executor-direction').value;
    const optionType = document.getElementById('executor-option-type').value;
    const strikePrice = parseFloat(document.getElementById('executor-strike').value);
    const purchasePrice = parseFloat(document.getElementById('executor-price').value);
    
    // Position size can be number or "lotto"
    const posSizeRaw = document.getElementById('executor-pos-size').value.trim();
    const posSize = posSizeRaw.toLowerCase() === 'lotto' ? 'lotto' : (parseInt(posSizeRaw) || 2);
    
    const month = document.getElementById('executor-month').value.trim();
    const day = document.getElementById('executor-day').value.trim();
    const year = document.getElementById('executor-year').value.trim();
    
    // Validate required fields
    if (!ticker || isNaN(strikePrice) || isNaN(purchasePrice)) {
        const resultDiv = document.getElementById('executor-result');
        resultDiv.innerHTML = '<div class="test-result error show">❌ Please fill in all required fields (Ticker, Strike Price, Purchase Price)</div>';
        return;
    }
    
    // Build signal data
    const signalData = {
        ticker,
        direction,
        option_type: optionType,
        strike_price: strikePrice,
        purchase_price: purchasePrice,
        input_position_size: posSize,
        signal_title: signalTitle
    };
    
    // Add date if provided
    if (month && day) {
        signalData.expiration_date = {
            year: year || null,
            month: month.padStart(2, '0'),
            day: day.padStart(2, '0')
        };
    }
    
    const resultDiv = document.getElementById('executor-result');
    
    // Show processing with input summary
    let processingHtml = '<div class="test-result info show">';
    processingHtml += '<h3 style="margin-top: 0;">🔄 Processing Smart Trade Execution...</h3>';
    processingHtml += '<div style="background: #f0f9ff; padding: 16px; border-radius: 8px; margin: 16px 0; border: 2px solid #0ea5e9;">';
    processingHtml += '<h4 style="margin: 0 0 12px 0;">📋 Input Summary</h4>';
    processingHtml += '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 0.9rem;">';
    processingHtml += `<div><strong>Platform:</strong> ${platform.toUpperCase()}</div>`;
    processingHtml += `<div><strong>Ticker:</strong> ${ticker}</div>`;
    processingHtml += `<div><strong>Direction:</strong> ${direction}</div>`;
    processingHtml += `<div><strong>Option Type:</strong> ${optionType}</div>`;
    processingHtml += `<div><strong>Strike Price:</strong> $${strikePrice.toFixed(2)}</div>`;
    processingHtml += `<div><strong>Purchase Price:</strong> $${purchasePrice.toFixed(2)}</div>`;
    processingHtml += `<div><strong>Position Size Input:</strong> ${posSize}</div>`;
    processingHtml += `<div><strong>Budget:</strong> <em>(determined by filters)</em></div>`;
    if (signalTitle) {
        processingHtml += `<div style="grid-column: 1 / -1;"><strong>Signal Title:</strong> ${signalTitle}</div>`;
    }
    if (month && day) {
        processingHtml += `<div style="grid-column: 1 / -1;"><strong>Expiration Date:</strong> ${month}/${day}${year ? '/' + year : ' (year will be inferred)'}</div>`;
    } else {
        processingHtml += `<div style="grid-column: 1 / -1;"><strong>Expiration Date:</strong> Not provided (will search for nearest)</div>`;
    }
    processingHtml += '</div></div>';
    
    // Add step progress indicators
    processingHtml += '<div style="margin: 20px 0;">';
    processingHtml += '<h4 style="margin: 0 0 12px 0;">🔄 Execution Steps</h4>';
    processingHtml += '<div style="display: grid; gap: 8px;">';
    for (let i = 1; i <= 6; i++) {
        const stepNames = {
            1: 'Validate Required Fields',
            2: 'Validate & Infer Date',
            3: 'Find Nearest Options Chain',
            4: 'Verify Strike Price',
            5: 'Calculate Position Size',
            6: 'Fill Order Incrementally'
        };
        processingHtml += `<div style="padding: 8px; background: #f3f4f6; border-radius: 4px; display: flex; align-items: center; gap: 8px;">`;
        processingHtml += `<span style="font-weight: bold; color: #6b7280;">Step ${i}:</span>`;
        processingHtml += `<span>${stepNames[i]}</span>`;
        processingHtml += `<span style="margin-left: auto; color: #6b7280;">⏳ Pending</span>`;
        processingHtml += `</div>`;
    }
    processingHtml += '</div></div>';
    processingHtml += '<div style="text-align: center; padding: 20px;"><div class="spinner" style="display: inline-block; width: 40px; height: 40px; border: 4px solid #f3f4f6; border-top: 4px solid #0ea5e9; border-radius: 50%; animation: spin 1s linear infinite;"></div></div>';
    processingHtml += '</div>';
    
    resultDiv.innerHTML = processingHtml;
    
    try {
        const res = await fetch('/api/executor/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                platform,
                signal_data: signalData
            })
        });
        
        const data = await res.json();
        
        // Build detailed result display
        let html = '';
        
        if (data.success) {
            html += '<div class="test-result success show">';
            html += '<h2 style="margin-top: 0; color: #059669;">✅ Trade Executed Successfully!</h2>';
            
            // Final Results Summary
            html += '<div style="background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); padding: 20px; border-radius: 8px; margin: 16px 0; border: 2px solid #059669; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">';
            html += '<h3 style="margin: 0 0 16px 0; color: #065f46;">📊 Execution Results</h3>';
            html += '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">';
            html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Order ID:</strong><br><span style="font-family: monospace; font-size: 0.9rem;">${data.order_id}</span></div>`;
            html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Filled Price:</strong><br><span style="color: #059669; font-weight: bold; font-size: 1.2rem;">$${data.filled_price.toFixed(2)}</span></div>`;
            html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Position Size:</strong><br><span style="font-weight: bold; font-size: 1.1rem;">${data.position_size} contracts</span></div>`;
            html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Expiration Date:</strong><br><span style="font-weight: bold;">${data.expiration_date}</span></div>`;
            html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Fill Attempts:</strong><br><span style="font-weight: bold;">${data.fill_attempts} of 14</span></div>`;
            html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Total Cost:</strong><br><span style="font-weight: bold; font-size: 1.1rem;">$${(data.filled_price * data.position_size * 100).toFixed(2)}</span></div>`;
            html += '</div></div>';
        } else {
            html += '<div class="test-result error show">';
            html += `<h2 style="margin-top: 0; color: #dc2626;">❌ Trade Execution Failed</h2>`;
            
            // Failure Summary
            html += '<div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); padding: 20px; border-radius: 8px; margin: 16px 0; border: 2px solid #dc2626; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">';
            html += '<h3 style="margin: 0 0 12px 0; color: #991b1b;">⚠️ Failure Information</h3>';
            html += `<div style="background: white; padding: 16px; border-radius: 6px; margin-bottom: 12px;">`;
            html += `<p style="margin: 0;"><strong>Failed at:</strong> <span style="color: #dc2626; font-weight: bold; font-size: 1.1rem;">Step ${data.step_failed}</span></p>`;
            html += `</div>`;
            html += `<div style="background: white; padding: 16px; border-radius: 6px;">`;
            html += `<p style="margin: 0 0 8px 0;"><strong>Error Message:</strong></p>`;
            html += `<p style="margin: 0; color: #991b1b; font-family: monospace; font-size: 0.95rem; line-height: 1.6;">${data.error}</p>`;
            html += `</div></div>`;
        }
        
        // Step-by-Step Breakdown
        html += '<div style="margin: 24px 0;">';
        html += '<h3 style="margin: 0 0 16px 0;">📋 Step-by-Step Execution Log</h3>';
        html += '<div style="background: #1e293b; color: #e2e8f0; padding: 20px; border-radius: 8px; max-height: 500px; overflow-y: auto; font-family: \'Courier New\', monospace; font-size: 0.85rem; line-height: 1.7; box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);">';
        
        // Parse and format the log
        if (data.log && data.log.length > 0) {
            data.log.forEach(line => {
                let color = '#e2e8f0'; // default
                let weight = 'normal';
                let bgColor = '';
                
                // Color coding based on content
                if (line.includes('✅') || line.includes('STEP') && line.includes('Complete')) {
                    color = '#4ade80'; // green
                    weight = 'bold';
                } else if (line.includes('❌') || line.includes('FAILED')) {
                    color = '#f87171'; // red
                    weight = 'bold';
                } else if (line.includes('⚠️')) {
                    color = '#fbbf24'; // yellow
                } else if (line.includes('STEP') || line.includes('===')) {
                    color = '#60a5fa'; // blue
                    weight = 'bold';
                } else if (line.includes('🔄')) {
                    color = '#a78bfa'; // purple
                } else if (line.includes('•')) {
                    color = '#d1d5db'; // light gray
                }
                
                html += `<div style="color: ${color}; font-weight: ${weight}; margin: 2px 0;">${escapeHtml(line)}</div>`;
            });
        } else {
            html += '<div style="color: #fbbf24;">No execution log available</div>';
        }
        
        html += '</div></div>';
        
        // Input Summary (reminder)
        html += '<div style="margin: 24px 0; padding: 16px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">';
        html += '<h4 style="margin: 0 0 12px 0; color: #475569;">📝 Input Data (For Reference)</h4>';
        html += '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 0.85rem;">';
        html += `<div><strong>Ticker:</strong> ${ticker}</div>`;
        html += `<div><strong>Direction:</strong> ${direction}</div>`;
        html += `<div><strong>Option Type:</strong> ${optionType}</div>`;
        html += `<div><strong>Strike:</strong> $${strikePrice.toFixed(2)}</div>`;
        html += `<div><strong>Purchase Price:</strong> $${purchasePrice.toFixed(2)}</div>`;
        html += `<div><strong>Pos. Size Input:</strong> ${posSize}</div>`;
        html += '</div></div>';
        
        html += '</div>';
        
        resultDiv.innerHTML = html;
        
        // Refresh history
        executorLoadHistory();
    } catch (error) {
        console.error('Executor error:', error);
        let errorHtml = '<div class="test-result error show">';
        errorHtml += '<h2 style="margin-top: 0; color: #dc2626;">❌ Network/Server Error</h2>';
        errorHtml += '<div style="background: #fee2e2; padding: 16px; border-radius: 8px; border: 1px solid #dc2626; margin: 16px 0;">';
        errorHtml += `<p style="margin: 0; color: #991b1b;"><strong>Error:</strong> ${error.message}</p>`;
        errorHtml += '<p style="margin: 8px 0 0 0; color: #7f1d1d; font-size: 0.9rem;">This may be a connection issue or the server may not be running.</p>';
        errorHtml += '</div>';
        errorHtml += '<div style="margin-top: 16px; padding: 12px; background: #fffbeb; border-radius: 6px; border: 1px solid #fbbf24;">';
        errorHtml += '<p style="margin: 0; color: #92400e; font-size: 0.9rem;"><strong>💡 Troubleshooting:</strong></p>';
        errorHtml += '<ul style="margin: 8px 0 0 0; padding-left: 20px; color: #92400e; font-size: 0.85rem;">';
        errorHtml += '<li>Ensure the TradeIQ server is running</li>';
        errorHtml += '<li>Check your network connection</li>';
        errorHtml += '<li>Check the browser console for detailed errors (F12)</li>';
        errorHtml += '<li>Verify API credentials are configured</li>';
        errorHtml += '</ul></div></div>';
        resultDiv.innerHTML = errorHtml;
    }
}

// Helper function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function executorLoadHistory(resetView = false) {
    const historyDiv = document.getElementById('executor-history');
    if (!historyDiv) return;
    
    // Reset view to show only recent executions if requested
    if (resetView) {
        visibleExecutionsCount = INITIAL_EXECUTIONS_LIMIT;
    }
    
    historyDiv.innerHTML = '<div class="test-result info show">Loading history...</div>';
    
    try {
        const res = await fetch('/api/executor/history?limit=100');
        const data = await res.json();
        
        if (data.success && data.executions && data.executions.length > 0) {
            // Store all executions
            allExecutionsData = data.executions;
            
            // Determine which executions to show based on visibleExecutionsCount
            const executionsToShow = allExecutionsData.slice(0, visibleExecutionsCount);
            
            // Create table format for execution history with horizontal scroll wrapper for mobile
            let tableHtml = `
                <div style="overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 0 -10px; padding: 0 10px;">
                <table style="width: 100%; min-width: 800px; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <thead>
                        <tr style="background: #f3f4f6; border-bottom: 2px solid #e5e7eb;">
                            <th style="padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Status</th>
                            <th style="padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Ticker</th>
                            <th style="padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Type</th>
                            <th style="padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Strike</th>
                            <th style="padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Direction</th>
                            <th style="padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Price</th>
                            <th style="padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Platform</th>
                            <th style="padding: 12px; text-align: left; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Date</th>
                            <th style="padding: 12px; text-align: center; font-weight: 600; font-size: 0.9rem; color: #374151; white-space: nowrap;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            executionsToShow.forEach(exec => {
                const statusColor = exec.status === 'success' ? '#10b981' : exec.status === 'failed' ? '#fbbf24' : '#f59e0b';
                const statusIcon = exec.status === 'success' ? '✅' : exec.status === 'failed' ? '' : '⏳';
                const filledPrice = exec.status === 'success' && exec.filled_price ? `$${exec.filled_price.toFixed(2)}` : '-';
                const positionSize = exec.status === 'success' && exec.final_position_size ? `${exec.final_position_size}` : '-';
                
                tableHtml += `
                    <tr style="border-bottom: 1px solid #e5e7eb; transition: background 0.2s;" onmouseover="this.style.background='#f9fafb'" onmouseout="this.style.background='white'">
                        <td style="padding: 12px;">
                            <span style="background: ${statusColor}; color: ${exec.status === 'failed' ? '#92400e' : 'white'}; padding: 4px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 500;">
                                ${exec.status.toUpperCase()}
                            </span>
                        </td>
                        <td style="padding: 12px; font-weight: 600;">${exec.ticker || '-'}</td>
                        <td style="padding: 12px;">${exec.option_type || '-'}</td>
                        <td style="padding: 12px;">${exec.strike_price ? `$${exec.strike_price}` : '-'}</td>
                        <td style="padding: 12px;">${exec.direction || '-'}</td>
                        <td style="padding: 12px;">
                            ${exec.status === 'success' ? `<span style="color: #059669; font-weight: bold;">${filledPrice}</span>` : `$${exec.purchase_price ? exec.purchase_price.toFixed(2) : '-'}`}
                            ${exec.status === 'success' && positionSize !== '-' ? `<br><small style="color: #6b7280;">${positionSize} contracts</small>` : ''}
                        </td>
                        <td style="padding: 12px; text-transform: uppercase; font-size: 0.85rem; color: #6b7280;">${exec.platform || '-'}</td>
                        <td style="padding: 12px; font-size: 0.85rem; color: #6b7280;">
                            ${new Date(exec.created_at).toLocaleDateString()}<br>
                            <small>${new Date(exec.created_at).toLocaleTimeString()}</small>
                        </td>
                        <td style="padding: 12px; text-align: center;">
                            <button onclick="executorDeleteExecution(${exec.id})" style="background: transparent; color: #6b7280; border: 1px solid #d1d5db; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 600;" title="Delete">🗑️</button>
                            ${exec.execution_log ? `<button onclick="toggleExecutionLog(${exec.id})" style="background: #f3f4f6; border: 1px solid #d1d5db; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; margin-left: 4px;" title="View Log">📋</button>` : ''}
                        </td>
                    </tr>
                `;
                
                if (exec.execution_log) {
                    tableHtml += `
                        <tr id="exec-log-row-${exec.id}" style="display: none;">
                            <td colspan="9" style="padding: 0;">
                                <pre id="exec-log-${exec.id}" style="background: #1e293b; color: #e2e8f0; padding: 16px; margin: 0; max-height: 300px; overflow-y: auto; font-size: 0.8rem; line-height: 1.4; white-space: pre-wrap; word-wrap: break-word;">${escapeHtml(exec.execution_log)}</pre>
                            </td>
                        </tr>
                    `;
                }
                
                if (exec.status === 'failed' && exec.error_message) {
                    tableHtml += `
                        <tr style="background: #fef2f2;">
                            <td colspan="9" style="padding: 12px; color: #991b1b; font-size: 0.85rem;">
                                <strong>Error:</strong> ${escapeHtml(exec.error_message)} ${exec.step_reached ? `| Step Failed: ${exec.step_reached}` : ''}
                            </td>
                        </tr>
                    `;
                }
            });
            
            tableHtml += `
                    </tbody>
                </table>
                </div>
            `;
            
            // Add "Show More" button if there are more executions
            if (allExecutionsData.length > visibleExecutionsCount) {
                const remainingCount = allExecutionsData.length - visibleExecutionsCount;
                const nextIncrement = Math.min(EXECUTIONS_INCREMENT, remainingCount);
                
                tableHtml += `
                    <div style="text-align: center; padding: 20px; margin-top: 20px;">
                        <button onclick="showMoreExecutions()" class="btn btn-secondary" style="padding: 10px 20px; font-size: 0.9rem; font-weight: 500;">
                            Show More (${nextIncrement} more execution${nextIncrement !== 1 ? 's' : ''})
                        </button>
                        ${visibleExecutionsCount > INITIAL_EXECUTIONS_LIMIT ? `
                            <button onclick="resetExecutionsView()" class="btn btn-secondary" style="padding: 10px 20px; font-size: 0.9rem; font-weight: 500; margin-left: 10px;">
                                Show Less
                            </button>
                        ` : ''}
                        <p style="margin: 8px 0 0 0; color: #6b7280; font-size: 0.85rem;">Showing ${visibleExecutionsCount} of ${allExecutionsData.length} executions</p>
                    </div>
                `;
            } else if (visibleExecutionsCount > INITIAL_EXECUTIONS_LIMIT && allExecutionsData.length === visibleExecutionsCount) {
                // All executions are shown, but more than initial limit
                tableHtml += `
                    <div style="text-align: center; padding: 20px; margin-top: 20px;">
                        <button onclick="resetExecutionsView()" class="btn btn-secondary" style="padding: 10px 20px; font-size: 0.9rem; font-weight: 500;">
                            Show Less (${INITIAL_EXECUTIONS_LIMIT} most recent)
                        </button>
                        <p style="margin: 8px 0 0 0; color: #6b7280; font-size: 0.85rem;">Showing all ${allExecutionsData.length} executions</p>
                    </div>
                `;
            }
            
            historyDiv.innerHTML = tableHtml;
            
            // Show scroll hint on mobile
            if (window.innerWidth <= 768) {
                const scrollHint = document.createElement('p');
                scrollHint.style.cssText = 'color: #6b7280; font-size: 0.8rem; margin-bottom: 8px; text-align: center;';
                scrollHint.innerHTML = '👆 Swipe left/right to see more columns';
                historyDiv.insertBefore(scrollHint, historyDiv.firstChild);
            }
            
            // Style Clear History button after loading
            setTimeout(() => {
                styleClearHistoryButton();
            }, 100);
        } else {
            historyDiv.innerHTML = '<div class="test-result info show">No execution history found.</div>';
        }
    } catch (error) {
        console.error('Error loading history:', error);
        historyDiv.innerHTML = `<div class="test-result error show">❌ Error loading history: ${error.message}</div>`;
    }
}

// Helper function to create execution card
function createExecutionCard(exec, stackIndex, isVisible) {
    const card = document.createElement('div');
    card.className = 'execution-card';
    card.setAttribute('data-exec-id', exec.id);
    card.setAttribute('data-stack-index', stackIndex);
    
    if (!isVisible) {
        card.classList.add('stacked');
    }
    
    const statusColor = exec.status === 'success' ? '#10b981' : exec.status === 'failed' ? '#fbbf24' : '#f59e0b';
    const statusIcon = exec.status === 'success' ? '✅' : exec.status === 'failed' ? '' : '⏳';
    
    let cardHtml = `<div style="background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; box-shadow: ${isVisible ? '0 8px 16px rgba(0,0,0,0.15)' : '0 2px 4px rgba(0,0,0,0.1)'}; transform-style: preserve-3d; transition: all 0.3s ease;">`;
    cardHtml += `<div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">`;
    cardHtml += `<div>`;
    cardHtml += `<div style="font-weight: bold; font-size: 1.2rem; margin-bottom: 4px;">${exec.ticker} ${exec.option_type} $${exec.strike_price}</div>`;
    cardHtml += `<div style="font-size: 0.85rem; color: #6b7280;">Platform: ${exec.platform.toUpperCase()} | ID: ${exec.id}</div>`;
    cardHtml += `</div>`;
    cardHtml += `<div style="display: flex; gap: 8px; align-items: center;">`;
    cardHtml += `<div style="background: ${statusColor}; color: ${exec.status === 'failed' ? '#92400e' : 'white'}; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 500;">${exec.status.toUpperCase()}</div>`;
    cardHtml += `<button onclick="executorDeleteExecution(${exec.id})" style="background: transparent; color: #6b7280; border: 1px solid #d1d5db; padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 600;">🗑️</button>`;
    cardHtml += `</div>`;
    cardHtml += `</div>`;
    
    cardHtml += `<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 0.9rem;">`;
    cardHtml += `<div><strong>Direction:</strong> ${exec.direction}</div>`;
    cardHtml += `<div><strong>Purchase Price:</strong> $${exec.purchase_price.toFixed(2)}</div>`;
    
    if (exec.status === 'success') {
        cardHtml += `<div><strong>Filled Price:</strong> <span style="color: #059669; font-weight: bold;">$${exec.filled_price.toFixed(2)}</span></div>`;
        cardHtml += `<div><strong>Position Size:</strong> ${exec.final_position_size} contracts</div>`;
        cardHtml += `<div><strong>Expiration:</strong> ${exec.final_expiration_date}</div>`;
        cardHtml += `<div><strong>Fill Attempts:</strong> ${exec.fill_attempts}</div>`;
    } else if (exec.status === 'failed') {
        cardHtml += `<div style="grid-column: 1 / -1;"><strong>Step Failed:</strong> ${exec.step_reached}</div>`;
        cardHtml += `<div style="grid-column: 1 / -1; color: #991b1b;"><strong>Error:</strong> ${escapeHtml(exec.error_message || 'N/A')}</div>`;
    }
    
    cardHtml += `</div>`;
    
    cardHtml += `<div style="margin-top: 12px; font-size: 0.8rem; color: #6b7280;">`;
    cardHtml += `<strong>Created:</strong> ${new Date(exec.created_at).toLocaleString()}`;
    if (exec.completed_at) {
        cardHtml += ` | <strong>Completed:</strong> ${new Date(exec.completed_at).toLocaleString()}`;
    }
    cardHtml += `</div>`;
    
    if (exec.execution_log) {
        cardHtml += `<div style="margin-top: 12px;">`;
        cardHtml += `<button onclick="toggleExecutionLog(${exec.id})" style="background: #f3f4f6; border: 1px solid #d1d5db; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">📋 View Execution Log</button>`;
        cardHtml += `<pre id="exec-log-${exec.id}" style="display: none; background: #1e293b; color: #e2e8f0; padding: 12px; border-radius: 4px; margin-top: 8px; max-height: 300px; overflow-y: auto; font-size: 0.8rem; line-height: 1.4;">${escapeHtml(exec.execution_log)}</pre>`;
        cardHtml += `</div>`;
    }
    
    cardHtml += `</div>`;
    card.innerHTML = cardHtml;
    
    return card;
}

function toggleExecutionLog(execId) {
    const logRow = document.getElementById(`exec-log-row-${execId}`);
    const logElement = document.getElementById(`exec-log-${execId}`);
    if (logRow) {
        logRow.style.display = logRow.style.display === 'none' ? '' : 'none';
    } else if (logElement) {
        // Fallback for old format
        logElement.style.display = logElement.style.display === 'none' ? 'block' : 'none';
    }
}

async function executorDeleteExecution(executionId) {
    if (!confirm(`Are you sure you want to delete execution #${executionId}? This action cannot be undone.`)) {
        return;
    }
    
    try {
        const res = await fetch(`/api/executor/history/${executionId}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        
        if (data.success) {
            executorLoadHistory();
        } else {
            alert(`❌ Failed to delete execution: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting execution:', error);
        alert(`❌ Error deleting execution: ${error.message}`);
    }
}

async function executorClearHistory() {
    console.log('executorClearHistory called');
    if (!confirm('Are you sure you want to clear ALL execution history? This action cannot be undone.')) {
        console.log('User cancelled clear history');
        return;
    }
    
    const historyDiv = document.getElementById('executor-history');
    if (historyDiv) {
        historyDiv.innerHTML = '<div class="test-result info show">Clearing history...</div>';
    }
    
    try {
        console.log('Sending DELETE request to /api/executor/history/clear');
        const res = await fetch('/api/executor/history/clear', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        console.log('Response status:', res.status);
        const data = await res.json();
        console.log('Response data:', data);
        
        if (data.success) {
            console.log('History cleared successfully, reloading...');
            await executorLoadHistory();
            alert('✅ All execution history cleared successfully');
        } else {
            console.error('Failed to clear history:', data.error);
            alert(`❌ Failed to clear history: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error clearing history:', error);
        alert(`❌ Error clearing history: ${error.message}`);
        if (historyDiv) {
            historyDiv.innerHTML = `<div class="test-result error show">❌ Error: ${error.message}</div>`;
        }
    }
}

// Show 2 more executions
function showMoreExecutions() {
    visibleExecutionsCount = Math.min(visibleExecutionsCount + EXECUTIONS_INCREMENT, allExecutionsData.length);
    executorLoadHistory();
}

// Reset to show only the 2 most recent executions
function resetExecutionsView() {
    visibleExecutionsCount = INITIAL_EXECUTIONS_LIMIT;
    executorLoadHistory();
}

// Auto-load history when tab is opened
document.addEventListener('DOMContentLoaded', function() {
    // This will be called by switchTab when executor tab is opened
    // Load filters when page loads
    loadBudgetFilters();
    loadSellingFilters();
});

// ==================== Budget Filters Management ====================

let budgetFilters = [];
let budgetFilterIdCounter = 0;

function addBudgetFilter() {
    budgetFilterIdCounter++;
    const filter = {
        id: budgetFilterIdCounter,
        signalFilter: '',
        budget: 350,
        lottoBudget: 100
    };
    budgetFilters.push(filter);
    renderBudgetFilters();
}

function removeBudgetFilter(filterId) {
    budgetFilters = budgetFilters.filter(f => f.id !== filterId);
    renderBudgetFilters();
}

function updateBudgetFilter(filterId, field, value) {
    const filter = budgetFilters.find(f => f.id === filterId);
    if (filter) {
        if (field === 'budget' || field === 'lottoBudget') {
            filter[field] = parseFloat(value) || 0;
        } else {
            filter[field] = value;
        }
    }
}

function renderBudgetFilters() {
    const container = document.getElementById('budget-filters-list');
    if (!container) return;
    
    if (budgetFilters.length === 0) {
        container.innerHTML = '<p style="color: #6b7280; font-style: italic;">No budget filters configured. Default budget will be used.</p>';
        return;
    }
    
    let html = '';
    budgetFilters.forEach((filter, index) => {
        html += `
            <div style="background: #f9fafb; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #e5e7eb;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <strong style="color: #374151;">Filter #${index + 1}</strong>
                    <button onclick="removeBudgetFilter(${filter.id})" style="background: #fee2e2; color: #dc2626; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">🗑️ Remove</button>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">
                    <div>
                        <label style="font-size: 0.85rem; color: #6b7280; display: block; margin-bottom: 4px;">Signal Title Filter (case-insensitive)</label>
                        <input type="text" value="${escapeHtml(filter.signalFilter)}" 
                               onchange="updateBudgetFilter(${filter.id}, 'signalFilter', this.value)"
                               placeholder="e.g., VIP, premium, scalp"
                               style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; box-sizing: border-box;">
                    </div>
                    <div>
                        <label style="font-size: 0.85rem; color: #6b7280; display: block; margin-bottom: 4px;">Budget ($)</label>
                        <input type="number" value="${filter.budget}" 
                               onchange="updateBudgetFilter(${filter.id}, 'budget', this.value)"
                               placeholder="350"
                               style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; box-sizing: border-box;">
                    </div>
                    <div>
                        <label style="font-size: 0.85rem; color: #6b7280; display: block; margin-bottom: 4px;">Lotto Budget ($) <small style="color: #9ca3af;">(when position_size=lotto)</small></label>
                        <input type="number" value="${filter.lottoBudget}" 
                               onchange="updateBudgetFilter(${filter.id}, 'lottoBudget', this.value)"
                               placeholder="100"
                               style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; box-sizing: border-box;">
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

async function saveBudgetFilters() {
    try {
        const res = await fetch('/api/executor/budget-filters', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filters: budgetFilters })
        });
        const data = await res.json();
        if (data.success) {
            alert('✅ Budget filters saved successfully!');
        } else {
            alert('❌ Failed to save: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error saving budget filters:', error);
        alert('❌ Error saving budget filters: ' + error.message);
    }
}

async function loadBudgetFilters() {
    try {
        const res = await fetch('/api/executor/budget-filters');
        const data = await res.json();
        if (data.success && data.filters) {
            budgetFilters = data.filters;
            // Reset counter to max id + 1
            budgetFilterIdCounter = budgetFilters.length > 0 
                ? Math.max(...budgetFilters.map(f => f.id || 0)) + 1 
                : 0;
            renderBudgetFilters();
        }
    } catch (error) {
        console.error('Error loading budget filters:', error);
    }
}

// ==================== Selling Strategy Filters Management ====================

let sellingFilters = [];
let sellingFilterIdCounter = 0;

function addSellingFilter() {
    sellingFilterIdCounter++;
    const filter = {
        id: sellingFilterIdCounter,
        signalFilter: '',
        sellPercentage: 80,      // % of position to sell
        profitMultiplier: 1.3    // 1.3x = 30% profit
    };
    sellingFilters.push(filter);
    renderSellingFilters();
}

function removeSellingFilter(filterId) {
    sellingFilters = sellingFilters.filter(f => f.id !== filterId);
    renderSellingFilters();
}

function updateSellingFilter(filterId, field, value) {
    const filter = sellingFilters.find(f => f.id === filterId);
    if (filter) {
        filter[field] = parseFloat(value) || 0;
    }
}

function updateSellingFilterText(filterId, field, value) {
    const filter = sellingFilters.find(f => f.id === filterId);
    if (filter) {
        filter[field] = value;
    }
}

function renderSellingFilters() {
    const container = document.getElementById('selling-filters-list');
    if (!container) return;
    
    if (sellingFilters.length === 0) {
        container.innerHTML = '<p style="color: #6b7280; font-style: italic;">No selling strategies configured. Default strategy will be used (sell 80% at 1.3x profit).</p>';
        return;
    }
    
    let html = '';
    sellingFilters.forEach((filter, index) => {
        const profitPct = ((filter.profitMultiplier - 1) * 100).toFixed(0);
        html += `
            <div style="background: #f0fdf4; padding: 15px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #bbf7d0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <strong style="color: #166534;">Strategy #${index + 1}</strong>
                    <button onclick="removeSellingFilter(${filter.id})" style="background: #fee2e2; color: #dc2626; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">🗑️ Remove</button>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">
                    <div>
                        <label style="font-size: 0.85rem; color: #6b7280; display: block; margin-bottom: 4px;">Signal Title Filter (case-insensitive)</label>
                        <input type="text" value="${escapeHtml(filter.signalFilter)}" 
                               onchange="updateSellingFilterText(${filter.id}, 'signalFilter', this.value)"
                               placeholder="e.g., VIP, swing, scalp"
                               style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; box-sizing: border-box;">
                    </div>
                    <div>
                        <label style="font-size: 0.85rem; color: #6b7280; display: block; margin-bottom: 4px;">Sell % of Position</label>
                        <input type="number" value="${filter.sellPercentage}" min="1" max="100"
                               onchange="updateSellingFilter(${filter.id}, 'sellPercentage', this.value)"
                               placeholder="80"
                               style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; box-sizing: border-box;">
                        <small style="color: #9ca3af;">1-100%</small>
                    </div>
                    <div>
                        <label style="font-size: 0.85rem; color: #6b7280; display: block; margin-bottom: 4px;">Profit Multiplier</label>
                        <input type="number" value="${filter.profitMultiplier}" step="0.1" min="1.01"
                               onchange="updateSellingFilter(${filter.id}, 'profitMultiplier', this.value)"
                               placeholder="1.3"
                               style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px; box-sizing: border-box;">
                        <small style="color: #9ca3af;">1.3 = 30% profit, 1.5 = 50% profit, 2.0 = 100% profit</small>
                    </div>
                </div>
                <p style="margin: 10px 0 0 0; font-size: 0.85rem; color: #166534; background: #dcfce7; padding: 8px; border-radius: 4px;">
                    📊 This strategy will sell <strong>${filter.sellPercentage}%</strong> of the position at <strong>${profitPct}% profit</strong> (${filter.profitMultiplier}x)
                </p>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

async function saveSellingFilters() {
    try {
        const res = await fetch('/api/executor/selling-filters', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filters: sellingFilters })
        });
        const data = await res.json();
        if (data.success) {
            alert('✅ Selling strategies saved successfully!');
        } else {
            alert('❌ Failed to save: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error saving selling filters:', error);
        alert('❌ Error saving selling strategies: ' + error.message);
    }
}

async function loadSellingFilters() {
    try {
        const res = await fetch('/api/executor/selling-filters');
        const data = await res.json();
        if (data.success && data.filters) {
            sellingFilters = data.filters;
            // Reset counter to max id + 1
            sellingFilterIdCounter = sellingFilters.length > 0 
                ? Math.max(...sellingFilters.map(f => f.id || 0)) + 1 
                : 0;
            renderSellingFilters();
        }
    } catch (error) {
        console.error('Error loading selling filters:', error);
    }
}

