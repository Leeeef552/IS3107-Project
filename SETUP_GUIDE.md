# Bitcoin Analytics Platform — Full Setup & Deployment Guide

A Bitcoin analytics platform featuring:

- **Airflow orchestration**
- **TimescaleDB data warehouse**
- **Real-time price streaming**
- **News & sentiment ingestion (FinBERT)**
- **Whale transaction monitoring**
- **Machine-learning forecasting**
- **Interactive Streamlit dashboard**

This guide unifies all setup steps—including Docker, Airflow, environment variables, DAG order, and dashboard requirements—into a single, complete README.

---

# Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Deployment](#docker-deployment)
4. [Airflow DAG Execution Sequence](#airflow-dag-execution-sequence)
5. [Data Loading & Validation](#data-loading--validation)
6. [Live Price Stream](#live-price-stream)
7. [Streamlit Dashboard](#streamlit-dashboard)
8. [Periodic DAG Scheduling](#periodic-dag-scheduling)
9. [Troubleshooting](#troubleshooting)
10. [Architecture Overview](#architecture-overview)
11. [Next Steps](#next-steps)
12. [Support](#support)

---

# Prerequisites

### Required Software
- **Python 3.8+**
- **Docker Desktop**
- **Git**

Verify installations:

```bash
python --version
docker --version
git --version
````

### Hardware Requirements

* **8 GB RAM** minimum (16 GB recommended)
* **10+ GB free disk space**

---

# Environment Setup

### 1. Create `.env` File

```bash
cp example.env .env
```

### 2. Edit Required Environment Values

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

---

# Docker Deployment

### 1. Create Required Airflow Folders

```bash
mkdir -p airflow/logs airflow/plugins airflow/config
```

### 2. Build the Docker Image

```bash
docker build -t IS3107-project .
```

### 3. Start All Containers

```bash
docker compose up -d
```

### 4. Verify All Services

```bash
docker compose ps
```

Wait until all containers are healthy.

---

# Airflow DAG Execution Sequence

⚠ **Critical:** The order of DAG executions determines whether the database and dashboard work correctly.

Below is the correct initialization workflow.

---

## ✅ **1. Initialization DAGs (must run FIRST — any order within this group)**

Run each ONCE, but all must finish before proceeding:

1. `price_init_dag`
2. `whale_init_dag`
3. `fng_init_dag`
4. `news_init_dag` *(takes ~15+ minutes)*

These DAGs:

* Download historical datasets
* Create database tables & indexes
* Prepare TimescaleDB continuous aggregates

---

## ✅ **2. Batch Update DAGs (run only AFTER all init DAGs are complete)**

Order does not matter:

1. `batch_update_price_and_news`
2. `batch_update_whale`
3. `batch_update_fng`

These DAGs:

* Maintain up-to-date data
* Fetch new price, sentiment, whale, and FNG entries

---

## ✅ **3. Machine Learning DAGs (must run in strict order)**

These depend on full historical datasets being loaded.

**Run in order:**

1. `ml_training_dag`
2. `ml_prediction_dag`

Requirements:

* **Both must succeed before first dashboard run**
* Training creates feature sets & models
* Prediction generates the first 12-hour forecast window

---

# Data Loading & Validation

### Access Airflow UI

```
http://localhost:8080
```

Login:

```
airflow / airflow
```

### Validate TimescaleDB Connection

```bash
docker exec timescaledb psql -U postgres -d postgres -c "SELECT NOW();"
```

### Validate Data Exists

Price:

```bash
docker exec timescaledb psql -U postgres -d postgres -c \
"SELECT COUNT(*) FROM historical_price;"
```

News:

```bash
docker exec timescaledb psql -U postgres -d postgres -c \
"SELECT COUNT(*) FROM news_articles;"
```

Whales:

```bash
docker exec timescaledb psql -U postgres -d postgres -c \
"SELECT COUNT(*) FROM whale_transactions;"
```

---

# Live Price Stream

This project includes a **real-time Binance WebSocket price stream** that inserts data directly into TimescaleDB.

Script location:

```
scripts/test_orderbook_stream.py
```

Run to verify:

```bash
python scripts/test_orderbook_stream.py
```

This confirms:

* WebSocket connectivity
* Real-time order book ingestion
* Database write performance
* Dashboard readiness

Live stream capabilities are used by both:

* **Airflow incremental price update DAGs**
* **The Streamlit dashboard (real-time view)**

---

# Streamlit Dashboard

⚠ **The dashboard will NOT function correctly until:**

* **All 4 init DAGs have completed**
* **ML training DAG has been run successfully**
* **ML prediction DAG has been run successfully**

This ensures:

* All necessary tables exist
* Aggregates are available
* ML results (forecast columns) exist
* Live price stream can load smoothly

---

## 1. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Update `.env` for Local Dashboard

```
TIMESCALE_HOST=localhost
```

## 4. Launch Dashboard

```bash
streamlit run dashboard/app.py
```

Access:

```
http://localhost:8501
```

Dashboard features:

* Real-time OHLCV price charts
* Order book & market depth
* News sentiment analysis
* Fear & Greed metrics
* Whale activity alerts
* ML-based 12-hour forecasts

---

# Periodic DAG Scheduling

Once initialization is complete, enable these DAGs:

### 🔄 Batch DAGs

* May run as frequently as you want
* Keep the dataset fresh

### 🧠 ML Training DAG

* **Runs every 2 weeks**
* Re-trains models when regime change occurs

### 📈 ML Prediction DAG

* **Runs every 12 hours**
* Predicts the NEXT 12 hours of price movement

---

# Troubleshooting

### Missing DAGs

Check folder:

```bash
ls airflow/dags
```

### Webserver not loading

```bash
docker compose logs airflow-webserver
docker compose restart airflow-webserver
```

### Scheduler issues

```bash
docker compose logs airflow-scheduler
docker compose restart airflow-scheduler
```

### Database issues

```bash
docker compose logs timescaledb
docker exec timescaledb psql -U postgres -d postgres -c "SELECT NOW();"
```

### Ports in use

```bash
lsof -i :8080
lsof -i :8501
```

---

# Architecture Overview

```
                        DATA SOURCES
 ┌──────────────────────────────────────────────────────────┐
 │ Bitstamp | Binance WS | NewsAPI | CryptoCompare | Mempool│
 └───────────────┬───────────────┬──────────────────────────┘
                 │               │
                 ▼               ▼
                AIRFLOW ORCHESTRATION
 ┌──────────────────────────────────────────────────────────┐
 │ Init DAGs → Batch DAGs → ML Training → ML Prediction     │
 └───────────────┬──────────────────────────────────────────┘
                 │
                 ▼
                   TIMESCALEDB
 ┌──────────────────────────────────────────────────────────┐
 │ historical_price | news_articles | whale_transactions    │
 │ Live stream | Continuous aggregates | ML features        │
 └───────────────┬──────────────────────────────────────────┘
                 │
                 ▼
               STREAMLIT DASHBOARD
```

---

# Next Steps

* Add new sentiment models
* Integrate more exchanges for redundancy
* Build additional ML pipelines
* Add anomaly detection for whale activity

---

# Support

For issues:

* Check this README
* Inspect Airflow logs
* Validate database query results
* Ensure init DAGs + ML DAGs all completed

```

---
