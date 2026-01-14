// TradeIQ Frontend JavaScript

// Conversation state
let conversationState = {
    conversationId: null,
    context: {},
    isActive: false,
    isFirstMessage: true,
    builderPromptUsed: null
};

// Dashboard badge state for channel management signals
let dashboardReadSignals = new Set(); // Track which channel management signals have been read
let channelManagementChannels = []; // Cache of channel management channel names

// App icon badge state
let appBadgeCount = 0; // Track total unread notifications for app icon badge

// Helper function to toggle collapsible sections
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const toggle = document.getElementById(sectionId.replace('-section', '-toggle'));
    
    if (section && toggle) {
        if (section.style.display === 'none') {
            section.style.display = 'block';
            toggle.textContent = '▼';
        } else {
            section.style.display = 'none';
            toggle.textContent = '▶';
        }
    }
}

// Save Discord session manually
async function saveDiscordSession(event) {
    event.stopPropagation(); // Prevent collapse/expand
    
    if (!window.electronAPI || !window.electronAPI.saveDiscordSession) {
        alert('This feature requires the Electron desktop app');
        return;
    }
    
    const button = document.getElementById('save-discord-session-btn');
    const originalText = button.innerHTML;
    
    try {
        button.innerHTML = '⏳ Saving...';
        button.disabled = true;
        
        const result = await window.electronAPI.saveDiscordSession();
        
        if (result.success) {
            button.innerHTML = '✅ Saved!';
            console.log('Discord session saved:', result.message);
            
            // Reset button after 2 seconds
            setTimeout(() => {
                button.innerHTML = originalText;
                button.disabled = false;
            }, 2000);
        } else {
            button.innerHTML = '❌ Error';
            console.error('Failed to save session:', result.error);
            alert('Failed to save session: ' + result.error);
            
            setTimeout(() => {
                button.innerHTML = originalText;
                button.disabled = false;
            }, 2000);
        }
    } catch (err) {
        button.innerHTML = '❌ Error';
        console.error('Error saving session:', err);
        alert('Error: ' + err.message);
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
        }, 2000);
    }
}

// Initialize app on load
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    // Load channel management channels first
    loadChannelManagementChannels().then(() => {
        loadAllSignals();
    });
    loadChannels();
    loadConfig();
    
    // Update dashboard badge count on initial load (wait for signals to load)
    setTimeout(() => {
        updateDashboardBadge();
        updateAppIconBadge();
    }, 2000);
    
    // Initialize Discord browser if Dashboard tab is active (default tab)
    setTimeout(() => {
        const dashboardTab = document.getElementById('dashboard-tab');
        if (dashboardTab && dashboardTab.classList.contains('active')) {
            if (window.discordBrowser && typeof window.discordBrowser.onTabActivated === 'function') {
                console.log('Initializing Discord browser on Dashboard tab load...');
                window.discordBrowser.onTabActivated();
            }
        }
    }, 1000);
    
    // Check for signal ID in URL hash (for deep linking from notifications)
    const hash = window.location.hash;
    if (hash && hash.startsWith('#signal-')) {
        const signalId = parseInt(hash.replace('#signal-', ''));
        if (signalId) {
            // Wait for signals to load, then navigate
            setTimeout(() => {
                navigateToDashboardSignal(signalId);
            }, 2000);
        }
    }
    
    // Clear app icon badge when app is opened/focused
    clearAppIconBadge();
    
    // Update app icon badge when visibility changes (user comes back to app)
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            // App is visible, clear badge
            clearAppIconBadge();
        }
    });
    
    // Update app icon badge when window gains focus
    window.addEventListener('focus', () => {
        clearAppIconBadge();
    });
    
    // Start auto-refresh for dashboard (checked by default)
    startSignalsAutoRefresh();
    
    // Set up auto-refresh checkbox listener
    const checkbox = document.getElementById('auto-refresh-signals');
    if (checkbox) {
        checkbox.addEventListener('change', () => {
            console.log('Auto-refresh checkbox changed:', checkbox.checked);
            if (checkbox.checked) {
                startSignalsAutoRefresh();
            } else {
                stopSignalsAutoRefresh();
            }
        });
    }
    
    // Set up filter dropdown listener to reset view when filter changes
    const filterDropdown = document.getElementById('signal-source-filter');
    if (filterDropdown) {
        filterDropdown.addEventListener('change', () => {
            console.log('Signal source filter changed, resetting view to show most recent');
            loadAllSignals(true); // Reset view to show only most recent
        });
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeMoreSheet();
        }
    });
});

// Tab switching
function toggleMoreMenu() {
    const panel = document.getElementById('more-menu-panel');
    if (panel) {
        panel.classList.toggle('active');
    }
}

// Close menu when clicking outside
document.addEventListener('click', function(event) {
    const panel = document.getElementById('more-menu-panel');
    const hamburger = document.querySelector('.hamburger-btn');
    if (panel && panel.classList.contains('active')) {
        if (!panel.contains(event.target) && !hamburger.contains(event.target)) {
            panel.classList.remove('active');
        }
    }
});

// More Modules Dropdown Functions
function showMoreModules() {
    const menu = document.getElementById('more-modules-menu');
    if (menu) {
        menu.style.display = 'block';
    }
}

function hideMoreModules() {
    const menu = document.getElementById('more-modules-menu');
    if (menu) {
        menu.style.display = 'none';
    }
}

function switchTab(tabName, eventElement) {
    closeMoreSheet();
    hideMoreModules(); // Close dropdown when switching tabs
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabElement = document.getElementById(`${tabName}-tab`);
    if (tabElement) {
        tabElement.classList.add('active');
        
        // Initialize module-specific logic when tab is opened
        if (tabName === 'webull' && typeof webullInit === 'function') {
            webullInit();
        }
    } else {
        console.error(`Tab element not found: ${tabName}-tab`);
    }
    
    // Mark X signals as read when X tab is opened
    if (tabName === 'x' && typeof xMarkSignalsAsRead === 'function') {
        xMarkSignalsAsRead();
    }
    
    // Note: Dashboard signals are NOT automatically marked as read when tab opens
    // They must be explicitly clicked/touched to be marked as read
    
    // Discord Browser: initialize when Dashboard tab is active (Discord browser is now in Dashboard)
    if (window.discordBrowser) {
        if (tabName === 'dashboard') {
            // Initialize Discord browser when Dashboard tab is opened
            window.discordBrowser.onTabActivated();
        } else if (tabName === 'discord-browser') {
            // Legacy support for old discord-browser tab
            window.discordBrowser.onTabActivated();
        } else {
            window.discordBrowser.onTabDeactivated();
        }
    }
    
    // Add active class to clicked button (if eventElement provided)
    if (eventElement) {
        eventElement.classList.add('active');
    } else {
        // Fallback: find button by tab name
        document.querySelectorAll('.tab-btn').forEach(btn => {
            if (btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(`'${tabName}'`)) {
                btn.classList.add('active');
            }
        });
    }
    
    // Load data for specific tabs
    if (tabName === 'dashboard') {
        loadAllSignals();
        startSignalsAutoRefresh();
    } else if (tabName === 'channels') {
        loadChannels();
        stopSignalsAutoRefresh(); // Stop auto-refresh when switching away
    } else if (tabName === 'prompt-builder') {
        loadChannelsForSelectChat();
        stopSignalsAutoRefresh(); // Stop auto-refresh when switching away
    } else if (tabName === 'executor') {
        stopSignalsAutoRefresh(); // Stop auto-refresh when switching away
        // Load execution history (with error handling)
        if (typeof executorLoadHistory === 'function') {
            try {
                executorLoadHistory();
            } catch (error) {
                console.error('Error loading executor history:', error);
            }
        }
        // Load enabled state
        if (typeof smartExecutorLoadEnabled === 'function') {
            try {
                smartExecutorLoadEnabled();
            } catch (error) {
                console.error('Error loading Smart Executor enabled state:', error);
            }
        }
    } else if (tabName === 'tradingview-executor') {
        stopSignalsAutoRefresh();
        if (typeof tradingviewExecutorLoadConfig === 'function') {
            tradingviewExecutorLoadConfig();
        }
    } else if (tabName === 'discord') {
        stopSignalsAutoRefresh();
        if (typeof discordLoadConfig === 'function') {
            try {
                discordLoadConfig();
            } catch (error) {
                console.error('Error loading Discord config:', error);
            }
        }
        // Load X channel signals when Discord tab is activated
        if (typeof discordLoadXSignals === 'function') {
            try {
                discordLoadXSignals();
            } catch (error) {
                console.error('Error loading X channel signals:', error);
            }
        }
        // Start auto-refresh for X signals if checkbox is checked
        const xSignalsCheckbox = document.getElementById('discord-x-signals-autorefresh');
        if (xSignalsCheckbox && xSignalsCheckbox.checked && typeof discordToggleXSignalsAutoRefresh === 'function') {
            try {
                discordToggleXSignalsAutoRefresh();
            } catch (error) {
                console.error('Error starting X signals auto-refresh:', error);
            }
        }
    } else if (tabName === 'settings') {
        // Load X, Grok, and X bot keywords configs when Settings tab is activated
        if (typeof xLoadConfig === 'function') {
            try {
                xLoadConfig();
            } catch (error) {
                console.error('Error loading X config:', error);
            }
        }
        if (typeof loadXBotKeywords === 'function') {
            try {
                loadXBotKeywords();
            } catch (error) {
                console.error('Error loading X bot keywords:', error);
            }
        }
        if (typeof grokLoadConfig === 'function') {
            try {
                grokLoadConfig();
            } catch (error) {
                console.error('Error loading Grok config:', error);
            }
        }
    } else if (tabName === 'x') {
        stopSignalsAutoRefresh();
        // Load analytics immediately
        if (typeof xUpdateAnalytics === 'function') {
            try {
                xUpdateAnalytics();
            } catch (error) {
                console.error('Error loading X analytics:', error);
            }
        }
        
        // Start auto-refresh for X signals
        const xSignalsCheckbox = document.getElementById('x-signals-autorefresh');
        if (xSignalsCheckbox && xSignalsCheckbox.checked && typeof xStartAutoRefresh === 'function') {
            try {
                xStartAutoRefresh();
            } catch (error) {
                console.error('Error starting X signals auto-refresh:', error);
            }
        }
        if (typeof tradingviewExecutorLoadHistory === 'function') {
            tradingviewExecutorLoadHistory();
        }
    } else if (tabName === 'settings') {
        stopSignalsAutoRefresh(); // Stop auto-refresh when switching away
        loadConfig();
    }
}

function openMoreSheet() {
    const sheet = document.getElementById('more-sheet');
    const moreButton = document.getElementById('mobile-more-btn');
    if (sheet) {
        sheet.classList.add('active');
        sheet.setAttribute('aria-hidden', 'false');
    }
    if (moreButton) {
        moreButton.classList.add('active');
    }
}

function closeMoreSheet() {
    const sheet = document.getElementById('more-sheet');
    const moreButton = document.getElementById('mobile-more-btn');
    if (sheet) {
        sheet.classList.remove('active');
        sheet.setAttribute('aria-hidden', 'true');
    }
    if (moreButton) {
        moreButton.classList.remove('active');
    }
}

// Health check
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        // Update OpenAI status in header
        const openaiStatusEl = document.getElementById('openai-status');
        if (openaiStatusEl) {
            openaiStatusEl.textContent =
                data.openai_configured ? '✅ Connected' : '❌ Not Configured';
        }
    } catch (error) {
        console.error('Health check failed:', error);
    }
}

// Load recent signals
async function loadRecentSignals() {
    const signalsList = document.getElementById('signals-list');
    signalsList.innerHTML = '<p class="loading">Loading signals...</p>';
    
    try {
        const response = await fetch('/api/signals/recent?limit=20');
        const data = await response.json();
        
        if (data.signals && data.signals.length > 0) {
            signalsList.innerHTML = '';
            
            data.signals.forEach(signal => {
                const card = createSignalCard(signal);
                signalsList.appendChild(card);
            });
        } else {
            signalsList.innerHTML = '<p class="loading">No signals received yet</p>';
        }
    } catch (error) {
        signalsList.innerHTML = '<p class="loading">Error loading signals</p>';
        console.error('Error loading signals:', error);
    }
}

// Clear all signals
async function clearAllSignals() {
    // Confirm action
    const confirmed = confirm(
        '⚠️ Are you sure you want to clear ALL trading signals and executions?\n\n' +
        'This action cannot be undone. All signal history will be permanently deleted.'
    );
    
    if (!confirmed) {
        return;
    }
    
    const signalsList = document.getElementById('signals-list');
    signalsList.innerHTML = '<p class="loading">Clearing signals...</p>';
    
    try {
        const response = await fetch('/api/signals/clear', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show success message
            signalsList.innerHTML = `
                <div class="result-box success" style="padding: 20px; text-align: center;">
                    <h3>✅ Signals Cleared Successfully</h3>
                    <p><strong>${data.total_deleted}</strong> record(s) deleted</p>
                    <p>${data.signals_deleted} signal(s) and ${data.executions_deleted} execution(s) removed</p>
                </div>
            `;
            
            // Refresh the list after a short delay
            setTimeout(() => {
                loadRecentSignals();
            }, 2000);
        } else {
            signalsList.innerHTML = `
                <div class="result-box error" style="padding: 20px;">
                    <h3>❌ Error Clearing Signals</h3>
                    <p>${data.error || 'Unknown error occurred'}</p>
                    <button onclick="loadRecentSignals()" class="btn btn-secondary" style="margin-top: 10px;">🔄 Reload</button>
                </div>
            `;
        }
    } catch (error) {
        signalsList.innerHTML = `
            <div class="result-box error" style="padding: 20px;">
                <h3>❌ Error Clearing Signals</h3>
                <p>${error.message}</p>
                <button onclick="loadRecentSignals()" class="btn btn-secondary" style="margin-top: 10px;">🔄 Reload</button>
            </div>
        `;
        console.error('Error clearing signals:', error);
    }
}

// Real-time signals viewer
let signalsAutoRefreshInterval = null;
let allSignalsData = []; // Store all signals
let visibleSignalsCount = 2; // Track how many signals are currently visible
const INITIAL_SIGNALS_LIMIT = 2; // Show only 2 most recent by default
const SIGNALS_INCREMENT = 2; // Show 2 more signals each time "Show More" is clicked

// Filter state
let currentFilters = {
    status: '',
    channel: '',
    symbol: '',
    action: '',
    optionType: '',
    channelFilter: 'channel-management', // By default: 'channel-management' (all channels from channel management), or ''/'all' for all, or 'x', 'tradingview' for specific channels
    excludeCommentary: true // By default: exclude Commentary signals
};

// Filter panel visibility state
let filtersExpanded = false;

// Load channel management channels
async function loadChannelManagementChannels() {
    try {
        const response = await fetch('/api/channels/management');
        const data = await response.json();
        channelManagementChannels = data.channels || [];
        return channelManagementChannels;
    } catch (error) {
        console.error('[Dashboard] Error loading channel management channels:', error);
        return [];
    }
}

// Check if a channel is in channel management
// Channel Management includes all channels except special channels (x, TradingView, UNMATCHED)
function isChannelManagementChannel(channelName) {
    if (!channelName) return false;
    // Exclude special channels
    const excluded = ['x', 'TradingView', 'UNMATCHED'];
    if (excluded.includes(channelName)) return false;
    // All other channels are considered channel management channels
    // This includes "Master Channel", "remz 100k", "remz alerts", and any other channels
    return true;
}

