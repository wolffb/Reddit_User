# Project Structure

```
Reddit_User/
├── README.md                        # Complete documentation
├── QUICKSTART.md                    # Quick installation & usage guide
├── PROMPT_OPTIMIZATION.md           # Prompt engineering guide
├── .env.example                     # Environment variables template
├── .gitignore                       # Git ignore rules
├── requirements.txt                 # Python dependencies
├── setup_env.sh                     # Conda environment setup script
├── main.py                          # Main application entry point
│
├── src/                            # Source code modules
│   ├── __init__.py                 # Package init
│   ├── database.py                 # SQLite database operations
│   ├── gemini_client.py            # Gemini CLI integration
│   ├── reddit_client.py            # Reddit API wrapper (PRAW)
│   ├── lm_studio_client.py         # LM Studio API client
│   └── logger.py                   # Logging configuration
│
├── prompts/                        # AI prompt templates
│   ├── gemini_discovery.txt        # Thread discovery prompt for Gemini
│   └── response_generation.txt     # Response generation prompt for LLM
│
├── database/                       # Database files
│   ├── schema.sql                  # Database schema definition
│   └── reddit_engagement.db        # SQLite database (created on first run)
│
└── logs/                           # Application logs
    └── reddit_bot.log              # Main log file (created on first run)
```

## Application Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         MAIN LOOP                               │
│                    (Every 10 minutes)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. GEMINI CLI - Discover Relevant Threads                      │
│     • Read prompt from prompts/gemini_discovery.txt             │
│     • Execute: gemini < prompt                                  │
│     • Parse JSON response                                       │
│     • Log query to database                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. CHECK COOLDOWNS                                             │
│     • Query database for subreddit cooldowns                    │
│     • Skip if posted in subreddit < 3 days ago                  │
│     • Skip if already responded to thread                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. REDDIT API - Find Thread                                    │
│     • Search by exact title                                     │
│     • Fallback to keyword search                                │
│     • Check if locked/archived                                  │
│     • Extract thread details                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. SAVE TO DATABASE                                            │
│     • Add thread record (if new)                                │
│     • Check if already responded                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. LM STUDIO - Generate Response                               │
│     • Read prompt from prompts/response_generation.txt          │
│     • Insert thread context (title, content, subreddit)         │
│     • Call http://localhost:1234/v1/completions                 │
│     • Validate response quality                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. REDDIT API - Post Comment                                   │
│     • Submit comment to thread                                  │
│     • Get comment ID                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  7. UPDATE DATABASE                                             │
│     • Mark response as 'posted'                                 │
│     • Save comment ID                                           │
│     • Update subreddit cooldown (3 days)                        │
│     • Log statistics                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SLEEP FOR 10 MINUTES                         │
└─────────────────────────────────────────────────────────────────┘
```

## Key Features

### 🔍 Intelligent Discovery
- Gemini CLI identifies genuinely relevant threads
- Focuses on commercial lease pain points
- Returns structured data with relevance scoring

### 🤖 Natural Response Generation
- Local LLM (meta-llama-3.1-8b-instruct) via LM Studio
- Helper-first approach (not salesy)
- Customizable prompts for optimization

### 🛡️ Spam Prevention
- Never posts in same thread twice
- 3-day cooldown per subreddit (configurable)
- Respects Reddit rate limits (10-min intervals)

### 📊 Complete Tracking
- SQLite database logs all activity
- Track threads, responses, cooldowns, Gemini queries
- Built-in statistics and reporting

### 🔧 Highly Configurable
- All prompts in separate text files
- Environment variables for all settings
- Easy to adjust without code changes

### 📝 Comprehensive Logging
- File logging (database/reddit_bot.log)
- Console logging for monitoring
- Different log levels (DEBUG, INFO, WARNING, ERROR)

## Database Schema Summary

### Tables

1. **threads** - Discovered Reddit threads
   - Stores: ID, subreddit, title, URL, metadata
   
2. **responses** - Generated and posted responses
   - Stores: Response text, status, timestamps, comment IDs
   
3. **subreddit_cooldowns** - Prevents spam
   - Tracks: Last post time, cooldown expiration per subreddit
   
4. **gemini_queries** - Debug Gemini performance
   - Logs: All queries, responses, success/failure

## Environment Variables

### Required
- `REDDIT_CLIENT_ID` - Reddit API credentials
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USERNAME`
- `REDDIT_PASSWORD`
- `REDDIT_USER_AGENT`

### Optional (with defaults)
- `LM_STUDIO_URL` - Default: http://localhost:1234/v1/completions
- `LM_STUDIO_MODEL` - Default: meta-llama-3.1-8b-instruct
- `GEMINI_CLI_PATH` - Default: gemini
- `SUBREDDIT_COOLDOWN_DAYS` - Default: 3
- `THREAD_COOLDOWN_DAYS` - Default: 999999
- `CHECK_INTERVAL_MINUTES` - Default: 10

## Next Steps

1. **Setup Environment:**
   ```bash
   ./setup_env.sh
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Test Connections:**
   ```bash
   conda activate RedditUser
   python -c "from src.gemini_client import GeminiClient; GeminiClient().test_connection()"
   ```

3. **Run Application:**
   ```bash
   python main.py
   ```

4. **Monitor & Optimize:**
   - Watch logs: `tail -f logs/reddit_bot.log`
   - Check database: `sqlite3 database/reddit_engagement.db`
   - Adjust prompts based on performance

## Support

- README.md - Full documentation
- QUICKSTART.md - Installation guide
- PROMPT_OPTIMIZATION.md - Improve AI performance
