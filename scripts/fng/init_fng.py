import requests
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from utils.logger import get_logger
from configs.config import DB_CONFIG

log = get_logger("init_fng.py")

def connect_to_db():
    return psycopg2.connect(**DB_CONFIG)

def fetch_and_transform_fng(days=365):
    url = f"https://api.alternative.me/fng/?limit={days}&format=json"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch FNG  {response.status_code}")
    raw = response.json()['data']
    df = pd.DataFrame(raw)
    df['time'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
    df = df[['time', 'value', 'value_classification']].copy()
    df['value'] = df['value'].astype(int)
    return df.sort_values('time').reset_index(drop=True)

def load_fng(**kwargs):
    days = kwargs.get("days", 365)
    conn = connect_to_db()
    
    # Create table with PRIMARY KEY (idempotent)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fear_greed_index (
            time TIMESTAMPTZ NOT NULL PRIMARY KEY,
            value INTEGER CHECK (value >= 0 AND value <= 100),
            value_classification TEXT
        );
    """)
    conn.commit()
    cur.close()
    log.info("Table fear_greed_index ensured (with PRIMARY KEY)")

    # Fetch and upsert
    df = fetch_and_transform_fng(days=days)
    data = [tuple(row) for row in df[['time', 'value', 'value_classification']].values]

    cur = conn.cursor()
    execute_values(
        cur,
        "INSERT INTO fear_greed_index (time, value, value_classification) VALUES %s ON CONFLICT (time) DO NOTHING",
        data
    )
    conn.commit()
    cur.close()
    log.info(f"Initialized FNG: upserted {len(df)} records (duplicates skipped)")
    conn.close()
    return f"Loaded {len(df)} FNG records (idempotent)"