async function loadAllSignals(resetView = false) {
    const signalsList = document.getElementById('all-signals-list');
    if (!signalsList) return; // Tab not active
    
    // Load channel management channels if not already loaded
    if (channelManagementChannels.length === 0) {
        await loadChannelManagementChannels();
    }
    
    // Reset view to show only recent signals if requested (e.g., when filter changes)
    if (resetView) {
        visibleSignalsCount = INITIAL_SIGNALS_LIMIT;
    }
    
    const sourceFilter = document.getElementById('signal-source-filter')?.value || '';
    const url = sourceFilter 
        ? `/api/signals/all?limit=100&source=${encodeURIComponent(sourceFilter)}`
        : '/api/signals/all?limit=100';
    
    // Show/hide "Clear Filtered" button based on filter
    const clearFilteredBtn = document.getElementById('clear-filtered-btn');
    if (clearFilteredBtn) {
        clearFilteredBtn.style.display = sourceFilter ? 'inline-block' : 'none';
    }
    
    try {
        const response = await fetch(url);
        const data = await response.json();
        
        // Store all unfiltered signals
        let allUnfilteredSignals = data.signals || [];
        
        // Apply filters
        let filteredSignals = applyFilters(allUnfilteredSignals);
        allSignalsData = filteredSignals;
        
        // Auto-mark signals older than 1 hour as read
        dashboardAutoMarkOldSignalsAsRead();
        
        // Update dashboard badge count after loading signals
        updateDashboardBadge();
        
        // Update app icon badge
        updateAppIconBadge();
        
        // Get unique values for filter dropdowns from unfiltered signals (always, even if no signals)
        const uniqueStatuses = allUnfilteredSignals.length > 0 ? [...new Set(allUnfilteredSignals.map(s => s.status || 'received'))] : [];
        const uniqueChannels = allUnfilteredSignals.length > 0 ? [...new Set(allUnfilteredSignals.map(s => s.channel_name || '').filter(c => c && c !== 'UNMATCHED'))] : [];
        
        if (allUnfilteredSignals.length > 0) {
            // Determine which signals to show based on visibleSignalsCount
            const signalsToShow = allSignalsData.slice(0, visibleSignalsCount);
            
            // Debug logging for Show More button
            console.log('[Dashboard] allSignalsData.length:', allSignalsData.length);
            console.log('[Dashboard] visibleSignalsCount:', visibleSignalsCount);
            console.log('[Dashboard] Should show "Show More":', allSignalsData.length > visibleSignalsCount);
            console.log('[Dashboard] Current filter:', currentFilters.channelFilter);
            
            // If no signals match filters, show message with filters still visible
            if (allSignalsData.length === 0) {
                // Create filter controls bar with collapsible filters
                let filterControlsHtml = `
                    <div style="background: #f9fafb; padding: 10px; border-radius: 8px 8px 0 0; border: 1px solid #e5e7eb; border-bottom: none; margin-bottom: 0;">
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: ${filtersExpanded ? '10px' : '0'};">
                            <button id="toggle-filters-btn" onclick="toggleFiltersPanel()" style="background: #3b82f6; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 500; display: flex; align-items: center; gap: 6px;">
                                ${filtersExpanded ? '▼ Hide Filters' : '▶ Show Filters'}
                            </button>
                            <div style="font-size: 0.85rem; color: #6b7280;">
                                Showing 0 of ${allUnfilteredSignals.length} signals
                            </div>
                        </div>
                        <div id="filters-panel" style="display: ${filtersExpanded ? 'flex' : 'none'}; flex-direction: column; gap: 10px; padding-top: 10px; border-top: ${filtersExpanded ? '1px solid #e5e7eb' : 'none'};">
                            <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;" class="dashboard-channel-filters">
                                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                    <input type="checkbox" id="show-all-toggle" ${currentFilters.channelFilter === 'all' || currentFilters.channelFilter === '' ? 'checked' : ''} onchange="toggleChannelFilter('all')" style="cursor: pointer;">
                                    <span>All</span>
                                </label>
                                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                    <input type="checkbox" id="show-channel-management-toggle" ${!currentFilters.channelFilter || currentFilters.channelFilter === 'channel-management' ? 'checked' : ''} onchange="toggleChannelFilter('channel-management')" style="cursor: pointer;">
                                    <span>Channel Management</span>
                                </label>
                                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                    <input type="checkbox" id="show-x-channel-toggle" ${currentFilters.channelFilter === 'x' ? 'checked' : ''} onchange="toggleChannelFilter('x')" style="cursor: pointer;">
                                    <span>X</span>
                                </label>
                                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                    <input type="checkbox" id="show-tradingview-toggle" ${currentFilters.channelFilter === 'tradingview' ? 'checked' : ''} onchange="toggleChannelFilter('tradingview')" style="cursor: pointer;">
                                    <span>TradingView</span>
                                </label>
                                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                    <input type="checkbox" id="show-unmatched-toggle" ${currentFilters.channelFilter === 'unmatched' ? 'checked' : ''} onchange="toggleChannelFilter('unmatched')" style="cursor: pointer;">
                                    <span>⚠️ Unmatched</span>
                                </label>
                                <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer; margin-left: 10px; padding-left: 10px; border-left: 1px solid #d1d5db;">
                                    <input type="checkbox" id="exclude-commentary-toggle" ${currentFilters.excludeCommentary ? 'checked' : ''} onchange="toggleExcludeCommentary()" style="cursor: pointer;">
                                    <span>Exclude Commentary</span>
                                </label>
                            </div>
                        </div>
                    </div>
                `;
                
                signalsList.innerHTML = filterControlsHtml + `
                    <div style="background: white; padding: 20px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb; border-top: none; text-align: center;">
                        <p style="color: #6b7280; font-size: 0.9rem; margin: 0;">No signals match the current filters.</p>
                        <button onclick="clearAllFilters()" style="background: #fbbf24; color: #92400e; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 500; margin-top: 12px;">
                            Clear All Filters
                        </button>
                    </div>
                `;
                return;
            }
            const uniqueActions = [...new Set(allUnfilteredSignals.map(s => {
                let parsedData = null;
                if (s.parsed_signal) {
                    try {
                        parsedData = typeof s.parsed_signal === 'string' ? JSON.parse(s.parsed_signal) : s.parsed_signal;
                    } catch (e) {}
                }
                return parsedData?.action || s.action || '';
            }).filter(a => a))];
            const uniqueOptionTypes = [...new Set(allUnfilteredSignals.map(s => {
                let parsedData = null;
                if (s.parsed_signal) {
                    try {
                        parsedData = typeof s.parsed_signal === 'string' ? JSON.parse(s.parsed_signal) : s.parsed_signal;
                    } catch (e) {}
                }
                return parsedData?.option_type || s.option_type || '';
            }).filter(t => t))];
            
            // Check if any filters are active
            const hasActiveFilters = currentFilters.status || currentFilters.channel || currentFilters.symbol || 
                                   currentFilters.action || currentFilters.optionType || currentFilters.channelFilter;
            
            // Create filter controls bar with collapsible filters
            let filterControlsHtml = `
                <div style="background: #f9fafb; padding: 10px; border-radius: 8px 8px 0 0; border: 1px solid #e5e7eb; border-bottom: none; margin-bottom: 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: ${filtersExpanded ? '10px' : '0'};">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <button id="toggle-filters-btn" onclick="toggleFiltersPanel()" style="background: #3b82f6; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 500; display: flex; align-items: center; gap: 6px;">
                                ${filtersExpanded ? '▼ Hide Filters' : '▶ Show Filters'}
                            </button>
                            ${hasActiveFilters ? `
                                <button onclick="clearAllFilters()" style="background: #fbbf24; color: #92400e; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 500; transition: background 0.2s;" onmouseover="this.style.background='#f59e0b'" onmouseout="this.style.background='#fbbf24'">
                                    Clear All Filters
                                </button>
                            ` : ''}
                        </div>
                        <div style="font-size: 0.85rem; color: #6b7280;">
                            Showing ${allSignalsData.length} of ${allUnfilteredSignals.length} signals
                        </div>
                    </div>
                    <div id="filters-panel" style="display: ${filtersExpanded ? 'flex' : 'none'}; flex-direction: column; gap: 10px; padding-top: 10px; border-top: ${filtersExpanded ? '1px solid #e5e7eb' : 'none'};">
                        <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;" class="dashboard-channel-filters">
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-all-toggle" ${currentFilters.channelFilter === 'all' || currentFilters.channelFilter === '' ? 'checked' : ''} onchange="toggleChannelFilter('all')" style="cursor: pointer;">
                                <span>All</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-channel-management-toggle" ${!currentFilters.channelFilter || currentFilters.channelFilter === 'channel-management' ? 'checked' : ''} onchange="toggleChannelFilter('channel-management')" style="cursor: pointer;">
                                <span>Channel Management</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-x-channel-toggle" ${currentFilters.channelFilter === 'x' ? 'checked' : ''} onchange="toggleChannelFilter('x')" style="cursor: pointer;">
                                <span>X</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-tradingview-toggle" ${currentFilters.channelFilter === 'tradingview' ? 'checked' : ''} onchange="toggleChannelFilter('tradingview')" style="cursor: pointer;">
                                <span>TradingView</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-unmatched-toggle" ${currentFilters.channelFilter === 'unmatched' ? 'checked' : ''} onchange="toggleChannelFilter('unmatched')" style="cursor: pointer;">
                                <span>⚠️ Unmatched</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer; margin-left: 10px; padding-left: 10px; border-left: 1px solid #d1d5db;">
                                <input type="checkbox" id="exclude-commentary-toggle" ${currentFilters.excludeCommentary ? 'checked' : ''} onchange="toggleExcludeCommentary()" style="cursor: pointer;">
                                <span>Exclude Commentary</span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
            
            // Create table format for signals
            let tableHtml = filterControlsHtml + `
                <div class="dashboard-table-container" style="overflow-x: auto; overflow-y: visible; -webkit-overflow-scrolling: touch; margin-top: 0; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb; border-top: none;">
                <table style="min-width: 1200px; width: 100%; border-collapse: collapse; background: white; font-size: 0.85rem;">
                    <thead>
                        <tr style="background: #f3f4f6; border-bottom: 2px solid #e5e7eb;">
                            <th style="padding: 5px; text-align: left; font-weight: 600; color: #374151; width: 200px;">
                                <div>Status & Title</div>
                                <select id="filter-status" onchange="updateFilter('status', this.value)" style="width: 100%; padding: 4px; margin-top: 4px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.75rem;">
                                    <option value="">All</option>
                                    ${uniqueStatuses.map(s => `<option value="${s}" ${currentFilters.status === s ? 'selected' : ''}>${s}</option>`).join('')}
                                </select>
                            </th>
                            <th style="padding: 5px; text-align: left; font-weight: 600; color: #374151; width: 120px;">
                                <div>Channel</div>
                                <input type="text" id="filter-channel" oninput="updateFilter('channel', this.value)" placeholder="Filter..." value="${currentFilters.channel}" style="width: 100%; padding: 4px; margin-top: 4px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.75rem;">
                            </th>
                            <th style="padding: 5px; text-align: left; font-weight: 600; color: #374151; width: 80px;">
                                <div>Symbol</div>
                                <input type="text" id="filter-symbol" oninput="updateFilter('symbol', this.value)" placeholder="Filter..." value="${currentFilters.symbol}" style="width: 100%; padding: 4px; margin-top: 4px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.75rem;">
                            </th>
                            <th style="padding: 5px; text-align: left; font-weight: 600; color: #374151; width: 70px;">
                                <div>Action</div>
                                <select id="filter-action" onchange="updateFilter('action', this.value)" style="width: 100%; padding: 4px; margin-top: 4px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.75rem;">
                                    <option value="">All</option>
                                    ${uniqueActions.map(a => `<option value="${a}" ${currentFilters.action === a ? 'selected' : ''}>${a}</option>`).join('')}
                                </select>
                            </th>
                            <th style="padding: 5px; text-align: left; font-weight: 600; color: #374151; width: 80px;">
                                <div>Type</div>
                                <select id="filter-optionType" onchange="updateFilter('optionType', this.value)" style="width: 100%; padding: 4px; margin-top: 4px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.75rem;">
                                    <option value="">All</option>
                                    ${uniqueOptionTypes.map(t => `<option value="${t}" ${currentFilters.optionType === t ? 'selected' : ''}>${t}</option>`).join('')}
                                </select>
                            </th>
                            <th style="padding: 10px; text-align: left; font-weight: 600; color: #374151; width: 80px;">Strike</th>
                            <th style="padding: 10px; text-align: left; font-weight: 600; color: #374151; width: 100px;">Price</th>
                            <th style="padding: 10px; text-align: left; font-weight: 600; color: #374151; width: 100px;">Expiry</th>
                            <th style="padding: 10px; text-align: left; font-weight: 600; color: #374151; width: 80px;">Size</th>
                            <th style="padding: 10px; text-align: left; font-weight: 600; color: #374151;">Signal</th>
                            <th style="padding: 10px; text-align: left; font-weight: 600; color: #374151; width: 120px;">Time</th>
                            <th style="padding: 10px; text-align: center; font-weight: 600; color: #374151; width: 100px;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            signalsToShow.forEach(signal => {
                // Parse parsed_signal if available
                let parsedData = null;
                if (signal.parsed_signal) {
                    try {
                        parsedData = typeof signal.parsed_signal === 'string' 
                            ? JSON.parse(signal.parsed_signal) 
                            : signal.parsed_signal;
                    } catch (e) {
                        parsedData = null;
                    }
                }
                
                // Status colors and icons
                const statusColors = {
                    'executed': '#10b981',
                    'failed': '#fbbf24',
                    'execution_failed': '#fbbf24',
                    'parsed': '#3b82f6',
                    'processed': '#3b82f6',
                    'unmatched': '#fbbf24',
                    'validation_failed': '#f59e0b',
                    'parse_failed': '#f59e0b',
                    'received': '#6b7280'
                };
                
                const status = signal.status || 'received';
                const statusColor = statusColors[status] || '#6b7280';
                
                // Channel name
                const isUnmatched = signal.channel_name === 'UNMATCHED' || signal.status === 'unmatched';
                const channelName = isUnmatched ? '⚠️ UNMATCHED' : (signal.channel_name || '-');
                
                // Extract required fields from parsed data
                const symbol = parsedData?.symbol || signal.symbol || '-';
                const action = parsedData?.action || signal.action || '-';
                const optionType = parsedData?.option_type || signal.option_type || '-';
                const strike = parsedData?.strike || signal.strike || signal.strike_price || '-';
                const purchasePrice = parsedData?.purchase_price || signal.purchase_price || parsedData?.entry_price || signal.entry_price || '-';
                const positionSize = parsedData?.position_size || parsedData?.quantity || signal.position_size || signal.quantity || '-';
                
                // Format expiration date
                let expiryDisplay = '-';
                const expirationDate = parsedData?.expiration_date || signal.expiration_date;
                if (expirationDate) {
                    if (typeof expirationDate === 'object' && expirationDate !== null) {
                        const year = expirationDate.year || '';
                        const month = expirationDate.month || '';
                        const day = expirationDate.day || '';
                        if (month && day) {
                            expiryDisplay = `${month}/${day}${year ? '/' + year : ''}`;
                        } else if (month) {
                            expiryDisplay = month;
                        }
                    } else if (typeof expirationDate === 'string') {
                        try {
                            const date = new Date(expirationDate);
                            if (!isNaN(date.getTime())) {
                                expiryDisplay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                            } else {
                                expiryDisplay = expirationDate;
                            }
                        } catch (e) {
                            expiryDisplay = expirationDate;
                        }
                    }
                }
                
                // Signal content
                const signalContent = signal.message || signal.raw_content || signal.title || 'No content';
                const signalPreview = signalContent.length > 60 ? signalContent.substring(0, 60) + '...' : signalContent;
                
                // Format time
                const signalDate = new Date(signal.received_at || signal.created_at);
                const timeStr = signalDate.toLocaleTimeString();
                const dateStr = signalDate.toLocaleDateString();
                
                // Get title for display
                const signalTitle = signal.title || '-';
                
                // Format values for display
                const formatPrice = (val) => {
                    if (val === '-' || val === null || val === undefined || val === '') return '-';
                    const num = parseFloat(val);
                    return isNaN(num) ? '-' : `$${num.toFixed(2)}`;
                };
                const formatStrike = (val) => {
                    if (val === '-' || val === null || val === undefined || val === '') return '-';
                    const num = parseFloat(val);
                    return isNaN(num) ? '-' : `$${num}`;
                };
                
                // Check if signal is unread for dashboard (channel management channels)
                const isUnreadDashboard = isChannelManagementChannel(signal.channel_name) && !signal.dashboard_read;
                const unreadClass = isUnreadDashboard ? 'signal-unread-dashboard' : '';
                const cursorStyle = isUnreadDashboard ? 'cursor: pointer;' : '';
                const hoverBg = isUnreadDashboard ? '#c7d2fe' : '#f9fafb';
                const normalBg = isUnreadDashboard ? '#e0e7ff' : 'white';
                const dataMarkRead = isUnreadDashboard ? `data-mark-read="${signal.id}"` : '';
                
                tableHtml += `
                    <tr data-signal-id="${signal.id}" class="${unreadClass}" ${dataMarkRead} style="border-bottom: 1px solid #e5e7eb; ${cursorStyle}" onmouseover="this.style.background='${hoverBg}'" onmouseout="this.style.background='${normalBg}'">
                        <td style="padding: 10px;">
                            <div style="display: flex; flex-direction: column; gap: 6px;">
                                <span style="background: ${statusColor}; color: ${status === 'failed' || status === 'execution_failed' || status === 'unmatched' ? '#92400e' : 'white'}; padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 500; white-space: nowrap; width: fit-content;">
                                    ${status.toUpperCase()}
                                </span>
                                <div style="color: #1f2937; font-size: 0.85rem; word-break: break-word; line-height: 1.4;">${escapeHtml(signalTitle)}</div>
                            </div>
                        </td>
                        <td style="padding: 10px; color: #374151; font-size: 0.85rem;">${escapeHtml(channelName)}</td>
                        <td style="padding: 10px; color: #1f2937; font-weight: 600;">${escapeHtml(symbol)}</td>
                        <td style="padding: 10px; color: #1f2937;">
                            ${action !== '-' ? `<span style="background: ${action === 'BUY' ? '#10b981' : action === 'SELL' ? '#ef4444' : '#6b7280'}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">${escapeHtml(action)}</span>` : '-'}
                        </td>
                        <td style="padding: 10px; color: #6b7280; font-size: 0.85rem;">${escapeHtml(optionType)}</td>
                        <td style="padding: 10px; color: #1f2937; font-weight: 500;">${formatStrike(strike)}</td>
                        <td style="padding: 10px; color: #059669; font-weight: 600;">${formatPrice(purchasePrice)}</td>
                        <td style="padding: 10px; color: #6b7280; font-size: 0.8rem;">${escapeHtml(expiryDisplay)}</td>
                        <td style="padding: 10px; color: #6b7280; font-size: 0.85rem;">${positionSize !== '-' ? positionSize : '-'}</td>
                        <td style="padding: 10px; color: #1f2937; word-break: break-word; font-size: 0.85rem;" title="${escapeHtml(signalContent)}">${escapeHtml(signalPreview)}</td>
                        <td style="padding: 10px; color: #6b7280; font-size: 0.8rem; white-space: nowrap;">
                            ${timeStr}<br><small style="color: #9ca3af;">${dateStr}</small>
                        </td>
                        <td style="padding: 10px; text-align: center;">
                            <button onclick="deleteSignal(${signal.id})" style="background: transparent; color: #6b7280; border: 1px solid #d1d5db; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 0.8rem;" title="Delete">🗑️</button>
                        </td>
                    </tr>
                `;
            });
            
            tableHtml += `
                    </tbody>
                </table>
                </div>
            `;
            
            // Add "Show More" button if there are more signals
            if (allSignalsData.length > visibleSignalsCount) {
                const remainingCount = allSignalsData.length - visibleSignalsCount;
                const nextIncrement = Math.min(SIGNALS_INCREMENT, remainingCount);
                
                tableHtml += `
                    <div style="text-align: center; padding: 20px; margin-top: 20px;">
                        <button onclick="showMoreSignals()" class="btn btn-secondary" style="padding: 10px 20px; font-size: 0.9rem; font-weight: 500;">
                            Show More (${nextIncrement} more signal${nextIncrement !== 1 ? 's' : ''})
                        </button>
                        ${visibleSignalsCount > INITIAL_SIGNALS_LIMIT ? `
                            <button onclick="resetSignalsView()" class="btn btn-secondary" style="padding: 10px 20px; font-size: 0.9rem; font-weight: 500; margin-left: 10px;">
                                Show Less
                            </button>
                        ` : ''}
                        <p style="margin: 8px 0 0 0; color: #6b7280; font-size: 0.85rem;">Showing ${visibleSignalsCount} of ${allSignalsData.length} signals</p>
                    </div>
                `;
            } else if (visibleSignalsCount > INITIAL_SIGNALS_LIMIT && allSignalsData.length === visibleSignalsCount) {
                // All signals are shown, but more than initial limit
                tableHtml += `
                    <div style="text-align: center; padding: 20px; margin-top: 20px;">
                        <button onclick="resetSignalsView()" class="btn btn-secondary" style="padding: 10px 20px; font-size: 0.9rem; font-weight: 500;">
                            Show Less (${INITIAL_SIGNALS_LIMIT} most recent)
                        </button>
                        <p style="margin: 8px 0 0 0; color: #6b7280; font-size: 0.85rem;">Showing all ${allSignalsData.length} signals</p>
                    </div>
                `;
            }
            
            signalsList.innerHTML = tableHtml;
            
            // Attach click/touch event listeners for marking signals as read
            document.querySelectorAll('tr[data-mark-read]').forEach(row => {
                const signalId = parseInt(row.getAttribute('data-mark-read'));
                if (signalId) {
                    // Add both click and touchstart for mobile support
                    const handleMarkRead = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        markSignalAsReadInDashboard(signalId);
                    };
                    row.addEventListener('click', handleMarkRead);
                    row.addEventListener('touchend', handleMarkRead);
                }
            });
        } else {
            // Show filters even when no signals exist
            let filterControlsHtml = `
                <div style="background: #f9fafb; padding: 10px; border-radius: 8px 8px 0 0; border: 1px solid #e5e7eb; border-bottom: none; margin-bottom: 0;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: ${filtersExpanded ? '10px' : '0'};">
                        <button id="toggle-filters-btn" onclick="toggleFiltersPanel()" style="background: #3b82f6; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 500; display: flex; align-items: center; gap: 6px;">
                            ${filtersExpanded ? '▼ Hide Filters' : '▶ Show Filters'}
                        </button>
                        <div style="font-size: 0.85rem; color: #6b7280;">
                            Showing 0 of 0 signals
                        </div>
                    </div>
                    <div id="filters-panel" style="display: ${filtersExpanded ? 'flex' : 'none'}; flex-direction: column; gap: 10px; padding-top: 10px; border-top: ${filtersExpanded ? '1px solid #e5e7eb' : 'none'};">
                        <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;" class="dashboard-channel-filters">
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-all-toggle" ${currentFilters.channelFilter === 'all' || currentFilters.channelFilter === '' ? 'checked' : ''} onchange="toggleChannelFilter('all')" style="cursor: pointer;">
                                <span>All</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-channel-management-toggle" ${!currentFilters.channelFilter || currentFilters.channelFilter === 'channel-management' ? 'checked' : ''} onchange="toggleChannelFilter('channel-management')" style="cursor: pointer;">
                                <span>Channel Management</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-x-channel-toggle" ${currentFilters.channelFilter === 'x' ? 'checked' : ''} onchange="toggleChannelFilter('x')" style="cursor: pointer;">
                                <span>X</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-tradingview-toggle" ${currentFilters.channelFilter === 'tradingview' ? 'checked' : ''} onchange="toggleChannelFilter('tradingview')" style="cursor: pointer;">
                                <span>TradingView</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer;">
                                <input type="checkbox" id="show-unmatched-toggle" ${currentFilters.channelFilter === 'unmatched' ? 'checked' : ''} onchange="toggleChannelFilter('unmatched')" style="cursor: pointer;">
                                <span>⚠️ Unmatched</span>
                            </label>
                            <label style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer; margin-left: 10px; padding-left: 10px; border-left: 1px solid #d1d5db;">
                                <input type="checkbox" id="exclude-commentary-toggle" ${currentFilters.excludeCommentary ? 'checked' : ''} onchange="toggleExcludeCommentary()" style="cursor: pointer;">
                                <span>Exclude Commentary</span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
            
            signalsList.innerHTML = filterControlsHtml + `
                <div style="background: white; padding: 20px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb; border-top: none; text-align: center;">
                    <p class="loading" style="margin: 0;">No signals received yet</p>
                </div>
            `;
        }
    } catch (error) {
        signalsList.innerHTML = '<p class="loading">Error loading signals</p>';
        console.error('Error loading signals:', error);
    }
}

// Show 2 more signals
function showMoreSignals() {
    visibleSignalsCount = Math.min(visibleSignalsCount + SIGNALS_INCREMENT, allSignalsData.length);
    loadAllSignals();
}

// Reset to show only the 2 most recent signals
function resetSignalsView() {
    visibleSignalsCount = INITIAL_SIGNALS_LIMIT;
    loadAllSignals();
}

// Apply filters to signals
function applyFilters(signals) {
    return signals.filter(signal => {
        // Filter out Commentary signals if excludeCommentary is enabled
        if (currentFilters.excludeCommentary) {
            const channelName = signal.channel_name || '';
            if (channelName.toLowerCase() === 'commentary') {
                return false;
            }
        }
        
        // Filter by channel type (mutually exclusive)
        if (currentFilters.channelFilter) {
            if (currentFilters.channelFilter === 'channel-management') {
                // Show signals from all channel management channels
                const isChannelMgmt = isChannelManagementChannel(signal.channel_name);
                if (!isChannelMgmt) return false;
            } else if (currentFilters.channelFilter === 'x') {
                const isXChannel = signal.channel_name === 'x';
                if (!isXChannel) return false;
            } else if (currentFilters.channelFilter === 'tradingview') {
                const isTradingView = signal.channel_name === 'TradingView';
                if (!isTradingView) return false;
            } else if (currentFilters.channelFilter === 'unmatched') {
                // Show only unmatched signals
                const isUnmatched = signal.channel_name === 'UNMATCHED' || signal.status === 'unmatched';
                if (!isUnmatched) return false;
            }
            // If channelFilter is empty string or 'all', show all signals (no filtering)
        }
        
        // Filter by status
        if (currentFilters.status && signal.status !== currentFilters.status) {
            return false;
        }
        
        // Filter by channel
        if (currentFilters.channel) {
            const channelName = signal.channel_name || '';
            if (!channelName.toLowerCase().includes(currentFilters.channel.toLowerCase())) {
                return false;
            }
        }
        
        // Filter by symbol
        if (currentFilters.symbol) {
            let parsedData = null;
            if (signal.parsed_signal) {
                try {
                    parsedData = typeof signal.parsed_signal === 'string' 
                        ? JSON.parse(signal.parsed_signal) 
                        : signal.parsed_signal;
                } catch (e) {
                    parsedData = null;
                }
            }
            const symbol = parsedData?.symbol || signal.symbol || '';
            if (!symbol.toUpperCase().includes(currentFilters.symbol.toUpperCase())) {
                return false;
            }
        }
        
        // Filter by action
        if (currentFilters.action) {
            let parsedData = null;
            if (signal.parsed_signal) {
                try {
                    parsedData = typeof signal.parsed_signal === 'string' 
                        ? JSON.parse(signal.parsed_signal) 
                        : signal.parsed_signal;
                } catch (e) {
                    parsedData = null;
                }
            }
            const action = parsedData?.action || signal.action || '';
            if (action.toUpperCase() !== currentFilters.action.toUpperCase()) {
                return false;
            }
        }
        
        // Filter by option type
        if (currentFilters.optionType) {
            let parsedData = null;
            if (signal.parsed_signal) {
                try {
                    parsedData = typeof signal.parsed_signal === 'string' 
                        ? JSON.parse(signal.parsed_signal) 
                        : signal.parsed_signal;
                } catch (e) {
                    parsedData = null;
                }
            }
            const optionType = parsedData?.option_type || signal.option_type || '';
            if (optionType.toUpperCase() !== currentFilters.optionType.toUpperCase()) {
                return false;
            }
        }
        
        return true;
    });
}

// Update filter and reload signals
function updateFilter(filterType, value) {
    if (filterType === 'channelFilter') {
        currentFilters.channelFilter = value || 'channel-management';
    } else {
        currentFilters[filterType] = value;
    }
    visibleSignalsCount = INITIAL_SIGNALS_LIMIT; // Reset visible count when filter changes
    loadAllSignals();
}

// Toggle channel filter (mutually exclusive - only one can be selected at a time)
function toggleChannelFilter(filterType) {
    const allCheckbox = document.getElementById('show-all-toggle');
    const channelMgmtCheckbox = document.getElementById('show-channel-management-toggle');
    const xCheckbox = document.getElementById('show-x-channel-toggle');
    const tradingviewCheckbox = document.getElementById('show-tradingview-toggle');
    const unmatchedCheckbox = document.getElementById('show-unmatched-toggle');
    
    // If the clicked checkbox is being checked, uncheck others and set filter
    if (filterType === 'all' && allCheckbox && allCheckbox.checked) {
        if (channelMgmtCheckbox) channelMgmtCheckbox.checked = false;
        if (xCheckbox) xCheckbox.checked = false;
        if (tradingviewCheckbox) tradingviewCheckbox.checked = false;
        if (unmatchedCheckbox) unmatchedCheckbox.checked = false;
        currentFilters.channelFilter = '';
    } else if (filterType === 'channel-management' && channelMgmtCheckbox && channelMgmtCheckbox.checked) {
        if (allCheckbox) allCheckbox.checked = false;
        if (xCheckbox) xCheckbox.checked = false;
        if (tradingviewCheckbox) tradingviewCheckbox.checked = false;
        if (unmatchedCheckbox) unmatchedCheckbox.checked = false;
        currentFilters.channelFilter = 'channel-management';
    } else if (filterType === 'x' && xCheckbox && xCheckbox.checked) {
        if (allCheckbox) allCheckbox.checked = false;
        if (channelMgmtCheckbox) channelMgmtCheckbox.checked = false;
        if (tradingviewCheckbox) tradingviewCheckbox.checked = false;
        if (unmatchedCheckbox) unmatchedCheckbox.checked = false;
        currentFilters.channelFilter = 'x';
    } else if (filterType === 'tradingview' && tradingviewCheckbox && tradingviewCheckbox.checked) {
        if (allCheckbox) allCheckbox.checked = false;
        if (channelMgmtCheckbox) channelMgmtCheckbox.checked = false;
        if (xCheckbox) xCheckbox.checked = false;
        if (unmatchedCheckbox) unmatchedCheckbox.checked = false;
        currentFilters.channelFilter = 'tradingview';
    } else if (filterType === 'unmatched' && unmatchedCheckbox && unmatchedCheckbox.checked) {
        if (allCheckbox) allCheckbox.checked = false;
        if (channelMgmtCheckbox) channelMgmtCheckbox.checked = false;
        if (xCheckbox) xCheckbox.checked = false;
        if (tradingviewCheckbox) tradingviewCheckbox.checked = false;
        currentFilters.channelFilter = 'unmatched';
    } else {
        // If unchecking the current selection, revert to default (Channel Management)
        if (allCheckbox) allCheckbox.checked = false;
        if (channelMgmtCheckbox) channelMgmtCheckbox.checked = true;
        if (xCheckbox) xCheckbox.checked = false;
        if (tradingviewCheckbox) tradingviewCheckbox.checked = false;
        if (unmatchedCheckbox) unmatchedCheckbox.checked = false;
        currentFilters.channelFilter = 'channel-management';
    }
    
    visibleSignalsCount = INITIAL_SIGNALS_LIMIT;
    loadAllSignals();
}

// Toggle exclude commentary filter
function toggleExcludeCommentary() {
    const checkbox = document.getElementById('exclude-commentary-toggle');
    if (checkbox) {
        currentFilters.excludeCommentary = checkbox.checked;
        visibleSignalsCount = INITIAL_SIGNALS_LIMIT;
        loadAllSignals();
    }
}

// Toggle filter panel visibility
function toggleFiltersPanel() {
    filtersExpanded = !filtersExpanded;
    const filtersPanel = document.getElementById('filters-panel');
    const toggleButton = document.getElementById('toggle-filters-btn');
    if (filtersPanel) {
        filtersPanel.style.display = filtersExpanded ? 'flex' : 'none';
    }
    if (toggleButton) {
        toggleButton.textContent = filtersExpanded ? '▼ Hide Filters' : '▶ Show Filters';
    }
}

// ==================== Dashboard Badge Count for Channel Management ====================

async function countUnreadChannelManagementSignals() {
    try {
        const response = await fetch('/api/dashboard/unread-count');
        const data = await response.json();
        return data.count || 0;
    } catch (error) {
        console.error('[Dashboard] Error fetching unread count:', error);
        return 0;
    }
}

async function updateDashboardBadge() {
    try {
        const count = await countUnreadChannelManagementSignals();
        
        // Update mobile nav badge
        const mobileButton = document.querySelector('.mobile-tab-btn[onclick*="switchTab(\'dashboard\'"]');
        updateButtonBadge(mobileButton, count, 'dashboard-badge');
        
        // Update desktop nav badge
        const desktopButton = document.querySelector('.tabs > .tab-btn[onclick*="switchTab(\'dashboard\'"]');
        updateButtonBadge(desktopButton, count, 'dashboard-badge');
        
        // Update app icon badge
        updateAppIconBadge();
    } catch (error) {
        console.error('[Dashboard] Error updating badge:', error);
    }
}

// Helper function to update badge on a button
function updateButtonBadge(button, count, badgeClass) {
    if (!button) return;
    
    let badge = button.querySelector(`.${badgeClass}`);
            
            if (count > 0) {
                if (!badge) {
                    badge = document.createElement('span');
            badge.className = badgeClass;
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

async function markDashboardSignalsAsRead() {
    // Mark all channel management signals as read when Dashboard tab is opened
    try {
        const response = await fetch('/api/dashboard/mark-all-read', {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            // Update all signal rows to remove unread styling
            document.querySelectorAll('tr[data-signal-id]').forEach(row => {
                const signalId = parseInt(row.getAttribute('data-signal-id'));
                // Check if it's a channel management signal
                const channelCell = row.querySelector('td:nth-child(2)');
                if (channelCell) {
                    const channelName = channelCell.textContent.trim();
                    if (isChannelManagementChannel(channelName)) {
                        row.classList.remove('signal-unread-dashboard');
                    }
                }
            });
            
            // Update badge (should show 0 now)
            updateDashboardBadge();
        }
    } catch (error) {
        console.error('[Dashboard] Error marking all signals as read:', error);
    }
}

async function markSignalAsReadInDashboard(signalId) {
    try {
        const response = await fetch(`/api/signals/${signalId}/mark-dashboard-read`, {
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
            // Remove highlight from signal row and data attribute
            const signalRow = document.querySelector(`tr[data-signal-id="${signalId}"]`);
            if (signalRow) {
                signalRow.classList.remove('signal-unread-dashboard');
                signalRow.removeAttribute('data-mark-read');
                // Update background to normal (non-unread) state
                signalRow.style.background = 'white';
                // Remove event listeners by cloning the row
                const newRow = signalRow.cloneNode(true);
                signalRow.parentNode.replaceChild(newRow, signalRow);
            }
            
            // Update the signal data in allSignalsData
            const signal = allSignalsData.find(s => s.id === signalId);
            if (signal) {
                signal.dashboard_read = true;
            }
            
            // Update badge count
            updateDashboardBadge();
        } else {
            console.error('[Dashboard] Failed to mark signal as read:', data.error);
            alert('Failed to mark signal as read. Please try again.');
        }
    } catch (error) {
        console.error('[Dashboard] Error marking signal as read:', error);
        alert('Error marking signal as read. Please check your connection and try again.');
    }
}

// Auto-mark dashboard signals older than 1 hour as read
async function dashboardAutoMarkOldSignalsAsRead() {
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000); // 1 hour in milliseconds
    
    for (const signal of allSignalsData) {
        // Only process channel management signals that are unread
        if (isChannelManagementChannel(signal.channel_name) && !signal.dashboard_read) {
            if (signal.received_at) {
                const signalTime = new Date(signal.received_at);
                if (signalTime < oneHourAgo) {
                    // Mark as read in database
                    try {
                        const response = await fetch(`/api/signals/${signal.id}/mark-dashboard-read`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' }
                        });
                        const data = await response.json();
                        if (data.success) {
                            signal.dashboard_read = true;
                            console.log(`[Dashboard] Auto-marked old signal ${signal.id} as read (older than 1 hour)`);
                        }
                    } catch (error) {
                        console.error(`[Dashboard] Error auto-marking signal ${signal.id} as read:`, error);
                    }
                }
            }
        }
    }
    
    // Update badge after marking old signals as read
    updateDashboardBadge();
}

// ==================== App Icon Badge Management ====================

// Throttle badge updates to prevent excessive service worker messages
let badgeUpdateTimeout = null;
let lastBadgeCount = -1;

async function updateAppIconBadge() {
    // Throttle: only update if last update was more than 500ms ago
    if (badgeUpdateTimeout) {
        return; // Skip if update is already pending
    }
    
    badgeUpdateTimeout = setTimeout(async () => {
        try {
            // Fetch both counts from API (async)
            const [dashboardResponse, xResponse] = await Promise.all([
                fetch('/api/dashboard/unread-count'),
                fetch('/api/x/unread-count')
            ]);
            
            const dashboardData = await dashboardResponse.json();
            const xData = await xResponse.json();
            
            const totalUnread = (dashboardData.count || 0) + (xData.count || 0);
            
            // Only update if count actually changed
            if (totalUnread !== lastBadgeCount) {
                lastBadgeCount = totalUnread;
                appBadgeCount = totalUnread;
                
                // Update app icon badge via service worker
                if ('serviceWorker' in navigator) {
                    navigator.serviceWorker.ready.then((registration) => {
                        if (registration.active) {
                            registration.active.postMessage({
                                type: 'update_badge',
                                count: totalUnread
                            });
                        }
                    });
                }
                
                // Also try direct badge API if available
                if ('setAppBadge' in navigator) {
                    if (totalUnread > 0) {
                        navigator.setAppBadge(totalUnread).catch(err => {
                            console.log('[App] Could not set app badge:', err);
                        });
                    } else {
                        navigator.clearAppBadge().catch(err => {
                            console.log('[App] Could not clear app badge:', err);
                        });
                    }
                }
            }
        } catch (error) {
            console.error('[App] Error updating app icon badge:', error);
        } finally {
            badgeUpdateTimeout = null;
        }
    }, 500); // Throttle to max once per 500ms
}

function clearAppIconBadge() {
    appBadgeCount = 0;
    
    // Clear badge via service worker
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.ready.then((registration) => {
            if (registration.active) {
                registration.active.postMessage({
                    type: 'clear_badge'
                });
            }
        });
    }
    
    // Also try direct badge API if available
    if ('clearAppBadge' in navigator) {
        navigator.clearAppBadge().catch(err => {
            console.log('[App] Could not clear app badge:', err);
        });
    }
}

function navigateToDashboardSignal(signalId) {
    console.log('[Dashboard] Navigating to signal:', signalId);
    
    // Switch to Dashboard tab if not already there
    const dashboardTab = document.getElementById('dashboard-tab');
    if (dashboardTab && !dashboardTab.classList.contains('active')) {
        // Try to use switchTab function if available
        if (typeof switchTab === 'function') {
            switchTab('dashboard');
        } else {
            // Fallback: find the Dashboard tab button and click it
            const dashboardTabButton = Array.from(document.querySelectorAll('.tab-btn')).find(btn => {
                const onclick = btn.getAttribute('onclick') || '';
                return onclick.includes("'dashboard'") || onclick.includes('"dashboard"') || btn.textContent.includes('Dashboard');
            });
            if (dashboardTabButton) {
                dashboardTabButton.click();
            }
        }
    }
    
    // Wait a bit for tab to switch and signals to load, then scroll to signal
    setTimeout(() => {
        // Reload signals to ensure the signal is in the list
        loadAllSignals();
        
        // Wait a bit more for signals to render
        setTimeout(() => {
            // Find the signal in the table/list
            const signalRow = document.querySelector(`tr[data-signal-id="${signalId}"]`) || 
                            document.querySelector(`[data-signal-id="${signalId}"]`);
            
            if (signalRow) {
                // Scroll to signal row
                signalRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                
                // Highlight the signal row temporarily
                signalRow.style.transition = 'box-shadow 0.3s ease';
                signalRow.style.boxShadow = '0 0 20px rgba(59, 130, 246, 0.6)';
                signalRow.style.border = '2px solid #3b82f6';
                
                // Remove highlight after 3 seconds
                setTimeout(() => {
                    signalRow.style.boxShadow = '';
                    signalRow.style.border = '';
                }, 3000);
            } else {
                console.warn('[Dashboard] Signal row not found:', signalId);
                // Signal might not be loaded yet, try loading signals first
                setTimeout(() => {
                    navigateToDashboardSignal(signalId);
                }, 500);
            }
        }, 500);
    }, 300);
}

// Listen for messages from service worker for dashboard navigation and badge updates
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
        console.log('[App] Message from service worker:', event.data);
        if (event.data && event.data.type === 'navigate_to_signal') {
            const signalId = event.data.signal_id;
            const tab = event.data.tab;
            
            if (tab === 'dashboard' && signalId) {
                navigateToDashboardSignal(signalId);
            }
        } else if (event.data && event.data.type === 'badge_updated') {
            // Service worker updated badge, sync our count
            appBadgeCount = event.data.count || 0;
        }
    });
}

// Clear all filters
function clearAllFilters() {
    currentFilters = {
        status: '',
        channel: '',
        symbol: '',
        action: '',
        optionType: '',
        channelFilter: 'channel-management', // Keep default behavior (Channel Management)
        excludeCommentary: true // Keep exclude commentary enabled by default
    };
    visibleSignalsCount = INITIAL_SIGNALS_LIMIT;
    loadAllSignals();
}

function createSignalCardWithSource(signal) {
    const card = document.createElement('div');
    card.className = 'signal-card';
    card.setAttribute('data-signal-id', signal.id);
    
    // Check if signal is matched or unmatched
    const isUnmatched = signal.channel_name === 'UNMATCHED' || signal.status === 'unmatched';
    const isMatched = !isUnmatched && signal.channel_name && signal.channel_name !== 'UNMATCHED';
    
    // Extract source from channel_name or source field
    const source = signal.source || (signal.channel_name && signal.channel_name.startsWith('external_') 
        ? signal.channel_name.replace('external_', '') 
        : 'api');
    
    const sourceBadge = source === 'chrome_extension' ? '🔔 Chrome' : 
                        source === 'api' ? '📡 API' : 
                        '🌐 ' + source;
    
    const statusClass = signal.status === 'executed' ? 'success' :
                        signal.status === 'failed' || signal.status === 'execution_failed' ? 'error' :
                        signal.status === 'parsed' || signal.status === 'processed' ? 'warning' :
                        signal.status === 'unmatched' ? 'error' : 'info';
    
    // Get signal details if available
    const signalDetails = signal.parsed_signal ? createSignalDetails(signal) : '';
    
    // Display title and message separately if available, otherwise use raw_content
    let contentDisplay = '';
    if (signal.title || signal.message) {
        contentDisplay = `
            ${signal.title ? `<div style="margin-bottom: 8px;"><strong>Title:</strong> ${escapeHtml(signal.title)}</div>` : ''}
            ${signal.message ? `<div><strong>Message:</strong> ${escapeHtml(signal.message)}</div>` : ''}
        `;
    } else {
        contentDisplay = `<div class="signal-raw">${escapeHtml(signal.raw_content || 'No content')}</div>`;
    }
    
    // Match status badge
    const matchBadge = isUnmatched 
        ? '<span class="signal-status error" style="margin-left: 8px;">⚠️ UNMATCHED</span>'
        : isMatched 
        ? `<span class="signal-status success" style="margin-left: 8px;">✅ Matched: ${escapeHtml(signal.channel_name)}</span>`
        : '';
    
    card.innerHTML = `
        <div class="signal-header">
            <div>
                <span class="signal-source-badge">${sourceBadge}</span>
                <span class="signal-status ${statusClass}">${signal.status || 'received'}</span>
                ${matchBadge}
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <div class="signal-time">${new Date(signal.received_at).toLocaleString()}</div>
                <button onclick="deleteSignal(${signal.id})" class="btn-delete-signal" title="Delete this signal">🗑️</button>
            </div>
        </div>
        <div class="signal-content">
            ${contentDisplay}
            ${signalDetails ? `<div class="signal-parsed"><div class="signal-details">${signalDetails}</div></div>` : ''}
        </div>
        ${isUnmatched ? '<div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 4px; color: #856404;"><strong>⚠️ No matching channel found.</strong> This signal was not matched to any channel based on title filter.</div>' : ''}
    `;
    
    return card;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function startSignalsAutoRefresh() {
    const checkbox = document.getElementById('auto-refresh-signals');
    if (!checkbox) return;

    // Clear existing interval
    if (signalsAutoRefreshInterval) {
        clearInterval(signalsAutoRefreshInterval);
    }

    // Start auto-refresh if checkbox is checked (dashboard is default tab)
    if (checkbox.checked) {
        signalsAutoRefreshInterval = setInterval(() => {
            const checkbox = document.getElementById('auto-refresh-signals');
            if (checkbox && checkbox.checked) {
                // Only refresh if we're still on the dashboard tab
                const dashboardTab = document.getElementById('dashboard-tab');
                if (dashboardTab && dashboardTab.classList.contains('active')) {
                    console.log('Auto-refreshing dashboard signals...');
                    loadAllSignals();
                }
            }
        }, 3000); // Refresh every 3 seconds
        console.log('Dashboard auto-refresh started');
    }
}

function stopSignalsAutoRefresh() {
    if (signalsAutoRefreshInterval) {
        clearInterval(signalsAutoRefreshInterval);
        signalsAutoRefreshInterval = null;
        console.log('Dashboard auto-refresh stopped');
    }
}

// Delete individual signal
async function deleteSignal(signalId) {
    // Confirm deletion
    if (!confirm('Are you sure you want to delete this signal? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/signals/${signalId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Remove the signal card from UI immediately
            const signalCard = document.querySelector(`[data-signal-id="${signalId}"]`);
            if (signalCard) {
                signalCard.style.opacity = '0';
                signalCard.style.transition = 'opacity 0.3s';
                setTimeout(() => {
                    signalCard.remove();
                    // Reload signals to update the list
                    loadAllSignals();
                }, 300);
            } else {
                // If card not found by data attribute, just reload
                loadAllSignals();
            }
        } else {
            alert(`Error deleting signal: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error deleting signal:', error);
        alert(`Error deleting signal: ${error.message}`);
    }
}

