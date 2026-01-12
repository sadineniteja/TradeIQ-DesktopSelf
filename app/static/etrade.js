// E*TRADE UI logic built on top of official Python client flows (rauth).

let etradeState = {
    authenticated: false,
  sandbox: true,
  defaultAccountId: null,
    accounts: [],
};

function etradeUpdateSavedStatus(data) {
  const sandboxStatus = document.getElementById('etrade-sandbox-status');
  const prodStatus = document.getElementById('etrade-prod-status');
  if (sandboxStatus) sandboxStatus.textContent = data.has_sandbox_keys ? 'Saved' : 'Not set';
  if (prodStatus) prodStatus.textContent = data.has_prod_keys ? 'Saved' : 'Not set';
  if (data.sandbox !== undefined) {
    const select = document.getElementById('etrade-sandbox-toggle');
    if (select) select.value = data.sandbox ? 'true' : 'false';
  }
}

async function etradeLoadConfig() {
  try {
    const res = await fetch('/api/etrade/config');
    const data = await res.json();
    if (data.success) {
      // Populate input fields with saved values
      const sandboxKeyInput = document.getElementById('etrade-sandbox-consumer-key');
      const sandboxSecretInput = document.getElementById('etrade-sandbox-consumer-secret');
      const prodKeyInput = document.getElementById('etrade-prod-consumer-key');
      const prodSecretInput = document.getElementById('etrade-prod-consumer-secret');
      
      if (sandboxKeyInput && data.sandbox_consumer_key) {
        sandboxKeyInput.value = data.sandbox_consumer_key;
      }
      if (sandboxSecretInput && data.sandbox_consumer_secret) {
        sandboxSecretInput.value = data.sandbox_consumer_secret;
      }
      if (prodKeyInput && data.prod_consumer_key) {
        prodKeyInput.value = data.prod_consumer_key;
      }
      if (prodSecretInput && data.prod_consumer_secret) {
        prodSecretInput.value = data.prod_consumer_secret;
      }
      
      etradeUpdateSavedStatus(data);
      etradeState.sandbox = data.sandbox;
    }
  } catch (err) {
    console.error('Config load error', err);
  }
}

async function etradeSaveConfig() {
  const sandboxKey = document.getElementById('etrade-sandbox-consumer-key').value.trim();
  const sandboxSecret = document.getElementById('etrade-sandbox-consumer-secret').value.trim();
  const prodKey = document.getElementById('etrade-prod-consumer-key').value.trim();
  const prodSecret = document.getElementById('etrade-prod-consumer-secret').value.trim();
  const sandbox = document.getElementById('etrade-sandbox-toggle').value === 'true';
  try {
    const res = await fetch('/api/etrade/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sandbox_consumer_key: sandboxKey,
        sandbox_consumer_secret: sandboxSecret,
        prod_consumer_key: prodKey,
        prod_consumer_secret: prodSecret,
        sandbox,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      etradeShowStatus(data.error || 'Failed to save config', 'error');
      return;
    }
    etradeShowStatus('Configuration saved. Proceed with OAuth.', 'success');
    etradeState.sandbox = sandbox;
    etradeUpdateSavedStatus(data);
  } catch (err) {
    etradeShowStatus(`Config save error: ${err}`, 'error');
  }
}

async function etradeTestKeys(isSandbox) {
  const key = isSandbox
    ? document.getElementById('etrade-sandbox-consumer-key').value.trim()
    : document.getElementById('etrade-prod-consumer-key').value.trim();
  const secret = isSandbox
    ? document.getElementById('etrade-sandbox-consumer-secret').value.trim()
    : document.getElementById('etrade-prod-consumer-secret').value.trim();
  
  const resultDiv = isSandbox
    ? document.getElementById('etrade-sandbox-test-result')
    : document.getElementById('etrade-prod-test-result');
  
  if (!key || !secret) {
    resultDiv.innerHTML = '<div class="test-result error show">⚠️ Please enter both key and secret before testing.</div>';
        return;
    }
  
  resultDiv.innerHTML = '<div class="test-result info show">🔄 Testing keys...</div>';
    
    try {
    const res = await fetch('/api/etrade/test-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ consumer_key: key, consumer_secret: secret, sandbox: isSandbox }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      resultDiv.innerHTML = `<div class="test-result error show">❌ <strong>Test Failed:</strong> ${data.error || 'Key test failed'}</div>`;
      return;
    }
    resultDiv.innerHTML = '<div class="test-result success show">✅ <strong>Test Succeeded!</strong> Keys are valid and working correctly.</div>';
  } catch (err) {
    resultDiv.innerHTML = `<div class="test-result error show">❌ <strong>Test Error:</strong> ${err.message || err}</div>`;
  }
}

function etradeShowStatus(message, type = 'info') {
  const el = document.getElementById('etrade-auth-status');
  if (!el) return;
  el.innerHTML = `<p class="${type}">${message}</p>`;
}

async function etradeCheckStatus() {
  try {
    const res = await fetch('/api/etrade/status');
    const data = await res.json();
    if (data.success === false && data.error) {
      etradeShowStatus(`Error: ${data.error}`, 'error');
      return;
    }
    etradeState.authenticated = data.authenticated;
    etradeState.sandbox = data.sandbox;
    etradeShowStatus(
      data.authenticated
        ? `Connected (${data.sandbox ? 'Sandbox' : 'Production'})`
        : 'Not authenticated',
      data.authenticated ? 'success' : 'warning'
    );
    if (data.authenticated) {
      document.getElementById('etrade-accounts-section').style.display = 'block';
      document.getElementById('etrade-balance-section').style.display = 'block';
      document.getElementById('etrade-portfolio-section').style.display = 'block';
      document.getElementById('etrade-orders-section').style.display = 'block';
      document.getElementById('etrade-order-status-section').style.display = 'block';
      document.getElementById('etrade-trade-section').style.display = 'block';
      document.getElementById('etrade-quote-section').style.display = 'block';
      document.getElementById('etrade-options-chain-section').style.display = 'block';
      document.getElementById('etrade-options-order-section').style.display = 'block';
      document.getElementById('etrade-equity-order-section').style.display = 'block';
      await etradeLoadAccounts();
      // Start auto-refresh for balance
      etradeStartBalanceAutoRefresh();
    }
  } catch (err) {
    etradeShowStatus(`Error checking status: ${err}`, 'error');
  }
}

async function etradeStartOAuth() {
  try {
    etradeShowStatus('Requesting authorization URL...', 'info');
    const res = await fetch('/api/etrade/oauth/request-token');
    const data = await res.json();
    if (!data.success) {
      etradeShowStatus(data.error || 'Failed to get request token', 'error');
      return;
    }
    const url = data.authorization_url;
    const linkHtml = `<a href="${url}" target="_blank">Open E*TRADE authorization</a>`;
    document.getElementById('etrade-auth-url').innerHTML = linkHtml;
    etradeShowStatus('Authorization URL retrieved. Open it and enter the verifier code.', 'success');
  } catch (err) {
    etradeShowStatus(`Error: ${err}`, 'error');
  }
}

async function etradeCompleteOAuth() {
  const verifier = document.getElementById('etrade-verifier').value.trim();
  if (!verifier) {
    etradeShowStatus('Please enter the verifier code.', 'warning');
    return;
  }
  try {
    etradeShowStatus('Completing OAuth...', 'info');
    const res = await fetch('/api/etrade/oauth/access-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verifier }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      etradeShowStatus(data.error || 'OAuth failed', 'error');
      return;
    }
    etradeShowStatus('Authenticated successfully.', 'success');
    etradeState.authenticated = true;
    await etradeLoadAccounts();
    document.getElementById('etrade-accounts-section').style.display = 'block';
    document.getElementById('etrade-balance-section').style.display = 'block';
    document.getElementById('etrade-portfolio-section').style.display = 'block';
    document.getElementById('etrade-orders-section').style.display = 'block';
    document.getElementById('etrade-trade-section').style.display = 'block';
    document.getElementById('etrade-quote-section').style.display = 'block';
    document.getElementById('etrade-equity-order-section').style.display = 'block';
    // Start auto-refresh for balance
    etradeStartBalanceAutoRefresh();
  } catch (err) {
    etradeShowStatus(`OAuth error: ${err}`, 'error');
  }
}

function etradeRenderAccounts(accounts) {
  const container = document.getElementById('etrade-accounts-list');
  if (!container) return;
  if (!accounts || !accounts.length) {
    container.innerHTML = '<p>No accounts found.</p>';
    return;
  }
  const items = accounts
    .map(
      (a) => `
      <div class="card account-card" data-account="${a.accountIdKey || a.accountId}">
        <div class="card-header">
          <strong>${a.accountDesc || 'Account'}</strong> (${a.accountIdKey || a.accountId})
                    </div>
        <div class="card-body">
          <p>Type: ${a.accountType || a.accountMode || 'N/A'}</p>
          <p>Status: ${a.accountStatus || 'N/A'}</p>
          <button class="btn btn-secondary" onclick="etradeSelectAccount('${
            a.accountIdKey || a.accountId
          }')">Select</button>
        </div>
      </div>`
    )
    .join('');
  container.innerHTML = items;
}

async function etradeLoadAccounts() {
  try {
    const res = await fetch('/api/etrade/accounts');
    const data = await res.json();
    if (!res.ok || !data.success) {
      etradeShowStatus(data.error || 'Failed to load accounts', 'error');
      return;
    }
    etradeState.accounts = data.accounts || [];
    etradeState.defaultAccountId = data.default_account_id || (data.accounts[0] && data.accounts[0].accountIdKey);
    etradeRenderAccounts(etradeState.accounts);
  } catch (err) {
    etradeShowStatus(`Error loading accounts: ${err}`, 'error');
  }
}

function etradeSelectAccount(accountId) {
  etradeState.defaultAccountId = accountId;
  etradeShowStatus(`Selected account: ${accountId}`, 'success');
}

// Auto-refresh interval for balance
let etradeBalanceRefreshInterval = null;

