## pull docker image

```bash
docker pull timescale/timescaledb:latest-pg15
```

## spin up container to run the timescale instance

```bash
docker run -d --name timescaledb -p 5432:5432 -e POSTGRES_PASSWORD=password timescale/timescaledb:latest-pg15
```