// Clear all input signals
async function clearAllInputSignals() {
    // Confirm action
    const confirmed = confirm(
        '⚠️ Are you sure you want to clear ALL input signals?\n\n' +
        'This action cannot be undone. All signal history will be permanently deleted.'
    );
    
    if (!confirmed) {
        return;
    }
    
    await clearSignalsBySource(null);
}

// Clear signals by source (null = all)
async function clearFilteredSignals() {
    const sourceFilter = document.getElementById('signal-source-filter')?.value || '';
    
    if (!sourceFilter) {
        // If no filter, use clear all
        clearAllInputSignals();
        return;
    }
    
    const sourceName = sourceFilter === 'chrome_extension' ? 'Chrome Extension' :
                      sourceFilter === 'api' ? 'API' :
                      sourceFilter === 'external' ? 'External' : sourceFilter;
    
    // Confirm action
    const confirmed = confirm(
        `⚠️ Are you sure you want to clear all signals from "${sourceName}"?\n\n` +
        'This action cannot be undone. All signals from this source will be permanently deleted.'
    );
    
    if (!confirmed) {
        return;
    }
    
    await clearSignalsBySource(sourceFilter);
}

// Helper function to clear signals by source
async function clearSignalsBySource(source) {
    const signalsList = document.getElementById('all-signals-list');
    signalsList.innerHTML = '<p class="loading">Clearing signals...</p>';
    
    try {
        const response = await fetch('/api/signals/clear-by-source', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ source: source || '' }) // Empty source = clear all
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show success message
            signalsList.innerHTML = `
                <div class="result-box success" style="padding: 20px; text-align: center;">
                    <h3>✅ Signals Cleared Successfully</h3>
                    <p><strong>${data.total_deleted}</strong> record(s) deleted</p>
                    <p>${data.signals_deleted} signal(s) and ${data.executions_deleted} execution(s) removed</p>
                </div>
            `;
            
            // Refresh the list after a short delay
            setTimeout(() => {
                loadAllSignals();
            }, 2000);
        } else {
            signalsList.innerHTML = `
                <div class="result-box error" style="padding: 20px;">
                    <h3>❌ Error Clearing Signals</h3>
                    <p>${data.error || 'Unknown error occurred'}</p>
                    <button onclick="loadAllSignals()" class="btn btn-secondary" style="margin-top: 10px;">🔄 Reload</button>
                </div>
            `;
        }
    } catch (error) {
        signalsList.innerHTML = `
            <div class="result-box error" style="padding: 20px;">
                <h3>❌ Error Clearing Signals</h3>
                <p>${error.message}</p>
                <button onclick="loadAllSignals()" class="btn btn-secondary" style="margin-top: 10px;">🔄 Reload</button>
            </div>
        `;
        console.error('Error clearing signals:', error);
    }
}

