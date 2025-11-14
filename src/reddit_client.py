"""
Reddit API client using PRAW for thread discovery and posting
"""

import praw
import logging
from datetime import datetime

logger = logging.getLogger('RedditBot')


class RedditClient:
    """Handles Reddit API interactions for searching and posting"""
    
    def __init__(self, client_id, client_secret, username, password, user_agent):
        """
        Initialize Reddit client with credentials.
        
        Args:
            client_id: Reddit API client ID
            client_secret: Reddit API client secret
            username: Reddit username
            password: Reddit password
            user_agent: User agent string
        """
        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                username=username,
                password=password,
                user_agent=user_agent
            )
            
            # Test authentication
            self.reddit.user.me()
            logger.info(f"Reddit client initialized for user: {username}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {str(e)}")
            raise
    
    def search_thread(self, subreddit_name, title_keywords):
        """
        Search for a thread in a subreddit by title keywords.
        
        Args:
            subreddit_name: Name of subreddit (without r/)
            title_keywords: List of keywords to match in title
        
        Returns:
            Reddit submission object if found, None otherwise
        """
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Search recent posts (last 24-48 hours)
            for submission in subreddit.new(limit=100):
                title_lower = submission.title.lower()
                
                # Check if any keywords match
                if any(keyword.lower() in title_lower for keyword in title_keywords):
                    logger.info(f"Found matching thread: {submission.title[:50]}... in r/{subreddit_name}")
                    return submission
            
            logger.debug(f"No matching thread found in r/{subreddit_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching r/{subreddit_name}: {str(e)}")
            return None
    
    def search_thread_by_exact_title(self, subreddit_name, title):
        """
        Search for a thread by exact title match.
        
        Args:
            subreddit_name: Name of subreddit (without r/)
            title: Exact thread title
        
        Returns:
            Reddit submission object if found, None otherwise
        """
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Search recent posts
            for submission in subreddit.new(limit=100):
                if submission.title.strip() == title.strip():
                    logger.info(f"Found thread by exact title in r/{subreddit_name}")
                    return submission
            
            # Also try searching
            search_results = subreddit.search(f'"{title}"', sort='new', time_filter='week', limit=20)
            for submission in search_results:
                if submission.title.strip() == title.strip():
                    logger.info(f"Found thread via search in r/{subreddit_name}")
                    return submission
            
            logger.warning(f"Thread not found: {title[:50]}... in r/{subreddit_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for exact thread: {str(e)}")
            return None
    
    def get_thread_details(self, submission):
        """
        Extract detailed information from a submission.
        
        Args:
            submission: PRAW submission object
        
        Returns:
            Dictionary with thread details
        """
        return {
            'reddit_thread_id': submission.id,
            'subreddit': submission.subreddit.display_name,
            'title': submission.title,
            'url': f"https://reddit.com{submission.permalink}",
            'created_utc': int(submission.created_utc),
            'author': str(submission.author) if submission.author else '[deleted]',
            'score': submission.score,
            'num_comments': submission.num_comments,
            'selftext': submission.selftext if submission.is_self else ''
        }
    
    def post_comment(self, submission, comment_text):
        """
        Post a comment on a submission.
        
        Args:
            submission: PRAW submission object
            comment_text: Text to post
        
        Returns:
            Comment ID if successful, None otherwise
        """
        try:
            logger.info(f"Posting comment to r/{submission.subreddit.display_name} thread: {submission.title[:50]}...")
            
            comment = submission.reply(comment_text)
            
            logger.info(f"Successfully posted comment: {comment.id}")
            return comment.id
            
        except praw.exceptions.APIException as e:
            logger.error(f"Reddit API error posting comment: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error posting comment: {str(e)}")
            return None
    
    def test_connection(self):
        """
        Test Reddit API connection.
        
        Returns:
            True if connected, False otherwise
        """
        try:
            user = self.reddit.user.me()
            logger.info(f"Reddit connection test successful - logged in as: {user.name}")
            return True
        except Exception as e:
            logger.error(f"Reddit connection test failed: {str(e)}")
            return False
    
    def get_subreddit_rules(self, subreddit_name):
        """
        Get subreddit rules (useful for checking if posting is allowed).
        
        Args:
            subreddit_name: Name of subreddit (without r/)
        
        Returns:
            List of rule dictionaries
        """
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            rules = list(subreddit.rules)
            
            logger.debug(f"Retrieved {len(rules)} rules for r/{subreddit_name}")
            return [{'short_name': rule.short_name, 'description': rule.description} for rule in rules]
            
        except Exception as e:
            logger.error(f"Error getting rules for r/{subreddit_name}: {str(e)}")
            return []
    
    def is_thread_archived(self, submission):
        """
        Check if a thread is archived (cannot comment).
        
        Args:
            submission: PRAW submission object
        
        Returns:
            True if archived, False otherwise
        """
        return submission.archived
    
    def is_thread_locked(self, submission):
        """
        Check if a thread is locked (cannot comment).
        
        Args:
            submission: PRAW submission object
        
        Returns:
            True if locked, False otherwise
        """
        return submission.locked
