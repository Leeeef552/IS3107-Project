import os
import requests
import praw
from datetime import datetime, timedelta, timezone
from typing import List, Dict
from dotenv import load_dotenv
from utils.logger import get_logger

log = get_logger("fetch_news.py")
load_dotenv()

# =====================================================================
# CONFIGURATION
# =====================================================================
BITCOIN_KEYWORDS = [
    "bitcoin", "btc", "btc-usd", "btcusd", "btc price", 
    "bitcoin price", "bitcoin market", "bitcoin trading"
]

class NewsAggregator:
    """Aggregates Bitcoin news from multiple free sources"""
    
    def __init__(self):
        self.news_api_key = os.getenv("NEWS_API_KEY")
        self.cryptocompare_api_key = os.getenv("CRYPTOCOMPARE_API_KEY")
        self.alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        
        # Reddit API credentials (free)
        self.reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        self.reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.reddit_user_agent = os.getenv("REDDIT_USER_AGENT", "BitcoinSentimentBot/1.0")
        
        self.articles = []

    # =================================================================
    # NewsAPI - Professional News Sources
    # =================================================================
    def fetch_newsapi(self, hours_back: int = 1) -> List[Dict]:
        if not self.news_api_key:
            log.warning("NEWS_API_KEY not set, skipping NewsAPI")
            return []
        
        if hours_back < 24:
            log.info("NewsAPI: Skipping for hourly intervals (use daily+ intervals)")
            return []
        
        try:
            max_days_back = 30
            capped_hours = min(hours_back, max_days_back * 24)
            from_date = (datetime.utcnow() - timedelta(hours=capped_hours)).isoformat()
            
            if hours_back > capped_hours:
                log.info(f"NewsAPI: Capped lookup from {hours_back}h to {capped_hours}h (30 day free tier limit)")
            
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": "bitcoin OR btc",
                "from": from_date,
                "sortBy": "publishedAt",
                "language": "en",
                "apiKey": self.news_api_key,
                "pageSize": 100
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            articles = []
            for article in data.get("articles", []):
                combined_text = f"{article.get('title', '')} {article.get('description', '')}".lower()
                if any(kw in combined_text for kw in BITCOIN_KEYWORDS):
                    articles.append({
                        "published_at": article.get("publishedAt"),
                        "title": article.get("title"),
                        "content": article.get("description") or article.get("content"),
                        "url": article.get("url"),
                        "source": f"NewsAPI:{article.get('source', {}).get('name', 'Unknown')}",
                        "author": article.get("author")
                    })
            
            log.info(f"NewsAPI: Fetched {len(articles)} Bitcoin articles")
            return articles
            
        except Exception as e:
            log.error(f"NewsAPI fetch failed: {e}")
            return []

    # =================================================================
    # CryptoCompare - Crypto-focused News
    # =================================================================
    def fetch_cryptocompare(self, hours_back: int = 1) -> List[Dict]:
        if not self.cryptocompare_api_key:
            log.warning("CRYPTOCOMPARE_API_KEY not set, skipping CryptoCompare")
            return []
        
        try:
            url = "https://min-api.cryptocompare.com/data/v2/news/"
            params = {
                "lang": "EN",
                "sortOrder": "latest",
                "categories": "BTC,Trading,Blockchain"
            }
            headers = {
                "authorization": f"Apikey {self.cryptocompare_api_key}"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            articles = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            
            for item in data.get("Data", []):
                pub_time = datetime.utcfromtimestamp(item.get("published_on", 0)).replace(tzinfo=timezone.utc)
                
                if pub_time < cutoff_time:
                    continue
                
                combined_text = f"{item.get('title', '')} {item.get('body', '')}".lower()
                if any(kw in combined_text for kw in BITCOIN_KEYWORDS):
                    articles.append({
                        "published_at": pub_time.isoformat().replace("+00:00", "Z"),
                        "title": item.get("title"),
                        "content": item.get("body"),
                        "url": item.get("url"),
                        "source": f"CryptoCompare:{item.get('source', 'Unknown')}",
                        "author": None,
                        "keywords": item.get("tags", "").split("|") if item.get("tags") else []
                    })
            
            log.info(f"CryptoCompare: Fetched {len(articles)} Bitcoin articles")
            return articles
            
        except Exception as e:
            log.error(f"CryptoCompare fetch failed: {e}")
            return []

    # =================================================================
    # Reddit - Community Sentiment
    # =================================================================
    def fetch_reddit(self, hours_back: int = 1, limit: int = 100) -> List[Dict]:
        if not all([self.reddit_client_id, self.reddit_client_secret]):
            log.warning("Reddit credentials not set, skipping Reddit")
            return []
        
        try:
            reddit = praw.Reddit(
                client_id=self.reddit_client_id,
                client_secret=self.reddit_client_secret,
                user_agent=self.reddit_user_agent
            )
            
            subreddits = ["Bitcoin", "CryptoCurrency", "BitcoinMarkets"]
            articles = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            
            for subreddit_name in subreddits:
                subreddit = reddit.subreddit(subreddit_name)
                for submission in subreddit.hot(limit=limit):
                    post_time = datetime.utcfromtimestamp(submission.created_utc).replace(tzinfo=timezone.utc)
                    
                    if post_time < cutoff_time:
                        continue
                    
                    combined_text = f"{submission.title} {submission.selftext}".lower()
                    if any(kw in combined_text for kw in BITCOIN_KEYWORDS):
                        articles.append({
                            "published_at": post_time.isoformat().replace("+00:00", "Z"),
                            "title": submission.title,
                            "content": submission.selftext[:1000] if submission.selftext else submission.title,
                            "url": f"https://reddit.com{submission.permalink}",
                            "source": f"Reddit:r/{subreddit_name}",
                            "author": str(submission.author) if submission.author else None,
                            "metadata": {
                                "score": submission.score,
                                "num_comments": submission.num_comments,
                                "upvote_ratio": submission.upvote_ratio
                            }
                        })
            
            log.info(f"Reddit: Fetched {len(articles)} Bitcoin posts")
            return articles
            
        except Exception as e:
            log.error(f"Reddit fetch failed: {e}")
            return []

    # =================================================================
    # Alpha Vantage - Chunked News with 30-Day Windows
    # =================================================================
    def fetch_alpha_vantage(self, hours_back: int = 1) -> List[Dict]:
        if not self.alpha_vantage_api_key:
            log.warning("ALPHA_VANTAGE_API_KEY not set, skipping Alpha Vantage")
            return []

        MAX_CHUNK_DAYS = 14
        OVERLAP_DAYS = 7  # Overlap between chunks in days
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=hours_back)
        all_articles = []

        current_start = start_time
        while current_start < now:
            current_end = min(current_start + timedelta(days=MAX_CHUNK_DAYS), now)
            time_from = current_start.strftime("%Y%m%dT%H%M")
            time_to = current_end.strftime("%Y%m%dT%H%M")

            url = "https://www.alphavantage.co/query"
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": "CRYPTO:BTC",
                "time_from": time_from,
                "time_to": time_to,
                "limit": "1000",
                "apikey": self.alpha_vantage_api_key,
                "sort": "RELEVANCE"  # Fixed typo
            }

            try:
                log.info(f"Alpha Vantage: fetching {current_start.strftime('%Y-%m-%d %H:%M')} → {current_end.strftime('%Y-%m-%d %H:%M')}")
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if "feed" not in data:
                    error_msg = data.get("Information") or data.get("Note") or data.get("Error Message") or "Unknown"
                    log.warning(f"Alpha Vantage chunk error: {error_msg}")
                else:
                    feed = data["feed"]
                    log.info(f"  → Retrieved {len(feed)} articles")

                    cutoff_time = now - timedelta(hours=hours_back)
                    for item in feed:
                        tp = item.get("time_published", "")
                        if len(tp) >= 14:
                            try:
                                pub_dt = datetime.strptime(tp[:14], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                            except ValueError:
                                pub_dt = now
                        else:
                            pub_dt = now

                        if pub_dt < cutoff_time:
                            continue

                        authors = item.get("authors", [])
                        author = authors[0] if authors else None

                        all_articles.append({
                            "published_at": pub_dt.isoformat().replace("+00:00", "Z"),
                            "title": item.get("title", ""),
                            "content": item.get("summary", ""),
                            "url": item.get("url", "").strip(),
                            "source": f"AlphaVantage:{item.get('source', 'Unknown')}",
                            "author": author,
                            "keywords": [t.get("topic") for t in item.get("topics", []) if t.get("topic")]
                        })

                # Advance with overlap: next start is current_end minus overlap
                if current_end >= now:
                    break
                current_start = current_end - timedelta(days=OVERLAP_DAYS)

            except Exception as e:
                log.error(f"Alpha Vantage chunk failed: {e}")
                # Still advance to avoid infinite loop
                if current_end >= now:
                    break
                current_start = current_end - timedelta(days=OVERLAP_DAYS)

        # Deduplicate within Alpha Vantage results (optional but safe)
        seen_urls = set()
        deduped = []
        for art in all_articles:
            url = art.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(art)

        log.info(f"Alpha Vantage: Fetched {len(deduped)} unique Bitcoin articles (chunked with {OVERLAP_DAYS}-day overlap)")
        return deduped

    # =================================================================
    # Aggregate All Sources
    # =================================================================
    def fetch_all(self, hours_back: int = 1) -> List[Dict]:
        log.info(f"Fetching Bitcoin news from last {hours_back} hour(s)...")
        
        all_articles = []
        all_articles.extend(self.fetch_newsapi(hours_back))
        all_articles.extend(self.fetch_cryptocompare(hours_back))
        all_articles.extend(self.fetch_reddit(hours_back))
        all_articles.extend(self.fetch_alpha_vantage(hours_back))
        
        # Deduplicate by URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            url = article.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)
        
        log.info(f"Total unique articles fetched: {len(unique_articles)}")
        return unique_articles


# =====================================================================
# MAIN FUNCTION (for testing)
# =====================================================================
def main():
    aggregator = NewsAggregator()
    articles = aggregator.fetch_all(hours_back=24)  # test with 24 hours
    
    print(f"\nFetched {len(articles)} unique Bitcoin articles\n")
    for i, article in enumerate(articles[:5], 1):
        print(f"{i}. [{article['source']}] {article['title']}")
        print(f"   Published: {article['published_at']}")
        print(f"   URL: {article['url']}\n")


if __name__ == "__main__":
    main()