// Create signal card
function createSignalCard(signal) {
    const card = document.createElement('div');
    card.className = `signal-card ${signal.execution_status || signal.status}`;
    
    const statusClass = signal.execution_status === 'executed' ? 'executed' : 
                       signal.status === 'failed' ? 'failed' : 'pending';
    
    card.innerHTML = `
        <div class="signal-header">
            <span class="signal-channel">📡 ${signal.channel_name}</span>
            <span class="signal-status ${statusClass}">${signal.execution_status || signal.status}</span>
        </div>
        <div class="signal-content">${signal.raw_content}</div>
        ${signal.parsed_signal ? `
            <div class="signal-details">
                ${createSignalDetails(signal)}
            </div>
        ` : ''}
        <div style="margin-top: 10px; font-size: 0.85rem; color: var(--text-secondary);">
            ${new Date(signal.received_at).toLocaleString()}
        </div>
    `;
    
    return card;
}

// Create signal details - Shows ALL required fields, including null values
function createSignalDetails(signal) {
    let details = '';
    
    // Parse parsed_signal if it's a JSON string
    let parsedData = null;
    if (signal.parsed_signal) {
        try {
            parsedData = typeof signal.parsed_signal === 'string' 
                ? JSON.parse(signal.parsed_signal) 
                : signal.parsed_signal;
        } catch (e) {
            parsedData = null;
        }
    }
    
    // Helper function to format field display
    function formatField(label, value, formatter = null) {
        const displayValue = value !== null && value !== undefined 
            ? (formatter ? formatter(value) : value) 
            : '<span style="color: #999; font-style: italic;">null</span>';
        return `<div class="signal-detail"><strong>${label}:</strong> ${displayValue}</div>`;
    }
    
    // REQUIRED FIELDS - Always display all 8 required fields
    details += '<div style="margin-top: 10px; padding: 10px; background: #f0f0f0; border-radius: 4px;"><strong style="color: #333;">Required Fields:</strong></div>';
    
    // 1. Stock Ticker (symbol)
    const symbol = signal.symbol || (parsedData && parsedData.symbol);
    details += formatField('Stock Ticker', symbol);
    
    // 2. Direction (action)
    const action = signal.action || (parsedData && parsedData.action);
    details += formatField('Direction', action);
    
    // 3. Expiry Date (expiration_date) - Handle both full dates and partial dates
    const expirationDate = signal.expiration_date || (parsedData && parsedData.expiration_date);
    details += formatField('Expiry Date', expirationDate, (val) => {
        if (!val) return null;
        // Check if it's a partial date object
        if (typeof val === 'object' && (val.year !== undefined || val.month !== undefined || val.day !== undefined)) {
            const year = val.year || 'null';
            const month = val.month || 'null';
            const day = val.day || 'null';
            return `${month}/${day}/${year}`;
        }
        // Full date string
        return val;
    });
    
    // 4. Option Type (option_type)
    const optionType = signal.option_type || (parsedData && parsedData.option_type);
    details += formatField('Option Type', optionType);
    
    // 5. Strike Price (strike)
    const strike = signal.strike || (parsedData && parsedData.strike);
    details += formatField('Strike Price', strike, (val) => `$${val}`);
    
    // 6. Purchase Price (purchase_price)
    const purchasePrice = signal.purchase_price || (parsedData && parsedData.purchase_price);
    details += formatField('Purchase Price', purchasePrice, (val) => `$${val}`);
    
    // 7. Fraction (fraction)
    const fraction = parsedData && parsedData.fraction;
    details += formatField('Fraction', fraction, (val) => {
        const percentage = (val * 100).toFixed(0);
        return `${val} (${percentage}%)`;
    });
    
    // 8. Position Size (position_size)
    const positionSize = parsedData && (parsedData.position_size || parsedData.quantity);
    details += formatField('Position Size', positionSize);
    
    // Additional optional fields
    const entryPrice = parsedData && parsedData.entry_price;
    const stopLoss = parsedData && parsedData.stop_loss;
    const takeProfit = parsedData && parsedData.take_profit;
    
    if (entryPrice || stopLoss || takeProfit) {
        details += '<div style="margin-top: 10px; padding: 10px; background: #f9f9f9; border-radius: 4px;"><strong style="color: #666;">Additional Fields:</strong></div>';
        
        if (entryPrice && !purchasePrice) {
            details += formatField('Entry Price', entryPrice, (val) => `$${val}`);
        }
        if (stopLoss) {
            details += formatField('Stop Loss', stopLoss, (val) => `$${val}`);
        }
        if (takeProfit) {
            details += formatField('Take Profit', takeProfit, (val) => `$${val}`);
        }
    }
    
    if (signal.webull_order_id) {
        details += `<div class="signal-detail"><strong>Order ID:</strong> ${signal.webull_order_id}</div>`;
    }
    if (signal.error_message) {
        details += `<div class="signal-detail" style="color: var(--danger-color);"><strong>Error:</strong> ${signal.error_message}</div>`;
    }
    
    return details;
}