function formatBalanceData(balance) {
  if (!balance) return '<div class="test-result error show">No balance data available</div>';
  
  const cash = balance.Cash || {};
  const computed = balance.Computed || {};
  const realTime = computed.RealTimeValues || {};
  
  const formatCurrency = (val) => {
    if (val === null || val === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  };
  
  const formatDate = () => {
    return new Date().toLocaleString('en-US', { 
      hour12: true, 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  };
  
  return `
    <div class="balance-display">
      <div class="balance-header">
        <h3>Account Balance</h3>
        <span class="balance-timestamp">Last updated: ${formatDate()}</span>
      </div>
      
      <div class="balance-grid">
        <div class="balance-card primary">
          <div class="balance-label">Total Account Value</div>
          <div class="balance-value ${realTime.totalAccountValue >= 0 ? 'positive' : 'negative'}">
            ${formatCurrency(realTime.totalAccountValue)}
          </div>
        </div>
        
        <div class="balance-card">
          <div class="balance-label">Net Market Value</div>
          <div class="balance-value ${realTime.netMv >= 0 ? 'positive' : 'negative'}">
            ${formatCurrency(realTime.netMv)}
          </div>
        </div>
        
        <div class="balance-card">
          <div class="balance-label">Cash Balance</div>
          <div class="balance-value ${computed.cashBalance >= 0 ? 'positive' : 'negative'}">
            ${formatCurrency(computed.cashBalance)}
          </div>
        </div>
        
        <div class="balance-card">
          <div class="balance-label">Net Cash</div>
          <div class="balance-value ${computed.netCash >= 0 ? 'positive' : 'negative'}">
            ${formatCurrency(computed.netCash)}
          </div>
        </div>
        
        <div class="balance-card">
          <div class="balance-label">Available for Investment</div>
          <div class="balance-value ${computed.cashAvailableForInvestment >= 0 ? 'positive' : 'negative'}">
            ${formatCurrency(computed.cashAvailableForInvestment)}
          </div>
        </div>
        
        <div class="balance-card">
          <div class="balance-label">Available for Withdrawal</div>
          <div class="balance-value ${computed.cashAvailableForWithdrawal >= 0 ? 'positive' : 'negative'}">
            ${formatCurrency(computed.cashAvailableForWithdrawal)}
          </div>
        </div>
      </div>
      
      <div class="balance-details-section">
        <h4>Account Details</h4>
        <div class="balance-details-grid">
          <div class="detail-item">
            <span class="detail-label">Account ID:</span>
            <span class="detail-value">${balance.accountId || 'N/A'}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Account Type:</span>
            <span class="detail-value">${balance.accountType || 'N/A'}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Option Level:</span>
            <span class="detail-value">${balance.optionLevel || 'N/A'}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Money Market Balance:</span>
            <span class="detail-value">${formatCurrency(cash.moneyMktBalance)}</span>
          </div>
        </div>
      </div>
      
      <div class="balance-details-section">
        <h4>Additional Information</h4>
        <div class="balance-details-grid">
          <div class="detail-item">
            <span class="detail-label">Funds for Open Orders:</span>
            <span class="detail-value">${formatCurrency(cash.fundsForOpenOrdersCash)}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Settled Cash:</span>
            <span class="detail-value">${formatCurrency(computed.settledCashForInvestment)}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Unsettled Cash:</span>
            <span class="detail-value">${formatCurrency(computed.unSettledCashForInvestment)}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Open Calls:</span>
            <span class="detail-value">${formatCurrency(computed.OpenCalls?.cashCall || 0)}</span>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function etradeLoadBalance(showLoading = true) {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
    return;
  }
  const instType = document.getElementById('etrade-inst-type').value;
  const target = document.getElementById('etrade-balance-details');
  if (showLoading) {
    target.innerHTML = '<div class="test-result info show">Loading balance...</div>';
  }
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/balance?instType=${instType}`);
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Failed to load balance'}</div>`;
      return;
    }
    target.innerHTML = formatBalanceData(data.balance);
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ Error: ${err.message || err}</div>`;
  }
}

function etradeStartBalanceAutoRefresh() {
  // Clear any existing interval
  if (etradeBalanceRefreshInterval) {
    clearInterval(etradeBalanceRefreshInterval);
  }
  
  // Load balance immediately
  etradeLoadBalance(true);
  
  // Set up auto-refresh every 30 seconds
  etradeBalanceRefreshInterval = setInterval(() => {
    etradeLoadBalance(false); // Don't show loading message on auto-refresh
  }, 30000); // 30 seconds
}

function etradeStopBalanceAutoRefresh() {
  if (etradeBalanceRefreshInterval) {
    clearInterval(etradeBalanceRefreshInterval);
    etradeBalanceRefreshInterval = null;
  }
}

function formatPortfolioData(portfolio) {
  if (!portfolio) return '<div class="test-result error show">No portfolio data available</div>';
  
  const accountPortfolio = portfolio.AccountPortfolio;
  if (!accountPortfolio || !Array.isArray(accountPortfolio) || accountPortfolio.length === 0) {
    return '<div class="test-result info show">Portfolio is empty</div>';
  }
  
  const formatCurrency = (val) => {
    if (val === null || val === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  };
  
  const formatPercent = (val) => {
    if (val === null || val === undefined) return '0.00%';
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  };
  
  const formatDate = (timestamp) => {
    if (!timestamp || timestamp < 0) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  };
  
  const formatTime = (timestamp) => {
    if (!timestamp || timestamp < 0) return 'N/A';
    const date = new Date(timestamp * 1000); // E*TRADE uses seconds
    return date.toLocaleTimeString('en-US', { hour12: true, hour: '2-digit', minute: '2-digit' });
  };
  
  let html = '<div class="portfolio-display">';
  
  // Process all positions from all accounts
  let allPositions = [];
  accountPortfolio.forEach(account => {
    if (account.Position && Array.isArray(account.Position)) {
      account.Position.forEach(pos => {
        allPositions.push({ ...pos, accountId: account.accountId });
      });
    }
  });
  
  if (allPositions.length === 0) {
    return '<div class="test-result info show">No positions found</div>';
  }
  
  // Calculate totals
  const totalMarketValue = allPositions.reduce((sum, pos) => sum + (pos.marketValue || 0), 0);
  const totalDaysGain = allPositions.reduce((sum, pos) => sum + (pos.daysGain || 0), 0);
  const totalGain = allPositions.reduce((sum, pos) => sum + (pos.totalGain || 0), 0);
  
  // Summary section
  html += `
    <div class="portfolio-summary">
      <div class="summary-card">
        <div class="summary-label">Total Positions</div>
        <div class="summary-value">${allPositions.length}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">Total Market Value</div>
        <div class="summary-value ${totalMarketValue >= 0 ? 'positive' : 'negative'}">${formatCurrency(totalMarketValue)}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">Today's Gain/Loss</div>
        <div class="summary-value ${totalDaysGain >= 0 ? 'positive' : 'negative'}">${formatCurrency(totalDaysGain)}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">Total Gain/Loss</div>
        <div class="summary-value ${totalGain >= 0 ? 'positive' : 'negative'}">${formatCurrency(totalGain)}</div>
      </div>
    </div>
  `;

  const positionCards = allPositions.map(pos => {
    const symbol = pos.Product?.symbol || pos.symbolDescription || 'N/A';
    const positionType = pos.positionType || 'N/A';
    const quantity = pos.quantity || 0;
    const lastPrice = pos.Quick?.lastTrade || 0;
    const marketValue = pos.marketValue || 0;
    const costBasis = pos.totalCost || 0;
    const daysGain = pos.daysGain || 0;
    const daysGainPct = pos.daysGainPct || 0;
    const totalGain = pos.totalGain || 0;
    const totalGainPct = pos.totalGainPct || 0;
    const pctOfPortfolio = pos.pctOfPortfolio || 0;
    const dateAcquired = pos.dateAcquired;
    const change = pos.Quick?.change || 0;
    const changePct = pos.Quick?.changePct || 0;
    const lastTradeTime = pos.Quick?.lastTradeTime;

    const positionTypeBadge = positionType === 'LONG' ? '🔼 LONG' : '🔽 SHORT';
    const changeLabel = pos.Quick
      ? `${change >= 0 ? '↑' : '↓'} ${formatCurrency(Math.abs(change))} (${formatPercent(changePct)})`
      : 'N/A';

    return `
      <details class="position-card">
        <summary>
          <div class="position-summary">
            <span class="position-symbol">${symbol}</span>
            <span class="position-summary-value ${marketValue >= 0 ? 'positive' : 'negative'}">${formatCurrency(marketValue)}</span>
          </div>
          <div class="position-summary-meta">
            <span>${positionTypeBadge}</span>
            <span>Qty ${quantity}</span>
            <span>P&L ${formatCurrency(totalGain)}</span>
            <span>${formatPercent(totalGainPct)}</span>
          </div>
        </summary>
        <div class="position-details">
          <div class="position-detail-row"><span class="position-detail-label">Last Price</span><span>${formatCurrency(lastPrice)}</span></div>
          <div class="position-detail-row"><span class="position-detail-label">Cost Basis</span><span>${formatCurrency(costBasis)}</span></div>
          <div class="position-detail-row"><span class="position-detail-label">Today's P&L</span><span>${formatCurrency(daysGain)} (${formatPercent(daysGainPct)})</span></div>
          <div class="position-detail-row"><span class="position-detail-label">Total P&L</span><span>${formatCurrency(totalGain)} (${formatPercent(totalGainPct)})</span></div>
          <div class="position-detail-row"><span class="position-detail-label">% of Portfolio</span><span>${formatPercent(pctOfPortfolio * 100)}</span></div>
          <div class="position-detail-row"><span class="position-detail-label">Change</span><span>${changeLabel}</span></div>
          <div class="position-detail-row"><span class="position-detail-label">Last Trade</span><span>${formatTime(lastTradeTime)}</span></div>
          <div class="position-detail-row"><span class="position-detail-label">Date Acquired</span><span>${formatDate(dateAcquired)}</span></div>
        </div>
      </details>
    `;
  }).join('');

  // Positions table
  html += `
    <div class="portfolio-table-container desktop-only">
      <table class="positions-table">
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Position</th>
            <th>Quantity</th>
            <th>Last Price</th>
            <th>Market Value</th>
            <th>Cost Basis</th>
            <th>Today's P&L</th>
            <th>Total P&L</th>
            <th>% of Portfolio</th>
            <th>Date Acquired</th>
          </tr>
        </thead>
        <tbody>
  `;
  
  allPositions.forEach(pos => {
    const symbol = pos.Product?.symbol || pos.symbolDescription || 'N/A';
    const positionType = pos.positionType || 'N/A';
    const quantity = pos.quantity || 0;
    const lastPrice = pos.Quick?.lastTrade || 0;
    const marketValue = pos.marketValue || 0;
    const costBasis = pos.totalCost || 0;
    const daysGain = pos.daysGain || 0;
    const daysGainPct = pos.daysGainPct || 0;
    const totalGain = pos.totalGain || 0;
    const totalGainPct = pos.totalGainPct || 0;
    const pctOfPortfolio = pos.pctOfPortfolio || 0;
    const dateAcquired = pos.dateAcquired;
    const change = pos.Quick?.change || 0;
    const changePct = pos.Quick?.changePct || 0;
    const lastTradeTime = pos.Quick?.lastTradeTime;
    
    const positionTypeClass = positionType === 'LONG' ? 'position-long' : 'position-short';
    const positionTypeBadge = positionType === 'LONG' ? '🔼 LONG' : '🔽 SHORT';
    
    html += `
      <tr class="position-row">
        <td class="symbol-cell">
          <strong>${symbol}</strong>
          ${pos.Quick ? `
            <div class="quote-info">
              <span class="price-change ${change >= 0 ? 'positive' : 'negative'}">
                ${change >= 0 ? '↑' : '↓'} ${formatCurrency(Math.abs(change))} (${formatPercent(changePct)})
              </span>
              <span class="trade-time">${formatTime(lastTradeTime)}</span>
            </div>
          ` : ''}
        </td>
        <td><span class="position-badge ${positionTypeClass}">${positionTypeBadge}</span></td>
        <td class="quantity-cell">${quantity}</td>
        <td class="price-cell">${formatCurrency(lastPrice)}</td>
        <td class="value-cell ${marketValue >= 0 ? 'positive' : 'negative'}">${formatCurrency(marketValue)}</td>
        <td class="cost-cell">${formatCurrency(costBasis)}</td>
        <td class="gain-cell ${daysGain >= 0 ? 'positive' : 'negative'}">
          ${formatCurrency(daysGain)}
          <div class="gain-percent">${formatPercent(daysGainPct)}</div>
        </td>
        <td class="gain-cell ${totalGain >= 0 ? 'positive' : 'negative'}">
          ${formatCurrency(totalGain)}
          <div class="gain-percent">${formatPercent(totalGainPct)}</div>
        </td>
        <td class="percent-cell">${formatPercent(pctOfPortfolio * 100)}</td>
        <td class="date-cell">${formatDate(dateAcquired)}</td>
      </tr>
    `;
  });
  
  html += `
        </tbody>
      </table>
    </div>
  `;

  html += `
    <div class="positions-list mobile-only">
      ${positionCards}
    </div>
  `;
  
  html += '</div>';
  return html;
}

async function etradeLoadPortfolio() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
        return;
    }
  const target = document.getElementById('etrade-portfolio-list');
  target.innerHTML = '<div class="test-result info show">Loading portfolio...</div>';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/portfolio`);
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Failed to load portfolio'}</div>`;
      return;
    }
    target.innerHTML = formatPortfolioData(data.portfolio);
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ Error: ${err.message || err}</div>`;
  }
}

function formatOrdersData(orders) {
  if (!orders) return '<div class="test-result error show">No orders data available</div>';
  
  const orderList = orders.Order;
  if (!orderList || !Array.isArray(orderList) || orderList.length === 0) {
    return '<div class="test-result info show">No orders found</div>';
  }
  
  const formatCurrency = (val) => {
    if (val === null || val === undefined) return '$0.00';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);
  };
  
  const formatDate = (timestamp) => {
    if (!timestamp || timestamp < 0) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };
  
  const formatOrderType = (type) => {
    const types = {
      'EQ': 'Equity',
      'OPTN': 'Options',
      'SPREADS': 'Spreads',
      'ONE_CANCELS_ALL': 'One Cancels All',
      'BUTTERFLY': 'Butterfly',
      'IRON_CONDOR': 'Iron Condor'
    };
    return types[type] || type;
  };
  
  const formatStatus = (status) => {
    const statusMap = {
      'OPEN': { text: 'OPEN', class: 'status-open', icon: '⏳' },
      'EXECUTED': { text: 'EXECUTED', class: 'status-executed', icon: '✅' },
      'CANCELLED': { text: 'CANCELLED', class: 'status-cancelled', icon: '❌' },
      'REJECTED': { text: 'REJECTED', class: 'status-rejected', icon: '⚠️' },
      'EXPIRED': { text: 'EXPIRED', class: 'status-expired', icon: '⏰' },
      'FILLED': { text: 'FILLED', class: 'status-executed', icon: '✅' }
    };
    const statusInfo = statusMap[status] || { text: status, class: 'status-unknown', icon: '❓' };
    return `<span class="order-status ${statusInfo.class}">${statusInfo.icon} ${statusInfo.text}</span>`;
  };
  
  const formatInstrument = (instrument) => {
    const product = instrument.Product || {};
    const symbol = product.symbol || product.productId?.symbol || 'N/A';
    const securityType = product.securityType || 'N/A';
    const action = instrument.orderAction || 'N/A';
    const quantity = instrument.orderedQuantity || 0;
    const filledQty = instrument.filledQuantity || 0;
    const avgPrice = instrument.averageExecutionPrice || 0;
    const symbolDesc = instrument.symbolDescription || symbol;
    
    let instrumentHtml = `
      <div class="instrument-item">
        <div class="instrument-header">
          <strong class="instrument-symbol">${symbol}</strong>
          <span class="instrument-type">${securityType}</span>
        </div>
        <div class="instrument-details">
          <div class="detail-row">
            <span class="detail-label">Action:</span>
            <span class="detail-value action-${action.toLowerCase().replace('_', '-')}">${action}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Quantity:</span>
            <span class="detail-value">${quantity} ${filledQty > 0 ? `(${filledQty} filled)` : ''}</span>
          </div>
    `;
    
    if (securityType === 'OPTN') {
      const expiry = product.expiryYear && product.expiryMonth && product.expiryDay
        ? `${product.expiryMonth}/${product.expiryDay}/${product.expiryYear}`
        : 'N/A';
      const callPut = product.callPut || 'N/A';
      const strike = product.strikePrice || 0;
      
      instrumentHtml += `
          <div class="detail-row">
            <span class="detail-label">Option:</span>
            <span class="detail-value">${callPut} ${formatCurrency(strike)}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Expiry:</span>
            <span class="detail-value">${expiry}</span>
          </div>
      `;
    }
    
    if (avgPrice > 0) {
      instrumentHtml += `
          <div class="detail-row">
            <span class="detail-label">Avg Price:</span>
            <span class="detail-value">${formatCurrency(avgPrice)}</span>
          </div>
      `;
    }
    
    instrumentHtml += `
          <div class="detail-row">
            <span class="detail-label">Description:</span>
            <span class="detail-value">${symbolDesc}</span>
          </div>
        </div>
      </div>
    `;
    
    return instrumentHtml;
  };
  
  let html = '<div class="orders-display">';
  
  // Summary
  const openCount = orderList.filter(o => o.OrderDetail?.[0]?.status === 'OPEN').length;
  const executedCount = orderList.filter(o => o.OrderDetail?.[0]?.status === 'EXECUTED').length;
  const rejectedCount = orderList.filter(o => o.OrderDetail?.[0]?.status === 'REJECTED').length;
  
  html += `
    <div class="orders-summary">
      <div class="summary-item">
        <span class="summary-label">Total Orders:</span>
        <span class="summary-value">${orderList.length}</span>
      </div>
      ${openCount > 0 ? `<div class="summary-item"><span class="summary-label">Open:</span><span class="summary-value status-open">${openCount}</span></div>` : ''}
      ${executedCount > 0 ? `<div class="summary-item"><span class="summary-label">Executed:</span><span class="summary-value status-executed">${executedCount}</span></div>` : ''}
      ${rejectedCount > 0 ? `<div class="summary-item"><span class="summary-label">Rejected:</span><span class="summary-value status-rejected">${rejectedCount}</span></div>` : ''}
    </div>
  `;
  
  // Orders list
  html += '<div class="orders-list">';
  
  orderList.forEach(order => {
    const orderId = order.orderId || 'N/A';
    const orderType = formatOrderType(order.orderType || 'N/A');
    const orderDetails = order.OrderDetail || [];
    
    if (orderDetails.length === 0) return;
    
    const firstDetail = orderDetails[0];
    const status = firstDetail.status || 'UNKNOWN';
    const placedTime = firstDetail.placedTime;
    const executedTime = firstDetail.executedTime;
    const priceType = firstDetail.priceType || 'N/A';
    const limitPrice = firstDetail.limitPrice || 0;
    const stopPrice = firstDetail.stopPrice || 0;
    const orderTerm = firstDetail.orderTerm || 'N/A';
    const marketSession = firstDetail.marketSession || 'N/A';
    const orderValue = firstDetail.orderValue || 0;
    const estimatedCommission = orderDetails.reduce((sum, d) => {
      return sum + (d.Instrument?.reduce((s, i) => s + (i.estimatedCommission || 0), 0) || 0);
    }, 0);
    const totalCommission = order.totalCommission || estimatedCommission;
    const totalOrderValue = order.totalOrderValue || orderValue;
    
    html += `
      <div class="order-card">
        <div class="order-header">
          <div class="order-id-section">
            <span class="order-id-label">Order ID:</span>
            <strong class="order-id-value">${orderId}</strong>
            ${formatStatus(status)}
          </div>
          <div class="order-type-badge">${orderType}</div>
        </div>
        
        <div class="order-body">
          <div class="order-info-grid">
            <div class="info-item">
              <span class="info-label">Placed:</span>
              <span class="info-value">${formatDate(placedTime)}</span>
            </div>
            ${executedTime ? `
            <div class="info-item">
              <span class="info-label">Executed:</span>
              <span class="info-value">${formatDate(executedTime)}</span>
            </div>
            ` : ''}
            <div class="info-item">
              <span class="info-label">Price Type:</span>
              <span class="info-value">${priceType}</span>
            </div>
            ${limitPrice > 0 ? `
            <div class="info-item">
              <span class="info-label">Limit Price:</span>
              <span class="info-value">${formatCurrency(limitPrice)}</span>
            </div>
            ` : ''}
            ${stopPrice > 0 ? `
            <div class="info-item">
              <span class="info-label">Stop Price:</span>
              <span class="info-value">${formatCurrency(stopPrice)}</span>
            </div>
            ` : ''}
            <div class="info-item">
              <span class="info-label">Order Term:</span>
              <span class="info-value">${orderTerm}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Session:</span>
              <span class="info-value">${marketSession}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Order Value:</span>
              <span class="info-value">${formatCurrency(totalOrderValue)}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Commission:</span>
              <span class="info-value">${formatCurrency(totalCommission)}</span>
            </div>
          </div>
          
          <div class="instruments-section">
            <h4>Instruments (${orderDetails.length} ${orderDetails.length === 1 ? 'leg' : 'legs'}):</h4>
            <div class="instruments-list">
    `;
    
    orderDetails.forEach((detail, detailIdx) => {
      const instruments = detail.Instrument || [];
      instruments.forEach((instrument, instIdx) => {
        html += formatInstrument(instrument);
      });
    });
    
    html += `
            </div>
          </div>
        </div>
        
        ${status === 'OPEN' ? `
        <div class="order-actions">
          <button class="btn btn-danger btn-sm" onclick="etradeCancelOrderById(${orderId}, event)" title="Cancel this order">
            ❌ Cancel Order
          </button>
        </div>
        ` : ''}
      </div>
    `;
  });
  
  html += '</div></div>';
  return html;
}

async function etradeLoadOrders() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
    return;
  }
  const status = document.getElementById('etrade-order-status').value;
  const target = document.getElementById('etrade-orders-list');
  target.innerHTML = '<div class="test-result info show">Loading orders...</div>';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/orders?status=${status}`);
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Failed to load orders'}</div>`;
      return;
    }
    target.innerHTML = formatOrdersData(data.orders);
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ Error: ${err.message || err}</div>`;
  }
}

function etradeCancelOrderById(orderId, event) {
  if (!confirm(`Are you sure you want to cancel order #${orderId}?`)) {
    return;
  }
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
        return;
    }
    
  // Find the cancel button
  const cancelBtn = event ? event.target : document.querySelector(`button[onclick*="etradeCancelOrderById(${orderId})"]`);
  const originalText = cancelBtn ? cancelBtn.innerHTML : '';
  if (cancelBtn) {
    cancelBtn.innerHTML = 'Cancelling...';
    cancelBtn.disabled = true;
  }
  
  fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/cancel-order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ order_id: orderId.toString() }),
  })
  .then(res => res.json())
  .then(data => {
    if (!data.success) {
      etradeShowStatus(data.error || 'Failed to cancel order', 'error');
      if (cancelBtn) {
        cancelBtn.innerHTML = originalText;
        cancelBtn.disabled = false;
      }
        } else {
      etradeShowStatus(`Order #${orderId} cancelled successfully`, 'success');
      // Reload orders
      etradeLoadOrders();
    }
  })
  .catch(err => {
    etradeShowStatus(`Error: ${err.message || err}`, 'error');
    if (cancelBtn) {
      cancelBtn.innerHTML = originalText;
      cancelBtn.disabled = false;
    }
  });
}

