## 🐳 Setting Up the Airflow Environment (Crypto Analytics Pipeline)

### 1. **Start with the `.env` file**
- follow the `env.example` to `.env` in the **project root**.
- Update any environment variables as needed (API keys). 
- Note: This new .env is meant to allow the project to run properly on docker 

---

### 2. **Project Structure**
- create the logs/plugins/config folders within airflow folder. This is to ensure proper volume mounts into docker
- **All Airflow-related assets go under `/airflow`**, but the `docker-compose.yml`, `Dockerfile`, and `.env` should remain in the **project root**.

```
BT3107-Project/
│
├── docker-compose.yaml
├── Dockerfile
├── requirements.txt
├── .env
├── scripts/
│   ├── price/
│   │   └── init_historical_price.py
│   └── ...
│
└── airflow/
    ├── dags/
    │   ├── price_init_dag.py
    │   ├── news_init_dag.py
    │   ├── whale_init_dag.py
    │   ├── batch_update_price_and_news.py
    │   ├── batch_update_whale.py
    │   └── ... (future: ml_training_dag.py)
    │
    ├── logs/          
    ├── plugins/       
    └── config/        
```

> ✅ **Important**: The `dags/` folder is mounted into the Airflow containers via `docker-compose.yml`, so any `.py` files you place here will be automatically detected.

---

### 3. **Build the Custom Airflow Image**
- uses the dockerfile and will download the `requirements.txt` within the docker containers' environments

```bash
docker build -t bt3107-project .
```

---

### 4. **Docker compose up the project containers**
- there should be total 8 containers, but one is only used for set up (airflow-init container)
- the other 7 containers should be running and healthy for the airflow and timescale to work together properly

```bash
docker compose up -d
```

### 5. Airflow UI 
- the docker compose takes awhile, sometimes might face localhost connection error, if you face this just make sure all the containers are healthy and running
- usually once the airflow-webserver container is running well the ui should be up

Open your browser to:
- **URL**: [http://localhost:8080](http://localhost:8080)
- **Username**: `airflow`
- **Password**: `airflow`

🔍 **Verify DAGs are loaded**:
- Go to the **DAGs** page.
- In the **Tags** search bar, type `crypto`.
- You should see **5 DAGs** appear:
  - `price_init_dag`
  - `news_init_dag`
  - `whale_init_dag`
  - `batch_update_price_and_news`
  - `batch_update_whale`

---

### 6. **DAG Overview & Configuration Tips**

#### 🧱 **Initialization DAGs** (Run once to bootstrap data)
| DAG | Purpose |
|-----|--------|
| `price_init_dag` | Downloads historical price data (e.g., from Kaggle), loads into DB, creates dashboard-ready views |
| `news_init_dag` | Fetches historical news, runs FinBERT sentiment scoring, loads into DB |
| `whale_init_dag` | Fetches recent **N blocks** of Bitcoin transactions, extracts whale/on-chain features, loads into DB |

> ⚠️ **Performance Note**:  
> - These DAGs can take **a long time** if `op_kwargs` (e.g., whale_init_dag `op_kwargs` parameter : `count=10000`) are too large.  
> - **Temporarily reduce block count or date range** for testing (e.g., `count=10`).  
> - Edit the DAG file (the *.py DAG python scripts) directly to adjust these parameters.


#### 🔁 **Periodic Update DAGs** (Scheduled later)
| DAG | Purpose |
|-----|--------|
| `batch_update_price_and_news` | Pings live APIs to refresh price/news data; re-runs sentiment analysis |
| `batch_update_whale` | Fetches the **latest confirmed block**, processes new whale transactions |

> ✅ **Good to know**: These are lightweight and safe to run frequently (e.g., hourly).

---

### 7. **Notes & Next Steps**

#### 🕒 **Scheduling & Parameters Are Flexible**
- **DAG schedules** (e.g., `schedule_interval="0 * * * *"`) can be changed later, I didnt check to ensure all the DAGs are scheduled correctly eg. news and price how often to do the update because i was focusing on making sure every thing runs. Can tweak and adjust later
- **Runtime parameters** like `num_blocks`, `lookback_days`, or API endpoints are defined in each DAG using `op_kwargs`. Adjust them if the dags take too long to run, you should monitor based on the logs


#### 📌 **ML Training Consideration (Future Step)**
- To train models, likely need **more historical data** than the default init DAGs provide.

---

### 🔜 **What’s Next?**
Once Airflow is running and initial data is loaded, the next phase is:

1. **Write an ML pipeline script** (to be scheduled by a new DAG) that:
   - Pulls aligned data windows from **price**, **news**, **whale**, and **on-chain** tables
   - Preprocesses and merges features
   - Trains a model
   - Evaluates performance
   - Then we can display on the dashboard

2. **Create `ml_training_dag.py`** in `airflow/dags/` to orchestrate this workflow.
