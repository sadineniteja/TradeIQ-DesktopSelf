"""
Database module for managing channels, prompts, and trade history.
This module handles all database operations including creating tables,
storing channel prompts, and logging trade executions.
"""

import sqlite3
import json
import re
from datetime import datetime
from typing import List, Dict, Optional


class Database:
    def __init__(self, db_path: str = "tradeiq.db"):
        """Initialize database connection and create tables if they don't exist."""
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """Create database tables if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Channels table - stores channel-specific prompts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT UNIQUE NOT NULL,
                channel_prompt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                model_provider TEXT DEFAULT 'openai'
            )
        """)
        
        # Training data table - stores historical signals for prompt building
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT NOT NULL,
                signal_text TEXT NOT NULL,
                signal_date TEXT,
                weight REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (channel_name) REFERENCES channels(channel_name)
            )
        """)
        
        # Trade signals table - logs all received signals
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_name TEXT NOT NULL,
                raw_content TEXT NOT NULL,
                parsed_signal TEXT,
                status TEXT NOT NULL,
                received_at TEXT NOT NULL,
                processed_at TEXT
            )
        """)
        
        # Trade executions table - logs all executed trades
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity REAL,
                price REAL,
                stop_loss REAL,
                take_profit REAL,
                strike REAL,
                option_type TEXT,
                purchase_price REAL,
                expiration_date TEXT,
                webull_order_id TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                executed_at TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES trade_signals(id)
            )
        """)
        
        # Settings table - stores application settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Push subscriptions table - stores PWA push notification subscriptions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT UNIQUE NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                subscription_data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create trade_execution_attempts table for Smart Executor
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_execution_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                platform TEXT,
                step_reached INTEGER,
                status TEXT,
                ticker TEXT,
                direction TEXT,
                option_type TEXT,
                strike_price REAL,
                purchase_price REAL,
                input_position_size INTEGER,
                input_date_year TEXT,
                input_date_month TEXT,
                input_date_day TEXT,
                final_expiration_date TEXT,
                final_position_size INTEGER,
                order_id TEXT,
                filled_price REAL,
                fill_attempts INTEGER,
                error_message TEXT,
                execution_log TEXT,
                created_at TEXT,
                completed_at TEXT
            )
        """)
        
        # Create tradingview_execution_history table for TradingView Executor
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tradingview_execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                platform TEXT,
                symbol TEXT,
                action TEXT,
                signal_price REAL,
                position_size REAL,
                bid_delta REAL,
                ask_delta REAL,
                increments REAL,
                status TEXT,
                order_id TEXT,
                filled_price REAL,
                quantity REAL,
                attempts INTEGER,
                preview_id TEXT,
                error_message TEXT,
                execution_log TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Add preview_id column if it doesn't exist (migration)
        try:
            cursor.execute("PRAGMA table_info(tradingview_execution_history)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'preview_id' not in columns:
                cursor.execute("ALTER TABLE tradingview_execution_history ADD COLUMN preview_id TEXT")
                print("✓ Added preview_id column to tradingview_execution_history")
        except Exception as e:
            pass  # Column already exists or error adding it
        
        # Migration: Add new columns for options trading if table exists without them
        try:
            # Check if strike column exists by trying to query it
            cursor.execute("SELECT strike FROM trade_executions LIMIT 1")
        except:
            # Column doesn't exist, add it
            try:
                cursor.execute("ALTER TABLE trade_executions ADD COLUMN strike REAL")
            except:
                pass
        
        try:
            cursor.execute("SELECT option_type FROM trade_executions LIMIT 1")
        except:
            try:
                cursor.execute("ALTER TABLE trade_executions ADD COLUMN option_type TEXT")
            except:
                pass
        
        try:
            cursor.execute("SELECT purchase_price FROM trade_executions LIMIT 1")
        except:
            try:
                cursor.execute("ALTER TABLE trade_executions ADD COLUMN purchase_price REAL")
            except:
                pass
        
        try:
            cursor.execute("SELECT expiration_date FROM trade_executions LIMIT 1")
        except:
            try:
                cursor.execute("ALTER TABLE trade_executions ADD COLUMN expiration_date TEXT")
            except:
                pass
        
        # Migration: Add source column to trade_signals table if it doesn't exist
        try:
            cursor.execute("SELECT source FROM trade_signals LIMIT 1")
        except:
            # Column doesn't exist, add it
            try:
                cursor.execute("ALTER TABLE trade_signals ADD COLUMN source TEXT")
            except:
                pass
        
        # Migration: Add title and message columns to trade_signals table if they don't exist
        try:
            cursor.execute("SELECT title FROM trade_signals LIMIT 1")
        except:
            # Column doesn't exist, add it
            try:
                cursor.execute("ALTER TABLE trade_signals ADD COLUMN title TEXT")
            except:
                pass
        
        try:
            cursor.execute("SELECT message FROM trade_signals LIMIT 1")
        except:
            # Column doesn't exist, add it
            try:
                cursor.execute("ALTER TABLE trade_signals ADD COLUMN message TEXT")
            except:
                pass
        
        # Add dashboard_read and x_read columns if they don't exist (migration)
        try:
            cursor.execute("PRAGMA table_info(trade_signals)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'dashboard_read' not in columns:
                cursor.execute("ALTER TABLE trade_signals ADD COLUMN dashboard_read BOOLEAN DEFAULT 0")
            if 'x_read' not in columns:
                cursor.execute("ALTER TABLE trade_signals ADD COLUMN x_read BOOLEAN DEFAULT 0")
        except Exception as e:
            logger.warning(f"Could not add read status columns: {e}")
        
        # Migration: Add fraction column to trade_executions table if it doesn't exist
        try:
            cursor.execute("SELECT fraction FROM trade_executions LIMIT 1")
        except:
            # Column doesn't exist, add it
            try:
                cursor.execute("ALTER TABLE trade_executions ADD COLUMN fraction REAL")
            except:
                pass
        
        # Migration: Add title_filter column to channels table if it doesn't exist
        try:
            cursor.execute("SELECT title_filter FROM channels LIMIT 1")
        except:
            # Column doesn't exist, add it
            try:
                cursor.execute("ALTER TABLE channels ADD COLUMN title_filter TEXT")
            except:
                pass
        
        # Create x_signal_analysis table for storing signal analysis results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS x_signal_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER UNIQUE NOT NULL,
                signal_type TEXT,
                engagement_score REAL,
                score_breakdown TEXT,
                recommendation TEXT,
                star_rating TEXT,
                entities TEXT,
                analyzed_at TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES trade_signals(id)
            )
        """)
        
        # Create x_tweet_variants table for storing generated tweet variants
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS x_tweet_variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                analysis_id INTEGER NOT NULL,
                variant_type TEXT NOT NULL,
                tweet_text TEXT NOT NULL,
                predicted_engagement INTEGER,
                style_description TEXT,
                is_recommended BOOLEAN DEFAULT 0,
                is_selected BOOLEAN DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES trade_signals(id),
                FOREIGN KEY (analysis_id) REFERENCES x_signal_analysis(id)
            )
        """)
        
        # Create x_posted_tweets table for tracking posted tweets and their performance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS x_posted_tweets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                analysis_id INTEGER,
                variant_id INTEGER,
                tweet_id TEXT UNIQUE,
                tweet_text TEXT NOT NULL,
                predicted_engagement INTEGER,
                actual_likes INTEGER DEFAULT 0,
                actual_retweets INTEGER DEFAULT 0,
                actual_replies INTEGER DEFAULT 0,
                actual_views INTEGER DEFAULT 0,
                total_engagement INTEGER DEFAULT 0,
                posted_at TEXT NOT NULL,
                last_updated TEXT,
                FOREIGN KEY (signal_id) REFERENCES trade_signals(id),
                FOREIGN KEY (analysis_id) REFERENCES x_signal_analysis(id),
                FOREIGN KEY (variant_id) REFERENCES x_tweet_variants(id)
            )
        """)
        
        # Create x_grok_analyses table for storing Grok AI predictions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS x_grok_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                prompt TEXT,
                response TEXT,
                predicted_engagement INTEGER,
                confidence INTEGER,
                trending_data TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES trade_signals(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_channel_prompt(self, channel_name: str, prompt: str, title_filter: Optional[str] = None, model_provider: Optional[str] = None) -> bool:
        """Save or update a channel prompt with optional title filter and model provider."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Default to openai if not specified
        if not model_provider:
            model_provider = 'openai'
        
        try:
            # Check which columns exist
            cursor.execute("PRAGMA table_info(channels)")
            columns = [col[1] for col in cursor.fetchall()]
            has_title_filter = 'title_filter' in columns
            has_model_provider = 'model_provider' in columns
            
            if has_title_filter and has_model_provider:
                cursor.execute("""
                    INSERT INTO channels (channel_name, channel_prompt, title_filter, model_provider, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(channel_name) 
                    DO UPDATE SET channel_prompt = ?, title_filter = ?, model_provider = ?, updated_at = ?
                """, (channel_name, prompt, title_filter, model_provider, now, now, prompt, title_filter, model_provider, now))
            elif has_title_filter:
                cursor.execute("""
                    INSERT INTO channels (channel_name, channel_prompt, title_filter, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(channel_name) 
                    DO UPDATE SET channel_prompt = ?, title_filter = ?, updated_at = ?
                """, (channel_name, prompt, title_filter, now, now, prompt, title_filter, now))
            else:
                # Fallback for older schema
                cursor.execute("""
                    INSERT INTO channels (channel_name, channel_prompt, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(channel_name) 
                    DO UPDATE SET channel_prompt = ?, updated_at = ?
                """, (channel_name, prompt, now, now, prompt, now))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving channel prompt: {e}")
            return False
        finally:
            conn.close()
    
    def update_channel_title_filter(self, channel_name: str, title_filter: Optional[str] = None) -> bool:
        """Update the title filter for an existing channel."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            # Check if title_filter column exists, add it if it doesn't
            cursor.execute("PRAGMA table_info(channels)")
            columns = [col[1] for col in cursor.fetchall()]
            has_title_filter = 'title_filter' in columns
            
            if not has_title_filter:
                # Add the column if it doesn't exist (migration)
                try:
                    cursor.execute("ALTER TABLE channels ADD COLUMN title_filter TEXT")
                    conn.commit()
                    print("✓ Added title_filter column to channels table")
                except Exception as e:
                    print(f"Error adding title_filter column: {e}")
                    import traceback
                    traceback.print_exc()
                    conn.close()
                    return False
            
            # Update the title filter
            cursor.execute("""
                UPDATE channels 
                SET title_filter = ?, updated_at = ?
                WHERE channel_name = ?
            """, (title_filter, now, channel_name))
            
            if cursor.rowcount == 0:
                print(f"Warning: No rows updated for channel '{channel_name}'. Channel may not exist.")
                conn.close()
                return False
            
            conn.commit()
            conn.close()
            print(f"✓ Updated title_filter to '{title_filter}' for channel '{channel_name}'")
            return True
            
        except Exception as e:
            print(f"Error updating channel title filter: {e}")
            import traceback
            traceback.print_exc()
            try:
                conn.close()
            except:
                pass
            return False
    
    def duplicate_channel(self, source_channel_name: str, new_channel_name: str) -> bool:
        """Duplicate a channel with all its settings (prompt, title_filter, model_provider)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            # Get the source channel info
            source_info = self.get_channel_info(source_channel_name)
            if not source_info:
                print(f"Source channel '{source_channel_name}' not found")
                conn.close()
                return False
            
            # Check if new channel name already exists
            existing = self.get_channel_info(new_channel_name)
            if existing:
                print(f"Channel '{new_channel_name}' already exists")
                conn.close()
                return False
            
            # Get channel data
            prompt = source_info.get("channel_prompt", "")
            title_filter = source_info.get("title_filter")
            model_provider = source_info.get("model_provider", "openai")
            
            # Check which columns exist
            cursor.execute("PRAGMA table_info(channels)")
            columns = [col[1] for col in cursor.fetchall()]
            has_title_filter = 'title_filter' in columns
            has_model_provider = 'model_provider' in columns
            
            # Insert the duplicated channel
            if has_title_filter and has_model_provider:
                cursor.execute("""
                    INSERT INTO channels (channel_name, channel_prompt, title_filter, model_provider, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (new_channel_name, prompt, title_filter, model_provider, now, now))
            elif has_title_filter:
                cursor.execute("""
                    INSERT INTO channels (channel_name, channel_prompt, title_filter, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (new_channel_name, prompt, title_filter, now, now))
            else:
                cursor.execute("""
                    INSERT INTO channels (channel_name, channel_prompt, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                """, (new_channel_name, prompt, now, now))
            
            conn.commit()
            conn.close()
            print(f"✓ Duplicated channel '{source_channel_name}' to '{new_channel_name}'")
            return True
            
        except Exception as e:
            print(f"Error duplicating channel: {e}")
            import traceback
            traceback.print_exc()
            try:
                conn.close()
            except:
                pass
            return False
    
    def rename_channel(self, old_channel_name: str, new_channel_name: str) -> bool:
        """Rename a channel."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            # Check if old channel exists
            old_info = self.get_channel_info(old_channel_name)
            if not old_info:
                print(f"Channel '{old_channel_name}' not found")
                conn.close()
                return False
            
            # Check if new channel name already exists
            existing = self.get_channel_info(new_channel_name)
            if existing:
                print(f"Channel '{new_channel_name}' already exists")
                conn.close()
                return False
            
            # Update the channel name
            cursor.execute("""
                UPDATE channels 
                SET channel_name = ?, updated_at = ?
                WHERE channel_name = ?
            """, (new_channel_name, now, old_channel_name))
            
            if cursor.rowcount == 0:
                print(f"Warning: No rows updated for channel '{old_channel_name}'")
                conn.close()
                return False
            
            # Also update any related data (signals, training data, etc.)
            # Update trade_signals table
            try:
                cursor.execute("""
                    UPDATE trade_signals 
                    SET channel_name = ?
                    WHERE channel_name = ?
                """, (new_channel_name, old_channel_name))
            except Exception as e:
                print(f"Warning: Could not update trade_signals: {e}")
            
            # Update training_data table if it exists
            try:
                cursor.execute("""
                    UPDATE training_data 
                    SET channel_name = ?
                    WHERE channel_name = ?
                """, (new_channel_name, old_channel_name))
            except Exception as e:
                print(f"Warning: Could not update training_data: {e}")
            
            conn.commit()
            conn.close()
            print(f"✓ Renamed channel '{old_channel_name}' to '{new_channel_name}'")
            return True
            
        except Exception as e:
            print(f"Error renaming channel: {e}")
            import traceback
            traceback.print_exc()
            try:
                conn.close()
            except:
                pass
            return False
    
    def update_channel_model_provider(self, channel_name: str, model_provider: str) -> bool:
        """Update the model provider for an existing channel."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            # Check if model_provider column exists, add it if it doesn't
            cursor.execute("PRAGMA table_info(channels)")
            columns = [col[1] for col in cursor.fetchall()]
            has_model_provider = 'model_provider' in columns
            
            if not has_model_provider:
                # Add the column if it doesn't exist (migration)
                try:
                    cursor.execute("ALTER TABLE channels ADD COLUMN model_provider TEXT DEFAULT 'openai'")
                    conn.commit()
                    print("✓ Added model_provider column to channels table")
                except Exception as e:
                    print(f"Error adding model_provider column: {e}")
                    import traceback
                    traceback.print_exc()
                    conn.close()
                    return False
            
            # Update the model provider
            cursor.execute("""
                UPDATE channels 
                SET model_provider = ?, updated_at = ?
                WHERE channel_name = ?
            """, (model_provider, now, channel_name))
            
            if cursor.rowcount == 0:
                print(f"Warning: No rows updated for channel '{channel_name}'. Channel may not exist.")
                conn.close()
                return False
            
            conn.commit()
            conn.close()
            print(f"✓ Updated model_provider to '{model_provider}' for channel '{channel_name}'")
            return True
            
        except Exception as e:
            print(f"Error updating channel model provider: {e}")
            import traceback
            traceback.print_exc()
            try:
                conn.close()
            except:
                pass
            return False
    
    def get_channel_prompt(self, channel_name: str) -> Optional[str]:
        """Get the prompt for a specific channel."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT channel_prompt FROM channels WHERE channel_name = ?
        """, (channel_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def get_all_channels(self) -> List[Dict]:
        """Get all channels with their metadata including title_filter and model_provider."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check which columns exist
        cursor.execute("PRAGMA table_info(channels)")
        columns = [col[1] for col in cursor.fetchall()]
        has_title_filter = 'title_filter' in columns
        has_model_provider = 'model_provider' in columns
        
        if has_title_filter and has_model_provider:
            cursor.execute("""
                SELECT channel_name, title_filter, model_provider, created_at, updated_at 
                FROM channels 
                ORDER BY updated_at DESC
            """)
        elif has_title_filter:
            cursor.execute("""
                SELECT channel_name, title_filter, created_at, updated_at 
                FROM channels 
                ORDER BY updated_at DESC
            """)
        else:
            cursor.execute("""
                SELECT channel_name, created_at, updated_at 
                FROM channels 
                ORDER BY updated_at DESC
            """)
        
        channels = []
        for row in cursor.fetchall():
            if has_title_filter and has_model_provider:
                channels.append({
                    "channel_name": row[0],
                    "title_filter": row[1],
                    "model_provider": row[2] or "openai",  # Default to openai if null
                    "created_at": row[3],
                    "updated_at": row[4]
                })
            elif has_title_filter:
                channels.append({
                    "channel_name": row[0],
                    "title_filter": row[1],
                    "model_provider": "openai",  # Default to openai for old channels
                    "created_at": row[2],
                    "updated_at": row[3]
                })
            else:
                channels.append({
                    "channel_name": row[0],
                    "title_filter": None,
                    "model_provider": "openai",  # Default to openai for old channels
                    "created_at": row[1],
                    "updated_at": row[2]
                })
        
        conn.close()
        return channels
    
    def get_channel_info(self, channel_name: str) -> Optional[Dict]:
        """Get channel information including prompt, title_filter, and model_provider."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check which columns exist
        cursor.execute("PRAGMA table_info(channels)")
        columns = [col[1] for col in cursor.fetchall()]
        has_title_filter = 'title_filter' in columns
        has_model_provider = 'model_provider' in columns
        
        if has_title_filter and has_model_provider:
            cursor.execute("""
                SELECT channel_name, channel_prompt, title_filter, model_provider, created_at, updated_at
                FROM channels WHERE channel_name = ?
            """, (channel_name,))
        elif has_title_filter:
            cursor.execute("""
                SELECT channel_name, channel_prompt, title_filter, created_at, updated_at
                FROM channels WHERE channel_name = ?
            """, (channel_name,))
        else:
            cursor.execute("""
                SELECT channel_name, channel_prompt, created_at, updated_at
                FROM channels WHERE channel_name = ?
            """, (channel_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        if has_title_filter and has_model_provider:
            return {
                "channel_name": result[0],
                "channel_prompt": result[1],
                "title_filter": result[2],
                "model_provider": result[3],
                "created_at": result[4],
                "updated_at": result[5]
            }
        elif has_title_filter:
            return {
                "channel_name": result[0],
                "channel_prompt": result[1],
                "title_filter": result[2],
                "created_at": result[3],
                "updated_at": result[4]
            }
        else:
            return {
                "channel_name": result[0],
                "channel_prompt": result[1],
                "title_filter": None,
                "created_at": result[2],
                "updated_at": result[3]
            }
    
    def find_channel_by_title_filter(self, title: str) -> Optional[str]:
        """
        Find channel whose title_filter matches the given title.
        Uses case-insensitive substring matching.
        Supports both OR and AND logic:
        - Multiple filters separated by "(OR)" match if ANY filter matches
        - Multiple filters separated by "(AND)" match if ALL filters match
        - Can combine both: "filter1 (AND) filter2 (OR) filter3" means (filter1 AND filter2) OR filter3
        
        Examples:
        - "test1" matches title containing "test1"
        - "test1 (OR) test2 (OR) test3" matches title containing any of "test1", "test2", or "test3"
        - "test1 (AND) test2" matches title containing both "test1" AND "test2"
        - "test1 (AND) test2 (OR) test3" matches title containing (both "test1" AND "test2") OR "test3"
        
        Args:
            title: The signal title to match against
            
        Returns:
            Channel name if match found, None otherwise
        """
        if not title or not title.strip():
            return None
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if title_filter column exists
        cursor.execute("PRAGMA table_info(channels)")
        columns = [col[1] for col in cursor.fetchall()]
        has_title_filter = 'title_filter' in columns
        
        if not has_title_filter:
            conn.close()
            return None
        
        # Get all channels with title_filter
        cursor.execute("""
            SELECT channel_name, title_filter 
            FROM channels 
            WHERE title_filter IS NOT NULL AND title_filter != ''
        """)
        
        title_lower = title.lower().strip()
        
        for row in cursor.fetchall():
            channel_name = row[0]
            title_filter = row[1]
            
            if title_filter:
                # Split by "(OR)" (case-insensitive) to get OR groups
                # Each OR group will be evaluated separately
                or_groups = re.split(r'\s*\(OR\)\s*', title_filter, flags=re.IGNORECASE)
                
                # Check if any OR group matches
                for or_group in or_groups:
                    or_group = or_group.strip()
                    if not or_group:
                        continue
                    
                    # Check if this OR group contains AND logic
                    if re.search(r'\s*\(AND\)\s*', or_group, flags=re.IGNORECASE):
                        # Split by "(AND)" - ALL parts must match
                        and_filters = re.split(r'\s*\(AND\)\s*', or_group, flags=re.IGNORECASE)
                        all_match = True
                        
                        for and_filter in and_filters:
                            filter_lower = and_filter.strip().lower()
                            if filter_lower and filter_lower not in title_lower:
                                all_match = False
                                break
                        
                        # If all AND filters match, this OR group matches
                        if all_match:
                            conn.close()
                            return channel_name
                    else:
                        # No AND logic - just check if this single filter matches
                        filter_lower = or_group.strip().lower()
                        if filter_lower and filter_lower in title_lower:
                            conn.close()
                            return channel_name
        
        conn.close()
        return None
    
    # ==================== Smart Executor Methods ====================
    
    def create_execution_attempt(self, signal_data: Dict, platform: str) -> int:
        """Create a new execution attempt record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Extract date components if present
        exp_date = signal_data.get("expiration_date")
        year, month, day = None, None, None
        
        if isinstance(exp_date, dict):
            year = exp_date.get("year")
            month = exp_date.get("month")
            day = exp_date.get("day")
        elif isinstance(exp_date, str) and exp_date:
            try:
                parts = exp_date.split("-")
                if len(parts) == 3:
                    year, month, day = parts
            except:
                pass
        
        cursor.execute("""
            INSERT INTO trade_execution_attempts 
            (signal_id, platform, status, ticker, direction, option_type, 
             strike_price, purchase_price, input_position_size,
             input_date_year, input_date_month, input_date_day,
             created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_data.get("signal_id"),
            platform,
            "in_progress",
            signal_data.get("ticker"),
            signal_data.get("direction"),
            signal_data.get("option_type"),
            signal_data.get("strike_price"),
            signal_data.get("purchase_price"),
            signal_data.get("input_position_size", 2),
            year,
            month,
            day,
            now
        ))
        
        execution_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return execution_id
    
    def update_execution_attempt(
        self,
        execution_id: int,
        status: str = None,
        step_reached: int = None,
        error_message: str = None,
        order_id: str = None,
        filled_price: float = None,
        final_position_size: int = None,
        final_expiration_date: str = None,
        fill_attempts: int = None,
        log: str = None
    ):
        """Update an execution attempt record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Build update query dynamically
        updates = []
        params = []
        
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        
        if step_reached is not None:
            updates.append("step_reached = ?")
            params.append(step_reached)
        
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        
        if order_id is not None:
            updates.append("order_id = ?")
            params.append(order_id)
        
        if filled_price is not None:
            updates.append("filled_price = ?")
            params.append(filled_price)
        
        if final_position_size is not None:
            updates.append("final_position_size = ?")
            params.append(final_position_size)
        
        if final_expiration_date is not None:
            updates.append("final_expiration_date = ?")
            params.append(final_expiration_date)
        
        if fill_attempts is not None:
            updates.append("fill_attempts = ?")
            params.append(fill_attempts)
        
        if log is not None:
            updates.append("execution_log = ?")
            params.append(log)
        
        updates.append("completed_at = ?")
        params.append(now)
        
        params.append(execution_id)
        
        query = f"UPDATE trade_execution_attempts SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, tuple(params))
        
        conn.commit()
        conn.close()
    
    def get_execution_attempts(self, limit: int = 50) -> List[Dict]:
        """Get execution attempt history."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, signal_id, platform, step_reached, status,
                ticker, direction, option_type, strike_price, purchase_price,
                input_position_size, input_date_year, input_date_month, input_date_day,
                final_expiration_date, final_position_size,
                order_id, filled_price, fill_attempts,
                error_message, execution_log,
                created_at, completed_at
            FROM trade_execution_attempts
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        executions = []
        for row in cursor.fetchall():
            executions.append({
                "id": row[0],
                "signal_id": row[1],
                "platform": row[2],
                "step_reached": row[3],
                "status": row[4],
                "ticker": row[5],
                "direction": row[6],
                "option_type": row[7],
                "strike_price": row[8],
                "purchase_price": row[9],
                "input_position_size": row[10],
                "input_date_year": row[11],
                "input_date_month": row[12],
                "input_date_day": row[13],
                "final_expiration_date": row[14],
                "final_position_size": row[15],
                "order_id": row[16],
                "filled_price": row[17],
                "fill_attempts": row[18],
                "error_message": row[19],
                "execution_log": row[20],
                "created_at": row[21],
                "completed_at": row[22]
            })
        
        conn.close()
        return executions
    
    def delete_execution_attempt(self, execution_id: int) -> bool:
        """Delete a specific execution attempt by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                DELETE FROM trade_execution_attempts WHERE id = ?
            """, (execution_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            print(f"Error deleting execution attempt: {e}")
            conn.rollback()
            conn.close()
            return False
    
    def clear_execution_attempts(self) -> bool:
        """Clear all execution attempts."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First check if table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='trade_execution_attempts'
            """)
            table_exists = cursor.fetchone()
            if not table_exists:
                print("[ERROR] trade_execution_attempts table does not exist")
                conn.close()
                return False
            
            # Get count before deletion
            cursor.execute("SELECT COUNT(*) FROM trade_execution_attempts")
            count_before = cursor.fetchone()[0]
            print(f"[DEBUG] Clearing {count_before} execution attempts")
            
            # Delete all records
            cursor.execute("DELETE FROM trade_execution_attempts")
            deleted_count = cursor.rowcount
            conn.commit()
            
            print(f"[DEBUG] Deleted {deleted_count} execution attempts")
            conn.close()
            return True
        except Exception as e:
            print(f"[ERROR] Error clearing execution attempts: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            conn.close()
            return False
    
    def delete_channel(self, channel_name: str, delete_related_data: bool = True) -> Dict:
        """
        Delete a channel and optionally all related data.
        
        Args:
            channel_name: Name of the channel to delete
            delete_related_data: If True, also delete training data, signals, and executions
            
        Returns:
            Dictionary with deletion results
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if channel exists
            cursor.execute("SELECT id FROM channels WHERE channel_name = ?", (channel_name,))
            channel = cursor.fetchone()
            
            if not channel:
                return {
                    "success": False,
                    "error": f"Channel '{channel_name}' not found",
                    "channel_deleted": False,
                    "training_data_deleted": 0,
                    "signals_deleted": 0,
                    "executions_deleted": 0
                }
            
            training_deleted = 0
            signals_deleted = 0
            executions_deleted = 0
            
            if delete_related_data:
                # Get signal IDs for this channel
                cursor.execute("SELECT id FROM trade_signals WHERE channel_name = ?", (channel_name,))
                signal_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete executions for these signals
                if signal_ids:
                    placeholders = ','.join('?' * len(signal_ids))
                    cursor.execute(f"DELETE FROM trade_executions WHERE signal_id IN ({placeholders})", signal_ids)
                    executions_deleted = cursor.rowcount
                
                # Delete signals for this channel
                cursor.execute("DELETE FROM trade_signals WHERE channel_name = ?", (channel_name,))
                signals_deleted = cursor.rowcount
                
                # Delete training data for this channel
                cursor.execute("DELETE FROM training_data WHERE channel_name = ?", (channel_name,))
                training_deleted = cursor.rowcount
            
            # Delete the channel itself
            cursor.execute("DELETE FROM channels WHERE channel_name = ?", (channel_name,))
            channel_deleted = cursor.rowcount > 0
            
            conn.commit()
            
            return {
                "success": True,
                "channel_deleted": channel_deleted,
                "training_data_deleted": training_deleted,
                "signals_deleted": signals_deleted,
                "executions_deleted": executions_deleted,
                "total_deleted": 1 + training_deleted + signals_deleted + executions_deleted
            }
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e),
                "channel_deleted": False,
                "training_data_deleted": 0,
                "signals_deleted": 0,
                "executions_deleted": 0
            }
        finally:
            conn.close()
    
    def save_training_data(self, channel_name: str, signal_text: str, 
                          signal_date: Optional[str] = None, weight: float = 1.0) -> bool:
        """Save training data for a channel."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO training_data 
                (channel_name, signal_text, signal_date, weight, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (channel_name, signal_text, signal_date, weight, now))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving training data: {e}")
            return False
        finally:
            conn.close()
    
    def get_training_data(self, channel_name: str) -> List[Dict]:
        """Get all training data for a channel."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT signal_text, signal_date, weight, created_at
            FROM training_data
            WHERE channel_name = ?
            ORDER BY signal_date DESC NULLS LAST
        """, (channel_name,))
        
        training_data = []
        for row in cursor.fetchall():
            training_data.append({
                "signal_text": row[0],
                "signal_date": row[1],
                "weight": row[2],
                "created_at": row[3]
            })
        
        conn.close()
        return training_data
    
    def log_received_signal(self, channel_name: str, raw_content: str, 
                           title: Optional[str] = None, message: Optional[str] = None) -> int:
        """Log a received trade signal and return its ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        # Check if title and message columns exist
        cursor.execute("PRAGMA table_info(trade_signals)")
        columns = [col[1] for col in cursor.fetchall()]
        has_title_message = 'title' in columns and 'message' in columns
        
        if has_title_message:
            cursor.execute("""
                INSERT INTO trade_signals 
                (channel_name, raw_content, status, received_at, title, message)
                VALUES (?, ?, 'received', ?, ?, ?)
            """, (channel_name, raw_content, now, title, message))
        else:
            cursor.execute("""
                INSERT INTO trade_signals 
                (channel_name, raw_content, status, received_at)
                VALUES (?, ?, 'received', ?)
            """, (channel_name, raw_content, now))
        
        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return signal_id
    
    def update_signal_status(self, signal_id: int, status: str, 
                            parsed_signal: Optional[str] = None):
        """Update the status of a trade signal."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        if parsed_signal:
            cursor.execute("""
                UPDATE trade_signals 
                SET status = ?, parsed_signal = ?, processed_at = ?
                WHERE id = ?
            """, (status, parsed_signal, now, signal_id))
        else:
            cursor.execute("""
                UPDATE trade_signals 
                SET status = ?, processed_at = ?
                WHERE id = ?
            """, (status, now, signal_id))
        
        conn.commit()
        conn.close()
    
    def log_trade_execution(self, signal_id: int, symbol: str, action: str,
                           quantity: float = None, price: float = None,
                           stop_loss: float = None, take_profit: float = None,
                           strike: float = None, option_type: str = None,
                           purchase_price: float = None, expiration_date: str = None,
                           fraction: float = None,
                           webull_order_id: str = None, status: str = "executed",
                           error_message: str = None) -> int:
        """Log a trade execution."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        cursor.execute("""
            INSERT INTO trade_executions 
            (signal_id, symbol, action, quantity, price, stop_loss, take_profit,
             strike, option_type, purchase_price, expiration_date, fraction,
             webull_order_id, status, error_message, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (signal_id, symbol, action, quantity, price, stop_loss, take_profit,
              strike, option_type, purchase_price, expiration_date, fraction,
              webull_order_id, status, error_message, now))
        
        execution_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return execution_id
    
    def get_recent_signals(self, limit: int = 50, exclude_commentary: bool = False) -> List[Dict]:
        """Get recent trade signals with their execution status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if title and message columns exist
        cursor.execute("PRAGMA table_info(trade_signals)")
        columns = [col[1] for col in cursor.fetchall()]
        has_title_message = 'title' in columns and 'message' in columns
        
        # Build WHERE clause to exclude Commentary if requested (case-insensitive)
        where_clause = ""
        if exclude_commentary:
            where_clause = "WHERE LOWER(ts.channel_name) != 'commentary'"
        
        if has_title_message:
            query = f"""
                SELECT 
                    ts.id, ts.channel_name, ts.raw_content, ts.parsed_signal,
                    ts.status, ts.received_at, ts.processed_at, ts.title, ts.message,
                    te.symbol, te.action, te.status as execution_status,
                    te.strike, te.option_type, te.purchase_price, te.expiration_date,
                    te.webull_order_id, te.error_message
                FROM trade_signals ts
                LEFT JOIN trade_executions te ON ts.id = te.signal_id
                {where_clause}
                ORDER BY ts.received_at DESC
                LIMIT ?
            """
            cursor.execute(query, (limit,))
        else:
            query = f"""
                SELECT 
                    ts.id, ts.channel_name, ts.raw_content, ts.parsed_signal,
                    ts.status, ts.received_at, ts.processed_at,
                    te.symbol, te.action, te.status as execution_status,
                    te.strike, te.option_type, te.purchase_price, te.expiration_date,
                    te.webull_order_id, te.error_message
                FROM trade_signals ts
                LEFT JOIN trade_executions te ON ts.id = te.signal_id
                {where_clause}
                ORDER BY ts.received_at DESC
                LIMIT ?
            """
            cursor.execute(query, (limit,))
        
        signals = []
        for row in cursor.fetchall():
            if has_title_message:
                signal = {
                    "id": row[0],
                    "channel_name": row[1],
                    "raw_content": row[2],
                    "parsed_signal": row[3],
                    "status": row[4],
                    "received_at": row[5],
                    "processed_at": row[6],
                    "title": row[7],
                    "message": row[8],
                    "symbol": row[9],
                    "action": row[10],
                    "execution_status": row[11],
                }
                # Adjust indices for remaining fields
                idx = 12
            else:
                signal = {
                    "id": row[0],
                    "channel_name": row[1],
                    "raw_content": row[2],
                    "parsed_signal": row[3],
                    "status": row[4],
                    "received_at": row[5],
                    "processed_at": row[6],
                    "title": None,
                    "message": None,
                    "symbol": row[7],
                    "action": row[8],
                    "execution_status": row[9],
                }
                idx = 10
            
            # Add remaining execution fields
            if has_title_message:
                signal.update({
                    "strike": row[12] if len(row) > 12 else None,
                    "option_type": row[13] if len(row) > 13 else None,
                    "purchase_price": row[14] if len(row) > 14 else None,
                    "expiration_date": row[15] if len(row) > 15 else None,
                    "webull_order_id": row[16] if len(row) > 16 else None,
                    "error_message": row[17] if len(row) > 17 else None,
                })
            else:
                signal.update({
                    "strike": row[10] if len(row) > 10 else None,
                    "option_type": row[11] if len(row) > 11 else None,
                    "purchase_price": row[12] if len(row) > 12 else None,
                    "expiration_date": row[13] if len(row) > 13 else None,
                    "webull_order_id": row[14] if len(row) > 14 else None,
                    "error_message": row[15] if len(row) > 15 else None,
                })
            
            signals.append(signal)
        
        conn.close()
        return signals
    
    def clear_all_signals(self) -> Dict:
        """
        Clear all trade signals and their associated executions.
        
        Returns:
            Dictionary with deletion results
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First, delete all trade executions (they reference signals)
            cursor.execute("DELETE FROM trade_executions")
            executions_deleted = cursor.rowcount
            
            # Then, delete all trade signals
            cursor.execute("DELETE FROM trade_signals")
            signals_deleted = cursor.rowcount
            
            conn.commit()
            
            return {
                "success": True,
                "signals_deleted": signals_deleted,
                "executions_deleted": executions_deleted,
                "total_deleted": signals_deleted + executions_deleted
            }
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e),
                "signals_deleted": 0,
                "executions_deleted": 0,
                "total_deleted": 0
            }
        finally:
            conn.close()
    
    def delete_signal(self, signal_id: int) -> Dict:
        """
        Delete a single signal and its associated executions.
        
        Args:
            signal_id: ID of the signal to delete
            
        Returns:
            Dictionary with deletion results
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First, delete executions for this signal
            cursor.execute("DELETE FROM trade_executions WHERE signal_id = ?", (signal_id,))
            executions_deleted = cursor.rowcount
            
            # Then, delete the signal itself
            cursor.execute("DELETE FROM trade_signals WHERE id = ?", (signal_id,))
            signal_deleted = cursor.rowcount > 0
            
            conn.commit()
            
            return {
                "success": signal_deleted,
                "signal_deleted": signal_deleted,
                "executions_deleted": executions_deleted,
                "total_deleted": (1 if signal_deleted else 0) + executions_deleted
            }
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e),
                "signal_deleted": False,
                "executions_deleted": 0,
                "total_deleted": 0
            }
        finally:
            conn.close()
    
    def clear_signals_by_source(self, source: str) -> Dict:
        """
        Clear all trade signals from a specific source.
        
        Args:
            source: Source identifier (e.g., 'chrome_extension')
            
        Returns:
            Dictionary with deletion results
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if source column exists
            cursor.execute("PRAGMA table_info(trade_signals)")
            columns = [col[1] for col in cursor.fetchall()]
            has_source_column = 'source' in columns
            
            if not has_source_column:
                # If source column doesn't exist, filter by channel_name
                channel_pattern = f"external_{source}%"
                cursor.execute("SELECT id FROM trade_signals WHERE channel_name LIKE ?", (channel_pattern,))
            else:
                # Filter by source column
                cursor.execute("SELECT id FROM trade_signals WHERE source = ?", (source,))
            
            signal_ids = [row[0] for row in cursor.fetchall()]
            
            if not signal_ids:
                return {
                    "success": True,
                    "signals_deleted": 0,
                    "executions_deleted": 0,
                    "total_deleted": 0,
                    "message": f"No signals found for source: {source}"
                }
            
            # Delete executions for these signals
            placeholders = ','.join('?' * len(signal_ids))
            cursor.execute(f"DELETE FROM trade_executions WHERE signal_id IN ({placeholders})", signal_ids)
            executions_deleted = cursor.rowcount
            
            # Delete signals
            if not has_source_column:
                cursor.execute("DELETE FROM trade_signals WHERE channel_name LIKE ?", (channel_pattern,))
            else:
                cursor.execute("DELETE FROM trade_signals WHERE source = ?", (source,))
            signals_deleted = cursor.rowcount
            
            conn.commit()
            
            return {
                "success": True,
                "signals_deleted": signals_deleted,
                "executions_deleted": executions_deleted,
                "total_deleted": signals_deleted + executions_deleted
            }
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e),
                "signals_deleted": 0,
                "executions_deleted": 0,
                "total_deleted": 0
            }
        finally:
            conn.close()
    
    def clear_signals_by_channel(self, channel_name: str) -> Dict:
        """
        Clear all trade signals for a specific channel.
        
        Args:
            channel_name: Name of the channel to clear signals for
            
        Returns:
            Dictionary with deletion results
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First, get signal IDs for this channel
            cursor.execute("SELECT id FROM trade_signals WHERE channel_name = ?", (channel_name,))
            signal_ids = [row[0] for row in cursor.fetchall()]
            
            if not signal_ids:
                return {
                    "success": True,
                    "signals_deleted": 0,
                    "executions_deleted": 0,
                    "total_deleted": 0,
                    "message": f"No signals found for channel: {channel_name}"
                }
            
            # Delete executions for these signals
            placeholders = ','.join('?' * len(signal_ids))
            cursor.execute(f"DELETE FROM trade_executions WHERE signal_id IN ({placeholders})", signal_ids)
            executions_deleted = cursor.rowcount
            
            # Delete signals for this channel
            cursor.execute("DELETE FROM trade_signals WHERE channel_name = ?", (channel_name,))
            signals_deleted = cursor.rowcount
            
            conn.commit()
            
            return {
                "success": True,
                "signals_deleted": signals_deleted,
                "executions_deleted": executions_deleted,
                "total_deleted": signals_deleted + executions_deleted
            }
        except Exception as e:
            conn.rollback()
            return {
                "success": False,
                "error": str(e),
                "signals_deleted": 0,
                "executions_deleted": 0,
                "total_deleted": 0
            }
        finally:
            conn.close()
    
    def save_setting(self, setting_key: str, setting_value: str) -> bool:
        """
        Save or update a setting.
        
        Args:
            setting_key: Setting key/name
            setting_value: Setting value
        
        Returns:
            True if successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO settings (setting_key, setting_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(setting_key) 
                DO UPDATE SET setting_value = ?, updated_at = ?
            """, (setting_key, setting_value, now, setting_value, now))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Error saving setting: {e}")
            return False
        finally:
            conn.close()
    
    def get_setting(self, setting_key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a setting value.
        
        Args:
            setting_key: Setting key/name
            default: Default value if setting not found
        
        Returns:
            Setting value or default
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT setting_value FROM settings WHERE setting_key = ?", (setting_key,))
            result = cursor.fetchone()
            return result[0] if result else default
        except Exception as e:
            print(f"Error getting setting: {e}")
            return default
        finally:
            conn.close()