async function etradeCancelOrder() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
    return;
  }
  const orderId = document.getElementById('etrade-cancel-id').value.trim();
  if (!orderId) {
    etradeShowStatus('Enter an order ID to cancel.', 'warning');
        return;
    }
  const target = document.getElementById('etrade-orders-list');
  target.innerHTML = 'Cancelling...';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/cancel-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ order_id: orderId }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `Error: ${data.error || 'Failed to cancel order'}`;
      return;
    }
    target.innerHTML = `<pre>${JSON.stringify(data.cancel || data, null, 2)}</pre>`;
  } catch (err) {
    target.innerHTML = `Error: ${err}`;
  }
}

async function etradeLookupOrderStatus() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
    return;
  }
  
  const orderId = document.getElementById('etrade-lookup-order-id').value.trim();
  if (!orderId) {
    etradeShowStatus('Please enter an Order ID.', 'warning');
    return;
  }
  
  const target = document.getElementById('etrade-order-status-result');
  target.innerHTML = '<div class="test-result info show">🔍 Searching for order...</div>';
  
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/orders/${orderId}`);
    const data = await res.json();
    
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Order not found'}</div>`;
      return;
    }
    
    const order = data.order;
    const status = data.status;
    const orderDetails = order.OrderDetail || [];
    const firstDetail = orderDetails[0] || {};
    
    // Format order status display
    let html = '<div class="orders-display">';
    html += '<div style="background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); padding: 20px; border-radius: 8px; margin-bottom: 16px; border: 2px solid #3b82f6;">';
    html += '<h3 style="margin: 0 0 16px 0; color: #1e40af;">📋 Order Details</h3>';
    
    // Order ID and Status
    const orderStatus = firstDetail.status || status || 'UNKNOWN';
    const statusMap = {
      'OPEN': { text: 'OPEN', icon: '⏳', color: '#f59e0b' },
      'EXECUTED': { text: 'EXECUTED', icon: '✅', color: '#059669' },
      'CANCELLED': { text: 'CANCELLED', icon: '❌', color: '#dc2626' },
      'REJECTED': { text: 'REJECTED', icon: '⚠️', color: '#dc2626' },
      'EXPIRED': { text: 'EXPIRED', icon: '⏰', color: '#7c3aed' },
      'FILLED': { text: 'FILLED', icon: '✅', color: '#059669' }
    };
    const statusInfo = statusMap[orderStatus] || { text: orderStatus, icon: '❓', color: '#6b7280' };
    
    html += `<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px;">`;
    html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Order ID:</strong><br><span style="font-family: monospace; font-size: 1.1rem; font-weight: bold;">${order.orderId || 'N/A'}</span></div>`;
    html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Status:</strong><br><span style="font-weight: bold; color: ${statusInfo.color}; font-size: 1.1rem;">${statusInfo.icon} ${statusInfo.text}</span></div>`;
    html += `</div>`;
    
    // Order Type and Details
    html += `<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px;">`;
    html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Order Type:</strong><br>${formatOrderType(order.orderType || 'N/A')}</div>`;
    html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Price Type:</strong><br>${firstDetail.priceType || 'N/A'}</div>`;
    html += `</div>`;
    
    // Prices
    if (firstDetail.limitPrice || firstDetail.stopPrice) {
      html += `<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px;">`;
      if (firstDetail.limitPrice) {
        html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Limit Price:</strong><br>$${parseFloat(firstDetail.limitPrice).toFixed(2)}</div>`;
      }
      if (firstDetail.stopPrice) {
        html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Stop Price:</strong><br>$${parseFloat(firstDetail.stopPrice).toFixed(2)}</div>`;
      }
      html += `</div>`;
    }
    
    // Timestamps
    html += `<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px;">`;
    if (firstDetail.placedTime) {
      const placedDate = new Date(parseInt(firstDetail.placedTime));
      html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Placed Time:</strong><br>${placedDate.toLocaleString()}</div>`;
    }
    if (firstDetail.executedTime) {
      const executedDate = new Date(parseInt(firstDetail.executedTime));
      html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Executed Time:</strong><br>${executedDate.toLocaleString()}</div>`;
    }
    html += `</div>`;
    
    // Instruments
    if (orderDetails.length > 0) {
      html += '<div style="background: white; padding: 16px; border-radius: 6px; margin-bottom: 16px;">';
      html += '<h4 style="margin: 0 0 12px 0;">Instruments:</h4>';
      
      orderDetails.forEach((detail, idx) => {
        const instruments = detail.Instrument || [];
        const instList = Array.isArray(instruments) ? instruments : [instruments];
        
        instList.forEach((inst, instIdx) => {
          html += '<div style="padding: 12px; background: #f9fafb; border-radius: 4px; margin-bottom: 8px; border-left: 3px solid #3b82f6;">';
          html += `<strong>Instrument ${idx + 1}-${instIdx + 1}:</strong><br>`;
          
          if (inst.Product) {
            const prod = inst.Product;
            html += `Symbol: <strong>${prod.symbol || 'N/A'}</strong><br>`;
            if (prod.securityType === 'OPTN') {
              html += `Type: ${prod.callPut || 'N/A'} | Strike: $${parseFloat(prod.strikePrice || 0).toFixed(2)}<br>`;
              html += `Expiry: ${prod.expiryMonth}/${prod.expiryDay}/${prod.expiryYear}<br>`;
            }
          }
          
          html += `Action: <strong>${inst.orderAction || 'N/A'}</strong><br>`;
          html += `Quantity: <strong>${inst.quantity || 'N/A'}</strong><br>`;
          
          if (inst.filledQuantity) {
            html += `Filled: <strong style="color: #059669;">${inst.filledQuantity}</strong><br>`;
          }
          if (inst.averageExecutionPrice) {
            html += `Avg Execution Price: <strong style="color: #059669;">$${parseFloat(inst.averageExecutionPrice).toFixed(2)}</strong><br>`;
          }
          
          html += '</div>';
        });
      });
      
      html += '</div>';
    }
    
    // Commission and Value
    if (firstDetail.orderValue || order.totalCommission) {
      html += `<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;">`;
      if (firstDetail.orderValue) {
        html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Order Value:</strong><br>$${parseFloat(firstDetail.orderValue).toFixed(2)}</div>`;
      }
      if (order.totalCommission) {
        html += `<div style="background: white; padding: 12px; border-radius: 6px;"><strong>Commission:</strong><br>$${parseFloat(order.totalCommission).toFixed(2)}</div>`;
      }
      html += `</div>`;
    }
    
    html += '</div>'; // Close gradient box
    
    // Raw JSON (collapsible)
    html += '<details style="margin-top: 16px;">';
    html += '<summary style="cursor: pointer; padding: 8px; background: #f3f4f6; border-radius: 4px; font-weight: 500;">📄 View Raw JSON</summary>';
    html += `<pre style="background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 4px; overflow-x: auto; margin-top: 8px; font-size: 0.85rem;">${JSON.stringify(order, null, 2)}</pre>`;
    html += '</details>';
    
    html += '</div>';
    target.innerHTML = html;
    
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ Error: ${err.message || err}</div>`;
  }
}

