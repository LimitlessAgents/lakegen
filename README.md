<p align="center">
  <img src="static/logo.png" alt="LakeGen logo" width="180" />
</p>

<h1 align="center">LakeGen</h1>

<p align="center">
  An AI-powered operator for modern lakehouses.
</p>

LakeGen turns natural-language requests into lakehouse operations. Instead of
switching between catalog consoles, SQL clients, and infrastructure tools,
teams can connect a catalog and use one conversational control plane to
understand and operate their lakehouse.

LakeGen currently focuses on [Apache Iceberg](https://iceberg.apache.org/) and
supports AWS Glue, Iceberg REST, and SQL-backed catalogs.

> [!IMPORTANT]
> LakeGen is an early-stage project under active development. APIs and workflows
> may change, and the current release is intended for local development and
> evaluation rather than production deployment.

## Why LakeGen

Operating a lakehouse requires detailed knowledge of catalogs, namespaces,
storage layouts, and vendor-specific interfaces. LakeGen provides an
intelligent operational layer over that infrastructure while preserving the
underlying Iceberg model.

- **Natural-language operations** — interact with lakehouse infrastructure
  through a conversational workflow.
- **Apache Iceberg intelligence** — understand tables, schemas, snapshots,
  partitions, manifests, references, and history.
- **Multiple catalog backends** — connect AWS Glue, Iceberg REST, or SQL
  catalogs through a consistent interface.
- **Streaming responses** — receive agent progress and results through
  Server-Sent Events (SSE).
- **OpenAI-compatible inference** — use OpenAI or another compatible model
  provider.
- **Credential-aware connections** — keep catalog configuration and secrets
  separate from the agent workflow.

## How it works

LakeGen combines a React web application with a FastAPI backend, an agentic
runtime, and PyIceberg catalog integrations.

```text
Web interface → FastAPI and SSE → Agent runtime → PyIceberg → Iceberg catalog
                                  ↓
                           PostgreSQL history
```

The agent interprets a request, selects the appropriate read-only tool, queries
the active catalog, and returns the result as a streamed conversation. This
keeps the user experience simple while exposing Iceberg's metadata model when
more detail is needed.

## Quickstart

### Docker

**Prerequisites:** [Docker](https://docs.docker.com/get-docker/) with Compose
v2 and an OpenAI-compatible inference API key.

Copy [`.env.example`](.env.example) to `.env`, set `OPENAI_API_KEY`, then run
`docker compose up -d` from the repository root.

Open [http://localhost:8080](http://localhost:8080).

### Manual development

For debugging with hot reload, run the API and web app on the host instead of
Compose.

**Prerequisites:** Python 3.13+, [uv](https://docs.astral.sh/uv/), Node.js and
npm, PostgreSQL, and an inference API key.

In `.env`, set `OPENAI_API_KEY` and `LAKEGEN_DATABASE_URL` (see
[`.env.example`](.env.example)). Optional: `OPENAI_BASE_URL` for OpenRouter or
another compatible provider.

API (repo root):

```bash
uv sync
uvicorn lakegen.api.app:app --reload
```

Web (second terminal):

```bash
cd apps/web && npm install && npm run dev
```

UI: [http://localhost:5173](http://localhost:5173). API:
[http://localhost:8000](http://localhost:8000) (`GET /health`). Vite proxies
`/v1` and `/health` to the API.

## Project status

The current release provides read-only metadata exploration, local session
management, streamed agent turns, and PostgreSQL-backed turn persistence.
Authentication is designed for local development and must be replaced before
LakeGen is used in a shared or multi-tenant environment.

## Contributing

Contributions, bug reports, and design proposals are welcome. To keep work
coordinated, all changes begin with a GitHub issue and maintainer approval
before implementation.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

LakeGen is available under the [MIT License](LICENSE).