"""
X (Twitter) API integration module for TradeIQ.
Handles posting tweets to X (Twitter) account.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Try to import tweepy, but handle if not installed
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    logger.warning("Tweepy not installed. X (Twitter) integration will not work. Install with: pip install tweepy")


class XAPI:
    def __init__(self, api_key: str = None, api_secret: str = None, 
                 access_token: str = None, access_token_secret: str = None,
                 bearer_token: str = None, db: Optional[object] = None):
        """
        Initialize X (Twitter) API connection.
        
        Args:
            api_key: X API Key
            api_secret: X API Secret Key
            access_token: X Access Token
            access_token_secret: X Access Token Secret
            bearer_token: X Bearer Token (optional, for read-only operations)
            db: Database instance (optional)
        """
        if not TWEEPY_AVAILABLE:
            self.is_available = False
            self.api = None
            self.client = None
            return
        
        self.db = db
        
        # Load from database if available
        if db:
            saved_api_key = db.get_setting("x_api_key", "")
            saved_api_secret = db.get_setting("x_api_secret", "")
            saved_access_token = db.get_setting("x_access_token", "")
            saved_access_token_secret = db.get_setting("x_access_token_secret", "")
            saved_bearer_token = db.get_setting("x_bearer_token", "")
            
            if saved_api_key:
                api_key = api_key or saved_api_key
            if saved_api_secret:
                api_secret = api_secret or saved_api_secret
            if saved_access_token:
                access_token = access_token or saved_access_token
            if saved_access_token_secret:
                access_token_secret = access_token_secret or saved_access_token_secret
            if saved_bearer_token:
                bearer_token = bearer_token or saved_bearer_token
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.bearer_token = bearer_token
        
        # Check if we have minimum required credentials for posting
        self.is_configured = bool(
            self.api_key and 
            self.api_secret and 
            self.access_token and 
            self.access_token_secret
        )
        
        self.is_available = TWEEPY_AVAILABLE
        self.api = None
        self.client = None
        
        # Initialize API if configured
        if self.is_configured and self.is_available:
            try:
                # OAuth 1.0a authentication for posting tweets
                auth = tweepy.OAuth1UserHandler(
                    self.api_key,
                    self.api_secret,
                    self.access_token,
                    self.access_token_secret
                )
                self.api = tweepy.API(auth, wait_on_rate_limit=True)
                
                # Also initialize v2 client if bearer token is available
                if self.bearer_token:
                    self.client = tweepy.Client(
                        bearer_token=self.bearer_token,
                        consumer_key=self.api_key,
                        consumer_secret=self.api_secret,
                        access_token=self.access_token,
                        access_token_secret=self.access_token_secret,
                        wait_on_rate_limit=True
                    )
                else:
                    # Use v1.1 API if no bearer token
                    self.client = None
                    
            except Exception as e:
                logger.error(f"Error initializing X API: {e}")
                self.api = None
                self.client = None
    
    def is_enabled(self) -> bool:
        """Check if X integration is enabled"""
        if not self.db:
            return False
        return self.db.get_setting("x_enabled", "true").lower() == "true"
    
    def save_config(self, api_key: str, api_secret: str, access_token: str, 
                   access_token_secret: str, bearer_token: str = None) -> bool:
        """
        Save X (Twitter) configuration to database.
        
        Args:
            api_key: X API Key
            api_secret: X API Secret Key
            access_token: X Access Token
            access_token_secret: X Access Token Secret
            bearer_token: X Bearer Token (optional)
            
        Returns:
            bool: True if saved successfully
        """
        try:
            # Ensure all required values are strings (not None)
            api_key = api_key or ""
            api_secret = api_secret or ""
            access_token = access_token or ""
            access_token_secret = access_token_secret or ""
            
            if self.db:
                self.db.save_setting("x_api_key", api_key)
                self.db.save_setting("x_api_secret", api_secret)
                self.db.save_setting("x_access_token", access_token)
                self.db.save_setting("x_access_token_secret", access_token_secret)
                if bearer_token:
                    self.db.save_setting("x_bearer_token", bearer_token)
                else:
                    # Clear bearer token if not provided
                    self.db.save_setting("x_bearer_token", "")
            
            # Update instance variables
            self.api_key = api_key
            self.api_secret = api_secret
            self.access_token = access_token
            self.access_token_secret = access_token_secret
            if bearer_token:
                self.bearer_token = bearer_token
            
            # Reinitialize API with new credentials
            self.is_configured = bool(
                self.api_key and 
                self.api_secret and 
                self.access_token and 
                self.access_token_secret
            )
            
            if self.is_configured and self.is_available:
                try:
                    # Prioritize API v2 client (required for most access levels)
                    # Try to create v2 client first (works with or without bearer token)
                    try:
                        if self.bearer_token:
                            self.client = tweepy.Client(
                                bearer_token=self.bearer_token,
                                consumer_key=self.api_key,
                                consumer_secret=self.api_secret,
                                access_token=self.access_token,
                                access_token_secret=self.access_token_secret,
                                wait_on_rate_limit=True
                            )
                        else:
                            # Create v2 client using OAuth 1.0a (no bearer token needed)
                            self.client = tweepy.Client(
                                consumer_key=self.api_key,
                                consumer_secret=self.api_secret,
                                access_token=self.access_token,
                                access_token_secret=self.access_token_secret,
                                wait_on_rate_limit=True
                            )
                        logger.info("X API v2 client initialized successfully")
                    except Exception as e:
                        logger.warning(f"Could not initialize v2 client: {e}")
                        self.client = None
                    
                    # Also initialize v1.1 API as fallback (though it may not work with limited access)
                    try:
                        auth = tweepy.OAuth1UserHandler(
                            self.api_key,
                            self.api_secret,
                            self.access_token,
                            self.access_token_secret
                        )
                        self.api = tweepy.API(auth, wait_on_rate_limit=True)
                        
                        # Test authentication by verifying credentials
                        try:
                            self.api.verify_credentials()
                            logger.info("X API v1.1 credentials verified successfully")
                        except tweepy.Unauthorized:
                            logger.warning("X API v1.1 credentials verification failed - Unauthorized")
                        except Exception as e:
                            logger.warning(f"X API v1.1 credentials verification issue: {e}")
                    except Exception as e:
                        logger.warning(f"Could not initialize v1.1 API: {e}")
                        self.api = None
                except Exception as e:
                    logger.error(f"Error reinitializing X API: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error saving X config: {e}")
            return False
    
    def get_config(self) -> Dict:
        """
        Get X (Twitter) configuration from database.
        
        Returns:
            Dict with API credentials (secrets masked)
        """
        if self.db:
            return {
                "api_key": self.db.get_setting("x_api_key", ""),
                "api_secret": self.db.get_setting("x_api_secret", ""),
                "access_token": self.db.get_setting("x_access_token", ""),
                "access_token_secret": self.db.get_setting("x_access_token_secret", ""),
                "bearer_token": self.db.get_setting("x_bearer_token", ""),
            }
        return {
            "api_key": self.api_key or "",
            "api_secret": self.api_secret or "",
            "access_token": self.access_token or "",
            "access_token_secret": self.access_token_secret or "",
            "bearer_token": self.bearer_token or "",
        }
    
    def post_tweet(self, text: str) -> Dict:
        """
        Post a tweet to X (Twitter).
        
        Args:
            text: Tweet text (max 280 characters for standard tweets)
            
        Returns:
            Dict with success status and tweet data or error
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Tweepy library not installed. Install with: pip install tweepy"
            }
        
        if not self.is_configured:
            return {
                "success": False,
                "error": "X API not configured. Please set API Key, API Secret, Access Token, and Access Token Secret."
            }
        
        if not self.is_enabled():
            return {
                "success": False,
                "error": "X integration is disabled"
            }
        
        if not text or not text.strip():
            return {
                "success": False,
                "error": "Tweet text cannot be empty"
            }
        
        # Check tweet length (280 characters for standard tweets)
        if len(text) > 280:
            return {
                "success": False,
                "error": f"Tweet text is too long ({len(text)} characters). Maximum is 280 characters."
            }
        
        # Reinitialize API if not already initialized (in case config was just saved)
        if not self.api and not self.client and self.is_configured and self.is_available:
            try:
                auth = tweepy.OAuth1UserHandler(
                    self.api_key,
                    self.api_secret,
                    self.access_token,
                    self.access_token_secret
                )
                self.api = tweepy.API(auth, wait_on_rate_limit=True)
                
                if self.bearer_token:
                    self.client = tweepy.Client(
                        bearer_token=self.bearer_token,
                        consumer_key=self.api_key,
                        consumer_secret=self.api_secret,
                        access_token=self.access_token,
                        access_token_secret=self.access_token_secret,
                        wait_on_rate_limit=True
                    )
            except Exception as e:
                logger.error(f"Error reinitializing X API: {e}")
                return {
                    "success": False,
                    "error": f"Failed to initialize X API: {str(e)}"
                }
        
        try:
            # Always try API v2 first (required for most access levels)
            # If bearer token is not provided, try to use v2 client with OAuth 1.0a
            if not self.client and self.is_configured:
                # Try to create v2 client without bearer token (using OAuth 1.0a)
                try:
                    self.client = tweepy.Client(
                        consumer_key=self.api_key,
                        consumer_secret=self.api_secret,
                        access_token=self.access_token,
                        access_token_secret=self.access_token_secret,
                        wait_on_rate_limit=True
                    )
                except Exception as e:
                    logger.warning(f"Could not create v2 client without bearer token: {e}")
            
            if self.client:
                # Use Twitter API v2 (required for most access levels)
                try:
                    response = self.client.create_tweet(text=text)
                    tweet_id = response.data['id']
                    tweet_text = response.data['text']
                    
                    logger.info(f"Tweet posted successfully via API v2. Tweet ID: {tweet_id}")
                    return {
                        "success": True,
                        "tweet_id": str(tweet_id),
                        "text": tweet_text,
                        "api_version": "v2"
                    }
                except tweepy.Forbidden as e:
                    error_msg = str(e)
                    if "453" in error_msg or "subset of X API V2" in error_msg:
                        logger.error(f"API v2 Forbidden - Access level issue: {e}")
                        return {
                            "success": False,
                            "error": "Your X API access level doesn't include tweet posting. Error 453: You have limited API access. To post tweets, you need to upgrade your API access level. Visit https://developer.x.com/en/portal/product to upgrade. Free tier may not support posting - consider Basic tier ($100/month) or check your current access level settings."
                        }
                    else:
                        raise
                except tweepy.Unauthorized as e:
                    logger.error(f"API v2 Unauthorized error: {e}")
                    # Don't fall back to v1.1 for unauthorized - credentials are wrong
                    raise
            elif self.api:
                # Use Twitter API v1.1
                status = self.api.update_status(status=text)
                tweet_id = status.id
                tweet_text = status.text
                
                logger.info(f"Tweet posted successfully via API v1.1. Tweet ID: {tweet_id}")
                return {
                    "success": True,
                    "tweet_id": str(tweet_id),
                    "text": tweet_text,
                    "api_version": "v1.1"
                }
            else:
                return {
                    "success": False,
                    "error": "X API not properly initialized. Please check your credentials and try saving the configuration again."
                }
                
        except tweepy.TooManyRequests:
            return {
                "success": False,
                "error": "Rate limit exceeded. Please wait before posting again."
            }
        except tweepy.Unauthorized as e:
            error_msg = str(e)
            logger.error(f"X API Unauthorized error: {error_msg}")
            return {
                "success": False,
                "error": f"Unauthorized. Please check your API credentials. Details: {error_msg}. Make sure your app has 'Read and Write' permissions and that your Access Token and Access Token Secret are correct."
            }
        except tweepy.Forbidden as e:
            error_msg = str(e)
            logger.error(f"X API Forbidden error: {error_msg}")
            
            # Check for specific error 453 (access level issue)
            if "453" in error_msg or "subset of X API V2" in error_msg:
                return {
                    "success": False,
                    "error": "Your X API access level doesn't include tweet posting. Error 453: You have limited API access. To post tweets, you need to upgrade your API access level. Visit https://developer.x.com/en/portal/product to upgrade. Free tier may not support posting - consider Basic tier ($100/month) or check your current access level settings."
                }
            else:
                return {
                    "success": False,
                    "error": f"Forbidden. Your app may not have permission to post tweets, or the tweet content violates Twitter's rules. Details: {error_msg}"
                }
        except tweepy.BadRequest as e:
            error_msg = str(e)
            logger.error(f"X API BadRequest error: {error_msg}")
            return {
                "success": False,
                "error": f"Bad request: {error_msg}"
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error posting tweet: {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": f"Unexpected error: {error_msg}"
            }
    
    def test_connection(self) -> Dict:
        """
        Test the X (Twitter) connection by posting a test tweet.
        
        Returns:
            Dict with success status and test result
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "X API not configured. Please set API Key, API Secret, Access Token, and Access Token Secret."
            }
        
        test_tweet = "🧪 Test tweet from TradeIQ - X integration is working!"
        return self.post_tweet(test_tweet)