// Send test signal
async function sendTestSignal(event) {
    event.preventDefault();
    
    const channel = document.getElementById('test-channel').value;
    const signal = document.getElementById('test-signal').value;
    const resultBox = document.getElementById('test-result');
    
    try {
        const response = await fetch('/api/signal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: channel,
                content: signal
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            const parsed = data.parsed_signal || {};
            let detailsHtml = `<strong>Order ID:</strong> ${data.order_id || 'N/A'}<br><br>`;
            
            // Show ALL required fields (8 fields) - always display, show null if not found
            detailsHtml += `<strong>Required Fields:</strong><br>`;
            
            // Helper to format field for test display
            function formatTestField(label, value, formatter = null) {
                if (value !== null && value !== undefined) {
                    return `<strong>${label}:</strong> ${formatter ? formatter(value) : value}<br>`;
                } else {
                    return `<strong>${label}:</strong> <span style="color: #999; font-style: italic;">null</span><br>`;
                }
            }
            
            // 1. Stock Ticker
            detailsHtml += formatTestField('Stock Ticker', parsed.symbol);
            
            // 2. Direction
            detailsHtml += formatTestField('Direction', parsed.action);
            
            // 3. Expiry Date - Handle both full dates and partial dates
            const expirationDate = parsed.expiration_date;
            detailsHtml += formatTestField('Expiry Date', expirationDate, (val) => {
                if (!val) return null;
                // Check if it's a partial date object
                if (typeof val === 'object' && (val.year !== undefined || val.month !== undefined || val.day !== undefined)) {
                    const year = val.year || 'null';
                    const month = val.month || 'null';
                    const day = val.day || 'null';
                    return `${month}/${day}/${year}`;
                }
                // Full date string
                return val;
            });
            
            // 4. Option Type
            detailsHtml += formatTestField('Option Type', parsed.option_type);
            
            // 5. Strike Price
            detailsHtml += formatTestField('Strike Price', parsed.strike, (val) => `$${val}`);
            
            // 6. Purchase Price
            detailsHtml += formatTestField('Purchase Price', parsed.purchase_price, (val) => `$${val}`);
            
            // 7. Fraction
            const fraction = parsed.fraction;
            if (fraction !== null && fraction !== undefined) {
                const percentage = (fraction * 100).toFixed(0);
                detailsHtml += formatTestField('Fraction', fraction, (val) => `${val} (${percentage}%)`);
            } else {
                detailsHtml += formatTestField('Fraction', null);
            }
            
            // 8. Position Size
            const positionSize = parsed.position_size || parsed.quantity;
            detailsHtml += formatTestField('Position Size', positionSize);
            
            // Additional fields if present
            if (parsed.entry_price || parsed.stop_loss || parsed.take_profit) {
                detailsHtml += `<br><strong>Additional Fields:</strong><br>`;
                if (parsed.entry_price && !parsed.purchase_price) {
                    detailsHtml += formatTestField('Entry Price', parsed.entry_price, (val) => `$${val}`);
                }
                if (parsed.stop_loss) {
                    detailsHtml += formatTestField('Stop Loss', parsed.stop_loss, (val) => `$${val}`);
                }
                if (parsed.take_profit) {
                    detailsHtml += formatTestField('Take Profit', parsed.take_profit, (val) => `$${val}`);
                }
            }
            
            showResult(resultBox, 'success', `
                ✅ Signal processed successfully!<br>
                ${detailsHtml}
                ${data.warnings && data.warnings.length > 0 ? 
                  `<br><strong>Warnings:</strong> ${data.warnings.join(', ')}` : ''}
            `);
            
            // Refresh signals list
            loadAllSignals();
            
            // Clear form
            document.getElementById('test-signal-form').reset();
        } else {
            let errorHtml = `❌ Error: ${data.error || 'Unknown error'}<br>`;
            
            // Show validation errors if present
            if (data.validation_errors && data.validation_errors.length > 0) {
                errorHtml += `<br><strong>Validation Errors:</strong><br>`;
                data.validation_errors.forEach(err => {
                    errorHtml += `• ${err}<br>`;
                });
            }
            
            // Show missing fields if present
            if (data.missing_fields && data.missing_fields.length > 0) {
                errorHtml += `<br><strong>Missing Required Fields:</strong><br>`;
                data.missing_fields.forEach(field => {
                    errorHtml += `• ${field}<br>`;
                });
            }
            
            // Show parsed signal data if available (for debugging)
            if (data.parsed_signal) {
                errorHtml += `<br><strong>Parsed Signal Data:</strong><br>`;
                errorHtml += `<pre style="background: #f0f0f0; padding: 10px; border-radius: 4px; font-size: 0.9rem;">${JSON.stringify(data.parsed_signal, null, 2)}</pre>`;
            }
            
            // Show other details
            if (data.details) {
                errorHtml += `<br>Details: ${data.details}`;
            }
            
            showResult(resultBox, 'error', errorHtml);
        }
    } catch (error) {
        showResult(resultBox, 'error', `❌ Error: ${error.message}`);
    }
}

// Reset prompt builder
function resetPromptBuilder() {
    const action = document.querySelector('input[name="prompt-action"]:checked').value;
    const newInput = document.getElementById('new-channel-input');
    const existingInput = document.getElementById('existing-channel-input');
    
    if (action === 'create') {
        newInput.style.display = 'block';
        existingInput.style.display = 'none';
    } else {
        newInput.style.display = 'none';
        existingInput.style.display = 'block';
        loadChannelsForSelectChat();
    }
    
    // Reset conversation state
    conversationState = {
        conversationId: null,
        context: {},
        isActive: false,
        isFirstMessage: true,
        builderPromptUsed: null
    };
    
    // Reset chat UI
    const chatMessages = document.getElementById('chat-messages');
    chatMessages.innerHTML = `
        <div class="chat-message bot-message">
            <div class="message-content">
                <strong>AI Assistant:</strong><br>
                Hello! I'm here to help you build a channel-specific prompt. 
                <br><br>
                <strong>How it works:</strong><br>
                1. Paste ALL your trade signals below (any format, with or without dates)<br>
                2. I'll analyze them and ask clarifying questions if needed<br>
                3. Answer my questions in the chat<br>
                4. Once I understand the format, I'll generate the perfect parsing prompt!<br>
                <br>
                Ready? Paste your signals below! 👇
            </div>
        </div>
    `;
    
    document.getElementById('chat-input').value = '';
    document.getElementById('send-button').style.display = 'inline-flex';
    document.getElementById('generate-button').style.display = 'none';
}

// Send chat message (start or continue conversation)
async function sendChatMessage() {
    const chatInput = document.getElementById('chat-input');
    const message = chatInput.value.trim();
    
    if (!message) {
        alert('Please enter a message');
        return;
    }
    
    const action = document.querySelector('input[name="prompt-action"]:checked').value;
    const channelName = action === 'create' ? 
        document.getElementById('chat-channel-name').value :
        document.getElementById('chat-channel-select').value;
    
    if (!channelName) {
        alert('Please enter or select a channel name');
        return;
    }
    
    // Add user message to chat
    addChatMessage(message, 'user');
    chatInput.value = '';
    
    // Show loading
    addChatLoading();
    
    // Disable input
    chatInput.disabled = true;
    document.getElementById('send-button').disabled = true;
    
    try {
        let response, data;
        
        if (conversationState.isFirstMessage) {
            // Get title filter and model provider if provided
            const titleFilter = document.getElementById('chat-title-filter')?.value.trim() || null;
            const modelProvider = document.getElementById('chat-model-provider')?.value || 'openai';
            
            // Start new conversation
            response = await fetch('/api/prompt-builder/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    channel_name: channelName,
                    signals_dump: message,
                    title_filter: titleFilter,
                    model_provider: modelProvider,
                    is_update: action === 'update'
                })
            });
            
            data = await response.json();
            
            if (response.ok && data.success) {
                conversationState.conversationId = data.conversation_id;
                conversationState.context = data.context;
                conversationState.isActive = true;
                conversationState.isFirstMessage = false;
                
                removeChatLoading();
                addChatMessage(data.response, 'bot');
                
                if (data.ready_to_build) {
                    document.getElementById('send-button').style.display = 'none';
                    document.getElementById('generate-button').style.display = 'inline-flex';
                }
            } else {
                removeChatLoading();
                addChatMessage(`❌ Error: ${data.error || 'Unknown error'}`, 'bot');
            }
        } else {
            // Continue existing conversation
            response = await fetch('/api/prompt-builder/continue', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: conversationState.conversationId,
                    user_response: message,
                    context: conversationState.context
                })
            });
            
            data = await response.json();
            
            if (response.ok && data.success) {
                conversationState.context = data.context;
                
                removeChatLoading();
                addChatMessage(data.response, 'bot');
                
                if (data.ready_to_build) {
                    document.getElementById('send-button').style.display = 'none';
                    document.getElementById('generate-button').style.display = 'inline-flex';
                }
            } else {
                removeChatLoading();
                addChatMessage(`❌ Error: ${data.error || 'Unknown error'}`, 'bot');
            }
        }
    } catch (error) {
        removeChatLoading();
        addChatMessage(`❌ Error: ${error.message}`, 'bot');
    } finally {
        chatInput.disabled = false;
        document.getElementById('send-button').disabled = false;
        chatInput.focus();
    }
}

// Generate final prompt
async function generateFinalPrompt() {
    if (!conversationState.conversationId) {
        alert('No active conversation');
        return;
    }
    
    // Show loading
    addChatLoading();
    
    // Disable buttons
    document.getElementById('generate-button').disabled = true;
    
    try {
        const response = await fetch('/api/prompt-builder/finalize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_id: conversationState.conversationId,
                context: conversationState.context
            })
        });
        
        const data = await response.json();
        
        removeChatLoading();
        
        if (response.ok && data.success) {
            const channelName = conversationState.context.channel_name;
            const isUpdate = conversationState.context.is_update;
            
            // Store the builder prompt used
            conversationState.builderPromptUsed = data.builder_prompt_used;
            
            // Update context with finalize prompts if available
            if (data.context) {
                conversationState.context = { ...conversationState.context, ...data.context };
            }
            
            addChatMessage(`
                ✅ **Prompt ${isUpdate ? 'Updated' : 'Created'} Successfully!**<br><br>
                <strong>Channel:</strong> ${channelName}<br><br>
                <strong>Generated Prompt:</strong><br>
                <div style="background: #f0f0f0; padding: 15px; border-radius: 4px; margin-top: 10px; max-height: 300px; overflow-y: auto; white-space: pre-wrap; font-size: 0.85rem;">${data.prompt}</div>
                <br>
                <button onclick="showBuilderPrompt()" class="btn btn-secondary" style="margin-top: 10px;">🔍 View Builder Prompt Used</button>
                <br><br>
                You can now use this channel to receive and process trade signals! 🎉
            `, 'bot');
            
            // Hide generate button
            document.getElementById('generate-button').style.display = 'none';
            
            // Reload channels
            loadChannels();
        } else {
            addChatMessage(`❌ Error generating prompt: ${data.error || 'Unknown error'}`, 'bot');
        }
    } catch (error) {
        removeChatLoading();
        addChatMessage(`❌ Error: ${error.message}`, 'bot');
    } finally {
        document.getElementById('generate-button').disabled = false;
    }
}

