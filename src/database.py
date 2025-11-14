"""
Database operations for Reddit engagement tracking
"""

import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

logger = logging.getLogger('RedditBot')


class Database:
    """Handles all database operations for the Reddit bot"""
    
    def __init__(self, db_path='./database/reddit_engagement.db'):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        
        # Create database directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database schema
        self._initialize_schema()
        logger.info(f"Database initialized at {db_path}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            conn.close()
    
    def _initialize_schema(self):
        """Create database tables if they don't exist"""
        schema_file = os.path.join(os.path.dirname(self.db_path), 'schema.sql')
        
        if os.path.exists(schema_file):
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                logger.debug("Database schema created/verified")
        else:
            logger.warning(f"Schema file not found: {schema_file}")
    
    # ==================== THREAD OPERATIONS ====================
    
    def thread_exists(self, reddit_thread_id):
        """Check if thread already exists in database"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM threads WHERE reddit_thread_id = ?",
                (reddit_thread_id,)
            )
            return cursor.fetchone() is not None
    
    def add_thread(self, reddit_thread_id, subreddit, title, url, created_utc=None, 
                   author=None, score=0, num_comments=0):
        """
        Add a new thread to the database.
        
        Returns:
            Thread ID if added, None if already exists
        """
        if self.thread_exists(reddit_thread_id):
            logger.debug(f"Thread {reddit_thread_id} already exists")
            return None
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO threads (reddit_thread_id, subreddit, title, url, 
                                   created_utc, author, score, num_comments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (reddit_thread_id, subreddit, title, url, created_utc, 
                  author, score, num_comments))
            
            thread_id = cursor.lastrowid
            logger.info(f"Added thread {reddit_thread_id} from r/{subreddit}")
            return thread_id
    
    def get_thread_by_reddit_id(self, reddit_thread_id):
        """Get thread details by Reddit ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM threads WHERE reddit_thread_id = ?",
                (reddit_thread_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== RESPONSE OPERATIONS ====================
    
    def has_responded_to_thread(self, reddit_thread_id):
        """Check if we've already responded to this thread"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id FROM responses 
                WHERE reddit_thread_id = ? AND status = 'posted'
            """, (reddit_thread_id,))
            return cursor.fetchone() is not None
    
    def add_response(self, thread_id, reddit_thread_id, subreddit, response_text, status='pending'):
        """
        Add a generated response to the database.
        
        Returns:
            Response ID
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO responses (thread_id, reddit_thread_id, subreddit, 
                                     response_text, status)
                VALUES (?, ?, ?, ?, ?)
            """, (thread_id, reddit_thread_id, subreddit, response_text, status))
            
            response_id = cursor.lastrowid
            logger.info(f"Added response for thread {reddit_thread_id} (status: {status})")
            return response_id
    
    def update_response_posted(self, response_id, comment_id):
        """Mark a response as successfully posted"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE responses 
                SET status = 'posted', posted_at = ?, comment_id = ?
                WHERE id = ?
            """, (datetime.now(), comment_id, response_id))
            logger.info(f"Response {response_id} marked as posted (comment: {comment_id})")
    
    def update_response_failed(self, response_id, error_message):
        """Mark a response as failed to post"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE responses 
                SET status = 'failed', error_message = ?
                WHERE id = ?
            """, (error_message, response_id))
            logger.warning(f"Response {response_id} marked as failed: {error_message}")
    
    def update_response_skipped(self, response_id, reason):
        """Mark a response as skipped"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE responses 
                SET status = 'skipped', error_message = ?
                WHERE id = ?
            """, (reason, response_id))
            logger.info(f"Response {response_id} skipped: {reason}")
    
    # ==================== COOLDOWN OPERATIONS ====================
    
    def is_subreddit_on_cooldown(self, subreddit, cooldown_days):
        """
        Check if subreddit is on cooldown.
        
        Args:
            subreddit: Subreddit name
            cooldown_days: Number of days for cooldown period
        
        Returns:
            True if on cooldown, False otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT cooldown_until FROM subreddit_cooldowns 
                WHERE subreddit = ?
            """, (subreddit,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            cooldown_until = datetime.fromisoformat(row['cooldown_until'])
            on_cooldown = datetime.now() < cooldown_until
            
            if on_cooldown:
                logger.debug(f"r/{subreddit} is on cooldown until {cooldown_until}")
            
            return on_cooldown
    
    def update_subreddit_cooldown(self, subreddit, cooldown_days):
        """
        Update the cooldown timestamp for a subreddit after posting.
        
        Args:
            subreddit: Subreddit name
            cooldown_days: Number of days for cooldown period
        """
        now = datetime.now()
        cooldown_until = now + timedelta(days=cooldown_days)
        
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO subreddit_cooldowns (subreddit, last_post_at, cooldown_until)
                VALUES (?, ?, ?)
                ON CONFLICT(subreddit) DO UPDATE SET
                    last_post_at = excluded.last_post_at,
                    cooldown_until = excluded.cooldown_until
            """, (subreddit, now, cooldown_until))
            
            logger.info(f"r/{subreddit} cooldown set until {cooldown_until}")
    
    # ==================== GEMINI QUERY LOGGING ====================
    
    def log_gemini_query(self, query_text, response_text=None, success=True, 
                        error_message=None, threads_found=0):
        """
        Log a Gemini CLI query for debugging and optimization.
        
        Returns:
            Query log ID
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO gemini_queries (query_text, response_text, success, 
                                          error_message, threads_found)
                VALUES (?, ?, ?, ?, ?)
            """, (query_text, response_text, success, error_message, threads_found))
            
            query_id = cursor.lastrowid
            logger.debug(f"Logged Gemini query {query_id} (success: {success}, threads: {threads_found})")
            return query_id
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self):
        """Get overall statistics for monitoring"""
        with self.get_connection() as conn:
            stats = {}
            
            # Total threads discovered
            cursor = conn.execute("SELECT COUNT(*) as count FROM threads")
            stats['total_threads'] = cursor.fetchone()['count']
            
            # Responses by status
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM responses 
                GROUP BY status
            """)
            stats['responses_by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Posts in last 24 hours
            cursor = conn.execute("""
                SELECT COUNT(*) as count 
                FROM responses 
                WHERE posted_at > datetime('now', '-1 day') AND status = 'posted'
            """)
            stats['posts_last_24h'] = cursor.fetchone()['count']
            
            # Active subreddit cooldowns
            cursor = conn.execute("""
                SELECT COUNT(*) as count 
                FROM subreddit_cooldowns 
                WHERE cooldown_until > datetime('now')
            """)
            stats['active_cooldowns'] = cursor.fetchone()['count']
            
            return stats
