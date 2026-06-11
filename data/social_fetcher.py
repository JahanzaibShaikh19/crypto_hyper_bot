"""
data/social_fetcher.py — Social media sentiment via RSS.

Sources:
  1. Nitter RSS — X/Twitter from key accounts (no API key)
  2. Reddit RSS — Hot posts from crypto subreddits
  3. YouTube RSS — Video titles from top crypto channels

Zero API keys needed. Pure RSS parsing.
"""
import asyncio
import feedparser
import httpx
from loguru import logger

from config import (
    NITTER_INSTANCES, NITTER_ACCOUNTS, REDDIT_SUBREDDITS,
    YOUTUBE_CHANNELS, CACHE_NEWS
)
from utils.cache import cache_get, cache_set
from utils.rate_limiter import RSS_LIMITER
from utils.nlp_helper import combined_score, sentiment_score


# ═══════════════════════════════════════════
# NITTER RSS (X/Twitter)
# ═══════════════════════════════════════════

# High-influence accounts — their posts get extra weight
HIGH_INFLUENCE = {"PlanB", "RaoulGMI", "woonomic", "CryptoCobie", "Pentosh1"}
MACRO_ORACLES  = {"PlanB", "RaoulGMI", "APompliano"}  # Macro calls from these = strong override


async def fetch_nitter_account(username: str) -> list:
    """
    Fetch recent tweets for a username via Nitter RSS.
    Tries multiple Nitter instances in case one is down.
    """
    cache_key = f"nitter:{username}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    await RSS_LIMITER.acquire()

    tweets = []
    for instance in NITTER_INSTANCES:
        rss_url = f"{instance}/{username}/rss"
        try:
            feed = await asyncio.get_event_loop().run_in_executor(
                None, feedparser.parse, rss_url
            )
            if feed.entries:
                for entry in feed.entries[:10]:
                    text = entry.get("summary", entry.get("title", ""))
                    # Strip HTML
                    import re
                    text = re.sub(r'<[^>]+>', '', text)

                    nlp = combined_score(text)
                    is_high_influence = username in HIGH_INFLUENCE
                    is_macro_oracle = username in MACRO_ORACLES

                    tweets.append({
                        "account": username,
                        "text": text[:500],
                        "published": entry.get("published", ""),
                        "link": entry.get("link", ""),
                        "sentiment": nlp["final"],
                        "bearish_keywords": nlp["bearish_keywords"],
                        "bullish_keywords": nlp["bullish_keywords"],
                        "is_high_influence": is_high_influence,
                        "is_macro_oracle": is_macro_oracle,
                        "source": "nitter",
                    })
                break  # Got data from this instance, stop
        except Exception as e:
            logger.debug(f"Nitter {instance} failed for {username}: {e}")
            continue

    cache_set(cache_key, tweets, CACHE_NEWS)
    return tweets


