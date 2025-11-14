"""
Main application - Reddit User Engagement Bot for LeaseWatch

Discovers relevant Reddit threads using Gemini CLI, generates responses with 
LM Studio, and posts comments while tracking engagement to prevent spam.
"""

import os
import sys
import time
import signal
from datetime import datetime
from dotenv import load_dotenv

from src.logger import setup_logger
from src.database import Database
from src.gemini_client import GeminiClient
from src.reddit_client import RedditClient
from src.lm_studio_client import LMStudioClient

# Load environment variables
load_dotenv()

# Initialize logger
logger = setup_logger(
    log_level=os.getenv('LOG_LEVEL', 'INFO'),
    log_file=os.getenv('LOG_FILE', './logs/reddit_bot.log')
)

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    logger.info("Shutdown signal received. Finishing current cycle...")
    running = False


def validate_environment():
    """
    Validate that all required environment variables are set.
    
    Returns:
        True if valid, False otherwise
    """
    required_vars = [
        'REDDIT_CLIENT_ID',
        'REDDIT_CLIENT_SECRET',
        'REDDIT_USERNAME',
        'REDDIT_PASSWORD',
        'REDDIT_USER_AGENT'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please copy .env.example to .env and fill in all values")
        return False
    
    return True


def initialize_clients():
    """
    Initialize all API clients.
    
    Returns:
        Tuple of (database, gemini_client, reddit_client, lm_studio_client)
        or None if initialization fails
    """
    try:
        # Initialize database
        db_path = os.getenv('DATABASE_PATH', './database/reddit_engagement.db')
        db = Database(db_path)
        
        # Initialize Gemini client
        gemini = GeminiClient(
            cli_path=os.getenv('GEMINI_CLI_PATH', 'gemini'),
            prompt_file='./prompts/gemini_discovery.txt'
        )
        
        # Initialize Reddit client
        reddit = RedditClient(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            username=os.getenv('REDDIT_USERNAME'),
            password=os.getenv('REDDIT_PASSWORD'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )
        
        # Initialize LM Studio client
        lm_studio = LMStudioClient(
            api_url=os.getenv('LM_STUDIO_URL', 'http://localhost:1234/v1/chat/completions'),
            model=os.getenv('LM_STUDIO_MODEL', 'meta-llama-3.1-8b-instruct'),
            temperature=float(os.getenv('LM_STUDIO_TEMPERATURE', '0.7')),
            max_tokens=int(os.getenv('LM_STUDIO_MAX_TOKENS', '-1')),
            prompt_file='./prompts/response_generation.txt'
        )
        
        return db, gemini, reddit, lm_studio
        
    except Exception as e:
        logger.error(f"Failed to initialize clients: {str(e)}")
        return None


def test_connections(gemini, reddit, lm_studio):
    """
    Test all API connections before starting main loop.
    
    Args:
        gemini: GeminiClient instance
        reddit: RedditClient instance
        lm_studio: LMStudioClient instance
    
    Returns:
        True if all connections successful, False otherwise
    """
    logger.info("Testing API connections...")
    
    # Test Gemini CLI
    if not gemini.test_connection():
        logger.error("Gemini CLI test failed - check installation and PATH")
        return False
    
    # Test Reddit API
    if not reddit.test_connection():
        logger.error("Reddit API test failed - check credentials")
        return False
    
    # Test LM Studio API
    if not lm_studio.test_connection():
        logger.error("LM Studio API test failed - ensure LM Studio is running")
        return False
    
    logger.info("All API connections successful!")
    return True


def process_thread(db, reddit, lm_studio, thread_info, subreddit_cooldown_days, thread_cooldown_days):
    """
    Process a single thread: search, generate response, and post.
    
    Args:
        db: Database instance
        reddit: RedditClient instance
        lm_studio: LMStudioClient instance
        thread_info: Thread information from Gemini
        subreddit_cooldown_days: Subreddit cooldown period
        thread_cooldown_days: Thread cooldown period (usually very large)
    
    Returns:
        True if successfully posted, False otherwise
    """
    subreddit = thread_info.get('subreddit')
    title = thread_info.get('title')
    keywords = thread_info.get('keywords', [])
    
    logger.info(f"Processing thread: {title[:50]}... in r/{subreddit}")
    
    # Check subreddit cooldown
    if db.is_subreddit_on_cooldown(subreddit, subreddit_cooldown_days):
        logger.info(f"r/{subreddit} is on cooldown - skipping")
        return False
    
    # Search for thread on Reddit
    submission = reddit.search_thread_by_exact_title(subreddit, title)
    
    if not submission:
        # Try keyword search as fallback
        submission = reddit.search_thread(subreddit, [title] + keywords)
    
    if not submission:
        logger.warning(f"Could not find thread on Reddit: {title[:50]}...")
        return False
    
    # Get thread details
    thread_details = reddit.get_thread_details(submission)
    reddit_thread_id = thread_details['reddit_thread_id']
    
    # Check if thread is locked or archived
    if reddit.is_thread_archived(submission):
        logger.info(f"Thread {reddit_thread_id} is archived - skipping")
        return False
    
    if reddit.is_thread_locked(submission):
        logger.info(f"Thread {reddit_thread_id} is locked - skipping")
        return False
    
    # Check if we've already responded to this thread
    if db.has_responded_to_thread(reddit_thread_id):
        logger.info(f"Already responded to thread {reddit_thread_id} - skipping")
        return False
    
    # Add thread to database if not exists
    thread_id = db.add_thread(
        reddit_thread_id=reddit_thread_id,
        subreddit=thread_details['subreddit'],
        title=thread_details['title'],
        url=thread_details['url'],
        created_utc=thread_details['created_utc'],
        author=thread_details['author'],
        score=thread_details['score'],
        num_comments=thread_details['num_comments']
    )
    
    if thread_id is None:
        # Thread already exists, get the ID
        existing_thread = db.get_thread_by_reddit_id(reddit_thread_id)
        thread_id = existing_thread['id']
    
    # Generate response using LM Studio
    logger.info("Generating response with LM Studio...")
    response_text = lm_studio.generate_response(
        subreddit=thread_details['subreddit'],
        title=thread_details['title'],
        content=thread_details['selftext']
    )
    
    if not response_text:
        logger.error("Failed to generate response")
        return False
    
    # Validate response
    if not lm_studio.validate_response(response_text):
        logger.error("Generated response failed validation")
        return False
    
    # Save response to database
    response_id = db.add_response(
        thread_id=thread_id,
        reddit_thread_id=reddit_thread_id,
        subreddit=thread_details['subreddit'],
        response_text=response_text,
        status='pending'
    )
    
    # Post comment to Reddit
    logger.info("Posting comment to Reddit...")
    comment_id = reddit.post_comment(submission, response_text)
    
    if comment_id:
        # Mark as posted and update cooldown
        db.update_response_posted(response_id, comment_id)
        db.update_subreddit_cooldown(subreddit, subreddit_cooldown_days)
        logger.info(f"Successfully posted comment {comment_id} to r/{subreddit}")
        return True
    else:
        # Mark as failed
        db.update_response_failed(response_id, "Failed to post to Reddit")
        logger.error("Failed to post comment")
        return False


def main_loop(db, gemini, reddit, lm_studio):
    """
    Main execution loop - runs every CHECK_INTERVAL_MINUTES.
    
    Args:
        db: Database instance
        gemini: GeminiClient instance
        reddit: RedditClient instance
        lm_studio: LMStudioClient instance
    """
    check_interval = int(os.getenv('CHECK_INTERVAL_MINUTES', '10')) * 60  # Convert to seconds
    subreddit_cooldown_days = int(os.getenv('SUBREDDIT_COOLDOWN_DAYS', '3'))
    thread_cooldown_days = int(os.getenv('THREAD_COOLDOWN_DAYS', '999999'))
    
    logger.info(f"Starting main loop (checking every {check_interval/60} minutes)")
    logger.info(f"Subreddit cooldown: {subreddit_cooldown_days} days")
    logger.info(f"Thread cooldown: {thread_cooldown_days} days")
    
    cycle_count = 0
    
    while running:
        cycle_count += 1
        cycle_start = datetime.now()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting cycle #{cycle_count} at {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}")
        
        try:
            # Query Gemini for relevant threads
            threads = gemini.discover_threads()
            
            # Log Gemini query to database
            db.log_gemini_query(
                query_text="Discovery query",
                response_text=f"Found {len(threads)} threads",
                success=True,
                threads_found=len(threads)
            )
            
            if not threads:
                logger.info("No relevant threads found in this cycle")
            else:
                logger.info(f"Found {len(threads)} potentially relevant threads")
                
                # Process each thread
                posts_made = 0
                for idx, thread_info in enumerate(threads, 1):
                    logger.info(f"\nProcessing thread {idx}/{len(threads)}")
                    
                    success = process_thread(
                        db, reddit, lm_studio, thread_info,
                        subreddit_cooldown_days, thread_cooldown_days
                    )
                    
                    if success:
                        posts_made += 1
                        # Only post once per cycle to be conservative
                        logger.info("Posted successfully - stopping this cycle")
                        break
                
                logger.info(f"Cycle complete: {posts_made} post(s) made")
            
            # Print statistics
            stats = db.get_statistics()
            logger.info(f"\nOverall Statistics:")
            logger.info(f"  Total threads discovered: {stats['total_threads']}")
            logger.info(f"  Posts in last 24h: {stats['posts_last_24h']}")
            logger.info(f"  Active cooldowns: {stats['active_cooldowns']}")
            logger.info(f"  Response status breakdown: {stats['responses_by_status']}")
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}", exc_info=True)
        
        # Calculate time until next cycle
        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        sleep_time = max(0, check_interval - cycle_duration)
        
        if running and sleep_time > 0:
            next_run = datetime.now().timestamp() + sleep_time
            next_run_str = datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"\nSleeping for {sleep_time/60:.1f} minutes until next cycle at {next_run_str}")
            
            # Sleep in smaller intervals to allow for graceful shutdown
            for _ in range(int(sleep_time)):
                if not running:
                    break
                time.sleep(1)


def main():
    """Main entry point"""
    logger.info("="*60)
    logger.info("Reddit User Engagement Bot for LeaseWatch")
    logger.info("="*60)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Validate environment
    if not validate_environment():
        logger.error("Environment validation failed")
        sys.exit(1)
    
    # Initialize clients
    clients = initialize_clients()
    if not clients:
        logger.error("Client initialization failed")
        sys.exit(1)
    
    db, gemini, reddit, lm_studio = clients
    
    # Test connections
    if not test_connections(gemini, reddit, lm_studio):
        logger.error("Connection tests failed")
        sys.exit(1)
    
    # Start main loop
    try:
        main_loop(db, gemini, reddit, lm_studio)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    main()
