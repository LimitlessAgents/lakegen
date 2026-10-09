<p align="center">
  <img src="static/logo.png" alt="LakeGen logo" width="160" />
</p>

<h1 align="center">LakeGen</h1>

<p align="center">
  <strong>The AI agent for your lakehouse.</strong><br />
  Understand your data environment, preserve operational context, and carry
  out lakehouse work through one interface.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13%2B-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python 3.13+" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&amp;logo=docker&amp;logoColor=white" alt="Docker Compose" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-2F855A?style=flat-square" alt="MIT License" /></a>
</p>

<p align="center">
  <a href="#overview">Overview</a> ·
  <a href="#what-lakegen-helps-you-do">What it helps you do</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#development">Development</a> ·
  <a href="#project-status">Status</a> ·
  <a href="#contributing">Contributing</a>
</p>

---

## Overview

LakeGen is an AI layer for managing lakehouses built on
[Apache Iceberg™](https://iceberg.apache.org/). It combines lakehouse-aware
tools, an agent runtime, and a streamed web interface so teams can investigate,
understand, and operate their data environment through one consistent workflow.

<p align="center">
  <strong>AWS Glue</strong> &nbsp;·&nbsp;
  <strong>Apache Iceberg™ REST</strong> &nbsp;·&nbsp;
  <strong>SQL-backed catalogs</strong>
</p>

## What LakeGen helps you do

<table>
  <tr>
    <td width="50%" valign="top">
      <strong>Understand your lakehouse</strong><br />
      Get answers grounded in the structure and live state of your data
      environment.
    </td>
    <td width="50%" valign="top">
      <strong>Investigate issues faster</strong><br />
      Examine tables, partitions, manifests, files, and references without
      moving between specialized tools.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <strong>Trace how data changed</strong><br />
      Follow snapshots and table history to understand what changed and what
      state came before.
    </td>
    <td width="50%" valign="top">
      <strong>Preserve operational context</strong><br />
      Continue work across turns without repeatedly explaining your catalog or
      investigation.
    </td>
  </tr>
</table>

## Quickstart

> [!TIP]
> This path runs the complete LakeGen stack. You only need Docker and an
> inference API key.

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

Docker starts PostgreSQL, the API, and the web application.

> [!IMPORTANT]
> LakeGen is ready at [http://localhost:8080](http://localhost:8080) once the
> services are healthy.

To stop LakeGen, run `docker compose down`. PostgreSQL data remains in the
`lakegen_pg_data` Docker volume.

## Development

<details>
<summary><strong>Run LakeGen locally with hot reload</strong></summary>

<br />

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

</details>

## Project status

> [!NOTE]
> The current release supports read-only lakehouse investigation, persistent
> conversational context, streamed agent execution, and PostgreSQL-backed
> catalog and turn persistence.

## Contributing

Contributions, bug reports, and design proposals are welcome. To keep work
coordinated, all changes begin with a GitHub issue and maintainer approval
before implementation.

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

## License

LakeGen is available under the [MIT License](LICENSE).