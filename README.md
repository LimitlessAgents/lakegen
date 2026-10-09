<p align="center">
  <img src="static/logo.png" alt="LakeGen logo" width="180" />
</p>

<h1 align="center">LakeGen</h1>

<p align="center">
  <strong>The AI agent for your lakehouse.</strong>
</p>

LakeGen is an AI layer for managing lakehouses. It understands your data
environment, reasons across operational context, and uses lakehouse-native
tools to investigate problems and carry out work.

<video src="static/videos/product_demo.mp4" controls width="100%" title="LakeGen product demo"></video>

> If the preview is unavailable, [watch the product demo](static/videos/product_demo.mp4).

**Navigate:** [Overview](#overview) ·
[What it helps you do](#what-lakegen-helps-you-do) ·
[Development](#development) · [Project status](#project-status) ·
[Contributing](#contributing) · [License](#license)

## Overview

LakeGen provides a conversational control plane over
[Apache Iceberg™](https://iceberg.apache.org/). It combines catalog-aware tools,
an agent runtime, and a streamed web interface so teams can understand and
operate their lakehouse through one consistent workflow.

Supported catalog backends:

- AWS Glue
- Apache Iceberg™ REST
- SQL-backed catalogs

## What LakeGen helps you do

- **Understand your lakehouse** — get answers grounded in the structure and
  live metadata of your data environment.
- **Investigate issues faster** — examine tables, partitions, manifests, files,
  and references without navigating several specialized tools.
- **Trace how data changed** — follow snapshots and table history to understand
  what changed, when it changed, and what state came before.
- **Preserve operational context** — continue work across turns without
  repeatedly explaining your catalog or the investigation.
- **Work consistently across catalogs** — use the same workflow with AWS Glue,
  Apache Iceberg™ REST, and SQL-backed catalogs.


## Quickstart

The recommended path runs the complete stack with Docker Compose.

### 1. Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- An OpenAI or OpenAI-compatible API key

### 2. Configure inference

From the repository root:

```bash
cp .env.example .env
```

Set your key in `.env`:

```dotenv
OPENAI_API_KEY=your-api-key
```

For another OpenAI-compatible provider, also set `OPENAI_BASE_URL`.

### 3. Start LakeGen

```bash
docker compose up -d
```

Docker starts PostgreSQL, the FastAPI service, and the web application. Once
the services are healthy, open [http://localhost:8080](http://localhost:8080).

Your PostgreSQL data remains in the `lakegen_pg_data` Docker volume.

## Development

Run the API and web application on the host when you need hot reload or local
debugging.

**Requirements:** Python 3.13+, [uv](https://docs.astral.sh/uv/), Node.js,
npm, PostgreSQL, and an inference API key.

1. Copy `.env.example` to `.env`.
2. Set `OPENAI_API_KEY` and `LAKEGEN_DATABASE_URL`.
3. Start the API from the repository root:

   ```bash
   uv sync
   uv run uvicorn lakegen.api.app:app --reload
   ```

4. Start the web application in a second terminal:

   ```bash
   cd apps/web
   npm install
   npm run dev
   ```

Open [http://localhost:5173](http://localhost:5173). The API runs at
[http://localhost:8000](http://localhost:8000), with health status available
at [`/health`](http://localhost:8000/health). Vite proxies `/v1` and `/health`
to the API during development.

## Project status

The current release supports read-only lakehouse investigation, persistent
conversational context, streamed agent execution, and PostgreSQL-backed
catalog and turn persistence.

## Contributing

Contributions, bug reports, and design proposals are welcome. To keep work
coordinated, all changes begin with a GitHub issue and maintainer approval
before implementation.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

LakeGen is available under the [MIT License](LICENSE).