async function etradePreviewOrder() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
        return;
    }
  const xml = document.getElementById('etrade-order-xml').value;
  const target = document.getElementById('etrade-order-result');
  if (!xml.trim()) {
    target.innerHTML = 'Provide XML payload.';
    return;
  }
  target.innerHTML = 'Previewing...';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/preview-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/xml' },
      body: xml,
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `Error: ${data.error || 'Failed to preview order'}`;
      return;
    }
    target.innerHTML = `<pre>${JSON.stringify(data.preview, null, 2)}</pre>`;
  } catch (err) {
    target.innerHTML = `Error: ${err}`;
  }
}

async function etradePlaceOrder() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
        return;
    }
  const xml = document.getElementById('etrade-order-xml').value;
  const target = document.getElementById('etrade-order-result');
  if (!xml.trim()) {
    target.innerHTML = 'Provide XML payload.';
    return;
  }
  target.innerHTML = 'Placing order...';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/place-order`, {
            method: 'POST',
      headers: { 'Content-Type': 'application/xml' },
      body: xml,
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `Error: ${data.error || 'Failed to place order'}`;
      return;
    }
    target.innerHTML = `<pre>${JSON.stringify(data.order, null, 2)}</pre>`;
  } catch (err) {
    target.innerHTML = `Error: ${err}`;
  }
}

function formatQuoteData(quoteData) {
  if (!quoteData || !quoteData.QuoteData || quoteData.QuoteData.length === 0) {
    return '<div class="test-result error show">No quote data available</div>';
  }
  
  const quote = quoteData.QuoteData[0];
  const all = quote.All || {};
  const product = quote.Product || {};
  const extendedHour = all.ExtendedHourQuoteDetail || {};
  
  // Helper function to format currency
  const formatCurrency = (value) => {
    if (value === null || value === undefined || value === '') return 'N/A';
    return '$' + parseFloat(value).toFixed(2);
  };
  
  // Helper function to format number
  const formatNumber = (value) => {
    if (value === null || value === undefined || value === '') return 'N/A';
    return parseFloat(value).toLocaleString();
  };
  
  // Helper function to format percentage
  const formatPercent = (value) => {
    if (value === null || value === undefined || value === '') return 'N/A';
    const num = parseFloat(value);
    return (num >= 0 ? '+' : '') + num.toFixed(2) + '%';
  };
  
  // Determine if market is open or closed
  const isAfterHours = quote.ahFlag === 'true' || extendedHour.quoteStatus;
  const quoteStatus = quote.quoteStatus || 'UNKNOWN';
  const isExtendedHours = isAfterHours && extendedHour.lastPrice;
  
  // Current price (use extended hours if available, otherwise regular)
  const currentPrice = isExtendedHours ? extendedHour.lastPrice : all.lastTrade;
  const change = isExtendedHours ? extendedHour.change : all.changeClose;
  const percentChange = isExtendedHours ? extendedHour.percentChange : all.changeClosePercentage;
  const isPositive = change >= 0;
  
  let html = `
    <div class="quote-display-container">
      <!-- Header -->
      <div class="quote-header">
        <div class="quote-symbol-section">
          <h3 class="quote-symbol">${product.symbol || 'N/A'}</h3>
          <div class="quote-company-name">${all.companyName || all.symbolDescription || 'N/A'}</div>
          <div class="quote-exchange">${all.primaryExchange || 'N/A'}</div>
        </div>
        <div class="quote-status-badge status-${quoteStatus.toLowerCase()}">
          ${quoteStatus.replace(/_/g, ' ')}
        </div>
      </div>
      
      <!-- Price Section -->
      <div class="quote-price-section">
        <div class="quote-main-price ${isPositive ? 'positive' : 'negative'}">
          ${formatCurrency(currentPrice)}
        </div>
        <div class="quote-change">
          <span class="change-amount ${isPositive ? 'positive' : 'negative'}">
            ${isPositive ? '+' : ''}${formatCurrency(change)}
          </span>
          <span class="change-percent ${isPositive ? 'positive' : 'negative'}">
            (${formatPercent(percentChange)})
          </span>
        </div>
        ${isExtendedHours ? `
          <div class="quote-extended-hours-badge">
            ⏰ Extended Hours: ${formatCurrency(extendedHour.lastPrice)}
            ${extendedHour.change ? `(${isPositive ? '+' : ''}${formatCurrency(extendedHour.change)})` : ''}
          </div>
        ` : ''}
      </div>
      
      <!-- Trading Info Grid -->
      <div class="quote-info-grid">
        <div class="quote-info-card">
          <div class="quote-info-label">Bid</div>
          <div class="quote-info-value">${formatCurrency(isExtendedHours ? extendedHour.bid : all.bid)}</div>
          <div class="quote-info-sub">Size: ${formatNumber(isExtendedHours ? extendedHour.bidSize : all.bidSize)}</div>
        </div>
        <div class="quote-info-card">
          <div class="quote-info-label">Ask</div>
          <div class="quote-info-value">${formatCurrency(isExtendedHours ? extendedHour.ask : all.ask)}</div>
          <div class="quote-info-sub">Size: ${formatNumber(isExtendedHours ? extendedHour.askSize : all.askSize)}</div>
        </div>
        <div class="quote-info-card">
          <div class="quote-info-label">Previous Close</div>
          <div class="quote-info-value">${formatCurrency(all.previousClose)}</div>
        </div>
        <div class="quote-info-card">
          <div class="quote-info-label">Open</div>
          <div class="quote-info-value">${formatCurrency(all.open)}</div>
        </div>
        <div class="quote-info-card">
          <div class="quote-info-label">Day High</div>
          <div class="quote-info-value positive">${formatCurrency(all.high)}</div>
        </div>
        <div class="quote-info-card">
          <div class="quote-info-label">Day Low</div>
          <div class="quote-info-value negative">${formatCurrency(all.low)}</div>
        </div>
        <div class="quote-info-card">
          <div class="quote-info-label">Volume</div>
          <div class="quote-info-value">${formatNumber(all.totalVolume || all.volume)}</div>
          <div class="quote-info-sub">Avg: ${formatNumber(all.averageVolume)}</div>
        </div>
        <div class="quote-info-card">
          <div class="quote-info-label">52 Week High</div>
          <div class="quote-info-value positive">${formatCurrency(all.high52)}</div>
        </div>
        <div class="quote-info-card">
          <div class="quote-info-label">52 Week Low</div>
          <div class="quote-info-value negative">${formatCurrency(all.low52)}</div>
        </div>
      </div>
      
      <!-- Company Metrics -->
      <div class="quote-metrics-section">
        <h4>📈 Company Metrics</h4>
        <div class="quote-metrics-grid">
          <div class="quote-metric-item">
            <span class="metric-label">Market Cap</span>
            <span class="metric-value">${formatCurrency(all.marketCap / 1000000)}M</span>
          </div>
          <div class="quote-metric-item">
            <span class="metric-label">P/E Ratio</span>
            <span class="metric-value">${all.pe ? all.pe.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="quote-metric-item">
            <span class="metric-label">EPS</span>
            <span class="metric-value">${formatCurrency(all.eps)}</span>
          </div>
          <div class="quote-metric-item">
            <span class="metric-label">Beta</span>
            <span class="metric-value">${all.beta ? all.beta.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="quote-metric-item">
            <span class="metric-label">Dividend</span>
            <span class="metric-value">${formatCurrency(all.dividend)}</span>
          </div>
          <div class="quote-metric-item">
            <span class="metric-label">Yield</span>
            <span class="metric-value">${all.yield ? (all.yield * 100).toFixed(2) + '%' : 'N/A'}</span>
          </div>
          <div class="quote-metric-item">
            <span class="metric-label">Shares Outstanding</span>
            <span class="metric-value">${formatNumber(all.sharesOutstanding)}</span>
          </div>
        </div>
      </div>
      
      <!-- Timestamp -->
      <div class="quote-timestamp">
        Last Updated: ${quote.dateTime || 'N/A'}
      </div>
    </div>
  `;
  
  return html;
}

async function etradeGetQuote() {
  const symbol = document.getElementById('etrade-quote-symbol').value.trim();
  const target = document.getElementById('etrade-quote-details');
    if (!symbol) {
    target.innerHTML = '<div class="test-result error show">Enter a symbol.</div>';
        return;
    }
  target.innerHTML = '<div class="test-result info show">Loading quote...</div>';
  try {
    const res = await fetch(`/api/etrade/quote/${encodeURIComponent(symbol)}`);
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">Error: ${data.error || 'Failed to get quote'}</div>`;
      return;
    }
    // Use the formatted display function
    target.innerHTML = formatQuoteData(data.quote);
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">Error: ${err.message || err}</div>`;
  }
}