// Add message to chat
function addChatMessage(message, type) {
    const chatMessages = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}-message`;
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    if (type === 'bot') {
        // Parse markdown-style formatting for bot messages
        let formatted = '';
        const lines = message.split('\n');
        let inList = false;
        let listType = null; // 'ul' or 'ol'
        
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            const trimmed = line.trim();
            
            // Headers
            if (trimmed.startsWith('#### ')) {
                if (inList) {
                    formatted += listType === 'ul' ? '</ul>' : '</ol>';
                    inList = false;
                }
                formatted += `<h4>${trimmed.substring(5)}</h4><br>`;
            } else if (trimmed.startsWith('### ')) {
                if (inList) {
                    formatted += listType === 'ul' ? '</ul>' : '</ol>';
                    inList = false;
                }
                formatted += `<h3>${trimmed.substring(4)}</h3><br>`;
            } else if (trimmed.startsWith('## ')) {
                if (inList) {
                    formatted += listType === 'ul' ? '</ul>' : '</ol>';
                    inList = false;
                }
                formatted += `<h2>${trimmed.substring(3)}</h2><br>`;
            } else if (trimmed.startsWith('# ')) {
                if (inList) {
                    formatted += listType === 'ul' ? '</ul>' : '</ol>';
                    inList = false;
                }
                formatted += `<h1>${trimmed.substring(2)}</h1><br>`;
            } else if (/^[\*\-\+] /.test(trimmed)) {
                // Bullet point
                if (!inList || listType !== 'ul') {
                    if (inList && listType === 'ol') {
                        formatted += '</ol>';
                    }
                    formatted += '<ul>';
                    inList = true;
                    listType = 'ul';
                }
                formatted += `<li>${trimmed.substring(2)}</li>`;
            } else if (/^\d+\. /.test(trimmed)) {
                // Numbered list
                if (!inList || listType !== 'ol') {
                    if (inList && listType === 'ul') {
                        formatted += '</ul>';
                    }
                    formatted += '<ol>';
                    inList = true;
                    listType = 'ol';
                }
                const match = trimmed.match(/^\d+\. (.+)$/);
                formatted += `<li>${match ? match[1] : trimmed}</li>`;
            } else if (trimmed === '') {
                // Empty line - close list if open, add spacing
                if (inList) {
                    formatted += listType === 'ul' ? '</ul>' : '</ol>';
                    inList = false;
                }
                formatted += '<br>';
            } else {
                // Regular text line
                if (inList) {
                    formatted += listType === 'ul' ? '</ul>' : '</ol>';
                    inList = false;
                }
                // Convert bold text
                line = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                formatted += line + '<br>';
            }
        }
        
        // Close any open list
        if (inList) {
            formatted += listType === 'ul' ? '</ul>' : '</ol>';
        }
        
        content.innerHTML = formatted;
    } else {
        content.innerHTML = `<strong>You:</strong><br>${message.replace(/\n/g, '<br>')}`;
    }
    
    messageDiv.appendChild(content);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add loading indicator
function addChatLoading() {
    const chatMessages = document.getElementById('chat-messages');
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-loading';
    loadingDiv.id = 'chat-loading';
    loadingDiv.innerHTML = '<strong>AI is thinking</strong>';
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Remove loading indicator
function removeChatLoading() {
    const loading = document.getElementById('chat-loading');
    if (loading) {
        loading.remove();
    }
}

// Load channels
async function loadChannels() {
    const channelsList = document.getElementById('channels-list');
    channelsList.innerHTML = '<p class="loading">Loading channels...</p>';
    
    try {
        const response = await fetch('/api/channels');
        const data = await response.json();
        
        console.log('[Channel Management] API response:', data);
        console.log('[Channel Management] Channels count:', data.channels ? data.channels.length : 0);
        
        if (data.channels && data.channels.length > 0) {
            channelsList.innerHTML = '';
            
            for (const channel of data.channels) {
                console.log('[Channel Management] Creating card for:', channel.channel_name);
                try {
                const card = await createChannelCard(channel);
                channelsList.appendChild(card);
                } catch (cardError) {
                    console.error('[Channel Management] Error creating card for', channel.channel_name, ':', cardError);
            }
            }
            console.log('[Channel Management] Total cards created:', channelsList.children.length);
        } else {
            channelsList.innerHTML = '<p class="loading">No channels created yet. Use the Prompt Builder to create one!</p>';
        }
    } catch (error) {
        channelsList.innerHTML = '<p class="loading">Error loading channels</p>';
        console.error('Error loading channels:', error);
    }
}

// Create channel card
async function createChannelCard(channel) {
    const card = document.createElement('div');
    card.className = 'channel-card';
    card.id = `channel-${channel.channel_name}`;
    
    // Get token count (from channel data or calculate)
    const tokenCount = channel.token_count || 0;
    const tokenDisplay = tokenCount > 0 
        ? `<span style="background: #e3f2fd; color: #1976d2; padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 500;">📊 ${tokenCount.toLocaleString()} tokens</span>`
        : '<span style="color: #999; font-size: 0.85rem;">📊 No prompt</span>';
    
    // Fetch the full channel details including prompt
    try {
        const response = await fetch(`/api/channel/${channel.channel_name}`);
        const data = await response.json();
        
        // Use token count from API if available, otherwise use from channel data
        const finalTokenCount = data.token_count || tokenCount;
        const finalTokenDisplay = finalTokenCount > 0 
            ? `<span style="background: #e3f2fd; color: #1976d2; padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 500;">📊 ${finalTokenCount.toLocaleString()} tokens</span>`
            : '<span style="color: #999; font-size: 0.85rem;">📊 No prompt</span>';
        
        // Display title filter if available
        // Show multiple filters nicely formatted (supports both OR and AND)
        const titleFilterDisplay = data.title_filter 
            ? (() => {
                const filterText = data.title_filter;
                
                // Check if it contains (OR) separators
                const orGroups = filterText.split(/\s*\(OR\)\s*/i);
                
                if (orGroups.length > 1) {
                    // Multiple OR groups - format each group
                    const formattedGroups = orGroups.map(group => {
                        group = group.trim();
                        // Check if this group contains AND logic
                        if (/\s*\(AND\)\s*/i.test(group)) {
                            const andFilters = group.split(/\s*\(AND\)\s*/i);
                            return andFilters.map(f => f.trim()).filter(f => f).join(' <strong style="color: #1976d2;">AND</strong> ');
                        }
                        return group;
                    }).filter(g => g);
                    
                    const filterList = formattedGroups.join(' <strong style="color: #856404;">OR</strong> ');
                    return `<span style="background: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; margin-left: 8px;">🔍 Filters: ${filterList}</span>`;
                } else {
                    // Single filter - check if it contains AND
                    if (/\s*\(AND\)\s*/i.test(filterText)) {
                        const andFilters = filterText.split(/\s*\(AND\)\s*/i);
                        const filterList = andFilters.map(f => f.trim()).filter(f => f).join(' <strong style="color: #1976d2;">AND</strong> ');
                        return `<span style="background: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; margin-left: 8px;">🔍 Filters: ${filterList}</span>`;
                    } else {
                        // Single simple filter
                        return `<span style="background: #fff3cd; color: #856404; padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; margin-left: 8px;">🔍 Filter: "${filterText}"</span>`;
                    }
                }
            })()
            : '';
        
        // Display model provider badge and dropdown
        const modelProvider = data.model_provider || channel.model_provider || 'openai';
        const currentTitleFilter = data.title_filter || '';
        
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap; flex: 1;">
                    <div class="channel-name" style="display: flex; align-items: center; gap: 8px;">
                        <span>📡 ${channel.channel_name}</span>
                        <button onclick="renameChannel('${channel.channel_name}')" class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem; min-width: auto;">✏️ Rename</button>
                    </div>
                    ${finalTokenDisplay}
                    ${titleFilterDisplay}
                </div>
                <div style="display: flex; gap: 8px;">
                    <button onclick="duplicateChannel('${channel.channel_name}')" class="btn btn-secondary" style="padding: 6px 12px; font-size: 0.85rem;">📋 Duplicate</button>
                    <button onclick="deleteChannel('${channel.channel_name}')" class="btn btn-danger" style="padding: 6px 12px; font-size: 0.85rem;">🗑️ Delete</button>
                </div>
            </div>
            <div style="margin-bottom: 15px; padding: 12px; background: #f9fafb; border-radius: 6px; border: 1px solid #e5e7eb;">
                <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #374151; font-size: 0.9rem;">
                    🔍 Title Filter:
                </label>
                <div style="display: flex; gap: 8px; align-items: flex-start;">
                    <input type="text" id="title-filter-${channel.channel_name}" value="${currentTitleFilter.replace(/"/g, '&quot;')}" placeholder="e.g., XYZ-Trade-alerts or test1 (OR) test2 or keyword1 (AND) keyword2" style="flex: 1; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; background: white;">
                    <button onclick="updateChannelTitleFilter('${channel.channel_name}')" class="btn btn-primary" style="padding: 8px 16px; font-size: 0.9rem; white-space: nowrap;">💾 Save</button>
                </div>
                <div style="margin-top: 6px; font-size: 0.8rem; color: #6b7280;">
                    Matches signal titles. Use "(OR)" for any match, "(AND)" for all required. Leave empty to remove filter.
                </div>
            </div>
            <div style="margin-bottom: 15px; padding: 12px; background: #f9fafb; border-radius: 6px; border: 1px solid #e5e7eb;">
                <label style="display: block; margin-bottom: 8px; font-weight: 600; color: #374151; font-size: 0.9rem;">
                    🤖 AI Model Provider:
                </label>
                <select id="model-provider-${channel.channel_name}" onchange="updateChannelModelProvider('${channel.channel_name}', this.value)" style="width: 100%; padding: 8px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; background: white; cursor: pointer;">
                    <option value="openai" ${modelProvider === 'openai' ? 'selected' : ''}>OpenAI (${data.execution_model || 'gpt-4-turbo-preview'})</option>
                    <option value="grok" ${modelProvider === 'grok' ? 'selected' : ''}>Grok (${data.grok_model || 'grok-2-1212'})</option>
                </select>
                <div style="margin-top: 6px; font-size: 0.8rem; color: #6b7280;">
                    Switch between OpenAI and Grok for this channel. Changes apply immediately to new signals.
                </div>
            </div>
            <div class="channel-meta">
                <span>Created: ${new Date(channel.created_at).toLocaleDateString()}</span>
                <span>Updated: ${new Date(channel.updated_at).toLocaleDateString()}</span>
            </div>
            <div class="channel-prompt">${data.prompt}</div>
        `;
    } catch (error) {
        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                    <div class="channel-name">📡 ${channel.channel_name}</div>
                    ${tokenDisplay}
                </div>
                <button onclick="deleteChannel('${channel.channel_name}')" class="btn btn-danger" style="padding: 6px 12px; font-size: 0.85rem;">🗑️ Delete</button>
            </div>
            <div class="channel-meta">
                <span>Created: ${new Date(channel.created_at).toLocaleDateString()}</span>
                <span>Updated: ${new Date(channel.updated_at).toLocaleDateString()}</span>
            </div>
        `;
    }
    
    return card;
}

// Rename channel
async function renameChannel(channelName) {
    // Prompt for new channel name
    const newChannelName = prompt(
        `Enter a new name for the channel:\n\n` +
        `Current: ${channelName}\n\n` +
        `Note: This will also update all signals and training data associated with this channel.`
    );
    
    if (!newChannelName || !newChannelName.trim()) {
        return; // User cancelled or entered empty name
    }
    
    const trimmedName = newChannelName.trim();
    
    // Validate channel name
    if (trimmedName.length === 0) {
        alert('Channel name cannot be empty');
        return;
    }
    
    if (trimmedName === channelName) {
        alert('New channel name must be different from current name');
        return;
    }
    
    try {
        const response = await fetch(`/api/channel/${encodeURIComponent(channelName)}/rename`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                new_channel_name: trimmedName
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Channel renamed successfully!\n\nOld: ${channelName}\nNew: ${trimmedName}`);
            // Reload channels to show the updated name
            loadChannels();
        } else {
            alert(`❌ Failed to rename channel: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('[Channels] Error renaming channel:', error);
        alert(`❌ Error renaming channel: ${error.message}`);
    }
}

// Duplicate channel
async function duplicateChannel(channelName) {
    // Prompt for new channel name
    const newChannelName = prompt(
        `Enter a name for the duplicated channel:\n\n` +
        `Source: ${channelName}\n\n` +
        `The new channel will have the same prompt, filter, and model provider.`
    );
    
    if (!newChannelName || !newChannelName.trim()) {
        return; // User cancelled or entered empty name
    }
    
    const trimmedName = newChannelName.trim();
    
    // Validate channel name (basic validation)
    if (trimmedName.length === 0) {
        alert('Channel name cannot be empty');
        return;
    }
    
    try {
        const response = await fetch(`/api/channel/${encodeURIComponent(channelName)}/duplicate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                new_channel_name: trimmedName
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Channel duplicated successfully!\n\nNew channel: ${trimmedName}\n\nYou can now edit the name and filter as needed.`);
            // Reload channels to show the new one
            loadChannels();
        } else {
            alert(`❌ Failed to duplicate channel: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('[Channels] Error duplicating channel:', error);
        alert(`❌ Error duplicating channel: ${error.message}`);
    }
}

// Update channel title filter
async function updateChannelTitleFilter(channelName) {
    const inputEl = document.getElementById(`title-filter-${channelName}`);
    if (!inputEl) {
        alert('Title filter input not found');
        return;
    }
    
    const titleFilter = inputEl.value.trim() || null;
    
    // Find the save button - it's a sibling in the same flex container
    const saveBtn = inputEl.parentElement.querySelector('button');
    if (!saveBtn) {
        alert('Save button not found');
        return;
    }
    
    const originalText = saveBtn.textContent;
    
    // Show loading state
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    
    try {
        const response = await fetch(`/api/channel/${encodeURIComponent(channelName)}/title-filter`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title_filter: titleFilter
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show success feedback
            saveBtn.style.background = '#10b981';
            saveBtn.textContent = '✓ Saved';
            setTimeout(() => {
                saveBtn.style.background = '';
                saveBtn.textContent = originalText;
                saveBtn.disabled = false;
            }, 1500);
            
            // Reload channels to update the display
            loadChannels();
            
            console.log(`[Channels] Title filter updated for channel: ${channelName}`);
        } else {
            alert(`Failed to update title filter: ${data.error || 'Unknown error'}`);
            saveBtn.disabled = false;
            saveBtn.textContent = originalText;
        }
    } catch (error) {
        console.error('[Channels] Error updating title filter:', error);
        alert(`Error updating title filter: ${error.message}`);
        saveBtn.disabled = false;
        saveBtn.textContent = originalText;
    }
}

// Update channel model provider
async function updateChannelModelProvider(channelName, modelProvider) {
    try {
        const response = await fetch(`/api/channel/${encodeURIComponent(channelName)}/model-provider`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model_provider: modelProvider
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show success message briefly
            const selectEl = document.getElementById(`model-provider-${channelName}`);
            if (selectEl) {
                const originalBg = selectEl.style.background;
                selectEl.style.background = '#d1fae5';
                selectEl.style.borderColor = '#10b981';
                setTimeout(() => {
                    selectEl.style.background = originalBg;
                    selectEl.style.borderColor = '#d1d5db';
                }, 1500);
            }
            
            console.log(`[Channels] Model provider updated to ${modelProvider.toUpperCase()} for channel: ${channelName}`);
        } else {
            alert(`Failed to update model provider: ${data.error || 'Unknown error'}`);
            // Revert the dropdown
            loadChannels();
        }
    } catch (error) {
        console.error('[Channels] Error updating model provider:', error);
        alert(`Error updating model provider: ${error.message}`);
        // Revert the dropdown
        loadChannels();
    }
}

