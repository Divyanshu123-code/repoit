# Infrastructure & Operations (`infra`)

Infrastructure definitions, Docker configurations, and container orchestration templates for RepoPilot AI.

## Docker Compose Stack

The stack is defined in `docker-compose.yml` at the repository root:

| Service | Image / Build | Port | Healthcheck | Role |
|---|---|---|---|---|
| `api` | `apps/api/Dockerfile` | 8000 | `GET /healthz` | FastAPI backend |
| `worker` | `apps/worker/Dockerfile` | — | Process alive | Background ingestion & scan worker |
| `web` | `apps/web/Dockerfile` | 5173 | `wget http://localhost:80/` | Web UI shell (Nginx) |
| `postgres` | `pgvector/pgvector:pg16` | 5432 | `pg_isready` | PostgreSQL with pgvector extension |
| `redis` | `redis:7-alpine` | 6379 | `redis-cli ping` | Task broker & cache |

## Running the Stack

```bash
# Start all services with logs
docker compose up --build

# Start in background
docker compose up -d

# Verify service health status
docker compose ps

# Tail API service logs
docker compose logs -f api

# Stop and clean up containers
docker compose down
```