function formatOptionChainData(chain) {
  if (!chain || !chain.OptionChainResponse) {
    return '<div class="test-result error show">No option chain data available</div>';
  }
  
  const response = chain.OptionChainResponse;
  const optionPairs = response.OptionPair || [];
  
  if (optionPairs.length === 0) {
    return '<div class="test-result info show">No options found for this criteria</div>';
  }
  
  const selectedED = response.SelectedED || {};
  const expiryDate = `${selectedED.month}/${selectedED.day}/${selectedED.year}`;
  
  // Check if user might want more strikes
  const wantsMoreStrikes = optionPairs.length === 1;
  
  const formatCurrency = (val) => {
    if (val === null || val === undefined) return '-';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(val);
  };
  
  const formatNumber = (val, decimals = 4) => {
    if (val === null || val === undefined) return '-';
    return parseFloat(val).toFixed(decimals);
  };
  
  const formatPercent = (val) => {
    if (val === null || val === undefined) return '-';
    return `${(val * 100).toFixed(2)}%`;
  };
  
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      etradeShowStatus(`Copied ${text} to clipboard`, 'success');
    });
  };
  
  const populateOrderForm = (osiKey, optionType) => {
    document.getElementById('etrade-opt-order-symbol').value = osiKey;
    etradeShowStatus(`${optionType} option loaded into order form`, 'success');
    // Scroll to order form
    document.getElementById('etrade-options-order-section').scrollIntoView({ behavior: 'smooth' });
  };
  
  let html = '<div class="option-chain-display">';
  
  // Header
  html += `
    <div class="option-chain-header">
      <h3>Options Chain</h3>
      <div class="chain-info">
        <span class="chain-expiry">📅 Expiration: <strong>${expiryDate}</strong></span>
        <span class="chain-count">📊 ${optionPairs.length} Strike${optionPairs.length !== 1 ? 's' : ''}</span>
      </div>
    </div>
  `;
  
  // Show helpful message if only 1 strike returned
  if (wantsMoreStrikes) {
    // Get the params that were used (from localStorage or window object if we set it)
    const lastParams = window.lastOptionChainParams || {};
    html += `
      <div class="test-result warning show" style="margin-bottom: 15px;">
        ⚠️ Only 1 strike returned by E*TRADE API. 
        ${lastParams.strikePriceNear && lastParams.noOfStrikes ? 
          `<br><strong>Debug:</strong> You requested ${lastParams.noOfStrikes} strikes near $${lastParams.strikePriceNear}, but E*TRADE only returned 1 strike.
          <br>This may mean:
          <br>• The strike price you entered doesn't exist for this expiration
          <br>• E*TRADE has limited data for this option
          <br>• Try a different "Strike Near" value (e.g., use the current stock price)
          <br>• Check the terminal/server logs for E*TRADE's raw response` :
          `<br><strong>To get multiple strikes:</strong> Fill in both "Strike Near" (e.g., current stock price like 500) and "Number of Strikes" (e.g., 10) in the form above.`
        }
      </div>
    `;
  }
  
  // Legend
  html += `
    <div class="option-chain-legend">
      <div class="legend-item"><span class="legend-dot itm"></span> In The Money</div>
      <div class="legend-item"><span class="legend-dot otm"></span> Out of The Money</div>
      <div class="legend-item"><span class="legend-info">💡 Click osiKey to load into order form</span></div>
    </div>
  `;
  
  const optionCards = optionPairs.map(pair => {
    const call = pair.Call || {};
    const put = pair.Put || {};
    const strikePrice = call.strikePrice || put.strikePrice || 0;

    const callITM = call.inTheMoney === 'y';
    const putITM = put.inTheMoney === 'y';

    const callGreeks = call.OptionGreeks || {};
    const putGreeks = put.OptionGreeks || {};

    const callOsiKey = call.osiKey || '';
    const putOsiKey = put.osiKey || '';

    return `
      <details class="option-chain-card">
        <summary>
          <div class="option-chain-summary">
            <span class="option-chain-strike">Strike ${formatCurrency(strikePrice)}</span>
            <span class="option-chain-prices">Call ${formatCurrency(call.lastPrice)} · Put ${formatCurrency(put.lastPrice)}</span>
          </div>
        </summary>
        <div class="option-chain-details">
          <div class="option-side-card">
            <div class="option-side-title">📈 Call ${callITM ? 'ITM' : 'OTM'}</div>
            <div class="option-detail-row"><span class="option-detail-label">Bid / Ask</span><span>${formatCurrency(call.bid)} / ${formatCurrency(call.ask)}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">Last</span><span>${formatCurrency(call.lastPrice)}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">Change</span><span>${call.netChange ? (call.netChange >= 0 ? '+' : '') + formatCurrency(call.netChange) : '-'}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">Volume / OI</span><span>${call.volume || 0} / ${call.openInterest ? call.openInterest.toLocaleString() : 0}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">IV</span><span>${formatPercent(callGreeks.iv)}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">Greeks</span><span>Δ ${formatNumber(callGreeks.delta)} · Γ ${formatNumber(callGreeks.gamma)} · Θ ${formatNumber(callGreeks.theta)}</span></div>
            ${callOsiKey ? `
              <div class="option-actions">
                <button class="osikey-btn" onclick="navigator.clipboard.writeText('${callOsiKey}').then(() => etradeShowStatus('Copied ${callOsiKey}', 'success'))">📋 Copy</button>
                <button class="osikey-btn" onclick="event.preventDefault(); const el=document.getElementById('etrade-opt-order-symbol'); el.value='${callOsiKey}'; el.scrollIntoView({behavior:'smooth'}); etradeShowStatus('CALL loaded into order form', 'success');">Load</button>
              </div>
            ` : '<div class="option-detail-row"><span class="option-detail-label">OSI Key</span><span>-</span></div>'}
          </div>
          <div class="option-side-card">
            <div class="option-side-title">📉 Put ${putITM ? 'ITM' : 'OTM'}</div>
            <div class="option-detail-row"><span class="option-detail-label">Bid / Ask</span><span>${formatCurrency(put.bid)} / ${formatCurrency(put.ask)}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">Last</span><span>${formatCurrency(put.lastPrice)}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">Change</span><span>${put.netChange ? (put.netChange >= 0 ? '+' : '') + formatCurrency(put.netChange) : '-'}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">Volume / OI</span><span>${put.volume || 0} / ${put.openInterest ? put.openInterest.toLocaleString() : 0}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">IV</span><span>${formatPercent(putGreeks.iv)}</span></div>
            <div class="option-detail-row"><span class="option-detail-label">Greeks</span><span>Δ ${formatNumber(putGreeks.delta)} · Γ ${formatNumber(putGreeks.gamma)} · Θ ${formatNumber(putGreeks.theta)}</span></div>
            ${putOsiKey ? `
              <div class="option-actions">
                <button class="osikey-btn" onclick="navigator.clipboard.writeText('${putOsiKey}').then(() => etradeShowStatus('Copied ${putOsiKey}', 'success'))">📋 Copy</button>
                <button class="osikey-btn" onclick="event.preventDefault(); const el=document.getElementById('etrade-opt-order-symbol'); el.value='${putOsiKey}'; el.scrollIntoView({behavior:'smooth'}); etradeShowStatus('PUT loaded into order form', 'success');">Load</button>
              </div>
            ` : '<div class="option-detail-row"><span class="option-detail-label">OSI Key</span><span>-</span></div>'}
          </div>
        </div>
      </details>
    `;
  }).join('');

  // Table
  html += `
    <div class="option-chain-table-container desktop-only">
      <table class="option-chain-table">
        <thead>
          <tr>
            <th colspan="9" class="section-header call-header">CALLS</th>
            <th class="strike-header">STRIKE</th>
            <th colspan="9" class="section-header put-header">PUTS</th>
          </tr>
          <tr class="sub-header">
            <!-- Calls -->
            <th class="osikey-col">osiKey</th>
            <th>Last</th>
            <th>Change</th>
            <th>Bid</th>
            <th>Ask</th>
            <th>Vol</th>
            <th>OI</th>
            <th>IV</th>
            <th class="greeks-col">Greeks</th>
            
            <!-- Strike -->
            <th class="strike-col">Price</th>
            
            <!-- Puts -->
            <th class="greeks-col">Greeks</th>
            <th>IV</th>
            <th>OI</th>
            <th>Vol</th>
            <th>Ask</th>
            <th>Bid</th>
            <th>Change</th>
            <th>Last</th>
            <th class="osikey-col">osiKey</th>
          </tr>
        </thead>
        <tbody>
  `;
  
  optionPairs.forEach(pair => {
    const call = pair.Call || {};
    const put = pair.Put || {};
    const strikePrice = call.strikePrice || put.strikePrice || 0;
    
    const callITM = call.inTheMoney === 'y';
    const putITM = put.inTheMoney === 'y';
    
    const callGreeks = call.OptionGreeks || {};
    const putGreeks = put.OptionGreeks || {};
    
    const callBidAskSpread = call.ask && call.bid ? call.ask - call.bid : 0;
    const putBidAskSpread = put.ask && put.bid ? put.ask - put.bid : 0;
    
    html += `
      <tr class="option-row">
        <!-- CALL DATA -->
        <td class="osikey-cell ${callITM ? 'itm' : 'otm'}">
          <button class="osikey-btn" onclick="navigator.clipboard.writeText('${call.osiKey}').then(() => etradeShowStatus('Copied ${call.osiKey}', 'success'))" title="Copy to clipboard">
            📋
          </button>
          <a href="#" class="osikey-link" onclick="event.preventDefault(); const el=document.getElementById('etrade-opt-order-symbol'); el.value='${call.osiKey}'; el.scrollIntoView({behavior:'smooth'}); etradeShowStatus('CALL loaded into order form', 'success');" title="Load into order form">
            ${call.osiKey || '-'}
          </a>
        </td>
        <td class="price-cell ${callITM ? 'itm' : 'otm'}">${formatCurrency(call.lastPrice)}</td>
        <td class="change-cell ${call.netChange >= 0 ? 'positive' : 'negative'} ${callITM ? 'itm' : 'otm'}">
          ${call.netChange ? (call.netChange >= 0 ? '+' : '') + formatCurrency(call.netChange) : '-'}
        </td>
        <td class="price-cell ${callITM ? 'itm' : 'otm'}">${formatCurrency(call.bid)}</td>
        <td class="price-cell ${callITM ? 'itm' : 'otm'}">${formatCurrency(call.ask)}</td>
        <td class="volume-cell ${callITM ? 'itm' : 'otm'}">${call.volume || 0}</td>
        <td class="oi-cell ${callITM ? 'itm' : 'otm'}">${call.openInterest ? call.openInterest.toLocaleString() : 0}</td>
        <td class="iv-cell ${callITM ? 'itm' : 'otm'}">${formatPercent(callGreeks.iv)}</td>
        <td class="greeks-cell ${callITM ? 'itm' : 'otm'}">
          <div class="greeks-tooltip">
            <span class="greeks-icon">📈</span>
            <div class="greeks-popup">
              <div class="greeks-row"><span>Δ Delta:</span> <span>${formatNumber(callGreeks.delta)}</span></div>
              <div class="greeks-row"><span>Γ Gamma:</span> <span>${formatNumber(callGreeks.gamma)}</span></div>
              <div class="greeks-row"><span>Θ Theta:</span> <span>${formatNumber(callGreeks.theta)}</span></div>
              <div class="greeks-row"><span>V Vega:</span> <span>${formatNumber(callGreeks.vega)}</span></div>
              <div class="greeks-row"><span>ρ Rho:</span> <span>${formatNumber(callGreeks.rho)}</span></div>
            </div>
          </div>
        </td>
        
        <!-- STRIKE PRICE -->
        <td class="strike-cell">${formatCurrency(strikePrice)}</td>
        
        <!-- PUT DATA -->
        <td class="greeks-cell ${putITM ? 'itm' : 'otm'}">
          <div class="greeks-tooltip">
            <span class="greeks-icon">📈</span>
            <div class="greeks-popup">
              <div class="greeks-row"><span>Δ Delta:</span> <span>${formatNumber(putGreeks.delta)}</span></div>
              <div class="greeks-row"><span>Γ Gamma:</span> <span>${formatNumber(putGreeks.gamma)}</span></div>
              <div class="greeks-row"><span>Θ Theta:</span> <span>${formatNumber(putGreeks.theta)}</span></div>
              <div class="greeks-row"><span>V Vega:</span> <span>${formatNumber(putGreeks.vega)}</span></div>
              <div class="greeks-row"><span>ρ Rho:</span> <span>${formatNumber(putGreeks.rho)}</span></div>
            </div>
          </div>
        </td>
        <td class="iv-cell ${putITM ? 'itm' : 'otm'}">${formatPercent(putGreeks.iv)}</td>
        <td class="oi-cell ${putITM ? 'itm' : 'otm'}">${put.openInterest ? put.openInterest.toLocaleString() : 0}</td>
        <td class="volume-cell ${putITM ? 'itm' : 'otm'}">${put.volume || 0}</td>
        <td class="price-cell ${putITM ? 'itm' : 'otm'}">${formatCurrency(put.ask)}</td>
        <td class="price-cell ${putITM ? 'itm' : 'otm'}">${formatCurrency(put.bid)}</td>
        <td class="change-cell ${put.netChange >= 0 ? 'positive' : 'negative'} ${putITM ? 'itm' : 'otm'}">
          ${put.netChange ? (put.netChange >= 0 ? '+' : '') + formatCurrency(put.netChange) : '-'}
        </td>
        <td class="price-cell ${putITM ? 'itm' : 'otm'}">${formatCurrency(put.lastPrice)}</td>
        <td class="osikey-cell ${putITM ? 'itm' : 'otm'}">
          <a href="#" class="osikey-link" onclick="event.preventDefault(); const el=document.getElementById('etrade-opt-order-symbol'); el.value='${put.osiKey}'; el.scrollIntoView({behavior:'smooth'}); etradeShowStatus('PUT loaded into order form', 'success');" title="Load into order form">
            ${put.osiKey || '-'}
          </a>
          <button class="osikey-btn" onclick="navigator.clipboard.writeText('${put.osiKey}').then(() => etradeShowStatus('Copied ${put.osiKey}', 'success'))" title="Copy to clipboard">
            📋
          </button>
        </td>
      </tr>
    `;
  });
  
  html += `
        </tbody>
      </table>
    </div>
  `;

  html += `
    <div class="option-chain-list mobile-only">
      ${optionCards}
    </div>
  `;
  
  html += '</div>';
  return html;
}

async function etradeGetExpirationDates() {
  const symbolInput = document.getElementById('etrade-exp-dates-symbol');
  const resultDiv = document.getElementById('etrade-expiration-dates-result');
  
  if (!symbolInput || !resultDiv) {
    console.error('Expiration dates UI elements not found');
    return;
  }
  
  const symbol = symbolInput.value.trim().toUpperCase();
  if (!symbol) {
    resultDiv.innerHTML = '<div class="test-result error show">⚠️ Please enter a symbol</div>';
    return;
  }
  
  resultDiv.innerHTML = '<div class="test-result info show">Loading expiration dates...</div>';
  
  try {
    const res = await fetch(`/api/etrade/options/expiration-dates?symbol=${encodeURIComponent(symbol)}`);
    const data = await res.json();
    
    if (res.ok && data.success) {
      const dates = data.expiration_dates || [];
      const nearestDate = data.nearest_date;
      
      if (dates.length === 0) {
        resultDiv.innerHTML = '<div class="test-result warning show">⚠️ No expiration dates found for this symbol</div>';
        return;
      }
      
      // Create a nice display with clickable dates
      let html = `<div class="test-result success show" style="max-height: 400px; overflow-y: auto;">`;
      html += `<div style="margin-bottom: 8px;"><strong>✅ Found ${dates.length} expiration date(s) for ${symbol}</strong></div>`;
      
      if (nearestDate) {
        html += `<div style="margin-bottom: 12px; padding: 8px; background: #e8f5e9; border-radius: 4px; border-left: 3px solid #4caf50;">`;
        html += `<strong>📅 Nearest Date:</strong> <span style="font-family: monospace; font-weight: bold; color: #2e7d32;">${nearestDate}</span>`;
        html += `</div>`;
      }
      
      html += `<div style="margin-top: 12px;"><strong>All Available Dates:</strong></div>`;
      html += `<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; margin-top: 8px;">`;
      
      dates.forEach((date, index) => {
        const dateStr = date.date_string;
        const isNearest = dateStr === nearestDate;
        const dateDisplay = `${date.month}/${date.day}/${date.year}`;
        
        html += `<div style="
          padding: 8px;
          background: ${isNearest ? '#e8f5e9' : '#f5f5f5'};
          border: 1px solid ${isNearest ? '#4caf50' : '#ddd'};
          border-radius: 4px;
          cursor: pointer;
          text-align: center;
          transition: all 0.2s;
          ${isNearest ? 'font-weight: bold;' : ''}
        " 
        onclick="etradeSelectExpirationDate('${dateStr}')"
        onmouseover="this.style.background='${isNearest ? '#c8e6c9' : '#e0e0e0'}'; this.style.transform='scale(1.02)'"
        onmouseout="this.style.background='${isNearest ? '#e8f5e9' : '#f5f5f5'}'; this.style.transform='scale(1)'"
        title="Click to use this date">
          <div style="font-size: 0.85rem; color: #666;">${dateDisplay}</div>
          <div style="font-size: 0.75rem; color: #999; margin-top: 2px; font-family: monospace;">${dateStr}</div>
          ${isNearest ? '<div style="font-size: 0.7rem; color: #4caf50; margin-top: 2px;">⭐ Nearest</div>' : ''}
        </div>`;
      });
      
      html += `</div>`;
      html += `<div style="margin-top: 8px; font-size: 0.85rem; color: #666;">💡 Click any date to auto-fill the expiry field below</div>`;
      html += `</div>`;
      
      resultDiv.innerHTML = html;
    } else {
      const errorMsg = data.error || 'Failed to get expiration dates';
      resultDiv.innerHTML = `<div class="test-result error show">❌ ${errorMsg}</div>`;
    }
  } catch (error) {
    console.error('Error fetching expiration dates:', error);
    resultDiv.innerHTML = `<div class="test-result error show">❌ Error: ${error.message}</div>`;
  }
}

