# Infrastructure & Operations (`infra`)

Infrastructure definitions, Docker configurations, and container orchestration templates for RepoPilot AI.

## Responsibilities
- **Container Orchestration**: `docker-compose.yml` defining the local development stack:
  - `web`: React frontend development server or production Nginx container.
  - `api`: FastAPI backend container.
  - `worker`: Background task worker container.
  - `db`: PostgreSQL database with `pgvector` extension enabled.
  - `redis`: Redis instance for message brokering and background job management.
- **Dockerfiles**: Production multi-stage Docker build files for services.
- **Environment & Deployment Scripts**: Configurations and scripts for CI/CD and deployment environments.

