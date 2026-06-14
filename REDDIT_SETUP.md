# Reddit Auto-Posting Setup

## What You Need

To enable automatic Reddit posting, you need to create a Reddit app and get API credentials.

## Step 1: Create Reddit App

1. Go to: https://www.reddit.com/prefs/apps
2. Click **"create another app..."** (or "create app" if first time)
3. Fill in:
   - **Name**: `PulseWatch-HIVE`
   - **App type**: Select **"script"**
   - **Description**: `Automated monitoring and community engagement`
   - **About url**: `https://pulsewatch.us` (optional)
   - **Redirect uri**: `http://localhost:8080` (required, but not used for script apps)
4. Click **"create app"**

## Step 2: Get Your Credentials

After creating the app, you'll see:
- **client_id**: The string under the app name (e.g., `abc123xyz`)
- **client_secret**: The "secret" field
- Your Reddit **username** and **password** (you already have these)

## Step 3: Store Credentials Securely

Create a `.env` file in the workspace root:

```bash
# /home/dario/.openclaw/workspace/.env

# Reddit API Credentials
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
REDDIT_USER_AGENT=PulseWatch-HIVE/1.0 by Dario
```

**Important:** Add `.env` to `.gitignore` so credentials are never committed.

## Step 4: Install PRAW

```bash
pip install praw
```

Or with uv (if available):
```bash
uv pip install praw
```

## Step 5: Test It

```bash
cd /home/dario/.openclaw/workspace
source .env  # or export the variables
python3 scripts/reddit-post.py test "Test post" "This is a test comment from HIVE"
```

## Usage

Once set up, the HIVE can auto-post to Reddit:

```bash
./scripts/reddit-post.sh sre "Re: Monitoring" "Your comment text here..."
```

Or from Python directly:
```bash
python3 scripts/reddit-post.py sre "Your comment" "Optional title"
```

---

*Created: 2026-06-08*
*Status: Ready for credential setup*
