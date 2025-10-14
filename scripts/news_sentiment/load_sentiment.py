"""
Load News Sentiment Data into TimescaleDB
Initializes sentiment tables and loads sentiment data
"""

import os
import sys
import psycopg2
import sqlparse
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
from utils.logger import get_logger

log = get_logger("load_sentiment.py")

# =====================================================================
# DATABASE CONFIGURATION
# =====================================================================
def get_db_config():
    """Load database configuration from environment variables"""
    load_dotenv()
    return {
        "host": os.getenv("TIMESCALE_HOST", "localhost"),
        "port": int(os.getenv("TIMESCALE_PORT", 5432)),
        "user": os.getenv("TIMESCALE_USER"),
        "password": os.getenv("TIMESCALE_PASSWORD"),
        "dbname": os.getenv("TIMESCALE_DBNAME", "postgres"),
    }

# =====================================================================
# DATABASE OPERATIONS
# =====================================================================
def connect_to_db(config):
    """Establish connection to TimescaleDB"""
    try:
        conn = psycopg2.connect(**config)
        log.info(f"Connected to TimescaleDB at {config['host']}:{config['port']}/{config['dbname']}")
        return conn
    except Exception as e:
        log.exception(f"Failed to connect to database: {e}")
        raise

def execute_schema_script(conn, script_path: str):
    """Execute SQL schema file"""
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Schema file not found: {os.path.abspath(script_path)}")
    
    with open(script_path, "r") as file:
        sql_commands = file.read()
    
    cur = conn.cursor()
    for statement in sqlparse.split(sql_commands):
        stmt = statement.strip()
        if stmt:
            try:
                cur.execute(stmt)
            except Exception as e:
                log.warning(f"Skipping failed statement:\n{stmt[:100]}...\nError: {e}")
    conn.commit()
    cur.close()
    log.info(f"Schema executed successfully: {script_path}")

def insert_article(conn, article: Dict) -> Optional[int]:
    """
    Insert a news article into the database
    
    Returns:
        article_id if successful, None otherwise
    """
    try:
        cur = conn.cursor()
        
        # Parse published_at timestamp
        published_at = article.get('published_at')
        if isinstance(published_at, str):
            # Handle ISO format with 'Z' or timezone
            published_at = published_at.replace('Z', '+00:00')
            try:
                published_at = datetime.fromisoformat(published_at)
            except:
                published_at = datetime.utcnow()
        
        # Insert article (ON CONFLICT DO NOTHING to handle duplicates)
        insert_query = """
            INSERT INTO news_articles 
            (published_at, title, content, url, source, author, keywords)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (url) DO UPDATE SET
                published_at = EXCLUDED.published_at
            RETURNING article_id
        """
        
        keywords = article.get('keywords', [])
        if isinstance(keywords, str):
            keywords = [keywords]
        
        cur.execute(insert_query, (
            published_at,
            article.get('title'),
            article.get('content'),
            article.get('url'),
            article.get('source'),
            article.get('author'),
            keywords
        ))
        
        result = cur.fetchone()
        article_id = result[0] if result else None
        
        conn.commit()
        cur.close()
        
        return article_id
        
    except Exception as e:
        log.error(f"Failed to insert article: {e}")
        conn.rollback()
        return None

def insert_sentiment(conn, article_id: int, article: Dict) -> bool:
    """
    Insert sentiment data for an article
    
    Returns:
        True if successful, False otherwise
    """
    try:
        cur = conn.cursor()
        
        # Parse timestamp
        published_at = article.get('published_at')
        if isinstance(published_at, str):
            published_at = published_at.replace('Z', '+00:00')
            try:
                published_at = datetime.fromisoformat(published_at)
            except:
                published_at = datetime.utcnow()
        
        # Insert sentiment
        insert_query = """
            INSERT INTO news_sentiment 
            (time, article_id, sentiment_score, sentiment_label, confidence, model_used)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (time, article_id) DO UPDATE SET
                sentiment_score = EXCLUDED.sentiment_score,
                sentiment_label = EXCLUDED.sentiment_label,
                confidence = EXCLUDED.confidence,
                model_used = EXCLUDED.model_used
        """
        
        cur.execute(insert_query, (
            published_at,
            article_id,
            article.get('sentiment_score', 0.0),
            article.get('sentiment_label', 'neutral'),
            article.get('confidence', 0.0),
            article.get('model_used', 'unknown')
        ))
        
        conn.commit()
        cur.close()
        
        return True
        
    except Exception as e:
        log.error(f"Failed to insert sentiment: {e}")
        conn.rollback()
        return False

def bulk_insert_articles_with_sentiment(conn, articles: List[Dict]) -> int:
    """
    Bulk insert articles and their sentiment data
    
    Returns:
        Number of successfully inserted articles
    """
    success_count = 0
    
    for article in articles:
        # Insert article
        article_id = insert_article(conn, article)
        
        if article_id:
            # Insert sentiment
            if insert_sentiment(conn, article_id, article):
                success_count += 1
    
    log.info(f"Successfully inserted {success_count}/{len(articles)} articles with sentiment")
    return success_count

def refresh_continuous_aggregates(conn):
    """Manually refresh continuous aggregates"""
    try:
        # Save original autocommit state
        original_autocommit = conn.autocommit
        
        # Set autocommit to True (required for refresh_continuous_aggregate)
        conn.autocommit = True
        cur = conn.cursor()
        
        aggregates = ['sentiment_1h', 'sentiment_1d', 'sentiment_1w', 'sentiment_1mo']
        
        for agg in aggregates:
            try:
                log.info(f"Refreshing {agg}...")
                cur.execute(f"CALL refresh_continuous_aggregate('{agg}', NULL, NULL);")
                log.info(f"Refreshed {agg}")
            except Exception as e:
                log.warning(f"Failed to refresh {agg}: {e}")
        
        cur.close()
        
        # Restore original autocommit state
        conn.autocommit = original_autocommit
        
    except Exception as e:
        log.error(f"Failed to refresh aggregates: {e}")
        # Restore autocommit on error
        try:
            conn.autocommit = original_autocommit
        except:
            pass

# =====================================================================
# INITIALIZATION FUNCTION
# =====================================================================
def initialize_database(force: bool = False):
    """
    Initialize sentiment database schema
    
    Args:
        force: If True, recreate tables even if they exist
    """
    log.info("=== Initializing Sentiment Database ===")
    
    db_config = get_db_config()
    conn = connect_to_db(db_config)
    
    # Execute schema scripts
    schema_files = [
        "schema/sentiment/init_sentiment_db.sql",
        "schema/sentiment/sentiment_aggregates.sql"
    ]
    
    for schema_file in schema_files:
        if os.path.exists(schema_file):
            execute_schema_script(conn, schema_file)
        else:
            log.warning(f"Schema file not found: {schema_file}")
    
    conn.close()
    log.info("=== Sentiment Database Initialized ===")

# =====================================================================
# MAIN FUNCTION
# =====================================================================
def main():
    """Initialize sentiment database"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize sentiment database')
    parser.add_argument('--force', action='store_true', help='Force recreation of tables')
    args = parser.parse_args()
    
    initialize_database(force=args.force)

if __name__ == "__main__":
    main()

