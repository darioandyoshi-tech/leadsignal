#!/usr/bin/env python3
"""
Reddit Auto-Post via PRAW
Usage: python3 reddit-post.py <subreddit> <title> <comment_text>
"""

import sys
import os
import praw
from datetime import datetime

# Load credentials from environment or .env file
def load_reddit_credentials():
    """Load Reddit API credentials securely."""
    return {
        'client_id': os.getenv('REDDIT_CLIENT_ID'),
        'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
        'user_agent': os.getenv('REDDIT_USER_AGENT', 'PulseWatch-HIVE/1.0 by Dario'),
        'username': os.getenv('REDDIT_USERNAME'),
        'password': os.getenv('REDDIT_PASSWORD')
    }

def post_comment(subreddit_name, title, comment_text):
    """Post a comment to a subreddit discussion."""
    creds = load_reddit_credentials()
    
    if not all(creds.values()):
        print("ERROR: Missing Reddit credentials. Set REDDIT_* environment variables.")
        sys.exit(1)
    
    try:
        # Initialize Reddit client
        reddit = praw.Reddit(
            client_id=creds['client_id'],
            client_secret=creds['client_secret'],
            user_agent=creds['user_agent'],
            username=creds['username'],
            password=creds['password']
        )
        
        # Test connection
        print(f"Logged in as: {reddit.user.me()}")
        
        # Find the target submission (search by title or get hot posts)
        subreddit = reddit.subreddit(subreddit_name)
        
        # Search for recent posts matching the title/context
        # For now, we'll post as a new submission if no match found
        submission = None
        for post in subreddit.hot(limit=25):
            if title.lower() in post.title.lower() or 'third party' in post.title.lower() or 'monitoring' in post.title.lower():
                submission = post
                break
        
        if submission:
            # Reply to existing discussion
            reply = submission.reply(comment_text)
            print(f"SUCCESS: Replied to '{submission.title}'")
            print(f"Comment permalink: https://reddit.com{reply.permalink}")
            return reply.permalink
        else:
            # Create new submission (fallback)
            new_post = subreddit.submit(title, selftext=comment_text)
            print(f"SUCCESS: Created new post '{title}'")
            print(f"Post permalink: https://reddit.com{new_post.permalink}")
            return new_post.permalink
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 reddit-post.py <subreddit> <comment_text> [title]")
        sys.exit(1)
    
    subreddit = sys.argv[1]
    comment = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else "Re: Discussion"
    
    post_comment(subreddit, title, comment)
