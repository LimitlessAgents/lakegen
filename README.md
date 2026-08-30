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

### Prerequisites

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js and npm
- A running PostgreSQL instance
- Access to an OpenAI-compatible inference API

Clone the repository, then create a `.env` file in the project root:

```dotenv
OPENAI_API_KEY=your-api-key
LAKEGEN_DATABASE_URL=postgresql://user:password@localhost:5432/lakegen

# Optional when using OpenRouter or another compatible provider
OPENAI_BASE_URL=https://your-provider.example/v1
```

Install the backend dependencies and start the API:

```bash
uv sync
uvicorn lakegen.api.app:app --reload
```

In a second terminal, start the web application:

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173), add a catalog, and begin a
conversation. The API is available on port `8000`, and its health endpoint is
`GET /health`.

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