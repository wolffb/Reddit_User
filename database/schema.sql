-- Reddit Engagement Tracking Database Schema

-- Table: threads
-- Stores information about discovered Reddit threads
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reddit_thread_id TEXT UNIQUE NOT NULL,
    subreddit TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_utc INTEGER,
    author TEXT,
    score INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0
);

-- Table: responses
-- Stores generated and posted responses to threads
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    reddit_thread_id TEXT NOT NULL,
    subreddit TEXT NOT NULL,
    response_text TEXT NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    posted_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending',
    comment_id TEXT,
    error_message TEXT,
    FOREIGN KEY (thread_id) REFERENCES threads(id)
);

-- Table: subreddit_cooldowns
-- Tracks when we last posted to each subreddit to enforce cooldown periods
CREATE TABLE IF NOT EXISTS subreddit_cooldowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subreddit TEXT UNIQUE NOT NULL,
    last_post_at TIMESTAMP NOT NULL,
    cooldown_until TIMESTAMP NOT NULL
);

-- Table: gemini_queries
-- Logs all Gemini CLI queries for debugging and optimization
CREATE TABLE IF NOT EXISTS gemini_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT NOT NULL,
    response_text TEXT,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT 1,
    error_message TEXT,
    threads_found INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_threads_reddit_id ON threads(reddit_thread_id);
CREATE INDEX IF NOT EXISTS idx_threads_subreddit ON threads(subreddit);
CREATE INDEX IF NOT EXISTS idx_responses_status ON responses(status);
CREATE INDEX IF NOT EXISTS idx_subreddit_cooldowns_subreddit ON subreddit_cooldowns(subreddit);
CREATE INDEX IF NOT EXISTS idx_responses_posted_at ON responses(posted_at);
