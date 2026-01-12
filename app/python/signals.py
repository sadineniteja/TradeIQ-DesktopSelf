"""
Signals module for recording and retrieving trade signals.
Handles signals from various sources (Chrome extension, API, etc.)
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class Signals:
    def __init__(self, db=None):
        """
        Initialize Signals handler.
        
        Args:
            db: Database instance
        """
        self.db = db
    
    def record_signal(
        self,
        source: str,
        title: str = None,
        message: str = None,
        metadata: Optional[Dict] = None,
        channel_name: Optional[str] = None,
        status: str = "received"
    ) -> int:
        """
        Record a signal into the database.
        
        Args:
            source: Source identifier (e.g., 'chrome_extension', 'api', 'external')
            title: Signal title
            message: Signal message/content
            metadata: Optional metadata dictionary
            channel_name: Optional channel name (defaults to external_source)
            status: Signal status (default: 'received')
        
        Returns:
            Signal ID
        """
        if not self.db:
            logger.error("Database instance not provided")
            return None
        
        # Combine title and message for raw_content
        raw_content_parts = []
        if title:
            raw_content_parts.append(f"Title: {title}")
        if message:
            raw_content_parts.append(f"Message: {message}")
        raw_content = "\n".join(raw_content_parts) if raw_content_parts else message or title or ""
        
        # Default channel_name based on source if not provided
        if not channel_name:
            channel_name = f"external_{source}" if source else "external"
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if source, title, and message columns exist
            cursor.execute("PRAGMA table_info(trade_signals)")
            columns = [col[1] for col in cursor.fetchall()]
            has_source = 'source' in columns
            has_title_message = 'title' in columns and 'message' in columns
            
            now = datetime.now().isoformat()
            
            if has_source and has_title_message:
                cursor.execute("""
                    INSERT INTO trade_signals 
                    (channel_name, raw_content, status, received_at, source, title, message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (channel_name, raw_content, status, now, source, title, message))
            elif has_source:
                cursor.execute("""
                    INSERT INTO trade_signals 
                    (channel_name, raw_content, status, received_at, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (channel_name, raw_content, status, now, source))
            elif has_title_message:
                cursor.execute("""
                    INSERT INTO trade_signals 
                    (channel_name, raw_content, status, received_at, title, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (channel_name, raw_content, status, now, title, message))
            else:
                cursor.execute("""
                    INSERT INTO trade_signals 
                    (channel_name, raw_content, status, received_at)
                    VALUES (?, ?, ?, ?)
                """, (channel_name, raw_content, status, now))
            
            signal_id = cursor.lastrowid
            conn.commit()
            logger.info(f"✓ Recorded signal {signal_id} from source: {source}")
            return signal_id
        except Exception as e:
            logger.error(f"Error recording signal: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_signals(self, limit: int = 100, source: Optional[str] = None) -> List[Dict]:
        """
        Get signals from the database.
        
        Args:
            limit: Maximum number of signals to return
            source: Optional source filter (e.g., 'chrome_extension', 'api')
        
        Returns:
            List of signal dictionaries
        """
        if not self.db:
            logger.error("Database instance not provided")
            return []
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check which columns exist
            cursor.execute("PRAGMA table_info(trade_signals)")
            columns = [col[1] for col in cursor.fetchall()]
            has_source = 'source' in columns
            has_title_message = 'title' in columns and 'message' in columns
            
            # Build query based on available columns and filters
            if source and has_source:
                if has_title_message:
                    cursor.execute("""
                        SELECT id, channel_name, raw_content, parsed_signal, status,
                               received_at, processed_at, source, title, message
                        FROM trade_signals
                        WHERE source = ?
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (source, limit))
                else:
                    cursor.execute("""
                        SELECT id, channel_name, raw_content, parsed_signal, status,
                               received_at, processed_at, source
                        FROM trade_signals
                        WHERE source = ?
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (source, limit))
            else:
                if has_title_message and has_source:
                    cursor.execute("""
                        SELECT id, channel_name, raw_content, parsed_signal, status,
                               received_at, processed_at, source, title, message
                        FROM trade_signals
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (limit,))
                elif has_title_message:
                    cursor.execute("""
                        SELECT id, channel_name, raw_content, parsed_signal, status,
                               received_at, processed_at, title, message
                        FROM trade_signals
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (limit,))
                elif has_source:
                    cursor.execute("""
                        SELECT id, channel_name, raw_content, parsed_signal, status,
                               received_at, processed_at, source
                        FROM trade_signals
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (limit,))
                else:
                    cursor.execute("""
                        SELECT id, channel_name, raw_content, parsed_signal, status,
                               received_at, processed_at
                        FROM trade_signals
                        ORDER BY received_at DESC
                        LIMIT ?
                    """, (limit,))
            
            signals = []
            for row in cursor.fetchall():
                signal = {
                    "id": row[0],
                    "channel_name": row[1],
                    "raw_content": row[2],
                    "parsed_signal": row[3],
                    "status": row[4],
                    "received_at": row[5],
                    "processed_at": row[6],
                }
                
                # Add optional fields based on what's available
                idx = 7
                if has_source and len(row) > idx:
                    signal["source"] = row[idx]
                    idx += 1
                if has_title_message and len(row) > idx:
                    signal["title"] = row[idx]
                    signal["message"] = row[idx + 1] if len(row) > idx + 1 else None
                
                signals.append(signal)
            
            return signals
        except Exception as e:
            logger.error(f"Error getting signals: {str(e)}")
            return []
        finally:
            conn.close()