function etradeSelectExpirationDate(dateStr) {
  // Auto-fill the expiry field in the options chain section
  const expiryInput = document.getElementById('etrade-opt-expiry');
  if (expiryInput) {
    expiryInput.value = dateStr;
    expiryInput.style.background = '#e8f5e9';
    setTimeout(() => {
      expiryInput.style.background = '';
    }, 2000);
    
    // Also auto-fill the symbol if it's empty
    const symbolInput = document.getElementById('etrade-opt-symbol');
    const expDatesSymbolInput = document.getElementById('etrade-exp-dates-symbol');
    if (symbolInput && expDatesSymbolInput && !symbolInput.value.trim()) {
      symbolInput.value = expDatesSymbolInput.value.trim().toUpperCase();
    }
  }
}

async function etradeLoadOptionChain() {
  const symbol = document.getElementById('etrade-opt-symbol').value.trim();
  const expiry = document.getElementById('etrade-opt-expiry').value.trim();
  const strikeNear = document.getElementById('etrade-opt-strike-near').value.trim();
  const strikeCount = document.getElementById('etrade-opt-strike-count').value.trim();
  const includeWeekly = document.getElementById('etrade-opt-include-weekly').value === 'true';
  const target = document.getElementById('etrade-options-chain');
  
  if (!symbol || !expiry) {
    target.innerHTML = '<div class="test-result error show">Symbol and expiry are required.</div>';
    return;
  }
  
  // Validate that both strikeNear and strikeCount are provided together
  if ((strikeNear && !strikeCount) || (!strikeNear && strikeCount)) {
    target.innerHTML = '<div class="test-result error show">⚠️ To get multiple strikes, you must provide BOTH "Strike Near" and "Number of Strikes". Leave both empty to get all available strikes.</div>';
    return;
  }
  
  target.innerHTML = '<div class="test-result info show">Loading option chain...</div>';
  try {
    const [y, m, d] = expiry.split('-');
    const params = new URLSearchParams({
      symbol,
      expiryYear: y,
      expiryMonth: m,
      expiryDay: d,
      includeWeekly: includeWeekly ? 'true' : 'false',
    });
    if (strikeNear) params.append('strikePriceNear', strikeNear);
    if (strikeCount) params.append('noOfStrikes', strikeCount);
    const requestUrl = `/api/etrade/options/chain?${params.toString()}`;
    
    // Store params for debugging
    window.lastOptionChainParams = {
      symbol,
      expiryYear: y,
      expiryMonth: m,
      expiryDay: d,
      strikePriceNear: strikeNear || null,
      noOfStrikes: strikeCount || null,
      includeWeekly: includeWeekly
    };
    
    console.log('Options chain request URL:', requestUrl);
    console.log('Parameters:', window.lastOptionChainParams);
    
    const res = await fetch(requestUrl);
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Failed to load option chain'}</div>`;
        return;
    }
    
    // Log what we received
    const optionPairs = data.chain?.OptionChainResponse?.OptionPair || [];
    console.log('Received strikes:', optionPairs.length);
    
    target.innerHTML = formatOptionChainData(data.chain);
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ ${err.message || err}</div>`;
  }
}

function formatOptionsOrderPreview(preview) {
  if (!preview) return '<div class="test-result error show">No preview data available</div>';
  
  const formatCurrency = (val) => {
    if (val === null || val === undefined || val === 0) return '$0.00';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(val);
  };
  
  const formatDate = (timestamp) => {
    if (!timestamp || timestamp < 0) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true
    });
  };
  
  const orders = preview.Order || [];
  const previewIds = preview.PreviewIds || [];
  const disclosure = preview.Disclosure || {};
  const portfolioMargin = preview.PortfolioMargin || {};
  
  let html = '<div class="order-preview-display">';
  
  // Header
  html += `
    <div class="preview-header">
      <h3>📋 Order Preview</h3>
      <div class="preview-time">Preview Time: ${formatDate(preview.previewTime)}</div>
    </div>
  `;
  
  // Preview ID
  if (previewIds.length > 0) {
    // E*TRADE API uses "PreviewId" (capital P) inside PreviewIds array
    const previewId = previewIds[0].PreviewId || previewIds[0].previewId;
    html += `
      <div class="preview-id-section">
        <div class="preview-id-badge">
          <span class="preview-id-label">Preview ID:</span>
          <strong class="preview-id-value">${previewId}</strong>
        </div>
        <div class="preview-id-note">Use this ID to place the order</div>
      </div>
    `;
  }
  
  // Process each order
  orders.forEach((order, orderIdx) => {
    const instruments = order.Instrument || [];
    const messages = order.messages?.Message || [];
    const messageList = Array.isArray(messages) ? messages : [messages];
    
    html += `
      <div class="preview-order-card">
        <div class="order-card-header">
          <h4>Order ${orderIdx + 1}${orders.length > 1 ? ` of ${orders.length}` : ''}</h4>
          <span class="order-type-badge">${preview.orderType || 'OPTN'}</span>
        </div>
        
        <div class="order-details-section">
    `;
    
    // Instruments
    instruments.forEach((instrument, instIdx) => {
      const product = instrument.Product || {};
      const expiry = product.expiryYear && product.expiryMonth && product.expiryDay
        ? `${product.expiryMonth}/${product.expiryDay}/${product.expiryYear}`
        : 'N/A';
      
      html += `
        <div class="instrument-preview">
          <div class="instrument-header-preview">
            <div>
              <strong class="instrument-symbol-preview">${product.symbol || 'N/A'}</strong>
              <span class="instrument-type-badge">${product.securityType || 'OPTN'}</span>
            </div>
            <div class="instrument-action-badge action-${instrument.orderAction?.toLowerCase().replace('_', '-') || 'unknown'}">
              ${instrument.orderAction || 'N/A'}
            </div>
          </div>
          
          <div class="instrument-details-preview">
            <div class="detail-grid">
              ${product.securityType === 'OPTN' ? `
              <div class="detail-item-preview">
                <span class="detail-label-preview">Option Type:</span>
                <span class="detail-value-preview">${product.callPut || 'N/A'}</span>
              </div>
              <div class="detail-item-preview">
                <span class="detail-label-preview">Strike Price:</span>
                <span class="detail-value-preview">${formatCurrency(product.strikePrice || 0)}</span>
              </div>
              <div class="detail-item-preview">
                <span class="detail-label-preview">Expiry:</span>
                <span class="detail-value-preview">${expiry}</span>
              </div>
              <div class="detail-item-preview">
                <span class="detail-label-preview">osiKey:</span>
                <span class="detail-value-preview osikey-preview">${instrument.osiKey || 'N/A'}</span>
              </div>
              ` : `
              <div class="detail-item-preview">
                <span class="detail-label-preview">Security Type:</span>
                <span class="detail-value-preview">${product.securityType || 'EQ'}</span>
              </div>
              `}
              <div class="detail-item-preview">
                <span class="detail-label-preview">Quantity:</span>
                <span class="detail-value-preview">${instrument.quantity || 0}</span>
              </div>
              <div class="detail-item-preview">
                <span class="detail-label-preview">Description:</span>
                <span class="detail-value-preview">${instrument.symbolDescription || product.symbol || 'N/A'}</span>
              </div>
            </div>
          </div>
        </div>
      `;
    });
    
    // Pricing
    html += `
          <div class="pricing-section">
            <h5>💰 Pricing</h5>
            <div class="pricing-grid">
              <div class="pricing-item">
                <span class="pricing-label">Price Type:</span>
                <span class="pricing-value">${order.priceType || 'N/A'}</span>
              </div>
              ${order.limitPrice > 0 ? `
              <div class="pricing-item">
                <span class="pricing-label">Limit Price:</span>
                <span class="pricing-value">${formatCurrency(order.limitPrice)}</span>
              </div>
              ` : ''}
              ${order.stopPrice > 0 ? `
              <div class="pricing-item">
                <span class="pricing-label">Stop Price:</span>
                <span class="pricing-value">${formatCurrency(order.stopPrice)}</span>
              </div>
              ` : ''}
              <div class="pricing-item">
                <span class="pricing-label">Estimated Commission:</span>
                <span class="pricing-value">${formatCurrency(order.estimatedCommission || 0)}</span>
              </div>
              <div class="pricing-item">
                <span class="pricing-label">Estimated Fees:</span>
                <span class="pricing-value">${formatCurrency(order.estimatedFees || 0)}</span>
              </div>
              <div class="pricing-item total">
                <span class="pricing-label">Total Cost:</span>
                <span class="pricing-value">${formatCurrency((order.estimatedCommission || 0) + (order.estimatedFees || 0))}</span>
              </div>
            </div>
          </div>
          
          <div class="order-settings-section">
            <h5>⚙️ Order Settings</h5>
            <div class="settings-grid">
              <div class="setting-item">
                <span class="setting-label">Order Term:</span>
                <span class="setting-value">${order.orderTerm || 'N/A'}</span>
              </div>
              <div class="setting-item">
                <span class="setting-label">Market Session:</span>
                <span class="setting-value">${order.marketSession || 'N/A'}</span>
              </div>
              <div class="setting-item">
                <span class="setting-label">All or None:</span>
                <span class="setting-value">${order.allOrNone ? 'Yes' : 'No'}</span>
              </div>
              ${order.egQual ? `
              <div class="setting-item">
                <span class="setting-label">EG Qualification:</span>
                <span class="setting-value">${order.egQual}</span>
              </div>
              ` : ''}
            </div>
          </div>
    `;
    
    // Messages/Warnings
    if (messageList.length > 0) {
      html += `
        <div class="messages-section">
          <h5>⚠️ Messages & Warnings</h5>
          <div class="messages-list">
      `;
      
      messageList.forEach(msg => {
        const msgType = msg.type || 'INFO';
        const msgClass = msgType === 'WARNING' ? 'warning' : msgType === 'ERROR' ? 'error' : 'info';
        html += `
          <div class="message-item ${msgClass}">
            <span class="message-icon">${msgType === 'WARNING' ? '⚠️' : msgType === 'ERROR' ? '❌' : 'ℹ️'}</span>
            <div class="message-content">
              <div class="message-code">Code: ${msg.code || 'N/A'}</div>
              <div class="message-description">${msg.description || 'N/A'}</div>
            </div>
          </div>
        `;
      });
      
      html += `
          </div>
        </div>
      `;
    }
    
    html += `
        </div>
      </div>
    `;
  });
  
  // Account Info
  html += `
    <div class="account-info-section">
      <h5>📊 Account Information</h5>
      <div class="account-grid">
        <div class="account-item">
          <span class="account-label">Account ID:</span>
          <span class="account-value">${preview.accountId || 'N/A'}</span>
        </div>
        <div class="account-item">
          <span class="account-label">Margin Level:</span>
          <span class="account-value">${preview.marginLevelCd || 'N/A'}</span>
        </div>
        <div class="account-item">
          <span class="account-label">Option Level:</span>
          <span class="account-value">Level ${preview.optionLevelCd || 'N/A'}</span>
        </div>
        <div class="account-item">
          <span class="account-label">DST Flag:</span>
          <span class="account-value">${preview.dstFlag ? 'Yes' : 'No'}</span>
        </div>
      </div>
    </div>
  `;
  
  // Portfolio Margin
  if (portfolioMargin.pmEligible !== undefined) {
    html += `
      <div class="portfolio-margin-section">
        <h5>💼 Portfolio Margin</h5>
        <div class="pm-grid">
          <div class="pm-item">
            <span class="pm-label">PM Eligible:</span>
            <span class="pm-value ${portfolioMargin.pmEligible ? 'positive' : 'negative'}">${portfolioMargin.pmEligible ? 'Yes' : 'No'}</span>
          </div>
          ${portfolioMargin.houseExcessEquityCurr !== undefined ? `
          <div class="pm-item">
            <span class="pm-label">Current Excess Equity:</span>
            <span class="pm-value">${formatCurrency(portfolioMargin.houseExcessEquityCurr)}</span>
          </div>
          ` : ''}
          ${portfolioMargin.houseExcessEquityNew !== undefined ? `
          <div class="pm-item">
            <span class="pm-label">New Excess Equity:</span>
            <span class="pm-value">${formatCurrency(portfolioMargin.houseExcessEquityNew)}</span>
          </div>
          ` : ''}
          ${portfolioMargin.houseExcessEquityChange !== undefined ? `
          <div class="pm-item">
            <span class="pm-label">Equity Change:</span>
            <span class="pm-value ${portfolioMargin.houseExcessEquityChange >= 0 ? 'positive' : 'negative'}">${formatCurrency(portfolioMargin.houseExcessEquityChange)}</span>
          </div>
          ` : ''}
        </div>
      </div>
    `;
  }
  
  // Disclosure
  html += `
    <div class="disclosure-section">
      <h5>📄 Disclosures</h5>
      <div class="disclosure-grid">
        <div class="disclosure-item">
          <span class="disclosure-label">AO Disclosure:</span>
          <span class="disclosure-value ${disclosure.aoDisclosureFlag ? 'warning' : 'success'}">${disclosure.aoDisclosureFlag ? '⚠️ Required' : '✅ Not Required'}</span>
        </div>
        <div class="disclosure-item">
          <span class="disclosure-label">Conditional Disclosure:</span>
          <span class="disclosure-value ${disclosure.conditionalDisclosureFlag ? 'warning' : 'success'}">${disclosure.conditionalDisclosureFlag ? '⚠️ Required' : '✅ Not Required'}</span>
        </div>
        <div class="disclosure-item">
          <span class="disclosure-label">EH Disclosure:</span>
          <span class="disclosure-value ${disclosure.ehDisclosureFlag ? 'warning' : 'success'}">${disclosure.ehDisclosureFlag ? '⚠️ Required' : '✅ Not Required'}</span>
        </div>
      </div>
    </div>
  `;
    
    html += '</div>';
  return html;
}

async function etradePreviewOptionsOrder() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
        return;
    }
  const payload = {
    option_symbol: document.getElementById('etrade-opt-order-symbol').value.trim(),
    order_action: document.getElementById('etrade-opt-order-action').value,
    price_type: document.getElementById('etrade-opt-price-type').value,
    limit_price: document.getElementById('etrade-opt-limit-price').value.trim(),
    order_term: document.getElementById('etrade-opt-order-term').value,
    quantity: document.getElementById('etrade-opt-quantity').value,
    client_order_id: Date.now().toString(),
  };
  const target = document.getElementById('etrade-options-order-result');
  if (!payload.option_symbol) {
    target.innerHTML = '<div class="test-result error show">Option symbol is required.</div>';
    return;
  }
  
  // CLEAR OLD PREVIEW DATA AT START (to ensure we don't reuse stale previewId)
  const oldPreviewId = etradeState.optionsPreviewId;
  if (oldPreviewId) {
    console.log('🔄 Clearing OLD options previewId before new preview:', oldPreviewId);
    delete etradeState.optionsPreviewId;
  }
  if (etradeState.optionsPreviewPayload) {
    console.log('🔄 Clearing OLD options preview payload before new preview');
    delete etradeState.optionsPreviewPayload;
  }
  if (etradeState.optionsPreviewTimestamp) {
    delete etradeState.optionsPreviewTimestamp;
  }
  
  target.innerHTML = '<div class="test-result info show">Previewing options order...</div>';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/preview-options-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Failed to preview options order'}</div>`;
      // Clear stored previewId and payload on error
      if (etradeState.optionsPreviewId) {
        delete etradeState.optionsPreviewId;
      }
      if (etradeState.optionsPreviewPayload) {
        delete etradeState.optionsPreviewPayload;
      }
      return;
    }
    
    // Capture PreviewId from the response
    // The preview structure is: { PreviewOrderResponse: { PreviewIds: [{ PreviewId: ... }] } }
    console.log('🔍 DEBUG: Full options preview response:', JSON.stringify(data.preview, null, 2));
    
    const previewResponse = data.preview?.PreviewOrderResponse || data.preview;
    console.log('🔍 DEBUG: options previewResponse:', previewResponse);
    
    const previewIds = previewResponse?.PreviewIds || [];
    console.log('🔍 DEBUG: options previewIds from PreviewOrderResponse:', previewIds);
    
    // Also check if PreviewIds is at root level
    const rootPreviewIds = data.preview?.PreviewIds || [];
    console.log('🔍 DEBUG: options rootPreviewIds:', rootPreviewIds);
    
    const allPreviewIds = previewIds.length > 0 ? previewIds : rootPreviewIds;
    console.log('🔍 DEBUG: options allPreviewIds (final):', allPreviewIds);
    
    // E*TRADE API uses "PreviewId" (capital P) inside PreviewIds array
    if (allPreviewIds.length > 0 && (allPreviewIds[0].PreviewId || allPreviewIds[0].previewId)) {
      const newPreviewId = allPreviewIds[0].PreviewId || allPreviewIds[0].previewId;
      const oldPreviewId = etradeState.optionsPreviewId;
      
      if (oldPreviewId && oldPreviewId === newPreviewId) {
        console.warn('⚠️ WARNING: New options previewId is the same as old previewId:', newPreviewId);
        console.warn('   This might indicate the preview response is not being parsed correctly');
      }
      
      etradeState.optionsPreviewId = newPreviewId;
      // Store the entire preview payload to reuse same parameters (especially client_order_id)
      etradeState.optionsPreviewPayload = payload;
      etradeState.optionsPreviewTimestamp = Date.now();
      console.log('✅ Captured NEW options previewId:', etradeState.optionsPreviewId);
      console.log('✅ Previous options previewId was:', oldPreviewId || 'none');
      console.log('✅ Stored options preview payload for place order (client_order_id:', payload.client_order_id + ')');
    } else {
      console.error('❌ ERROR: No options previewId found in preview response!');
      console.error('   Preview response structure:', JSON.stringify(data.preview, null, 2));
      console.error('   previewResponse:', previewResponse);
      console.error('   previewIds:', previewIds);
      console.error('   rootPreviewIds:', rootPreviewIds);
      console.error('   allPreviewIds:', allPreviewIds);
      if (etradeState.optionsPreviewId) {
        console.warn('⚠️ Keeping old options previewId:', etradeState.optionsPreviewId, '(this is likely wrong!)');
      } else {
        // Clear everything if no previewId found
        if (etradeState.optionsPreviewId) {
          delete etradeState.optionsPreviewId;
        }
        if (etradeState.optionsPreviewPayload) {
          delete etradeState.optionsPreviewPayload;
        }
      }
    }
    
    // Reuse the same preview formatter (works for both options and equity)
    target.innerHTML = formatOptionsOrderPreview(data.preview);
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ ${err.message || err}</div>`;
    // Clear stored previewId and payload on error
    if (etradeState.optionsPreviewId) {
      delete etradeState.optionsPreviewId;
    }
    if (etradeState.optionsPreviewPayload) {
      delete etradeState.optionsPreviewPayload;
    }
  }
}

async function etradePlaceOptionsOrder() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
    return;
  }
  const target = document.getElementById('etrade-options-order-result');
  
  // Check if previewId and preview payload exist (must preview first)
  if (!etradeState.optionsPreviewId || !etradeState.optionsPreviewPayload) {
    target.innerHTML = '<div class="test-result error show">❌ Please preview the options order first to get a PreviewId. Click "Preview Options Order" before placing.</div>';
    etradeShowStatus('Preview the options order first before placing.', 'warning');
    return;
  }
  
  // Use the EXACT same payload from preview, only add PreviewId
  // This ensures client_order_id and all parameters match exactly
  // Note: E*TRADE API is case-sensitive, must use "PreviewId" (capital P)
  const payload = {
    ...etradeState.optionsPreviewPayload,  // Reuse all parameters from preview (including client_order_id)
    PreviewId: etradeState.optionsPreviewId, // Add the PreviewId (capital P for E*TRADE API)
  };
  
  if (!payload.option_symbol) {
    target.innerHTML = '<div class="test-result error show">Option symbol is required.</div>';
    return;
  }
  
  console.log('🔄 Using stored options preview payload for place order');
  console.log('   client_order_id:', payload.client_order_id);
  console.log('   PreviewId:', payload.PreviewId);
  
  target.innerHTML = '<div class="test-result info show">Placing options order with PreviewId: ' + etradeState.optionsPreviewId + '...</div>';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/place-options-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Failed to place options order'}</div>`;
      // Clear previewId and payload on error so user can preview again
      if (etradeState.optionsPreviewId) {
        delete etradeState.optionsPreviewId;
      }
      if (etradeState.optionsPreviewPayload) {
        delete etradeState.optionsPreviewPayload;
      }
      return;
    }
    // Clear previewId and payload after successful placement
    if (etradeState.optionsPreviewId) {
      delete etradeState.optionsPreviewId;
    }
    if (etradeState.optionsPreviewPayload) {
      delete etradeState.optionsPreviewPayload;
    }
    target.innerHTML = `<pre>${JSON.stringify(data.order, null, 2)}</pre>`;
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ ${err.message || err}</div>`;
    // Clear previewId and payload on error
    if (etradeState.optionsPreviewId) {
      delete etradeState.optionsPreviewId;
    }
    if (etradeState.optionsPreviewPayload) {
      delete etradeState.optionsPreviewPayload;
    }
  }
}

async function etradePreviewEquityOrder() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
    return;
  }
  const payload = {
    symbol: document.getElementById('etrade-equity-symbol').value.trim().toUpperCase(),
    order_action: document.getElementById('etrade-equity-action').value,
    price_type: document.getElementById('etrade-equity-price-type').value,
    limit_price: document.getElementById('etrade-equity-limit-price').value.trim(),
    stop_price: document.getElementById('etrade-equity-stop-price').value.trim(),
    order_term: document.getElementById('etrade-equity-order-term').value,
    market_session: document.getElementById('etrade-equity-market-session').value,
    all_or_none: document.getElementById('etrade-equity-all-or-none').value === 'true',
    quantity: parseInt(document.getElementById('etrade-equity-quantity').value),
    client_order_id: Date.now().toString(),
  };
  const target = document.getElementById('etrade-equity-order-result');
  if (!payload.symbol) {
    target.innerHTML = '<div class="test-result error show">Symbol is required.</div>';
    return;
  }
  // CLEAR OLD PREVIEW DATA AT START (to ensure we don't reuse stale previewId)
  const oldPreviewId = etradeState.equityPreviewId;
  if (oldPreviewId) {
    console.log('🔄 Clearing OLD previewId before new preview:', oldPreviewId);
    delete etradeState.equityPreviewId;
  }
  if (etradeState.equityPreviewPayload) {
    console.log('🔄 Clearing OLD preview payload before new preview');
    delete etradeState.equityPreviewPayload;
  }
  if (etradeState.equityPreviewTimestamp) {
    delete etradeState.equityPreviewTimestamp;
  }
  
  target.innerHTML = '<div class="test-result info show">Previewing equity order...</div>';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/preview-equity-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Failed to preview equity order'}</div>`;
      // Clear stored previewId and payload on error
      if (etradeState.equityPreviewId) {
        delete etradeState.equityPreviewId;
      }
      if (etradeState.equityPreviewPayload) {
        delete etradeState.equityPreviewPayload;
      }
      return;
    }
    // Capture PreviewId from the response
    // The preview structure is: { PreviewOrderResponse: { PreviewIds: [{ PreviewId: ... }] } }
    console.log('🔍 DEBUG: Full preview response:', JSON.stringify(data.preview, null, 2));
    
    const previewResponse = data.preview?.PreviewOrderResponse || data.preview;
    console.log('🔍 DEBUG: previewResponse:', previewResponse);
    
    const previewIds = previewResponse?.PreviewIds || [];
    console.log('🔍 DEBUG: previewIds from PreviewOrderResponse:', previewIds);
    
    // Also check if PreviewIds is at root level
    const rootPreviewIds = data.preview?.PreviewIds || [];
    console.log('🔍 DEBUG: rootPreviewIds:', rootPreviewIds);
    
    const allPreviewIds = previewIds.length > 0 ? previewIds : rootPreviewIds;
    console.log('🔍 DEBUG: allPreviewIds (final):', allPreviewIds);
    
    // E*TRADE API uses "PreviewId" (capital P) inside PreviewIds array
    if (allPreviewIds.length > 0 && (allPreviewIds[0].PreviewId || allPreviewIds[0].previewId)) {
      const newPreviewId = allPreviewIds[0].PreviewId || allPreviewIds[0].previewId;
      const oldPreviewId = etradeState.equityPreviewId;
      
      if (oldPreviewId && oldPreviewId === newPreviewId) {
        console.warn('⚠️ WARNING: New previewId is the same as old previewId:', newPreviewId);
        console.warn('   This might indicate the preview response is not being parsed correctly');
      }
      
      etradeState.equityPreviewId = newPreviewId;
      // Store the entire preview payload to reuse same parameters (especially client_order_id)
      etradeState.equityPreviewPayload = payload;
      etradeState.equityPreviewTimestamp = Date.now();
      console.log('✅ Captured NEW previewId:', etradeState.equityPreviewId);
      console.log('✅ Previous previewId was:', oldPreviewId || 'none');
      console.log('✅ Stored preview payload for place order (client_order_id:', payload.client_order_id + ')');
    } else {
      console.error('❌ ERROR: No previewId found in preview response!');
      console.error('   Preview response structure:', JSON.stringify(data.preview, null, 2));
      console.error('   previewResponse:', previewResponse);
      console.error('   previewIds:', previewIds);
      console.error('   rootPreviewIds:', rootPreviewIds);
      console.error('   allPreviewIds:', allPreviewIds);
      if (etradeState.equityPreviewId) {
        console.warn('⚠️ Keeping old previewId:', etradeState.equityPreviewId, '(this is likely wrong!)');
        // Don't delete - we'll see if old one is being used incorrectly
      } else {
        if (etradeState.equityPreviewId) {
          delete etradeState.equityPreviewId;
        }
        if (etradeState.equityPreviewPayload) {
          delete etradeState.equityPreviewPayload;
        }
      }
    }
    // Reuse the same preview formatter (works for both options and equity)
    target.innerHTML = formatOptionsOrderPreview(data.preview);
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ ${err.message || err}</div>`;
    // Clear stored previewId and payload on error
    if (etradeState.equityPreviewId) {
      delete etradeState.equityPreviewId;
    }
    if (etradeState.equityPreviewPayload) {
      delete etradeState.equityPreviewPayload;
    }
  }
}

async function etradePlaceEquityOrder() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
        return;
    }
  
  // Check if previewId and preview payload exist (must preview first)
  if (!etradeState.equityPreviewId || !etradeState.equityPreviewPayload) {
    const target = document.getElementById('etrade-equity-order-result');
    target.innerHTML = '<div class="test-result error show">❌ Please preview the order first to get a previewId. Click "Preview Order" before placing.</div>';
    etradeShowStatus('Preview the order first before placing.', 'warning');
    return;
  }
  
  // Use the EXACT same payload from preview, only add PreviewId
  // This ensures client_order_id and all parameters match exactly
  // Note: E*TRADE API is case-sensitive, must use "PreviewId" (capital P)
  const payload = {
    ...etradeState.equityPreviewPayload,  // Reuse all parameters from preview (including client_order_id)
    PreviewId: etradeState.equityPreviewId, // Add the PreviewId (capital P for E*TRADE API)
  };
  
  console.log('🔄 Using stored preview payload for place order');
  console.log('   client_order_id:', payload.client_order_id);
  console.log('   PreviewId:', payload.PreviewId);
  const target = document.getElementById('etrade-equity-order-result');
  if (!payload.symbol) {
    target.innerHTML = '<div class="test-result error show">Symbol is required.</div>';
    return;
  }
  target.innerHTML = '<div class="test-result info show">Placing equity order with previewId: ' + etradeState.equityPreviewId + '...</div>';
  try {
    const res = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/place-equity-order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      target.innerHTML = `<div class="test-result error show">❌ ${data.error || 'Failed to place equity order'}</div>`;
      // Clear previewId and payload on error so user can preview again
      if (etradeState.equityPreviewId) {
        delete etradeState.equityPreviewId;
      }
      if (etradeState.equityPreviewPayload) {
        delete etradeState.equityPreviewPayload;
      }
      return;
    }
    target.innerHTML = `<div class="test-result success show">✅ Order placed successfully!<br><pre>${JSON.stringify(data.order, null, 2)}</pre></div>`;
    // Clear previewId and payload after successful placement
    if (etradeState.equityPreviewId) {
      delete etradeState.equityPreviewId;
    }
    if (etradeState.equityPreviewPayload) {
      delete etradeState.equityPreviewPayload;
    }
    // Reload orders to show the new order
    setTimeout(() => etradeLoadOrders(), 1000);
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ ${err.message || err}</div>`;
    // Clear previewId and payload on error
    if (etradeState.equityPreviewId) {
      delete etradeState.equityPreviewId;
    }
    if (etradeState.equityPreviewPayload) {
      delete etradeState.equityPreviewPayload;
    }
  }
}

