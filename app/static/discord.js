// Discord Integration UI Logic

function discordShowMessage(message, type = 'info') {
    const messageDiv = document.getElementById('discord-message');
    if (!messageDiv) return;
    
    messageDiv.style.display = 'block';
    messageDiv.className = `result-box ${type} show`;
    messageDiv.textContent = message;
    
    // Auto-hide after 5 seconds for success messages
    if (type === 'success') {
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 5000);
    }
}

// Load configuration
async function discordLoadConfig() {
    try {
        const response = await fetch('/api/discord/config');
        
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorMessage;
            } catch (e) {
                const errorText = await response.text();
                errorMessage = errorText || errorMessage;
            }
            throw new Error(errorMessage);
        }
        
        const data = await response.json();
        console.log('[Discord] Config loaded:', data);
        
        if (!data.success) {
            throw new Error(data.error || 'Failed to load configuration');
        }
        
        if (data.config) {
            const botTokenEl = document.getElementById('discord-bot-token');
            const channelIdEl = document.getElementById('discord-channel-id');
            const channelManagementChannelIdEl = document.getElementById('discord-channel-management-channel-id');
            const commentaryChannelIdEl = document.getElementById('discord-commentary-channel-id');
            
            if (!botTokenEl || !channelIdEl) {
                console.warn('[Discord] Configuration form elements not found. Tab may not be loaded yet.');
                // Don't throw error, just log warning - elements might not be in DOM yet
                return;
            }
            
            botTokenEl.value = data.config.bot_token || '';
            channelIdEl.value = data.config.channel_id || '';
            if (channelManagementChannelIdEl) {
                channelManagementChannelIdEl.value = data.config.channel_management_channel_id || '';
            }
            if (commentaryChannelIdEl) {
                commentaryChannelIdEl.value = data.config.commentary_channel_id || '';
            }
        } else {
            console.warn('[Discord] No config data in response');
        }
        
        // Load enabled state
        try {
            const enabledResponse = await fetch('/api/discord/enabled');
            if (enabledResponse.ok) {
                const enabledData = await enabledResponse.json();
                if (enabledData.success) {
                    const enabled = enabledData.enabled !== false; // Default to true if not set
                    const enabledCheckbox = document.getElementById('discord-enabled');
                    if (enabledCheckbox) {
                        enabledCheckbox.checked = enabled;
                        updateDiscordStatus(enabled);
                    }
                }
            }
        } catch (enabledError) {
            console.warn('[Discord] Error loading enabled state:', enabledError);
            // Don't show error for enabled state, just log it
        }
    } catch (error) {
        console.error('[Discord] Error loading config:', error);
        const errorMsg = error.message || 'Unknown error';
        discordShowMessage('Error loading configuration: ' + errorMsg, 'error');
    }
}

// Toggle enabled state
async function discordToggleEnabled() {
    const enabled = document.getElementById('discord-enabled').checked;
    
    try {
        const response = await fetch('/api/discord/enabled', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateDiscordStatus(enabled);
            discordShowMessage(
                enabled ? '✅ Discord integration enabled' : '⚠️ Discord integration disabled',
                enabled ? 'success' : 'warning'
            );
        } else {
            // Revert checkbox on error
            document.getElementById('discord-enabled').checked = !enabled;
            discordShowMessage('Failed to update enabled state: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        // Revert checkbox on error
        document.getElementById('discord-enabled').checked = !enabled;
        discordShowMessage('Error updating enabled state: ' + error.message, 'error');
    }
}

// Update status display
function updateDiscordStatus(enabled) {
    const statusEl = document.getElementById('discord-status');
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
async function discordSaveConfig() {
    const botToken = document.getElementById('discord-bot-token').value.trim();
    const channelId = document.getElementById('discord-channel-id').value.trim();
    const channelManagementChannelIdEl = document.getElementById('discord-channel-management-channel-id');
    const channelManagementChannelId = channelManagementChannelIdEl ? channelManagementChannelIdEl.value.trim() : '';
    const commentaryChannelIdEl = document.getElementById('discord-commentary-channel-id');
    const commentaryChannelId = commentaryChannelIdEl ? commentaryChannelIdEl.value.trim() : '';
    
    if (!botToken || !channelId) {
        discordShowMessage('Please enter both Bot Token and Channel ID', 'error');
        return;
    }
    
    try {
        const requestBody = {
            bot_token: botToken,
            channel_id: channelId
        };
        
        // Add channel management channel ID if provided
        if (channelManagementChannelId) {
            requestBody.channel_management_channel_id = channelManagementChannelId;
        }
        
        // Add commentary channel ID if provided
        if (commentaryChannelId) {
            requestBody.commentary_channel_id = commentaryChannelId;
        }
        
        const response = await fetch('/api/discord/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (data.success) {
            discordShowMessage('✅ Configuration saved successfully!', 'success');
        } else {
            discordShowMessage('❌ Failed to save configuration: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error saving Discord config:', error);
        discordShowMessage('Error saving configuration: ' + error.message, 'error');
    }
}

// Send test message
async function discordSendTestMessage() {
    const testMessage = document.getElementById('discord-test-message').value.trim() || '🧪 Test message from TradeIQ!';
    const testChannelIdEl = document.getElementById('discord-test-channel-id');
    const testChannelId = testChannelIdEl ? testChannelIdEl.value.trim() : '';
    const resultDiv = document.getElementById('discord-test-result');
    
    resultDiv.innerHTML = '<div class="test-result info show">📤 Sending test message...</div>';
    
    try {
        const requestBody = {
            message: testMessage
        };
        
        // Add channel_id if provided
        if (testChannelId) {
            requestBody.channel_id = testChannelId;
        }
        
        const response = await fetch('/api/discord/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (data.success) {
            resultDiv.innerHTML = `
                <div class="test-result success show">
                    <h3 style="margin-top: 0; color: #059669;">✅ Test Message Sent Successfully!</h3>
                    <div style="background: #d1fae5; padding: 12px; border-radius: 6px; margin-top: 10px;">
                        <p style="margin: 0;"><strong>Message ID:</strong> ${data.message_id || 'N/A'}</p>
                        <p style="margin: 5px 0 0 0;"><strong>Channel ID:</strong> ${data.channel_id || 'N/A'}</p>
                        <p style="margin: 5px 0 0 0;"><strong>Message:</strong> ${escapeHtml(testMessage)}</p>
                    </div>
                    <p style="margin-top: 12px; color: #059669;">Check your Discord channel to see the message!</p>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `
                <div class="test-result error show">
                    <h3 style="margin-top: 0; color: #dc2626;">❌ Failed to Send Test Message</h3>
                    <div style="background: #fee2e2; padding: 12px; border-radius: 6px; margin-top: 10px;">
                        <p style="margin: 0; color: #991b1b;"><strong>Error:</strong> ${escapeHtml(data.error || 'Unknown error')}</p>
                        ${data.status_code ? `<p style="margin: 5px 0 0 0; color: #991b1b;"><strong>Status Code:</strong> ${data.status_code}</p>` : ''}
                    </div>
                    <p style="margin-top: 12px; color: #dc2626;">
                        <strong>Common Issues:</strong><br>
                        • Bot token is incorrect<br>
                        • Channel ID is incorrect<br>
                        • Bot is not in the server<br>
                        • Bot lacks "Send Messages" permission
                    </p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error sending test message:', error);
        resultDiv.innerHTML = `
            <div class="test-result error show">
                <h3 style="margin-top: 0; color: #dc2626;">❌ Error</h3>
                <p>${escapeHtml(error.message)}</p>
            </div>
        `;
    }
}

// Helper function for HTML escaping
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

