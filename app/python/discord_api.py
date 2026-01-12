"""
Discord API integration module for TradeIQ.
Handles sending messages to Discord channels via bot.
"""

import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DiscordAPI:
    def __init__(self, bot_token: str = None, channel_id: str = None, db: Optional[object] = None):
        """
        Initialize Discord API connection.
        
        Args:
            bot_token: Discord bot token
            channel_id: Discord channel ID
            db: Database instance (optional)
        """
        self.db = db
        
        # Load from database if available
        saved_channel_management_channel_id = None
        saved_commentary_channel_id = None
        if db:
            saved_token = db.get_setting("discord_bot_token", "")
            saved_channel_id = db.get_setting("discord_channel_id", "")
            saved_channel_management_channel_id = db.get_setting("discord_channel_management_channel_id", "") or None
            saved_commentary_channel_id = db.get_setting("discord_commentary_channel_id", "") or None
            
            if saved_token:
                bot_token = bot_token or saved_token
            if saved_channel_id:
                channel_id = channel_id or saved_channel_id
        
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.channel_management_channel_id = saved_channel_management_channel_id
        self.commentary_channel_id = saved_commentary_channel_id
        self.base_url = "https://discord.com/api/v10"
        self.is_configured = bool(self.bot_token and self.channel_id)
    
    def is_enabled(self) -> bool:
        """Check if Discord integration is enabled"""
        if not self.db:
            return False
        return self.db.get_setting("discord_enabled", "true").lower() == "true"
    
    def save_config(self, bot_token: str, channel_id: str, channel_management_channel_id: str = None, commentary_channel_id: str = None) -> bool:
        """
        Save Discord configuration to database.
        
        Args:
            bot_token: Discord bot token
            channel_id: Discord channel ID
            channel_management_channel_id: Discord channel ID for channel management signals (optional)
            commentary_channel_id: Discord channel ID for commentary signals (optional)
            
        Returns:
            bool: True if saved successfully
        """
        try:
            if self.db:
                self.db.save_setting("discord_bot_token", bot_token)
                self.db.save_setting("discord_channel_id", channel_id)
                if channel_management_channel_id:
                    self.db.save_setting("discord_channel_management_channel_id", channel_management_channel_id)
                else:
                    # Clear if empty
                    self.db.save_setting("discord_channel_management_channel_id", "")
                if commentary_channel_id:
                    self.db.save_setting("discord_commentary_channel_id", commentary_channel_id)
                else:
                    # Clear if empty
                    self.db.save_setting("discord_commentary_channel_id", "")
            
            self.bot_token = bot_token
            self.channel_id = channel_id
            self.channel_management_channel_id = channel_management_channel_id or ""
            self.commentary_channel_id = commentary_channel_id or ""
            self.is_configured = bool(self.bot_token and self.channel_id)
            return True
        except Exception as e:
            logger.error(f"Error saving Discord config: {e}")
            return False
    
    def get_config(self) -> Dict:
        """
        Get Discord configuration from database.
        
        Returns:
            Dict with bot_token, channel_id, channel_management_channel_id, and commentary_channel_id
        """
        try:
            if self.db:
                bot_token = self.db.get_setting("discord_bot_token", "") or ""
                channel_id = self.db.get_setting("discord_channel_id", "") or ""
                channel_management_channel_id = self.db.get_setting("discord_channel_management_channel_id", "") or ""
                commentary_channel_id = self.db.get_setting("discord_commentary_channel_id", "") or ""
                return {
                    "bot_token": bot_token,
                    "channel_id": channel_id,
                    "channel_management_channel_id": channel_management_channel_id,
                    "commentary_channel_id": commentary_channel_id,
                }
            return {
                "bot_token": self.bot_token or "",
                "channel_id": self.channel_id or "",
                "channel_management_channel_id": getattr(self, 'channel_management_channel_id', '') or "",
                "commentary_channel_id": getattr(self, 'commentary_channel_id', '') or "",
            }
        except Exception as e:
            logger.error(f"Error getting Discord config: {e}")
            # Return default config on error
            return {
                "bot_token": "",
                "channel_id": "",
                "channel_management_channel_id": "",
                "commentary_channel_id": "",
            }
    
    def send_message(self, message: str, channel_id: str = None) -> Dict:
        """
        Send a message to a Discord channel.
        
        Args:
            message: Message content to send
            channel_id: Channel ID (optional, uses saved channel_id if not provided)
            
        Returns:
            Dict with success status and response data or error
        """
        if not self.bot_token:
            return {"success": False, "error": "Bot token not configured"}
        
        target_channel_id = channel_id or self.channel_id
        if not target_channel_id:
            return {"success": False, "error": "Channel ID not configured"}
        
        try:
            url = f"{self.base_url}/channels/{target_channel_id}/messages"
            headers = {
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json"
            }
            data = {
                "content": message
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Discord message sent successfully to channel {target_channel_id}")
                return {
                    "success": True,
                    "message_id": result.get("id"),
                    "channel_id": target_channel_id,
                    "content": message
                }
            elif response.status_code == 401:
                return {"success": False, "error": "Invalid bot token"}
            elif response.status_code == 403:
                return {"success": False, "error": "Bot lacks permission to send messages in this channel"}
            elif response.status_code == 404:
                return {"success": False, "error": "Channel not found or bot is not in the server"}
            elif response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "unknown")
                return {"success": False, "error": f"Rate limited. Retry after {retry_after} seconds"}
            else:
                error_text = response.text[:200] if response.text else "Unknown error"
                return {
                    "success": False,
                    "error": f"Failed to send message: {error_text}",
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout - Discord API did not respond"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Discord message: {e}")
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error sending Discord message: {e}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
    
    def test_connection(self) -> Dict:
        """
        Test the Discord connection by sending a test message.
        
        Returns:
            Dict with success status and test result
        """
        if not self.is_configured:
            return {"success": False, "error": "Discord not configured. Please set bot token and channel ID."}
        
        test_message = "🧪 Test message from TradeIQ - Discord integration is working!"
        return self.send_message(test_message)