// Preview and Place Equity Order in one action
async function etradePreviewAndPlaceEquityOrder() {
  if (!etradeState.defaultAccountId) {
    etradeShowStatus('Select an account first.', 'warning');
    return;
  }
  
  const target = document.getElementById('etrade-equity-order-result');
  
  // Step 1: Show processing
  target.innerHTML = '<div class="test-result info show"><h3>⚡ Preview & Place Order</h3><p>Step 1/2: Previewing order...</p></div>';
  
  // Get payload
  const payload = {
    symbol: document.getElementById('etrade-equity-symbol').value.trim().toUpperCase(),
    order_action: document.getElementById('etrade-equity-action').value,
    price_type: document.getElementById('etrade-equity-price-type').value,
    limit_price: document.getElementById('etrade-equity-limit-price').value.trim(),
    stop_price: document.getElementById('etrade-equity-stop-price').value.trim(),
    order_term: document.getElementById('etrade-equity-order-term').value,
    market_session: document.getElementById('etrade-equity-market-session').value,
    all_or_none: document.getElementById('etrade-equity-all-or-none').value === 'true',
    quantity: parseInt(document.getElementById('etrade-equity-quantity').value),
    client_order_id: Date.now().toString(),
  };
  
  if (!payload.symbol) {
    target.innerHTML = '<div class="test-result error show">❌ Symbol is required.</div>';
    return;
  }
  
  // Clear old preview data
  delete etradeState.equityPreviewId;
  delete etradeState.equityPreviewPayload;
  delete etradeState.equityPreviewTimestamp;
  
  try {
    // Step 1: Preview
    const previewRes = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/preview-equity-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const previewData = await previewRes.json();
    
    if (!previewRes.ok || !previewData.success) {
      target.innerHTML = `<div class="test-result error show">❌ Preview failed: ${previewData.error || 'Unknown error'}</div>`;
      return;
    }
    
    // Extract PreviewId
    const previewResponse = previewData.preview?.PreviewOrderResponse || previewData.preview;
    const previewIds = previewResponse?.PreviewIds || previewData.preview?.PreviewIds || [];
    
    if (previewIds.length === 0 || (!previewIds[0].PreviewId && !previewIds[0].previewId)) {
      target.innerHTML = '<div class="test-result error show">❌ No PreviewId returned from preview</div>';
      return;
    }
    
    const previewId = previewIds[0].PreviewId || previewIds[0].previewId;
    
    // Store for the place request
    etradeState.equityPreviewId = previewId;
    etradeState.equityPreviewPayload = payload;
    etradeState.equityPreviewTimestamp = Date.now();
    
    // Show preview success
    target.innerHTML = '<div class="test-result success show"><h3>✅ Step 1/2: Preview Successful</h3><p>PreviewId: ' + previewId + '</p><p>Step 2/2: Placing order...</p></div>';
    
    // Step 2: Place order (after 1 second delay)
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const placePayload = {
      ...payload,
      PreviewId: previewId,
    };
    
    const placeRes = await fetch(`/api/etrade/accounts/${etradeState.defaultAccountId}/place-equity-order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(placePayload),
    });
    const placeData = await placeRes.json();
    
    if (!placeRes.ok || !placeData.success) {
      target.innerHTML = `<div class="test-result error show"><h3>❌ Step 2/2: Place Order Failed</h3><p>${placeData.error || 'Unknown error'}</p></div>`;
      delete etradeState.equityPreviewId;
      delete etradeState.equityPreviewPayload;
      return;
    }
    
    // Success!
    let html = '<div class="test-result success show">';
    html += '<h2 style="margin-top: 0; color: #059669;">✅ Order Placed Successfully!</h2>';
    html += '<div style="background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); padding: 20px; border-radius: 8px; margin: 16px 0; border: 2px solid #059669;">';
    html += '<h3 style="margin: 0 0 16px 0; color: #065f46;">📊 Order Details</h3>';
    html += '<pre style="background: white; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 0.9rem;">' + JSON.stringify(placeData.order, null, 2) + '</pre>';
    html += '</div></div>';
    target.innerHTML = html;
    
    // Clear preview data
    delete etradeState.equityPreviewId;
    delete etradeState.equityPreviewPayload;
    
    // Reload orders
    setTimeout(() => etradeLoadOrders(), 1000);
    
  } catch (err) {
    target.innerHTML = `<div class="test-result error show">❌ Error: ${err.message || err}</div>`;
    delete etradeState.equityPreviewId;
    delete etradeState.equityPreviewPayload;
  }
}

// Initialize when tab is opened
function initEtrade() {
  etradeLoadConfig().then(() => etradeCheckStatus());
}

// Hook into global switchTab if available
if (typeof window !== 'undefined') {
  const originalSwitch = window.switchTab;
  window.switchTab = function (tabName, button) {
    if (originalSwitch) {
      originalSwitch(tabName, button);
    }
            if (tabName === 'etrade') {
                initEtrade();
            }
        };
    }
