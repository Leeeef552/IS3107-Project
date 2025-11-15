# **Bitcoin Analytics Platform — Complete Setup & Deployment Guide**

This guide walks you through the **entire lifecycle** of deploying, initializing, and running the Bitcoin Analytics Platform—from Docker build to Streamlit dashboard interaction.
It integrates environment setup, Airflow DAG sequencing, TimescaleDB validation, real-time streaming, dashboard launch instructions, and project directory structure into a single, cohesive workflow.

---

# **Table of Contents**

1. [Prerequisites](#prerequisites)
2. [Project Directory Structure](#project-directory-structure)
3. [Environment Setup](#environment-setup)
4. [Build Docker Image & Validate API Keys](#build-docker-image--validate-api-keys)
5. [Start the System Using Docker Compose](#start-the-system-using-docker-compose)
6. [Airflow Setup & DAG Execution Order](#airflow-setup--dag-execution-order)
7. [Database Verification](#database-verification)
8. [Start Real-Time Price Stream](#start-real-time-price-stream)
9. [Enable Batch Update Pipelines](#enable-batch-update-pipelines)
10. [Run the Streamlit Dashboard](#run-the-streamlit-dashboard)
11. [Interact With the Dashboard](#interact-with-the-dashboard)
12. [Troubleshooting](#troubleshooting)
13. [Architecture Summary](#architecture-summary)

---

# **Prerequisites**

### **Required Software**

* Python **3.8+**
* Docker Desktop
* Git

Verify installations:

```bash
python --version
docker --version
git --version
```

### **Hardware Requirements**

* **8 GB RAM minimum** (16 GB recommended)
* **10+ GB free disk space**

---

# **Project Directory Structure**

Use this as a reference for where each major component lives.

```

IS3107-Project/
├── .env
├── .gitignore
├── README.md
├── requirements.txt
├── docker-compose.yaml
├── Dockerfile
├── example.env
├── ml.ipynb
│
├── airflow/
│   ├── dags/
│   │   ├── __init__.py
│   │   ├── batch_update_fng.py
│   │   ├── batch_update_price_and_news.py
│   │   ├── batch_update_whale.py
│   │   ├── fng_init_dag.py
│   │   ├── model_prediction_pipeline.py
│   │   ├── model_training_pipeline_dag.py
│   │   ├── news_init_dag.py
│   │   ├── price_init_dag.py
│   │   └── whale_init_dag.py
│   └── logs/
│
├── configs/
│   └── config.py
│
├── dashboard/
│   ├── .streamlit/
│   │   └── config.toml
│   ├── __init__.py
│   ├── app.py
│   ├── binance_ws.py
│   ├── cryptocompare_orderbook_ws.py
│   ├── data_queries.py
│   └── README.md
│
├── historical_data/
│   └── btcusd_1-min_data.parquet
│
├── prediction/
│   ├── output/
│   │   └── predictions_20251115_005321.csv
│   ├── prepared/
│   │   └── inference_data_lb120_20251115_005316.joblib
│   ├── preprocessed/
│   │   ├── fear_greed_processed.parquet
│   │   ├── price_1h_processed.parquet
│   │   └── sentiment_1h_processed.parquet
│   └── raw/
│       ├── fear_greed_index.parquet
│       ├── historical_price.parquet
│       └── news_sentiment.parquet
│
├── schema/
│   ├── aggregates/
│   │   ├── agg_15min.sql
│   │   ├── agg_1day.sql
│   │   ├── agg_1hour.sql
│   │   ├── agg_1month.sql
│   │   ├── agg_1w.sql
│   │   └── agg_5min.sql
│   ├── sentiment/
│   │   ├── init_sentiment_db.sql
│   │   └── sentiment_aggregates.sql
│   ├── init_price_db.sql
│   └── init_whale_db.sql
│
├── scripts/
│   ├── __init__.py
│   ├── fng/
│   │   ├── init_fng.py
│   │   └── update_fng.py
│   ├── machine_learning_prediction/
│   │   ├── predict.py
│   │   ├── prepare_prediction_data.py
│   │   ├── preprocess_data.py
│   │   ├── pull_data.py
│   │   └── save_predictions.py
│   ├── machine_learning_training/
│   │   ├── evaluation.py
│   │   ├── model.py
│   │   ├── prepare_training_data.py
│   │   ├── preprocess_data.py
│   │   ├── pull_data.py
│   │   └── training.py
│   ├── news_sentiment/
│   │   ├── analyze_sentiment.py
│   │   ├── fetch_news.py
│   │   ├── load_sentiment.py
│   │   └── update_sentiment.py
│   ├── price/
│   │   ├── __init__.py
│   │   ├── backfill_price.py
│   │   ├── create_aggregates.py
│   │   ├── init_historical_price.py
│   │   ├── load_price.py
│   │   └── update_price.py
│   ├── stream_data/
│   │   ├── __init__.py
│   │   └── price_stream.py
│   └── whale/
│       ├── __init__.py
│       ├── extract_large_transactions.py
│       ├── fetch_recent_blocks.py
│       ├── load_whale_transactions.py
│       └── transform_whale_sentiments.py
│
├── training/
│   ├── evaluation/
│   │   ├── evaluation_results_20251115_004644.joblib
│   │   └── plots/
│   │       ├── error_distribution_20251115_004644.png
│   │       ├── forecast_20251115_004644.png
│   │       └── loss_curves_20251115_004644.png
│   ├── model/
│   │   ├── best_model_regression.pth
│   │   └── training_artifacts_20251115_004638.joblib
│   ├── preprocessed/
│   │   ├── fear_greed_processed.parquet
│   │   ├── price_1h_processed.parquet
│   │   └── sentiment_1h_processed.parquet
│   ├── raw/
│   │   ├── fear_greed_index.parquet
│   │   ├── historical_price.parquet
│   │   └── news_sentiment.parquet
│   └── train_test_splits/
│       └── training_data_lb60_fh6_20251115_004622.joblib
│
└── utils/
    ├── __init__.py
    └── logger.py
```

---

# **Important: Run ALL Commands From the Project Root**

Before running **anything**, ensure you are in:

```bash
cd bitcoin-analytics-platform
```

This ensures:

* Docker builds correctly
* Volume mounts work correctly
* Airflow recognizes DAG files
* Streamlit can import modules
* Python scripts resolve paths correctly

---

# **Environment Setup**

### 1. Copy the sample environment file

```bash
cp example.env .env
```

### 2. Fill all required keys

```env
TIMESCALE_HOST=timescaledb
TIMESCALE_PORT=5432
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=pass
TIMESCALE_DBNAME=postgres

AIRFLOW_UID=50000
AIRFLOW_GID=0

NEWS_API_KEY=your_key
ALPHA_VANTAGE_API_KEY=your_key
CRYPTOCOMPARE_API_KEY=your_key
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
REDDIT_USER_AGENT=BitcoinSentimentBot/1.0
```

All external APIs must be filled or the DAGs will fail.

---

# **Build Docker Image & Validate API Keys**

### 1. Create required Airflow directories

```bash
mkdir -p airflow/logs airflow/plugins airflow/config
```

### 2. Build the platform image

```bash
docker build -t IS3107-project .
```

### 3. Confirm `.env` contains all variables

```bash
cat .env
```

Double-check API keys.

---

# **Start the System Using Docker Compose**

From the project root:

```bash
docker compose up -d
```

Check all containers:

```bash
docker compose ps
```

Ensure everything is **healthy** before proceeding.

---

# **Airflow Setup & DAG Execution Order**

Access Airflow UI:

```
http://localhost:8080
```

Login:

```
airflow / airflow
```

---

## **1. Initialization DAGs (run FIRST, once each)**

Order inside the group does not matter:

1. `price_init_dag`
2. `whale_init_dag`
3. `fng_init_dag`
4. `news_init_dag` *(~15 min)*

These will:

* Download historical data
* Create TimescaleDB tables & indexes
* Build continuous aggregates

---

## **2. Batch Update DAGs (after init DAGs)**

Run in any order:

* `batch_update_price_and_news`
* `batch_update_whale`
* `batch_update_fng`

These keep your database up to date.

---

## **3. ML DAGs (strict order)**

1. `ml_training_dag`
2. `ml_prediction_dag`

Both must succeed before the dashboard can show forecasts.

---

# **Database Verification**

### Test TimescaleDB connectivity:

```bash
docker exec timescaledb psql -U postgres -d postgres -c "SELECT NOW();"
```

### Validate tables:

```bash
docker exec timescaledb psql -U postgres -d postgres -c "SELECT COUNT(*) FROM historical_price;"
```

```bash
docker exec timescaledb psql -U postgres -d postgres -c "SELECT COUNT(*) FROM news_articles;"
```

```bash
docker exec timescaledb psql -U postgres -d postgres -c "SELECT COUNT(*) FROM whale_transactions;"
```

Expect **non-zero** row counts after initialization DAGs.

---

# **Start Real-Time Price Stream**

Run once DB is initialized:

```bash
python -m scripts.stream_data.price_stream
```

This:

* Connects to Binance WebSocket
* Streams OHLCV candles into TimescaleDB
* Keeps the database updated with real-time prices

Run this **in the background** for continuous updates.

---

# **Enable Batch Update Pipelines**

In Airflow UI, **unpause**:

* `batch_update_price_and_news`
* `batch_update_whale`
* `batch_update_fng`

These maintain fresh data automatically.

---

# **Run the Streamlit Dashboard**

### 1. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Update local `.env` (for dashboard only)

```
TIMESCALE_HOST=localhost
```

### 4. Start Streamlit

```bash
streamlit run dashboard/app.py
```

Access the dashboard:

```
http://localhost:8501
```

---

# **Interact With the Dashboard**

You now have access to:

* 📈 Live OHLCV charts
* 📊 Market depth & order book
* 📰 News sentiment (FinBERT)
* 🐋 Whale transactions
* 😨 Fear & Greed Index
* 🤖 12-hour ML forecasts

All components require:

* Initialized database
* ML training + prediction completed
* Live price stream running
* Batch DAGs enabled

---

# **Troubleshooting**

### DAGs not appearing

```bash
ls airflow/dags
```

### Airflow webserver issues

```bash
docker compose restart airflow-webserver
```

### Scheduler issues

```bash
docker compose restart airflow-scheduler
```

### TimescaleDB logs

```bash
docker compose logs timescaledb
```

### Port conflicts

```bash
lsof -i :8080
lsof -i :8501
```

---

# **Architecture Summary**

```
                 ┌──────────────────────────────┐
                 │     External Data Sources    │
                 │ Binance | NewsAPI | FNG |    │
                 │ CryptoCompare | Reddit       │
                 └──────────────┬───────────────┘
                                │
                                ▼
                        AIRFLOW PIPELINE
       ┌──────────────────────────────────────────────┐
       │ Init DAGs → Batch DAGs → ML Training → Pred  │
       └──────────────┬───────────────────────────────┘
                      │
                      ▼
                     TIMESCALEDB
       ┌──────────────────────────────────────────────┐
       │  Historical tables | Live stream | ML tables │
       └──────────────┬──────────────────────────────┘
                      │
                      ▼
               STREAMLIT DASHBOARD
```


