1. ensure you have the .env file set up using the env.example

2. ensure within project you have an airflow directory and the following subdirectories
    - must have `docker-compose.yml`, `Dockerfile` and `.env` all in the same directory (or just leave in root)
```bash
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
    │   ├── price_pipeline_dag.py
    │   └── ...
    │
    ├── logs/
    │   ├── scheduler/
    │   ├── worker/
    │   └── ...
    │
    ├── plugins/
    │   └── ...
    │
    └── config/
        └── ...       
```

3. Building the custom airflow image
```bash
docker build -t "bt3107-project" .
```

4. docker compose up with airflow-init
- So this service:
    - Runs database migrations (airflow db migrate) → sets up Airflow’s metadata tables in Postgres.
    - Creates an admin user (airflow users create ...) → so you can log in to the UI.
    - Does NOT restart (restart: "no") → it’s a one-time setup task.
    - Exits when done.

```bash
docker-compose up airflow-init
#or 
docker compose up airflow-init
# should see exit status 0 meaning run was successful
```

5. Spin up the network of containers
```bash
docker-compose up -d
# or
docker compose up -d
```

6. Access the webserver at localhost:8080
    - under DAGs should be able to search for all the DAGs within ./airflow/dags
    - user: airflow
    - password: airflow