// Delete channel
async function deleteChannel(channelName) {
    // Confirm action
    const confirmed = confirm(
        `⚠️ Are you sure you want to delete the channel "${channelName}"?\n\n` +
        'This will permanently delete:\n' +
        '• The channel and its prompt\n' +
        '• All associated training data\n' +
        '• All signals received for this channel\n' +
        '• All trade executions for this channel\n\n' +
        'This action cannot be undone!'
    );
    
    if (!confirmed) {
        return;
    }
    
    const channelCard = document.getElementById(`channel-${channelName}`);
    if (!channelCard) {
        alert('Channel card not found');
        return;
    }
    
    // Show loading state
    const originalContent = channelCard.innerHTML;
    channelCard.innerHTML = '<p class="loading">Deleting channel...</p>';
    channelCard.style.opacity = '0.6';
    
    try {
        const response = await fetch(`/api/channel/${encodeURIComponent(channelName)}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show success message briefly
            channelCard.innerHTML = `
                <div class="result-box success" style="padding: 15px; text-align: center;">
                    <h3>✅ Channel Deleted</h3>
                    <p>${data.message}</p>
                    <p style="font-size: 0.9rem; margin-top: 10px;">
                        ${data.total_deleted} record(s) deleted
                    </p>
                </div>
            `;
            
            // Remove the card after a short delay
            setTimeout(() => {
                channelCard.style.transition = 'opacity 0.3s ease-out';
                channelCard.style.opacity = '0';
                setTimeout(() => {
                    channelCard.remove();
                    // Reload channels to refresh the list
                    loadChannels();
                    // Also refresh the dropdown in prompt builder if it exists
                    loadChannelsForSelectChat();
                }, 300);
            }, 2000);
        } else {
            // Show error message
            channelCard.innerHTML = `
                <div class="result-box error" style="padding: 15px;">
                    <h3>❌ Error Deleting Channel</h3>
                    <p>${data.error || 'Unknown error occurred'}</p>
                    <button onclick="loadChannels()" class="btn btn-secondary" style="margin-top: 10px;">🔄 Reload</button>
                </div>
            `;
            channelCard.style.opacity = '1';
        }
    } catch (error) {
        // Show error message
        channelCard.innerHTML = `
            <div class="result-box error" style="padding: 15px;">
                <h3>❌ Error Deleting Channel</h3>
                <p>${error.message}</p>
                <button onclick="loadChannels()" class="btn btn-secondary" style="margin-top: 10px;">🔄 Reload</button>
            </div>
        `;
        channelCard.style.opacity = '1';
        console.error('Error deleting channel:', error);
    }
}

// Load channels for select dropdown (chat version)
async function loadChannelsForSelectChat() {
    const select = document.getElementById('chat-channel-select');
    
    try {
        const response = await fetch('/api/channels');
        const data = await response.json();
        
        if (data.channels && data.channels.length > 0) {
            select.innerHTML = '<option value="">Select a channel...</option>';
            
            data.channels.forEach(channel => {
                const option = document.createElement('option');
                option.value = channel.channel_name;
                option.textContent = channel.channel_name;
                select.appendChild(option);
            });
        } else {
            select.innerHTML = '<option value="">No channels available</option>';
        }
    } catch (error) {
        select.innerHTML = '<option value="">Error loading channels</option>';
        console.error('Error loading channels:', error);
    }
}

// Load configuration
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        
        // Set form values
        document.getElementById('config-execution-model').value = data.execution_model;
        document.getElementById('config-builder-model').value = data.builder_model;
        document.getElementById('paper-trading-toggle').checked = data.paper_trading;
        
        // Update status displays
        document.getElementById('current-trading-mode').textContent =
            data.paper_trading ? '📝 Paper Trading' : '💰 Live Trading';
        
        // Settings tab status
        document.getElementById('settings-openai-status').textContent =
            data.openai_configured ? '✅ Configured' : '❌ Not Configured';
        document.getElementById('settings-api-key-preview').textContent = 
            data.openai_api_key || 'Not configured';
        
        // Also load other component configs
        if (typeof snaptradeLoadProxyUrl === 'function') {
            snaptradeLoadProxyUrl();
        }
        if (typeof loadXBotKeywords === 'function') {
            loadXBotKeywords();
        }
        if (typeof loadEtradeConfig === 'function') {
            loadEtradeConfig();
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Load X bot keywords configuration
async function loadXBotKeywords() {
    try {
        const response = await fetch('/api/x-bot-keywords');
        const data = await response.json();
        
        if (data.success) {
            const keywordsField = document.getElementById('x-bot-keywords');
            if (keywordsField) {
                keywordsField.value = data.keywords || '"flow-bot" OR "uwhale-news-bot" OR "x-news-bot"';
            }
        } else {
            showXBotKeywordsResult('Error loading keywords: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error loading X bot keywords:', error);
        showXBotKeywordsResult('Error loading keywords: ' + error.message, 'error');
    }
}

// Save X bot keywords configuration
async function saveXBotKeywords() {
    const keywordsField = document.getElementById('x-bot-keywords');
    if (!keywordsField) {
        showXBotKeywordsResult('Keywords field not found', 'error');
        return;
    }
    
    const keywords = keywordsField.value.trim();
    if (!keywords) {
        showXBotKeywordsResult('Please enter at least one keyword', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/x-bot-keywords', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keywords: keywords })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showXBotKeywordsResult('✅ Keywords saved successfully!', 'success');
        } else {
            showXBotKeywordsResult('❌ Failed to save keywords: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error saving X bot keywords:', error);
        showXBotKeywordsResult('Error saving keywords: ' + error.message, 'error');
    }
}

// Show result message for X bot keywords
function showXBotKeywordsResult(message, type) {
    const resultDiv = document.getElementById('x-bot-keywords-result');
    if (resultDiv) {
        resultDiv.style.display = 'block';
        resultDiv.className = `result-box ${type} show`;
        resultDiv.textContent = message;
        
        // Auto-hide after 5 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                resultDiv.style.display = 'none';
            }, 5000);
        }
    }
}

// Update configuration
async function updateConfig(event) {
    event.preventDefault();
    
    const apiKey = document.getElementById('config-api-key').value.trim();
    const executionModel = document.getElementById('config-execution-model').value.trim();
    const builderModel = document.getElementById('config-builder-model').value.trim();
    const resultBox = document.getElementById('config-result');
    
    if (!apiKey && !executionModel && !builderModel) {
        showResult(resultBox, 'error', '❌ Please provide at least one value to update');
        return;
    }
    
    showResult(resultBox, 'info', '⏳ Updating configuration...');
    
    try {
        const response = await fetch('/api/config/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                openai_api_key: apiKey || undefined,
                execution_model: executionModel || undefined,
                builder_model: builderModel || undefined
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showResult(resultBox, 'success', `
                ✅ Configuration updated successfully!<br>
                <strong>Execution Model:</strong> ${data.config.execution_model}<br>
                <strong>Builder Model:</strong> ${data.config.builder_model}<br>
                <strong>OpenAI:</strong> ${data.config.openai_configured ? 'Configured ✅' : 'Not Configured ❌'}
            `);
            
            // Clear API key field for security
            document.getElementById('config-api-key').value = '';
            
            // Reload config display
            loadConfig();
            checkHealth();
        } else {
            showResult(resultBox, 'error', `❌ Error: ${data.error || 'Unknown error'}`);
        }
    } catch (error) {
        showResult(resultBox, 'error', `❌ Error: ${error.message}`);
    }
}

// Test AI model
async function testModel(modelType, eventElement) {
    const apiKey = document.getElementById('config-api-key').value.trim();
    const modelInput = document.getElementById(`config-${modelType}-model`);
    const modelName = modelInput.value.trim();
    const resultDiv = document.getElementById(`${modelType}-test-result`);
    
    if (!modelName) {
        showTestResult(resultDiv, 'error', '❌ Please enter a model name first');
        return;
    }
    
    // Show loading
    showTestResult(resultDiv, 'info', '⏳ Testing model...');
    
    // Disable button during test
    const button = eventElement || document.querySelector(`button[onclick*="testModel('${modelType}')"]`);
    if (button) {
        button.disabled = true;
        button.textContent = '⏳ Testing...';
    }
    
    try {
        const response = await fetch('/api/config/test-model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                api_key: apiKey || undefined,
                model_name: modelName
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showTestResult(resultDiv, 'success', `
                ✅ <strong>Model Test Successful!</strong><br>
                <strong>Model:</strong> ${data.model}<br>
                <strong>Response Time:</strong> ${data.response_time}<br>
                <strong>Tokens Used:</strong> ${data.tokens_used}<br>
                <strong>Response:</strong> "${data.response}"
            `);
        } else {
            let errorMsg = `❌ <strong>Model Test Failed</strong><br>${data.error}`;
            if (data.suggestion) {
                errorMsg += `<br><br>💡 <strong>Suggestion:</strong> ${data.suggestion}`;
            }
            showTestResult(resultDiv, 'error', errorMsg);
        }
    } catch (error) {
        showTestResult(resultDiv, 'error', `❌ Error: ${error.message}`);
    } finally {
        // Re-enable button
        if (button) {
            button.disabled = false;
            button.textContent = '🧪 Test';
        }
    }
}

// Show test result
function showTestResult(element, type, message) {
    element.className = `test-result ${type} show`;
    element.innerHTML = message;
    element.style.display = 'block';
    
    // Auto-hide success after 10 seconds
    if (type === 'success') {
        setTimeout(() => {
            element.style.display = 'none';
        }, 10000);
    }
}

// Toggle paper trading
async function togglePaperTrading() {
    const checkbox = document.getElementById('paper-trading-toggle');
    
    try {
        const response = await fetch('/api/config/paper-trading', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                paper_trading: checkbox.checked
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert(`Trading mode switched to ${data.paper_trading ? 'PAPER' : 'LIVE'} mode`);
        }
    } catch (error) {
        console.error('Error toggling paper trading:', error);
        // Revert checkbox on error
        checkbox.checked = !checkbox.checked;
    }
}

// ==================== Webhook URL Functions ====================

async function loadWebhookUrl() {
    try {
        const response = await fetch('/api/webhook/config');
        const data = await response.json();
        
        if (data.webhook_url) {
            document.getElementById('webhook-url').value = data.webhook_url;
            updateWebhookDisplay(data.webhook_url);
        }
    } catch (error) {
        console.error('Error loading webhook URL:', error);
    }
}

async function saveWebhookUrl() {
    const webhookUrl = document.getElementById('webhook-url').value.trim();
    const resultElement = document.getElementById('webhook-result');
    
    if (!webhookUrl) {
        showResult(resultElement, 'error', '❌ Webhook URL is required');
        return;
    }
    
    // Validate URL format
    try {
        new URL(webhookUrl);
    } catch (e) {
        showResult(resultElement, 'error', '❌ Invalid URL format');
        return;
    }
    
    try {
        const response = await fetch('/api/webhook/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ webhook_url: webhookUrl })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult(resultElement, 'success', '✅ Webhook URL saved successfully');
            updateWebhookDisplay(webhookUrl);
        } else {
            showResult(resultElement, 'error', `❌ ${data.error || 'Failed to save webhook URL'}`);
        }
    } catch (error) {
        console.error('Error saving webhook URL:', error);
        showResult(resultElement, 'error', '❌ Network error. Please try again.');
    }
}

function updateWebhookDisplay(baseUrl) {
    const fullUrlElement = document.getElementById('full-webhook-url');
    if (baseUrl) {
        const fullUrl = baseUrl.replace(/\/$/, '') + '/api/signals/receive';
        fullUrlElement.textContent = fullUrl;
    } else {
        fullUrlElement.textContent = 'Not configured';
    }
}

function copyWebhookUrl() {
    const urlElement = document.getElementById('full-webhook-url');
    const url = urlElement.textContent;
    
    if (url === 'Not configured') {
        const resultElement = document.getElementById('webhook-result');
        showResult(resultElement, 'error', '❌ No webhook URL configured');
        return;
    }
    
    // Copy to clipboard
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(() => {
            const resultElement = document.getElementById('webhook-result');
            showResult(resultElement, 'success', '✅ URL copied to clipboard');
        }).catch(err => {
            console.error('Failed to copy:', err);
            fallbackCopyWebhookUrl(url);
        });
    } else {
        fallbackCopyWebhookUrl(url);
    }
}

function fallbackCopyWebhookUrl(text) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.top = "-9999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        const resultElement = document.getElementById('webhook-result');
        showResult(resultElement, 'success', '✅ URL copied to clipboard');
    } catch (err) {
        console.error('Fallback copy failed:', err);
    }
    
    document.body.removeChild(textArea);
}

// Load webhook URL config on page load
document.addEventListener('DOMContentLoaded', () => {
    loadWebhookUrl();
});

// Show result
function showResult(element, type, message) {
    element.className = `result-box ${type} show`;
    element.innerHTML = message;
    
    // Auto-hide after 10 seconds for success messages
    if (type === 'success') {
        setTimeout(() => {
            element.classList.remove('show');
        }, 10000);
    }
}

// Show builder prompt overlay
function showBuilderPrompt() {
    if (!conversationState.builderPromptUsed) {
        alert('No builder prompt available');
        return;
    }
    
    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'builder-prompt-overlay';
    overlay.className = 'overlay';
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            closeBuilderPrompt();
        }
    };
    
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'modal';
    
    modal.innerHTML = `
        <div class="modal-header">
            <h2>🔍 Builder Prompt Used</h2>
            <button onclick="closeBuilderPrompt()" class="close-btn">✕</button>
        </div>
        <div class="modal-body">
            <p class="help-text">This is the actual AI prompt used to analyze your signals and generate the channel prompt.</p>
            <div class="prompt-display">
                <pre>${escapeHtml(conversationState.builderPromptUsed)}</pre>
            </div>
        </div>
        <div class="modal-footer">
            <button onclick="copyBuilderPrompt()" class="btn btn-secondary">📋 Copy to Clipboard</button>
            <button onclick="closeBuilderPrompt()" class="btn btn-primary">Close</button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Fade in
    setTimeout(() => overlay.classList.add('show'), 10);
}

// Close builder prompt overlay
function closeBuilderPrompt() {
    const overlay = document.getElementById('builder-prompt-overlay');
    if (overlay) {
        overlay.classList.remove('show');
        setTimeout(() => overlay.remove(), 300);
    }
}

// Copy builder prompt to clipboard
function copyBuilderPrompt() {
    if (!conversationState.builderPromptUsed) {
        return;
    }
    
    navigator.clipboard.writeText(conversationState.builderPromptUsed).then(() => {
        alert('✅ Builder prompt copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('❌ Failed to copy to clipboard');
    });
}

// Escape HTML for display
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Show builder prompt info - displays raw prompt templates with placeholders
function showBuilderPromptInfo() {
    // Create overlay
    const overlay = document.createElement('div');
    overlay.id = 'builder-prompt-overlay';
    overlay.className = 'overlay';
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            closeBuilderPrompt();
        }
    };
    
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.maxWidth = '95%';
    modal.style.maxHeight = '95vh';
    
    // Raw prompt templates with placeholders - extracted from prompt_builder.py
    const startSystemPrompt = `You are an expert AI assistant specializing in analyzing trade signal patterns for automated trading systems. 
Your goal is to deeply understand the signal format to generate a highly robust execution prompt.

YOUR ANALYSIS PROCESS:
1. **Initial Pattern Recognition:**
   - Identify if signals are for STOCKS, OPTIONS, or BOTH
   - Recognize action indicators (BUY/SELL/LONG/SHORT/CALL/PUT)
   - Map out the signal structure and component ordering
   - Identify consistent vs variable elements

2. **Deep Component Analysis:**
   - **Symbol Format:** How are tickers presented? Any prefixes/suffixes?
   - **Action Type:** What words indicate buy/sell? Any synonyms used?
   - **Price Components:** How are entry, stop loss, and take profit indicated?
     * Look for abbreviations (SL, TP, Entry, Tgt, Stop, etc.)
     * Check for implicit vs explicit price labels
   - **Options Signals (if applicable):**
     * Strike price format and location
     * Option type indicators (C/CALL, P/PUT)
     * Expiration date format (MM/DD/YY, YYYY-MM-DD, Dec 20, etc.)
     * Premium/purchase price indicators
   - **Quantity/Position Size:** How is size indicated? (lots, shares, contracts, %)
   - **Time Elements:** Expiration dates, entry timing, duration holds
   - **Confidence/Risk Levels:** Any indicators of signal strength or risk rating?

3. **Edge Case & Ambiguity Detection:**
   - What happens if some fields are missing? (e.g., no stop loss mentioned)
   - Are there signals with partial information?
   - How to handle ranges vs single values? (e.g., "240-250")
   - What about multi-leg or spread strategies?
   - How to distinguish between similar abbreviations? (e.g., "C" = call or close?)
   - Any special notation for urgent vs casual signals?
   - How are updates or cancellations indicated?

4. **Contextual Rules:**
   - Do emojis or special characters carry meaning?
   - Is there implicit information based on context? (e.g., all signals default to day orders)
   - Are there channel-specific conventions or jargon?
   - Any prefix/suffix patterns that modify meaning?

5. **Question Strategy:**
   - Ask SPECIFIC questions about ambiguities found
   - Request examples for unclear patterns
   - Clarify abbreviation meanings
   - Confirm implicit assumptions
   - Ask about rare/edge case scenarios

WHEN TO ASK QUESTIONS:
- If multiple interpretations are possible for any component
- If abbreviations could have different meanings
- If date/time formats are ambiguous
- If there's inconsistency in the pattern
- If options-specific fields are unclear or missing
- If price format could be confused (decimal vs strike, etc.)

WHEN YOU'RE READY TO BUILD:
- All patterns are clear and unambiguous
- Edge cases and variations are understood
- You have explicit rules for handling missing/partial data
- You know how to distinguish between similar-looking elements

Be thorough and systematic. Ask intelligent, specific questions. The execution prompt you'll eventually create must be bulletproof.

Respond in a JSON format:
{
    "analysis": "Your deep analysis of the signal patterns and structure",
    "questions": ["Specific question 1?", "Specific question 2?"],  // Empty if no questions needed
    "ready_to_build": true/false,
    "observations": ["Key observation 1", "Key observation 2", "Identified edge case 1", etc.]
}`;

    const startUserPromptCreate = `I need to CREATE a new prompt for channel: {channel_name}

SIGNALS DUMP:
{signals_dump}

Please analyze these signals thoroughly and determine:
1. What are the patterns and formats used?
2. Do you need any clarifications about the format?
3. Are there ambiguities that need clarification?

Provide your analysis and ask any clarifying questions.`;

    const startUserPromptUpdate = `I need to UPDATE the existing prompt for channel: {channel_name}

EXISTING PROMPT:
{existing_prompt}

NEW SIGNALS DUMP:
{signals_dump}

Please analyze these new signals and determine:
1. Are there new patterns or formats not covered by the existing prompt?
2. Do I need clarification on any variations?
3. What needs to be updated in the prompt?

Provide your analysis and ask any clarifying questions.`;

    const continueSystemPrompt = `You are continuing to analyze trade signals to build a robust parsing prompt for automated trading.

The user has provided answers to your previous questions. Based on their clarifications:

1. **Acknowledge & Integrate:**
   - Thank the user for their clarification
   - Summarize what you now understand
   - Update your mental model of the signal pattern

2. **Deep Follow-up Analysis:**
   - If their answer revealed new edge cases, explore them
   - If still ambiguous, ask more specific follow-up questions
   - Probe for implicit rules or conventions you might have missed
   - Verify your understanding with specific examples if needed

3. **Readiness Assessment:**
   - You're ready to build when:
     * All ambiguities are resolved
     * Edge cases are understood
     * You have clear rules for every component extraction
     * Date/price/abbreviation handling is crystal clear
     * You know how to handle missing/partial data
   - You need more info if:
     * Multiple interpretations still possible
     * Critical edge cases undefined
     * Abbreviations or patterns could be confused

4. **Build Comprehensive Understanding:**
   - For each answer, consider: "Could this be misinterpreted?"
   - Think about: "What if this field is missing?"
   - Ask yourself: "Are there similar-looking patterns that need disambiguation?"

Remember: The execution prompt you'll create must be bulletproof. When in doubt, ask one more clarifying question.

Respond in JSON format:
{
    "acknowledgment": "Thank the user and summarize their clarification with your updated understanding",
    "questions": ["Specific follow-up question 1?", "Specific follow-up question 2?"],  // Empty if no more questions needed
    "ready_to_build": true/false,
    "updated_observations": ["New insight 1", "New edge case identified", "Clarified rule", etc.]
}`;

    const finalizeSystemPromptCreate = `Based on the conversation and analysis, create a COMPREHENSIVE and ROBUST prompt for parsing trade signals.

The prompt you create will be used by another AI model (the execution model) to parse incoming signals from this channel in real-time. The execution model needs crystal-clear, unambiguous instructions to correctly extract trading information.

YOUR TASK: Create a parsing prompt that is:

1. **HIGHLY SPECIFIC** - Leave no room for interpretation
   - Explicitly state how to identify each component
   - Define what each abbreviation means
   - Provide exact extraction rules

2. **PATTERN-AWARE** - Document the signal structure
   - Explain the typical signal format/template
   - Describe component ordering and positioning
   - Note any consistent prefixes/suffixes or markers

3. **COMPREHENSIVE** - Cover all fields completely
   - Symbol extraction with any special formatting
   - Action identification (BUY/SELL and variations)
   - All price components (entry, stop loss, take profit)
   - Options-specific fields (strike, type, expiration, premium)
   - Quantity/position sizing
   - Additional context or notes

4. **EDGE-CASE READY** - Handle variations and problems
   - What to do when fields are missing?
   - How to handle ambiguous abbreviations?
   - Rules for distinguishing similar patterns
   - Date format normalization strategies
   - Multi-value scenarios (ranges, multiple targets)

5. **ERROR-RESISTANT** - Build in validation
   - Sanity checks (e.g., stop loss should be below entry for buys)
   - Required vs optional fields
   - Default values when information is implicit
   - How to handle conflicting information

6. **EXAMPLE-DRIVEN** - Show correct parsing
   - Include 2-3 example signals with their correct JSON output
   - Demonstrate edge case handling
   - Show date normalization examples for options

The execution model must parse signals into this COMPLETE JSON format:
{
    "symbol": "TICKER",
    "action": "BUY" or "SELL",
    "entry_price": float or null,
    "stop_loss": float or null,
    "take_profit": float or null,
    "quantity": int or null,
    "strike": float or null,
    "option_type": "CALL" or "PUT" or null,
    "purchase_price": float or null,
    "expiration_date": "YYYY-MM-DD" or null,
    "notes": "additional context"
}

CRITICAL REQUIREMENTS:
- For OPTIONS signals: extraction model MUST normalize expiration_date to "YYYY-MM-DD" format
- For OPTIONS signals: Clearly distinguish between entry_price (for stocks) and purchase_price (option premium)
- For OPTIONS signals: Specify how to identify strike price vs other prices
- Be explicit about disambiguation rules (e.g., "C" = Call vs Close)
- Define handling of implicit information
- Provide clear rules for edge cases discussed in the conversation

STRUCTURE YOUR PROMPT:
1. Start with: "You are parsing trade signals from [channel]. These signals follow this format..."
2. Describe the overall structure and pattern
3. Detail each field extraction with specific rules
4. Address variations and edge cases
5. Provide 2-3 parsing examples
6. End with validation rules and error handling guidance

Output ONLY the execution prompt text (not JSON, not wrapped in quotes). Make it thorough, clear, and bulletproof.`;

    const finalizeSystemPromptUpdate = `Based on the conversation and analysis, UPDATE the existing prompt for parsing trade signals.

EXISTING PROMPT:
{existing_prompt}

Create an UPDATED prompt that:
1. Preserves understanding of old formats
2. Incorporates new patterns from the conversation
3. Addresses all clarifications discussed
4. Provides clear, unambiguous parsing instructions
5. Includes robust error handling for edge cases

The prompt should instruct an AI to parse signals into this COMPLETE JSON format:
{
    "symbol": "TICKER",
    "action": "BUY" or "SELL",
    "entry_price": float or null,
    "stop_loss": float or null,
    "take_profit": float or null,
    "quantity": int or null,
    "strike": float or null,
    "option_type": "CALL" or "PUT" or null,
    "purchase_price": float or null,
    "expiration_date": "YYYY-MM-DD" or null,
    "notes": "additional context"
}

REQUIREMENTS FOR THE UPDATED PROMPT:
- Be extremely specific about how each field is identified and extracted
- Provide explicit rules for abbreviations and variations
- Include disambiguation rules when patterns could be confused
- Specify how to handle missing or partial information
- Define clear fallback behaviors
- Include examples of correct parsing for complex cases
- Address all edge cases discovered in the conversation
- For options: emphasize date normalization to YYYY-MM-DD format
- For prices: clarify which number corresponds to which field when multiple prices exist

Output ONLY the updated prompt text (not JSON, not wrapped in quotes).`;

    const finalizeUserPrompt = `Channel: {channel_name}

Key Observations:
{observations_list}

Sample Signals:
{signals_dump_preview}...

Based on our conversation and analysis, generate the optimal parsing prompt now.`;

    // Build the content
    let content = `
        <div class="modal-header">
            <h2>ℹ️ What is a Builder Prompt?</h2>
            <button onclick="closeBuilderPrompt()" class="close-btn">✕</button>
        </div>
        <div class="modal-body" style="max-height: calc(95vh - 120px); overflow-y: auto;">
            <h3 style="color: var(--primary-color);">Understanding Builder Prompts</h3>
            <p>A <strong>Builder Prompt</strong> is the raw prompt template with placeholders that will be sent to the AI builder model. These templates show the structure and instructions before your actual data is filled in.</p>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin: 20px 0;">
                <strong>📋 Note:</strong> The placeholders like <code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">{channel_name}</code>, <code style="background: #f0f0f0; padding: 2px 6px; border-radius: 3px;">{signals_dump}</code> will be replaced with your actual data when the prompt is sent to the builder model.
            </div>
            
            <div style="margin-top: 30px;">
                <h3 style="color: var(--primary-color); margin-bottom: 20px;">📨 Raw Prompt Templates</h3>
                
                <!-- START CONVERSATION PROMPTS -->
                <div style="margin-bottom: 30px; border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; background: var(--bg-color);">
                    <h4 style="color: #34d399; font-size: 1.2rem; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                        <span>🚀</span> <span>Step 1: Start Conversation (Create New Channel)</span>
                        <button onclick="copyPromptTemplate('start-system-create')" class="btn btn-secondary" style="margin-left: auto; padding: 4px 12px; font-size: 0.8rem;">📋 Copy</button>
                    </h4>
                    <p class="help-text" style="margin-bottom: 10px;">System prompt sent when starting a new channel conversation:</p>
                    <div id="start-system-create" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; max-height: 400px; overflow-y: auto; border: 1px solid #444;">${escapeHtml(startSystemPrompt)}</div>
                    
                    <p class="help-text" style="margin-top: 15px; margin-bottom: 10px;">User prompt template (placeholders will be replaced):</p>
                    <div id="start-user-create" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; max-height: 300px; overflow-y: auto; border: 1px solid #444;">${escapeHtml(startUserPromptCreate)}</div>
                    <div style="margin-top: 10px; padding: 10px; background: #1a1a2e; border-radius: 6px; font-size: 0.85rem; color: #a78bfa;">
                        <strong>Placeholders:</strong> <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{channel_name}</code>, <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{signals_dump}</code>
                    </div>
                </div>
                
                <div style="margin-bottom: 30px; border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; background: var(--bg-color);">
                    <h4 style="color: #34d399; font-size: 1.2rem; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                        <span>🔄</span> <span>Step 1: Start Conversation (Update Existing Channel)</span>
                        <button onclick="copyPromptTemplate('start-user-update')" class="btn btn-secondary" style="margin-left: auto; padding: 4px 12px; font-size: 0.8rem;">📋 Copy</button>
                    </h4>
                    <p class="help-text" style="margin-bottom: 10px;">System prompt (same as create, but user prompt includes existing prompt):</p>
                    <div id="start-system-update" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; max-height: 400px; overflow-y: auto; border: 1px solid #444; opacity: 0.7;">${escapeHtml(startSystemPrompt)}</div>
                    <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 5px;">(Same as create mode - see above)</p>
                    
                    <p class="help-text" style="margin-top: 15px; margin-bottom: 10px;">User prompt template for updates:</p>
                    <div id="start-user-update" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; max-height: 300px; overflow-y: auto; border: 1px solid #444;">${escapeHtml(startUserPromptUpdate)}</div>
                    <div style="margin-top: 10px; padding: 10px; background: #1a1a2e; border-radius: 6px; font-size: 0.85rem; color: #a78bfa;">
                        <strong>Placeholders:</strong> <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{channel_name}</code>, <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{existing_prompt}</code>, <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{signals_dump}</code>
                    </div>
                </div>
                
                <!-- CONTINUE CONVERSATION PROMPTS -->
                <div style="margin-bottom: 30px; border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; background: var(--bg-color);">
                    <h4 style="color: #60a5fa; font-size: 1.2rem; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                        <span>💬</span> <span>Step 2: Continue Conversation</span>
                        <button onclick="copyPromptTemplate('continue-system')" class="btn btn-secondary" style="margin-left: auto; padding: 4px 12px; font-size: 0.8rem;">📋 Copy</button>
                    </h4>
                    <p class="help-text" style="margin-bottom: 10px;">System prompt sent when continuing the conversation (after user answers questions):</p>
                    <div id="continue-system" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; max-height: 400px; overflow-y: auto; border: 1px solid #444;">${escapeHtml(continueSystemPrompt)}</div>
                    <div style="margin-top: 10px; padding: 10px; background: #1a1a2e; border-radius: 6px; font-size: 0.85rem; color: #a78bfa;">
                        <strong>Note:</strong> The conversation history (previous messages) is automatically included in the messages array before this system prompt.
                    </div>
                </div>
                
                <!-- FINALIZE PROMPTS -->
                <div style="margin-bottom: 30px; border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; background: var(--bg-color);">
                    <h4 style="color: #f59e0b; font-size: 1.2rem; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                        <span>✨</span> <span>Step 3: Finalize & Generate Prompt (Create New)</span>
                        <button onclick="copyPromptTemplate('finalize-system-create')" class="btn btn-secondary" style="margin-left: auto; padding: 4px 12px; font-size: 0.8rem;">📋 Copy</button>
                    </h4>
                    <p class="help-text" style="margin-bottom: 10px;">System prompt for generating the final channel prompt (create mode):</p>
                    <div id="finalize-system-create" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; max-height: 500px; overflow-y: auto; border: 1px solid #444;">${escapeHtml(finalizeSystemPromptCreate)}</div>
                    
                    <p class="help-text" style="margin-top: 15px; margin-bottom: 10px;">User prompt template:</p>
                    <div id="finalize-user-create" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; max-height: 200px; overflow-y: auto; border: 1px solid #444;">${escapeHtml(finalizeUserPrompt)}</div>
                    <div style="margin-top: 10px; padding: 10px; background: #1a1a2e; border-radius: 6px; font-size: 0.85rem; color: #a78bfa;">
                        <strong>Placeholders:</strong> <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{channel_name}</code>, <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{observations_list}</code>, <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{signals_dump_preview}</code>
                        <br><strong>Note:</strong> Conversation history (first and last messages) are also included in the messages array before the user prompt.
                    </div>
                </div>
                
                <div style="margin-bottom: 30px; border: 1px solid var(--border-color); border-radius: 8px; padding: 20px; background: var(--bg-color);">
                    <h4 style="color: #f59e0b; font-size: 1.2rem; margin-bottom: 15px; display: flex; align-items: center; gap: 8px;">
                        <span>🔄</span> <span>Step 3: Finalize & Generate Prompt (Update Existing)</span>
                        <button onclick="copyPromptTemplate('finalize-system-update')" class="btn btn-secondary" style="margin-left: auto; padding: 4px 12px; font-size: 0.8rem;">📋 Copy</button>
                    </h4>
                    <p class="help-text" style="margin-bottom: 10px;">System prompt for updating an existing channel prompt:</p>
                    <div id="finalize-system-update" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 0.85rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; max-height: 500px; overflow-y: auto; border: 1px solid #444;">${escapeHtml(finalizeSystemPromptUpdate)}</div>
                    <div style="margin-top: 10px; padding: 10px; background: #1a1a2e; border-radius: 6px; font-size: 0.85rem; color: #a78bfa;">
                        <strong>Placeholders:</strong> <code style="background: #2d2d44; padding: 2px 6px; border-radius: 3px;">{existing_prompt}</code>
                        <br><strong>Note:</strong> User prompt is same as create mode, conversation history also included.
                    </div>
                </div>
            </div>
            
            <div style="background: var(--bg-color); padding: 15px; border-radius: 8px; margin-top: 20px; border: 1px solid var(--border-color);">
                <h4 style="color: var(--primary-color); margin-bottom: 10px;">📋 How It Works</h4>
                <ol style="line-height: 1.8; margin: 0;">
                    <li><strong>Start:</strong> System prompt + User prompt (with <code>{channel_name}</code> and <code>{signals_dump}</code> filled in)</li>
                    <li><strong>Continue:</strong> System prompt + Full conversation history + User's answer</li>
                    <li><strong>Finalize:</strong> System prompt + Conversation context (first/last messages) + User prompt (with <code>{channel_name}</code>, <code>{observations_list}</code>, <code>{signals_dump_preview}</code>)</li>
                </ol>
                <p style="margin-top: 15px; margin-bottom: 0;"><strong>💡 Pro Tip:</strong> These templates show the structure before your data is inserted. When actually sent, all placeholders are replaced with your actual channel name, signals, and conversation context.</p>
            </div>
        </div>
        <div class="modal-footer">
            <button onclick="copyAllTemplates()" class="btn btn-secondary">📋 Copy All Templates</button>
            <button onclick="closeBuilderPrompt()" class="btn btn-primary">Got It!</button>
        </div>
    `;
    
    modal.innerHTML = content;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Fade in
    setTimeout(() => overlay.classList.add('show'), 10);
}

// Copy prompt template to clipboard
function copyPromptTemplate(templateId) {
    const element = document.getElementById(templateId);
    if (!element) {
        alert('Template not found');
        return;
    }
    
    const text = element.textContent || element.innerText;
    navigator.clipboard.writeText(text).then(() => {
        alert('✅ Template copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('❌ Failed to copy to clipboard');
    });
}

// Copy all templates
function copyAllTemplates() {
    const templates = {
        'Start Conversation (Create) - System': document.getElementById('start-system-create')?.textContent || '',
        'Start Conversation (Create) - User': document.getElementById('start-user-create')?.textContent || '',
        'Start Conversation (Update) - User': document.getElementById('start-user-update')?.textContent || '',
        'Continue Conversation - System': document.getElementById('continue-system')?.textContent || '',
        'Finalize (Create) - System': document.getElementById('finalize-system-create')?.textContent || '',
        'Finalize (Create) - User': document.getElementById('finalize-user-create')?.textContent || '',
        'Finalize (Update) - System': document.getElementById('finalize-system-update')?.textContent || ''
    };
    
    let allText = '=== BUILDER PROMPT TEMPLATES ===\n\n';
    allText += 'These are the raw prompt templates with placeholders that will be sent to the builder model.\n';
    allText += 'Placeholders like {channel_name}, {signals_dump} will be replaced with actual data.\n\n';
    allText += '═'.repeat(60) + '\n\n';
    
    Object.entries(templates).forEach(([name, content]) => {
        if (content) {
            allText += `=== ${name} ===\n\n`;
            allText += content;
            allText += '\n\n' + '═'.repeat(60) + '\n\n';
        }
    });
    
    navigator.clipboard.writeText(allText).then(() => {
        alert('✅ All templates copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('❌ Failed to copy to clipboard');
    });
}

// Removed E*TRADE environment selection functions