async def fetch_all_nitter() -> list:
    """Fetch all monitored accounts in parallel."""
    tasks = [fetch_nitter_account(acct) for acct in NITTER_ACCOUNTS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_tweets = []
    for r in results:
        if isinstance(r, list):
            all_tweets.extend(r)
    return all_tweets


# ═══════════════════════════════════════════
# REDDIT RSS
# ═══════════════════════════════════════════

async def fetch_reddit_subreddit(subreddit: str) -> list:
    """
    Fetch hot posts from a subreddit via JSON API.
    No authentication needed for public feeds.
    """
    cache_key = f"reddit:{subreddit}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    await RSS_LIMITER.acquire()

    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=15"
    headers = {"User-Agent": "CryptoSignalBot/1.0 (research tool)"}

    try:
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.debug(f"Reddit r/{subreddit} error: {e}")
        return []

    posts = []
    for post in data.get("data", {}).get("children", []):
        p = post.get("data", {})
        title = p.get("title", "")
        score = p.get("score", 0)     # upvotes
        nlp   = combined_score(title)

        posts.append({
            "subreddit": subreddit,
            "title": title,
            "score": score,
            "comments": p.get("num_comments", 0),
            "sentiment": nlp["final"],
            "bearish_keywords": nlp["bearish_keywords"],
            "bullish_keywords": nlp["bullish_keywords"],
            "source": "reddit",
        })

    cache_set(cache_key, posts, CACHE_NEWS)
    return posts


async def fetch_all_reddit() -> list:
    """Fetch all monitored subreddits in parallel."""
    tasks = [fetch_reddit_subreddit(sr) for sr in REDDIT_SUBREDDITS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_posts = []
    for r in results:
        if isinstance(r, list):
            all_posts.extend(r)
    return all_posts


# ═══════════════════════════════════════════
# YOUTUBE RSS
# ═══════════════════════════════════════════

YOUTUBE_BEARISH_TITLES = [
    "massive dump", "crash incoming", "bear market", "it's over",
    "sell everything", "bottom not in", "be careful",
]
YOUTUBE_BULLISH_TITLES = [
    "bottom is in", "altseason", "bull run", "to the moon",
    "massive pump", "buy now", "time to buy", "bullish",
    "breakout", "all time high",
]


async def fetch_youtube_channel(channel_name: str, channel_id: str) -> list:
    """
    Fetch recent video titles from a YouTube channel via RSS.
    No YouTube API key needed — this is a public feed.
    """
    cache_key = f"youtube:{channel_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    await RSS_LIMITER.acquire()

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    try:
        feed = await asyncio.get_event_loop().run_in_executor(
            None, feedparser.parse, rss_url
        )
    except Exception as e:
        logger.debug(f"YouTube {channel_name} error: {e}")
        return []

    videos = []
    for entry in feed.entries[:5]:
        title = entry.get("title", "")
        title_lower = title.lower()

        # YouTube title sentiment is crude but useful for aggregate
        nlp = combined_score(title)

        # Check for specific crypto YouTube signals
        yt_bearish = any(kw in title_lower for kw in YOUTUBE_BEARISH_TITLES)
        yt_bullish = any(kw in title_lower for kw in YOUTUBE_BULLISH_TITLES)

        if yt_bearish:
            yt_score = -0.5
        elif yt_bullish:
            yt_score = 0.5
        else:
            yt_score = nlp["final"] * 0.5  # YouTube titles = weaker signal

        videos.append({
            "channel": channel_name,
            "title": title,
            "published": entry.get("published", ""),
            "sentiment": yt_score,
            "source": "youtube",
        })

    cache_set(cache_key, videos, CACHE_NEWS)
    return videos


async def fetch_all_youtube() -> list:
    """Fetch all monitored YouTube channels in parallel."""
    tasks = [
        fetch_youtube_channel(name, channel_id)
        for name, channel_id in YOUTUBE_CHANNELS.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_videos = []
    for r in results:
        if isinstance(r, list):
            all_videos.extend(r)
    return all_videos


# ═══════════════════════════════════════════
# AGGREGATE SOCIAL SCORE
# ═══════════════════════════════════════════

def aggregate_social_score(tweets: list, reddit_posts: list, youtube_videos: list) -> dict:
    """
    Combine Nitter, Reddit, YouTube into single social sentiment score.

    Weighting philosophy:
    - High-influence Twitter > Reddit > YouTube > regular Twitter
    - Macro oracle posts get extra weight
    - More volume of positive signals = stronger conviction
    """
    all_scores = []

    # Twitter — weight by influence
    for tweet in tweets:
        weight = 3 if tweet.get("is_macro_oracle") else \
                 2 if tweet.get("is_high_influence") else 1
        all_scores.append(tweet["sentiment"] * weight)

    # Reddit — weight by upvotes (proxy for engagement)
    for post in reddit_posts:
        upvote_weight = min(post.get("score", 100) / 1000, 2.0) + 1  # 1-3
        all_scores.append(post["sentiment"] * upvote_weight)

    # YouTube — lower weight (often clickbait)
    for video in youtube_videos:
        all_scores.append(video["sentiment"] * 0.5)

    if not all_scores:
        return {"score": 0.0, "tweet_count": 0, "reddit_count": 0, "yt_count": 0}

    avg = sum(all_scores) / len(all_scores)

    # Check for macro oracle macro bearish override
    macro_bearish = [t for t in tweets
                     if t.get("is_macro_oracle") and t["sentiment"] < -0.5]
    macro_override = None
    if macro_bearish:
        macro_override = {
            "account": macro_bearish[0]["account"],
            "text": macro_bearish[0]["text"][:100],
            "score_impact": -1.5,
        }

    # Influencer bullish detection
    influencer_bullish = [t for t in tweets
                          if t.get("is_high_influence") and t["sentiment"] > 0.5]

    return {
        "score": max(-4, min(4, avg * 4)),  # Scale to [-4, +4]
        "tweet_count": len(tweets),
        "reddit_count": len(reddit_posts),
        "yt_count": len(youtube_videos),
        "macro_override": macro_override,
        "influencer_bullish": [
            {"account": t["account"], "text": t["text"][:100]}
            for t in influencer_bullish[:2]
        ],
        "top_tweets": [
            {"account": t["account"], "text": t["text"][:80], "sentiment": t["sentiment"]}
            for t in sorted(tweets, key=lambda x: abs(x["sentiment"]), reverse=True)[:3]
        ],
    }
