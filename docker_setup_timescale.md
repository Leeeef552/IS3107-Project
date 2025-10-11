## pull docker image
```bash
docker pull timescale/timescaledb-ha:pg17
```

## spin up container to run the timescale instance
```bash
docker run -d --name timescaledb -p 5432:5432 -e POSTGRES_PASSWORD=pass timescale/timescaledb-ha:pg17
```
